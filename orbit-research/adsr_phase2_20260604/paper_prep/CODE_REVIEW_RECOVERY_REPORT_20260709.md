# ADSR Code Review Recovery Report

MODEL_IDENTITY_STATUS = RESOLVED_ACE_STEP_V1
evidence: paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md; paper_prep/execution_20260709/ESCALATION_T0.md
A_PRIME_CARDINALITY_STATUS = RECONCILED
evidence: paper_prep/validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv; paper_prep/validation_A_prime/A_PRIME_CARDINALITY_REPORT.md; paper_prep/scripts/reconcile_a_prime_cardinality.py; tests/test_reconcile_a_prime_cardinality.py
REGENERATION_FIDELITY_STATUS = EXACT
evidence: paper_prep/validation_A_prime/REGENERATION_FIDELITY_CONTROLS.csv; paper_prep/validation_A_prime/REGENERATION_FIDELITY_REPORT.md; paper_prep/validation_A_prime/regeneration_fidelity_20260709/CONTROL_GENERATION_LEDGER.jsonl; paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_RELABEL_RESULTS.csv; paper_prep/scripts/regeneration_fidelity_20260709.py; tests/test_regeneration_fidelity_20260709.py
AMENDMENT_STATUS = SIGNED
evidence: paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md; paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_SIGNATURE_20260710.md; paper_prep/scripts/validation_gate_v2.py; tests/test_validation_gate_v2.py
BATCH3_REANALYSIS_STATUS = PASS
evidence: paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.json; paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.md; paper_prep/reanalysis_20260709/BATCH3_OLD_VS_V2_DIFF.csv; paper_prep/reanalysis_20260709/BATCH3_LEDGER_COMPLETENESS_REPORT.md; scripts/batch3_analyze_v2.py; tests/test_batch3_analyze_v2.py
PUBLICATION_STATS_V2_STATUS = PASS
evidence: paper_prep/scripts/build_publication_analysis_package_v2.py; paper_prep/analysis_v2/PUBLICATION_STATS_V2_REPORT.md; paper_prep/analysis_v2/OLD_VS_V2_PUBLICATION_NUMBER_DIFF.md; paper_prep/analysis_v2/deployment_success_metrics.csv; paper_prep/analysis_v2/n2_regime_membership_bootstrap.csv; paper_prep/figures_v2/fig2_retry_regime_ecdf_forest.png; tests/test_publication_analysis_package_v2.py
A_PRIME_PRIMARY_PACKAGE_STATUS = ORIGINAL_ONLY_PI_READY
evidence: paper_prep/validation_A_prime/primary_package_20260709/README.md; paper_prep/validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_ADMIN.csv; paper_prep/validation_A_prime/A_PRIME_HUMAN_GATE_REPORT_20260709.md; paper_prep/validation_A_prime/score_human_A_prime.py
B_PRIME_PI_PACKAGE_STATUS = READY
evidence: paper_prep/validation_B_prime/pi_package_20260709/README.md; paper_prep/validation_B_prime/pi_package_20260709/B_PRIME_ORDERED_ADMIN.csv; paper_prep/validation_B_prime/B_PRIME_HUMAN_GATE_REPORT_20260709.md; paper_prep/validation_B_prime/score_human_B_prime.py
JUDGE_VALIDATION_STATUS = PI_BLOCKED
evidence: paper_prep/judge_selfhost_20260709/SELFHOST_JUDGE_REPORT.md; paper_prep/legacy_human_results_20260710/JUDGE_GOLD_CXY_T7_REPORT.md; paper_prep/legacy_human_results_20260710/JUDGE_GOLD_CXY_20260710.csv; paper_prep/judge_raw/selfhost_qwen3_omni_legacy_cxy_heldout_20260710.jsonl; tests/test_selfhost_audio_judge.py; tests/test_legacy_cxy_t7_audit_20260710.py
SA3_INTERMEDIATE_STATUS = TRUE_INTERMEDIATE_COMPLETE
evidence: src/mprm/inference/sa3.py; paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_REPORT.md; paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_METRICS.csv; tests/test_sa3_true_intermediate.py; tests/test_sa3_intermediate_analysis.py
SA3_LABEL_CALIBRATION_STATUS = PACKAGE_READY
evidence: paper_prep/sao/stable_audio_3_medium/label_calibration/SA3_LABEL_CALIBRATION_REPORT.md; paper_prep/sao/stable_audio_3_medium/label_calibration/SA3_LABEL_CALIBRATION_ADMIN.csv; paper_prep/sao/stable_audio_3_medium/score_sa3_label_calibration.py; paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_REPORT.md; tests/test_sa3_label_calibration.py; tests/test_sa3_intervention_fidelity.py
V15_REPLICATION_STATUS = COMPLETE
evidence: paper_prep/v15_replication_20260709/V15_FINAL_REPLICATION_REPORT.md; paper_prep/v15_replication_20260709/V15_ATTEMPT_AUDIT.csv; paper_prep/v15_replication_20260709/V15_AUDIO_MANIFEST.csv; paper_prep/scripts/audit_v15_replication.py; tests/test_v15_replication.py
TEST_SUITE_STATUS = PASS
evidence: paper_prep/execution_20260709/logs/full_pytest_legacy_ingest_20260710.log; tests/test_code_review_recovery_report.py; tests/test_legacy_cxy_ingest_20260710.py; tests/test_legacy_cxy_t7_audit_20260710.py; tests/test_rating_package_integrity_20260710.py
P0_OPEN_COUNT = 0
evidence: paper_prep/execution_20260709/CODE_REVIEW_RECOVERY_LEDGER.jsonl; paper_prep/TODO_COMPLIANCE_20260709.md; paper_prep/PLAN.md
FULL_DRAFT_STATUS = NOT_READY
evidence: paper_prep/validation_A_prime/A_PRIME_HUMAN_GATE_REPORT_20260709.md; paper_prep/validation_B_prime/B_PRIME_HUMAN_GATE_REPORT_20260709.md; paper_prep/judge_selfhost_20260709/SELFHOST_JUDGE_REPORT.md
REDUCED_DRAFT_STATUS = READY_WITH_REDUCED_CLAIMS
evidence: paper_prep/PLAN.md; paper_prep/TODO_COMPLIANCE_20260709.md; paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md

