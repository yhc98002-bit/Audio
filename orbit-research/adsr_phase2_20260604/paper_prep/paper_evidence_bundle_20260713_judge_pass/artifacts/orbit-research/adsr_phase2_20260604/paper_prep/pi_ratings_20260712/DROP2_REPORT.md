# Drop 2 PI Ratings Report

Date: 2026-07-12/13 (Asia/Shanghai)
Scope: ingest the t3/t4/t5 `pi:Richard` exports, score the B-prime numerical
conditions without making the PI gate call, record the t4 protocol deviation,
and score the SA3 label-calibration pilot.

## Status Contract

DROP2_INGESTION = PASS
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_INGEST_AUDIT.json`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/T3_B_PRIME_PRIMARY_OFFICIAL.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/T4_B_PRIME_REVERSE_OFFICIAL.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/T5_SA3_CALIBRATION_OFFICIAL.csv`

B_PRIME_GATE = PI_CALL_PENDING
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_REPORT_20260712.md`, `orbit-research/adsr_phase2_20260604/paper_prep/validation_B_prime/B_PRIME_GATE_RESULT_20260712.json`

T4_DEVIATION_LOGGED = YES
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/DROP2_STUDY_LOG.jsonl`, `orbit-research/adsr_phase2_20260604/paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709_APPENDIX_20260712.md`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/T4_ORDER_BIAS_AND_RELIABILITY_REPORT_20260712.md`

SA3_CALIBRATION = SCORED_PASS
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/SA3_LABEL_CALIBRATION_REPORT_20260712.md`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/SA3_LABEL_CALIBRATION_RESULT_20260712.json`

TEST_SUITE_STATUS = PASS
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_FULL_TEST_RESULTS.txt`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_FULL_TEST_RESULTS.exit`, `orbit-research/adsr_phase2_20260604/paper_prep/pi_ratings_20260712/processed/DROP2_FULL_TEST_RESULTS_METADATA.json`

## Ingestion

All three exports matched their v2 keys-side manifests exactly, carried the
required `pi:Richard` provenance, and had no blank required answers.

| Bundle | Expected IDs | Received IDs | Exact set | Required-answer blanks | Optional confidence blanks |
|---|---:|---:|---|---:|---:|
| t3 primary | 80 | 80 | yes | 0 | 0 |
| t4 reverse | 24 | 24 | yes | 0 | 0 |
| t5 SA3 | 60 | 60 | yes | 0 | 59 |

The t5 confidence field is optional by protocol. Its 59 blank values are
annotation-missing and did not invalidate any row. The pipeline was executed
twice: all generated scoring artifacts retained identical SHA256 hashes, and
the idempotent t4 study log retained exactly one deviation event.

Input SHA256 values:

- t3: `030d84866b1b2be015c230796fa7946f799e02997cc3da2801c2d34e9ffbb9c1`
- t4: `0b63fbb518971d23860b5c34524ae49d4c2e46435b2abe0fce7c6cf54ceb3ac5`
- t5: `d448588b0b1fd2c3120d7fc86a742a8a52e74a09bdcd5c9f87c72c8eb5ff79f9`

## B-prime Primary Gate Inputs

Only the 80 t3 first presentations enter the gate denominator. Ties are
excluded from the primary rate. The signed primary condition is a one-sided
95% score lower confidence bound above 0.40; an exact lower bound is reported
as a cross-check. The scorer is fail-closed and cannot emit PASS.

| Endpoint | Method | Baseline | Ties | Decided method rate | Score LCB | Exact LCB | Signed condition |
|---|---:|---:|---:|---:|---:|---:|---|
| quality (primary) | 20 | 28 | 32 | 0.416667 | 0.307145 | 0.295877 | not met |
| overall | 18 | 27 | 35 | 0.400000 | 0.288866 | 0.276826 | not met |
| constraint | 15 | 26 | 39 | 0.365854 | 0.254029 | 0.240809 | not met |

Primary tie sensitivities are 0.450000 with ties as half and 0.250000 with
ties against the method. Under the labeled secondary original rule, quality
meets the `>=40%` plus not-significantly-below-50% check (`p=0.156163`), but
that secondary does not override the signed lower-bound condition. Request-
direction breakdowns are in the gate report. The required disposition remains
`PI_CALL_PENDING`; no automatic PASS or FAIL was recorded.

## t4 Deviation

The t3 export was written at `2026-07-12T16:36:43.026Z`; t4 was written at
`2026-07-12T17:09:36.829Z`, only 1,973.803 seconds later and on the same UTC
day. This violates the later-day rule and is logged as
`PROTOCOL_DEVIATION_T4_SAME_SESSION`. All t4 agreement values are therefore
upper bounds. The t6 hidden-repeat block supersedes t4 as the primary
rater-stability evidence.

- Quality arm-mapped agreement upper bound: 10/24 (0.416667).
- Overall arm-mapped agreement upper bound: 14/24 (0.583333).
- Constraint arm-mapped agreement upper bound: 15/24 (0.625000).
- One answer triple was non-identical across endpoints:
  `r_948a9b024a4595ffc8a6` / `bprime_0104_326d135bd3e2`.
- One row answered overall before constraint after a valid reveal:
  `r_ea04ed1265668c57303f` / `bprime_0094_c00387063c17`.

Neither informational row changes the t3 gate counts. The signed amendment
was not modified; the deviation is recorded in a dated appendix.

## SA3 Calibration

Unsure is treated as abstention. Across 60 rows there were 20 Yes, 36 No, and
4 Unsure ratings. On 56 decided rows, sensitivity was 0.750000, specificity
0.694444, and balanced accuracy 0.722222. The package's frozen balanced-
accuracy criterion was met.

| Stratum | Yes | No | Unsure | Sensitivity | Specificity | Balanced accuracy |
|---|---:|---:|---:|---:|---:|---:|
| far below | 0 | 20 | 0 | NA | 1.000000 | NA |
| near threshold | 8 | 8 | 4 | 0.375000 | 0.625000 | 0.500000 |
| far above | 12 | 8 | 0 | 1.000000 | 0.000000 | 0.500000 |

`SCORED_PASS` applies only to this calibration package. SA3 remains a pilot;
this result does not promote a full second-backbone ADSR claim.

## Housekeeping And W2

`LIGHT_PLAN_ADDENDUM_DISPOSITION = UNUSED` was already recorded in
`paper_prep/LIGHT_PLAN_ADDENDUM_UNUSED_NOTE_20260712.md`; the signed historical
addendum remains unchanged.

Drop 2 is independent of the W2 execution package and did not wait on or alter
it. W2 was dispatched and its compact evidence package is committed: exact
spine recovery passed, the t6 calibration package is
`READY_BLOCKED_ON_SIGNATURE`, the factorial was generated, and downstream
promotion remains blocked on ratings/signatures. The authoritative dispatch
record is `paper_prep/w2_execution_20260712/W2_EXECUTION_REPORT.md`.

## Implementation And Tests

- Evidence implementation commit: `e30f40f9f9ee14ff07557f6b17e205fb174dfcb8`
  (`DROP2: ingest PI B-prime and SA3 ratings`).
- W2 dispatch/report commit immediately preceding Drop 2: `0df1cbb0a01c045c00cd9920edee04d1535b788f`.
- Scorer: `paper_prep/scripts/ingest_drop2_ratings_20260712.py`.
- Drop 2 tests: `tests/test_ingest_drop2_ratings_20260712.py`, 8/8 passed.
- Full command: `/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python -m pytest -q`.
- Full result: 306/306 passed, exit code 0.
- Full output SHA256: `7fe91ad5fb746be448eeb2b9046edd2af9503c92d8a929f2a082bb52308cd497`.

## Remaining PI Call

Richard must make the final B-prime gate disposition after reviewing the
signed-condition miss and the t4 same-session deviation. This is the only
decision introduced by Drop 2; no engineering task is being mislabeled as a
PI decision.
