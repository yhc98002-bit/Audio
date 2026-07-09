# ORBIT Researcher Log

## 2026-05-24 Phase C1 Cost-Aware First Wave

PI instruction: advance Phase C1 first-wave under updated <=240 GPU-h decision rule, while running two offline diagnostics when possible:
Early-Tweedie pruning retrospective and time-uniform quality diagnostic.

Research interpretation:
- Primary question: can C1 first-wave be launched/completed without changing method definitions, after the prior run stopped under the old 120 GPU-h cap?
- Diagnostic hypothesis F: bad trajectories are often identifiable from early Tweedie estimates, enabling inference-time pruning.
- Diagnostic hypothesis G: good vs bad generations differ by persistent/global quality more than isolated local time failures.

Initial delegation:
- executor: C1 cost triage, scheduling plan, proposed launch command, Claude Code review; no formal launch until Researcher GO.
- helper: offline diagnostics from existing artifacts, prompt/artifact consistency, Claude Code review; no C1 config edits or GPU use without approval.

Initial independent observations:
- `configs/runs/phase_c1_firstwave.yaml` still records the old `safety.hard_cap_gpu_h: 120.0` and launch policy threshold 120.
- `runs/phase_c1_firstwave_20260524_115325/observed_cost_projection.json` projects 168.1218 GPU-h total across four methods from early observed steps.
- `scripts/launch_phase_c1_firstwave_8gpu.sh` launches one method per GPU on GPUs 0-3; it does not prompt-shard a method.
- `scripts/phase_c1_grpo.py` refuses to append to an existing train log and checkpointing occurs every 100 steps or at completion.
- No checkpoint files were found under the partial run at max depth 3 during initial inspection.
- Current GPU snapshot showed all 8 A800s idle.

Policy-only edit:
- Updated `configs/runs/phase_c1_firstwave.yaml` cap fields from 120.0 to 240.0 to match the PI's current Task C launch rule.
- Updated the matching comment in `scripts/launch_phase_c1_firstwave_8gpu.sh`.
- No reward, sigma, prompt, credit-unit, seed, step-count, method, or gate definition was changed.

## 2026-05-24 13:20 CST C1 Launch Gate

Independent Claude launch audit returned `ACCEPT_WITH_NONBLOCKING_NOTES`.
Accepted points: reward, sigma, prompt, credit-unit, method, seed, step-count,
and gate definitions are preserved; the four methods are comparable; the
stopped partial run is not a fair resume point; one-method-per-GPU parallelism
is scientifically safe; and the active GPU-hour projection (`154.74-168.12`) is
below the PI's current `240.0` Task C cap.

Nonblocking notes: stale `120.0` hard caps remain in per-method diagnostic
configs but do not drive runtime enforcement; the partial projection artifact
still records the old cap; the launcher uses GPUs 0-3 only; terminal method
cost estimates need early monitoring.

Formal C1 clean restart launched in tmux session `c1_firstwave`:

```bash
bash scripts/launch_phase_c1_firstwave_8gpu.sh configs/runs/phase_c1_firstwave.yaml runs/phase_c1_firstwave_20260524_researcher_go_01
```

Preflight and pairing audit passed before method processes started. An
accidental `_probe` root was created and terminated after a few seconds; it is
marked non-formal and must not be used as evidence.

## 2026-05-24 Diagnostics Review

Helper generated offline diagnostic reports from cached H2/H3 artifacts. Claude
diagnostics review required tightening the Early-Tweedie claim boundary because
the exact BoN candidate-level quantities were unavailable from current
artifacts. The revised report now:

- labels the requested BoN-retention test as
  `unavailable_for_requested_bon_retention_test`;
- labels the H2 early/final persistence analysis as `likely_proxy`;
- explicitly mark exact BoN winner-retention, false-negative, and pruned
  schedule metrics unavailable from current artifacts;
- flag lyric-intelligibility rows as non-robust when `top_pruned` is high;
- clarify that H3 credit-unit `FAIL` and time-uniform `likely` answer different
  questions.

The time-uniform report was then narrowed to CU-FW/CU-BW only and regenerated
from cached H3 artifacts. Claude review returned `PASS` with no required fixes.
Residual scientific risks: CU-BW musicality is near threshold, and coherence is
weak/degenerate in cached local vectors.

## 2026-05-24 Continued C1 Monitoring Policy

PI requested continued monitoring and notification when results are out.
Researcher delegated existing C1 run monitoring to executor with low-frequency
polling only:

- no configs/scripts/raw outputs edited;
- no relaunch/restart/resume without Researcher approval;
- routine polling updates suppressed;
- notify only checkpoint/completion/failure/cost-cap/safety/GPU-stall/decision
  events;
- completion interpretation requires Claude review if used as scientific
  evidence.

## 2026-05-24 Helper Follow-Up Tasks During Live C1

