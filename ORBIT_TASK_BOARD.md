# ORBIT Task Board

Last refreshed: 2026-05-28

## Current Active Board

Active inference-time validation is running. No training is authorized or active.

Current cycle status: `TRAJECTORY_AWARE_BON16_VALIDATION_RUNNING`.

| Track | Status | Current Artifact |
|---|---|---|
| Track A: Early-Tweedie BoN-8 pruning validation | complete | `orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.md` |
| Track A: BoN-16 subset validation | running; finalizer installed | `orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.md` |
| Learned Early Trajectory Verifier | complete for BoN-8; awaiting BoN-16 subset | `orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.md` |
| Human spot-check packet | pair manifest ready; audio regeneration pending BoN-16 GPU release | `orbit-research/human_spotcheck_packet_20260528/HUMAN_SPOTCHECK_PACKET_MANIFEST.md` |
| Track B: global/time-uniform quality analysis | complete | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| Track C: bounded RL rescue | stopped before GPU launch | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` |
| C1 RL first wave | complete, no clear common-metric win | `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` |
| Project synthesis | partial final report ready; final report pending BoN-16/audio completion | `orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md` |

## PI-Facing Next Step

Wait for BoN-16 subset validation and automatic finalizer completion, then review
the final PI report and completion check.

Start from:

- `orbit-research/CURRENT_CANONICAL_FILES.md`
- `orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.md`
- `orbit-research/TRAJECTORY_AWARE_EXPERIMENT_PROGRESS_2026-05-28.md`
- `orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md`
- `orbit-research/TRAJECTORY_PHASE_COMPLETION_CHECK_2026-05-28.md`

## Guardrails

- No Phase D.
- No human evaluation.
- No pruning+RL.
- No additional full 1000-step RL training.
- No BeatWin/LyricSpan PRM expansion.
- No canonical proposal rewrite.
- Do not modify `configs/eval/gate_v1.yaml`.
- Do not edit raw evidence under `runs/**`.

## Historical Board

The previous C1 live-monitoring board was preserved at:

`orbit-research/archive/2026-05-doc-hygiene-post-c1/repo-root-md/ORBIT_TASK_BOARD.legacy_2026-05-28.md`
