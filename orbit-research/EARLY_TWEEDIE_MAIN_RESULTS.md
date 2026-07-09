# Early-Tweedie Main Results

Generated UTC: `2026-06-03T22:21:11Z`

## Scope

Paper-grade offline validation from existing 512-prompt BoN-8 artifacts. No RL training, pruning+RL, Phase D, human crowdsourcing, gate edit, or reward-definition change was launched.

## Primary Robust/Common Metric

| schedule | compute | reward_fraction | winner_match | top2_any | fn_top1 | fn_top2_candidate | median_regret |
|---|---:|---:|---:|---:|---:|---:|---:|
| full_bon8 | 1.000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| bon4_first4 | 0.500 | 0.9819 | 0.4824 | 0.7754 | 0.5176 | 0.5020 | 0.0028 |
| bon4_random_subset | 0.500 | 0.9823 | 0.4986 | 0.7885 | 0.5014 | 0.4992 | 0.0001 |
| raw_schedule_a_sigma0.9_top4_sigma0.7_top2 | 0.500 | 0.9864 | 0.5703 | 0.7871 | 0.4297 | 0.4990 | 0.0000 |
| raw_schedule_b_sigma0.8_top4_sigma0.7_top2 | 0.583 | 0.9913 | 0.6680 | 0.8594 | 0.3320 | 0.4277 | 0.0000 |
| raw_schedule_c_sigma0.8_top6 | 0.850 | 0.9987 | 0.9434 | 0.9922 | 0.0566 | 0.0840 | 0.0000 |
| raw_bottom_prune_sigma0.8_remove_bottom25 | 0.850 | 0.9987 | 0.9434 | 0.9922 | 0.0566 | 0.0840 | 0.0000 |
| raw_bottom_prune_sigma0.7_remove_bottom25 | 0.883 | 0.9998 | 0.9805 | 1.0000 | 0.0195 | 0.0391 | 0.0000 |
| random_prune_keep4_keep2 | 0.500 | 0.9571 | 0.2529 | 0.4633 | 0.7471 | 0.7508 | 0.0702 |

## Same-Compute BoN-4 Check

- Raw ETP@50 reward fraction: `0.9864`.
- Random-subset BoN-4 reward fraction: `0.9823`.
- Reviewer-risk verdict: `PASS`.
- Paired bootstrap delta reward fraction: `0.0038` (95% CI `0.0015`, `0.0061`).

## Cross-Axis Caveat

When pruning selects by `common_robust_lcb`, the same 50% schedule preserves the primary/common and aesthetic axes better than random BoN-4, but it does not uniformly preserve all non-primary axes. The semantic and lyric axes are the main limitation to report rather than overclaiming axis-general quality.

## Output Tables

- `orbit-research/EARLY_TWEEDIE_PARETO.csv`
- `orbit-research/EARLY_TWEEDIE_AXIS_BREAKDOWN.csv`
- `orbit-research/EARLY_TWEEDIE_STRATUM_BREAKDOWN.csv`
- `orbit-research/EARLY_TWEEDIE_CROSS_AXIS_GENERALIZATION.csv`
- `orbit-research/EARLY_TWEEDIE_BON4_BOOTSTRAP.csv`
