# Trajectory-Aware Inference-Time Scaling PI Report

Generated UTC: `2026-05-28T20:42:22Z`
Report status: `COMPLETE`

## Executive Summary

The project is now best framed as early trajectory verification for flow-matching music generation. C1 RL post-training remains useful boundary evidence because the backend trained cleanly but common downstream evaluation showed no clear winner. The positive evidence is instead concentrated in Early-Tweedie / Early Trajectory Verifier inference-time selection.

Main current conclusion: raw Early-Tweedie pruning is a credible transparent baseline, while the learned lightweight ETV is the stronger candidate for the main method when the claim is risk-aware pruning rather than simple heuristic pruning.

## Dataset Card

- Dataset: `orbit-research/trajectory_candidate_dataset.jsonl`
- Dataset card: `orbit-research/TRAJECTORY_CANDIDATE_DATASET_CARD.md`
- Candidates: `4096`
- Prompts: `512`
- Analysis splits: `{'test': 2048, 'train': 1552, 'validation': 496}`
- Split rule: prompt-level split only; no prompt's candidates cross train/validation/test boundaries.

## Main BoN-8 Early-Tweedie Result

| method | compute | reward_fraction | winner_match | false_negative_top1 |
|---|---:|---:|---:|---:|
| Full BoN-8 | 1.000 | 1.0000 | 1.0000 | 0.0000 |
| BoN-4 random subset | 0.500 | 0.9821 | 0.4976 | 0.5024 |
| Raw ETP Schedule A | 0.500 | 0.9858 | 0.5762 | 0.4238 |
| Raw ETP Schedule C | 0.850 | 0.9986 | 0.9395 | 0.0605 |
| Bottom-prune sigma0.7 remove bottom25 | 0.883 | 0.9996 | 0.9805 | 0.0195 |
| Random prune matched to Schedule A | 0.500 | 0.9568 | 0.2527 | 0.7473 |

Same-compute BoN-4 comparison:

- ETP@50 reward fraction: `0.9858`.
- BoN-4 random-subset reward fraction: `0.9821`.
- Paired bootstrap delta reward fraction: `0.0036` with 95% CI `[0.0013, 0.0060]`.
- Interpretation: the primary/common-axis advantage is statistically separated but modest; do not overstate the effect size.

Cross-axis caveat:

- Common-selected ETP@50 evaluated on `semantic_fit` has reward_fraction `0.8384`.
- Common-selected ETP@50 evaluated on `lyric_intelligibility` has reward_fraction `0.8432`.
- The semantic and lyric axes are the main limitation; the paper should not claim uniform all-axis preservation.

## Learned ETV Result

| method | compute | reward_fraction | winner_match | false_negative_top1 |
|---|---:|---:|---:|---:|
| Learned ETV Schedule A | 0.500 | 0.9907 | 0.6641 | 0.3359 |
| Learned ETV bottom-prune sigma0.7 remove bottom25 | 0.883 | 0.9998 | 0.9922 | 0.0078 |

Prediction evidence:

- `ridge_stage_0.9`: Spearman `0.6723`, prompt NDCG `0.9871`.
- `ridge_stage_0.8`: Spearman `0.7892`, prompt NDCG `0.9928`.
- `ridge_stage_0.7`: Spearman `0.8768`, prompt NDCG `0.9951`.
- `raw_early_0.7_common`: Spearman `0.7853`, prompt NDCG `0.9946`.

Empirical risk-calibrated pruning:

| target | epsilon | prune_bottom | test_compute | test_reward_fraction | test_fn_top1 | test_fn_top2_candidate |
|---|---:|---:|---:|---:|---:|---:|
| top1_prompt | 0.01 | 2 | 0.883 | 0.9998 | 0.0078 | 0.0176 |
| top1_prompt | 0.03 | 2 | 0.883 | 0.9998 | 0.0078 | 0.0176 |
| top1_prompt | 0.05 | 3 | 0.825 | 0.9988 | 0.0391 | 0.0605 |
| top2_candidate | 0.01 | 1 | 0.942 | 0.9999 | 0.0039 | 0.0039 |
| top2_candidate | 0.03 | 2 | 0.883 | 0.9998 | 0.0078 | 0.0176 |
| top2_candidate | 0.05 | 2 | 0.883 | 0.9998 | 0.0078 | 0.0176 |

