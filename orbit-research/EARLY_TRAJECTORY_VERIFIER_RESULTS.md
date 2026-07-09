# Early Trajectory Verifier Results

Generated UTC: `2026-06-03T22:21:11Z`

## Models

Lightweight ridge regressors predict final robust/common reward from early sigma reward vectors, slopes, early ranks, and prompt metadata. No large neural audio model is used.

## Rank/Value Prediction

| split | model | spearman | prompt_ndcg |
|---|---|---:|---:|
| train | ridge_stage_0.9 | 0.5736 | 0.9864 |
| train | ridge_stage_0.8 | 0.7184 | 0.9923 |
| train | ridge_stage_0.7 | 0.8519 | 0.9953 |
| train | raw_early_0.7_common | 0.7548 | 0.9947 |
| validation | ridge_stage_0.9 | 0.7496 | 0.9873 |
| validation | ridge_stage_0.8 | 0.8017 | 0.9925 |
| validation | ridge_stage_0.7 | 0.8800 | 0.9955 |
| validation | raw_early_0.7_common | 0.7769 | 0.9945 |
| test | ridge_stage_0.9 | 0.6424 | 0.9868 |
| test | ridge_stage_0.8 | 0.7780 | 0.9929 |
| test | ridge_stage_0.7 | 0.8697 | 0.9956 |
| test | raw_early_0.7_common | 0.7749 | 0.9949 |

## Learned Pruning Schedules

The pruning schedule table is evaluated on held-out/test prompts only. Train/validation prompts are used only for fitting ridge weights and selecting risk thresholds.

| schedule | compute | reward_fraction | winner_match | fn_top1 | median_regret |
|---|---:|---:|---:|---:|---:|
| etv_schedule_a_sigma0.9_top4_sigma0.7_top2 | 0.500 | 0.9914 | 0.6641 | 0.3359 | 0.0000 |
| etv_schedule_b_sigma0.8_top4_sigma0.7_top2 | 0.583 | 0.9944 | 0.7188 | 0.2812 | 0.0000 |
| etv_schedule_c_sigma0.8_top6 | 0.850 | 0.9994 | 0.9570 | 0.0430 | 0.0000 |
| etv_bottom_prune_sigma0.7_remove_bottom25 | 0.883 | 0.9998 | 0.9922 | 0.0078 | 0.0000 |

## Empirically Calibrated Bottom Pruning

Thresholds are calibrated on validation prompts and measured on held-out/test prompts. The confidence intervals are Wilson binomial intervals; this is empirical risk calibration, not a distribution-free guarantee.

| target | epsilon | prune_bottom | test_compute | test_reward_fraction | test_fn_top1 [95% CI] | test_fn_top2_candidate [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| top1_prompt | 0.01 | 1 | 0.942 | 1.0000 | 0.0000 [0.0000, 0.0148] | 0.0039 [0.0011, 0.0141] |
| top1_prompt | 0.03 | 2 | 0.883 | 0.9998 | 0.0078 [0.0021, 0.0280] | 0.0156 [0.0079, 0.0305] |
| top1_prompt | 0.05 | 3 | 0.825 | 0.9993 | 0.0469 [0.0270, 0.0801] | 0.0605 [0.0430, 0.0847] |
| top2_candidate | 0.01 | 1 | 0.942 | 1.0000 | 0.0000 [0.0000, 0.0148] | 0.0039 [0.0011, 0.0141] |
| top2_candidate | 0.03 | 2 | 0.883 | 0.9998 | 0.0078 [0.0021, 0.0280] | 0.0156 [0.0079, 0.0305] |
| top2_candidate | 0.05 | 2 | 0.883 | 0.9998 | 0.0078 [0.0021, 0.0280] | 0.0156 [0.0079, 0.0305] |
