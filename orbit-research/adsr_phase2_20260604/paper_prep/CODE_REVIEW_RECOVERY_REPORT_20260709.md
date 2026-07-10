# ADSR Code Review Recovery Report

MODEL_IDENTITY_STATUS = RESOLVED_ACE_STEP_V1
evidence: paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md; paper_prep/execution_20260709/ESCALATION_T0.md
A_PRIME_CARDINALITY_STATUS = RECONCILED
evidence: paper_prep/validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv; paper_prep/validation_A_prime/A_PRIME_CARDINALITY_REPORT.md; paper_prep/scripts/reconcile_a_prime_cardinality.py; tests/test_reconcile_a_prime_cardinality.py
REGENERATION_FIDELITY_STATUS = TODO
evidence: TODO
AMENDMENT_STATUS = DRAFTED_AWAITING_SIGNATURE
evidence: paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md; paper_prep/scripts/validation_gate_v2.py; tests/test_validation_gate_v2.py
BATCH3_REANALYSIS_STATUS = PASS
evidence: paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.json; paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.md; paper_prep/reanalysis_20260709/BATCH3_OLD_VS_V2_DIFF.csv; paper_prep/reanalysis_20260709/BATCH3_LEDGER_COMPLETENESS_REPORT.md; scripts/batch3_analyze_v2.py; tests/test_batch3_analyze_v2.py
PUBLICATION_STATS_V2_STATUS = PASS
evidence: paper_prep/scripts/build_publication_analysis_package_v2.py; paper_prep/analysis_v2/PUBLICATION_STATS_V2_REPORT.md; paper_prep/analysis_v2/OLD_VS_V2_PUBLICATION_NUMBER_DIFF.md; paper_prep/analysis_v2/deployment_success_metrics.csv; paper_prep/analysis_v2/n2_regime_membership_bootstrap.csv; paper_prep/figures_v2/fig2_retry_regime_ecdf_forest.png; tests/test_publication_analysis_package_v2.py
A_PRIME_PRIMARY_PACKAGE_STATUS = ORIGINAL_ONLY_PI_READY
evidence: paper_prep/validation_A_prime/primary_package_20260709/README.md; paper_prep/validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_ADMIN.csv; paper_prep/validation_A_prime/A_PRIME_HUMAN_GATE_REPORT_20260709.md; paper_prep/validation_A_prime/score_human_A_prime.py
B_PRIME_PI_PACKAGE_STATUS = READY
evidence: paper_prep/validation_B_prime/pi_package_20260709/README.md; paper_prep/validation_B_prime/pi_package_20260709/B_PRIME_ORDERED_ADMIN.csv; paper_prep/validation_B_prime/B_PRIME_HUMAN_GATE_REPORT_20260709.md; paper_prep/validation_B_prime/score_human_B_prime.py
JUDGE_VALIDATION_STATUS = TODO
evidence: TODO
SA3_INTERMEDIATE_STATUS = TRUE_INTERMEDIATE_COMPLETE
evidence: src/mprm/inference/sa3.py; paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_REPORT.md; paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_LEDGER.jsonl; paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_METRICS.csv; tests/test_sa3_true_intermediate.py; tests/test_sa3_intermediate_analysis.py
SA3_LABEL_CALIBRATION_STATUS = PACKAGE_READY
evidence: paper_prep/sao/stable_audio_3_medium/label_calibration/SA3_LABEL_CALIBRATION_REPORT.md; paper_prep/sao/stable_audio_3_medium/label_calibration/SA3_LABEL_CALIBRATION_ADMIN.csv; paper_prep/sao/stable_audio_3_medium/score_sa3_label_calibration.py; paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_REPORT.md; tests/test_sa3_label_calibration.py; tests/test_sa3_intervention_fidelity.py
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

- Sign the D4/D5 criteria amendment.
- Rate the 690-row original-only A-prime package and the 104-presentation
  B-prime package; current fail-closed reports are `AWAITING_RATINGS`.
- Rate the separate 42-clip decisive construct packet before selecting the
  self-hosted-judge calibration branch.

## Changed Claims

- SA3 true-intermediate capture is implemented and audited, but D7 promotion
  fails because it does not beat the perfect independent low-step comparator.
- The SA3 intervention lift is automatic-label pilot evidence only: 14/256 to
  191/256 present at matched budgets; human threshold calibration is unrated.
- No full cross-backbone ADSR claim is allowed from the SA3 lane.

## Dual-PI Blockers

TODO after T1 and T2.
