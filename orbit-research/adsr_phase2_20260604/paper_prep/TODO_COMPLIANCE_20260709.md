# T11 Documentation And P1 Compliance

`T11_STATUS = PASS_WITH_DOCUMENTED_7_ROW_THRESHOLD_EXCEPTION`

## Documentation

| Requirement | Status | Evidence |
|---|---|---|
| Gate-B supersession note | PASS | `paper_prep/GATE_B_SUPERSESSION_NOTE_20260709.md` |
| Publication-guide v2 delta | PASS | `paper_prep/ADSR_PUBLICATION_TODO_V2_DELTA_20260709.md` |
| Refresh project instructions | PASS | `AGENTS.md` |
| Refresh canonical index | PASS | `orbit-research/CURRENT_CANONICAL_FILES.md` |
| Concise manual code-review path | PASS | `Code_Review_Guide.md` |

## P1 Hardening

| Requirement | Status | Implementation and evidence |
|---|---|---|
| Deep-copy nested baseline config per seed | PASS | `scripts/launch_baseline.py::_copy_config_for_seed`; mutation-isolation test |
| Single canonical vocal threshold | PASS_WITH_EXCEPTION | `src/mprm/common/thresholds.py`; numeric-constant scan test; all active code imports 0.1791 |
| Audit historical 0.179/0.1791 gap | FAIL_7_ROWS_RESOLVED | `code_hardening_20260709/VOCAL_THRESHOLD_GAP_AUDIT.{json,md}` remains failed. `VOCAL_THRESHOLD_MIGRATION_RESOLUTION.md` proves the 4,096-row historical source has zero gap rows and all seven broad-corpus rows were already labeled at 0.1791. No frozen artifact was rewritten. |
| Canonical labeler cross-implementation agreement | PASS | 200/200 labels and near-silent flags agree; maximum ratio delta 0.000000060507. See `CANONICAL_LABELER_AGREEMENT_REPORT.md`. |
| Per-arm near-silent table and definition | PASS | `reanalysis_20260709/BATCH3_RESULTS_V2.{json,md}`; every arm has 0 near-silent completed rows, with denominators 2,048-4,096. |
| Blinding key from environment nonce | PASS | A-prime/B-prime, decisive packet, SA3 calibration, and SA3 pair builders require `ADSR_BLINDING_NONCE`; nonce-difference test exists. |
| Standalone arm-2 yoke guard | PASS | `scripts/batch3_online_harness.py::_validate_only_arm`; standalone arm 2 raises before model load. |
| Accurate `DemucsVocalStem` contract | PASS | Docstring states explicit stochastic seeding and propagating failures; canonical ratio method added. |
| Config/Git/model SHA ledger fields | PASS | `src/mprm/common/provenance.py` and `run_ledger.py`; provenance persists across start/final/fail events. |
| Remove release-code absolute workspace paths | PASS | `MPRM_REPO_ROOT` plus file-relative defaults; static regression test scans source trees. |

## Tests

The focused T11, ledger, Batch-3 v2, validation-package, and decisive-packet
suites pass: 24 tests. The final repository-wide suite is reported separately
in `CODE_REVIEW_RECOVERY_REPORT_20260709.md` after T9 completes.

The seven-row broad threshold exception is not hidden and is not a P0 claim
blocker: six clean rows and one quarantined duplicate already carry canonical
0.1791 labels; the historical 4,096-row source affected by old code has zero
rows in the interval.
