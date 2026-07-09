# A-prime Human Gate Report

A_PRIME_STATUS = FALLBACK_READY

Input ratings: `paper_prep/validation_A_prime/human_package/A_PRIME_SYNTHETIC_RATINGS.csv`

## Coverage

- Admin rows: 816
- Rating rows read: 12
- Rows joined to admin: 12
- Unanswered/unsure/unparsed rows: 12

## Frozen Criteria

- Rare-basin confirmation: 0/0 = nan; required >= 0.90 on about 50 clips.
- Detector-disagreement agreement with reference label: 0/0 = nan; checklist requires >= 0.70 on 112 cases.
- Agreement-spotcheck failures: 0/0; required <= 2/30.
- Stratified global disagreement: 0/12 = 0.000000; Wilson 95% CI [0.000000, 0.242501].

## Set-Level Human Labels

- `stratified_random_500`: unsure=12

## Interpretation

Do not claim A-prime passed unless `A_PRIME_STATUS = PASS`. If this report says
`FALLBACK_READY`, the package still needs completed PI/human ratings or has
insufficient cardinality for the frozen checklist.
