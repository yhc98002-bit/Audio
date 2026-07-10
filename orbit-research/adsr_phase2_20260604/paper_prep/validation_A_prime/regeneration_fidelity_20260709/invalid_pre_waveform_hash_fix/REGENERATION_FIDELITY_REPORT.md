# Regeneration Fidelity Report

`REGENERATION_FIDELITY_STATUS = NOT_REPRODUCIBLE`

## Protocol

- 50 controls were selected from the reconstructed 112-case primary A-prime
  universe; every source is original media.
- Historical candidate seeds were replayed in an isolated output directory.
- Generation settings match the frozen recollection summaries: ACE-Step v1,
  30 steps, CFG 5.0, `cfg_type=cfg`, guidance interval 0.5, bf16.
- Canonical relabeling uses `htdemucs`, `apply_model(..., split=True,
  overlap=0.1)`, `near_silent = rms < 1e-3`, and threshold 0.1791.
- CLAP comparison is audio-embedding cosine between the original and replay,
  using the project-pinned `630k-audioset-best` checkpoint.

## Control Results

| Measure | Result |
|---|---:|
| Controls completed | 50/50 |
| Exact waveform SHA256 | 0/50 |
| Same sample rate | 50/50 |
| Demucs label flips | 2/50 |
| Mean absolute rescored Demucs-ratio delta | 0.003349 |
| Mean aligned waveform NRMSE | 0.000000 |
| Mean CLAP audio cosine | 0.802084 |
| Minimum CLAP audio cosine | 0.451021 |
| Manual mismatch flags completed | 0/50 (`UNRATED`; review queue is explicit in the CSV) |

## Regenerated-Cohort Relabeling

| Cohort | Rows | Label flips | Mean absolute ratio delta | Maximum absolute ratio delta |
|---|---:|---:|---:|---:|
| A-prime regenerated media | 100 | 18 | 0.015857 | 0.117989 |
| Rare-clean regenerated media | 26 | 2 | 0.002833 | 0.012339 |

## Interpretation

`NOT_REPRODUCIBLE` is mechanical: `EXACT` requires all 50 waveform hashes to match;
`LABEL_STABLE_ONLY` requires zero canonical-label flips across controls and both
regenerated cohorts when hashes are not exact; otherwise the result is
`NOT_REPRODUCIBLE`.

Regenerated rows remain sensitivity-only unless this report is `EXACT` or
`LABEL_STABLE_ONLY` and dual-PI approval explicitly admits them. T1 separately
restored all 112 primary disagreement clips as originals, so the primary A-prime
gate does not depend on regenerated media.

## Artifacts

- `paper_prep/validation_A_prime/REGENERATION_FIDELITY_CONTROLS.csv`
- `paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_CONTROL_MANIFEST.csv`
- `paper_prep/validation_A_prime/regeneration_fidelity_20260709/CONTROL_GENERATION_LEDGER.jsonl`
- `paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_RELABEL_RESULTS.csv`
- `paper_prep/SEED_REGISTRY.md`
