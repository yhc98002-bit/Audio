# Phase C1 Common Eval Status

Date: 2026-05-26
Helper: helper
Status: COMPLETE_FOR_STEP1000_WITH_ROW_ONLY_RECOVERY

## Completed

Built and ran a dev-only common downstream eval for Base plus C1 step1000
checkpoints using one shared sampler and one shared metric stack.

Created:

- `configs/runs/phase_c1_common_downstream_eval.review.yaml`
- `scripts/phase_c1_common_downstream_eval.py`
- `runs/phase_c1_common_downstream_eval_20260526_helper01/common_eval_results.json`
- `runs/phase_c1_common_downstream_eval_20260526_helper01/per_prompt_common_eval.jsonl`
- `runs/phase_c1_common_downstream_eval_20260526_helper01/method_by_checkpoint_summary.csv`
- `runs/phase_c1_common_downstream_eval_20260526_helper01/paired_delta_vs_base.csv`
- `runs/phase_c1_common_downstream_eval_20260526_helper01/paired_delta_method_vs_method.csv`
- `orbit-research/PHASE_C1_COMMON_EVAL_AUDIT_2026-05-26.md`
- `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`

## Final Output Root

`runs/phase_c1_common_downstream_eval_20260526_helper01`

Final row counts:

- `per_prompt_common_eval.jsonl`: 320 rows.
- `method_by_checkpoint_summary.csv`: 5 targets.
- `paired_delta_vs_base.csv`: 4 method rows.
- `paired_delta_method_vs_method.csv`: 6 method-pair rows.

## Metrics

| Target | n | Robust-LCB mean | Delta vs Base |
|---|---:|---:|---:|
| Base | 64 | 2.133676 | 0 |
| R8a step1000 | 64 | 2.145297 | +0.011621 |
| R8b step1000 | 64 | 2.148166 | +0.014490 |
| M-FixedWin step1000 | 64 | 2.145825 | +0.012149 |
| M-Section step1000 | 64 | 2.146055 | +0.012379 |

Process audit:

- M-FixedWin: FixedWin-process -1.677325, Section-process -1.584986.
- M-Section: FixedWin-process -1.704717, Section-process -1.575054.

Interpretation: all methods are slightly above Base on mean paired robust-LCB,
but effect sizes are small and not separable. This supports "no obvious
common-eval degradation" rather than "significant improvement."

## Runtime And Cost

Smoke:

- GPU0.
- 307.347 s.
- 0.085374 GPU-h.

Full step1000:

- GPU0: Base + R8a.
- GPU1: Base + R8b.
- GPU2: Base + M-FixedWin.
- GPU3: Base + M-Section.

Exact full-shard GPU hours were not written because the old shard runner failed
after complete JSONL rows and before shard summary JSON. Lower-bound row-file
active spans sum to 2.240000 GPU-h. Smoke plus this lower bound is 2.325374 GPU-h.
The true cost is slightly higher due pre-first-row model loading.

## Bug And Patch

Bug: the full shards streamed `per_prompt_common_eval.jsonl`, then the aggregate
writer refused to write summaries because that JSONL already existed. The bug did
not corrupt per-prompt rows.

Patch:

- Streaming eval now calls `_write_aggregate_outputs(..., per_prompt_already_written=True)`.
- Existing streamed JSONL must match in-memory row keys before summaries are written.
- Merge-only can recover row-only shards only after strict coverage, policy,
  sampler, duplicate, Base, and safety validation.

Final merged result records `row_only_recovery_used: true` and
`shard_gpu_hours_consumed: null`.

## Claude Review

Claude CLI verdict: `ACCEPT_WITH_NONBLOCKING_NOTES`.

Key review points:

- Implementation and recovery patch match the task.
- No leakage or unfair baseline was found.
- Row-only recovery is acceptable and internally consistent.
- Do not claim significant improvement; deltas are tiny and no significance test
  was run.
- GPU-hour accounting is incomplete and must be reported as such.

Changes from review: no code changes required; final wording was constrained to
avoid overclaiming.

## Not Run

- Checkpoint sweep over step100, nearest-step250, and step500.
- Held-out eval.
- Phase D.
- Human eval.
- Any training or optimizer step.

## Next Recommended Step

If the Researcher needs training-dynamics evidence, run the checkpoint sweep with
the patched script. If the goal is only to screen step1000 before a later decision,
use this result as a no-obvious-degradation audit and wait for explicit approval
before any held-out or Phase D work.
