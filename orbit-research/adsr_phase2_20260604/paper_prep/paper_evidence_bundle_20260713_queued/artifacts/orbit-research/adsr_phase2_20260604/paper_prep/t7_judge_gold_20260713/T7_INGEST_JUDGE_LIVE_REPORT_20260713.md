# T7 Ingest, Judge Validation, And Live-Confirm Queue

`T7_INGESTION_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_RATINGS_INGEST_AUDIT.json`, `paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_TOPUP_INGEST_REPORT.md`

`JUDGE_VALIDATION_STATUS = QUEUED_AWAITING_GPUS`
evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_DISJOINT_GOLD_MANIFEST.csv`, `paper_prep/t7_judge_gold_20260713/gpu_queue/judge_gpu_watch.jsonl`

`JUDGE_500_STATUS = QUEUED_AFTER_VALIDATION`
evidence: `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`

`A_PRIME_GATE = QUEUED_AFTER_JUDGE`
evidence: `paper_prep/pi_ratings_20260711/processed/T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv`, `paper_prep/scripts/complete_t7_judge_aprime_20260713.py`

`W2_AMENDMENT_STATUS = PI1_SIGNED_PI2_PENDING`
evidence: `paper_prep/W2_AMENDMENT_20260712.md`, `paper_prep/t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md`

`W2_ADOPTION = PI1_SIGNED_PI2_PENDING`
evidence: `paper_prep/t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md`, `paper_prep/autochain_20260712/recompute/DUAL_PI_ADOPTION_PACKET.md`

`PLAN_CLAIMS_SUPERSESSION = NOT_APPLIED`
evidence: `paper_prep/autochain_20260712/recompute/PLAN_UPDATE_DRAFT.md`, `paper_prep/autochain_20260712/recompute/CLAIMS_UPDATE_DRAFT.md`, `paper_prep/PLAN.md`, `paper_prep/CLAIMS.md`

`LIVE_CONFIRM_STATUS = QUEUED_AWAITING_GPUS`
evidence: `paper_prep/t7_judge_gold_20260713/gpu_queue/live_gpu_watch.jsonl`, `paper_prep/scripts/run_w2_liveconfirm_20260713.sh`, `paper_prep/scripts/w2_liveconfirm_worker_20260713.py`

`EVIDENCE_BUNDLE_STATUS = BUILT`
evidence: `paper_prep/paper_evidence_bundle_20260713_queued/INDEX.md`, `paper_prep/paper_evidence_bundle_20260713_queued.tar.gz`

`TEST_SUITE_STATUS = PASS`
evidence: `paper_prep/t7_judge_gold_20260713/FULL_TEST_RESULT_SUMMARY_20260713.json`, `tests/test_t7_judge_gold_20260713.py`

## Validated Input

- T7 response IDs: 40/40 exact; provenance: `pi:Richard`.
- Authoritative Label A composition: 40 `no`, zero blanks.
- Optional Label B blanks: 2; optional confidence blanks: 40.
- T7 hash overlap with detector selection/promotion: 0; overlap with prior judge gold: 0.
- Pooled disjoint gold: 216 rows = 149 human `yes` positives + 67 human `no` negatives.
- Stratified-500: 500 frozen IDs mapping to 493 unique media hashes; inference and estimation deduplicate first.

## Queue Contract

- Judge watcher: local tmux `adsr_t7_judge_gpu_watch_20260713`, pane PID `4097337`; last state `WAITING`.
- Judge launch predicate: four genuinely idle GPUs on `an29` for 20 consecutive minutes. The 66 GiB node-local model uses tensor parallelism 4 and cannot split across nodes.
- Live watcher: local tmux `adsr_w2_live_gpu_watch_20260713`, pane PID `4097341`; last state `WAITING`.
- Live launch predicate: both W2 amendment/adoption signatures plus four genuinely idle GPUs on one of `an12` or `an29` for 20 consecutive minutes. The prepared four-worker launcher does not split across nodes.
- Poll interval: 10 minutes. Queue timeout: 24 hours. No running process is killed, suspended, or preempted.
- The live-confirm 48-hour hard-stop clock begins only at the launcher's recorded actual-launch timestamp.

## Signature-Gated Branch

PI 1 (`pi:Richard`) is signed. PI 2 name/date/commit/decision remain blank in both the W2 amendment/adoption chain, and the Claude attestation remains absent. Therefore PLAN/CLAIMS supersession was not applied and the live launcher remains fail-closed even if GPUs are idle.

## Judge Branch

If pooled validation passes, the chain scores 493 unique stratified clips, maps results to all 500 frozen IDs, enforces the 190-human + 500-validated-judge provenance contract, and emits `A_PRIME_GATE = PI_CALL_PENDING`. If validation fails, the judge remains exploratory and the same gate status is emitted from the official 190-row human core alone. Neither branch auto-passes A-prime.
