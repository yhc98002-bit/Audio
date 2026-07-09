"""D5 — mini Flow-GRPO sampling smoke (DIAGNOSTIC_EXPERIMENT_PLAN §2 D5).

This validates the sampling-side machinery that R8 / R9 / future M-PRM all depend on:
- Per-prompt grouped rollouts with SDE noise injection.
- Per-step trajectory return.
- Reward harness end-to-end.

It does NOT run a real GRPO weight update (that is deferred to the next /experiment-bridge
when R8 is fully implemented). It only verifies the *call path* for sampling + reward.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import torch

from mprm.common.seeding import seed_everything
from mprm.data.prompts import Prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["ace_step_v15", "sao_1_0"], default="ace_step_v15")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-prompts", type=int, default=4)
    parser.add_argument("--group-size", type=int, default=4)
    parser.add_argument("--t-train", type=int, default=5)
    args = parser.parse_args()
    seed_everything(args.seed)

    if args.model == "ace_step_v15":
        from mprm.inference.ace_step import AceStepModel
        model = AceStepModel(checkpoint="ace-step/ACE-Step-1.5")
    else:
        from mprm.inference.sao import StableAudioOpenModel
        model = StableAudioOpenModel(checkpoint="stabilityai/stable-audio-open-1.0")

    try:
        from mprm.rewards.audiobox import AudioboxReward
        from mprm.rewards.clap import ClapReward
        rewards = [AudioboxReward(target_axis="PQ"), ClapReward()]
    except Exception as e:  # noqa: BLE001
        print(f"D5 FAIL: cannot load rewards: {e}")
        return 1

    prompts = [
        Prompt(prompt_id=f"d5_{i:02d}",
               text="a melodic acoustic guitar piece, no vocals",
               lyrics=None, structure_hint="AABA", duration_target=20.0)
        for i in range(args.n_prompts)
    ]

    failures: list[str] = []
    rewards_per_prompt: list[list[float]] = []
    for p in prompts:
        try:
            eta_schedule = torch.full((args.t_train,), 0.5)
            group_rewards = []
            for g in range(args.group_size):
                res = model.sample(p, seed=args.seed + g, steps=args.t_train,
                                    sde_mode=True, eta_schedule=eta_schedule,
                                    return_trajectory=True)
                if res.trajectory is None:
                    failures.append(f"prompt={p.prompt_id} group={g}: trajectory None")
                    continue
                if res.waveform.isnan().any() or res.waveform.isinf().any():
                    failures.append(f"prompt={p.prompt_id} group={g}: NaN/Inf in waveform")
                    continue
                axis_scores = [r.score(res.waveform, res.sample_rate, p).value for r in rewards]
                group_rewards.append(statistics.mean(axis_scores))
            if len(group_rewards) >= 2:
                rewards_per_prompt.append(group_rewards)
        except Exception as e:  # noqa: BLE001
            failures.append(f"prompt={p.prompt_id}: {type(e).__name__}: {e}")

    if failures:
        print("D5 FAIL with failures:")
        for f in failures:
            print(f"  {f}")
        return 1

    if not rewards_per_prompt:
        print("D5 FAIL: no successful prompt group")
        return 1

    advantage_spreads = [statistics.pstdev(group) for group in rewards_per_prompt
                          if len(group) > 1]
    print(f"D5 results over {len(rewards_per_prompt)} prompts, group_size={args.group_size}:")
    print(f"  per-prompt mean reward: {[round(statistics.mean(g), 3) for g in rewards_per_prompt]}")
    print(f"  per-prompt advantage spread: {[round(s, 3) for s in advantage_spreads]}")
    if all(s < 1e-4 for s in advantage_spreads):
        print("D5 WARN: advantage spread is near-zero across all prompts; GRPO won't have signal.")
        print("        Increase eta or check base-policy diversity (A6).")
        return 1
    print("D5 PASS (sampling + reward harness call path validated; full GRPO update deferred)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
