# W2 PI-Calibrated Instrument Report

`W2_CALIBRATION_STATUS = COMPLETE_DUAL_PI_ADOPTION_REQUIRED`

The instrument family and threshold(s) were selected on 103 PI-gold clips before the held-out 105 clips were evaluated. This calibration does not modify frozen evidence, `PLAN.md`, or any gate status.

| Candidate | Demucs threshold | PANNs threshold | Train balanced accuracy | Held-out sensitivity | Held-out specificity | Held-out balanced accuracy | Held-out MCC |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_demucs | 0.17910000 | 0.50000000 | 0.436426 | 0.295918 | 0.571429 | 0.433673 | -0.071886 |
| demucs | 0.05074835 | 0.50000000 | 0.682990 | 0.877551 | 0.142857 | 0.510204 | 0.015456 |
| panns | 0.17910000 | 0.08266667 | 0.849656 | 0.785714 | 0.857143 | 0.821429 | 0.366900 |
| or | 0.21282213 | 0.08266667 | 0.859966 | 0.857143 | 0.714286 | 0.785714 | 0.370252 |
| and | 0.03863953 | 0.03181814 | 0.953608 | 0.897959 | 0.714286 | 0.806122 | 0.436436 |

## Frozen Selection

- Family: `and`.
- Demucs threshold: `0.0386395287`.
- PANNs threshold: `0.0318181422`.
- Selection used calibration metrics only; the held-out result did not alter the chosen family or thresholds.
- Adoption into headline claims requires dual-PI review of the downstream old-versus-corrected diff.
