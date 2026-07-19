# Exit-1 closeout test manifest — 2026-07-19

`TEST_SUITE_STATUS = PASS`

`NO_NEW_EXPERIMENTS = TRUE`

`NO_AUDIO_GENERATION = TRUE`

## Execution identity

| Field | Recorded value |
|---|---|
| Node | `ln206` |
| Tested Git base | `43c6a4bd06d0fb4548054f74eb95bae0e20bece4` |
| Environment | existing `/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm`; Python `3.10.20`; pytest `9.0.3` |
| Project configuration | `pyproject.toml`; SHA256 `5697038f89486f0ae75defdda03203b020011fcf9b487bcb10e65db08487aeb8` |
| Full-suite command | `PYTHONPATH=/tmp/AudioDiffusion_exit1_closeout_20260719/src /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python -m pytest -q -p no:cacheprovider` |
| Collection command | `PYTHONPATH=/tmp/AudioDiffusion_exit1_closeout_20260719/src /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python -m pytest --collect-only -p no:cacheprovider` |
| Seed | N/A — repository tests only; no experiment or generation launched |
| Placement | CPU test run on `ln206`; GPU IDs N/A; TP width N/A; replicas N/A; placement justified because no model inference was run |

## Passing result

| Field | Recorded value | Evidence |
|---|---|---|
| Collected test cases | `389` | `logs/EXIT1_EVIDENCE_CLOSEOUT_COLLECTION_20260719.log`; SHA256 `1489cdddb9c82b1f49e7461bf4e5500f59a3be833274a2339b144ffa0649a691` |
| Full-suite result | exit `0`; completed through `[100%]`; `TEST_SUITE_STATUS = PASS` | `logs/EXIT1_EVIDENCE_CLOSEOUT_FULL_TESTS_ATTEMPT4_20260719.log`; SHA256 `b1a89b214556b457de8e9ec25effe7900051c6998caddacea9508465092f99ca` |
| Statistical unit / CI | unit = repository test case; CI = N/A | collection and passing logs above |

## Environment hydration and restoration audit

| Item | Exact disposition |
|---|---|
| Persistent-storage quota | A hard user-quota error blocked writes; the dedicated clean Exit-1 worktree was moved intact to `/tmp/AudioDiffusion_exit1_closeout_20260719`. No user artifact was deleted. |
| Existing ignored inputs | Read-only links were provided during testing for two PI-media directories, two judge-result JSONL files, the T5 calibration ZIP, and two demo PNGs. These existing files were read only; no audio was generated. |
| Root compatibility link | The task worktree's ignored `paper_prep` compatibility link was temporarily pointed to its current-main canonical directory and restored to its original target after testing. |
| Append-only ledger compatibility | The already-recorded A-prime event contains an absolute historical worktree root. Its one test-worktree row was temporarily path-adjusted solely for the idempotence test, then restored exactly; post-test blob `a21d119bec816c2e5ad9e940625f3ecdce2c4a40` equals `HEAD`. |
| Original-worktree recovery | A quota-interrupted idempotent rewrite had truncated `A_PRIME_GATE_RESULT_20260713.json`; it was restored from the original branch blob and verified as `cb89fe0241dd731d9ad358f824bff780beb58b6e`. No unrelated dirty-worktree files were changed. |
| Pytest cache | Disabled with `-p no:cacheprovider` after the quota error. |
| Post-test cleanup | All hydration links were removed; the compatibility link was restored; only closeout evidence files and logs remain as intended changes. |

## Append-only attempt history

| Attempt | Status | Boundary / reason | Preserved log |
|---|---|---|---|
| Initial full suite | `ENVIRONMENT_BLOCKED` | One ignored PI-media directory absent from the clean checkout | `logs/EXIT1_EVIDENCE_CLOSEOUT_FULL_TESTS_20260719.log`; SHA256 `b678d886f35eace657f3d773ed51829db8d63d08a9a4286c743c8f23d8f97577` |
| Media-focused attempt 1 | `ENVIRONMENT_BLOCKED` | Target assertion completed, then pytest cache write hit the hard quota | `logs/EXIT1_EVIDENCE_CLOSEOUT_MEDIA_HYDRATION_FOCUSED_20260719.log`; SHA256 `e303cc6bd0b0baf361dcb42246f57c72f10aa92e41c12215b5b7e59f53ecb2ba` |
| Media-focused attempt 2 | `PASS` | Same focused assertion with cache disabled | `logs/EXIT1_EVIDENCE_CLOSEOUT_MEDIA_HYDRATION_FOCUSED_ATTEMPT2_20260719.log`; SHA256 `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d` |
| Full-suite attempt 2 | `ENVIRONMENT_BLOCKED` | Quota interrupted an idempotent audit-file rewrite; the tee log itself stopped after `479` bytes | `logs/EXIT1_EVIDENCE_CLOSEOUT_FULL_TESTS_ATTEMPT2_20260719.log`; SHA256 `42be4a6221afc5d25567b23bb101e778ad70b0c3b1f97f5ca464ab8d0f863504` |
| Isolated full-suite attempt 3 | `ENVIRONMENT_BLOCKED` | T5 ZIP and two demo PNGs absent from the clean checkout | `logs/EXIT1_EVIDENCE_CLOSEOUT_FULL_TESTS_ATTEMPT3_20260719.log`; SHA256 `a5c0829a282c5f12842b6c79ceb43adc2f054c8d59a77cc7c8acf761b29a0f75` |
| Isolated full-suite attempt 4 | `PASS` | Exact existing ignored inputs linked read-only; cache disabled; exit `0` | `logs/EXIT1_EVIDENCE_CLOSEOUT_FULL_TESTS_ATTEMPT4_20260719.log`; SHA256 `b1a89b214556b457de8e9ec25effe7900051c6998caddacea9508465092f99ca` |
