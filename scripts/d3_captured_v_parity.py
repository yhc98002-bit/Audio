"""Captured-v parity test (Phase B prep §B, 2026-05-22).

For 4 prompts × 3 seeds × 3 target σ values, verify that:

    captured_trajectory_v_k  ≈  AceStepModel.predict_velocity(z_k, σ_k, prompt)

under the validated `cfg_type='cfg'`, `ERG=False` scope. This is a parity
test, NOT a statistical H2 evaluation — the σ values used here are test
locations only; final Stage-1 σ selection is the σ calibration diagnostic's
responsibility (`scripts/d3_sigma_calibration.py`).

Report:
- max absolute error (over all (z, v) element pairs)
- mean absolute error
- relative error (mean |v_pred - v_capt| / mean |v_capt|)
- tolerance + PASS/FAIL verdict

Hard-fail if any captured v_out is missing — recomputing via
predict_velocity (the very function we're testing) is NOT a valid fallback.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from mprm.common.seeding import seed_everything
from mprm.data.prompts import Prompt


PROMPT_TEMPLATES = [
    "a calm acoustic guitar melody with no vocals",
    "an upbeat electronic dance track with synthesizer leads",
    "a melancholic piano piece in a minor key",
    "a jazzy lo-fi hip-hop beat with vinyl crackle",
]


def _pick_checkpoints_for_sigmas(target_sigmas, traj_sigmas):
    return [
        min(range(len(traj_sigmas)), key=lambda k: abs(traj_sigmas[k] - t))
        for t in target_sigmas
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--n-prompts", type=int, default=4)
    parser.add_argument("--n-seeds", type=int, default=3)
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--target-sigmas", default="0.7,0.5,0.3,0.1",
                        help="Test locations for parity; NOT final Stage-1 σ. "
                             "Default spans both INSIDE (σ≈0.7 at step ~14 "
                             "for guidance_interval=0.5, 30 steps) and OUTSIDE "
                             "(σ∈{0.5, 0.3, 0.1} at steps {22,25,28}) the "
                             "guidance interval [start_idx=7, end_idx=22).")
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-step", type=int, default=30)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--cfg-type", default="cfg",
                        help="Must be 'cfg' for parity (the validated scope). "
                             "Passing anything else is a configuration error.")
    parser.add_argument(
        "--tolerance-rel", type=float, default=0.05,
        help="Relative-error tolerance (mean |Δ| / mean |v_capt|). Default 0.05 "
             "= 5%%. PASS if observed below this.",
    )
    parser.add_argument(
        "--report-out", default="orbit-research/CAPTURED_V_PARITY_2026-05-22.json",
        help="Where to write the report.",
    )
    args = parser.parse_args()

    if args.cfg_type != "cfg":
        print(f"PARITY FAIL: --cfg-type={args.cfg_type!r} but the validated scope "
              f"is 'cfg' (ERG=False); APG/ERG parity is explicitly out of scope.")
        return 2

    target_sigmas = [float(x) for x in args.target_sigmas.split(",") if x.strip()]
    if not target_sigmas:
        print("PARITY FAIL: empty --target-sigmas")
        return 2

    from mprm.inference.ace_step import AceStepModel
    model = AceStepModel(checkpoint=args.checkpoint or "ace-step/ACE-Step-1.5")

    n_prompts = min(args.n_prompts, len(PROMPT_TEMPLATES))
    print(f"PARITY: {n_prompts} prompts × {args.n_seeds} seeds × σ {target_sigmas}")
    print(f"PARITY: cfg_type={args.cfg_type}, cfg_scale={args.cfg_scale}, "
          f"infer_step={args.infer_step}, duration={args.duration}s")
    print(f"PARITY: tolerance (relative) = {args.tolerance_rel:.4f}")

    # Per-case records: { (prompt_idx, seed, σ_target): { sigma_actual, max_abs, mean_abs, rel_err } }
    cases: list[dict] = []
    overall_max_abs = 0.0
    overall_sum_abs = 0.0
    overall_sum_capt_abs = 0.0
    overall_count = 0

    for p_idx in range(n_prompts):
        prompt_text = PROMPT_TEMPLATES[p_idx]
        prompt = Prompt(
            prompt_id=f"parity_{p_idx:02d}",
            text=prompt_text,
            lyrics=None,
            structure_hint=None,
            duration_target=float(args.duration),
        )
        # Build condition cache once per prompt (saves re-encoding text/lyric).
        condition_cache = None

        for seed_idx in range(args.n_seeds):
            seed = args.base_seed + p_idx * 100 + seed_idx
            seed_everything(seed)
            try:
                res = model.sample(
                    prompt,
                    seed=seed,
                    cfg_scale=args.cfg_scale,
                    steps=args.infer_step,
                    return_trajectory=True,
                    extras={"cfg_type": args.cfg_type,
                             "use_erg_tag": False,
                             "use_erg_lyric": False,
                             "use_erg_diffusion": False},
                )
            except Exception as e:  # noqa: BLE001
                print(f"PARITY FAIL sampling prompt={p_idx} seed={seed}: "
                      f"{type(e).__name__}: {e}")
                return 1
            traj = res.trajectory or []
            traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
            traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
            cfg_active_flags = (res.extras or {}).get("trajectory_cfg_active", [])
            start_idx = (res.extras or {}).get("guidance_interval_start_idx")
            end_idx = (res.extras or {}).get("guidance_interval_end_idx")
            if (not traj or not traj_sigmas or len(traj_vs) != len(traj)
                    or len(cfg_active_flags) != len(traj)):
                print(
                    f"PARITY FAIL prompt={p_idx} seed={seed}: trajectory plumbing "
                    f"missing or inconsistent (traj={len(traj)}, "
                    f"sigmas={len(traj_sigmas)}, vs={len(traj_vs)}, "
                    f"cfg_active={len(cfg_active_flags)})."
                )
                return 1

            # Build condition cache once after we know the model is loaded.
            if condition_cache is None:
                condition_cache = model._build_condition_cache(prompt)

            step_indices = _pick_checkpoints_for_sigmas(target_sigmas, traj_sigmas)
            for target_sigma, k in zip(target_sigmas, step_indices):
                sigma_actual = float(traj_sigmas[k])
                z_k = traj[k]
                v_captured = traj_vs[k]
                cfg_active_at_k = bool(cfg_active_flags[k])
                if v_captured is None:
                    print(f"PARITY FAIL prompt={p_idx} seed={seed} σ={sigma_actual}: "
                          f"captured v missing at step {k}.")
                    return 1
                # Recompute v via predict_velocity at the same (z, σ, prompt),
                # matching the per-step cfg_active flag the sampler used.
                v_pred = model.predict_velocity(
                    z_k, sigma_actual, prompt,
                    cfg_scale=args.cfg_scale,
                    condition_cache=condition_cache,
                    cfg_active=cfg_active_at_k,
                ).detach().cpu().to(torch.float32)
                v_capt = v_captured.detach().cpu().to(torch.float32)
                if v_pred.shape != v_capt.shape:
                    # predict_velocity may add a batch dim; squeeze if so.
                    if v_pred.dim() == v_capt.dim() + 1 and v_pred.shape[0] == 1:
                        v_pred = v_pred.squeeze(0)
                    elif v_capt.dim() == v_pred.dim() + 1 and v_capt.shape[0] == 1:
                        v_capt = v_capt.squeeze(0)
                    else:
                        print(
                            f"PARITY FAIL prompt={p_idx} seed={seed} σ={sigma_actual}: "
                            f"shape mismatch v_pred {tuple(v_pred.shape)} vs "
                            f"v_capt {tuple(v_capt.shape)}."
                        )
                        return 1
                diff = (v_pred - v_capt).abs()
                max_abs = float(diff.max())
                mean_abs = float(diff.mean())
                mean_capt_abs = float(v_capt.abs().mean())
                rel_err = mean_abs / max(mean_capt_abs, 1e-8)
                cases.append({
                    "prompt_idx": p_idx,
                    "prompt_text": prompt_text,
                    "seed": seed,
                    "sigma_target": target_sigma,
                    "sigma_actual": sigma_actual,
                    "step_index": k,
                    "guidance_start_idx": start_idx,
                    "guidance_end_idx": end_idx,
                    "cfg_active": cfg_active_at_k,
                    "captured_branch": ("CFG-mixed" if cfg_active_at_k else "cond-only"),
                    "max_abs_err": max_abs,
                    "mean_abs_err": mean_abs,
                    "mean_v_capt_abs": mean_capt_abs,
                    "relative_err": rel_err,
                    "v_shape": list(v_capt.shape),
                })
                overall_max_abs = max(overall_max_abs, max_abs)
                overall_sum_abs += mean_abs * v_capt.numel()
                overall_sum_capt_abs += mean_capt_abs * v_capt.numel()
                overall_count += v_capt.numel()
                branch_str = "CFG-mixed" if cfg_active_at_k else "cond-only"
                print(f"  prompt={p_idx} seed={seed} step={k:>2} σ={sigma_actual:.4f} "
                      f"cfg_active={cfg_active_at_k!s:>5} ({branch_str:>9}): "
                      f"max_abs={max_abs:.4e} mean_abs={mean_abs:.4e} "
                      f"rel_err={rel_err:.4e}")

    overall_mean_abs = overall_sum_abs / max(overall_count, 1)
    overall_mean_capt_abs = overall_sum_capt_abs / max(overall_count, 1)
    overall_rel_err = overall_mean_abs / max(overall_mean_capt_abs, 1e-8)

    verdict = "PASS" if overall_rel_err <= args.tolerance_rel else "FAIL"

    report = {
        "schema_version": "captured_v_parity_v1",
        "generated": "2026-05-22",
        "scope": {
            "cfg_type": args.cfg_type,
            "erg": False,
            "note": "APG/ERG parity is explicitly out of scope.",
        },
        "config": {
            "n_prompts": n_prompts,
            "n_seeds": args.n_seeds,
            "target_sigmas": target_sigmas,
            "cfg_scale": args.cfg_scale,
            "infer_step": args.infer_step,
            "duration_s": args.duration,
            "base_seed": args.base_seed,
            "tolerance_rel": args.tolerance_rel,
        },
        "overall": {
            "max_abs_err": overall_max_abs,
            "mean_abs_err": overall_mean_abs,
            "mean_v_capt_abs": overall_mean_capt_abs,
            "relative_err": overall_rel_err,
            "count_elements": overall_count,
        },
        "cases": cases,
        "verdict": verdict,
    }
    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nCAPTURED-V PARITY [{verdict}]")
    print(f"  overall_max_abs   = {overall_max_abs:.4e}")
    print(f"  overall_mean_abs  = {overall_mean_abs:.4e}")
    print(f"  overall_rel_err   = {overall_rel_err:.4e}  (tolerance {args.tolerance_rel:.4e})")
    print(f"  report saved      = {args.report_out}")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
