# C1-Lite RL Rescue Stop Decision

Decision marker: `STOP_TRACK_C`

Decision: do not run Track C; stop after CPU prep.

## Rationale

Track A robust Early-Tweedie validation has completed with:

- 512 prompts / 4096 BoN-8 candidates;
- verifier status `PASS_WITH_WARNINGS` with 0 errors;
- PI decision status `STRONG_CANDIDATE_MAIN_APPLICATION`;
- primary robust/common schedule A at compute fraction 0.5000 with reward
  fraction 0.9858;
- bottom-prune false-negative best readout 0.0195.

Track B global-quality structure analysis is also complete and supports the
mechanism interpretation that ACE-Step short-form local-window rewards mostly
track persistent global quality rather than isolated local failures.

C1 first-wave and common dev eval already showed no clear RL downstream win.
Given the strong Track A/Track B readout, spending the bounded RL rescue
opportunity is not needed for the current trajectory-aware paper direction.

## Evidence

- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md`
- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json`
- `orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json`
- `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md`
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md`
- `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md`

## Boundary Confirmation

- No Phase D launched.
- No human eval launched.
- No pruning+RL launched.
- No full 1000-step RL rescue launched.
- No Track C GPU smoke launched.
- No reward-definition changes.
- No sigma-policy changes for RL.
- No prompt-split changes.
- No credit-unit-definition changes.
- `configs/eval/gate_v1.yaml` untouched.
- No canonical proposal rewrite.

## Scope

This resolves the bounded Track C rescue opportunity for the current
trajectory-aware objective. It does not claim Early-Tweedie is the final main
method without PI sign-off, and it does not authorize held-out expansion, Phase
D, human evaluation, pruning+RL, or paper rewriting.
