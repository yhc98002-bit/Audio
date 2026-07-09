# Phase C1 Training Dynamics Audit

Run root: `runs/phase_c1_firstwave_20260524_researcher_go_01`

Scope: CPU-only audit of completed training logs, `train_results.json`, backend ledgers, checkpoints, and the GRPO runner/backend code. No training, evaluation, held-out, Phase D, human eval, pruning+RL, Early-Tweedie resume, or config/reward/sigma/prompt/credit-unit/gate edits were performed.

## Outputs

- `orbit-research/phase_c1_training_dynamics_audit_20260526/ratio_kl_summary.csv`
- `orbit-research/phase_c1_training_dynamics_audit_20260526/reward_window_summary.csv`
- `orbit-research/phase_c1_training_dynamics_audit_20260526/adapter_checkpoint_summary.csv`

## Executive Read

- Completion health remains clean: all four methods have `status=PASS`, `steps_completed=1000`, ten checkpoint events/files, finite JSON logs, and no recorded held-out/Phase D/human-eval launches.
- Base-model safety evidence is positive: every optimizer-step log records `frozen_parameters.unchanged=true` with no changed names, every result has `base_parameters_frozen=true`, and checkpoint payload parameter summaries also report base parameters frozen.
- Adapter movement is recoverable from checkpoints: checkpoint digests change at every checkpoint interval and the step-1000 checkpoint digest matches each method's `final_adapter_digest`. Initial adapter norm is not recoverable because no step-0 adapter checkpoint was saved; only `initial_adapter_digest` is available in `train_results.json`.
- `ratio_mean=1`, `ratio_std=0`, and `log_ratio=0` throughout are expected for this implementation's logging point: `cache_old_and_ref_logps()` caches old logps immediately before `update()`, and `update()` logs `new_logp` before `optimizer.step()` on the same parameters. This does not prove no learning, but it does mean ratio/log-ratio logs are not useful post-update movement diagnostics here.
- Reward curves are noisy on-policy training traces over changing prompts/seeds. They do not provide held-out quality evidence. Descriptively, none of the four methods shows a clean monotonic reward increase; terminal methods show increasing KL_ref magnitude while process methods stay near zero KL_ref.

## Method Summary

| method | reward mode | status | steps | GPU-h | first100 reward | last100 reward | last-first | min group reward std | zero-var groups | max abs KL_ref | final KL_ref | adapter L2 100 -> 1000 | final digest ok | base unchanged |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| R8a | terminal | PASS | 1000 | 37.7902 | 0.477921 | 0.385888 | -0.0920326 | 0.0885056 | 0 | 0.103004 | -0.0284026 | 39.1906 -> 39.2212 | True | True |
| R8b | terminal | PASS | 1000 | 41.1546 | 0.687829 | 0.634345 | -0.0534835 | 0.0597587 | 0 | 0.102728 | -0.029579 | 39.1907 -> 39.2216 | True | True |
| M-FixedWin | process | PASS | 1000 | 21.3986 | -1.70256 | -1.7257 | -0.023145 | 0.124213 | 0 | 0.00507018 | 6.63926e-05 | 39.1929 -> 39.1936 | True | True |
| M-Section | process | PASS | 1000 | 19.4068 | -1.57442 | -1.60672 | -0.0323047 | 0.0991594 | 0 | 0.00180236 | -7.25389e-05 | 39.1931 -> 39.1932 | True | True |

## Ratio / KL Interpretation

Code path checked: `scripts/phase_c1_grpo.py` calls `old_ref = backend.cache_old_and_ref_logps(rollouts)` immediately before `update_metrics = backend.update(rollouts)`. In `src/mprm/training/ace_lora_grpo.py`, `update()` recomputes rollout logp for the current policy before `optimizer.step()`, then logs `log_ratio = new_logp - old_logps`, `ratio = exp(clamped log_ratio)`, and `approx_kl_old = old_logps - new_logp`. Because old and new are evaluated at the same pre-step parameters, the logged ratio/log-ratio are exactly the pre-update PPO ratio, not a post-update ratio.

| method | ratio mean range | max ratio std | max abs log-ratio | max abs KL_old | max abs KL_ref | final KL_ref | clip frac max | exact_logprob all false |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| R8a | 1-1 | 0 | 0 | 0 | 0.103004 | -0.0284026 | 0 | True |
| R8b | 1-1 | 0 | 0 | 0 | 0.102728 | -0.029579 | 0 | True |
| M-FixedWin | 1-1 | 0 | 0 | 0 | 0.00507018 | 6.63926e-05 | 0 | True |
| M-Section | 1-1 | 0 | 0 | 0 | 0.00180236 | -7.25389e-05 | 0 | True |

Interpretation: ratio/log-ratio constancy is expected logging behavior for the flow-matching surrogate backend with `exact_logprob=false`. It is a weak diagnostic for training dynamics in this run. KL_ref is more informative for drift from the adapter-disabled reference, but it is still an on-policy surrogate quantity, not a quality metric. All max absolute KL_ref values stayed far below the configured abort threshold of `5.0`.

## Adapter Checkpoint Dynamics

| method | checkpoints | digest changed each interval | step100 L2 | step1000 L2 | last interval delta L2 | step1000 digest matches final | initial norm availability |
|---|---:|---|---:|---:|---:|---|---|
| R8a | 10 | True | 39.1906 | 39.2212 | 0.17543 | True | unavailable; no step-0 checkpoint |
| R8b | 10 | True | 39.1907 | 39.2216 | 0.181967 | True | unavailable; no step-0 checkpoint |
| M-FixedWin | 10 | True | 39.1929 | 39.1936 | 0.0591364 | True | unavailable; no step-0 checkpoint |
| M-Section | 10 | True | 39.1931 | 39.1932 | 0.0547534 | True | unavailable; no step-0 checkpoint |

