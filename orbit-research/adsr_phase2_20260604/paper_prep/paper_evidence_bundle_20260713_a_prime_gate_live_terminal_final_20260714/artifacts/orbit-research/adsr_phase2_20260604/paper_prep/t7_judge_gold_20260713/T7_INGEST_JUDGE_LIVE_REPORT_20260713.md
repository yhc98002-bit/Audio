# T7 Ingest, Judge Validation, And Live-Confirm Queue

`T7_INGESTION_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_RATINGS_INGEST_AUDIT.json`, `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_TOPUP_INGEST_REPORT.md`

`JUDGE_VALIDATION_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv`, `paper_prep/t7_judge_gold_20260713/gpu_queue/judge_gpu_watch.jsonl`, `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`

`JUDGE_500_STATUS = COMPLETE`
evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`, `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_REPORT.md`

`A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`
evidence: `paper_prep/pi_ratings_20260711/processed/T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`, `paper_prep/scripts/record_a_prime_gate_call_20260714.py`, `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`

`W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS`
evidence: `paper_prep/W2_AMENDMENT_20260712.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`

`W2_ADOPTION = PI1_SIGNED_PI2_INCOMPLETE`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`

`PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`
evidence: `paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md`, `paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md`, `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`

`LIVE_CONFIRM_STATUS = COMPLETE_CRITERIA_NOT_ALL_MET`
evidence: `paper_prep/w2_execution_20260712/live_confirmation_20260713/GENERATION_COMPLETION_AUDIT.json`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_AUDIT.json`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_REPORT.md`, `paper_prep/w2_execution_20260712/live_confirmation_20260713/LIVE_CONFIRM_RESULTS.csv`

`EVIDENCE_BUNDLE_STATUS = BUILT`
evidence: `paper_prep/paper_evidence_bundle_20260713_a_prime_gate_live_terminal_final_20260714/INDEX.md`, `paper_prep/paper_evidence_bundle_20260713_a_prime_gate_live_terminal_final_20260714.tar.gz`

`TEST_SUITE_STATUS = PASS`
evidence: `paper_prep/validation_A_prime/A_PRIME_UNBLOCK_FULL_TEST_SUMMARY_20260714.json`, `tests/test_t7_judge_gold_20260713.py`

## Validated Input

- T7 response IDs: 40/40 exact; provenance: `pi:Richard`.
- Authoritative Label A composition: 40 `no`, zero blanks.
- Optional Label B blanks: 2; optional confidence blanks: 40.
- T7 hash overlap with detector selection/promotion: 0; overlap with prior judge gold: 0.
- Pooled disjoint gold: 216 rows = 149 human `yes` positives + 67 human `no` negatives.
- Stratified-500: 500 frozen IDs mapping to 493 unique media hashes; inference and estimation deduplicate first.

## Judge Validation And A-Prime

- Pooled judge validation: sensitivity 0.991421, specificity 0.909989, balanced accuracy 0.950705, MCC 0.946184, abstention 0.000000.
- One-sided 95% lower bounds: sensitivity 0.982743, specificity 0.893122, balanced accuracy 0.941113; all frozen checks passed.
- Gold-set SHA-256: `2b2008a63ff4a9e95c20384062baa510575c292bfa3809fc33abac128d380594`; tuning/evaluation overlap: 0.
- Stratified judge result, all unique clips: apparent voice rate 0.916836; calibrated voice rate 0.917257.
- Requested-instrumental clips: apparent Label-A violation 0.719178; calibrated violation 0.697981.
- Provenance merge: 690 rows = 190 PI core + 500 validated-judge supplement.
- Frozen Label-A criteria all met: `false`. PI decision: `FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`; the legacy instrument is not validated.
- Core results: disagreement 7/112; rare basin 16/47 decided; controls 28/30.

## Queue Contract

- Judge watcher: local tmux `adsr_t7_judge_gpu_watch_20260713`, pane PID `not-running`; last state `LAUNCHED`.
- Judge launch: `an12` GPUs `[0, 1, 2, 3]` after 1224.5 continuous idle seconds at `2026-07-14T14:26:02+08:00`. Tensor parallelism 4 required one node and could not split across nodes.
- Live execution status: `COMPLETE_CRITERIA_NOT_ALL_MET`. It ran in remote tmux `adsr_w2_liveconfirm_resume_20260714` on `an12` GPUs 4-7; GPUs 0-3 were occupied by another PI job and were not touched.
- Live launch predicate: signed W2 amendment plus mechanical T6 promotion and four genuinely idle GPUs on one node. The prepared four-worker launcher does not split across nodes.
- Judge recovery polled every 2 minutes; the standing live watcher polls every 10 minutes. Queue timeout: 24 hours. No running process was killed, suspended, or preempted.
- The live-confirm clock began at `2026-07-14T17:00:55+08:00` and ends at `2026-07-16T17:00:55+08:00`; recovery did not reset either timestamp.
- Attempt 2 failed after generation when obsolete local reward-model defaults fell back to blocked Hugging Face. The repaired resume passed an offline local-model preflight and recovered four orphan FLACs in place without regeneration.
- The judge model and runtime were copied from `an29` to `an12`, checksum-dry-run verified, and CUDA-import tested. The first detached launch failed before GPU allocation because bare `python` was unavailable; the repaired launcher uses the verified runtime interpreter and completed on GPUs 0-3.

## Signature-Gated Branch

The W2 amendment has complete PI 1, PI 2, and Claude blocks, so the live branch was authorized and executed. Publication adoption remains fail-closed because its dedicated PI 2 block is blank and the escalation-file PI 2 sentence is truncated. Therefore broad W2 corrected-number supersession was not applied. The targeted A-prime PI gate-call and instrument-scope wording update are separately authorized by the 2026-07-13 PI decision.

## Live Confirmation Result

- Result: `CRITERIA_NOT_ALL_MET`; no automatic PASS was issued.
- Generation audit: 512/512 units, 1,536 unique ledger records, and 774/774 checksum-matching decoded FLACs.
- Final violation: no-probe reseed 0.265625; corrected probe/action 0.312500; always direction-conditioned 0.164062.
- Frozen primary reduction LCB: -0.109375; policy-3 noninferiority UCB: 0.203125.
- Primary superiority and policy-3 noninferiority were not met; no corrected online-router headline is available.

## Judge Branch

Pooled validation passed. The chain scored 493 unique stratified clips with three deterministic calls each and mapped results to all 500 frozen IDs. The 690-row provenance contract is complete. The PI recorded `A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`; A-prime is the falsification study for the legacy instrument, not a PASS. Positive label-validity evidence is instrument-scoped to the separate T6 corrected-instrument held-out evaluation.
