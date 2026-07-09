# Phase C1 Checkpoint Triage Eval

Generated: 2026-05-26

## Verdict

`NO_CHECKPOINT_SWEEP_EXPANSION_WARRANTED`

The small common eval ran on 16 dev prompts for Base plus step100, nearest-step250
(`actual_step=200`), step500, and step1000 checkpoints for all four C1 methods.
All shards completed with `exit=0` and merged successfully.

No earlier checkpoint shows a meaningful advantage over step1000 or Base. Some
checkpoint means are slightly above Base, but the effects are small relative to
paired variation. This does not justify expanding any checkpoint subset to full
64 prompts.

## Outputs

Output root:

`runs/phase_c1_checkpoint_triage_eval_20260526`

Key files:

- `runs/phase_c1_checkpoint_triage_eval_20260526/common_eval_results.json`
- `runs/phase_c1_checkpoint_triage_eval_20260526/per_prompt_common_eval.jsonl`
- `runs/phase_c1_checkpoint_triage_eval_20260526/method_by_checkpoint_summary.csv`
- `runs/phase_c1_checkpoint_triage_eval_20260526/paired_delta_vs_base.csv`
- `runs/phase_c1_checkpoint_triage_eval_20260526/paired_delta_method_vs_method.csv`

Shard roots:

- `runs/phase_c1_checkpoint_triage_eval_20260526_shards/r8a_16`
- `runs/phase_c1_checkpoint_triage_eval_20260526_shards/r8b_16`
- `runs/phase_c1_checkpoint_triage_eval_20260526_shards/m_fixedwin_16`
- `runs/phase_c1_checkpoint_triage_eval_20260526_shards/m_section_16`

## Scope

- Split: dev only.
- Prompt count: 16.
- Shared sampler: Phase B/C 30-step binding.
- Shared metric: read-only `configs/eval/gate_v2.yaml.draft` robust-LCB policy.
- Targets: Base plus 4 checkpoints for each of R8a, R8b, M-FixedWin, M-Section.
- No training, optimizer step, held-out, Phase D, human eval, gate activation, or
  reward/sigma/prompt/credit-unit definition change.

Merged result:

- `status`: PASS
- `n_prompts`: 16
- `n_targets`: 17
- `shard_gpu_hours_consumed`: 5.361239
- `boundary_flags`: all false

## Common Robust-LCB Means

| Method | step100 | nearest-step250 (actual 200) | step500 | step1000 |
|---|---:|---:|---:|---:|
| R8a | 2.222605 | 2.216840 | 2.222174 | 2.225455 |
| R8b | 2.214896 | 2.212001 | 2.231049 | 2.231321 |
| M-FixedWin | 2.233622 | 2.232004 | 2.212979 | 2.223235 |
| M-Section | 2.209318 | 2.217376 | 2.212455 | 2.229515 |

Base mean on the same 16 prompts: 2.200010.

## Paired Delta Versus Base

| Method | step100 | nearest-step250 | step500 | step1000 |
|---|---:|---:|---:|---:|
| R8a | +0.022594 | +0.016830 | +0.022164 | +0.025444 |
| R8b | +0.014885 | +0.011990 | +0.031039 | +0.031310 |
| M-FixedWin | +0.033611 | +0.031994 | +0.012968 | +0.023224 |
| M-Section | +0.009307 | +0.017366 | +0.012445 | +0.029505 |

All deltas are small. They are consistent with the completed step1000 common dev
eval interpretation: no obvious degradation versus Base, but no clear quality
improvement claim.

## Paired Delta Versus Step1000

| Method | step100 - step1000 | nearest-step250 - step1000 | step500 - step1000 |
|---|---:|---:|---:|
| R8a | -0.002850, std 0.040594 | -0.008615, std 0.055925 | -0.003280, std 0.044451 |
| R8b | -0.016425, std 0.040340 | -0.019320, std 0.034093 | -0.000272, std 0.027980 |
| M-FixedWin | +0.010387, std 0.040543 | +0.008770, std 0.028595 | -0.010256, std 0.071596 |
| M-Section | -0.020197, std 0.033446 | -0.012139, std 0.041690 | -0.017060, std 0.038527 |

M-FixedWin step100 and nearest-step250 are numerically above M-FixedWin step1000
by about 0.009-0.010 robust-LCB, but this is much smaller than the paired
standard deviation. It is not a meaningful checkpoint advantage.

## Decision

Do not expand to full 64 for any checkpoint subset.

Rationale:

- No checkpoint has a robust paired advantage over step1000.
- No checkpoint has a large enough delta versus Base to overcome the completed
  common dev interpretation of `COMMON_DEV_NO_CLEAR_WIN`.
- A full checkpoint sweep would mostly add cost without changing the decision.

## Recommendation

Stop checkpoint-sweep evaluation here. Use the triage as evidence that step1000
is not obviously overtrained relative to earlier checkpoints, but also not a
clear winner. Further Phase C progress should focus on learning-signal/backend
sensitivity or a PI-authorized held-out decision, not automatic sweep expansion.
