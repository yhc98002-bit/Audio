# Node Saturation Audit 20260708

Generated: 2026-07-08 13:45 CST

NODE_SATURATION_STATUS = ADSR_JOBS_COMPLETED_NO_IDLE_GAP_OVER_30_MIN

## an12

- Node: `an12`, 8 x NVIDIA A800 80GB PCIe.
- ADSR-relevant jobs run in this recovery pass:
  - `sa3_lowstep500_20260708`: SA3 Medium low-step observability proxy, 500 prompts x 2 seeds = 1,000 generated rows.
  - `sa3_demucs_lowstep500_20260708`: Demucs scoring for the 1,000-row low-step proxy.
- Output artifacts:
  - `paper_prep/sao/stable_audio_3_medium/observability/lowstep_full500/SA3_PREVALENCE_LEDGER.jsonl`
  - `paper_prep/sao/stable_audio_3_medium/observability/lowstep_full500/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
  - `paper_prep/sao/stable_audio_3_medium/observability/SA3_OBSERVABILITY_REPORT.md`
- Current status at 13:43 CST: no active ADSR compute process; all GPUs idle after completed ADSR scoring.
- Idle gap greater than 30 minutes: none observed during this recovery pass.
- Non-ADSR GPU jobs currently occupying node: none observed.
- Heartbeat log: `paper_prep/heartbeat_an12.log`.
- Active heartbeat session: `codex_heartbeat_20260708_an12`.

## an29

- Node: `an29`, 8 x NVIDIA A800 80GB PCIe.
- ADSR-relevant jobs run in this recovery pass:
  - `sa3_full500_20260708`: SA3 Medium full prevalence scan. The initial shard 1 saw the manifest before rows were available and exited without rows.
  - `sa3_full500_shard1_recover_20260708`: targeted recovery of the missing full-scan shard 1 rows.
  - `sa3_demucs_full500_20260708`: Demucs scoring for the 4,000-row full scan.
- Output artifacts:
  - `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_LEDGER.jsonl`
  - `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
  - `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_REPORT.md`
- Current status at 13:43 CST: no active ADSR compute process; all GPUs idle after completed ADSR scoring.
- Idle gap greater than 30 minutes: none observed during this recovery pass.
- Non-ADSR GPU jobs currently occupying node: none observed.
- Heartbeat log: `paper_prep/heartbeat_an29.log`.
- Active heartbeat session: `codex_heartbeat_20260708_an29`.

## Utilization Notes

- an29 carried the main SA3 guide-scale prevalence scan from 13:29 to 13:37 CST and full Demucs scoring from 13:38 to 13:41 CST.
- an12 carried the SA3 low-step observability proxy from 13:30 to 13:37 CST and low-step Demucs scoring from 13:38 to 13:39 CST.
- The older heartbeat sessions existed but their logs were stale. Fresh heartbeat sessions were started at 13:44 CST with `paper_prep/scripts/heartbeat_20260708.sh`; the first entries record current GPU, tmux, process, and ledger-count state.
- Remaining full-readiness blockers are A-prime/B-prime human or PI ratings, not GPU compute jobs. No additional ADSR GPU task was queued after 13:41 CST because the requested SA3 download, smoke, full prevalence scan, observability proxy, intervention, and scoring outputs were complete.
