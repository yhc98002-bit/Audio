# A-prime Human-Ready Report

Generated: 2026-07-08

A_PRIME_PACKAGE_STATUS = HUMAN_READY_ZERO_MISSING

This package is for PI/human adjudication. It does not convert A-prime to PASS
until human ratings are recorded and scored by
`paper_prep/validation_A_prime/score_human_A_prime.py`.

## Outputs

- Admin manifest: `paper_prep/validation_A_prime/human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv`
- Rater template: `paper_prep/validation_A_prime/human_package/A_PRIME_HUMAN_RATING_TEMPLATE.csv`
- Blinded media directory: `paper_prep/validation_A_prime/human_package/media/`
- Missing media table: `paper_prep/validation_A_prime/A_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv`
- Synthetic ratings: `paper_prep/validation_A_prime/human_package/A_PRIME_SYNTHETIC_RATINGS.csv`
- Scoring script: `paper_prep/validation_A_prime/score_human_A_prime.py`

## Coverage

- Full A-prime manifest rows: 816
- Human package rater rows with media: 816
- Missing media rows: 0
- Recovered/regenerated media rows used: 100
- Rows with expected/reference present label available: 790

## Set Coverage

- `agreement_spotcheck_30`: 30 rows, 0 missing media
- `detector_disagreement_packet`: 82 rows, 0 missing media
- `phase0_near_threshold_packet`: 130 rows, 0 missing media
- `rare_basin`: 74 rows, 0 missing media
- `stratified_random_500`: 500 rows, 0 missing media

## Important Caveats

- The phase-0 rater packet contains 100 `demucs_whisper_disagree` rows, not the
  112 stated in the checklist. The current deduplicated A-prime manifest has 92
  detector-disagreement rows.
- The previously unavailable rows were dangling symlinks into missing
  `runs/adsr_recollect_resume/...` or `runs/adsr_recollect_20260604_full01/...`
  targets. They are now materialized from the recovered-media manifest when
  available; admin rows record `media_recovery_method` and `recovery_source_path`.
- The rater-facing template contains only blinded media paths and empty answer
  columns; labels and source details are in the admin manifest only.
