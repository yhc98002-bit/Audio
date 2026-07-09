# BoN-16 Pruning Subset Results

Generated UTC: `2026-05-28T20:31:54Z`

## Scope

BoN-16 subset validation on 128 stratified prompts. Inference/evaluation only: no RL training, pruning+RL, Phase D, human crowdsourcing, gate edit, or reward-definition change.

## Results

| schedule | compute | reward_fraction | winner_match | fn_top1 | top2_any | median_regret |
|---|---:|---:|---:|---:|---:|---:|
| full_bon16 | 1.000 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| bon8_first8 | 0.500 | 0.9885 | 0.4766 | 0.5234 | 0.7422 | 0.0042 |
| bon8_random_subset | 0.500 | 0.9868 | 0.5026 | 0.4974 | 0.7748 | 0.0000 |
| raw_etp16_sigma0.9_top8_sigma0.7_top4 | 0.500 | 0.9914 | 0.6094 | 0.3906 | 0.8281 | 0.0000 |
| raw_etp16_sigma0.8_top12 | 0.850 | 0.9990 | 0.9375 | 0.0625 | 0.9922 | 0.0000 |
| random_prune16_keep8_keep4 | 0.500 | 0.9693 | 0.2484 | 0.7516 | 0.4478 | 0.0520 |
| etv16_sigma0.9_top8_sigma0.7_top4 | 0.500 | 0.9940 | 0.6719 | 0.3281 | 0.9062 | 0.0000 |
| etv16_sigma0.8_top12 | 0.850 | 0.9998 | 0.9766 | 0.0234 | 1.0000 | 0.0000 |

## Output Files

- JSON: `orbit-research/BON16_PRUNING_SUBSET_RESULTS.json`
- CSV: `orbit-research/BON16_PRUNING_SUBSET_RESULTS.csv`
- run_root: `runs/early_tweedie_bon16_subset_128_20260528_full01`
- GPU-hours sum: `91.1064`
