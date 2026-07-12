# W2 Node Saturation Audit

Date: 2026-07-12 (Asia/Shanghai)
Scope: W2 amendment execution from the first factorial dispatch through the
exact-runtime spine replay and scoring handoff.

## Evidence Sources

- `paper_prep/heartbeat_an12.log`
- `paper_prep/heartbeat_an29.log`
- `paper_prep/execution_20260709/CODE_REVIEW_RECOVERY_LEDGER.jsonl`
- `paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/generation_ledgers/`
- `paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery/scoring_ledgers/`
- `paper_prep/w2_execution_20260712/factorial/`

The dedicated W2 heartbeat sessions started at 18:35 and append a full GPU,
tmux, Python-process, and ledger-count block every ten minutes. Historical
heartbeat blocks before 21:32 have a known status-line defect: the broad
`pgrep` matched the heartbeat process and sleeping tmux wrappers. Those
`ADSR_RELEVANT_PROCESS_ACTIVE` lines are not used as utilization evidence.
The GPU/process/tmux payloads remain valid. At 21:32 the implementation was
changed to count only live project `w2_*.py` Python workers; two regression
tests passed, both heartbeat sessions were restarted, and the first corrected
blocks accurately reported `NO_ADSR_RELEVANT_PROCESS_ACTIVE` after scoring.

## an12

- ADSR work run: first spine reconstruction, first current/candidate detector
  scoring, Batch-3 scoring completion, survivor/runtime diagnosis, the 51-row
  exact-runtime probe, exact-runtime full replay shards, and rotating detector
  score shards.
- The exact replay initially used workers 0-7. When pre-existing load reduced
  headroom on GPUs 0-4 to about 7 GiB, workers 0-4 were stopped cleanly and
  resumed on second slots on an29. Workers 5-7 completed on an12.
- Exact replay outcome before the final audit: 4,096/4,096 unique generation
  PASS rows, zero duplicates, zero failures, and zero near-silent rows.
- Scoring launched only after all GPUs passed a 10-GiB free-memory gate. The
  initial score processes used about 2.0-2.3 GiB each. Shards on GPUs 0-4 were
  moved away when they were compute-starved; GPUs 5-7 then served deterministic
  shard rotations until all 16 ledgers reached 256 rows.
- Final score outcome: 4,096/4,096 unique PASS rows, zero duplicate task IDs,
  and zero failures. All scoring tmux sessions were closed at 21:29.
- Non-ADSR occupancy: BlindGain Qwen jobs occupied GPUs 0-4 from before this
  recovery run, using roughly 61-64 GiB per GPU. No ADSR document located here
  establishes PI authorization for those jobs. They are not counted as ADSR
  progress and were not interrupted. The user's non-interference rule allowed
  co-location only while explicit memory headroom remained safe.

## an29

- ADSR work run: 3,072-row instrumental factorial generation, the corrected
  1,024-row positive-only cohort, factorial/current-candidate scoring, first
  spine reconstruction/scoring shards, isolated torch-2.5.1 wheel staging and
  environment validation, exact-runtime probe/replay, and final scoring.
- During exact generation, workers 8-15 plus relocated workers 0-4 ran on
  GPUs 0-4 in safe second slots. More than 60 GiB per affected GPU remained
  free after relocation. Workers 13-15 and all original shards completed
  without task overlap.
- During scoring, one process per GPU used about 2.2 GiB. Incomplete paired
  shards were rotated to free an12 GPUs 5-7 only after their old process was
  stopped. The global completed-ID scan and final 256-row-per-shard audit show
  zero handoff duplication.
- No non-ADSR GPU process was observed on an29 during the final exact-runtime
  replay/scoring interval.

## Idle-Gap Audit

- an12 had one material free-slice gap, approximately 19:45-20:42, after the
  first spine audit exposed a runtime-fidelity failure and before the isolated
  torch-2.5.1 runtime plus 51/51 probe authorized replay. The exact dependency
  recovery ran on an29 during this interval. Launching another replay on an12
  would have repeated known-invalid torch-2.7.1 evidence; no other approved W2
  GPU task was unblocked. GPUs 0-4 remained occupied by non-ADSR work and are
  not counted as ADSR utilization.
- an29 has no unexplained ADSR gap longer than 30 minutes in the audited W2
  interval. It moved from factorial/spine work to environment recovery, probe,
  replay, and scoring.
- From 21:29, both nodes were GPU-idle while the mandatory full 64-GiB decoded-
  audio fidelity audit ran on the login host. Promotion, EVPD training, human
  ratings, and live confirmation remained signature/rating-gated, so no safe
  GPU successor was eligible for launch.

## Current Disposition

At the scoring handoff, all W2 GPU generation and detector scoring jobs were
complete and their tmux sessions were closed. Heartbeat sessions remain active
on both nodes. The subsequent full audit passed with 4,096/4,096 generation
rows, 4,096/4,096 scoring rows, 50/50 exact controls, 1/1 exact surviving
original, and no missing, invalid, near-silent, duplicate, or conflicting
rows. This audit does not promote the candidate instrument or change
`PLAN.md`.