PI instructed that C1 remains primary and must not be interrupted. Current live
GPU snapshot showed C1 on physical GPUs 0-3 and GPUs 4-7 idle. Researcher
assigned helper three independent tasks:

1. Build `scripts/analyze_phase_c1_firstwave.py` and
   `orbit-research/C1_POSTRUN_ANALYSIS_TEMPLATE.md` for post-run C1 tables and
   plot-ready curves.
2. Write `orbit-research/TIME_UNIFORM_QUALITY_PI_MEMO.md` from existing
   time-uniform artifacts without changing method or paper claims.
3. Check existing candidate-level Early-Tweedie BoN artifacts; if absent, run a
   small isolated BoN-8 collection only on physical GPUs 4-7 after cost estimate
   and Claude CLI review. Stop/pause if GPU contention appears.

No routine helper updates requested; notify only completion, blocker, P0,
contention, or decision-needed state.

## 2026-05-24 Multi-Agent Long-Message Transport Fix

PI observed that large delegated prompts can be compressed by the Codex chat UI
as `[Pasted Content ...]` and then remain stuck in the worker composer. Diagnosis
from the helper pane confirmed:

- direct multi-kilobyte tmux paste into Codex is unsafe;
- `Enter` did not reliably submit worker messages in the helper pane;
- `Tab` did submit/queue the short worker prompt;
- clearing a stuck composer with `Ctrl-C` can terminate the worker Codex session,
  so it should not be used as a normal delivery recovery path.

Researcher updated `/tmp/orbit_tmux_comm.sh`:

- messages over 900 bytes or containing newlines are now written under
  `/HOME/paratera_xy/pxy1289/.codex/orbit_comm/inbox/<agent>/`;
- the worker chat receives only a one-line pointer with `file_sha256` and
  `file_bytes`;
- `send-file` supports explicitly prepared payload files;
- `spool-only` supports local protocol tests without disturbing live workers;
- default `send`/`send-file` worker submit key is `Enter`, so
  `[Task assigned by Researcher]` messages are delivered immediately instead of
  queued behind the worker's current task;
- explicit `queue`/`queue-file` commands use `Tab` only for intentionally
  low-priority queued follow-ups;
- payload pointer hash now refers to the actual file hash, not only the raw
  message-body hash.

The protocol was validated by sending helper a file-backed task pointer; helper
read the payload from disk and ACKed the task. The first live pointer had a
wrapper-level checksum mismatch because the original script advertised the raw
message hash; helper correctly treated it as an audit concern and continued
only after identifying it as a wrapper issue. The bug is fixed for future
payloads. One harmless `/tmp/orbit_comm_test` regression pointer was queued to
helper during testing; future tests should use `spool-only` instead. PI then
clarified that task-assignment messages must use `Enter`, not the Codex queue;
the script and Researcher identity config were updated accordingly. Follow-up
calibration showed that tmux key name `Enter` can leave text in the composer;
the reliable implementation of "press Enter" for this TUI is tmux `C-m`.
`/tmp/orbit_tmux_comm.sh` now defaults to `C-m` for `send`/`send-file`, while
`queue`/`queue-file` remain explicit `Tab` operations.

PI further clarified monitoring policy: fast-iteration worker windows should be
checked with occasional low-frequency tmux snapshots to decide whether
Researcher clarification is needed, but stable windows waiting on long training,
reviews, or well-specified tasks should not be actively probed; wait for worker
outbox/completion/stage-level reports instead. Researcher identity config was
updated with this window-state-aware polling rule.

## 2026-05-24 C1 Background Watcher

PI agreed to convert C1 checkpoint monitoring from passive executor ACK into a
real lightweight watcher. Researcher created
`/HOME/paratera_xy/pxy1289/.codex/orbit_c1_watcher.py`, which is read-only for
experiment artifacts and writes only `.codex` watcher state/outbox/heartbeat
files.

Initial dry-run caught a watcher bug: the fatal-pattern regex matched `INFO` as
`Inf`. The false-positive dry-run watcher state/outbox were archived with
`dryrun_falsepositive_20260524_151707` suffixes. The regex was fixed to require
word-boundary `NaN`/`Inf`, and dry-run then reported zero events and zero fatal
tail hits.

An initial `nohup ... &` launch wrote one heartbeat but did not persist in this
exec environment, with no error log. Researcher switched to a dedicated tmux
session `c1_watcher`, which is the active watcher mechanism:

```bash
tmux new-session -d -s c1_watcher -c /XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion \
  "bash -lc '/HOME/paratera_xy/pxy1289/.codex/orbit_c1_watcher.py \
  --run-root runs/phase_c1_firstwave_20260524_researcher_go_01 \
  --interval-seconds 60 \
  --post-checkpoint-interval-seconds 300 \
  --stall-seconds 1800 \
  >> /HOME/paratera_xy/pxy1289/.codex/c1_watcher.log 2>&1'"
```

