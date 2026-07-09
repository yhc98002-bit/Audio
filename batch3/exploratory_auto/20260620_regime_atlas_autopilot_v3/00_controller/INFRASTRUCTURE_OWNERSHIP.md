# INFRASTRUCTURE OWNERSHIP

- Launch mechanism: **nohup-detached non-LLM workers** per node (proven this project; resume via
  per-worker ledger replay). tmux/slurm available if needed.
- Detachment/resume owner: each worker owns its own `ledger_w{i}.jsonl` (append-only, skip-done resume).
- Orchestrator (Claude Code) only: writes specs, launches, monitors heartbeat/logs, validates, analyzes.
- Shared FS: `/XYFS02` Lustre is visible from login + an17 + an29 (same paths) → a single shared
  `queue/` under the output root is usable across nodes. (To be exercised at large-N; sanity gate
  used direct per-node launch.) `/dev/shm` is node-local (transient WAV only; never for queue/ledgers).
- Quota: /XYFS02 500/510GB; keep-only + FLAC + /dev/shm transient. Check `lfs quota -u pxy1289 .`.
