# QUEUE SCHEMA

Filesystem queue under `queue/{pending,running,done,failed}`. Atomic claim = rename
pending/job.json → running/{host}_{pid}_{jobid}.json. Success→done/, fail→failed/+report. Max 2 retries.

Job JSON: job_id, workstream, model, modality, prompt_list, seed_start, seed_end, axis,
condition, output_dir, expected_rows, max_wallclock_hours, validation_command, resume_policy,
keep_policy, detector_config, priority(spine=high/exploration=low), created_by, created_at.

Circuit breakers: gen chunk ≤12h, scoring ≤6h, analysis ≤4h, sanity ≤2h; no heartbeat/progress
>90min ⇒ stale⇒inspect. Chunk large-N (8–32 prompts × 32–64 seeds/job). Validate chunks incrementally.
NOTE: shared-mount visibility across an17/an29 to be verified in INFRASTRUCTURE_OWNERSHIP.md before
multi-node queueing; until then per-node launch (node_launcher pattern) is used.
