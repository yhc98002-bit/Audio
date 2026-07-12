# B-prime Gate Report: PI Drop 2

`B_PRIME_GATE = FAIL_NONINFERIORITY_NOT_ESTABLISHED`

Primary evidence uses only the 80 t3 first presentations. The 24 t4
reversed presentations are excluded from every gate denominator.

## PI Gate Call

- Provenance: `pi:Richard`.
- Decision date: `2026-07-12`.
- Decision: `FAIL_NONINFERIORITY_NOT_ESTABLISHED`.
- Dual-PI notification recorded: `true`.
- The pre-registered non-inferiority bound was not met: the quality
  score LCB was 0.307145 and the exact LCB cross-check was 0.295877,
  both below the required strict threshold of 0.40.
- No re-rating or study enlargement was performed.

Approved paper wording:

> no statistically significant quality preference in either direction
> (method preferred in 42% of decided pairs; one-sided p = 0.156); the
> pre-registered non-inferiority bound (LCB > 0.40) was NOT met, so
> no-quality-degradation is reported as unconfirmed, not established.

Banned phrasings: `no quality loss`, `no degradation`, and
`quality preserved`.

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

As a labeled secondary sensitivity, quality and overall preference
both meet the original >=40% / not-significantly-below-50% rule.
Quality has one-sided p = 0.156163; overall has p = 0.116347.
This does not override the failed pre-registered non-inferiority bound.

## Request-Direction Breakdown

| Endpoint | Direction | Rows | Method | Baseline | Ties | Rate | Score LCB | Exact LCB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `quality_preference` | vocal | 51 | 15 | 21 | 15 | 0.416667 | 0.292017 | 0.277195 |
| `quality_preference` | instrumental | 29 | 5 | 7 | 17 | 0.416667 | 0.219978 | 0.181025 |
| `overall_preference` | vocal | 51 | 12 | 20 | 19 | 0.375000 | 0.249223 | 0.232622 |
| `overall_preference` | instrumental | 29 | 6 | 7 | 16 | 0.461538 | 0.261148 | 0.223955 |
| `constraint_preference` | vocal | 51 | 12 | 20 | 19 | 0.375000 | 0.249223 | 0.232622 |
| `constraint_preference` | instrumental | 29 | 3 | 6 | 20 | 0.333333 | 0.141971 | 0.097747 |

## Disclosed Limitations

- single expert rater.
- 40% tie rate.
- B-prime pairs selected under the pre-W2 detector.
- t4 same-session protocol deviation.

The numerical scorer cannot emit PASS. The final status above is a
PI decision loaded from the append-only study log, not an automatic gate.
