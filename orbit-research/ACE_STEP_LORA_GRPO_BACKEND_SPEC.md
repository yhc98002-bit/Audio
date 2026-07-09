# ACE-Step LoRA/GRPO Backend Spec

Date: 2026-05-24

## Scope

This spec defines one shared ACE-Step LoRA/GRPO backend for:

- R8a Outcome-GRPO plain;
- R8b Outcome-GRPO guarded;
- M-FixedWin-PRM primary;
- M-Section-PRM diagnostic / negative control.

The backend is an implementation unblocker only. It does not authorize formal
Phase C, held-out, Phase D, human evaluation, BeatWin/LyricSpan PRM, new
ablations, reward-definition changes, sigma-policy changes, prompt-split
changes, credit-unit-definition changes, `gate_v1.yaml` changes, or paper
claim rewrites.

## 1. LoRA Insertion Targets

LoRA is inserted only into the ACE-Step diffusion transformer:

- `pipeline.ace_step_transformer`.

Within that transformer, LoRA targets the attention projection modules used by
`LinearTransformerBlock`:

- self-attention: `attn.to_q`, `attn.to_k`, `attn.to_v`, `attn.to_out.0`;
- cross-attention: `cross_attn.to_q`, `cross_attn.to_k`, `cross_attn.to_v`,
  `cross_attn.to_out.0`;
- added encoder projections when present: `add_q_proj`, `add_k_proj`,
  `add_v_proj`, `to_add_out`.

The implementation target-module suffix list is:

```text
to_q, to_k, to_v, to_out.0, add_q_proj, add_k_proj, add_v_proj, to_add_out
```

No LoRA is inserted into:

- MusicDCAE encoder/decoder;
- vocoder;
- UMT5 text encoder;
- lyric encoder;
- reward models;
- prompt or gate evaluators.

## 2. Trainable and Frozen Parameters

Trainable:

- LoRA adapter parameters attached to the ACE-Step diffusion transformer only.

Frozen:

- all original ACE-Step base transformer parameters;
- all non-transformer ACE-Step modules;
- all reward models;
- all prompt, segmentation, sigma, and gate logic.

The optimizer must be built from adapter parameters only. A smoke must verify:

- at least one adapter parameter is trainable;
- no base parameter has `requires_grad=True`;
- adapter gradients are nonzero after loss backward;
- sampled frozen/base parameter checksums are unchanged after optimizer step.

## 3. Old / Reference / New Policy Semantics

The backend distinguishes three policies:

1. `reference_policy`: the frozen base ACE-Step model with LoRA adapters
   disabled. This is the KL anchor.
2. `old_policy`: the policy used to generate a rollout group. Operationally,
   this is represented by cached rollout-time score/log-ratio terms and, when
   needed, an adapter-state snapshot saved before the optimizer update.
3. `new_policy`: the current ACE-Step model with the active LoRA adapter.
   Gradients flow only through the adapter parameters.

For the first optimizer update of a fresh adapter, `old_policy` and
`new_policy` have identical adapter weights before the update, but they are
still represented separately in logs and checkpoints. `reference_policy`
remains the base model with adapters disabled.

## 4. Rollout Group Construction

Each GRPO update consumes rollout groups:

- group key: prompt id by default;
- group size: from the method config (`group_size`);
- rollout seed: deterministic function of base seed, update step, prompt index,
  and group member index;
- sampling backend: ACE-Step with existing sampler binding;
- trajectory capture: existing scheduler-step hook captures latents, sigmas,
  next sigmas, timesteps, CFG-active flags, and old model outputs.

The backend must not alter prompt splits or prompt order. R8a/R8b use their
configured dev prompts. M-FixedWin/M-Section use the paired Phase C dev prompt
source/order.

## 5. Ratio / Logprob Estimator

ACE-Step sampling in this checkout uses the deterministic public Euler flow
path. The backend therefore must not claim an exact stochastic-policy logprob.

The backend uses a documented Flow-GRPO-style approximate estimator:

1. For each selected trajectory step `k`, take captured latent `z_k`, scheduler
   sigma `sigma_k`, and final generated audio.
2. Encode final generated audio with frozen MusicDCAE to obtain `z_0`.
3. Align `z_0` to the captured latent time length if needed by deterministic
   crop/pad on the latent time axis.
4. Define the detached flow target:

```text
u_k = (z_k - z_0) / max(sigma_k, sigma_floor)
```

