# A-Prime Gate Report - PI Decision

`A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`

## PI Gate Call

- Provenance: `pi:Richard`.
- Decision date: `2026-07-13`.
- The 690-row provenance-enforced instrument contains 190 PI human-core rows
  and 500 held-out-validated-judge supplement rows.
- The frozen criteria evaluate the legacy Demucs-energy threshold 0.1791.
- The failed disagreement and rare-basin criteria quantify `demucs_missing`.
- The legacy instrument is **not validated** and must never be described as validated.

| Set | Reference | Matches/decided | Match rate | Frozen condition met |
|---|---|---:|---:|---:|
| Detector disagreement | `pi:Richard` | 7/112 | 0.062500 | `false` |
| Rare basin | `pi:Richard` | 16/47 | 0.340426 | `false` |
| Agreement controls | `pi:Richard` | 28/30 | 0.933333 | `true` |
| Stratified global disagreement | validated judge | 124/493 | 0.251521 | outside pass shape |

## Endpoint Scope And Replacement Instrument

A-prime measures Label A (perceived voice presence). The signed amendment's
paper-primary endpoint is Label B (request-conditional constraint satisfaction).
A-prime therefore does not validate or invalidate the paper-primary endpoint.

The positive label-validity evidence is the separate T6 prospective held-out
promotion of the corrected instrument: design-weighted balanced accuracy
0.987308, sensitivity 1.000000, specificity 0.974616, with 20/20 Label-A
and 20/20 Label-B hidden-repeat agreement. This T6 evidence must not be
misreported as an A-prime PASS or as validation of the legacy detector.

## Evidence

- `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_INSTRUMENT_MERGED_690.csv`
- `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`
- `paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`
- `paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md`
- `paper_prep/validation_A_prime/A_PRIME_STUDY_LOG.jsonl`
