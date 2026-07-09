# SANITY GATE RESULTS (facts-only)

- rows: 160  | generation errors: 0
- source ledgers: `ledger_w*.jsonl` (4 workers)
- audio manifest: `SANITY_GATE_AUDIO_MANIFEST.csv` (all 160 clips kept as FLAC under `keep/`)

## By control category

| category | n | type-correct | mean Demucs ratio | Demucs↔PANNs agree | near-silent |
|---|---|---|---|---|---|
| A_trivial_vocal | 40 | 0.9 | 0.4098 | 0.85 | 0.0 |
| B_trivial_instrumental | 40 | 0.825 | 0.0825 | 0.75 | 0.0 |
| C_contradictory | 24 | 0.458 | 0.187 | 0.458 | 0.0 |
| D_e2_vocal_tail | 32 | 0.0 | 0.0528 | 0.125 | 0.0 |
| E_instrumental_risk | 24 | 0.375 | 0.257 | 0.792 | 0.0 |

## Auto-flags (hard-interrupt conditions, §13)
- none triggered

## Expected reference (NOT a pass/fail by the agent — PI decides)
- **A_trivial_vocal**: type_correct should be HIGH (≈≥0.8) if pipeline healthy
- **B_trivial_instrumental**: type_correct should be HIGH (≈≥0.8)
- **C_contradictory**: defines the bad/ill-posed reference signature (no expectation)
- **D_e2_vocal_tail**: expected LOW type_correct (these are the frozen failing vocal tail)
- **E_instrumental_risk**: expected MIXED/low (instrumental-leak risk prompts)

## Source trace
- analysis script: `sanity_gate_analyze.py`
- inputs: `ledger_w*.jsonl` (160 rows, 0 gen-errors excluded)
- outputs: `SANITY_GATE_RESULTS.{md,json}`, `SANITY_GATE_AUDIO_MANIFEST.csv`