5. Evaluate the active adapter policy velocity `v_theta(z_k, sigma_k, cond)`
   by calling `ace_step_transformer.decode` with gradients enabled for adapter
   parameters.
6. Define a Gaussian flow-matching surrogate log density:

```text
logp_theta(k) = - mean((v_theta - u_k)^2) / (2 * ratio_variance)
```

7. Cache `logp_old` at rollout/update construction time under `old_policy`.
8. Compute:

```text
log_ratio = sum_k(logp_new(k) - logp_old(k))
ratio = exp(clamp(log_ratio, -ratio_clip_log, ratio_clip_log))
```

Default step selection:

- if the method config provides sigma checkpoints, select the captured
  trajectory steps nearest those configured sigma targets and assert that the
  selected step indices / actual sigmas match the config provenance;
- otherwise, select all captured rollout steps. This is the R8a/R8b default
  because their terminal backend path is governed by `t_train` / rollout steps
  rather than the Phase C H2 sigma policy.

The selected-step policy is configurable only through backend training config
fields and must be logged. It must not alter Phase C sigma policy.

This is an approximate ODE-to-score/flow-matching surrogate, not exact
trajectory likelihood. It is defensible as a minimal Flow-GRPO-style policy
improvement signal because it compares old/new adapter scores on the same
captured states and detached flow targets, but it omits exact probability-flow
ODE divergence terms and does not model a true stochastic reverse-SDE action
density.

Every run must log:

- `estimator_type = flow_matching_surrogate`;
- `exact_logprob = false`;
- `ratio_variance` (default `1.0`, configurable; temperature for surrogate
  log-ratio scale);
- `sigma_floor` (default `1.0e-5`, used only to avoid division by zero near
  the data endpoint);
- selected sigma/step indices;
- known limitations.

`z_0` length mismatch after frozen MusicDCAE re-encoding is expected to be a
codec/stride rounding artifact. The implementation logs the mismatch in latent
frames; crop/pad alignment is allowed for small mismatches and must be visible
in smoke metrics.

## 6. Terminal Reward Path for R8a/R8b

R8a and R8b use terminal scalar rewards per rollout:

- R8a: terminal robust-LCB reward, no lyric guard, no curriculum.
- R8b: terminal robust-LCB reward plus the existing Lagrangian lyric guard and
  existing optional curriculum behavior.

The backend does not redefine these rewards. It ingests the scalar terminal
reward after the existing reward stack computes it.

For a prompt group with rewards `r_i`, advantages are group-normalized:

```text
A_i = (r_i - mean_group(r)) / (std_group(r) + eps)
```

If group variance is nearly zero, advantages are set to zero and the update is
logged as `zero_advantage_group=true`.

## 7. Process Reward Path for M-FixedWin/M-Section

M-FixedWin and M-Section use the same backend with different credit units:

- M-FixedWin: `fixed_window`;
- M-Section diagnostic: `musical_section`.

The backend does not implement new credit units and does not change existing
definitions. It ingests detached per-segment / per-sigma reward deltas computed
from the existing H2-allowed axis x sigma pairs.

Process advantages are normalized within the configured grouping scope. The
minimal backend supports:

- per-rollout scalar process aggregate, e.g. CVaR over detached segment deltas;
- optional per-step weights that attach process rewards to matching selected
  sigma checkpoints.

For the minimal production backend in this task, process rewards are collapsed
to one detached scalar per rollout before entering the shared advantage API.
Per-step weights may be logged for later extension, but the common API consumes
the collapsed scalar:

```text
compute_group_advantages(process_scalar_rewards, rollout_group_ids, eps)
```

The Phase C configs keep CVaR `alpha=0.30`, `beta=0`, `beta_robust=0.5`, lyric
guard policy, sampler binding, sigma policy, and H2-allowed reward axes
unchanged.

## 8. Advantage Normalization

The backend supports one common advantage API:

```text
compute_group_advantages(rewards, group_ids, eps)
```

This is used for both terminal and process rewards. Reward computation remains
outside the backend; the backend only normalizes detached reward values and
consumes the resulting advantages.

The implementation must log per-update:

- reward mean/std/min/max;
- advantage mean/std/min/max;
- number of zero-variance groups;
- reward mode: `terminal` or `process`;
- method id: R8a/R8b/M-FixedWin/M-Section.

## 9. PPO/GRPO Clipping and KL Monitoring

For each rollout item:

```text
unclipped = ratio * A
clipped = clamp(ratio, 1 - epsilon_clip, 1 + epsilon_clip) * A
policy_loss = -mean(min(unclipped, clipped))
```

