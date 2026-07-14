# Live Confirmation Launch Attempt 1 Failure

`LIVE_LAUNCH_ATTEMPT_1 = FAIL_PRE_GPU_CLIENT_ENV`

- Watcher dispatch: `2026-07-14T16:56:20+08:00`.
- Watcher launch timestamp: `2026-07-14T16:56:24+08:00`.
- Node/GPU allocation: `an12`, GPUs 4-7 after 20 continuous idle minutes.
- GPU processes started: 0.
- Live ledger rows written: 0.
- `ACTUAL_LAUNCH_TIMESTAMP.txt` written: no.
- 48-hour clock started: no.

The remote tmux session exited after creating the output directory and before
the launch guard or any worker started. The launcher invoked bare `python` for
its GPU occupancy check before activating `audio-prm`; bare `python` is absent
from the non-login tmux environment on `an12`. This is the same pre-GPU client
environment class already observed in the repaired T7 judge launch.

Recovery: activate `audio-prm` before the occupancy check, capture launcher
stdout/stderr, re-run syntax and guard tests, re-check GPUs 4-7, and relaunch on
the already-qualified allocation. No evidence, GPU process, or hard-stop clock
was created by attempt 1.

Evidence:

- `paper_prep/t7_judge_gold_20260713/gpu_queue/live_gpu_watch.jsonl`
- `paper_prep/scripts/run_w2_liveconfirm_20260713.sh`
- `paper_prep/scripts/watch_gpu_queue_20260713.py`
- empty pre-worker directory
  `paper_prep/w2_execution_20260712/live_confirmation_20260713/logs/`

