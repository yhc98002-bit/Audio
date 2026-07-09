# Storage Triage Log

Generated: 2026-07-07T03:19:46
Seed: 20260707

## Scope

This triage implements the sample-first deletion boundary for the ADSR Phase-2/ATLAS audio corpora. It protects pending consumers first, then marks only unprotected original FLAC files under the PH2 online keep and ATLAS keep roots as delete candidates.

Allowed deletion roots:
- `orbit-research/adsr_phase2_20260604/batch3/online_run/keep`
- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/keep`

Out of scope for this pass:
- RL-era audio under `runs/` (explicitly skipped)
- JSONL ledgers, paper state files, configs, checkpoints, EVPD model, and trajectory spine
- The self-contained human-eval package tarball in `/tmp`

## Materialized Consumers

- CLAP fidelity input manifest: `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/CLAP_FIDELITY_INPUT_MANIFEST.csv`
  - Group 1 selected winners: 553
  - Group 6 selected winners: 708
- A-prime judge sample: `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/A_PRIME_500_JUDGE_SAMPLE/manifest.csv` (500 copied FLACs)
- Fig 6 candidate pool: `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/FIG6_CANDIDATE_POOL/manifest.csv` (30 copied FLACs; categories={'caught': 10, 'missed': 6, 'rescued': 10, 'contrast_fill': 4})
- Rare-clean hard-prompt protection: `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/RARE_CLEAN_PROTECTED/manifest.csv` (14 canonical copied FLACs; 26 regenerated rare clips protected inside the package tarball)
- Release keep manifest: `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/RELEASE_KEEP_MANIFEST.csv` (1342 copied retained FLACs, 8.48 GiB)

## Audio Universe

- Total source FLAC records considered: 15952
- By corpus after protection accounting: {'ATLAS': 11833, 'PH2_ONLINE': 4119}

## Protection Boundary

- Protected union rows: 3074
- Original source paths protected from deletion: 1475
- Release/sample copied FLACs protected separately: 1342
- Delete candidates: 14477 original FLACs, 87.24 GiB projected

## Audit Files

- `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/PROTECTED_AUDIO_UNION.csv`
- `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/DELETE_CANDIDATES.csv`
- `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/checksums/SHA256SUMS.txt`
- `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/HUMAN_PACKAGE_SOURCE_REFERENCES.csv`

Deletion was performed from `DELETE_CANDIDATES.csv`; actual results are in `DELETED_AUDIO_MANIFEST.csv`.


## Deletion Execution

- Started: 2026-07-07T03:21:18
- Finished: 2026-07-07T03:21:27
- Candidate rows validated: 14477
- Deleted FLAC files: 14477
- Missing before delete: 0
- Reclaimed bytes from deleted files: 93674626545 (87.24 GiB)
- Deletion manifest: `orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/DELETED_AUDIO_MANIFEST.csv`

Safety checks at deletion time:
- Protected source/delete overlap: 0
- Allowed roots only: yes
- FLAC suffix only: yes
