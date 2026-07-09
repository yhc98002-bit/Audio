# Experiment Progress Context

Date: 2026-05-28  
Project: When and Where to Reward: Music-Structured Process Rewards for Flow-Matching Song Generation  
Backbone: ACE-Step v1.5  
Status: synthesis memo only; not a canonical proposal rewrite

## Executive Summary

The project has moved from a pure RL/process-reward framing toward a stronger trajectory-aware inference-time selection story.

The core empirical picture is now:

1. ACE-Step has real inference-time headroom.
2. Intermediate Tweedie estimates are predictive in non-trivial sigma regions.
3. Section is not the best default credit unit for ACE-Step 30-40s short-form generation.
4. C1 LoRA/GRPO post-training infrastructure works end to end, but first-wave RL does not show a clear common-metric win.
5. Early-Tweedie pruning is the strongest current positive result and is a strong candidate main application result.
6. Time-uniform/global-quality analysis supports the hypothesis that short-form quality differences are persistent across time rather than isolated local-window defects.
7. RL post-training should be treated as bounded exploratory or negative evidence unless a future small triage produces a clear movement signal.

The current recommended paper direction is:

> Trajectory-aware inference-time selection and quality-emergence analysis for flow-matching music generation, with RL post-training as an exploratory backend result rather than the primary contribution.

No Phase D, human evaluation, pruning+RL, full additional 1000-step RL training, or canonical proposal rewrite has been authorized.

## Current Decision State

The latest project-level report marks the trajectory-aware goal as complete for the current cycle:

- Track A, robust Early-Tweedie validation: complete.
- Track B, global/time-uniform quality analysis: complete.
- Track C, bounded RL rescue: explicitly stopped before GPU launch.
- Hard boundaries were preserved.
- `gate_v1` remains untouched.

Primary decision:

Early-Tweedie pruning is a strong candidate main application result, but it is not yet a final claimed main method until PI sign-off and paper framing decisions are made.

## Evidence Timeline

### Phase A / H1: Inference-Time Headroom

Accepted conclusion:

ACE-Step has inference-time headroom. The saturation pivot was not triggered.

The earlier R050 mini-headroom probe was positive, with median improvement around `+0.0413` and `21/32` positive cases. This supports the premise that selection or search over trajectories can improve generated outputs without changing the model.

Interpretation:

This makes inference-time methods scientifically plausible. It also motivates asking when useful quality information appears along the diffusion/flow trajectory.

### Phase B.1 / H2: When to Reward

Canonical verdict:

`STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`

Key result:

Intermediate Tweedie estimates carry predictive reward signal in non-trivial sigma regions. The 128-prompt canonical analysis found enough reliable primary sigma survival to support early reward emergence.

Important details:

- `n_primary_full = 20`
- `n_primary_strict = 17`
- `strong_holds_strict = True`
- all 7 reward axes have at least one primary sigma survival
- the conclusion does not depend on near-threshold pairs

Representative primary sigma correlations:

| Axis | Sigma Region | Evidence |
|---|---:|---:|
| aesthetic_pq | 0.8 / 0.7 / 0.6 | 0.658 / 0.696 / 0.854 |
| aesthetic_cu | 0.9 / 0.8 / 0.7 / 0.6 | 0.641 / 0.724 / 0.752 / 0.882 |
| section_coherence | 0.8 / 0.7 / 0.6 | 0.639 / 0.761 / 0.818 |
| semantic_fit | 0.6 | 0.659 |
| lyric_intelligibility | 0.8 / 0.7 / 0.6 | 0.646 / 0.753 / 0.788 |

Interpretation:

H2 supports trajectory-aware inference because meaningful quality information appears before final generation. This is the foundation for Early-Tweedie pruning.

Limitations:

- late sigma correlations are not the primary evidence
- Audiobox axes are correlated
- section coherence has limited dynamic range
- lyric intelligibility is vocal-only
- 128 prompts remain moderate for near-threshold correlation claims

### Phase B.3 / H3: Where to Reward

Corrected held-out v2 verdict:

Section failed as the best general credit unit.

Consensus ranking:

