# Project: ADSR for Flow-Matching Music Generation

Music-generation research project whose frozen ADSR evidence uses ACE-Step v1.
ACE-Step v1.5 is a bounded replication target, and Stable Audio 3 Medium is the
executed cross-backbone pilot. Stable Audio Open 1.0 remains a legacy adapter,
not the model used by the SA3 pilot.

ADSR means **Axis-Deferred Speculative Restart**: allocate inference compute via
RESTART / DEFER / CONTINUE. Restart terminates a low-promise trajectory and
launches a new independent seed. It is not rollback, repair, RL post-training,
or fixed-pool prune-and-select. Raw Early-Tweedie pruning is now a baseline;
M-PRM / section credit / RL evidence is boundary context.

## Current State

```yaml
stage: publication_code_review_recovery
proposal_status: PI_AUTHORIZED_JUNE_PROGRAM_AND_RESULTS
adsr_final_plan: ADSR_Research_Plan_FINAL_EN_2026-05-29.md
authoritative_results_index: orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md
publication_recovery_report: orbit-research/adsr_phase2_20260604/paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md
retry_study_logs: batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/
canonical_index: orbit-research/CURRENT_CANONICAL_FILES.md
run_ledger: orbit-research/RUN_LEDGER.jsonl
last_updated: "2026-07-09"
```

PI authorization note, 2026-07-06:

- PI has reviewed and authorized the June ADSR program and its results.
- The old "awaiting STOP-A approval" state is superseded.
- The current authoritative results index is
  `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` plus the retry-study
  logs under `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/`.
- New downstream work still requires the approvals and frozen-file constraints below.

## Foundation Evidence

Short context only; detailed evidence lives in the references below.

- ACE-Step has headroom; high/low trajectories separate early.
- H2 verdict: `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`.
- Raw ETP baseline: `0.9864` reward_fraction at `0.500` compute; sigma0.7
  bottom-prune false-negative `0.0195`.
- Lyric axis is English vocal only: `0.682`, n=282.
- Global quality: median globalness `0.861`, sign consistency `1.000`.
- RL first wave is boundary evidence: clean run, no clear common dev winner.

## Active Next Step

Close the code-review recovery brief without changing frozen evidence. Stage 3,
N2, and the SA3 pilot are complete. `an12` is assigned to the bounded ACE-Step
v1.5 replication; `an29` is assigned to ADSR detector/calibration audits and
SA3 follow-up. `an17` is no longer allocated and must not be targeted.

## Hard Boundaries

Do not launch without explicit PI approval: Phase D; human evaluation including
E2 / E8 listening sessions; pruning+RL; additional full RL training;
BeatWin/LyricSpan PRM expansion; EVPD training; ADSR real-generation;
canonical proposal rewrite beyond the approved ADSR reframe.

Do not modify: `configs/eval/gate_v1.yaml`, `runs/**`, `_pi_review_pkg/**`,
listening packets or tarballs, calibration/parity/gate evidence files,
`orbit-research/trajectory_candidate_dataset.jsonl`, or
`orbit-research/archive/etv_pre_adsr_20260604/`.

`configs/eval/gate_v2.yaml.draft` remains a draft. Do not activate it by
renaming.

## Environment

```bash
module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
```

## Essential References

Core entrypoints: `orbit-research/CURRENT_CANONICAL_FILES.md`,
`orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md`,
`orbit-research/adsr_phase2_20260604/paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md`,
`orbit-research/adsr_phase2_20260604/paper_prep/GATE_B_SUPERSESSION_NOTE_20260709.md`,
`ADSR_Research_Plan_FINAL_EN_2026-05-29.md`, `experiment_plan_current.md`,
`refine-logs/ADSR_REFRAME_BRIEF.md`, `refine-logs/FINAL_PROPOSAL.md`,
`refine-logs/METHOD_SPEC.md`, `refine-logs/EXPERIMENT_PLAN_EXEC.md`,
`refine-logs/EXPERIMENT_PLAN.md`, and `orbit-research/PROPOSAL_REVISE_STATE.json`.

<!-- ORBIT:BEGIN -->
## ORBIT Skill Scope
ORBIT skills installed in this project: 73 entries.
Manifest: `.aris/installed-skills.txt`.
For ORBIT workflows, prefer project-local skills under `.claude/skills/` over global skills.
Do not modify or delete files under the ORBIT skill target.
<!-- ORBIT:END -->

## Claude Code CLI Review And Help

do Not call claude in codex
