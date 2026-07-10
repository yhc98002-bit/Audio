# Regeneration Fidelity Report

`REGENERATION_FIDELITY_STATUS = EXACT`

## Protocol

- 50 controls were selected from the reconstructed 112-case primary A-prime
  universe; every source is original media.
- Historical candidate seeds were replayed in an isolated output directory.
- Generation settings match the frozen recollection summaries: ACE-Step v1,
  30 steps, CFG 5.0, `cfg_type=cfg`, guidance interval 0.5, bf16.
- Canonical relabeling uses `htdemucs`, `apply_model(..., shifts=1,
  split=True, overlap=0.1)`, `near_silent = rms < 1e-3`, and threshold
  0.1791. Original/replay pairs share a stable scoring seed so Demucs shift
  and CLAP crop randomness cannot masquerade as generation drift.
- CLAP comparison is audio-embedding cosine between the original and replay,
  using the project-pinned `630k-audioset-best` checkpoint.

## Control Results

| Measure | Result |
|---|---:|
| Controls completed | 50/50 |
| Exact decoded-waveform SHA256 | 50/50 |
| Exact container-file SHA256 | 0/50 |
| Same sample rate | 50/50 |
| Demucs label flips | 0/50 |
| Mean absolute rescored Demucs-ratio delta | 0.000000 |
| Mean aligned waveform NRMSE | 0.000000 |
| Mean CLAP audio cosine | 1.000000 |
| Minimum CLAP audio cosine | 1.000000 |
| Manual mismatch flags completed | 0/50 (`UNRATED`; review queue is explicit in the CSV) |

## Regenerated-Cohort Relabeling

| Cohort | Rows | Label flips | Mean absolute ratio delta | Maximum absolute ratio delta |
|---|---:|---:|---:|---:|
| A-prime regenerated media | 100 | 18 | 0.015467 | 0.121097 |
| Rare-clean regenerated media | 26 | 2 | 0.003105 | 0.012253 |

## Interpretation

`EXACT` is mechanical: `EXACT` requires all 50 waveform hashes to match;
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
