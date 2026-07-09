# B-prime Human-Ready Report

Generated: 2026-07-08

B_PRIME_PACKAGE_STATUS = HUMAN_READY_ZERO_MISSING

This package is for PI/human B-prime quality validation and calibration. It does
not convert B-prime to PASS until ratings are recorded and scored by
`paper_prep/validation_B_prime/score_human_B_prime.py`.

## Outputs

- Pair admin manifest: `paper_prep/validation_B_prime/human_package/B_PRIME_HUMAN_PAIR_ADMIN.csv`
- Ordered admin manifest: `paper_prep/validation_B_prime/human_package/B_PRIME_HUMAN_ORDERED_ADMIN_MANIFEST.csv`
- Rater template: `paper_prep/validation_B_prime/human_package/B_PRIME_HUMAN_RATING_TEMPLATE.csv`
- Calibration subset: `paper_prep/validation_B_prime/human_package/B_PRIME_CALIBRATION_24_PAIRS.csv`
- Blinded media directory: `paper_prep/validation_B_prime/human_package/media/`
- Missing media table: `paper_prep/validation_B_prime/B_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv`
- Synthetic ratings: `paper_prep/validation_B_prime/human_package/B_PRIME_SYNTHETIC_RATINGS.csv`
- Scoring script: `paper_prep/validation_B_prime/score_human_B_prime.py`

## Coverage

- Pair rows: 80
- Ordered rating rows: 160
- Calibration pairs: 24
- Missing-media pairs: 0

## Randomization / Leakage

- Each pair is presented in both `ab` and `ba` order.
- Rater-facing filenames use opaque rating IDs and A/B letters only.
- Arm identities and source paths are restricted to admin manifests.
