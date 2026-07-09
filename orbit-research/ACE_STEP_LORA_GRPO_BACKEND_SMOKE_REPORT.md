# ACE-Step LoRA/GRPO Backend Smoke Report

Date: 2026-05-24 (Asia/Shanghai)

## Scope

Implemented and smoke-tested the minimal shared ACE-Step LoRA/GRPO backend from:

- `orbit-research/ACE_STEP_LORA_GRPO_BACKEND_SPEC.md`

This task did not launch formal Phase C, held-out, Phase D, human evaluation,
BeatWin/LyricSpan PRM, extra ablations, or paper rewrites.

## Backend Code

- `src/mprm/training/ace_lora_grpo.py`
- `src/mprm/training/__init__.py`
- `scripts/ace_lora_grpo_backend_smoke.py`
- `tests/test_ace_lora_grpo_backend.py`

The formal launch guards remain closed. Phase C configs still have
`production_weight_update_status: not_ready`; `launch_baseline.py --mode
production` still blocks R8a/R8b formal launches pending PI approval.

## Estimator

- Estimator type: `flow_matching_surrogate`
- Exact logprob: `false`
- Default `ratio_variance`: `1.0`
- Default `sigma_floor`: `1.0e-5`

The estimator uses captured ACE-Step trajectory latents, frozen MusicDCAE
re-encoding of final audio as `z_0`, detached flow target
`u_k = (z_k - z_0) / max(sigma_k, sigma_floor)`, and a Gaussian
flow-matching surrogate log density over adapter-policy velocities. It is not
an exact stochastic-policy logprob and omits probability-flow divergence terms.

## LoRA Summary

Smoke rank: 2.

Target module suffixes:

```text
to_q, to_k, to_v, to_out.0, add_q_proj, add_k_proj, add_v_proj, to_add_out
```

Observed insertion summary:

- LoRA module count: 288
- Trainable adapter params: 2,949,120
- Frozen/base params: 3,847,338,204
- Trainable tensors: 576
- Adapter tensors: 576
- Base parameters frozen: true

## Non-GPU Tests

Command:

```bash
PYTHONPATH=src pytest -q tests/test_credit_units.py tests/test_ace_lora_grpo_backend.py tests/test_run_ledger.py
```

Result: PASS, 38 tests.

Additional checks:

- `python -m py_compile src/mprm/training/ace_lora_grpo.py scripts/ace_lora_grpo_backend_smoke.py tests/test_ace_lora_grpo_backend.py`: PASS
- Phase C pairing audit: PASS

## GPU Smoke Results

All GPU smokes used `CUDA_VISIBLE_DEVICES=0`, LoRA rank 2, and wrote under
`runs/ace_lora_grpo_backend_smoke`.

| Smoke | Status | Reward source | Loss | Grad norm | Adapter update | Base unchanged | Resume | GPU-h |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| LoRA insertion | PASS | n/a | n/a | n/a | n/a | true | n/a | n/a |
| old/new/reference forward | PASS | smoke terminal scalar | 0.000000119 | 0.039401 | true | true | true | 0.007655 |
| R8a terminal-GRPO | PASS | smoke terminal scalar | 0.000000119 | 0.045257 | true | true | true | 0.006525 |
| M-FixedWin process-GRPO | PASS | Phase C H2-allowed process reward stack | 0.000000119 | 0.215642 | true | true | true | 0.069098 |
| M-Section process-GRPO | PASS | Phase C H2-allowed process reward stack | 0.000000119 | 0.177414 | true | true | true | 0.012640 |

Notes:

- R8a terminal smoke uses a smoke-only finite terminal scalar to verify backend
  trajectory, ratio, loss, gradient, optimizer, checkpoint, and resume behavior.
  It does not claim to validate final R8a robust-LCB reward quality.
- M-FixedWin and M-Section process smokes use the existing Phase C H2-allowed
  reward stack and existing credit-unit implementations.
- Ratio is exactly 1.0 before the first adapter update because old and new
  adapter weights are identical at rollout construction. Adapter gradients are
  still nonzero under the surrogate objective, and adapter digests change after
  optimizer step.

## Smoke Artifacts

- `runs/ace_lora_grpo_backend_smoke/lora_insertion/smoke_results.json`
- `runs/ace_lora_grpo_backend_smoke/old_new_policy_forward/smoke_results.json`
- `runs/ace_lora_grpo_backend_smoke/r8a_terminal_grpo/smoke_results.json`
- `runs/ace_lora_grpo_backend_smoke/m_fixedwin_process_grpo/smoke_results.json`
- `runs/ace_lora_grpo_backend_smoke/m_section_process_grpo/smoke_results.json`

## Boundary Confirmation

- `configs/eval/gate_v1.yaml` untouched.
- Reward definitions unchanged.
- Sigma policy unchanged.
- Prompt splits unchanged.
- Credit-unit definitions unchanged.
- No formal Phase C launched.
- No held-out launched.
- No Phase D launched.
- No human evaluation launched.
- No BeatWin/LyricSpan PRM launched.

## Remaining PI Decision

The backend smoke path is implemented and passes. Formal launch remains guarded
until PI decides whether to:

1. approve a bounded formal R8a/R8b training smoke using the same backend;
2. approve M-FixedWin/M-Section first-wave preparation with this backend;
3. hold for more review, especially around the approximate ratio estimator and
   R8a real terminal robust-LCB smoke coverage.
