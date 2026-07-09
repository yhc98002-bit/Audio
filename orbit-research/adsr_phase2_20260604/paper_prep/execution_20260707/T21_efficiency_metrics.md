# T2.1 Efficiency Metrics

Source ledgers:
- Baseline: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/bon256_w*.jsonl`
- Vocal intervention: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/v3_vocal_w*.jsonl`
- Instrumental intervention: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/istrong_instr_w*.jsonl`

## Summary

- Baseline dedup rows: 16384 (raw 16384, dropped 0).
- Prompts: 32 (17 vocal, 15 instrumental).
- Zero-clean prompts at frozen baseline: 0.
- Vocal clean-rate median: 0.0645; mean: 0.0881.
- Instrumental clean-rate median: 0.3613; mean: 0.3591.
- V3 vocal intervention mean delta: +0.6858; improved 17/17 prompts.
- I_strong instrumental intervention mean delta: +0.0055; improved 9/15 prompts.

CSV: `T21_efficiency_metrics.csv`
JSON: `T21_efficiency_metrics.json`
