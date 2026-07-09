# Early-Tweedie Pruning Validation

Generated UTC: `2026-06-04T04:29:35Z`

## Scope

Early-Tweedie BoN validation from existing prompt splits. This is inference/evaluation only: no RL training, pruning+RL, Phase D, human eval, reward-definition edits, prompt-split edits, or gate activation.

## Run Metadata

| field | value |
|---|---|
| run_root | `runs/early_tweedie_validation_final_lyricfix_20260603` |
| manifest | `orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json` |
| n_prompts | 512 |
| bon_n | 8 |
| metrics | `common_robust_lcb, aesthetic_pq, semantic_fit, lyric_intelligibility` |
| record_files | `['runs/early_tweedie_validation_final_lyricfix_20260603/shard00/candidate_records.jsonl']` |
| shard_logs | `['runs/early_tweedie_validation_final_lyricfix_20260603/shard00_stdout.log', 'runs/early_tweedie_validation_final_lyricfix_20260603/shard00_stderr.log']` |
| gpu_hours_actual_sum | 29.713571 |

## Robust/Common Metric Schedule Summary

| schedule | compute | reward_fraction | winner_match | false_negative | n |
|---|---:|---:|---:|---:|---:|
| full_bon8 | 1.000 | 1.0000 | 1.000 | 0.000 | 512 |
| schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1 | 0.500 | 0.9864 | 0.570 | 0.430 | 512 |
| schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1 | 0.583 | 0.9913 | 0.668 | 0.332 | 512 |
| schedule_c_sigma0.8_keep_top6_final_top1 | 0.850 | 0.9987 | 0.943 | 0.057 | 512 |
| bottom_prune_sigma0.8_remove_bottom25_final_top1 | 0.850 | 0.9987 | 0.943 | 0.057 | 512 |
| bottom_prune_sigma0.7_remove_bottom25_final_top1 | 0.883 | 0.9998 | 0.980 | 0.020 | 512 |
| random_prune_keep4_keep2_final_top1 | 0.500 | 0.9571 | 0.251 | 0.749 | 10240 |

## Interpretation Threshold

- Strong candidate main application result requires `reward_fraction >= 0.98` at `compute_fraction <= 0.5` under robust/common metric and bottom-prune false-negative `<= 5%`.
- If that threshold is not met, treat the result as a conservative inference-time side diagnostic only.

## Output Files

- JSON: `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json`
- Plot CSV: `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv`
- Retention CSV: `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv`
