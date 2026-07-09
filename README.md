# Audio Diffusion - When and Where to Reward

Open-codebase research project for music generation with ACE-Step v1.5.
Stable Audio Open remains audit-only.

## Current State (2026-05-28)

Status: `TRAJECTORY_AWARE_CURRENT_CYCLE_COMPLETE`.

- Phase A / H1: ACE-Step has inference-time headroom.
- Phase B.1 / H2: intermediate Tweedie estimates carry predictive signal in
  non-trivial sigma regions. Verdict: `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`.
- Phase B.3 / H3: Section is not the best default credit unit for 30-40s ACE-Step
  generations. FixedWin remains the conservative PRM credit unit; Section is
  diagnostic / negative-control.
- Phase C1: four-method LoRA/GRPO first wave completed cleanly, but common dev
  evaluation showed `COMMON_DEV_NO_CLEAR_WIN`.
- Track A: robust Early-Tweedie BoN-8 pruning validation completed on 512 prompts /
  4096 candidates. Status: `STRONG_CANDIDATE_MAIN_APPLICATION`.
- Track B: global/time-uniform quality analysis supports persistent global quality
  differences over isolated local-window failures.
- Track C: bounded RL rescue was explicitly stopped before GPU launch.

Recommended current framing: trajectory-aware inference-time selection and
quality-emergence analysis. RL post-training is exploratory / negative evidence
unless a future bounded triage is approved.

Start from [`orbit-research/CURRENT_CANONICAL_FILES.md`](orbit-research/CURRENT_CANONICAL_FILES.md)
for the current reading path.

## Most Important Documents

- Current synthesis: `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md`
- PI report: `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md`
- Completion audit: `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md`
- Early-Tweedie validation: `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md`
- Early-Tweedie PI decision memo: `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md`
- Global quality analysis: `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md`
- C1 common eval: `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`
- C1 training dynamics: `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md`
- RL rescue stop decision: `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md`

Historical proposal files remain in `refine-logs/`, but they are no longer the
current scientific framing.

## Boundaries

Do not launch without explicit PI approval:

- Phase D
- human evaluation
- pruning+RL
- more full 1000-step RL training
- BeatWin/LyricSpan PRM expansion
- canonical proposal rewrite

Do not modify:

- `configs/eval/gate_v1.yaml`
- raw run outputs under `runs/**`
- PI review packages under `_pi_review_pkg/**`
- listening packets or tarballs
- calibration/parity/gate evidence files

## Environment

```bash
module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
```

## Quick Inspection

```bash
# Read the current state
sed -n '1,220p' orbit-research/CURRENT_CANONICAL_FILES.md

# Inspect the latest synthesis
sed -n '1,220p' orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md

# Confirm the main positive result
sed -n '1,140p' orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md
```

## Layout

```text
src/mprm/        implementation modules
scripts/         diagnostics, launchers, analysis tools
configs/         frozen gate policy, draft gate policy, run configs, prompts
runs/            raw and summarized run outputs
orbit-research/  current research state, conclusions, audits, archive
papers/          explainers, diagnostics, listening packets
refine-logs/     historical proposal and method-contract documents
```

## Documentation Hygiene

Superseded prose has been moved under dated archive directories, most recently:

`orbit-research/archive/2026-05-doc-hygiene-post-c1/`

The archive preserves audit history. The default reading path is the current
canonical index, not archived intermediate reports.

## License

Code license is TBD. ACE-Step weights: Apache 2.0. Stable Audio Open weights:
non-commercial license, audit-only in this project.
