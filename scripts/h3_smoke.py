"""H3 smoke test — 4 prompts × σ ∈ {0.7, 0.6} × all 6 credit-unit segmenters.

PI directive 2026-05-23 (PM):
  - 4 prompts (2 vocal + 2 instrumental, to exercise D3 lyric_span policy).
  - sigma ∈ {0.7, 0.6} (primary H3 σ per D4).
  - all available credit units (CU-TS, CU-FW, CU-BW, CU-LS, CU-MS, CU-NULL).
  - NO formal H3 verdict.

Purpose: verify the 5 credit-unit modules produce sensible segments on real
Tweedie-clean intermediate audio + final audio. Surface any bugs / surprises
before H3a launches on 64 prompts.

Outputs:
  runs/h3_smoke/h3_smoke_results.json
  runs/h3_smoke/h3_smoke_summary.md
  runs/h3_smoke/launch.log (stdout/stderr)

Do NOT compute formal H3 metrics; do NOT compute per-segment reward scores
in this smoke (that's H3a).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mprm.common.seeding import seed_everything
from mprm.data.prompts import Prompt
from mprm.credit_units import (
    REGISTRY,
    BeatWindowUnit,
    FixedWindowUnit,
    LyricSpanUnit,
    MusicalSectionUnit,
    RandomSectionNullUnit,
    TimestepUnit,
)


SMOKE_PROMPT_IDS = [
    "dev_0000",  # vocal rock — present in formal Phase B.1 prompts
    "dev_0002",  # vocal electronic
    "dev_0001",  # instrumental classical
    "dev_0010",  # instrumental rock
]

SIGMA_TARGETS = {
    0.7: dict(scheduler_sigma_actual=0.7104662656784058, step_index=16, cfg_active=True),
    0.6: dict(scheduler_sigma_actual=0.6143013834953308, step_index=19, cfg_active=True),
}


def load_prompt(jsonl_path: Path, prompt_id: str) -> Prompt:
    with open(jsonl_path) as f:
        for line in f:
            p = json.loads(line)
            if p["prompt_id"] == prompt_id:
                return Prompt(
                    prompt_id=p["prompt_id"],
                    text=p.get("text", ""),
                    lyrics=p.get("lyrics"),
                    structure_hint=p.get("structure_hint"),
                    duration_target=float(p.get("duration_target", 30.0)),
                    metadata=p.get("metadata", {}),
                    strata=p.get("strata", {}),
                )
    raise KeyError(f"prompt_id={prompt_id!r} not found in {jsonl_path}")


def _pick_sigma_index(target: float, traj_sigmas: list[float]) -> int:
    return min(range(len(traj_sigmas)), key=lambda k: abs(traj_sigmas[k] - target))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts-jsonl", default="configs/prompts/dev.jsonl")
    parser.add_argument("--output-dir", default="runs/h3_smoke")
    parser.add_argument("--no-mert", action="store_true", help="Skip MERT and use librosa-only segmentation")
    parser.add_argument("--no-demucs", action="store_true", help="Skip Demucs vocal isolation for lyric_span")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[smoke] H3 smoke test starting; output → {out_dir}", flush=True)

    prompts = [load_prompt(Path(args.prompts_jsonl), pid) for pid in SMOKE_PROMPT_IDS]
    for p in prompts:
        is_instr = bool((p.metadata or {}).get("instrumental", False)) or not p.lyrics
        print(f"  prompt {p.prompt_id} (instrumental={is_instr}): {p.text[:80]!r}", flush=True)

    # Load model + segmenters.
    from mprm.inference.ace_step import AceStepModel
    print("[smoke] loading ACE-Step model", flush=True)
    model = AceStepModel()

    segmenters = {
        "CU-TS": TimestepUnit(),
        "CU-FW": FixedWindowUnit(window_seconds=4.0),
        "CU-BW": BeatWindowUnit(),
        "CU-LS": LyricSpanUnit(use_demucs=not args.no_demucs),
        "CU-MS": MusicalSectionUnit(use_mert=not args.no_mert),
    }
    # Build the null using the same CU-MS instance for consistency.
    segmenters["CU-NULL-rand-section"] = RandomSectionNullUnit(
        underlying_ms_unit=segmenters["CU-MS"], permutation_seed=20260524
    )
    print(f"[smoke] loaded {len(segmenters)} segmenters", flush=True)

    results: dict = {
        "smoke_version": "h3_smoke_v1",
        "timestamp_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "prompts": SMOKE_PROMPT_IDS,
        "sigma_targets": list(SIGMA_TARGETS.keys()),
        "credit_units": list(segmenters.keys()),
        "per_prompt": {},
    }

    t_start = time.time()
    for p_idx, prompt in enumerate(prompts):
        print(f"\n[smoke] prompt {p_idx+1}/{len(prompts)}: {prompt.prompt_id}", flush=True)
        seed = 100 + p_idx
        seed_everything(seed)
        sample_t = time.time()
        try:
            res = model.sample(
                prompt, seed=seed,
                cfg_scale=5.0, steps=30,
                return_trajectory=True,
                extras={"cfg_type": "cfg",
                         "use_erg_tag": False,
                         "use_erg_lyric": False,
                         "use_erg_diffusion": False},
            )
        except Exception as e:  # noqa: BLE001
            print(f"  [smoke] sampling failed: {type(e).__name__}: {e}", flush=True)
            return 1
        print(f"  sampling done in {time.time() - sample_t:.1f}s", flush=True)
        traj = res.trajectory or []
        traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
        traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
        cfg_flags = (res.extras or {}).get("trajectory_cfg_active", [])
        final_audio = res.waveform

        per_sigma_results: dict[str, dict] = {}
        for sigma_target, binding in SIGMA_TARGETS.items():
            k = _pick_sigma_index(sigma_target, traj_sigmas)
            sigma_actual = float(traj_sigmas[k])
            assert abs(sigma_actual - binding["scheduler_sigma_actual"]) < 1e-5
            assert bool(cfg_flags[k]) == binding["cfg_active"]
            v_eff = traj_vs[k]
            z_k = traj[k]
            z0 = z_k.to(torch.float32) - sigma_actual * v_eff.to(torch.float32)
            intermediate_audio = model.decode(z0)
            print(f"  σ={sigma_target} step={k} cfg={cfg_flags[k]} intermediate decoded", flush=True)

            sigma_results: dict[str, dict] = {}
            for unit_id, seg_obj in segmenters.items():
                try:
                    seg_t = time.time()
                    out = seg_obj.segment(intermediate_audio, res.sample_rate, prompt, seed=seed)
                    elapsed = time.time() - seg_t
                    sigma_results[unit_id] = {
                        "applicable": out.applicable,
                        "not_applicable_reason": out.not_applicable_reason,
                        "n_segments": len(out.segments),
                        "total_covered_seconds": out.total_covered_seconds(),
                        "segments": [
                            {"start_s": s.start_s, "end_s": s.end_s, "label": s.label,
                             "duration_s": s.duration()}
                            for s in out.segments[:20]  # cap for log readability
                        ],
                        "metadata": {k: v for k, v in out.metadata.items()
                                     if k not in ("transcript",)},  # transcript may be long
                        "elapsed_seconds": elapsed,
                    }
                    if "transcript" in out.metadata:
                        sigma_results[unit_id]["transcript_preview"] = str(out.metadata["transcript"])[:200]
                    print(f"    {unit_id}: applicable={out.applicable} n_seg={len(out.segments)} "
                          f"elapsed={elapsed:.2f}s", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"    {unit_id}: FAILED — {type(e).__name__}: {e}", flush=True)
                    sigma_results[unit_id] = {
                        "applicable": False,
                        "not_applicable_reason": f"exception: {type(e).__name__}: {e}",
                        "n_segments": 0,
                    }
            per_sigma_results[str(sigma_target)] = sigma_results

        # Also run on the FINAL audio for reference.
        print(f"  segmenting final audio", flush=True)
        final_results: dict[str, dict] = {}
        for unit_id, seg_obj in segmenters.items():
            try:
                out = seg_obj.segment(final_audio, res.sample_rate, prompt, seed=seed)
                final_results[unit_id] = {
                    "applicable": out.applicable,
                    "not_applicable_reason": out.not_applicable_reason,
                    "n_segments": len(out.segments),
                    "total_covered_seconds": out.total_covered_seconds(),
                    "segments": [
                        {"start_s": s.start_s, "end_s": s.end_s, "label": s.label,
                         "duration_s": s.duration()}
                        for s in out.segments[:20]
                    ],
                }
            except Exception as e:  # noqa: BLE001
                final_results[unit_id] = {
                    "applicable": False,
                    "not_applicable_reason": f"exception: {type(e).__name__}",
                    "n_segments": 0,
                }

        is_instrumental = bool((prompt.metadata or {}).get("instrumental", False)) or not prompt.lyrics
        results["per_prompt"][prompt.prompt_id] = {
            "text": prompt.text,
            "is_instrumental": is_instrumental,
            "lyrics_first_line": (prompt.lyrics or "").split("\n")[0][:100] if prompt.lyrics else None,
            "duration_target": prompt.duration_target,
            "duration_actual_s": float(final_audio.shape[-1]) / res.sample_rate,
            "sample_rate": res.sample_rate,
            "per_sigma_intermediate": per_sigma_results,
            "final_audio_segmentation": final_results,
        }
    results["elapsed_total_seconds"] = time.time() - t_start
    results["elapsed_total_gpu_h"] = results["elapsed_total_seconds"] / 3600.0

    out_json = out_dir / "h3_smoke_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[smoke] wrote {out_json}", flush=True)

    # Markdown summary
    summary_lines = []
    summary_lines.append("# H3 Smoke Test Summary")
    summary_lines.append("")
    summary_lines.append(f"- elapsed: {results['elapsed_total_seconds']:.1f}s "
                          f"({results['elapsed_total_gpu_h']:.4f} GPU-h)")
    summary_lines.append(f"- prompts: {', '.join(SMOKE_PROMPT_IDS)}")
    summary_lines.append(f"- σ targets: {list(SIGMA_TARGETS.keys())}")
    summary_lines.append(f"- credit units: {list(segmenters.keys())}")
    summary_lines.append("")
    summary_lines.append("## Per-prompt segmentation counts")
    summary_lines.append("")
    summary_lines.append("| prompt | instr | unit | σ=0.7 | σ=0.6 | final |")
    summary_lines.append("|---|---|---|---:|---:|---:|")
    for pid in SMOKE_PROMPT_IDS:
        pr = results["per_prompt"][pid]
        instr = "Y" if pr["is_instrumental"] else "N"
        for unit_id in segmenters.keys():
            n07 = pr["per_sigma_intermediate"]["0.7"].get(unit_id, {}).get("n_segments", "?")
            applicable07 = pr["per_sigma_intermediate"]["0.7"].get(unit_id, {}).get("applicable")
            n06 = pr["per_sigma_intermediate"]["0.6"].get(unit_id, {}).get("n_segments", "?")
            nf = pr["final_audio_segmentation"].get(unit_id, {}).get("n_segments", "?")
            applicableF = pr["final_audio_segmentation"].get(unit_id, {}).get("applicable")
            mark07 = f"{n07}" if applicable07 else "NA"
            markF = f"{nf}" if applicableF else "NA"
            summary_lines.append(f"| {pid} | {instr} | {unit_id} | {mark07} | {n06 if applicable07 else 'NA'} | {markF} |")
    summary_lines.append("")
    summary_lines.append("## D3 lyric_span behavior check")
    summary_lines.append("")
    for pid in SMOKE_PROMPT_IDS:
        pr = results["per_prompt"][pid]
        ls_07 = pr["per_sigma_intermediate"]["0.7"].get("CU-LS", {})
        applicable = ls_07.get("applicable")
        reason = ls_07.get("not_applicable_reason", "—")
        instr = pr["is_instrumental"]
        status = ("✓ NA on instrumental" if (instr and not applicable and reason == "instrumental")
                  else ("✓ applicable on vocal" if (not instr and applicable)
                  else ("⚠ unexpected" if (instr ^ applicable) else "applicable=" + str(applicable))))
        summary_lines.append(f"- `{pid}` (instr={instr}): CU-LS applicable={applicable}, reason={reason!r} → {status}")
    summary_lines.append("")
    out_md = out_dir / "h3_smoke_summary.md"
    out_md.write_text("\n".join(summary_lines) + "\n")
    print(f"[smoke] wrote {out_md}", flush=True)

    print(f"\n[smoke] DONE. elapsed={results['elapsed_total_seconds']:.1f}s "
          f"({results['elapsed_total_gpu_h']:.4f} GPU-h)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