`CU-BW > CU-MS > CU-FW > CU-NULL-rand-section > CU-TS`

Key per-stratum section-minus-best-non-section margins:

| Stratum | Axis | Section Minus Best Non-Section |
|---|---|---:|
| vocal | musicality | -0.042 |
| vocal | coherence | -0.274 |
| vocal | prompt_fit | -0.082 |
| instrumental | musicality | +0.020 |
| instrumental | coherence | -0.278 |
| instrumental | prompt_fit | +0.167 |

Interpretation:

Section is not a reliable default credit unit for short-form ACE-Step outputs. It fails clearly on vocal prompts and coherence. It has a real positive signal for instrumental prompt fit, but not enough to justify it as the primary credit unit.

Phase C implication:

FixedWin was chosen as the conservative primary PRM credit unit because it has full coverage and fewer coverage/pathology risks. Section was retained as a diagnostic or negative-control method.

### Phase C0: Backend Validation

Accepted state:

The C0 backend validation passed for all planned C1 methods:

- R8a Outcome-GRPO plain
- R8b Outcome-GRPO guarded
- M-FixedWin-PRM
- M-Section-PRM

Validated backend properties:

- LoRA insertion works.
- Base parameters remain frozen.
- Adapter parameters update.
- Old/new policy forward works.
- Ratio/log-ratio and losses are finite in smoke.
- Checkpoint/resume works.

Interpretation:

The RL infrastructure is technically usable. Later weak scientific results should not be attributed to a simple failure to update adapters or save checkpoints.

### Phase C1: Four-Method First-Wave RL

Training status:

All four methods completed 1000 steps successfully:

- R8a Outcome-GRPO plain
- R8b Outcome-GRPO guarded
- M-FixedWin-PRM
- M-Section-PRM

Engineering status:

- training completed cleanly
- all methods produced `train_results.json`
- checkpoints were produced
- base parameters remained unchanged
- adapters updated
- losses, KL, and ratio logs stayed finite

GPU-hour accounting:

| Method | GPU-h |
|---|---:|
| R8a | 37.7902 |
| R8b | 41.1546 |
| M-FixedWin | 21.3986 |
| M-Section | 19.4068 |
| Total active training | 119.7502 |

Training dynamics audit:

- ratio_mean near `1.0`, ratio_std near `0.0`, and log_ratio near `0.0` are expected for the pre-update logging point used in the current implementation
- these logs are not proof of no learning
- adapter movement exists for all methods
- terminal methods show larger late KL_ref movement than process methods
- reward curves do not show clean monotonic improvement
- process methods show much smaller policy movement than terminal methods

Common dev evaluation:

The shared 64-dev common eval showed no clear method win.

| Method / Checkpoint | robust_lcb_mean | Delta vs Base |
|---|---:|---:|
| Base | 2.133676 | 0.000000 |
| R8a step1000 | 2.145297 | +0.011621 |
| R8b step1000 | 2.148166 | +0.014490 |
| M-FixedWin step1000 | 2.145825 | +0.012149 |
| M-Section step1000 | 2.146055 | +0.012379 |

Scientific interpretation:

The C1 backend is an engineering success, but the first-wave common dev result is `COMMON_DEV_NO_CLEAR_WIN`. The small positive deltas versus base are not enough to claim quality improvement or method ranking.

Checkpoint triage:

No checkpoint sweep evidence showed a better checkpoint than step1000 or base. This weakens the case that the first-wave RL result only failed because the wrong checkpoint was selected.

Current RL interpretation:

RL post-training is not the strongest positive result. It should be demoted to exploratory or negative evidence unless a future bounded triage shows clear common-metric movement beyond noise.

### Track A: Robust Early-Tweedie Pruning Validation

Status:

Complete and strongest positive result.

Run:

- run root: `runs/early_tweedie_validation_512_bon8_20260527_full01`
- prompts: `512`
- candidates: `4096`
- BoN: `8`
- split: `256 dev + 256 held_out`
- sigma checkpoints: `0.9`, `0.8`, `0.7`
- primary metric: `common_robust_lcb`
- GPU-hours actual sum: about `243.096`

