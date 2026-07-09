# B-prime Human Gate Report

B_PRIME_STATUS = FALLBACK_READY

Input ratings: `paper_prep/validation_B_prime/human_package/B_PRIME_SYNTHETIC_RATINGS.csv`

## Coverage

- Ordered admin rows: 160
- Rating rows read: 12
- Joined ordered rows: 12
- Unanswered/unsure/unparsed ordered rows: 0
- Pair rows with any scored vote: 6
- Decided pairs: 0
- Calibration pairs represented: 1
- Decided calibration pairs: 0

## Pair-Level Primary Result

- Method-preferred decided pairs: 0/0 = nan; Wilson 95% CI [nan, nan].
- One-sided binomial P[X <= observed | p=0.5]: nan; non-inferiority requires not significantly below 50% at 5%.
- Frozen pass shape: method rate >= 0.40 and p >= 0.05.

## Order Bias

- `ab`: tie=6
- `ba`: tie=6

## Interpretation

Do not claim B-prime passed unless `B_PRIME_STATUS = PASS`. If this report says
`FALLBACK_READY`, the package is ready for PI/human ratings but the ratings are
not complete enough for the gate.
