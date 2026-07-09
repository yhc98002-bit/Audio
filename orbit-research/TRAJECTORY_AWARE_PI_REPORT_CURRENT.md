# Trajectory-Aware PI Report

Generated UTC: `2026-06-04T04:29:43Z`
Overall status: `FINAL_READY`
Goal complete: `True`

## Refresh Status

- status: `MISSING`
- GPU jobs launched by refresh: `None`
- commands run by refresh: `None`
- Track A records in refresh snapshot: `None / None`
- completion audit status in refresh snapshot: `None`
- Track C preflight status in refresh snapshot: `None`
- next manual poll after local: `None`

## Completion Evidence

| requirement | status | details |
|---|---|---|
| Track A robust Early-Tweedie validation completed | COMPLETE | run_completed=True; records=4096/4096; launcher_exit=0; outputs_exist=True |
| Track A independent verification passed | COMPLETE | verifier_status=PASS_WITH_WARNINGS; error_count=0 |
| Track A PI decision memo produced | COMPLETE | decision_fields_present=True |
| Track B global-quality structure analysis completed | COMPLETE | json_status=COMPLETE_CPU_ONLY |
| Track C bounded rescue opportunity resolved | COMPLETE | explicit_stop_marker_present=True |
| Hard scientific boundaries preserved | COMPLETE | flags_ok=True; gate_v1_sha256=43a306753583f03563c792ac9399bb1e30b0525c98c902a1e18756d54e25b3c6; gate_v2_draft_exists=True |

## Track A: Early-Tweedie Validation

- run root: `runs/early_tweedie_validation_512_bon8_20260527_full01`
- records: `4096 / 4096`
- completed: `True`
- stall suspected: `False`
- verification status: `PASS_WITH_WARNINGS`
- PI decision status: `STRONG_CANDIDATE_MAIN_APPLICATION`
- active GPU-h elapsed estimate: `1625.434`
- final active GPU-h estimate: `1625.434`
- aggregate finish estimate local: `2026-06-04 12:29:39`
- slowest-shard finish estimate local: `2026-06-04 12:29:39`
- live record check status: `None`
- live record check records: `None`
- live record check record lag: `None`
- live record check fresh: `None`
- live record check complete prompts: `None`
- live record check errors: `None`

Primary robust/common schedule rows:

| schedule | compute_fraction | reward_fraction | winner_match | false_negative | median_regret |
|---|---:|---:|---:|---:|---:|
| full_bon8 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1 | 0.5000 | 0.9864 | 0.5703 | 0.4297 | 0.0000 |
| schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1 | 0.5833 | 0.9913 | 0.6680 | 0.3320 | 0.0000 |
| schedule_c_sigma0.8_keep_top6_final_top1 | 0.8500 | 0.9987 | 0.9434 | 0.0566 | 0.0000 |
| bottom_prune_sigma0.8_remove_bottom25_final_top1 | 0.8500 | 0.9987 | 0.9434 | 0.0566 | 0.0000 |
| bottom_prune_sigma0.7_remove_bottom25_final_top1 | 0.8833 | 0.9998 | 0.9805 | 0.0195 | 0.0000 |
| random_prune_keep4_keep2_final_top1 | 0.5000 | 0.9571 | 0.2509 | 0.7491 | 0.0706 |

Primary robust/common winner-retention rows:

| sigma | top1 | top2 | top4 | bottom25_false_negative |
|---|---:|---:|---:|---:|
| 0.9 | 0.2285 | 0.4121 | 0.6660 | 0.1348 |
| 0.8 | 0.3906 | 0.6094 | 0.8242 | 0.0566 |
| 0.7 | 0.4707 | 0.6797 | 0.9102 | 0.0195 |

## Track B: Global Quality Structure

- status: `COMPLETE_CPU_ONLY`
- classification: `supports_global_persistent_quality`
- cautious claim: For ACE-Step short-form outputs, local-window rewards appear to track persistent global quality more than isolated local failures.
- FixedWin read: `stable_local_proxy_for_global_quality_more_than_true_local_credit`
- primary median between-share: `0.5839`
- primary median between/within ratio: `1.4038`
- primary median crossing frequency: `0.0000`
- primary median globalness index: `0.8613`

## Track C: Bounded RL Rescue

- status: `STOPPED_BY_DECISION`
- resolution: `EXPLICIT_STOP_DECISION`
- run root: `None`
- logs: `None`
- GPU-h consumed: `0.0`
- smoke preflight status: `None`
- smoke preflight blockers: `[]`
- smoke launch plan status: `None`
- smoke launch plan GPU jobs: `None`

## Recommendation

Recommended framing: pivot toward trajectory-aware inference-time selection plus global-quality emergence analysis; keep RL rescue as bounded exploratory evidence.

## Boundary Confirmation

- gate_v1 SHA256: `43a306753583f03563c792ac9399bb1e30b0525c98c902a1e18756d54e25b3c6`
- gate_v2 draft exists: `True`
- full_1000_step_rl_rescue_launched: `False`
- human_eval_launched_by_current_stage: `False`
- phase_d_launched_by_current_stage: `False`
- pruning_rl_launched: `False`
- track_c_gpu_smoke_launched: `False`
- no canonical proposal rewrite is authorized by this report
- no pruning+RL is authorized by this report

## Files To Inspect

- `orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json`
- `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json`
- `orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.md`
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md`
- `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md`
- `orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.md`