Python watcher PID recorded at `/HOME/paratera_xy/pxy1289/.codex/c1_watcher.pid`; heartbeat at
`/HOME/paratera_xy/pxy1289/.codex/c1_watcher_heartbeat.json`; stage/P0 events at
`/HOME/paratera_xy/pxy1289/.codex/c1_watcher_to_researcher_outbox.jsonl`. The
watcher notifies only on step-100 checkpoint, checkpoint failure, method/all
completion, launcher exit, non-finite/parse errors, fatal log patterns, or
30-minute log stall.

## 2026-05-24 C1 Acceleration and Step-Budget PI Decision

PI decided not to hot-switch the current healthy 4-GPU C1 run. Current C1 should
continue until all-method step100 checkpoint unless P0 stop conditions occur.
In parallel, idle GPUs should be used to test whether a scientifically
equivalent 2-GPU-per-method path is feasible.

Researcher actions:

- Sent executor a concise updated monitoring instruction: continue current C1
  only to all-method step100, notify only all-method step100 or P0, do not edit
  configs or launch experiments.
- Sent helper a file-backed task assignment to evaluate a 2-GPU
  rollout-parallel/shared-adapter smoke on physical GPUs 5-6. GPU4 is occupied
  by the existing Early-Tweedie diagnostic and may finish if non-contending.
- Created `orbit-research/PHASE_C1_STEP_BUDGET_REVIEW.md`.

Step-budget review summary from live logs at 2026-05-24 16:01 CST:

- consumed active GPU-h: about `10.33`;
- estimated remaining to all-method step100: about `1.9 h`;
- estimated remaining to all-method step250: about `9.0 h` and `23.3`
  incremental active GPU-h;
- estimated remaining to all-method step1000: about `44.4 h` and `126.5`
  incremental active GPU-h;
- recommendation: do not clean-restart solely for step250. Treat step100 as
  health/early trend, step250 as the first C1 decision checkpoint, and step1000
  as extended training only if early trends justify it.

Helper completed the PI-priority follow-up at 2026-05-24 16:31 CST:

- C1 analyzer/template complete.
- Time-uniform PI memo complete.
- Early-Tweedie BoN-8 dev diagnostic complete on GPU4:
  `256` rows, `1.076944` GPU-h, sigma0.8 top4 winner retention `0.875`,
  pruning schedule winner match `0.469`, mean regret `0.128652`.
- 2GPU R8a shared-adapter smoke complete on GPUs 5/6:
  PASS, one controller-owned adapter/optimizer, full group aggregation,
  adapter update, base frozen, checkpoint/resume OK, Claude post-run review
  ACCEPT.

Researcher created
`orbit-research/PHASE_C1_8GPU_CLEAN_RESTART_PLAN_2026-05-24.md`. The plan is
not a launch authorization. Decision judgment: the 2GPU smoke supports
engineering feasibility, but does not justify clean-restarting solely to reach
step250. Continue current 4GPU C1 to step250 unless all-method step100 reveals
a stop issue or PI explicitly chooses restart. Reconsider 8GPU clean restart for
extended training only after step250 trends and a full four-method 8GPU runner
audit.

## 2026-05-24 Early-Tweedie Canonical Sync and C1 Poll

Researcher found that the canonical Early-Tweedie files under `orbit-research/`
still contained the earlier proxy-only `unavailable_for_requested_bon_retention_test`
state, while helper's GPU4 candidate-level BoN diagnostic had completed under
`runs/early_tweedie_bon_collection_20260524_1518/`.

Action taken:

- Archived the old proxy/unavailable canonical files to
  `orbit-research/archive/2026-05-superseded-state/`.
- Promoted the GPU4 candidate-level result to
  `orbit-research/EARLY_TWEEDIE_PRUNING_RETROSPECTIVE.md` and
  `orbit-research/EARLY_TWEEDIE_PRUNING_RETROSPECTIVE.json`.
- Added the requested plot-ready table with columns:
  `schedule`, `compute_fraction`, `reward_fraction`, `winner_retention`,
  `false_negative_rate`.

Canonical Early-Tweedie summary:

- status `PASS`;
- 32 dev prompts, BoN-8, 256 candidate records;
- GPU4 only, 1.076944 GPU-h;
- sigma0.8 top4 full-winner retention `0.875`;
- sigma0.8 bottom25 false-negative rate `0.031`;
- schedule `sigma0.9_top4_sigma0.7_top2_final_top1`: compute fraction `0.500`,
  reward fraction `0.984`, exact winner retention `0.469`, false-negative rate
  `0.531`.

C1 poll at 2026-05-24 16:47 CST:

- R8a: step 77, no checkpoint yet;
- R8b: step 72, no checkpoint yet;
- M-FixedWin: step 149, `checkpoint_step_000100.pt` present;
- M-Section: step 171, `checkpoint_step_000100.pt` present;
- all inspected numeric JSON fields finite;
- four training processes and `c1_watcher` process alive;
- GPU0-3 active, GPU4-7 idle.