The checkpoint payloads include adapter tensors and optimizer state, so checkpoint-to-checkpoint adapter norm/digest movement is recoverable. They do not include the initial adapter tensor state before training, so initial adapter norm cannot be reconstructed from saved artifacts. `train_results.json` does preserve initial and final adapter digests, and the final digest is consistent with the step-1000 checkpoint.

Process-method adapter movement is much smaller than terminal-method movement in these checkpoint norms: terminal methods move from about `39.191` at step 100 to `39.221` at step 1000, while process methods remain around `39.193`. This is consistent with their much smaller KL_ref magnitudes, but it should be treated as a training-dynamics observation only, not as a quality conclusion or a learning-rate decision without downstream evidence.

## Reward Curves

Terminal and process reward scales are kept separate below. These are training-time on-policy rewards over changing prompts/seeds; they support dynamics triage only, not final model-quality claims.

| method | mode | 0-249 mean | 250-499 mean | 500-749 mean | 750-999 mean | first100 | last100 | descriptive read |
|---|---|---:|---:|---:|---:|---:|---:|---|
| R8a | terminal | 0.396434 | 0.269023 | 0.263966 | 0.31216 | 0.477921 | 0.385888 | no monotonic terminal-reward gain; KL_ref magnitude grows late |
| R8b | terminal | 0.637427 | 0.541614 | 0.514481 | 0.593859 | 0.687829 | 0.634345 | no monotonic terminal-reward gain; KL_ref magnitude grows late |
| M-FixedWin | process | -1.71042 | -1.71181 | -1.70586 | -1.73386 | -1.70256 | -1.7257 | process reward remains negative and noisy; no reward-collapse signal |
| M-Section | process | -1.6013 | -1.62008 | -1.60665 | -1.62002 | -1.57442 | -1.60672 | process reward remains negative and noisy; no reward-collapse signal |

Reward-collapse checks are clean: minimum logged group reward std is above `1e-8` for every method, and logged zero-variance GRPO groups are zero. Overtraining cannot be concluded from these logs alone. The strongest caution is terminal-method KL_ref drift plus absence of monotonic training reward gains, which argues for downstream evaluation before any quality claim.

## Base / Safety Evidence

| method | base frozen result | base unchanged all logs | changed base names | adapter updated all logs | held-out | Phase D | human eval | reward/sigma/prompt/credit changed | gate_v1 touched |
|---|---|---|---|---|---|---|---|---|---|
| R8a | True | True | none | True | False | False | False | False | False |
| R8b | True | True | none | True | False | False | False | False | False |
| M-FixedWin | True | True | none | True | False | False | False | False | False |
| M-Section | True | True | none | True | False | False | False | False | False |

## Unavailable / Limitations

- No step-0 adapter checkpoint exists, so initial adapter norm and initial-to-step100 tensor delta are unavailable; only initial digest from `train_results.json` is available.
- Ratio/log-ratio logging is pre-update and therefore cannot diagnose post-update PPO ratio movement.
- Training reward curves are on-policy and prompt/sample dependent. They do not replace common downstream eval and should not be interpreted as held-out performance.
- No cross-mode scalar reward comparison is made between terminal and process rewards.

## Future Instrumentation Notes

- For future runs, save an initial adapter checkpoint before the first optimizer step if initial-to-step100 tensor deltas are needed.
- If post-update ratio movement is needed, add an explicit post-`optimizer.step()` diagnostic logp pass. The current ratio/log-ratio metrics are intentionally pre-update and are therefore trivial under the current single-update flow.

## Commands Used

- Read payload and verified SHA256 with `sha256sum` and `sed`.
- Inspected existing run artifacts with bounded `find`, `sed`, `grep`, and Python JSON readers.
- Inspected `scripts/phase_c1_grpo.py`, `src/mprm/training/ace_lora_grpo.py`, and `scripts/analyze_phase_c1_completion.py`.
- Generated these audit files with CPU-only Python in the `audio-prm` conda environment using `torch.load(..., map_location="cpu")` for checkpoints.

## Claude Audit

Claude Code was invoked with the required CLI protocol:

```bash
claude -p --dangerously-skip-permissions --output-format json --model opus --effort max "<prompt>"
```

Verdict: `ACCEPT_WITH_NOTES`.

Main notes:

- Ratio/logprob interpretation is correct: `cache_old_and_ref_logps()` and the `new_logp` computation inside `update()` both evaluate the same pre-step parameters; `optimizer.step()` is the first parameter mutation, so logged ratio/log-ratio are expected to be `1/0`.
- Training-dynamics conclusions are appropriately cautious and do not make quality claims.
- Base-unchanged evidence is valid across optimizer-step digest checks, frozen non-adapter parameters, and checkpoint parameter summaries.
- No held-out/Phase D/human eval/config/reward/sigma/prompt/credit-unit/gate changes are implied.
- No cross-mode scalar reward comparison is made.

Required changes: none.

Changes after review:

- Added a note that process-method adapter movement is much smaller than terminal-method movement and should be treated as a dynamics observation only.
- Added future instrumentation notes for step-0 checkpoints and post-update ratio diagnostics.