Primary common robust-LCB schedule results:

| Schedule | Compute Fraction | Reward Fraction | Winner Match | False Negative |
|---|---:|---:|---:|---:|
| Full BoN-8 | 1.000 | 1.0000 | 1.000 | 0.000 |
| Schedule A: sigma0.9 top4, sigma0.7 top2, final top1 | 0.500 | 0.9858 | 0.576 | 0.424 |
| Schedule B: sigma0.8 top4, sigma0.7 top2, final top1 | 0.583 | 0.9910 | 0.664 | 0.336 |
| Schedule C: sigma0.8 keep top6, final top1 | 0.850 | 0.9986 | 0.939 | 0.061 |
| Bottom-prune sigma0.8 remove bottom25, final top1 | 0.850 | 0.9986 | 0.939 | 0.061 |
| Bottom-prune sigma0.7 remove bottom25, final top1 | 0.883 | 0.9996 | 0.980 | 0.020 |
| Random prune keep4/keep2/final | 0.500 | 0.9570 | 0.254 | 0.746 |

Early winner retention:

| Sigma | Top-1 | Top-2 | Top-4 | Bottom-25 False Negative |
|---:|---:|---:|---:|---:|
| 0.9 | 0.2422 | 0.4531 | 0.6836 | 0.1406 |
| 0.8 | 0.3906 | 0.6113 | 0.8125 | 0.0605 |
| 0.7 | 0.4727 | 0.6816 | 0.8965 | 0.0195 |

Decision threshold:

The PI-defined confirmation threshold was:

- reward_fraction >= `0.98` at compute_fraction <= `0.5` for at least one schedule under robust/common metric
- bottom-prune false-negative <= `5%`

Result:

The threshold is satisfied:

- Schedule A gives `0.9858` reward fraction at `0.500` compute.
- Conservative bottom-prune at sigma `0.7` has false-negative `0.0195`.
- Random pruning is far worse at matched compute.

Interpretation:

Early-Tweedie pruning is a strong candidate main application result. The best framing is inference-time trajectory selection: early noisy estimates identify low-promise candidates well enough to recover most full BoN quality with substantially less compute.

Guardrails:

- do not claim final main-method status without PI sign-off
- do not launch pruning+RL
- do not convert this into new training without explicit approval
- constant or degenerate metric rows should remain diagnostic only

### Track B: Time-Uniform / Global Quality Structure

Status:

Complete CPU-only.

Primary conclusion:

For ACE-Step short-form outputs, local-window rewards appear to track persistent global quality more than isolated local failures.

Primary H3 globalness readout:

- H3 records: `256`
- usable primary cells: `4`
- median between-share: `0.5839`
- median between/within ratio: `1.4038`
- sign consistency: `1.0000`
- crossing frequency: `0.0000`
- globalness index: `0.8613`

Interpretation:

FixedWin does not currently look like a clean local credit-assignment mechanism for isolated temporal defects. It behaves more like a stable local proxy for global or trajectory-level quality.

Connection to C1:

This helps explain why Section and FixedWin PRM training did not strongly separate on common downstream evaluation. If quality differences are persistent across the full 30-40s clip, local-window supervision may not provide the kind of local causal credit that improves RL post-training.

Limitations:

- H3 proxy vectors are not human ratings.
- CU-LS is vocal-only and exploratory.
- coherence vectors have limited dynamic range.
- no new Demucs/source-separation experiments were launched.

### Track C: Bounded RL Rescue Triage

Status:

Stopped by explicit decision before GPU launch.

Decision marker:

`STOP_TRACK_C`

Rationale:

Track A became the stronger scientific direction, Track B completed the mechanism analysis, and C1 already showed no clear common-metric win. Spending the bounded RL rescue opportunity was not necessary for the current trajectory-aware paper direction.

GPU use:

`0.0` GPU-h for Track C triage.

Boundary confirmations:

- no Track C GPU smoke
- no additional 1000-step RL training
- no pruning+RL
- no reward/sigma/prompt/credit-unit changes
- no gate_v1 modification

