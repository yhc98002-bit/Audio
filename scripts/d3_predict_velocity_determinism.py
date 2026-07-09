"""Determinism diagnostic for predict_velocity (Phase B prep §B follow-up).

Single prompt × single seed × σ ∈ {0.5, 0.3, 0.1}. For each (prompt, σ),
call AceStepModel.predict_velocity TWICE with identical inputs and measure
the self-vs-self difference. This isolates the CUDA / bf16 precision floor
from any semantic mismatch between captured-v and predict_velocity.

If self-vs-self error ≈ captured-vs-predict error → the parity 'failure'
is dominated by bf16/CUDA non-determinism, not a code bug.
If self-vs-self error << captured-vs-predict error → there's a real
semantic mismatch (e.g., conditioning or CFG flow differs).

NOT a fix for the parity failure — just evidence-gathering.
"""
from __future__ import annotations

import argparse
import sys

import torch

from mprm.common.seeding import seed_everything
from mprm.data.prompts import Prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=5.0)
    parser.add_argument("--infer-step", type=int, default=30)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--target-sigmas", default="0.5,0.3,0.1")
    args = parser.parse_args()

    target_sigmas = [float(x) for x in args.target_sigmas.split(",") if x.strip()]
    seed_everything(args.seed)

    from mprm.inference.ace_step import AceStepModel
    model = AceStepModel(checkpoint=args.checkpoint or "ace-step/ACE-Step-1.5")

    prompt = Prompt(
        prompt_id="det_00",
        text="a calm acoustic guitar melody with no vocals",
        lyrics=None,
        structure_hint=None,
        duration_target=float(args.duration),
    )

    # Get a trajectory to sample some real (z, σ) tuples to test on.
    res = model.sample(
        prompt,
        seed=args.seed,
        cfg_scale=args.cfg_scale,
        steps=args.infer_step,
        return_trajectory=True,
        extras={"cfg_type": "cfg",
                "use_erg_tag": False,
                "use_erg_lyric": False,
                "use_erg_diffusion": False},
    )
    traj = res.trajectory or []
    traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])

    # Build condition cache once.
    condition_cache = model._build_condition_cache(prompt)

    def _pick(t_sigma):
        return min(range(len(traj_sigmas)), key=lambda k: abs(traj_sigmas[k] - t_sigma))

    print(f"DETERMINISM: prompt='{prompt.text}' seed={args.seed} cfg=cfg ERG=False")
    print(f"  {'σ_target':>8} {'σ_actual':>10} {'self_max_abs':>14} {'self_mean_abs':>14} {'self_rel_err':>14}")
    print(f"  {'-'*8} {'-'*10} {'-'*14} {'-'*14} {'-'*14}")
    for t_sigma in target_sigmas:
        k = _pick(t_sigma)
        sigma_actual = float(traj_sigmas[k])
        z_k = traj[k]
        v_a = model.predict_velocity(
            z_k, sigma_actual, prompt,
            cfg_scale=args.cfg_scale,
            condition_cache=condition_cache,
        ).detach().cpu().to(torch.float32)
        v_b = model.predict_velocity(
            z_k, sigma_actual, prompt,
            cfg_scale=args.cfg_scale,
            condition_cache=condition_cache,
        ).detach().cpu().to(torch.float32)
        if v_a.dim() > v_b.dim():
            v_a = v_a.squeeze(0)
        if v_b.dim() > v_a.dim():
            v_b = v_b.squeeze(0)
        diff = (v_a - v_b).abs()
        max_abs = float(diff.max())
        mean_abs = float(diff.mean())
        mean_a = float(v_a.abs().mean())
        rel_err = mean_abs / max(mean_a, 1e-8)
        print(f"  {t_sigma:>8.3f} {sigma_actual:>10.4f} {max_abs:>14.4e} {mean_abs:>14.4e} {rel_err:>14.4e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
