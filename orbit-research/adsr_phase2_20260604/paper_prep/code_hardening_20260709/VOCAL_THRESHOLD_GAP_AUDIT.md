# Vocal Threshold Gap Audit

`VOCAL_THRESHOLD_GAP_STATUS = FAIL`

The historical value 0.179 and canonical value
0.1791 differ only for candidate ratios in
`[0.179, 0.1791)`. This read-only audit scanned completed ADSR candidate
ledgers and analysis tables.

| Measure | Count |
|---|---:|
| Files discovered | 272 |
| Files containing candidate-ratio fields | 151 |
| Rows parsed | 164847 |
| Candidate-ratio values checked | 90304 |
| Values in `[0.179, 0.1791)` | 7 |
| Parse errors | 0 |

Conclusion: the threshold migration is not label-neutral; inspect the JSON audit before using it.
