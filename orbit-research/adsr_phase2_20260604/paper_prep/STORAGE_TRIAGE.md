# Storage Triage

Generated: 2026-07-07

Status: current recovery pass performed read-only triage only. No files were
deleted during this pass.

## Current Quota

- Command: `lfs quota -u pxy1289 .`
- Current usage: 251,864,920 KB of 524,288,000 KB soft quota
  (about 240.2 GiB of 500 GiB).
- Hard limit: 534,773,760 KB.

## Top Disk Consumers

Measured with `du -x -h --max-depth=4 . | sort -h | tail -n 25`.

| Size | Path |
|---:|---|
| 588M | `./batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/00_controls_and_sanity_gate` |
| 843M | `./runs/phase_c0_backend_validation_20260524_113433` |
| 902M | `./batch3` |
| 902M | `./batch3/exploratory_auto` |
| 902M | `./batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3` |
| 1.1G | `./runs/phase_b3_credit_unit` |
| 1.1G | `./runs/phase_b3_credit_unit/h3_held_out_v2_global_seed` |
| 1.1G | `./runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/audio` |
| 1.3G | `./orbit-research/adsr_phase2_20260604/batch3/online_confirm` |
| 2.1G | `./runs/phase_c1_firstwave_20260524_researcher_go_01/m_fixedwin` |
| 2.1G | `./runs/phase_c1_firstwave_20260524_researcher_go_01/m_section` |
| 2.1G | `./runs/phase_c1_firstwave_20260524_researcher_go_01/r8a` |
| 2.1G | `./runs/phase_c1_firstwave_20260524_researcher_go_01/r8b` |
| 6.0G | `./orbit-research/adsr_phase2_20260604/mel` |
| 8.4G | `./runs/phase_c1_firstwave_20260524_researcher_go_01` |
| 8.5G | `./orbit-research/adsr_phase2_20260604/paper_prep/storage_triage` |
| 13G | `./orbit-research/adsr_phase2_20260604/batch3/online_run` |
| 13G | `./runs` |
| 14G | `./orbit-research/adsr_phase2_20260604/batch3` |
| 33G | `./orbit-research/adsr_phase2_20260604/paper_prep/stage3_intervention_20260707` |
| 73G | `./orbit-research/adsr_phase2_20260604/paper_prep/population_retry_20260707` |
| 114G | `./orbit-research/adsr_phase2_20260604/paper_prep` |
| 134G | `./orbit-research/adsr_phase2_20260604` |
| 136G | `./orbit-research` |
| 150G | `.` |

## Protected Keep-List

Existing keep-list artifacts:

- Protected audio union: `paper_prep/storage_triage/PROTECTED_AUDIO_UNION.csv`
- Release keep manifest: `paper_prep/storage_triage/RELEASE_KEEP_MANIFEST.csv`
- CLAP fidelity input manifest: `paper_prep/storage_triage/CLAP_FIDELITY_INPUT_MANIFEST.csv`
- A-prime 500-clip sample manifest:
  `paper_prep/storage_triage/A_PRIME_500_JUDGE_SAMPLE/manifest.csv`
- Fig. 6 candidate pool manifest:
  `paper_prep/storage_triage/FIG6_CANDIDATE_POOL/manifest.csv`
- Rare clean protected manifest:
  `paper_prep/storage_triage/RARE_CLEAN_PROTECTED/manifest.csv`
- Human package source references:
  `paper_prep/storage_triage/HUMAN_PACKAGE_SOURCE_REFERENCES.csv`
- Checksums: `paper_prep/storage_triage/checksums/SHA256SUMS.txt`

Protected classes for all future deletion decisions:

- All JSONL ledgers.
- All files referenced in `paper_prep/PLAN.md` once materialized.
- Stage 3 and N2 final ledgers, summaries, audits, and preregistrations.
- Human/PI hearing package manifests and copied media.
- Selected-winner audio needed for CLAP fidelity.
- A-prime 500-clip sample.
- Fig. 6 gallery candidates.
- Rare clean clips from rare-basin prompts.
- `orbit-research/trajectory_candidate_dataset.jsonl`.
- `orbit-research/adsr_phase2_20260604/batch2/evpd_sigma08_online.joblib`.

## Existing Deletion Manifest

- Prior deletion log: `paper_prep/storage_triage/STORAGE_TRIAGE.md`
- Deletion candidate manifest: `paper_prep/storage_triage/DELETE_CANDIDATES.csv`
- Actual deletion manifest: `paper_prep/storage_triage/DELETED_AUDIO_MANIFEST.csv`
- Prior deletion result: 14,477 FLAC files deleted, 93,674,626,545 bytes
  reclaimed, 0 protected-source/delete overlap.

## Deletion Decision For This Pass

No deletion was performed.

Reason: current quota is below the safe threshold, the largest current
directories are claim-supporting Stage 3/N2 evidence or frozen/protected
trees, and the existing triage already removed clearly unprotected original
FLACs while retaining ledgers, copied release samples, and audit manifests.

Before any future deletion, create a new deletion manifest, verify 0 overlap
with `PROTECTED_AUDIO_UNION.csv`, verify that no path is referenced by
`paper_prep/PLAN.md`, and record reclaimed bytes.

