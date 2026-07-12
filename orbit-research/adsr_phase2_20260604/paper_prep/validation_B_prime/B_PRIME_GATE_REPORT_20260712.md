# B-prime Gate Report: PI Drop 2

`B_PRIME_GATE = PI_CALL_PENDING`

Primary evidence uses only the 80 t3 first presentations. The 24 t4
reversed presentations are excluded from every gate denominator.

## Endpoint Results

| Endpoint | Method | Baseline | Ties | Abstains | Rate | Score LCB | Exact LCB | Score > .40 | Exact > .40 | Ties half | Ties against |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `quality_preference` | 20 | 28 | 32 | 0 | 0.416667 | 0.307145 | 0.295877 | false | false | 0.450000 | 0.250000 |
| `overall_preference` | 18 | 27 | 35 | 0 | 0.400000 | 0.288866 | 0.276826 | false | false | 0.443750 | 0.225000 |
| `constraint_preference` | 15 | 26 | 39 | 0 | 0.365854 | 0.254029 | 0.240809 | false | false | 0.431250 | 0.187500 |

## Condition Booleans

- Frozen signed score-LCB condition met: `false`.
- Exact-LCB cross-check met: `false`.
- Both lower bounds exceed 0.40: `false`.
- Final gate call made mechanically: `false`.

## Original Frozen-Rule Sensitivity

This is secondary only: method preference at least 40% and not
significantly below 50% by the one-sided exact lower-tail test.

| Endpoint | Rate >= .40 | p(lower tail at .50) | Not below .50 | Rule met |
|---|---:|---:|---:|---:|
| `quality_preference` | true | 0.156163 | true | true |
| `overall_preference` | true | 0.116347 | true | true |
| `constraint_preference` | false | 0.058638 | true | false |

## Request-Direction Breakdown

| Endpoint | Direction | Rows | Method | Baseline | Ties | Rate | Score LCB | Exact LCB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `quality_preference` | vocal | 51 | 15 | 21 | 15 | 0.416667 | 0.292017 | 0.277195 |
| `quality_preference` | instrumental | 29 | 5 | 7 | 17 | 0.416667 | 0.219978 | 0.181025 |
| `overall_preference` | vocal | 51 | 12 | 20 | 19 | 0.375000 | 0.249223 | 0.232622 |
| `overall_preference` | instrumental | 29 | 6 | 7 | 16 | 0.461538 | 0.261148 | 0.223955 |
| `constraint_preference` | vocal | 51 | 12 | 20 | 19 | 0.375000 | 0.249223 | 0.232622 |
| `constraint_preference` | instrumental | 29 | 3 | 6 | 20 | 0.333333 | 0.141971 | 0.097747 |

The numerical scorer cannot emit PASS. Richard must make and record
the PI gate call after reviewing this report and the t4 deviation.
