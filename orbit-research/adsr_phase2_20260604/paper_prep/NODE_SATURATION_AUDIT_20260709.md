# ADSR Node Saturation Audit

Audit date: 2026-07-10 (Asia/Shanghai)

Scope: recovery tasks T0-T11 on `an12` and `an29`. GPU processes from other
repositories are reported but are not counted as ADSR utilization.

## Current Snapshot

Snapshot time: 2026-07-10 20:04 Asia/Shanghai.

| Node | GPU state | ADSR-relevant process | Non-ADSR process | Assessment |
|---|---|---|---|---|
| `an12` | GPUs 0-3 active; GPUs 4-7 free | none currently | BlindGain Ray training/evaluation on GPUs 0-3; additional BlindGain launchers present | The active load is not ADSR and is not counted. No repository artifact establishes PI authorization for that load. Processes were left untouched. |
| `an29` | GPUs 0,2,3,4 hold about 65.9 GiB each; other GPUs report 2 MiB at snapshot | Qwen3-Omni vLLM service in `adsr_qwen_server` on GPUs 0,2,3,4 | BlindGain launchers target GPUs 1,5,6,7 but had not allocated GPU memory at snapshot | Four GPUs are reserved by the working ADSR judge service. Unrelated processes are not counted and were left untouched. |

The Qwen service has zero utilization between requests; residency is retained so
the PI-gold smoke can run without repeating a 70.5 GB model transfer and model
startup. Its infrastructure smoke completed 10/10 calls. This is prepared ADSR
capacity, not evidence of judge validation.

## ADSR Work Executed

### `an12`

- T2 regeneration-fidelity control replay: 50 controls plus the 126-row
  sensitivity cohort; final status `EXACT`.
- T9 ACE-Step v1.5 bounded replication generation/scoring: 2 smoke rows, 1,024
  prevalence rows, 512 retry rows, and 256 matched intervention rows; final
  status `COMPLETE`.
- T7 was assigned to `an29` after T8 and T9 completed because both complete
  Qwen snapshots and the pinned runtime were staged in `an29` node-local memory.

Primary evidence:

- `validation_A_prime/REGENERATION_FIDELITY_REPORT.md`
- `v15_replication_20260709/V15_FINAL_REPLICATION_REPORT.md`
- `heartbeat_an12.log`

### `an29`

- T8 SA3 true-intermediate capture, threshold-calibration package construction,
  and intervention-fidelity audit; final statuses
  `TRUE_INTERMEDIATE_COMPLETE` and `PACKAGE_READY`.
- T9 v1.5 replication support and audit.
- T7 Qwen3-Omni Instruct and Captioner staging, CUDA environment recovery,
  bf16 TP4 serving, and ten-clip infrastructure smoke; final status
  `PI_BLOCKED` because human gold is absent.

Primary evidence:

- `sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_REPORT.md`
- `sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_REPORT.md`
- `judge_selfhost_20260709/SELFHOST_JUDGE_REPORT.md`
- `judge_selfhost_20260709/GPU_MEMORY_BEFORE.tsv`
- `judge_selfhost_20260709/GPU_MEMORY_DURING.tsv`
- `heartbeat_an29.log`

## Idle-Gap Accounting

The heartbeat files are periodic snapshots, not scheduler accounting records,
so exact per-GPU busy-hour reconstruction is not defensible. The following gaps
are known:

| Period | Node/GPU | Reason | Recovery action |
|---|---|---|---|
| T7 download and environment build | `an29`, before service launch | Work was network-, disk-, and package-resolution-bound; no model was yet loadable. | Resumable ModelScope staging and a checksum-pinned wheelhouse were executed; the service launched at 19:54 on 2026-07-10. |
| After completion of T2/T9 | `an12`, currently GPUs 4-7 | All claim-bearing, non-human-gated tasks T0-T9 and T11 are complete. T10 is explicitly nonblocking and has no frozen 32-prompt manifest or audited 50-clip smoke launcher in the repository. | No unreviewed 32,768-clip filler run was invented during finalization. The gap is logged here rather than counted as ADSR utilization. |
| Between Qwen requests | `an29`, GPUs 0,2,3,4 | Service is waiting for PI-gold labels. | Service remains ready in tmux; scale calls are fail-closed until calibration passes. |

The current state does not meet a 90% ADSR busy-GPU-hour target. Completed
claim-bearing compute is preserved, but unrelated BlindGain activity cannot be
reported as ADSR progress and human-gated validation cannot be replaced with
unlabeled scale calls.

## Heartbeats

- `paper_prep/heartbeat_an12.log`: active tmux heartbeat, last observed update
  2026-07-10 20:04 Asia/Shanghai.
- `paper_prep/heartbeat_an29.log`: active tmux heartbeat, last observed update
  2026-07-10 20:03 Asia/Shanghai.
- Current sessions: `codex_heartbeat_an12`, `codex_heartbeat_20260708_an12`,
  `codex_heartbeat_an29`, `codex_heartbeat_20260708_an29`, and
  `adsr_qwen_server`.

## Boundary

No process outside the AudioDiffusion repository was stopped, modified, or
counted as ADSR work. No filler generation was launched without the brief's
required frozen manifest, 50-clip smoke, sanity block, and append-only ledger.
