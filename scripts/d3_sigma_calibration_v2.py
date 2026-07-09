"""Stage 0 σ calibration — expanded v2 diagnostic (Phase B prep §D follow-up, 2026-05-22).

Same 16 dev prompts (`orbit-research/SIGMA_CALIBRATION_PROMPTS.json`, EXCLUDED
from formal Phase B.1) under formal Phase B sampler binding (cfg_type='cfg',
ERG=False, guidance_interval=0.5, infer_step=30, cfg_scale=5.0). Expanded σ
candidate set: {0.9, 0.8, 0.7, 0.6, 0.5, 0.3, 0.1}.

For each σ candidate, per prompt:
  1. Find trajectory step closest to σ → record actual σ, step, cfg_active
  2. Tweedie-decode via captured `v_effective(k) = trajectory_model_outputs[k]`
  3. Compute LSD vs final audio
  4. Compute Audiobox PQ, CLAP semantic, MERT coherence on the intermediate audio

v2 additions (over v1):
- Per-prompt per-axis values retained (not just medians)
- Per-axis delta-from-final per prompt (= reward[σ] - reward[final])
- Per-axis across-prompt spread (std + IQR)
- Per-axis dynamic-range assessment (max - min across σ values)
- Explicit assessments:
    (a) Is σ=0.1 too close to final to serve as a primary H2 checkpoint?
    (b) Does MERT have sufficient σ-dependent dynamic range to be a useful H2 axis?

Per PI directive: K=3 recommendation is heuristic — PI must approve or override.
Recommendation MUST NOT maximize Spearman or any formal H2 statistic.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

import torch

from mprm.common.seeding import seed_everything
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


def log_spectral_distance(a: torch.Tensor, b: torch.Tensor) -> float:
    a = a.mean(dim=0) if a.dim() == 2 else a
    b = b.mean(dim=0) if b.dim() == 2 else b
    if a.shape[-1] > b.shape[-1]:
        a = a[..., : b.shape[-1]]
    elif b.shape[-1] > a.shape[-1]:
        b = b[..., : a.shape[-1]]
    A = torch.stft(a, n_fft=2048, hop_length=512, return_complex=True).abs().clamp_min(1e-8).log()
    B = torch.stft(b, n_fft=2048, hop_length=512, return_complex=True).abs().clamp_min(1e-8).log()
    return float((A - B).pow(2).mean().sqrt())


def _pick(target, sigmas):
    return min(range(len(sigmas)), key=lambda k: abs(sigmas[k] - target))


def _stats(xs):
    """Return median, std (population), IQR (Q3-Q1)."""
    if not xs:
        return float("nan"), float("nan"), float("nan")
    if len(xs) == 1:
        return float(xs[0]), 0.0, 0.0
    med = statistics.median(xs)
    std = statistics.pstdev(xs)
    sx = sorted(xs)
    n = len(sx)
    # Tukey-style hinges (n>=4)
    if n >= 4:
        q1 = sx[n // 4]
        q3 = sx[(3 * n) // 4]
    else:
        q1 = sx[0]
        q3 = sx[-1]
    iqr = q3 - q1
    return med, std, iqr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts-json", default="orbit-research/SIGMA_CALIBRATION_PROMPTS.json")
    parser.add_argument("--dev-jsonl", default="configs/prompts/dev.jsonl")
    parser.add_argument("--candidate-sigmas", default="0.9,0.8,0.7,0.6,0.5,0.3,0.1")
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-step", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="papers/diagnostic/sigma_calibration_v2")
    parser.add_argument(
        "--report-out",
        default="orbit-research/SIGMA_CALIBRATION_REPORT_v2_2026-05-22.json",
    )
    args = parser.parse_args()

    candidate_sigmas = [float(x) for x in args.candidate_sigmas.split(",") if x.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = json.loads(Path(args.prompts_json).read_text())
    excluded_ids = sorted(cal["excluded_prompt_ids"])
    print(f"σ calibration v2: {len(excluded_ids)} prompts, candidate σ {candidate_sigmas}", flush=True)

    prompts_by_id: dict[str, dict] = {}
    with open(args.dev_jsonl) as f:
        for line in f:
            p = json.loads(line)
            prompts_by_id[p["prompt_id"]] = p
    cal_prompts = [prompts_by_id[pid] for pid in excluded_ids if pid in prompts_by_id]

    from mprm.inference.ace_step import AceStepModel
    model = AceStepModel()

    from mprm.rewards.audiobox import AudioboxReward
    aesthetic = AudioboxReward(target_axis="PQ")
    print("  [reward] Audiobox loaded", flush=True)
    from mprm.rewards.clap import ClapReward
    clap = ClapReward()
    print("  [reward] CLAP loaded", flush=True)
    from mprm.rewards.mert import MertReward
    mert = MertReward()
    print("  [reward] MERT loaded", flush=True)

    # per_sigma[σ]["per_prompt"] = list of dicts {prompt_id, sigma_actual, step,
    # cfg_active, lsd, aesthetic, clap, mert, delta_aes, delta_clap, delta_mert}
    per_sigma: dict[float, list[dict]] = {s: [] for s in candidate_sigmas}
    final_per_prompt: list[dict] = []  # final-audio rewards per prompt

    t_start = time.time()
    for p_idx, prompt_data in enumerate(cal_prompts):
        prompt = Prompt(
            prompt_id=prompt_data["prompt_id"],
            text=prompt_data.get("text", ""),
            lyrics=prompt_data.get("lyrics"),
            structure_hint=prompt_data.get("structure_hint"),
            duration_target=float(prompt_data.get("duration_target", 30.0)),
        )
        seed = args.seed + p_idx
        seed_everything(seed)
        res = model.sample(
            prompt, seed=seed, cfg_scale=args.cfg_scale, steps=args.infer_step,
            return_trajectory=True,
            extras={"cfg_type": "cfg",
                     "use_erg_tag": False,
                     "use_erg_lyric": False,
                     "use_erg_diffusion": False},
        )
        traj = res.trajectory or []
        traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
        traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
        cfg_active_flags = (res.extras or {}).get("trajectory_cfg_active", [])
        final_audio = res.waveform

        final_aes = aesthetic.score(final_audio, res.sample_rate, prompt).value
        final_clap = clap.score(final_audio, res.sample_rate, prompt).value
        final_mert = mert.score(final_audio, res.sample_rate, prompt).value
        final_per_prompt.append({
            "prompt_id": prompt.prompt_id,
            "aesthetic": final_aes,
            "clap": final_clap,
            "mert": final_mert,
        })

        for s in candidate_sigmas:
            k = _pick(s, traj_sigmas)
            sigma_actual = float(traj_sigmas[k])
            v_eff = traj_vs[k]
            z_k = traj[k]
            z0 = z_k.to(torch.float32) - sigma_actual * v_eff.to(torch.float32)
            ahat = model.decode(z0)
            lsd = log_spectral_distance(ahat, final_audio)
            aes = aesthetic.score(ahat, res.sample_rate, prompt).value
            clp = clap.score(ahat, res.sample_rate, prompt).value
            mrt = mert.score(ahat, res.sample_rate, prompt).value

            per_sigma[s].append({
                "prompt_id": prompt.prompt_id,
                "sigma_actual": sigma_actual,
                "step_index": int(k),
                "cfg_active": bool(cfg_active_flags[k]),
                "lsd": lsd,
                "aesthetic": aes,
                "clap": clp,
                "mert": mrt,
                "delta_aes": aes - final_aes,
                "delta_clap": clp - final_clap,
                "delta_mert": mrt - final_mert,
            })

            if p_idx == 0:
                save_audio(out_dir / f"sigma{s:.2f}_step{k}_prompt00.wav",
                            ahat, res.sample_rate)
        if p_idx == 0:
            save_audio(out_dir / "final_prompt00.wav", final_audio, res.sample_rate)
        if (p_idx + 1) % 4 == 0:
            elapsed = time.time() - t_start
            print(f"  {p_idx+1}/{len(cal_prompts)} prompts done, elapsed {elapsed:.1f}s",
                  flush=True)

    elapsed_total = time.time() - t_start

    # ------- summary -------
    print(f"\n=== σ calibration v2 (n={len(cal_prompts)} prompts) ===", flush=True)
    final_aes_med = statistics.median(p["aesthetic"] for p in final_per_prompt)
    final_clap_med = statistics.median(p["clap"] for p in final_per_prompt)
    final_mert_med = statistics.median(p["mert"] for p in final_per_prompt)
    final_aes_std = statistics.pstdev(p["aesthetic"] for p in final_per_prompt)
    final_clap_std = statistics.pstdev(p["clap"] for p in final_per_prompt)
    final_mert_std = statistics.pstdev(p["mert"] for p in final_per_prompt)
    print(f"Final-audio (across prompts): "
          f"aes med={final_aes_med:.4f} std={final_aes_std:.4f} | "
          f"clap med={final_clap_med:.4f} std={final_clap_std:.4f} | "
          f"mert med={final_mert_med:.4f} std={final_mert_std:.4f}",
          flush=True)

    rows = []
    print(f"\n  σ_tgt  σ_act  step  cfgA%  | LSD med  std  | "
          f"AES_med  Δmed  Δstd  | CLAP_med  Δmed  Δstd  | "
          f"MERT_med  Δmed  Δstd", flush=True)
    for s in candidate_sigmas:
        recs = per_sigma[s]
        if not recs:
            continue
        sigma_act_med, _, _ = _stats([r["sigma_actual"] for r in recs])
        step_med = statistics.median(r["step_index"] for r in recs)
        cfg_act_frac = sum(r["cfg_active"] for r in recs) / len(recs)
        lsd_med, lsd_std, lsd_iqr = _stats([r["lsd"] for r in recs])
        aes_med, aes_std, aes_iqr = _stats([r["aesthetic"] for r in recs])
        clap_med, clap_std, clap_iqr = _stats([r["clap"] for r in recs])
        mert_med, mert_std, mert_iqr = _stats([r["mert"] for r in recs])
        d_aes_med, d_aes_std, d_aes_iqr = _stats([r["delta_aes"] for r in recs])
        d_clap_med, d_clap_std, d_clap_iqr = _stats([r["delta_clap"] for r in recs])
        d_mert_med, d_mert_std, d_mert_iqr = _stats([r["delta_mert"] for r in recs])
        rows.append({
            "sigma_target": s,
            "sigma_actual_median": sigma_act_med,
            "step_index_median": step_med,
            "cfg_active_fraction": cfg_act_frac,
            "lsd": {"median": lsd_med, "std": lsd_std, "iqr": lsd_iqr},
            "aesthetic": {"median": aes_med, "std": aes_std, "iqr": aes_iqr,
                          "delta_median": d_aes_med, "delta_std": d_aes_std, "delta_iqr": d_aes_iqr},
            "clap": {"median": clap_med, "std": clap_std, "iqr": clap_iqr,
                     "delta_median": d_clap_med, "delta_std": d_clap_std, "delta_iqr": d_clap_iqr},
            "mert": {"median": mert_med, "std": mert_std, "iqr": mert_iqr,
                     "delta_median": d_mert_med, "delta_std": d_mert_std, "delta_iqr": d_mert_iqr},
            "n": len(recs),
        })
        print(f"  {s:>4.2f}  {sigma_act_med:.3f}  {step_med:>3.0f}   {cfg_act_frac*100:>4.1f}% | "
              f"{lsd_med:6.3f} {lsd_std:5.3f} | "
              f"{aes_med:6.3f} {d_aes_med:+5.2f} {d_aes_std:4.2f} | "
              f"{clap_med:6.3f} {d_clap_med:+5.3f} {d_clap_std:4.3f} | "
              f"{mert_med:6.3f} {d_mert_med:+5.3f} {d_mert_std:4.3f}",
              flush=True)

    # ------- assessments -------
    # (a) Is σ=0.1 too close to final to serve as a primary H2 checkpoint?
    sigma_01_row = next((r for r in rows if abs(r["sigma_target"] - 0.1) < 1e-9), None)
    sigma_01_assess = {}
    if sigma_01_row is not None:
        # "too close" heuristic: |Δ aesthetic| median small relative to final-audio std,
        # AND LSD median below a "near-final" threshold (say 0.5 — heuristic; bf16 + sampling
        # noise floor of repeated runs typically ~0.1-0.3 on this stack).
        delta_aes = abs(sigma_01_row["aesthetic"]["delta_median"])
        lsd = sigma_01_row["lsd"]["median"]
        delta_aes_norm = delta_aes / max(final_aes_std, 1e-6)  # in units of final-audio σ
        is_near_final = (delta_aes_norm < 0.5) and (lsd < 0.7)
        sigma_01_assess = {
            "lsd_median": lsd,
            "delta_aesthetic_median_abs": delta_aes,
            "delta_aesthetic_norm_by_final_std": delta_aes_norm,
            "verdict_too_close_to_final_for_primary_H2": bool(is_near_final),
            "interpretation": (
                "Near-final: σ=0.1 reconstruction reward is within 0.5 final-audio-std of "
                "the final reward AND LSD < 0.7. Risk: a downstream H2 reliability test "
                "at this σ would be testing the FINAL audio (no information about "
                "intermediate process); recommend using a slightly larger σ as the "
                "late primary H2 checkpoint."
                if is_near_final else
                "Not near-final: σ=0.1 reconstruction is distinct enough from final to "
                "carry process-reward information. Safe to use as a late H2 checkpoint."
            ),
        }
        print(f"\n[Assessment (a)] σ=0.1 vs final:", flush=True)
        print(f"  LSD median = {lsd:.3f}", flush=True)
        print(f"  |Δaesthetic| median = {delta_aes:.4f}", flush=True)
        print(f"  |Δaesthetic| / final-aes-std = {delta_aes_norm:.3f}", flush=True)
        print(f"  Verdict: σ=0.1 {'TOO CLOSE — avoid as primary H2 checkpoint' if is_near_final else 'NOT too close — OK as late H2 checkpoint'}",
              flush=True)

    # (b) Does MERT have sufficient σ-dependent dynamic range?
    mert_meds = [r["mert"]["median"] for r in rows]
    mert_dynamic_range = max(mert_meds) - min(mert_meds) if mert_meds else 0.0
    # Compare to MERT across-prompt std at final
    mert_range_vs_final_std = mert_dynamic_range / max(final_mert_std, 1e-6)
    # Heuristic: MERT useful if dynamic range across σ ≥ 1 × final-audio std at final
    mert_useful = mert_dynamic_range >= max(final_mert_std, 1e-6)
    print(f"\n[Assessment (b)] MERT σ-dependent dynamic range:", flush=True)
    print(f"  MERT median range across σ candidates = {mert_dynamic_range:.4f}", flush=True)
    print(f"  Final-audio MERT std across prompts = {final_mert_std:.4f}", flush=True)
    print(f"  Ratio (range / final std) = {mert_range_vs_final_std:.3f}", flush=True)
    print(f"  Verdict: MERT dynamic range "
          f"{'ADEQUATE (range ≥ final std) — usable as process-reward axis' if mert_useful else 'INADEQUATE (range < final std) — MERT may not discriminate σ levels'}",
          flush=True)
    # Cross-check: similar assessment for aesthetic + CLAP
    aes_meds = [r["aesthetic"]["median"] for r in rows]
    clap_meds = [r["clap"]["median"] for r in rows]
    aes_range = max(aes_meds) - min(aes_meds)
    clap_range = max(clap_meds) - min(clap_meds)
    print(f"  (comparison: aesthetic range = {aes_range:.4f} vs final std {final_aes_std:.4f}; "
          f"CLAP range = {clap_range:.4f} vs final std {final_clap_std:.4f})", flush=True)

    # ------- K=3 recommendation -------
    # PI directive: NOT maximizing Spearman. Use:
    #   - one early/non-trivial state
    #   - one middle state
    #   - one late-but-not-nearly-final state
    # Heuristic mapping over candidates:
    #   early: largest σ with cfg_active=True AND LSD median ≥ 0.8
    #   middle: σ near (early + late) / 2, preferring branch coverage
    #   late: smallest σ such that NOT classified as "too close" per assessment (a),
    #         and LSD median ≥ 0.5
    early = next((r for r in rows
                  if r["cfg_active_fraction"] > 0.5 and r["lsd"]["median"] >= 0.8),
                 rows[0])
    # late: walk from smallest σ upward, skip "too close to final"
    late = None
    for r in sorted(rows, key=lambda r: r["sigma_target"]):
        is_too_close = False
        delta_aes_norm = abs(r["aesthetic"]["delta_median"]) / max(final_aes_std, 1e-6)
        if delta_aes_norm < 0.5 and r["lsd"]["median"] < 0.7:
            is_too_close = True
        if not is_too_close and r["lsd"]["median"] >= 0.5:
            late = r
            break
    if late is None:
        late = sorted(rows, key=lambda r: r["sigma_target"])[1] if len(rows) > 1 else rows[0]
    # middle: candidate closest to midpoint
    mid_target = (early["sigma_target"] + late["sigma_target"]) / 2.0
    middle = min((r for r in rows
                  if r["sigma_target"] not in (early["sigma_target"], late["sigma_target"])),
                 key=lambda r: abs(r["sigma_target"] - mid_target))
    recommended = sorted(
        {early["sigma_target"], middle["sigma_target"], late["sigma_target"]},
        reverse=True,
    )

    print(f"\n=== Recommended K=3 σ set (PI to approve or override): {recommended} ===", flush=True)
    print(f"  early  (σ={early['sigma_target']}): cfg_active={early['cfg_active_fraction']*100:.0f}%, LSD={early['lsd']['median']:.3f}",
          flush=True)
    print(f"  middle (σ={middle['sigma_target']}): cfg_active={middle['cfg_active_fraction']*100:.0f}%, LSD={middle['lsd']['median']:.3f}",
          flush=True)
    print(f"  late   (σ={late['sigma_target']}): cfg_active={late['cfg_active_fraction']*100:.0f}%, LSD={late['lsd']['median']:.3f}, "
          f"|Δaes|/final_std={abs(late['aesthetic']['delta_median'])/max(final_aes_std,1e-6):.3f}",
          flush=True)

    # ------- save report -------
    report = {
        "schema_version": "sigma_calibration_v2",
        "generated": "2026-05-22",
        "scope": {
            "cfg_type": "cfg",
            "erg": False,
            "guidance_interval": 0.5,
            "infer_step": args.infer_step,
            "cfg_scale": args.cfg_scale,
            "candidate_sigmas": candidate_sigmas,
            "formula": "ace_step_paper: x̂_0 = z - σ·v_effective; v_effective = trajectory_model_outputs[k] per per-step cfg_active",
        },
        "config": {
            "n_prompts": len(cal_prompts),
            "calibration_prompts_json": args.prompts_json,
            "seed_base": args.seed,
            "elapsed_seconds": elapsed_total,
            "elapsed_gpu_h": elapsed_total / 3600.0,
        },
        "final_audio_per_prompt": final_per_prompt,
        "final_audio_summary": {
            "aesthetic_median": final_aes_med,
            "aesthetic_std": final_aes_std,
            "clap_median": final_clap_med,
            "clap_std": final_clap_std,
            "mert_median": final_mert_med,
            "mert_std": final_mert_std,
        },
        "per_sigma_per_prompt": {str(s): per_sigma[s] for s in candidate_sigmas},
        "per_sigma_summary_table": rows,
        "assessments": {
            "sigma_0_1_vs_final": sigma_01_assess,
            "mert_dynamic_range": {
                "median_range_across_sigma_candidates": mert_dynamic_range,
                "final_audio_mert_std": final_mert_std,
                "ratio_range_over_final_std": mert_range_vs_final_std,
                "verdict_adequate_for_h2_axis": bool(mert_useful),
                "comparison": {
                    "aesthetic_range": aes_range,
                    "aesthetic_final_std": final_aes_std,
                    "clap_range": clap_range,
                    "clap_final_std": final_clap_std,
                },
            },
        },
        "recommendation": {
            "k3_sigmas": recommended,
            "early": {"sigma": early["sigma_target"], "lsd": early["lsd"]["median"],
                      "cfg_active_frac": early["cfg_active_fraction"]},
            "middle": {"sigma": middle["sigma_target"], "lsd": middle["lsd"]["median"],
                       "cfg_active_frac": middle["cfg_active_fraction"]},
            "late": {"sigma": late["sigma_target"], "lsd": late["lsd"]["median"],
                     "cfg_active_frac": late["cfg_active_fraction"]},
            "rationale": (
                "Heuristic spacing (NOT Spearman-based per PI directive): "
                "early = largest σ inside CFG interval with LSD ≥ 0.8 (noisiest meaningful state); "
                "late = smallest σ that is NOT 'too close to final' (|Δaes|/final_std ≥ 0.5 OR LSD ≥ 0.7); "
                "middle = candidate closest to (early + late)/2."
            ),
            "pi_decision_required": True,
            "do_not_maximize_spearman": True,
            "do_not_treat_as_paper_result": True,
        },
    }
    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport saved: {args.report_out}", flush=True)
    print(f"Total elapsed: {elapsed_total:.1f}s = {elapsed_total/3600:.4f} GPU-h (cap = 20 GPU-h)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
