"""Collect and analyze candidate-level Early-Tweedie BoN pruning artifacts.

The collection is isolated under a new output directory. It does not launch
training, pruning+RL, held-out evaluation, Phase D, or human evaluation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SIGMAS = (0.9, 0.8, 0.7)
PRIMARY_AXIS = "aesthetic_pq"


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_prompts(path: Path) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            rows[row["prompt_id"]] = row
    return rows


def _prompt_from_row(row: dict[str, Any]):
    from mprm.data.prompts import Prompt

    return Prompt(
        prompt_id=row["prompt_id"],
        text=row.get("text", ""),
        lyrics=row.get("lyrics"),
        structure_hint=row.get("structure_hint"),
        duration_target=float(row.get("duration_target", 30.0)),
        metadata=row.get("metadata", {}),
        strata=row.get("strata", {}),
    )


def _nvidia_snapshot() -> list[dict[str, Any]]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return []
    rows = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 6:
            continue
        rows.append(
            {
                "index": int(parts[0]),
                "uuid": parts[1],
                "name": parts[2],
                "memory_used_mb": int(parts[3]),
                "memory_total_mb": int(parts[4]),
                "utilization_gpu_percent": int(parts[5]),
            }
        )
    return rows


def _assert_gpu_scope(allowed_gpus: set[int]) -> None:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if not visible:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must be set to one physical GPU in {4,5,6,7}")
    visible_ids = {int(x.strip()) for x in visible.split(",") if x.strip()}
    if not visible_ids or not visible_ids.issubset(allowed_gpus):
        raise RuntimeError(f"CUDA_VISIBLE_DEVICES={visible!r}; expected subset of {sorted(allowed_gpus)}")


def _pick_sigma_index(target: float, sigmas: list[float]) -> int:
    return min(range(len(sigmas)), key=lambda k: abs(float(sigmas[k]) - target))


def _score_all_axes(reward_models: list[Any], waveform: torch.Tensor, sample_rate: int, prompt: Any) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for rm in reward_models:
        axis = getattr(rm, "axis", type(rm).__name__)
        try:
            value = rm.score(waveform, sample_rate, prompt).value
        except Exception as exc:  # noqa: BLE001
            out[axis] = None
            out[f"{axis}_error"] = f"{type(exc).__name__}: {exc}"
            continue
        try:
            value_f = float(value)
        except (TypeError, ValueError):
            value_f = math.nan
        out[axis] = value_f if math.isfinite(value_f) else None
    return out


def _rank_desc(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda row: (float(row.get(key, float("-inf"))), -int(row["candidate_index"])), reverse=True)


def _bottom_indices(items: list[dict[str, Any]], key: str, fraction: float) -> set[int]:
    ordered = sorted(items, key=lambda row: (float(row.get(key, float("inf"))), int(row["candidate_index"])))
    n = max(1, int(math.ceil(len(ordered) * fraction)))
    return {int(row["candidate_index"]) for row in ordered[:n]}


def _analyze_records(records: list[dict[str, Any]], *, primary_axis: str) -> dict[str, Any]:
    by_prompt: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_prompt.setdefault(rec["prompt_id"], []).append(rec)

    sigmas = sorted(
        {
            float(key.split("_")[1])
            for rec in records
            for key in rec
            if key.startswith("early_") and key.endswith(f"_{primary_axis}")
        },
        reverse=True,
    )
    retention: dict[str, Any] = {}
    for sigma in sigmas:
        key = f"{sigma:.1f}"
        top_hits = {1: 0, 2: 0, 4: 0}
        bottom50_fn = 0
        bottom25_fn = 0
        n = 0
        for rows in by_prompt.values():
            if len(rows) < 2:
                continue
            final_ranked = _rank_desc(rows, f"final_{primary_axis}")
            final_winner = int(final_ranked[0]["candidate_index"])
            early_key = f"early_{key}_{primary_axis}"
            if any(row.get(early_key) is None for row in rows):
                continue
            early_ranked = _rank_desc(rows, early_key)
            early_order = [int(row["candidate_index"]) for row in early_ranked]
            n += 1
            for k in top_hits:
                if final_winner in set(early_order[:k]):
                    top_hits[k] += 1
            if final_winner in _bottom_indices(rows, early_key, 0.50):
                bottom50_fn += 1
            if final_winner in _bottom_indices(rows, early_key, 0.25):
                bottom25_fn += 1
        retention[key] = {
            "n_prompts": n,
            "winner_retention_top1": top_hits[1] / n if n else None,
            "winner_retention_top2": top_hits[2] / n if n else None,
            "winner_retention_top4": top_hits[4] / n if n else None,
            "early_bottom50_false_negative": bottom50_fn / n if n else None,
            "early_bottom25_false_negative": bottom25_fn / n if n else None,
        }

    schedule_hits = 0
    regrets: list[float] = []
    selected_scores: list[float] = []
    winner_scores: list[float] = []
    n_schedule = 0
    for rows in by_prompt.values():
        if len(rows) < 2:
            continue
        final_ranked = _rank_desc(rows, f"final_{primary_axis}")
        full_winner = final_ranked[0]
        s09 = f"early_{0.9:.1f}_{primary_axis}"
        s07 = f"early_{0.7:.1f}_{primary_axis}"
        if any(row.get(s09) is None or row.get(s07) is None for row in rows):
            continue
        keep4 = _rank_desc(rows, s09)[:4]
        keep2 = _rank_desc(keep4, s07)[:2]
        selected = _rank_desc(keep2, f"final_{primary_axis}")[0]
        n_schedule += 1
        schedule_hits += int(selected["candidate_index"] == full_winner["candidate_index"])
        selected_score = float(selected[f"final_{primary_axis}"])
        winner_score = float(full_winner[f"final_{primary_axis}"])
        selected_scores.append(selected_score)
        winner_scores.append(winner_score)
        regrets.append(winner_score - selected_score)

    pareto = []
    full_steps = 30.0
    sigma_step = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
    if n_schedule:
        schedule_fraction = (8 * sigma_step["0.9"] + 4 * (sigma_step["0.7"] - sigma_step["0.9"]) + 2 * (full_steps - sigma_step["0.7"])) / (8 * full_steps)
        pareto.append(
            {
                "strategy": "full_bon8",
                "relative_compute_proxy": 1.0,
                "mean_primary_reward": statistics.mean(winner_scores),
                "mean_regret_vs_full_bon8": 0.0,
                "winner_match_rate": 1.0,
            }
        )
        pareto.append(
            {
                "strategy": "sigma0.9_top4_sigma0.7_top2_final_top1",
                "relative_compute_proxy": schedule_fraction,
                "mean_primary_reward": statistics.mean(selected_scores),
                "mean_regret_vs_full_bon8": statistics.mean(regrets),
                "winner_match_rate": schedule_hits / n_schedule,
            }
        )

    return {
        "primary_axis": primary_axis,
        "n_prompts": len(by_prompt),
        "n_candidates": len(records),
        "retention_by_sigma": retention,
        "pruning_schedule": {
            "name": "sigma=0.9 keep top-4, sigma=0.7 keep top-2, final top-1",
            "n_prompts": n_schedule,
            "winner_match_rate": schedule_hits / n_schedule if n_schedule else None,
            "mean_regret_vs_full_bon8": statistics.mean(regrets) if regrets else None,
            "median_regret_vs_full_bon8": statistics.median(regrets) if regrets else None,
        },
        "quality_compute_pareto": pareto,
    }


def _write_report(out_dir: Path, summary: dict[str, Any], analysis: dict[str, Any]) -> None:
    md = out_dir / "EARLY_TWEEDIE_PRUNING_RETROSPECTIVE.md"
    lines = [
        "# Early-Tweedie BoN Pruning Retrospective",
        "",
        f"Generated UTC: `{summary['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "Candidate-level BoN-8 diagnostic on dev prompts. This run collects final audio rewards and early Tweedie reward estimates at sigma 0.9/0.8/0.7 for each candidate. No training or pruning+RL was launched.",
        "",
        "## Run Metadata",
        "",
        "| field | value |",
        "|---|---|",
        f"| output_dir | `{summary['output_dir']}` |",
        f"| prompt_source | `{summary['prompt_source']}` |",
        f"| prompt_ids_source | `{summary['prompt_ids_source']}` |",
        f"| n_prompts | {summary['n_prompts']} |",
        f"| bon_n | {summary['bon_n']} |",
        f"| target_sigmas | {summary['target_sigmas']} |",
        f"| primary_axis | {analysis['primary_axis']} |",
        f"| cuda_visible_devices | `{summary['cuda_visible_devices']}` |",
        f"| elapsed_seconds | {summary['elapsed_seconds']:.3f} |",
        f"| gpu_hours_consumed | {summary['gpu_hours_consumed']:.6f} |",
        "",
        "## Winner Retention",
        "",
        "| sigma | n | top1 | top2 | top4 | bottom50_fn | bottom25_fn |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for sigma, row in analysis["retention_by_sigma"].items():
        lines.append(
            f"| {sigma} | {row['n_prompts']} | {row['winner_retention_top1']:.3f} | "
            f"{row['winner_retention_top2']:.3f} | {row['winner_retention_top4']:.3f} | "
            f"{row['early_bottom50_false_negative']:.3f} | {row['early_bottom25_false_negative']:.3f} |"
        )
    sched = analysis["pruning_schedule"]
    lines.extend([
        "",
        "## Pruning Schedule",
        "",
        "| schedule | n | winner_match_rate | mean_regret | median_regret |",
        "|---|---:|---:|---:|---:|",
        f"| {sched['name']} | {sched['n_prompts']} | {sched['winner_match_rate']:.3f} | {sched['mean_regret_vs_full_bon8']:.6f} | {sched['median_regret_vs_full_bon8']:.6f} |",
        "",
        "## Quality-vs-Compute Pareto",
        "",
        "| strategy | relative_compute_proxy | mean_primary_reward | mean_regret_vs_full_bon8 | winner_match_rate |",
        "|---|---:|---:|---:|---:|",
    ])
    for row in analysis["quality_compute_pareto"]:
        lines.append(
            f"| {row['strategy']} | {row['relative_compute_proxy']:.3f} | "
            f"{row['mean_primary_reward']:.6f} | {row['mean_regret_vs_full_bon8']:.6f} | "
            f"{row['winner_match_rate']:.3f} |"
        )
    lines.extend([
        "",
        "## Caveats",
        "",
        "- This is a dev diagnostic, not held-out evidence.",
        "- The compute proxy counts sampler step fractions and ignores reward-model overhead.",
        "- Final ranking uses the existing R2 primary axis `aesthetic_pq`; all axis scores are retained in JSONL.",
    ])
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> int:
    _assert_gpu_scope({4, 5, 6, 7})
    args.output_dir.mkdir(parents=True, exist_ok=False)

    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from mprm.common.config import load_config
    from scripts.launch_baseline import _build_reward_models

    baseline_cfg = load_config(REPO_ROOT / "configs/baselines/r2_bon.yaml")
    reward_models = _build_reward_models(baseline_cfg.reward)

    prompt_rows = _load_prompts(REPO_ROOT / args.prompt_source)
    prompt_ids_payload = _load_json(REPO_ROOT / args.prompt_ids_source)
    all_prompt_ids = prompt_ids_payload["formal_prompt_ids"]
    prompt_ids = all_prompt_ids[args.prompt_offset : args.prompt_offset + args.n_prompts]
    missing = [pid for pid in prompt_ids if pid not in prompt_rows]
    if missing:
        raise RuntimeError(f"prompt IDs missing from prompt source: {missing}")
    prompts = [_prompt_from_row(prompt_rows[pid]) for pid in prompt_ids]

    summary: dict[str, Any] = {
        "schema_version": "early_tweedie_bon_collection_v1",
        "generated_at_utc": _now_utc(),
        "output_dir": str(args.output_dir),
        "prompt_source": args.prompt_source,
        "prompt_ids_source": args.prompt_ids_source,
        "prompt_ids": prompt_ids,
        "prompt_offset": int(args.prompt_offset),
        "n_prompts": len(prompts),
        "bon_n": args.bon_n,
        "target_sigmas": list(args.target_sigmas),
        "primary_axis": PRIMARY_AXIS,
        "sampler": {
            "cfg_scale": args.cfg_scale,
            "infer_steps": args.infer_steps,
            "cfg_type": args.cfg_type,
            "guidance_interval": args.guidance_interval,
        },
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "nvidia_smi_before": _nvidia_snapshot(),
        "command": " ".join(sys.argv),
        "status": "running",
    }
    (args.output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    model = AceStepModel()
    flat_records: list[dict[str, Any]] = []
    raw_path = args.output_dir / "candidate_records.jsonl"
    t0 = time.time()
    with raw_path.open("w", encoding="utf-8") as f:
        for p_idx, prompt in enumerate(prompts):
            for cand_idx in range(args.bon_n):
                global_prompt_index = int(args.prompt_offset) + p_idx
                seed = int(args.seed_base) + global_prompt_index * 1000 + cand_idx
                seed_everything(seed)
                start = time.time()
                res = model.sample(
                    prompt,
                    seed=seed,
                    cfg_scale=args.cfg_scale,
                    steps=args.infer_steps,
                    return_trajectory=True,
                    extras={
                        "cfg_type": args.cfg_type,
                        "guidance_interval": args.guidance_interval,
                        "use_erg_tag": False,
                        "use_erg_lyric": False,
                        "use_erg_diffusion": False,
                    },
                )
                traj = res.trajectory or []
                traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
                traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
                cfg_flags = (res.extras or {}).get("trajectory_cfg_active", [])
                if not traj or not traj_sigmas or not traj_vs:
                    raise RuntimeError("trajectory capture missing latents/sigmas/model_outputs")
                final_scores = _score_all_axes(reward_models, res.waveform, res.sample_rate, prompt)
                early_scores: dict[str, Any] = {}
                for target in args.target_sigmas:
                    k = _pick_sigma_index(float(target), traj_sigmas)
                    actual_sigma = float(traj_sigmas[k])
                    z0 = traj[k].to(torch.float32) - actual_sigma * traj_vs[k].to(torch.float32)
                    early_audio = model.decode(z0)
                    scores = _score_all_axes(reward_models, early_audio, res.sample_rate, prompt)
                    early_scores[f"{float(target):.1f}"] = {
                        "target_sigma": float(target),
                        "actual_sigma": actual_sigma,
                        "step_index": int(k),
                        "cfg_active": bool(cfg_flags[k]) if k < len(cfg_flags) else None,
                        "scores": scores,
                    }
                audio_path = None
                if args.save_audio:
                    audio_dir = args.output_dir / "audio" / prompt.prompt_id
                    audio_dir.mkdir(parents=True, exist_ok=True)
                    audio_path = audio_dir / f"candidate_{cand_idx:02d}_seed{seed}.wav"
                    save_audio(audio_path, res.waveform, res.sample_rate)
                rec = {
                    "prompt_id": prompt.prompt_id,
                    "prompt_index": p_idx,
                    "global_prompt_index": global_prompt_index,
                    "candidate_index": cand_idx,
                    "candidate_seed": seed,
                    "sample_rate": int(res.sample_rate),
                    "duration_actual_s": float(res.waveform.shape[-1]) / float(res.sample_rate),
                    "elapsed_seconds": time.time() - start,
                    "final_scores": final_scores,
                    "early_scores": early_scores,
                    "audio_path": str(audio_path) if audio_path else None,
                }
                flat = {
                    "prompt_id": rec["prompt_id"],
                    "global_prompt_index": rec["global_prompt_index"],
                    "candidate_index": rec["candidate_index"],
                    "candidate_seed": rec["candidate_seed"],
                    **{f"final_{k}": v for k, v in final_scores.items() if not k.endswith("_error")},
                }
                for sigma_key, payload in early_scores.items():
                    for axis, value in payload["scores"].items():
                        if not axis.endswith("_error"):
                            flat[f"early_{sigma_key}_{axis}"] = value
                    flat[f"early_{sigma_key}_actual_sigma"] = payload["actual_sigma"]
                    flat[f"early_{sigma_key}_step_index"] = payload["step_index"]
                    flat[f"early_{sigma_key}_cfg_active"] = payload["cfg_active"]
                f.write(json.dumps(flat) + "\n")
                f.flush()
                flat_records.append(flat)

    elapsed = time.time() - t0
    analysis = _analyze_records(flat_records, primary_axis=PRIMARY_AXIS)
    summary.update(
        {
            "status": "PASS",
            "elapsed_seconds": elapsed,
            "gpu_hours_consumed": elapsed / 3600.0,
            "nvidia_smi_after": _nvidia_snapshot(),
            "raw_records_path": str(raw_path),
            "analysis_path": str(args.output_dir / "EARLY_TWEEDIE_PRUNING_RETROSPECTIVE.json"),
            "report_path": str(args.output_dir / "EARLY_TWEEDIE_PRUNING_RETROSPECTIVE.md"),
        }
    )
    result = {"summary": summary, "analysis": analysis}
    (args.output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "EARLY_TWEEDIE_PRUNING_RETROSPECTIVE.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    _write_report(args.output_dir, summary, analysis)
    print(json.dumps({"status": "PASS", "output_dir": str(args.output_dir), "gpu_hours": elapsed / 3600.0}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--n-prompts", type=int, default=32)
    parser.add_argument("--prompt-offset", type=int, default=0)
    parser.add_argument("--bon-n", type=int, default=8)
    parser.add_argument("--prompt-source", default="configs/prompts/dev.jsonl")
    parser.add_argument("--prompt-ids-source", default="orbit-research/PHASE_B1_RELIABILITY_PROMPTS.json")
    parser.add_argument("--target-sigmas", type=float, nargs="+", default=list(DEFAULT_SIGMAS))
    parser.add_argument("--seed-base", type=int, default=2026052400)
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-steps", type=int, default=30)
    parser.add_argument("--cfg-type", default="cfg")
    parser.add_argument("--guidance-interval", type=float, default=0.5)
    parser.add_argument("--save-audio", action="store_true")
    parser.add_argument("--dry-run-cost", action="store_true", help="Print cost estimate and exit without model loading.")
    args = parser.parse_args()

    est_gpu_h_32 = 4.0
    est_gpu_h = est_gpu_h_32 * (args.n_prompts / 32.0) * (args.bon_n / 8.0) * (args.infer_steps / 30.0)
    if args.dry_run_cost:
        print(
            json.dumps(
                {
                    "status": "cost_estimate_only",
                    "estimated_gpu_hours": est_gpu_h,
                    "basis": "H3 corrected held-out v2: 256 trajectory samples at sigma 0.7/0.6 cost about 4 GPU-h; this run has n_prompts*bon_n trajectory samples.",
                    "n_prompts": args.n_prompts,
                    "prompt_offset": args.prompt_offset,
                    "bon_n": args.bon_n,
                    "infer_steps": args.infer_steps,
                    "target_sigmas": args.target_sigmas,
                },
                indent=2,
            )
        )
        return 0
    if est_gpu_h > 20.0:
        raise SystemExit(f"estimated GPU-hours {est_gpu_h:.2f} exceeds 20 GPU-h cap")
    return collect(args)


if __name__ == "__main__":
    raise SystemExit(main())
