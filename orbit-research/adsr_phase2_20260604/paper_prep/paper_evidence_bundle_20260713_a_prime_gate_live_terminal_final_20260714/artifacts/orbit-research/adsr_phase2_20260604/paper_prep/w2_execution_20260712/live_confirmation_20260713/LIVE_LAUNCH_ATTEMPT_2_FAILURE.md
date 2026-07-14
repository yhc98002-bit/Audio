# Live Confirmation Launch Attempt 2 Failure

`ATTEMPT_2_STATUS = FAILED_RECOVERABLE_REWARD_PATH`

- Actual launch: `2026-07-14T17:00:55+08:00`.
- Hard-stop deadline: `2026-07-16T17:00:55+08:00`; recovery does not reset it.
- Node/GPUs: `an12`, GPUs 4-7 after the non-preemptive idle predicate passed.
- Generation reached ACE-Step decoding on all four workers.
- Four non-silent, decodable 48 kHz FLACs were written before reward scoring.
- Five append-only records were written: four slot records and one unit-selection record.
- All workers then failed in common reward scoring before the generated FLACs
  could receive terminal slot records.

## Exact Cause

The CLAP compatibility shim and MERT reward still defaulted to obsolete
`/home/yehaocun23s/source/...` paths. Although the required checkpoints existed
under `/HOME/paratera_xy/pxy1289/source/`, reward loading fell back to
Hugging Face. The closed-network request for `facebook/bart-base` failed with
`RuntimeError: Cannot send a request, as the client has been closed`; MERT also
attempted a remote HEAD request. The worker traces are preserved in
`logs/worker_{0,1,2,3}.stderr.log`.

This is an execution-path defect, not a generation failure and not a metric
result. `LIVE_CONFIRM_STATUS = WORKER_FAIL` was therefore never treated as a
warning or PASS.

## Recovery

- Pin BERT, RoBERTa, BART, MERT, Audiobox, CLAP, and Whisper to verified local
  files and force Transformers/Hugging Face offline mode.
- Run a fail-closed offline import/path preflight before GPU allocation.
- Preserve the original launch timestamp and hard-stop deadline on resume.
- Recover and score every valid FLAC that exists without a terminal slot row;
  never overwrite or silently regenerate it.
- Write per-resume worker logs instead of truncating the failed traces.

Evidence: `paper_prep/scripts/preflight_w2_reward_models_20260714.py`,
`paper_prep/scripts/run_w2_liveconfirm_20260713.sh`,
`paper_prep/scripts/w2_liveconfirm_worker_20260713.py`,
`paper_prep/w2_execution_20260712/live_confirmation_20260713/audio/`, and
`paper_prep/w2_execution_20260712/live_confirmation_20260713/live_ledgers/`.
