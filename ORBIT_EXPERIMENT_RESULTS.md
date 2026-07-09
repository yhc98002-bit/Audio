# ORBIT Experiment Results

Last refreshed: 2026-05-28

This file is now a compact current-results index. Detailed historical live-run
snapshots were preserved in the documentation hygiene archive.

## Current Overall Result

The trajectory-aware cycle is in final validation, not yet complete.

Main conclusions:

- C1 RL post-training completed cleanly, but common dev eval showed
  `COMMON_DEV_NO_CLEAR_WIN`.
- BoN-8 Early-Tweedie pruning is the strongest positive result so far.
- BoN-16 subset validation is currently running and is required before the final
  PI report can be marked complete.
- Time-uniform/global quality analysis supports persistent global quality
  differences over isolated local-window failures.
- RL rescue triage was stopped before GPU launch.

## Key Result Files

| Result | Artifact |
|---|---|
| Live status | `orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.md` |
| Full current synthesis | `orbit-research/TRAJECTORY_AWARE_EXPERIMENT_PROGRESS_2026-05-28.md` |
| PI report draft/final target | `orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md` |
| Completion check | `orbit-research/TRAJECTORY_PHASE_COMPLETION_CHECK_2026-05-28.md` |
| Early-Tweedie main BoN-8 results | `orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.md` |
| Learned ETV results | `orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.md` |
| BoN-16 subset results | `orbit-research/BON16_PRUNING_SUBSET_RESULTS.md` |
| Human spot-check packet | `orbit-research/human_spotcheck_packet_20260528/HUMAN_SPOTCHECK_PACKET_MANIFEST.md` |
| Global quality analysis | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| C1 common eval | `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` |
| C1 dynamics audit | `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md` |
| Checkpoint triage | `orbit-research/PHASE_C1_CHECKPOINT_TRIAGE_EVAL_2026-05-26.md` |
| RL rescue stop | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` |

## Headline Numbers

### Live BoN-16 Subset Status

- Status source: `orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.md`
- Scope: 128 prompts, 2048 BoN-16 candidates target.
- Automatic finalizer: `trajectory_phase_finalizer_20260528`.
- Completion remains pending until BoN-16 reaches 2048 records, spot-check audio
  is regenerated, and `scripts/verify_trajectory_phase_completion.py` passes.

### Early-Tweedie Validation

- Scope: 512 prompts, 4096 BoN-8 candidates.
- Schedule A, sigma0.9 top4 -> sigma0.7 top2 -> final top1:
  reward fraction `0.9858` at compute fraction `0.5000`.
- Conservative bottom-prune at sigma0.7:
  bottom-25 false-negative `0.0195`.
- BoN-4 same-compute comparison: ETP@50 reward fraction `0.9858` vs BoN-4
  random-subset `0.9821`; paired bootstrap delta reward fraction `0.0036`
  with 95% CI `[0.0013, 0.0060]`.
- Cross-axis caveat: semantic and lyric axes are weaker under common-selected
  ETP@50 and must be reported as limitations.

### Learned ETV

- Test Spearman at sigma0.7: `0.8768`.
- Test prompt NDCG at sigma0.7: `0.9951`.
- Learned ETV Schedule A reward fraction: `0.9907` at compute fraction `0.500`.
- Learned bottom-prune sigma0.7 remove bottom25: reward fraction `0.9998`,
  false-negative top1 `0.0078`.
- Risk language is empirical validation-calibrated pruning, not a
  distribution-free guarantee.

### C1 Common Dev Eval

| Target | robust_lcb_mean | Delta vs Base |
|---|---:|---:|
| Base | 2.133676 | 0.000000 |
| R8a step1000 | 2.145297 | +0.011621 |
| R8b step1000 | 2.148166 | +0.014490 |
| M-FixedWin step1000 | 2.145825 | +0.012149 |
| M-Section step1000 | 2.146055 | +0.012379 |

Interpretation: small positive deltas, no separable method win.

### Global Quality Structure

- median between-share `0.5839`
- between/within ratio `1.4038`
- crossing frequency `0.0000`
- globalness index `0.8613`

Interpretation: local windows appear to track persistent global quality more than
isolated local failures.

## Boundaries

No Phase D, human evaluation, pruning+RL, additional full RL training, or
canonical proposal rewrite is authorized by these results.

## Historical Results Snapshot

The previous C1 live-run results board was preserved at:

`orbit-research/archive/2026-05-doc-hygiene-post-c1/repo-root-md/ORBIT_EXPERIMENT_RESULTS.legacy_2026-05-28.md`