This is empirical validation-calibrated pruning, not a distribution-free risk-control guarantee.

## BoN-16 Subset

- Status: `COMPLETE`.
- Run root: `runs/early_tweedie_bon16_subset_128_20260528_full01`
- Result files: `orbit-research/BON16_PRUNING_SUBSET_RESULTS.md`, `.json`, `.csv`
- Prompts: `128`
- Candidates: `2048`
- GPU-hours summed over shards: `91.1064`

| BoN-16 method | compute | reward_fraction | winner_match | false_negative_top1 |
|---|---:|---:|---:|---:|
| full_bon16 | 1.000 | 1.0000 | 1.0000 | 0.0000 |
| bon8_first8 | 0.500 | 0.9885 | 0.4766 | 0.5234 |
| bon8_random_subset | 0.500 | 0.9868 | 0.5026 | 0.4974 |
| raw_etp16_sigma0.9_top8_sigma0.7_top4 | 0.500 | 0.9914 | 0.6094 | 0.3906 |
| raw_etp16_sigma0.8_top12 | 0.850 | 0.9990 | 0.9375 | 0.0625 |
| random_prune16_keep8_keep4 | 0.500 | 0.9693 | 0.2484 | 0.7516 |
| etv16_sigma0.9_top8_sigma0.7_top4 | 0.500 | 0.9940 | 0.6719 | 0.3281 |
| etv16_sigma0.8_top12 | 0.850 | 0.9998 | 0.9766 | 0.0234 |

## Human Spot-Check Packet

- Manifest: `orbit-research/human_spotcheck_packet_20260528/HUMAN_SPOTCHECK_PACKET_MANIFEST.md`
- Audio status: `present`
- No crowdsourcing or human evaluation was launched.

## Global Quality Mechanism

- Mechanism memo: `orbit-research/GLOBAL_QUALITY_MECHANISM_FIGURES.md`
- Mechanism tables: `orbit-research/GLOBAL_QUALITY_MECHANISM_TABLES.csv`
- Interpretation: for ACE-Step short-form outputs, local-window rewards appear to track persistent global trajectory quality more than isolated local failures. This supports trajectory-aware inference-time selection and helps explain the weak RL-local-credit result.

## ICLR Reviewer-Risk Audit

- Audit memo: `orbit-research/ICLR_REVIEWER_RISK_AUDIT.md`
- Claude dataset/leakage audit: `ACCEPT_WITH_NONBLOCKING_NOTES`
- Claude same-compute baseline audit: `ACCEPT_WITH_NONBLOCKING_NOTES`
- Claude learned ETV/risk audit: `ACCEPT_WITH_NONBLOCKING_NOTES`

Main risks to disclose:

- The ETP@50 improvement over BoN-4 is small on the primary/common metric.
- Common-selected pruning weakens semantic/lyric cross-axis preservation relative to BoN-4.
- Empirical risk calibration is not a formal distribution-free guarantee.
- Human listening packet is prepared for PI review, but crowdsourcing has not been launched.

## Recommended Paper Framing

Recommended framing: **learned ETV as the main method candidate, with raw ETP as the transparent mechanistic baseline**.

Rationale:

- Raw ETP proves that early Tweedie estimates contain exploitable trajectory information.
- Learned ETV improves held-out rank prediction and conservative pruning, especially bottom-pruning.
- The mechanism analysis gives a coherent story: early local estimates are useful because quality differences are persistent across the short-form trajectory.
- RL post-training should be described as a bounded negative/boundary result rather than the main contribution.

## Remaining PI Decisions

- Whether to make learned ETV or raw ETP the headline method.
- Whether to run PI listening on the prepared human spot-check packet.
- Whether cross-axis semantic/lyric weakness requires a mitigation experiment or should be treated as a limitation.
- Whether to pursue a formal Learn-then-Test / conformal risk-control version after the current empirical result.

## Boundary Confirmation

- No new RL training launched.
- No pruning+RL launched.
- No Phase D launched.
- No human crowdsourcing launched.
- No `gate_v1.yaml` modification.
- No reward-definition change.
- No prompt-split change.
- No sigma definition change outside declared pruning schedules.
- No canonical proposal rewrite.