The backend logs:

- mean/min/max ratio;
- mean log-ratio;
- clip fraction;
- surrogate KL to old policy:

```text
approx_kl_old = mean(logp_old - logp_new)
```

- KL anchor to frozen reference:

```text
approx_kl_ref = mean(logp_new - logp_ref)
```

The training loss is:

```text
loss = policy_loss + lambda_kl * approx_kl_ref
```

If KL or ratio is nonfinite, the update aborts before optimizer step.

## 10. Lyric Guard and CVaR

Lyric guard remains a reward-side modifier:

- inactive for R8a;
- active for R8b as already configured;
- kept exactly as specified in Phase C configs for M-PRM.

CVaR remains a reward aggregation policy for process rewards. The backend only
consumes the detached scalar or per-step advantages after CVaR aggregation.

## 11. Checkpoint, Resume, and Rollback

Each backend checkpoint includes:

- adapter state dict;
- optimizer state dict;
- update step;
- estimator metadata;
- LoRA target summary;
- trainable/frozen parameter summary;
- RNG state where available;
- last update metrics;
- config hash/provenance;
- safety flags confirming no formal Phase C / held-out / Phase D / human eval.

Resume semantics:

- load adapter state before optimizer state;
- verify target-module list and adapter rank match;
- restore optimizer state;
- continue from `step + 1`;
- write a resume event to the run ledger.

Rollback semantics:

- if a nonfinite loss, ratio, KL, or gradient is detected before optimizer
  step, do not step and keep the previous checkpoint;
- if checkpoint write fails after a step, abort and report the run as unsafe;
- formal runners must keep refusing launch until PI explicitly approves moving
  from smoke to formal training.

## 12. Run Ledger

Every smoke/update writes ledger events with:

- method id;
- backend id;
- reward mode;
- estimator type;
- adapter trainable/frozen summary;
- checkpoint path;
- metrics path;
- safety scope flags.

## 13. Expected Limitations and Assumptions

Known limitations:

- estimator is approximate, not exact logprob;
- deterministic public Euler sampling does not expose a true stochastic action
  distribution;
- probability-flow ODE divergence terms are omitted;
- target velocity uses frozen MusicDCAE re-encoding of final audio and latent
  crop/pad alignment when required;
- old-policy semantics rely on cached rollout-time old scores for an update;
- DDP/formal sharding is out of scope for this task;
- reward-model definitions and H2 sigma policy are not modified to compensate
  for backend limitations.

Assumptions:

- `cfg_type='cfg'`, ERG disabled, and `guidance_interval=0.5` remain the Phase C
  sampler binding;
- ACE-Step trajectory capture remains serial per Python process because the
  current scheduler-step hook is process-global;
- adapter-only optimization is sufficient for the first production backend
  smoke, but formal training still requires PI approval.

## 14. Required Smoke Tests Before Formal Training

Formal training remains blocked until all of the following pass and Claude Code
accepts the implementation audit.

Non-GPU tests:

- existing credit-unit tests;
- backend unit tests;
- config-loading tests;
- freeze/trainable parameter tests.

GPU smoke tests only:

1. LoRA insertion:
   - intended modules receive LoRA;
   - base parameters frozen;
   - adapter parameters trainable.
2. Old/new/reference policy forward:
   - same prompt/seed;
   - old/reference/new forward paths run;
   - ratio/logprob estimator finite.
3. R8a terminal-GRPO smoke:
   - 2 prompts;
   - minimal rollout group;
   - terminal reward;
   - one optimizer update.
   - R8b uses the same backend path plus reward-side lyric guard; R8b backend
     coverage is validated by this terminal smoke plus existing lyric-guard
     reward wiring, without changing reward definitions.
4. M-FixedWin process-GRPO smoke:
   - 2 prompts;
   - FixedWin process reward;
   - one optimizer update.
5. M-Section diagnostic smoke:
   - 2 prompts;
   - Section process reward;
   - one optimizer update.

Smoke pass criteria:

- finite loss;
- finite reward tensors;
- finite ratio/logprob estimator;
- nonzero adapter gradients where expected;
- base parameters unchanged;
- adapter parameters update;
- checkpoint saved;
- checkpoint resume works if cheap;
- no NaN / Inf;
- KL / ratio stats logged.

Passing these smoke tests means the backend can be prepared for PI approval; it
does not authorize formal Phase C, held-out, Phase D, human evaluation, or any
new ablation.
