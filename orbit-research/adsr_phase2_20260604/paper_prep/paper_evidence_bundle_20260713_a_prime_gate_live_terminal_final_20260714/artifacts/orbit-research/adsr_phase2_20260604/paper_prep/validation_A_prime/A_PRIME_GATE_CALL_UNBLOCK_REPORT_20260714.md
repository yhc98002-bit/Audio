# A-Prime Gate Call And Unblock Report

`A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`
evidence: `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`, `paper_prep/validation_A_prime/A_PRIME_GATE_RESULT_20260713.json`, `paper_prep/validation_A_prime/A_PRIME_STUDY_LOG.jsonl`, `paper_prep/validation_A_prime/A_PRIME_GATE_CALL_AUDIT_20260713.json`

`T6_LABEL_VALIDITY_STATUS = PROMOTED`
evidence: `paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`, `paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json`, `paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md`, `paper_prep/autochain_20260712/T6_RELIABILITY_RESULT.json`

`PLAN_CLAIMS_LABEL_VALIDITY = UPDATED`
evidence: `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`, `paper_prep/scripts/record_a_prime_gate_call_20260714.py`

`W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS`
evidence: `paper_prep/W2_AMENDMENT_20260712.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`

`W2_ADOPTION = PI1_SIGNED_PI2_INCOMPLETE`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`

`PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`
evidence: `paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md`, `paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md`, `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`

`LIVE_CONFIRM_STATUS = COMPLETE_CRITERIA_NOT_ALL_MET`
evidence: `paper_prep/w2_execution_20260712/live_confirmation_20260713/GENERATION_COMPLETION_AUDIT.json`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_AUDIT.json`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_REPORT.md`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv`

`EVIDENCE_BUNDLE_CURRENT = BUILT_PRE_ADOPTION`
evidence: `paper_prep/paper_evidence_bundle_20260713_a_prime_gate_live_terminal_final_20260714/INDEX.md`, `paper_prep/paper_evidence_bundle_20260713_a_prime_gate_live_terminal_final_20260714/SHA256SUMS`, `paper_prep/paper_evidence_bundle_20260713_a_prime_gate_live_terminal_final_20260714.tar.gz.sha256`

`EVIDENCE_BUNDLE_POST_ADOPTION = BLOCKED_W2_ADOPTION`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`

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

The W2 amendment now contains complete PI 1, PI 2, and auditing-attestation
blocks and is mechanically marked `SIGNED_BY_BOTH_PIS`. The separate
publication-adoption branch remains incomplete: its dedicated request still
has a blank PI 2 block, while the new escalation-file PI 2 sentence ends after
`the promoted corrected`. Therefore:

- live confirmation launched on `an12` GPUs 4-7 at
  `2026-07-14T17:00:55+08:00`; its first worker attempt failed in offline
  reward-model resolution, then resumed at `2026-07-14T17:18:55+08:00` after
  the local-model preflight passed;
- the four FLACs written before the reward-path failure were decoded, hashed,
  scored, and ledgered in place with `recovered_orphan=true`; none was
  overwritten or regenerated;
- all four resumed workers completed 128 units each before the original
  `2026-07-16T17:00:55+08:00` hard stop;
- during the live run, `paper_prep/heartbeat_an12.log` identified the four
  relative-path worker commands, reported each live-ledger line count, and
  marked the node `ADSR_RELEVANT_PROCESS_ACTIVE`; after completion it reports
  no active ADSR Python worker;
- generation passed the independent completion audit at 512/512 units, 1,536
  unique ledger rows, and 774/774 checksum-matching, fully decoded, non-silent
  FLACs;
- the frozen live criteria were not all met: policy 4 violation 0.312500 vs
  policy 1 0.265625 and policy 3 0.164062; policy4-vs-policy1 reduction LCB
  -0.109375 and policy4-vs-policy3 excess UCB 0.203125;
- no corrected online-router PASS or headline is issued; the unapplied draft
  records removal of that claim if/when publication adoption is completed;
- broad corrected-number PLAN/CLAIMS supersession was not applied;
- the prior evidence bundle remains a pre-gate-call historical snapshot and
  was not rewritten or presented as current;
- the targeted A-prime decision and instrument-scope wording update were
  applied under Richard's explicit gate-call instruction.

## Verification

- Gate recorder rerun idempotence: PASS; one PI decision event and one
  execution-ledger event remain.
- Focused tests: 8 passed, zero failed.
- Full repository tests in the required `audio-prm` environment: 355 passed,
  zero failed (`torch 2.7.1+cu126`).
- Signed-amendment/live-launch targeted suite: 36 passed, zero failed.
- Offline reward path/import preflight: PASS for local BERT, RoBERTa, BART,
  MERT, Audiobox, CLAP, and Whisper artifacts.
- A first system-Python collection probe lacked `torch` and produced five
  import errors; it was replaced by the canonical environment run above.
- Python compile checks and `git diff --check` passed.
- Implementation commit: `9723bcf869987e55024dc7081f511146c9f88852`.
