# T7 Ingest, Judge Validation, And Live-Confirm Queue

`T7_INGESTION_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_RATINGS_INGEST_AUDIT.json`, `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_TOPUP_INGEST_REPORT.md`

`JUDGE_VALIDATION_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv`, `paper_prep/t7_judge_gold_20260713/gpu_queue/judge_gpu_watch.jsonl`, `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`

`JUDGE_500_STATUS = COMPLETE`
evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`, `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_REPORT.md`

`A_PRIME_GATE = PI_CALL_PENDING`
evidence: `paper_prep/pi_ratings_20260711/processed/T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`, `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`

`W2_AMENDMENT_STATUS = PI1_SIGNED_PI2_PENDING`
evidence: `paper_prep/W2_AMENDMENT_20260712.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`

`W2_ADOPTION = PI1_SIGNED_PI2_PENDING`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`

`PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`
evidence: `paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md`, `paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md`, `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`

`LIVE_CONFIRM_STATUS = QUEUED_AWAITING_GPUS`
evidence: `paper_prep/t7_judge_gold_20260713/gpu_queue/live_gpu_watch.jsonl`, `paper_prep/scripts/run_w2_liveconfirm_20260713.sh`, `paper_prep/scripts/w2_liveconfirm_worker_20260713.py`

`EVIDENCE_BUNDLE_STATUS = BUILT`
evidence: `paper_prep/paper_evidence_bundle_20260713_judge_pass_final/INDEX.md`, `paper_prep/paper_evidence_bundle_20260713_judge_pass_final.tar.gz`

`TEST_SUITE_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/FULL_TEST_RESULT_SUMMARY_20260714.json`, `tests/test_t7_judge_gold_20260713.py`

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
- Frozen Label-A criteria all met: `false`. The gate remains `PI_CALL_PENDING` and cannot auto-pass.
- Core results: disagreement 7/112; rare basin 16/47 decided; controls 28/30.

## Queue Contract

- Judge watcher: local tmux `adsr_t7_judge_gpu_watch_20260713`, pane PID `not-running`; last state `LAUNCHED`.
- Judge launch: `an12` GPUs `[0, 1, 2, 3]` after 1224.5 continuous idle seconds at `2026-07-14T14:26:02+08:00`. Tensor parallelism 4 required one node and could not split across nodes.
- Live watcher: local tmux `adsr_w2_live_gpu_watch_20260713`, pane PID `4097341`; last state `WAITING`.
- Live launch predicate: both W2 amendment/adoption signatures plus four genuinely idle GPUs on one of `an12` or `an29` for 20 consecutive minutes. The prepared four-worker launcher does not split across nodes.
- Judge recovery polled every 2 minutes; the standing live watcher polls every 10 minutes. Queue timeout: 24 hours. No running process was killed, suspended, or preempted.
- The live-confirm 48-hour hard-stop clock begins only at the launcher's recorded actual-launch timestamp.
- The judge model and runtime were copied from `an29` to `an12`, checksum-dry-run verified, and CUDA-import tested. The first detached launch failed before GPU allocation because bare `python` was unavailable; the repaired launcher uses the verified runtime interpreter and completed on GPUs 0-3.

## Signature-Gated Branch

PI 1 (`pi:Richard`) is signed. PI 2 name/date/commit/decision remain blank in both the W2 amendment/adoption chain, and the Claude attestation remains absent. Therefore PLAN/CLAIMS supersession was not applied and the live launcher remains fail-closed even if GPUs are idle.

## Judge Branch

Pooled validation passed. The chain scored 493 unique stratified clips with three deterministic calls each, mapped results to all 500 frozen IDs, enforced the 190-human + 500-validated-judge provenance contract, and emitted `A_PRIME_GATE = PI_CALL_PENDING`. The frozen human-core Label-A conditions are not all met, so this report does not characterize A-prime as passed.

## Verification

- Full repository suite: 336 passed, zero failed.
- Focused T7 suite after the launcher and report fixes: 14 passed, zero failed.
- Python compile checks, launcher shell syntax, and `git diff --check` passed.
- Final evidence snapshot: 104 indexed artifacts and 111 checksummed files; every checksum passed.
- Final tarball SHA-256: `1e459c49014b7899ff78dd7be12054d066f36e78618e62e4c2c90717f9f2de3b`.
- Terminal implementation and evidence commit: `65094d43d0e19777caa0626c31a266a2869b5911`.
