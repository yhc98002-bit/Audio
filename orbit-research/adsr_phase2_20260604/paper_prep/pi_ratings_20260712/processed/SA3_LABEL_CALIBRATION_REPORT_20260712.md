# SA3 Label Calibration: PI Drop 2

`SA3_LABEL_CALIBRATION_STATUS = SCORED_PASS`

Human Yes/No labels are the reference; Unsure is an abstention. Blank
confidence is optional annotation-missing and never a validation failure.

| Stratum | Rows | Yes | No | Unsure | TP | TN | FP | FN | Sensitivity | Specificity | Balanced accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `overall` | 60 | 20 | 36 | 4 | 15 | 25 | 11 | 5 | 0.750000 | 0.694444 | 0.722222 |
| `far_below` | 20 | 0 | 20 | 0 | 0 | 20 | 0 | 0 | NA | 1.000000 | NA |
| `near_threshold` | 20 | 8 | 8 | 4 | 3 | 5 | 3 | 5 | 0.375000 | 0.625000 | 0.500000 |
| `far_above` | 20 | 12 | 8 | 0 | 12 | 0 | 8 | 0 | 1.000000 | 0.000000 | 0.500000 |

- Optional confidence missing: 59/60.
- Frozen package criterion met: `true`.
- SA3 remains a pilot regardless of this calibration result; this
  score does not promote a full second-backbone ADSR claim.
