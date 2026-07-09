# Node Saturation Audit

Generated: 2026-07-07

## Heartbeats

- `paper_prep/heartbeat_an12.log`
- `paper_prep/heartbeat_an29.log`

Persistent heartbeat tmux sessions were started:

- `codex_heartbeat_an12`
- `codex_heartbeat_an29`

The heartbeat logs include timestamp, node, `nvidia-smi`, tmux sessions, Python
processes, ledger line counts, and current job status.

## an12

Current snapshot at 2026-07-08T05:49:11+08:00:

- GPUs 0-1: high memory use by a non-ADSR `BlindGain` Ray/VERL job.
- GPUs 2-7: saturated by `BlindGain` `scripts/gpu_profile.py --seconds 900`.
- Heartbeat session: `codex_heartbeat_an12`.

Recovery-period notes:

- Earlier heartbeats show long pre-existing idle gaps before this aggressive
  recovery pass.
- During this pass, an12 was occupied at different times by Qwen-VL/FlipTrack,
  GPU profile jobs, and later BlindGain/Ray work not launched by this ADSR
  recovery script.
- I did not kill unknown/non-ADSR jobs.

## an29

Current snapshot at 2026-07-08T05:49:11+08:00:

- GPUs 0-7: saturated by non-ADSR `BlindGain` `scripts/gpu_profile.py --seconds 900`.
- Heartbeat session: `codex_heartbeat_an29`.

Recovery-period notes:

- SAO package/environment work was executed from login and smoke was attempted on
  an29.
- SAO smoke failed because an29 cannot resolve Hugging Face and login-node
  prefetch failed with Hugging Face gated-repo 401.
- After SAO failed, I inspected the atlas backlog. I did not dispatch the old
  large-N atlas extension because prior `ext512` logs and `STATUS_DAILY.md`
  document tag reuse / duplicate-ledger risk. Launching without a new seed/tag
  plan risked corrupting frozen atlas evidence.
- Current an29 utilization is from non-ADSR GPU profile work, not from SAO.

## Dispatch Log

Backlog dispatch decision is recorded in:

- `paper_prep/execution_20260707/AGGRESSIVE_RECOVERY_LEDGER.md`

No ADSR generation backlog was launched after SAO failed because the only
available candidate was not dedup-safe without a new seed/tag plan. This is a
data-integrity exception, not an environment-purity block.
