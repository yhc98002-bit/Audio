# Exit-1 Evaluator Comparison v2

This report supersedes `analysis_exit1/EVALUATOR_COMPARISON_TABLE.md`. The v1 tree is preserved unchanged and used only as checksum-recorded input evidence.

## Canonical instrument

Exact line parsed from `T6_PROMOTION_REPORT.md`:

> - Selected family: `or`.

`T6_PROMOTION_RESULT.json` SHA-256: `2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2`.
The family and thresholds below were parsed from that JSON; they were not hard-coded in the Exit-1 evaluator.

## Panel A - PI-only held-out gold (primary)

**Panel A decided counts: 117 positive; 9 negative; 126 total.**

**POWER_LIMITED:** PI-only decided negatives = 9 < 30. Every Panel-A metric is marked accordingly; these estimates must not be presented as adequately powered specificity evidence.

| Instrument | Frozen operationalization | Sensitivity (95% CI) | Specificity (95% CI) | Balanced accuracy (95% CI) | MCC (95% CI) |
|---|---|---:|---:|---:|---:|
| Legacy Demucs energy ratio | Demucs >= 0.1791 | 0.256 [0.160, 0.342] **POWER_LIMITED** | 0.444 [0.167, 1.000] **POWER_LIMITED** | 0.350 [0.205, 0.609] **POWER_LIMITED** | -0.172 [-0.320, 0.085] **POWER_LIMITED** |
| Canonical promoted Demucs OR PANNs | Demucs >= 0.0316177709 OR PANNs >= 0.0440341365 | 1.000 [1.000, 1.000] **POWER_LIMITED** | 0.000 [0.000, 0.000] **POWER_LIMITED** | 0.500 [0.500, 0.500] **POWER_LIMITED** | 0.000 [0.000, 0.000] **POWER_LIMITED** |
| PANNs only | PANNs >= 0.04879267 (train-selected) | 0.940 [0.877, 0.991] **POWER_LIMITED** | 0.778 [0.500, 1.000] **POWER_LIMITED** | 0.859 [0.730, 0.991] **POWER_LIMITED** | 0.588 [0.369, 0.863] **POWER_LIMITED** |
| Whisper transcript | non-empty AND confidence >= 0.28481825 (train-selected) | 0.744 [0.649, 0.849] **POWER_LIMITED** | 0.778 [0.500, 1.000] **POWER_LIMITED** | 0.761 [0.619, 0.909] **POWER_LIMITED** | 0.295 [0.099, 0.454] **POWER_LIMITED** |
| AudioSet tagger | speech/singing max >= 0.05733276 (train-selected) | 0.932 [0.879, 0.976] **POWER_LIMITED** | 0.444 [0.100, 1.000] **POWER_LIMITED** | 0.688 [0.515, 0.973] **POWER_LIMITED** | 0.330 [0.028, 0.691] **POWER_LIMITED** |

## Panel B - merged PI plus validated-judge held-out gold (supplemental)

**Panel B decided counts: 416 positive; 35 negative; 451 total.**

Panel B is a precision supplement, not a replacement for Panel A. It includes validated-judge labels and must retain that instrument qualification.

| Instrument | Frozen operationalization | Sensitivity (95% CI) | Specificity (95% CI) | Balanced accuracy (95% CI) | MCC (95% CI) |
|---|---|---:|---:|---:|---:|
| Legacy Demucs energy ratio | Demucs >= 0.1791 | 0.202 [0.153, 0.264] | 0.829 [0.667, 0.971] | 0.515 [0.436, 0.594] | 0.020 [-0.084, 0.127] |
| Canonical promoted Demucs OR PANNs | Demucs >= 0.0316177709 OR PANNs >= 0.0440341365 | 1.000 [1.000, 1.000] | 0.600 [0.400, 0.800] | 0.800 [0.700, 0.900] | 0.762 [0.615, 0.887] |
| PANNs only | PANNs >= 0.04879267 (train-selected) | 0.969 [0.946, 0.988] | 0.857 [0.727, 0.963] | 0.913 [0.848, 0.968] | 0.752 [0.625, 0.875] |
| Whisper transcript | non-empty AND confidence >= 0.28481825 (train-selected) | 0.498 [0.429, 0.572] | 0.829 [0.708, 0.939] | 0.663 [0.595, 0.732] | 0.175 [0.098, 0.257] |
| AudioSet tagger | speech/singing max >= 0.05733276 (train-selected) | 0.957 [0.933, 0.977] | 0.771 [0.565, 0.958] | 0.864 [0.761, 0.957] | 0.650 [0.478, 0.810] |

## Threshold fitting and uncertainty

The canonical promoted rule and legacy Demucs threshold are frozen. PANNs-only, Whisper, and AudioSet thresholds were selected on the pre-existing 238-row training split only. Panels A and B use held-out rows only. Intervals are percentile 95% prompt-cluster bootstraps with 10,000 replicates and seed `2026071602`.

No BOLT output, new human label, or new model inference entered this v2 analysis.
