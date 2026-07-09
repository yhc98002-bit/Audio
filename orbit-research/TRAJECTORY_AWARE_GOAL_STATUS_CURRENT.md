# Trajectory-Aware Goal Current Status

Generated UTC: `2026-06-04T04:29:39Z`

## Track A

- run root: `runs/early_tweedie_validation_512_bon8_20260527_full01`
- records: `4096 / 4096`
- progress fraction: `1.0000`
- launch started UTC: `2026-05-26T17:18:58Z`
- wall elapsed hours: `203.179`
- aggregate records/hour: `20.16`
- aggregate ETA hours: `0.0`
- slowest shard ETA hours: `0.0`
- estimated active GPU-h elapsed: `1625.434`
- estimated remaining active GPU-h by shard rates: `0.0`
- estimated final active GPU-h by shard rates: `1625.434`
- aggregate estimated finish local: `2026-06-04 12:29:39`
- slowest shard estimated finish local: `2026-06-04 12:29:39`
- stall threshold sec: `1800`
- Track A stall suspected: `False`
- stalled shards: `[]`
- recommended manual poll interval sec: `0`
- next manual poll after local: `2026-06-04 12:29:39`
- manual poll guidance: Track A complete: run finalizer now.
- completed: `True`
- launcher.exit: `0`
- launch_finished exists: `True`
- newest write: `2026-05-28 08:08:25`
- age since newest write sec: `620474.5`
- collector processes: `0`
- progress watcher processes: `0`
- finalizer watcher processes: `0`
- finalizer lock exists: `True`
- live record check status: `None`
- live record check records: `None`
- live record check record lag: `None`
- live record check errors: `None`
- live record check warnings: `None`

| shard | records | records/hour | ETA hours | projected total GPU-h | last write age sec | stalled | summary_exists |
|---|---:|---:|---:|---:|---:|---|---|
| shard00 | 512 | 2.52 | 0.0 | 203.179 | 624470.5 | False | True |
| shard01 | 512 | 2.52 | 0.0 | 203.179 | 620894.5 | False | True |
| shard02 | 512 | 2.52 | 0.0 | 203.179 | 621968.5 | False | True |
| shard03 | 512 | 2.52 | 0.0 | 203.179 | 623747.5 | False | True |
| shard04 | 512 | 2.52 | 0.0 | 203.179 | 620474.5 | False | True |
| shard05 | 512 | 2.52 | 0.0 | 203.179 | 621749.5 | False | True |
| shard06 | 512 | 2.52 | 0.0 | 203.179 | 621354.5 | False | True |
| shard07 | 512 | 2.52 | 0.0 | 203.179 | 621708.5 | False | True |

## Deliverables

| key | exists | path |
|---|---|---|
| track_b_global_quality_md | True | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| track_b_global_quality_json | True | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.json` |
| synthesis_draft | False | `orbit-research/TRAJECTORY_AWARE_RESEARCH_SYNTHESIS_DRAFT_2026-05-27.md` |
| boundary_status | False | `orbit-research/TRAJECTORY_AWARE_BOUNDARY_AND_DELIVERABLE_STATUS_2026-05-27.md` |
| track_c_post_track_a_decision_rule | False | `orbit-research/TRACK_C_POST_TRACK_A_DECISION_RULE_2026-05-27.md` |
| track_c_stop_decision_template | False | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION_TEMPLATE.md` |
| track_a_finalize_wrapper | True | `scripts/finalize_early_tweedie_validation.py` |
| track_a_verifier | True | `scripts/verify_early_tweedie_validation.py` |
| track_a_decision_summarizer | True | `scripts/summarize_early_tweedie_decision.py` |
| track_a_live_record_checker | True | `scripts/check_early_tweedie_live_records.py` |
| track_a_live_record_check_md | False | `orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.md` |
| track_a_live_record_check_json | False | `orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.json` |
| track_c_output_summarizer | True | `scripts/summarize_c1_lite_rl_rescue.py` |
| track_c_smoke_preflight | True | `scripts/preflight_c1_lite_rl_rescue_smoke.py` |
| track_c_smoke_preflight_md | False | `orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.md` |
| track_c_smoke_preflight_json | False | `orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json` |
| track_c_smoke_wrapper | True | `scripts/run_c1_lite_rl_rescue_smoke.py` |
| track_c_smoke_launch_plan_md | False | `orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.md` |
| track_c_smoke_launch_plan_json | False | `orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.json` |
| trajectory_refresh_orchestrator | True | `scripts/refresh_trajectory_aware_status.py` |
| trajectory_refresh_status_md | False | `orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.md` |
| trajectory_refresh_status_json | False | `orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.json` |
| trajectory_pi_report_generator | True | `scripts/generate_trajectory_aware_pi_report.py` |
| trajectory_completion_auditor | True | `scripts/audit_trajectory_aware_goal_completion.py` |
| trajectory_completion_audit_md | True | `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md` |
| trajectory_completion_audit_json | True | `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json` |
| trajectory_pi_report_md | True | `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` |
| trajectory_pi_report_json | True | `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.json` |
| track_a_validation_md | True | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` |
| track_a_validation_json | True | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json` |
| track_a_validation_plot_csv | True | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv` |
| track_a_validation_retention_csv | True | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv` |
| track_a_verification_report | True | `orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json` |
| track_a_pi_decision | True | `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` |
| track_c_output_summary_md | False | `orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.md` |
| track_c_output_summary_json | False | `orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.json` |

## Boundary

- gate_v1 SHA256: `43a306753583f03563c792ac9399bb1e30b0525c98c902a1e18756d54e25b3c6`
- gate_v2 draft exists: `True`
- phase_d_launched_by_current_stage: `False`
- human_eval_launched_by_current_stage: `False`
- pruning_rl_launched: `False`
- full_1000_step_rl_rescue_launched: `False`
- track_c_gpu_smoke_launched: `False`

Historical artifact caveat:

Historical held-out artifacts exist in this checkout; they are not evidence of a new held-out launch during the current trajectory-aware stage.

## Next Action

Run `python scripts/finalize_early_tweedie_validation.py`.