## Headline Number Changes

| Topic | Earlier package | Recovered package | Consequence |
|---|---|---|---|
| Frozen backbone identity | Described as ACE-Step v1.5 | Recovered import/checkpoint provenance identifies ACE-Step v1 | All frozen primary claims are relabeled v1; v1.5 evidence is separate. |
| Batch-3 reanalysis | Historical rounded report | Maximum old-v2 headline difference below 0.00005; no gate flip | Numerical claim retained with a reproducible fail-closed analyzer. |
| Efficiency estimand | `1/mean(p)` labeled expected draws | Deployment success `S_N`; at N=4 vocal baseline 0.291566 vs V3 0.988660 | Retires the invalid estimand and keeps the difficult-set caveat. |
| N2 regime stability | Hard regime assignments only | 25/128 prompts have uncertain bootstrap membership | Regime counts remain, with membership uncertainty disclosed. |
| A-prime primary set | 816 mixed original/regenerated rows | 690/690 original-only rows; 126 regenerated rows sensitivity-only | Human package is complete, but 0 ratings means no validation pass. |
| B-prime endpoint | 160 ordered model calls treated as votes | 80 first-presentation primary pairs plus 24 delayed reversed reliability pairs | Old 50/77 model-call result is excluded from the primary claim. |
| SA3 observability | Low-step proxy | Same-trajectory intermediates captured and decoded; held-out balanced accuracy 1.000, tied with independent low-step | Instrumentation is complete, but D7 promotion fails. |
| ACE-Step v1.5 | No bounded replication | 1,024 prevalence, 512 retry, and 256 intervention rows | Severe vocal difficulty replicates; intervention lift +0.054688 is weak/uncertain. |
| Self-hosted judge | Failed external Qwen smoke | Complete Qwen3-Omni service and a clean held-out legacy-CXY diagnostic | Engineering blocker closed; validation remains PI-blocked because the pre-amendment gold is single-rater and class-imbalanced. |

T2 additionally found 20/126 label flips (18/100 A-prime regenerated + 2/26
rare-clean regenerated); the 50/50 regeneration controls remain exact. Mean
absolute ratio delta is 0.000000, and mean/minimum CLAP audio cosine is
1.000000. Container-byte differences are not treated as decoded waveform
differences.

## Files And Commits

| Task | Commit | Status | Principal review artifact |
|---|---|---|---|
| T0 | `7dd68c6` | model identity resolved as ACE-Step v1 | `paper_prep/model_identity/MODEL_IDENTITY_AUDIT_20260709.md` |
| T1 | `a5a6023` | cardinality reconciled | `paper_prep/validation_A_prime/A_PRIME_CARDINALITY_REPORT.md` |
| T5 | `ec3e80f` | Batch-3 v2 pass | `paper_prep/reanalysis_20260709/BATCH3_RESULTS_V2.md` |
| T6 | `5469f6c` | publication statistics v2 pass | `paper_prep/analysis_v2/PUBLICATION_STATS_V2_REPORT.md` |
| T3 | `f722880` | amendment drafted, packages fail-closed | `paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md` |
| T4 | `ba7eaf4` | 42-clip decisive packet ready | `paper_prep/pi_decisive_packet_20260709/README.md` |
| T8 | `1f7fa91` | true-intermediate capture complete | `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_REPORT.md` |
| T2 | `832e498` | regeneration fidelity exact | `paper_prep/validation_A_prime/REGENERATION_FIDELITY_REPORT.md` |
| T11 | `d7a66ae` | docs and P1 hardening pass with documented threshold exception | `paper_prep/TODO_COMPLIANCE_20260709.md` |
| T9 | `8cba0f5` | bounded v1.5 replication complete | `paper_prep/v15_replication_20260709/V15_FINAL_REPLICATION_REPORT.md` |
| T7 | `268518e` | service prepared, validation PI-blocked | `paper_prep/judge_selfhost_20260709/SELFHOST_JUDGE_REPORT.md` |
| Signature | `41d130c` | D4/D5 amendment signed by Richard Ye | `paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_SIGNATURE_20260710.md` |

