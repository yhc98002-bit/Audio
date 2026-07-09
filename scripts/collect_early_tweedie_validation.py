"""Collect Early-Tweedie BoN validation shards.

This script is inference/evaluation only. It reads prompt manifests and gate_v2
draft policy, samples ACE-Step candidates, records final full-generation metrics
and early Tweedie decoded metrics, and writes isolated shard artifacts. It does
not launch training, held-out evaluation workflows, Phase D, human evaluation,
or pruning+RL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
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


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
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
    rows: list[dict[str, Any]] = []
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


def _require_visible_gpu() -> None:
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if not visible:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must be set for shard collection")
    visible_ids = [x.strip() for x in visible.split(",") if x.strip()]
    if len(visible_ids) != 1:
        raise RuntimeError(f"expected one visible GPU per shard, got CUDA_VISIBLE_DEVICES={visible!r}")
    int(visible_ids[0])


def _pick_sigma_index(target: float, sigmas: list[float]) -> int:
    return min(range(len(sigmas)), key=lambda k: abs(float(sigmas[k]) - float(target)))


def _finite_metric(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _score_direct_axes(
    reward_models: list[Any],
    waveform: torch.Tensor,
    sample_rate: int,
    prompt: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rm in reward_models:
        axis = getattr(rm, "axis", type(rm).__name__)
        try:
            value = rm.score(waveform, sample_rate, prompt).value
        except Exception as exc:  # noqa: BLE001
            out[f"{axis}_error"] = f"{type(exc).__name__}: {exc}"
            out[axis] = None
            continue
        out[axis] = _finite_metric(value)
    return out


def _score_common_metrics(
    *,
    reward_models: list[Any],
    waveform: torch.Tensor,
    sample_rate: int,
    prompt: Any,
    gate_policy: dict[str, Any],
) -> dict[str, Any]:
    from mprm.rewards.clap import ClapReward
    from mprm.rewards.perturbations import perturbation_set
    from mprm.rewards.probes import anti_hacking_probes, probe_floors
    from mprm.rewards.robust_lcb import robust_lcb

    direct = _score_direct_axes(reward_models, waveform, sample_rate, prompt)
    clap = next((rm for rm in reward_models if isinstance(rm, ClapReward)), None)
    probe = anti_hacking_probes(waveform, sample_rate, prompt, clap=clap)
    lcb = robust_lcb(
        waveform,
        sample_rate,
        prompt,
        reward_models=reward_models,
        perturbations=perturbation_set(list(gate_policy["perturbations"])),
        probe_scores=probe,
        lambda_probe=dict(gate_policy["lambda_probe"]),
        probe_floors=probe_floors(),
        beta_robust=float(gate_policy["beta_robust"]),
    )
    out = dict(direct)
    out.update(
        {
            "common_robust_lcb": float(lcb.value),
            "common_mean_cells": float(lcb.mean_cells),
            "common_std_cells": float(lcb.std_cells),
            "common_probe_penalty": float(lcb.probe_penalty),
        }
    )
    for axis, value in lcb.per_axis.items():
        out[f"robust_axis_{axis}"] = _finite_metric(value)
    for name, value in probe.items():
        out[f"probe_{name}"] = _finite_metric(value)
    return out


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    rows = payload.get("prompts")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"{path}: expected non-empty prompts list")
    return rows


def _load_prompt_rows(manifest_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    sources = sorted({str(row["prompt_source"]) for row in manifest_rows})
    loaded: dict[str, dict[str, dict[str, Any]]] = {
        source: _load_jsonl_by_id(REPO_ROOT / source) for source in sources
    }
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in manifest_rows:
        source = str(row["prompt_source"])
        prompt_id = str(row["prompt_id"])
        if prompt_id not in loaded[source]:
            raise RuntimeError(f"prompt {prompt_id} missing from {source}")
        prompt_row = dict(loaded[source][prompt_id])
        prompt_row["_manifest_split"] = row.get("split")
        prompt_row["_manifest_index"] = row.get("manifest_index")
        out[(source, prompt_id)] = prompt_row
    return out


def collect(args: argparse.Namespace) -> int:
    _require_visible_gpu()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    from mprm.common.config import load_config
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.launch_baseline import (
        _assert_reward_axes_match_policy,
        _build_reward_models,
        load_gate_eval_policy,
    )

    gate_policy, gate_hash = load_gate_eval_policy(REPO_ROOT / args.gate_policy)
    baseline_cfg = load_config(REPO_ROOT / args.reward_config)
    reward_models = _build_reward_models(baseline_cfg.reward)
    _assert_reward_axes_match_policy(reward_models, gate_policy)

    manifest_rows = _load_manifest(REPO_ROOT / args.manifest)
    selected_manifest = manifest_rows[args.prompt_offset : args.prompt_offset + args.n_prompts]
    prompt_rows = _load_prompt_rows(selected_manifest)
    prompts = []
    prompt_meta = []
    for row in selected_manifest:
        source = str(row["prompt_source"])
        prompt_id = str(row["prompt_id"])
        prompt_row = prompt_rows[(source, prompt_id)]
        prompts.append(_prompt_from_row(prompt_row))
        strata = dict(prompt_row.get("strata") or {})
        prompt_meta.append(
            {
                "prompt_id": prompt_id,
                "split": row.get("split"),
                "prompt_source": source,
                "manifest_index": row.get("manifest_index"),
                "has_lyrics": bool((prompt_row.get("lyrics") or "").strip()),
                "vocal_stratum": "vocal" if (prompt_row.get("lyrics") or "").strip() else "instrumental",
                "genre": strata.get("genre"),
                "language": strata.get("language"),
                "lyric_density": strata.get("lyric_density"),
                "length_bin": strata.get("length_bin"),
            }
        )

    summary: dict[str, Any] = {
        "schema_version": "early_tweedie_validation_collection_v1",
        "generated_at_utc": _now_utc(),
        "output_dir": str(args.output_dir),
        "manifest": args.manifest,
        "manifest_sha256": _sha256(REPO_ROOT / args.manifest),
        "prompt_offset": int(args.prompt_offset),
        "n_prompts": len(prompts),
        "prompt_ids": [p.prompt_id for p in prompts],
        "bon_n": int(args.bon_n),
        "target_sigmas": [float(x) for x in args.target_sigmas],
        "gate_policy": args.gate_policy,
        "gate_policy_hash": gate_hash,
        "reward_config": args.reward_config,
        "reward_axes": [getattr(rm, "axis", "<unknown>") for rm in reward_models],
        "sampler": {
            "cfg_scale": float(args.cfg_scale),
            "infer_steps": int(args.infer_steps),
            "cfg_type": args.cfg_type,
            "guidance_interval": float(args.guidance_interval),
            "use_erg_tag": False,
            "use_erg_lyric": False,
            "use_erg_diffusion": False,
        },
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "nvidia_smi_before": _nvidia_snapshot(),
        "command": " ".join(sys.argv),
        "status": "running",
        "safety": {
            "training_launched": False,
            "held_out_workflow_launched": False,
            "phase_d_launched": False,
            "human_eval_launched": False,
            "pruning_rl_launched": False,
            "gate_v1_modified": False,
            "gate_v2_activated": False,
            "reward_sigma_prompt_credit_definitions_changed": False,
        },
    }
    (args.output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    model = AceStepModel()
    raw_path = args.output_dir / "candidate_records.jsonl"
    t0 = time.time()
    n_records = 0
    with raw_path.open("w", encoding="utf-8") as f:
        for local_prompt_index, (prompt, meta) in enumerate(zip(prompts, prompt_meta)):
            manifest_index = int(meta["manifest_index"])
            for cand_idx in range(int(args.bon_n)):
                seed = int(args.seed_base) + manifest_index * 1000 + cand_idx
                seed_everything(seed)
                start = time.time()
                res = model.sample(
                    prompt,
                    seed=seed,
                    cfg_scale=float(args.cfg_scale),
                    steps=int(args.infer_steps),
                    return_trajectory=True,
                    extras={
                        "cfg_type": args.cfg_type,
                        "guidance_interval": float(args.guidance_interval),
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
                final_scores = _score_common_metrics(
                    reward_models=reward_models,
                    waveform=res.waveform,
                    sample_rate=res.sample_rate,
                    prompt=prompt,
                    gate_policy=gate_policy,
                )
                flat: dict[str, Any] = {
                    **meta,
                    "local_prompt_index": local_prompt_index,
                    "candidate_index": cand_idx,
                    "candidate_seed": seed,
                    "sample_rate": int(res.sample_rate),
                    "duration_actual_s": float(res.waveform.shape[-1]) / float(res.sample_rate),
                    "elapsed_seconds": time.time() - start,
                }
                for key, value in final_scores.items():
                    flat[f"final_{key}"] = value
                for target in args.target_sigmas:
                    k = _pick_sigma_index(float(target), traj_sigmas)
                    actual_sigma = float(traj_sigmas[k])
                    z0 = traj[k].to(torch.float32) - actual_sigma * traj_vs[k].to(torch.float32)
                    early_audio = model.decode(z0)
                    early_scores = _score_common_metrics(
                        reward_models=reward_models,
                        waveform=early_audio,
                        sample_rate=res.sample_rate,
                        prompt=prompt,
                        gate_policy=gate_policy,
                    )
                    sigma_key = f"{float(target):.1f}"
                    flat[f"early_{sigma_key}_actual_sigma"] = actual_sigma
                    flat[f"early_{sigma_key}_step_index"] = int(k)
                    flat[f"early_{sigma_key}_cfg_active"] = bool(cfg_flags[k]) if k < len(cfg_flags) else None
                    for key, value in early_scores.items():
                        flat[f"early_{sigma_key}_{key}"] = value
                    # ADSR (2026-06-04): save the early Tweedie-clean decoded audio for the
                    # EVPD-input sigmas (>=0.7) so the early mel-spectrogram can be extracted
                    # offline (CPU). Lower sigmas (0.5/0.3) keep scores only to bound disk.
                    if args.save_audio and float(target) >= 0.7:
                        ea_dir = args.output_dir / "audio" / prompt.prompt_id
                        ea_dir.mkdir(parents=True, exist_ok=True)
                        ea_path = ea_dir / f"candidate_{cand_idx:02d}_seed{seed}_early{sigma_key}.wav"
                        save_audio(ea_path, early_audio, res.sample_rate)
                        flat[f"early_{sigma_key}_audio_path"] = str(ea_path)
                if args.save_audio:
                    audio_dir = args.output_dir / "audio" / prompt.prompt_id
                    audio_dir.mkdir(parents=True, exist_ok=True)
                    audio_path = audio_dir / f"candidate_{cand_idx:02d}_seed{seed}.wav"
                    save_audio(audio_path, res.waveform, res.sample_rate)
                    flat["audio_path"] = str(audio_path)
                f.write(json.dumps(flat, ensure_ascii=True) + "\n")
                f.flush()
                n_records += 1
                if n_records % int(args.progress_every) == 0:
                    elapsed = time.time() - t0
                    print(
                        json.dumps(
                            {
                                "event": "progress",
                                "records": n_records,
                                "elapsed_seconds": elapsed,
                                "records_per_hour": n_records / max(elapsed / 3600.0, 1.0e-9),
                            }
                        ),
                        flush=True,
                    )

    elapsed = time.time() - t0
    summary.update(
        {
            "status": "PASS",
            "elapsed_seconds": elapsed,
            "gpu_hours_consumed": elapsed / 3600.0,
            "n_candidate_records": n_records,
            "records_path": str(raw_path),
            "nvidia_smi_after": _nvidia_snapshot(),
        }
    )
    (args.output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output_dir": str(args.output_dir), "records": n_records}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", default="orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
    parser.add_argument("--prompt-offset", type=int, default=0)
    parser.add_argument("--n-prompts", type=int, default=2)
    parser.add_argument("--bon-n", type=int, default=2)
    parser.add_argument("--target-sigmas", type=float, nargs="+", default=list(DEFAULT_SIGMAS))
    parser.add_argument("--seed-base", type=int, default=2026052700)
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-steps", type=int, default=30)
    parser.add_argument("--cfg-type", default="cfg")
    parser.add_argument("--guidance-interval", type=float, default=0.5)
    parser.add_argument("--reward-config", default="configs/baselines/r2_bon.yaml")
    parser.add_argument("--gate-policy", default="configs/eval/gate_v2.yaml.draft")
    parser.add_argument("--save-audio", action="store_true")
    parser.add_argument("--progress-every", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        est_candidates = int(args.n_prompts) * int(args.bon_n)
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "manifest": args.manifest,
                    "prompt_offset": args.prompt_offset,
                    "n_prompts": args.n_prompts,
                    "bon_n": args.bon_n,
                    "candidate_count": est_candidates,
                    "target_sigmas": args.target_sigmas,
                    "gate_policy": args.gate_policy,
                },
                indent=2,
            )
        )
        return 0
    return collect(args)


if __name__ == "__main__":
    raise SystemExit(main())
