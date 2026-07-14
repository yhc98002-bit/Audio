# A-Prime Gate Report - Pooled Judge Completion

`A_PRIME_GATE = PI_CALL_PENDING`

The 190-row human core and nominal 500-row validated-judge supplement are complete and provenance-enforced. The supplement contains 493 unique audio hashes; inference and estimates are deduplicated to 493 clips, while labels map back to all 500 frozen rating IDs for the instrument contract. This report does not auto-pass the gate. The core and supplement measure Label A (perceived voice presence); they do not establish the signed amendment's paper-primary Label-B constraint endpoint.

| Set | Instrument | Matches/decided | Match rate | Frozen condition met |
|---|---|---:|---:|---:|
| Detector disagreement | `pi:Richard` | 7/112 | 0.062500 | `false` |
| Rare basin | `pi:Richard` | 16/47 | 0.340426 | `false` |
| Agreement controls | `pi:Richard` | 28/30 | 0.933333 | `true` |
| Stratified global bound | validated judge | 124/493 | 0.251521 | outside pass shape |

Judge evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`.

Instrument merge: `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_INSTRUMENT_MERGED_690.csv`.