The compact manual-review entry point is `Code_Review_Guide.md`. The claim
table is `paper_prep/PLAN.md`.

## Test Results

- Final full suite after legacy ingest: 171 passed, 0 failed, 0 skipped.
- Legacy-ingest/report-contract focused suite: 10 passed.
- Earlier T7 focused suite: 7 passed; launcher and staging scripts also passed `bash -n`.
- T2 focused rerun after path parameterization: 9 passed and the 1,794-audio
  v1.5 audit passed.
- The first finalization suite exposed one release-path test failure caused by
  a hard-coded external T9 root. `audit_v15_replication.py` now accepts
  `--external-root` or `ADSR_V15_EXTERNAL_ROOT`; the final suite above passed.

Evidence: `paper_prep/execution_20260709/logs/full_pytest_legacy_ingest_20260710.log`.

## Node Job Log

| Node | ADSR work completed | Current ADSR state | Non-ADSR load |
|---|---|---|---|
| `an12` | T2 exact replay; T9 bounded v1.5 generation/scoring | No active ADSR compute; all non-human-gated claim tasks are complete | BlindGain processes occupy GPUs 0-3; not counted as ADSR and not modified. |
| `an29` | T8 SA3 lane; T9 support; T7 model staging, runtime recovery, smoke, and held-out legacy-CXY diagnostic | `adsr_qwen_server` resident on GPUs 0,2,3,4, waiting for PI or second-rater agreement evidence | BlindGain launchers target other GPUs; not counted as ADSR and not modified. |

Heartbeat and gap details are in `paper_prep/NODE_SATURATION_AUDIT_20260709.md`,
`paper_prep/heartbeat_an12.log`, and `paper_prep/heartbeat_an29.log`.

## Remaining Human Actions

- Obtain PI or second-rater overlap on the original-media CXY judge-gold clips,
  report inter-rater kappa, and repeat the held-out T7 audit before considering
  judge promotion. The current diagnostic cannot auto-pass validation.
- Rate the 42-clip decisive construct packet first. This supplies the balanced
  PI-corrected truth needed for the self-hosted smoke and selects the construct
  branch; it is not itself an A-prime pass.
- Rate and score the 690-row original-only A-prime package.
- Rate and score the B-prime package: 80 primary presentations plus 24 delayed
  reversed reliability presentations.
- Rate the separate 60-clip SA3 threshold-calibration packet only if the PI
  wants to pursue promotion beyond the reduced second-backbone pilot.

## Changed Claims

- Frozen evidence is ACE-Step v1. The bounded v1.5 replication cannot be merged
  into, or used to relabel, the frozen evidence.
- Efficiency uses prompt-averaged limited-draw deployment success. The legacy
  `1/mean(p)` quantity is not an expected-draw claim.
- A-prime and B-prime are package-readiness/limitation statements only. No human
  confirmation or unqualified audible-quality claim is allowed.
- SA3 true-intermediate capture is implemented and audited, but D7 promotion
  fails because it does not beat the perfect independent low-step comparator.
- The SA3 intervention lift is automatic-label pilot evidence only: 14/256 to
  191/256 present at matched budgets; human threshold calibration is unrated.
- The router is an offline negative/reduced result: cross-validated threshold
  policy 0.970018 vs always-recondition 0.974455.
- CLAP wording is limited to no clear drop detected; the expanded mean delta is
  +0.005996 with 95% CI [-0.003375, 0.015661].
- No full cross-backbone ADSR or validated automatic-judge claim is allowed.

## Dual-PI Blockers

- T2 permits regenerated media to be considered, but the primary A-prime
  package remains original-only. Moving regenerated rows into a primary gate
  still requires the amendment's explicit dual-PI approval; no such promotion
  has been made.

## Final Recommendation

The project is ready to draft only with the reduced claim table in `PLAN.md`.
Full-strength readiness remains unavailable until real A-prime and B-prime
ratings pass their frozen scorers. There are no unresolved engineering P0 tasks;
the remaining primary gates require human judgment.

## Repository Publication

- Branch: `codex/publication-code-recovery-20260709`
- Draft review: `https://github.com/yhc98002-bit/Audio/pull/1`
- Final test log: `paper_prep/execution_20260709/logs/full_pytest_final.log`