## Current Scientific Interpretation

### What Looks Strong

Early-Tweedie pruning is the strongest positive result.

The evidence is robust because it uses:

- 512 prompts
- 4096 BoN-8 candidates
- common robust metric
- dev and held-out split coverage
- random-prune comparison
- multiple schedules
- winner retention and false-negative diagnostics

The main scientific story is:

Quality signal emerges along the trajectory early enough to support compute-saving inference-time selection.

### What Looks Plausible

The global-quality hypothesis is plausible and now empirically supported:

Short-form ACE-Step outputs appear to differ by persistent quality across time rather than by a few isolated bad windows. This explains why window-level rewards can predict final quality while still failing to become powerful local RL credit.

### What Looks Weak

C1 RL post-training is technically healthy but scientifically weak so far.

The common dev eval shows no clear method ranking, no strong improvement over base, and no checkpoint triage rescue. This suggests the current GRPO/LoRA configuration may have weak policy movement, noisy reward gradients, or a mismatch between process objectives and downstream common quality.

## Updated Paper Direction

Recommended framing:

1. Use Phase A/H1 and H2 to establish trajectory-aware quality emergence.
2. Use Track A as the main application result: Early-Tweedie pruning approximates BoN quality with lower compute.
3. Use Track B to explain the quality structure: short-form music quality appears global and persistent.
4. Use H3 and C1 as boundary-setting evidence:
   - Section is not a strong default credit unit.
   - FixedWin is a stable proxy but not necessarily true local credit.
   - first-wave RL post-training is an engineering success but not a scientific win.

Possible title direction:

> When Does Quality Emerge? Trajectory-Aware Selection for Flow-Matching Music Generation

The previous title, "When and Where to Reward", can still be used as historical framing, but the strongest evidence now points toward inference-time trajectory selection rather than RL process reward training as the main contribution.

## Current Non-Claims

Do not claim:

- Early-Tweedie is final main method without PI approval.
- RL post-training improves ACE-Step quality.
- M-FixedWin is better than M-Section on common downstream metrics.
- M-Section is a generally useful credit unit.
- FixedWin proves true local temporal credit assignment.
- human preference improvement.
- held-out paper-level generalization beyond the validated prompt split and metrics.

Do not launch without explicit PI approval:

- Phase D
- human evaluation
- pruning+RL
- more full 1000-step RL training
- BeatWin/LyricSpan PRM expansion
- canonical proposal rewrite

## Artifact Map

Most important files for PI review:

| Purpose | File |
|---|---|
| Current final trajectory-aware report | `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` |
| Completion audit | `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md` |
| Early-Tweedie validation report | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` |
| Early-Tweedie PI decision memo | `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` |
| Global quality structure analysis | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| C1 common eval status | `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` |
| C1 training dynamics audit | `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md` |
| C1 RL rescue stop decision | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` |
| H2 conclusion | `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md` |
| H3 interpretation | `orbit-research/H3_CREDIT_UNIT_INTERPRETATION_2026-05-23.md` |
| Canonical file index | `orbit-research/CURRENT_CANONICAL_FILES.md` |

Important run roots:

| Run | Path |
|---|---|
| C1 first-wave training | `runs/phase_c1_firstwave_20260524_researcher_go_01` |
| C1 common downstream eval | `runs/phase_c1_common_downstream_eval_20260526_helper01` |
| C1 checkpoint triage eval | `runs/phase_c1_checkpoint_triage_eval_20260526` |
| Early-Tweedie 512 BoN-8 validation | `runs/early_tweedie_validation_512_bon8_20260527_full01` |
| H3 held-out v2 global seed | `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed` |

## Boundary Confirmation

As of this synthesis:

- no Phase D was launched
- no human evaluation was launched
- no pruning+RL was launched
- no additional full 1000-step RL rescue was launched
- no Track C GPU smoke was launched
- no reward definitions were changed
- no prompt split definitions were changed
- no credit-unit definitions were changed
- `gate_v1.yaml` remains untouched
- no canonical paper/proposal rewrite has been authorized

This memo is only a context synthesis for PI and agent coordination.
