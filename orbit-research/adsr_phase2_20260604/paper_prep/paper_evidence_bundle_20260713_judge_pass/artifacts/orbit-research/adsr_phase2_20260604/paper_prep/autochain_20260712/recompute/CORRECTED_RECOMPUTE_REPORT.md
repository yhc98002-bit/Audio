# Corrected W2 Recompute

`RECOMPUTE_STATUS = COMPLETE_DRAFT_AWAITING_ADOPTION`

The mechanically promoted instrument was applied to all 27,966 target rows. These are draft supersession values only: the W2 amendment still lacks both adoption signatures, so PLAN.md, CLAIMS.md, and frozen historical reports were not changed.

| Cohort / direction | Rows | Apparent | Corrected instrument | Calibrated model | Nested 95% interval |
|---|---:|---:|---:|---:|---:|
| candidate_spine_4096 / instrumental_request | 1568 | 0.2596 | 0.5236 | 0.3865 | [0.3226, 0.4738] |
| candidate_spine_4096 / vocal_request | 2528 | 0.2120 | 0.0024 | 0.0023 | [0.0004, 0.0039] |
| n2_population_retry / instrumental_request | 6016 | 0.2389 | 0.5165 | 0.3924 | [0.3039, 0.5062] |
| n2_population_retry / vocal_request | 10368 | 0.5987 | 0.0125 | 0.0083 | [0.0004, 0.0112] |

Calibration model: `M2`, L2=0.1; selected on the 58 decided train rows only. The 2,000-replicate nested bootstrap resamples frozen calibration strata, refits the selected model form, and resamples target prompts.

Transport source-specific correction required: `false`. Rogan-Gladen direction-stratified estimates are sensitivity analyses, not the primary corrected values.
