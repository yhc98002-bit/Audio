# A-prime Gate Report

Generated: 2026-07-07

A_PRIME_STATUS = FALLBACK_READY

Important: Qwen smoke v2 did not pass. These rows are fallback evidence only
unless a scientifically acceptable replacement validation is approved.

## Inputs / Outputs

- Manifest: `paper_prep/validation_A_prime/A_PRIME_MANIFEST.csv`
- Judgeable manifest: `paper_prep/validation_A_prime/A_PRIME_JUDGEABLE_MANIFEST.csv`
- Raw responses: `paper_prep/validation_A_prime/A_PRIME_RAW_RESPONSES.jsonl`
- Agreement matrix: `paper_prep/validation_A_prime/A_PRIME_AGREEMENT_MATRIX.csv`

## Coverage

- Full manifest rows: 816
- Judgeable rows: 716
- Scored rows: 716
- Missing/unjudgeable manifest rows: 100

## Gate Criteria

- Rare-basin confirmation: 15/74 = 0.202703; required >= 0.90.
- Demucs match on detector-disagreement cases: 0/0 = nan; required >= 70% on 112 cases.
- Agreement spotcheck failures: 0/0; required <= 2/30.
- Stratified 500 disagreement rate versus Demucs: 363/499 = 0.727455; approximate 95% half-width 0.039069.

## Set-Level Counts

- `detector_disagreement_packet`: missing_audio=42, scored=50
- `phase0_near_threshold_packet`: missing_audio=58, scored=92
- `rare_basin_human_package`: disagree=30, match=4
- `rare_clean_protected`: disagree=1, match=13, scored=26
- `stratified_random_500`: disagree=363, match=136, scored=1

## Interpretation

Do not cite A-prime as passed unless `A_PRIME_STATUS = PASS`. If status is
`FALLBACK_READY`, the scored package can support a PI/human adjudication or a
reduced automatic-label caveat, but it is not a validated A-prime pass because
the model smoke did not clear and/or required sample coverage is incomplete.
