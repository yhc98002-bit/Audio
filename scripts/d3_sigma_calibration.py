"""Stage 0 σ calibration diagnostic (Phase B prep §D, 2026-05-22).

For 16 dev prompts (recorded in orbit-research/SIGMA_CALIBRATION_PROMPTS.json
and excluded from formal Phase B.1 reliability sample), sample once with
trajectory capture under the formal Phase B sampler binding
(cfg_type='cfg', ERG=False, guidance_interval=0.5), then for each σ
candidate ∈ {0.7, 0.5, 0.3, 0.2, 0.1}:

  1. Find the trajectory step closest to that σ
  2. Tweedie-decode using `v_effective(k) = trajectory_model_outputs[k]`
     (per-step CFG-mixed or cond-only, per `trajectory_cfg_active[k]`)
  3. Compute LSD vs final audio
  4. Compute aesthetic (Audiobox), CLAP semantic, MERT coherence on the
     intermediate audio when those reward models are cheap to load

Purpose: choose K=3 intermediate σ values that are neither effectively
final audio (LSD ≈ 0) nor degraded beyond meaningful musical content.

Per PI directive (2026-05-21 + 2026-05-22):
- σ choice MUST NOT maximize Spearman or any formal H2 statistic
- σ values are NOT a paper result
- The 16 calibration prompts are EXCLUDED from formal Phase B.1
"""
from __future__ import annotations

