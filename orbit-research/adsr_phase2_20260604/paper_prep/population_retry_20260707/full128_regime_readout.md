# Population Retry Read-Out

Verdict: **PASS**
Rows: 16384
Prompts: 128
Expected rows: 16384

## Regime Counts

| Regime | Prompts | Fraction |
|---|---:|---:|
| easy_ge_1_in_2 | 67 | 0.523438 |
| low_1_in_16_to_1_in_4 | 23 | 0.179688 |
| rare_le_1_in_16 | 5 | 0.039062 |
| seed_recoverable_1_in_4_to_1_in_2 | 33 | 0.257812 |

## Baseline-Violation Bin Summary

| Baseline violations in 8 | Prompts | Mean clean rate | Regime counts |
|---:|---:|---:|---|
| 0 | 51 | 0.746017 | `{'easy_ge_1_in_2': 42, 'low_1_in_16_to_1_in_4': 1, 'seed_recoverable_1_in_4_to_1_in_2': 8}` |
| 1 | 24 | 0.549805 | `{'easy_ge_1_in_2': 13, 'low_1_in_16_to_1_in_4': 3, 'seed_recoverable_1_in_4_to_1_in_2': 8}` |
| 2 | 17 | 0.403493 | `{'easy_ge_1_in_2': 6, 'low_1_in_16_to_1_in_4': 6, 'seed_recoverable_1_in_4_to_1_in_2': 5}` |
| 3 | 8 | 0.390625 | `{'easy_ge_1_in_2': 2, 'low_1_in_16_to_1_in_4': 3, 'seed_recoverable_1_in_4_to_1_in_2': 3}` |
| 4 | 11 | 0.318892 | `{'easy_ge_1_in_2': 3, 'low_1_in_16_to_1_in_4': 4, 'seed_recoverable_1_in_4_to_1_in_2': 4}` |
| 5 | 8 | 0.177734 | `{'low_1_in_16_to_1_in_4': 3, 'rare_le_1_in_16': 3, 'seed_recoverable_1_in_4_to_1_in_2': 2}` |
| 6 | 5 | 0.207813 | `{'low_1_in_16_to_1_in_4': 2, 'rare_le_1_in_16': 1, 'seed_recoverable_1_in_4_to_1_in_2': 2}` |
| 7 | 2 | 0.207031 | `{'low_1_in_16_to_1_in_4': 1, 'seed_recoverable_1_in_4_to_1_in_2': 1}` |
| 8 | 2 | 0.335938 | `{'easy_ge_1_in_2': 1, 'rare_le_1_in_16': 1}` |

## Stratum Summary

- `instrumental`: 47 prompts, mean clean rate 0.761137, regimes `{'easy_ge_1_in_2': 39, 'low_1_in_16_to_1_in_4': 1, 'seed_recoverable_1_in_4_to_1_in_2': 7}`
- `vocal`: 81 prompts, mean clean rate 0.401331, regimes `{'easy_ge_1_in_2': 28, 'low_1_in_16_to_1_in_4': 22, 'rare_le_1_in_16': 5, 'seed_recoverable_1_in_4_to_1_in_2': 26}`
