# ADSR Code Review Recovery Report

MODEL_IDENTITY_STATUS = RESOLVED_ACE_STEP_V1
evidence: paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md; paper_prep/execution_20260709/ESCALATION_T0.md
A_PRIME_CARDINALITY_STATUS = RECONCILED
evidence: paper_prep/validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv; paper_prep/validation_A_prime/A_PRIME_CARDINALITY_REPORT.md; paper_prep/scripts/reconcile_a_prime_cardinality.py; tests/test_reconcile_a_prime_cardinality.py
REGENERATION_FIDELITY_STATUS = TODO
evidence: TODO
AMENDMENT_STATUS = TODO
evidence: TODO
BATCH3_REANALYSIS_STATUS = PASS
evidence: paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.json; paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.md; paper_prep/reanalysis_20260709/BATCH3_OLD_VS_V2_DIFF.csv; paper_prep/reanalysis_20260709/BATCH3_LEDGER_COMPLETENESS_REPORT.md; scripts/batch3_analyze_v2.py; tests/test_batch3_analyze_v2.py
PUBLICATION_STATS_V2_STATUS = PASS
evidence: paper_prep/scripts/build_publication_analysis_package_v2.py; paper_prep/analysis_v2/PUBLICATION_STATS_V2_REPORT.md; paper_prep/analysis_v2/OLD_VS_V2_PUBLICATION_NUMBER_DIFF.md; paper_prep/analysis_v2/deployment_success_metrics.csv; paper_prep/analysis_v2/n2_regime_membership_bootstrap.csv; paper_prep/figures_v2/fig2_retry_regime_ecdf_forest.png; tests/test_publication_analysis_package_v2.py
A_PRIME_PRIMARY_PACKAGE_STATUS = TODO
evidence: TODO
B_PRIME_PI_PACKAGE_STATUS = TODO
evidence: TODO
JUDGE_VALIDATION_STATUS = TODO
evidence: TODO
SA3_INTERMEDIATE_STATUS = TODO
evidence: TODO
SA3_LABEL_CALIBRATION_STATUS = TODO
evidence: TODO
V15_REPLICATION_STATUS = TODO
evidence: TODO
TEST_SUITE_STATUS = TODO
evidence: TODO
P0_OPEN_COUNT = TODO
evidence: TODO
FULL_DRAFT_STATUS = TODO
evidence: TODO
REDUCED_DRAFT_STATUS = TODO
evidence: TODO

## Headline Number Changes

- T5: Batch-3 old-v2 headline differences are below 0.00005; both frozen
  interval readings support the tail-rescue endpoint.
- T6: all shared per-try old-v2 differences are below 0.000001. The legacy
  `1/mean(p)` quantity is retired and replaced by prompt-averaged deployment
  success at N={4,5,8,16}; this is an estimand correction, not a changed result.

## Files And Commits

TODO as tasks complete.

## Test Results

TODO after each task and at finalization.

## Node Job Log

TODO after node availability checks.

## Remaining Human Actions

TODO after T3, T4, T7, and T8 calibration packaging.

## Changed Claims

TODO after T5, T6, and T8.

## Dual-PI Blockers

TODO after T1 and T2.
