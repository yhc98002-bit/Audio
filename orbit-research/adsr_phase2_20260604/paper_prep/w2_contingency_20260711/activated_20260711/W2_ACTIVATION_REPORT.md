# W2 Corrected-Instrument Activation Report

`W2_ACTIVATION_STATUS = COMPLETE_REVIEW_REQUIRED`

Execution date: 2026-07-12 (Asia/Shanghai)

## Trigger And Scope

The amendment-compliant decisive packet returned `demucs_missing`, activating
the standing W2 contingency. W2 scored every retained audio file without
modifying frozen ledgers, generated audio, `PLAN.md`, or a gate/status line.

| Cohort | Retained files scored |
|---|---:|
| Stage 3 intervention | 6,144 |
| N2 population retry | 16,384 |
| Atlas keeps | 194 |
| 4,096-candidate spine | 1 |
| **Total** | **22,723** |

The other 4,095 candidate-spine rows have no retained media target and were not
regenerated. They remain explicit `not_retained_on_disk` rows in the inventory.

## PI-Gold Calibration

The calibration pool contains 208 unique, checksum-verified original-media
clips with `pi:Richard` Label-A truth: 195 yes and 13 no. Instrument selection
used 103 calibration clips; the 105 held-out clips were opened only after the
family and thresholds were frozen.

| Candidate | Train balanced accuracy | Held-out sensitivity | Held-out specificity | Held-out balanced accuracy | Held-out MCC |
|---|---:|---:|---:|---:|---:|
| Current Demucs 0.1791 | 0.436426 | 0.295918 | 0.571429 | 0.433673 | -0.071886 |
| Tuned Demucs | 0.682990 | 0.877551 | 0.142857 | 0.510204 | 0.015456 |
| Tuned PANNs | 0.849656 | 0.785714 | 0.857143 | 0.821429 | 0.366900 |
| Demucs OR PANNs | 0.859966 | 0.857143 | 0.714286 | 0.785714 | 0.370252 |
| **Demucs AND PANNs** | **0.953608** | **0.897959** | **0.714286** | **0.806122** | **0.436436** |

The calibration-only winner is Demucs ratio at least `0.0386395287` AND PANNs
vocal score at least `0.0318181422`. The held-out set is strongly imbalanced
(98 yes, 7 no), so its specificity estimate is based on seven negatives. This
instrument is a corrected-instrument candidate, not accepted ground truth.

## Execution Audit

- Merged rows: 22,723/22,723.
- Failed or missing rows: 0/22,723.
- Instrument ID: `w2_calibrated_and` on every row.
- Frozen Stage 3/N2 Demucs ratio rows checked: 22,528.
- Frozen ratio/0.1791-label mismatches: 0.
- Demucs execution source: 22,275 reused exact frozen-ledger ratios; 448 rows
  were live-recomputed in the preserved initial pass before the optimization.
- PANNs was run live on every retained file.

The first implementation recomputed both detectors and completed 448 rows. It
was stopped without deleting those rows, then resumed with exact stored Demucs
ratios for Stage 3/N2 and live Demucs only when no stored ratio existed.

## Old Versus Corrected Headlines

| Metric | Old | Corrected | Delta |
|---|---:|---:|---:|
| N2 overall clean rate | 0.533447 | 0.778870 | +0.245422 |
| Stage 3 instrumental both | 0.377083 | 0.078125 | -0.298958 |
| Stage 3 instrumental sampler | 0.344792 | 0.207292 | -0.137500 |
| Stage 3 instrumental text | 0.326042 | 0.177083 | -0.148958 |
| Stage 3 vocal both | 0.779412 | 0.992647 | +0.213235 |
| Stage 3 vocal guidance | 0.781250 | 0.989890 | +0.208640 |
| Stage 3 vocal hints | 0.093750 | 0.655331 | +0.561581 |
| N2 instrumental clean rate | 0.761137 | 0.606715 | -0.154422 |
| N2 vocal clean rate | 0.401331 | 0.878762 | +0.477431 |

| N2 regime | Old prompts | Corrected prompts | Delta |
|---|---:|---:|---:|
| Easy | 67 | 110 | +43 |
| Seed-recoverable | 33 | 9 | -24 |
| Low | 23 | 9 | -14 |
| Rare | 5 | 0 | -5 |

## Interpretation Boundary

This sensitivity result is too large to adopt mechanically. It changes the
Stage 3 decomposition, N2 regime map, and paper wording. The calibration sample
is intentionally enriched for detector disagreements and has only 13 unique
negative clips. It calibrates Label A voice presence, while the signed
amendment makes Label B constraint satisfaction the paper-primary construct.

Therefore:

- the result demonstrates that the frozen Demucs label is not robust to the tested
  human-calibrated detector alternative;
- it does not establish that the corrected numbers are publication truth;
- it cannot change `PLAN.md`, frozen evidence, or claim status without dual-PI
  sign-off and a representative Label-B calibration plan.

## Evidence

- Calibration report: `paper_prep/w2_contingency_20260711/activated_20260711/calibration/W2_INSTRUMENT_CALIBRATION_REPORT.md`
- Calibration JSON: `paper_prep/w2_contingency_20260711/activated_20260711/calibration/W2_INSTRUMENT_CALIBRATION.json`
- Retained inventory: `paper_prep/w2_contingency_20260711/W2_RETAINED_AUDIO_INVENTORY.json`
- Merge audit: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_CORRECTED_MERGE_AUDIT.json`
- Exact diff CSV: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_OLD_VS_CORRECTED_PLAN_DIFF.csv`
- Exact diff report: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_OLD_VS_CORRECTED_PLAN_DIFF_REPORT.md`
- Raw merged ledger: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_CORRECTED_MERGED.jsonl`
- Output checksums: `paper_prep/w2_contingency_20260711/activated_20260711/full_corrected/W2_OUTPUT_SHA256SUMS.txt`

`W2_ADOPTION_STATUS = AWAITING_DUAL_PI_REVIEW`
