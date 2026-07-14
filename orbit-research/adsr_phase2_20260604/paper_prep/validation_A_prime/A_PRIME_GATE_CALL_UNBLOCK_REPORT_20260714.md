# A-Prime Gate Call And Unblock Report

`A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`
evidence: `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`, `paper_prep/validation_A_prime/A_PRIME_GATE_RESULT_20260713.json`, `paper_prep/validation_A_prime/A_PRIME_STUDY_LOG.jsonl`, `paper_prep/validation_A_prime/A_PRIME_GATE_CALL_AUDIT_20260713.json`

`T6_LABEL_VALIDITY_STATUS = PROMOTED`
evidence: `paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`, `paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json`, `paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md`, `paper_prep/autochain_20260712/T6_RELIABILITY_RESULT.json`

`PLAN_CLAIMS_LABEL_VALIDITY = UPDATED`
evidence: `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`, `paper_prep/scripts/record_a_prime_gate_call_20260714.py`

`W2_AMENDMENT_STATUS = PI1_SIGNED_PI2_PENDING`
evidence: `paper_prep/W2_AMENDMENT_20260712.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`

`W2_ADOPTION = PI1_SIGNED_PI2_PENDING`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`

`PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`
evidence: `paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md`, `paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md`, `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`

`LIVE_CONFIRM_STATUS = BLOCKED_UNSIGNED_W2_AMENDMENT`
evidence: `paper_prep/t7_judge_gold_20260713/gpu_queue/live_gpu_watch.jsonl`, `paper_prep/scripts/watch_gpu_queue_20260713.py`, `paper_prep/scripts/run_w2_liveconfirm_20260713.sh`

`EVIDENCE_BUNDLE_REFRESH = BLOCKED_W2_ADOPTION`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`, `paper_prep/paper_evidence_bundle_20260713_judge_pass_final/INDEX.md`

`TEST_SUITE_STATUS = PASS`
evidence: `paper_prep/validation_A_prime/A_PRIME_GATE_CALL_TEST_RESULT_20260714.json`, `tests/test_a_prime_gate_call_20260714.py`

## Decision Record

Richard's PI decision dated 2026-07-13 closes the pending A-prime gate as a
failure of the legacy 0.1791 Demucs-energy instrument. The completed,
provenance-enforced evidence contains 690 rows: 190 human-core rows rated by
`pi:Richard` and 500 supplement rows scored by the held-out-validated judge.

The frozen Label-A results are:

| Bucket | Matches/decided | Rate | Disposition |
|---|---:|---:|---|
| Detector disagreement | 7/112 | 0.062500 | fails frozen criterion |
| Rare basin | 16/47 | 0.340426 | fails frozen criterion; one abstain among 48 rows |
| Agreement controls | 28/30 | 0.933333 | meets frozen criterion |
| Stratified global disagreement | 124/493 | 0.251521 | outside pass shape |

These results quantify `demucs_missing`; they do not validate the legacy
detector. A-prime measures Label A, while the signed amendment makes
request-conditional Label B the paper-primary endpoint.

## Corrected Instrument

The label-validity claim is carried by the separate T6 held-out corrected-
instrument evaluation: design-weighted balanced accuracy 0.987308,
sensitivity 1.000000, specificity 0.974616, and 20/20 hidden-repeat agreement
for both Label A and Label B. `PLAN.md` and `CLAIMS.md` now separate this
positive corrected-instrument evidence from the negative A-prime legacy-
instrument result. No wording may state or imply that the legacy detector was
validated.

## Signature Recheck

PI 1 (`pi:Richard`) is present in both signature chains. PI 2 name, date,
commit, and authentic decision remain blank in both the W2 amendment and W2
adoption request; the requested independent attestation is also absent.
Therefore:

- the live-confirm watcher remains fail-closed even though `an12` is idle;
- broad corrected-number PLAN/CLAIMS supersession was not applied;
- the prior evidence bundle remains a pre-gate-call historical snapshot and
  was not rewritten or presented as current;
- the targeted A-prime decision and instrument-scope wording update were
  applied under Richard's explicit gate-call instruction.

## Verification

- Gate recorder rerun idempotence: PASS; one PI decision event and one
  execution-ledger event remain.
- Focused tests: 8 passed, zero failed.
- Full repository tests in the required `audio-prm` environment: 344 passed,
  zero failed (`torch 2.7.1+cu126`).
- A first system-Python collection probe lacked `torch` and produced five
  import errors; it was replaced by the canonical environment run above.
- Python compile checks and `git diff --check` passed.
- Implementation commit: `9723bcf869987e55024dc7081f511146c9f88852`.
