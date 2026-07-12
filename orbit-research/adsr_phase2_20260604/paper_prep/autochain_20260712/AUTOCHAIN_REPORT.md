# T6 Promotion Autochain Report

Date: 2026-07-12/13 (Asia/Shanghai execution window)

`RELIABILITY_STATUS = PASS`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_RELIABILITY_RESULT.json`

`CORRECTED_INSTRUMENT_STATUS = PROMOTED`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/T6_HELDOUT_EXPOSURE_RECORD.json`

`RECOMPUTE_STATUS = COMPLETE_DRAFT_AWAITING_ADOPTION`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_RECOMPUTE_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/CORRECTED_PUBLICATION_RATES.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`

`FACTORIAL_SCORING_STATUS = COMPLETE_PROMOTED_INSTRUMENT_DRAFT`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_SCORING_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_CONDITION_RESULTS.csv`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/factorial/FACTORIAL_INTERACTION_CONTRASTS.csv`

`JUDGE_500_STATUS = BLOCKED_JUDGE_GOLD_NEGATIVE_COUNT`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_VALIDATION_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/judge_aprime/JUDGE_NEGATIVE_GOLD_TOPUP_ESCALATION.md`

`A_PRIME_GATE = BLOCKED_JUDGE_GOLD_NEGATIVE_COUNT`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260712.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/judge_aprime/JUDGE_LABEL_A_GOLD_BUILD.json`

`LIVE_CONFIRM_STATUS = BLOCKED_UNSIGNED_W2_AMENDMENT`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/LIVE_CONFIRM_STATUS_REPORT.md`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/LIVE_CONFIRM_GUARD_TRACEBACK.txt`, `orbit-research/adsr_phase2_20260604/paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/CORRECTED_EVPD_REPORT.md`

`EVIDENCE_BUNDLE_STATUS = BUILT`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/paper_evidence_bundle_20260712/INDEX.md`, `orbit-research/adsr_phase2_20260604/paper_prep/paper_evidence_bundle_20260712/SHA256SUMS`, `orbit-research/adsr_phase2_20260604/paper_prep/paper_evidence_bundle_20260712.tar.gz`

`TEST_SUITE_STATUS = PASS`
evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/FULL_TEST_RESULT_SUMMARY.json`, `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/FULL_TEST_RESULTS.txt`, `tests/test_autochain_t6_20260712.py`, `tests/test_w2_promotion_pipeline_20260712.py`

## C1 Reliability

The 201-row T6 export matched the admin manifest exactly, carried only
`pi:Richard` provenance, and had zero required blanks. Confidence was optional
under the W2 amendment and was absent on 181 rows. Hidden-repeat reliability was
computed before any fitting or held-out exposure:

- Label A exact agreement: 20/20; Cohen's kappa 1.000.
- Label B exact agreement: 20/20; Cohen's kappa 1.000.
- Satisfied-to-violated reversals: 0/20.

## C2 Promotion

Selection used the 58 decided rows from the frozen 60-row train split; two
`unsure` responses remained abstentions. The selected candidate is Demucs OR
PANNs at thresholds 0.0316177709 and 0.0440341365. The 100 held-out labels were
exposed once under a hash-locked record.

| Metric | Design-weighted point | One-sided 95% LCB |
|---|---:|---:|
| Balanced accuracy | 0.987308 | 0.972272 |
| Sensitivity | 1.000000 | 1.000000 |
| Specificity | 0.974616 | 0.944544 |

There were 31 decided positives, 67 decided negatives, and two abstentions.
The 20-row transport audit triggered no per-source correction flag. Promotion
is mechanical; publication adoption is still blocked on both W2 signatures.
No PLAN/CLAIMS row was changed.

## C3 Corrected Recompute

All 27,966 target rows were rescored. The train-only design-weighted
calibration selected M2 with L2=0.1. All 2,000 nested bootstrap replicates
succeeded, jointly resampling calibration strata, refitting the selected form,
and resampling target prompts. Outputs include 28 publication rows, 876 prompt
rows, prompt ECDFs, and PNG/PDF figures. Every value is labeled draft pending
dual-PI adoption; the current PLAN.md and CLAIMS.md remain authoritative.

## C4 Factorial

All 3,072 preregistered clips completed corrected-instrument, calibrated-model,
CLAP, Audiobox PQ, signal-quality, near-silence, and MFCC-diversity scoring with
zero failures. The best draft calibrated satisfaction rate was positive+sampler
(0.679794); positive-only text was 0.6608 and plain baseline was 0.4384. The
negative and positive interaction contrasts were -0.007493 and -0.001044. The
existing 20-pair blinded PI spot check remains staged and unrated.

## C5 Judge And A-Prime

T1/T2 are tuning-only and SHA-256-disjoint from the fresh T6 evaluation. The
self-hosted Qwen3-Omni judge completed 528/528 deterministic calls with no
errors or abstentions.

| Metric | Point | One-sided 95% LCB |
|---|---:|---:|
| Balanced accuracy | 0.947982 | 0.900360 |
| Sensitivity | 0.991421 | 0.975793 |
| Specificity | 0.904543 | 0.813256 |

Every metric threshold passed. The gate nevertheless failed because the fresh
evaluation contains 27 negatives rather than the frozen minimum of 50. Even all
available t1+t2+t6 PI gold contains only 43 negatives. Therefore no
stratified-500 judge calls, A-prime instrument merge, or gate call occurred.

## C6 EVPD And Live Confirmation

A draft direction-specific Label-B EVPD model was trained on the reconstructed
spine with prompt-disjoint splits: validation balanced accuracy 0.831660, test
balanced accuracy 0.833385, and test AUC 0.915448. The 512-unit live manifest
and policy hash remain frozen. The real launch guard rejected execution because
the W2 amendment lacks both signatures; no live generation ran.

## Evidence Bundle

The co-PI writing bundle contains 53 indexed artifacts and 60 internally
checksummed files. Internal SHA-256 verification passed. Tarball:

`paper_prep/paper_evidence_bundle_20260712.tar.gz`

SHA-256: `5f907b43bba616132bf440653295555dea81f35d6048a6d555c494cc4ee8a30e`.

## Escalations

1. Both PIs must sign/adopt W2 before corrected drafts can change PLAN/CLAIMS or the live confirmation can launch.
2. New hash-disjoint PI/human negative gold is required: 23 negatives for the fresh T6 validation design, or at least seven beyond all currently available t1+t2+t6 negatives under a newly frozen design.

## Readiness

- Full draft readiness: `NOT_READY` because A-prime has not passed and W2 adoption/live confirmation are unsigned.
- Reduced-claims readiness: `READY_WITH_REDUCED_CLAIMS`; current PLAN.md and CLAIMS.md remain unchanged.