import argparse
import json
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts-json", default="orbit-research/SIGMA_CALIBRATION_PROMPTS.json")
    parser.add_argument("--dev-jsonl", default="configs/prompts/dev.jsonl")
    parser.add_argument("--candidate-sigmas", default="0.7,0.5,0.3,0.2,0.1")
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-step", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="papers/diagnostic/sigma_calibration")
    parser.add_argument(
        "--report-out",
        default="orbit-research/SIGMA_CALIBRATION_REPORT_2026-05-22.json",
    )
    parser.add_argument("--skip-rewards", action="store_true",
                        help="LSD-only mode (skip CLAP/Audiobox/MERT for speed).")
    args = parser.parse_args()

    candidate_sigmas = [float(x) for x in args.candidate_sigmas.split(",") if x.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load calibration prompt IDs.
    cal = json.loads(Path(args.prompts_json).read_text())
    excluded_ids = set(cal["excluded_prompt_ids"])
    print(f"σ calibration: {len(excluded_ids)} prompts, candidate σ {candidate_sigmas}",
          flush=True)

    # Load full dev prompts and filter to calibration subset.
    prompts_by_id: dict[str, dict] = {}
    with open(args.dev_jsonl) as f:
        for line in f:
            p = json.loads(line)
            prompts_by_id[p["prompt_id"]] = p
    cal_prompts = [prompts_by_id[pid] for pid in sorted(excluded_ids) if pid in prompts_by_id]
    if len(cal_prompts) != len(excluded_ids):
        print(f"WARN: {len(excluded_ids) - len(cal_prompts)} calibration IDs not found in dev set",
              flush=True)

    from mprm.inference.ace_step import AceStepModel
    model = AceStepModel()

    # Optional reward models.
    aesthetic = clap = mert = None
    if not args.skip_rewards:
        try:
            from mprm.rewards.audiobox import AudioboxReward
            aesthetic = AudioboxReward(target_axis="PQ")
            print("  [reward] Audiobox loaded", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [reward] Audiobox FAILED: {e}", flush=True)
        try:
            from mprm.rewards.clap import ClapReward
            clap = ClapReward()
            print("  [reward] CLAP loaded", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [reward] CLAP FAILED: {e}", flush=True)
        try:
            from mprm.rewards.mert import MertReward
            mert = MertReward()
            print("  [reward] MERT loaded", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [reward] MERT FAILED: {e}", flush=True)

    per_sigma: dict[float, dict] = {s: {
        "actual_sigmas": [], "step_indices": [], "cfg_active_flags": [],
        "lsd": [], "aesthetic": [], "clap": [], "mert": [],
    } for s in candidate_sigmas}
    per_sigma_final_aes: list[float] = []
    per_sigma_final_clap: list[float] = []
    per_sigma_final_mert: list[float] = []

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
        try:
            res = model.sample(
                prompt, seed=seed, cfg_scale=args.cfg_scale, steps=args.infer_step,
                return_trajectory=True,
                extras={"cfg_type": "cfg",
                         "use_erg_tag": False,
                         "use_erg_lyric": False,
                         "use_erg_diffusion": False},
            )
        except Exception as e:  # noqa: BLE001
            print(f"σ-cal FAIL prompt={prompt.prompt_id}: {type(e).__name__}: {e}",
                  flush=True)
            return 1

        traj = res.trajectory or []
        traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
        traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
        cfg_active_flags = (res.extras or {}).get("trajectory_cfg_active", [])
        final_audio = res.waveform

        if aesthetic is not None:
            per_sigma_final_aes.append(aesthetic.score(final_audio, res.sample_rate, prompt).value)
        if clap is not None:
            per_sigma_final_clap.append(clap.score(final_audio, res.sample_rate, prompt).value)
        if mert is not None:
            per_sigma_final_mert.append(mert.score(final_audio, res.sample_rate, prompt).value)

        for s in candidate_sigmas:
            k = _pick(s, traj_sigmas)
            sigma_actual = float(traj_sigmas[k])
            v_eff = traj_vs[k]
            z_k = traj[k]
            z0 = z_k.to(torch.float32) - sigma_actual * v_eff.to(torch.float32)
            ahat = model.decode(z0)
            lsd = log_spectral_distance(ahat, final_audio)

            per_sigma[s]["actual_sigmas"].append(sigma_actual)
            per_sigma[s]["step_indices"].append(int(k))
            per_sigma[s]["cfg_active_flags"].append(bool(cfg_active_flags[k]))
            per_sigma[s]["lsd"].append(lsd)
            if aesthetic is not None:
                per_sigma[s]["aesthetic"].append(aesthetic.score(ahat, res.sample_rate, prompt).value)
            if clap is not None:
                per_sigma[s]["clap"].append(clap.score(ahat, res.sample_rate, prompt).value)
            if mert is not None:
                per_sigma[s]["mert"].append(mert.score(ahat, res.sample_rate, prompt).value)

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

    print(f"\nσ calibration table (n={len(cal_prompts)} prompts; "
          f"effective-v recomputation per per-step cfg_active):", flush=True)
    if per_sigma_final_aes:
        print(f"  Final-audio medians: "
              f"aesthetic={statistics.median(per_sigma_final_aes):.3f} "
              f"clap={statistics.median(per_sigma_final_clap):.3f} "
              f"mert={statistics.median(per_sigma_final_mert):.3f}", flush=True)
    print(f"\n  {'σ':>5}  {'σ_actual':>9}  {'step':>4}  {'cfg_act%':>8}  "
          f"{'LSD':>8}  {'aes_med':>8}  {'clap_med':>8}  {'mert_med':>8}", flush=True)
    print(f"  {'-'*5}  {'-'*9}  {'-'*4}  {'-'*8}  "
          f"{'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}", flush=True)
    table_rows = []
    for s in candidate_sigmas:
        d = per_sigma[s]
        if not d["actual_sigmas"]:
            continue
        sigma_actual_med = statistics.median(d["actual_sigmas"])
        step_med = statistics.median(d["step_indices"])
        cfg_active_frac = sum(d["cfg_active_flags"]) / len(d["cfg_active_flags"])
        lsd_med = statistics.median(d["lsd"])
        aes_med = statistics.median(d["aesthetic"]) if d["aesthetic"] else float("nan")
        clap_med = statistics.median(d["clap"]) if d["clap"] else float("nan")
        mert_med = statistics.median(d["mert"]) if d["mert"] else float("nan")
        row = {
            "sigma_target": s,
            "sigma_actual_median": sigma_actual_med,
            "step_index_median": step_med,
            "cfg_active_fraction": cfg_active_frac,
            "lsd_median": lsd_med,
            "aesthetic_median": aes_med,
            "clap_median": clap_med,
            "mert_median": mert_med,
            "n": len(d["actual_sigmas"]),
        }
        table_rows.append(row)
        print(f"  {s:>5.2f}  {sigma_actual_med:>9.4f}  {step_med:>4.1f}  "
              f"{cfg_active_frac*100:>7.1f}%  {lsd_med:>8.4f}  "
              f"{aes_med:>8.4f}  {clap_med:>8.4f}  {mert_med:>8.4f}", flush=True)

    final_aes_med = statistics.median(per_sigma_final_aes) if per_sigma_final_aes else float("nan")
    ordered = sorted(table_rows, key=lambda r: -r["sigma_target"])
    if len(ordered) >= 3:
        # Pick K=3 that span the dynamic range:
        #   - Largest σ in the candidate set (noisiest representation)
        #   - Smallest σ where LSD median is still ≥ 0.3 (NOT too close to final)
        #   - A middle σ between those two
        smallest_meaningful = next(
            (r for r in ordered[::-1] if r["lsd_median"] >= 0.3),
            ordered[-1],
        )
        # Pick the two endpoints, then a middle σ that's distinct.
        candidates_ordered = [r["sigma_target"] for r in ordered]
        sm = smallest_meaningful["sigma_target"]
        lg = candidates_ordered[0]
        middle_candidates = [s for s in candidates_ordered if s != lg and s != sm]
        if middle_candidates:
            middle_candidates.sort(key=lambda s: abs(s - (lg + sm) / 2.0))
            mid = middle_candidates[0]
        else:
            mid = sm  # degenerate
        recommended = sorted({lg, mid, sm}, reverse=True)
    else:
        recommended = candidate_sigmas[:3]

    print(f"\nRecommended K=3 σ set (PI to approve or override): {recommended}", flush=True)
    print(f"  Rationale: largest σ candidate spans the noisy/in-interval regime;",
          flush=True)
    print(f"  smallest σ with LSD median ≥ 0.3 (still distinguishable from final);",
          flush=True)
    print(f"  middle σ is the candidate closest to the midpoint of those two.",
          flush=True)
    print(f"  PI directive: NOT maximizing Spearman or any formal H2 statistic.",
          flush=True)

    report = {
        "schema_version": "sigma_calibration_v1",
        "generated": "2026-05-22",
        "scope": {
            "cfg_type": "cfg",
            "erg": False,
            "guidance_interval": 0.5,
            "candidate_sigmas": candidate_sigmas,
            "formula": "ace_step_paper: x̂_0 = z - σ·v_effective; v_effective = trajectory_model_outputs[k] per per-step cfg_active",
        },
        "config": {
            "n_prompts": len(cal_prompts),
            "cfg_scale": args.cfg_scale,
            "infer_step": args.infer_step,
            "seed_base": args.seed,
            "calibration_prompts_json": args.prompts_json,
            "elapsed_seconds": elapsed_total,
            "elapsed_gpu_h": elapsed_total / 3600.0,
        },
        "final_audio_metrics": {
            "aesthetic_median": (statistics.median(per_sigma_final_aes) if per_sigma_final_aes else None),
            "clap_median": (statistics.median(per_sigma_final_clap) if per_sigma_final_clap else None),
            "mert_median": (statistics.median(per_sigma_final_mert) if per_sigma_final_mert else None),
        },
        "per_sigma_table": table_rows,
        "recommendation": {
            "k3_sigmas": recommended,
            "rationale": "Heuristic spacing using LSD bands + branch coverage; PI to approve or override.",
            "pi_decision_required": True,
            "do_not_maximize_spearman": True,
        },
    }
    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport saved: {args.report_out}", flush=True)
    print(f"Total elapsed: {elapsed_total:.1f}s = {elapsed_total/3600:.4f} GPU-h "
          f"(cap = 20 GPU-h)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
