# Tweedie / Clean-Target Derivation Note — ACE-Step

> **Status (2026-05-23): RESOLVED for ACE-Step clean-target formula.** The original
> STOP-B-4 pre-flight note was ambiguous because it was written before direct source
> inspection and captured-v parity. STOP-B-9 plus Phase B.1 resolved the formula path:
> use `x_hat_0 = x_sigma - sigma * v_out` with branch-aware captured/effective velocity.
> See the canonical `STATUS: RESOLVED` line and scope note at the end of this file.

> **Historical note.** Early sections preserve the 2026-05-15 reasoning and uncertainty
> for audit trail. Later sections (§8 onward) supersede that uncertainty with installed
> ACE-Step source evidence, captured-v parity, and Phase B.1 reliability evidence.

---

## 1. ACE-Step version under derivation

- **Repository.** `ace-step/ACE-Step` (https://github.com/ace-step/ACE-Step).
- **Commit SHA.** _NOT VERIFIED_ — this environment has no clone of the repo; WebFetch
  was on `main` branch. Next-bridge: pin to a specific SHA and re-derive.
- **Python package import path.** _NOT INSTALLED in this env._ Expected at
  `<venv>/lib/python3.x/site-packages/acestep/` once installed.
- **Inference entry point.** `acestep/pipeline_ace_step.py`,
  `text2music_diffusion_process()` (per WebFetch).
- **Paper reference.** Gong et al., "ACE-Step: A Step Towards Music Generation Foundation
  Model", arXiv:2506.00045 (May 2025). §3.3.1 "Flow Matching Loss" (page 7) is the
  authoritative mathematical statement of the prediction target + interpolation.

## 2. Flow target

> What does `v_θ` (called `noise_pred_src` / `.sample` in the source) predict?

**Paper §3.3.1, page 7, verbatim:**

> "The model ε_θ, conditioned on x_noisy, the sampled time t, and various embeddings (text,
> speaker, lyric, denoted collectively as condition), is trained to predict a vector v_out.
> The target for this predicted vector v_out is **−(x₀ − z)**. This target can be
> interpreted as the **negative of the constant velocity field v = x₀ − z** associated with
> the linear path from z to x₀."

**Source quote (verbatim from installed `acestep/pipeline_ace_step.py`, audit-round update 2026-05-22). Lines 503–513 (transformer call in `calc_v`):**

```python
        noise_pred_src = self.ace_step_transformer(
            hidden_states=src_latent_model_input,
            attention_mask=attention_mask,
            encoder_text_hidden_states=encoder_text_hidden_states,
            text_attention_mask=text_attention_mask,
            speaker_embeds=speaker_embds,
            lyric_token_idx=lyric_token_ids,
            lyric_mask=lyric_mask,
            timestep=timestep,
        ).sample
```

**Verbatim from `acestep/pipeline_ace_step.py` lines 1232–1242 (main inference loop):**

```python
                noise_pred_with_cond = self.ace_step_transformer.decode(
                    hidden_states=latent_model_input,
                    attention_mask=attention_mask,
                    encoder_hidden_states=encoder_hidden_states,
                    encoder_hidden_mask=encoder_hidden_mask,
                    output_length=output_length,
                    timestep=timestep,
                ).sample
```

The variable is *named* `noise_pred` (a legacy naming from diffusion-training pipelines),
but the **target trained against** is `−(x₀ − z)`, i.e., the velocity along the σ axis.

**Conclusion.** The model predicts **velocity along the σ axis**, specifically the field
`v_out = z − x₀`. The naming `noise_pred` / `ε_θ` is misleading; the *semantics* are
velocity, not noise. This is corroborated by the scheduler step rule (§3 below):
`prev_sample = sample + (sigma_next − sigma) · model_output` is the standard Euler step
for `dx/dσ = v_out`.

## 3. Time convention

> Does `σ ∈ [0, 1]` indicate noise→data or data→noise? Are inference timesteps stored as
> an increasing array or a decreasing one? Does the model receive σ or a rescaled τ?

**Source quote (verbatim from installed `acestep/schedulers/scheduling_flow_match_euler_discrete.py`, audit-round update 2026-05-22).**

Lines 199–217 (`set_timesteps`, sigmas normalization + shift application):

```python
            timesteps = np.linspace(
                self._sigma_to_t(self.sigma_max),
                self._sigma_to_t(self.sigma_min),
                num_inference_steps,
            )

            sigmas = timesteps / self.config.num_train_timesteps

        if self.config.use_dynamic_shifting:
            sigmas = self.time_shift(mu, 1.0, sigmas)
        else:
            sigmas = self.config.shift * sigmas / (1 + (self.config.shift - 1) * sigmas)

        sigmas = torch.from_numpy(sigmas).to(dtype=torch.float32, device=device)
        timesteps = sigmas * self.config.num_train_timesteps

        self.timesteps = timesteps.to(device=device)
        self.sigmas = torch.cat([sigmas, torch.zeros(1, device=sigmas.device)])
```

Lines 165–174 (`scale_noise` forward process — confirms σ=0 data / σ=1 noise convention):

```python
        sigma = sigmas[step_indices].flatten()
        while len(sigma.shape) < len(sample.shape):
            sigma = sigma.unsqueeze(-1)

        sample = sigma * noise + (1.0 - sigma) * sample

        return sample
```

The pipeline's `__call__` (lines 595–605 + 875–880) creates the scheduler with
`FlowMatchEulerDiscreteScheduler(num_train_timesteps=1000, shift=3.0)`, so the
shift value is **hard-coded** at construction time (not user-configurable through
the public `__call__` API).

**Conclusion.**
- **σ = 0 is data**, **σ = 1 is noise** (opposite of the rectified-flow convention I
  initially assumed in `src/mprm/inference/interface.py:tweedie_clean`).
- Inference loop walks σ **DECREASING** (from σ_max ≈ 1 toward 0).
- The model receives the **scaled timestep** as input — an integer-valued float in
  `[1, 1000]` (= σ × 1000), not σ ∈ [0, 1] directly.
- The `shift=3.0` schedule means σ is a *non-linear* function of normalized step index;
  passing a uniform `τ ∈ {0.7, 0.5, 0.3, 0.1}` in the d3 sanity script does **not**
  correspond to evenly-spaced σ values in the actual schedule.

## 4. Latent scaling

**Paper §3.2.1, page 5, verbatim:**

> "An initial configuration using 32x compression in both time and frequency dimensions
> (f32c32, channel=32) resulted in unacceptable audio quality degradation. We subsequently
> adopted an 8x compression setting (f8c8, channel=8), yielding approximately **10.77 Hz
> temporal resolution in the latent space**, which provided a superior balance between
> compression ratio and fidelity."

**Conclusion.**
- DCAE: 8× compression in both time and frequency, 8 channels.
- **Latent temporal rate ≈ 10.77 Hz** (not 64× as the placeholder in
  `configs/models/ace_step_v15.yaml` says — `latent_rate_factor: 64` is WRONG and was
  flagged as Q-PRM-5 ambiguity in `METHOD_SPEC.md` §8).
- Implied latent-rate factor in *samples per latent frame*: 44100 / 10.77 ≈ **4094**.
- No explicit `scaling_factor` multiplier on the DCAE output is mentioned in the paper.
  The DCAE latent is fed directly into the linear DiT.

## 5. Clean-target formula

> Express `x̂_0` (or the clean-latent estimate) as a function of `(x_σ, σ, v_out)`.

**Paper §3.3.1, page 7, verbatim:**

> "The clean latent x₀ is then estimated from x_noisy and v_out using the preconditioning
> formula:
>
>   x₀^pred = v_out · (−σ_t) + x_noisy
>
> The flow matching loss L_FM is then the Mean Squared Error (MSE) between this
> reconstructed prediction x₀^pred and the ground truth x₀:
>
>   L_FM = E_{x₀,z,t}[ ‖( ε_θ(x_noisy, t, condition) · (−σ_t) + x_noisy ) − x₀ ‖₂² ]
>
> where x_noisy = (1 − σ_t) · x₀ + σ_t · z."

**Conclusion.** In M-PRM notation where `z_σ ↔ x_noisy` and `σ ↔ σ_t`:

> **x̂_0 = x_σ − σ · v_θ(x_σ, σ, condition)**

This is the ACE-Step authoritative clean-target formula.

**Comparison to the rectified-flow form currently in `interface.py:tweedie_clean`:**
```python
# src/mprm/inference/interface.py line 45–47 (CURRENT, WRONG for ACE-Step):
def tweedie_clean(self, z_tau: torch.Tensor, tau: float, prompt: Prompt) -> torch.Tensor:
    v_pred = self.predict_velocity(z_tau, tau, prompt)
    return z_tau + (1.0 - tau) * v_pred
```

The current formula assumes `τ = 1` is data and `v = x₀ − z`. For ACE-Step:
- `σ = 0` is data (the **opposite** convention),
- target `v_out = z − x₀ = −(x₀ − z)` (the **negative** of the rectified-flow velocity),
- correct formula: `x̂_0 = z_σ − σ · v_out`.

The substitution σ = 1 − τ AND a sign flip on v_pred bring the two into algebraic
equivalence:
```
z_σ − σ·v_out
  ↔ (substitute σ = 1 − τ and v_out_acestep = −v_rectified_flow)
  = z_(1−τ) − (1 − τ) · (−v_rf)
  = z_τ + (1 − τ) · v_rf   ← rectified-flow form
```
So the formulas are equivalent **after both relabels** — but the d3 script currently:
- (a) feeds raw `τ ∈ {0.7, 0.5, 0.3, 0.1}` to the model (which expects an int timestep in
  `[1, 1000]`, scaled-by-`shift=3.0`),
- (b) interprets the returned `.sample` as rectified-flow `v_rf`, not as the
  negative velocity `v_out` that the ACE-Step model actually predicts.

Both of those are wrong. The clean implementation for ACE-Step is:

```python
# CORRECT for ACE-Step (paper §3.3.1, scheduler step rule):
def tweedie_clean(self, x_sigma: torch.Tensor, sigma: float, prompt: Prompt) -> torch.Tensor:
    # Pass sigma as the timestep input the model expects (int-valued float in [1, 1000])
    timestep = float(sigma) * 1000.0  # convert normalized σ ∈ [0, 1] back to ACE-Step internal
    v_out = self.predict_velocity(x_sigma, timestep, prompt)  # ACE-Step .sample
    return x_sigma - sigma * v_out  # x̂_0 = x_σ − σ · v_out
```

Additionally, because of the `shift=3.0` schedule, the four checkpoints chosen in the
d3 script (`τ ∈ {0.7, 0.5, 0.3, 0.1}`) should be re-derived as the sigma values at the
corresponding inference-step indices when `shift=3.0` is applied, not as uniform σ values.

## 6. Candidate-formula reconstruction comparison

| Candidate name | Formula | Status |
|---|---|---|
| `rectified_flow` (current, in `interface.py`) | `x̂_1 = z_τ + (1 − τ) · v_pred` | **WRONG for ACE-Step** per paper §3.3.1 and scheduler step rule. Mark as the "raw default to falsify". |
| `ace_step_paper` (proposed RESOLVED) | `x̂_0 = x_σ − σ · v_θ(x_σ, σ·1000, c)`, σ=0 data, σ=1 noise | **Theoretically supported** by paper §3.3.1 and scheduler step rule. Pending GPU verification at the next bridge. |
| `velocity_alt` (sign-flipped) | `x̂_0 = x_σ + σ · v_θ` | Would apply if the model actually predicts `+(x₀ − z)`; ruled out by the paper's explicit `−(x₀ − z)` target. |
| `x0_mode` | `x̂_0 = v_θ` | Ruled out — paper says model predicts velocity, not x0 directly. |

When a GPU env with `ace_step` installed is available, run
`python scripts/d3_tweedie_sanity.py --candidate-formula ace_step_paper` and confirm the
mean reconstruction LSD is materially lower than the `rectified_flow` baseline. The
implementation diff in `src/mprm/inference/ace_step.py` should override `tweedie_clean`
with the formula in §5 above.

## 7. Implementation cross-reference

After resolution, the chosen formula MUST match the implementation in:
- `src/mprm/inference/interface.py::FlowMatchingModel.tweedie_clean()` — currently
  hard-codes the rectified-flow form (WRONG); to be **overridden in
  `src/mprm/inference/ace_step.py`** with the ACE-Step formula in §5.
- `src/mprm/inference/ace_step.py::AceStepModel.predict_velocity()` — also needs to pass
  `sigma * 1000` (or the integer timestep) as the time input, not the raw `tau` float.

**Required code change for the next bridge:**

1. Override `AceStepModel.tweedie_clean()` to implement `x̂_0 = x_σ − σ · v_out`.
2. Update `AceStepModel.predict_velocity()` time-encoding path to receive σ (normalized
   `[0, 1]`) and internally rescale to the int timestep `[1, 1000]` that the underlying
   `ace_step_transformer` expects, before calling `.sample`.
3. Re-derive the four d3 checkpoint τ values to match the `shift=3.0` schedule.

---

## 9. D3 empirical sanity test on Paratera A800 (2026-05-22, STOP-B-9 closure)

STOP-B-9 (`src/mprm/inference/ace_step.py`, 2026-05-22) implements the missing
adapter methods (`predict_velocity`, `decode`, `encode`, `tweedie_clean`,
`tweedie_decode`, `return_trajectory=True`). The d3 sanity test was then run
under controlled conditions (`cfg_type='cfg'`, 8 prompts × K=3 checkpoints at
ACE-Step σ ∈ {0.5, 0.3, 0.1}, 30 inference steps × 10 s audio, single A800).

**σ-value caveat (Codex audit 2026-05-22 [D]):** the three σ checkpoints
`{0.5, 0.3, 0.1}` are **magic-number placeholders pending the Stage 0
calibration sweep** (audit-Round-4 ADD 2026-05-21, cost-gated at 20 GPU-h).
They come from the theoretical-rectified-flow late regime (R2 #25) and were
chosen before any empirical reliability calibration. Phase B.1 (64 × 3
calibration prompts at ρ ≥ 0.5 binary gate per R2 #6) will re-derive the
optimal Stage-1 σ set; the directional finding (ace_step_paper >
rectified_flow at all three checkpoints) is robust to this caveat, but the
absolute LSD / Spearman values are NOT final calibration evidence.

**Implementation-form caveat (Codex audit 2026-05-22 [A]):** the body of
`AceStepModel.tweedie_clean` does not match the literal 3-line form
`timestep = float(sigma)*1000.0; v_out = predict_velocity(z, timestep,
prompt); return z - sigma*v_out`. The actual body has σ→`sigma`
re-binding, an optional `v_out` parameter (so captured-trajectory v can
skip the predict_velocity round-trip), and float32 dtype casts for
numerical stability. The FORBIDDEN constraints declared in the audit are
all satisfied: no extra latent-scaling factor, no sign flip on v_out, no
conditional σ routing on σ value, no silent σ-semantic type cast, σ×1000
is NOT replaced by `num_train_timesteps` or similar (it lives inside
`predict_velocity` as `sigma * 1000.0`, NOT in `tweedie_clean`, because
`predict_velocity` takes σ as its `tau` argument, not pre-multiplied
`timestep`). Per PI directive 2026-05-22, the current body is retained as
the spirit (formula correctness + FORBIDDEN constraints) is satisfied.

**Empirical result table** (`papers/diagnostic/d3/{ace_step_paper,rectified_flow}/`):

| σ_target | σ_actual (median) | ace_step_paper LSD ↓ | rectified_flow LSD ↓ | ace_step_paper aesthetic Spearman | rectified_flow aesthetic Spearman |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.491 | **1.102** | 2.905 | **+0.690** | +0.476 |
| 0.30 | 0.329 | **1.064** | 2.435 | **+0.833** | +0.429 |
| 0.10 | 0.104 | **0.654** | 1.152 | **+0.905** | +0.238 |

**Interpretation.** The `ace_step_paper` formula `x̂_0 = x_σ − σ · v_out`
(with σ pulled from `scheduler.sigmas[k]`, shift=3.0 applied; model receives
`timestep = σ · 1000`) **materially outperforms** the rectified-flow baseline
`x̂_1 = z_τ + (1 − τ) · v` at every checkpoint:

- **LSD is 1.7–2.7× lower** for `ace_step_paper` at every σ. At σ=0.1 the
  Tweedie-clean reconstruction is genuinely close to the final audio
  (LSD = 0.654 vs 1.152).
- **Aesthetic Spearman with the final reward** is materially higher under
  `ace_step_paper` at every σ. At σ=0.5 it already clears the Phase-B
  R2 #6 binary gate ρ ≥ 0.5 (ρ = +0.690); at σ=0.1 it reaches ρ = +0.905.
  Under `rectified_flow` the late-σ Spearman *decreases* with σ ↓ (the
  opposite of the expected trend), confirming the formula is wrong.
- **Aesthetic@final mean = 7.112** (single-prompt template, low diversity)
  shows the generator is producing reasonable audio; the formula-distinction
  test is therefore not confounded by degenerate generation.

**Caveats** (these do NOT block STATUS=RESOLVED, but bound the claim):
- n = 8 prompts is small for tight Spearman SE; the *directional* test
  (ace_step_paper > rectified_flow at every checkpoint) is robust to small-n
  variance, but the absolute Spearman values (especially +0.905) should be
  re-validated at Phase B.1 sample size (64 × 3 calibration prompts) before
  using them to set per-axis reliability gates downstream.
- The test was run under `cfg_type='cfg'` (plain CFG) so the captured
  velocities match `predict_velocity`'s mixing. Upstream's default
  `cfg_type='apg'` may produce a slightly different reconstruction signature
  in production sampling; `apg` parity is a Phase-B engineering task.
- Audio diversity is limited (single template prompt "a calm acoustic guitar
  melody with no vocals"). Phase B.1 calibration will use the 64 dev prompts
  for prompt diversity.

**Implementation cross-reference (closing the §7 list):**
1. `src/mprm/inference/ace_step.py:_SchedulerStepCapture` — context manager
   hooking `FlowMatchEulerDiscreteScheduler.step` to capture
   `(step_index, σ, σ_next, timestep, sample, model_output)` at each step.
2. `AceStepModel.sample(return_trajectory=True)` — populates
   `SamplingResult.trajectory` + `extras['trajectory_sigmas']` +
   `extras['trajectory_model_outputs']`.
3. `AceStepModel.predict_velocity(z, σ, prompt, *, cfg_scale, condition_cache)`
   — plain-CFG mixing of `ace_step_transformer.decode(...)` outputs.
4. `AceStepModel._build_condition_cache(prompt)` — replicates upstream's text /
   lyric / speaker embedding flow for `cfg_type='cfg'`.
5. `AceStepModel.decode(z)` / `encode(w)` — direct calls to
   `_pipeline.music_dcae.decode/encode` at sr=48000.
6. `AceStepModel.tweedie_clean(z, σ, prompt, *, v_out=...)` — implements
   `x̂_0 = z - σ · v_out`; accepts a captured `v_out` to skip the
   `predict_velocity` round-trip (faster + matches sampling exactly).
7. `AceStepModel.tweedie_decode(z, σ, prompt, *, v_out=...)` — composes the
   above two.
8. `scripts/d3_tweedie_sanity.py` — rewritten to use scheduler-σ from the
   captured trajectory; supports `--candidate-formula {ace_step_paper,
   rectified_flow}`; PASS if monotonic LSD or positive late Spearman.

## 8. Source-level verification on Paratera A800 box (2026-05-21, audit-round)

Update 2026-05-21: ACE-Step is now installed in this environment under
`/HOME/paratera_xy/pxy1289/HDD_POOL/source/ACE-Step` (editable install,
`pip install -e .`; git SHA `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`). Source
inspection at concrete line numbers (Paratera install, 2026-05-19 clone):

- **Forward (noise) process — `scale_noise()`**
  `acestep/schedulers/scheduling_flow_match_euler_discrete.py:167`:
  `sample = sigma * noise + (1.0 - sigma) * sample` →
  `x_σ = σ · z + (1 − σ) · x₀`. **Confirms σ=0 data, σ=1 noise.**
- **Time-shift schedule — `set_timesteps()`**
  `acestep/schedulers/scheduling_flow_match_euler_discrete.py:207–211`:
  pre-shift `sigmas = timesteps / num_train_timesteps`; either dynamic
  `time_shift(mu, ...)` or static `sigmas = config.shift * sigmas / (1 + (config.shift - 1) * sigmas)`
  with `shift=3.0`. Then `timesteps = sigmas * num_train_timesteps` (so
  scheduler-stored `timesteps[k] = σ_k_shifted × 1000` and
  `scheduler.sigmas[k] = σ_k_shifted`).
- **Euler step rule — `step()`**
  `acestep/schedulers/scheduling_flow_match_euler_discrete.py:316–326`:
  `sigma = self.sigmas[step_index]`, `sigma_next = self.sigmas[step_index + 1]`,
  `dx = (sigma_next - sigma) * model_output`,
  `prev_sample = sample + dx`.
  Integrates `dx/dσ = v_out` along the σ axis. Walking σ to 0 yields:
  `x̂₀ = x_σ + (0 − σ) · v_out = x_σ − σ · v_out`. **Confirms the clean-target
  formula at line level.**
- **Pipeline-level Tweedie usage — `pipeline_ace_step.py:709–711`**
  (pingpong-SDE branch, executed at every guidance step):
  `zt_edit_denoised = zt_edit - t_i * V_delta_avg`, with `t_i = t / 1000`
  defined at line 663. This is **literally `x̂₀ = x_σ − σ · v_out` in the
  shipped inference code**. The σ used here is shift-applied (it comes from
  scheduler.timesteps which already include the shift). Cross-checked against
  paper §3.3.1 (arXiv 2506.00045) which states `x₀^pred = v_out · (−σ_t) + x_noisy`
  — algebraically identical.
- **Model input is the shifted timestep, not raw σ.** `pipeline_ace_step.py:687`
  passes `t=t` (the scheduler timestep, in [1, 1000]) to `calc_v()`. The pipeline
  computes `t_i = t / 1000` locally; the scheduler stores the shifted σ in
  `self.sigmas` and the corresponding timestep in `self.timesteps`. **Therefore
  the d3 sanity script must pull σ from `scheduler.sigmas[k]` (or t from
  `scheduler.timesteps[k]`), not pass a raw uniform τ ∈ {0.7, 0.5, 0.3, 0.1}.**

**Authoritative formula (now line-confirmed against installed source):**

```
x̂_0 = x_σ − σ · v_out(x_σ, σ·1000, condition)

where:
  σ ∈ self.sigmas (shift-applied per shift=3.0, NOT raw uniform values)
  v_out = model output (ACEStepTransformer2DModel.forward(..., timestep, ...).sample)
  scheduler.timesteps[k] = σ_k * 1000 is what the model expects as `timestep` arg
```

**Remaining blocker before STATUS=RESOLVED:**

Source verification (Steps 1–2 of the §7 list) is COMPLETE.
Sanity check (Step 3) is NOT complete — `src/mprm/inference/ace_step.py`
currently raises `NotImplementedError` on `predict_velocity`, `decode`, `encode`,
`tweedie_clean`, `tweedie_decode`, and rejects `return_trajectory=True`. These
were deferred at STOP-B-8 for M1a; STOP-B-9 (the M-PRM adapter work that
exposes flow head + DCAE + trajectory) is the remaining engineering blocker.

Once STOP-B-9 lands, the d3 sanity needs to:
1. Use `scheduler.sigmas[k]` (shift-applied), NOT raw `τ ∈ {0.7, 0.5, 0.3, 0.1}`.
2. Pass `t_k = scheduler.timesteps[k]` to the model as the `timestep` arg.
3. Compute `x̂₀ = x_σ − σ_k · v_out` (NOT the rectified-flow form
   `x̂₁ = z_τ + (1 − τ) · v` currently in `interface.py:tweedie_clean`).
4. Compare LSD-to-final and aesthetic-axis Spearman against
   `--candidate-formula rectified_flow` (the wrong-default baseline) to make the
   selection auditable on disk.

## Derivation status

> Update the `STATUS:` line below when the four slots above are filled in.
> One of: `STATUS: RESOLVED`, `STATUS: AMBIGUOUS`, `STATUS: TBD`.
> If `STATUS: AMBIGUOUS`, fill in §6 candidate comparison, pick a winner, and bump to
> `STATUS: RESOLVED`.
>
> The `STATUS:` line must appear at the start of its own line (no `# `, no `> ` prefix)
> so `scripts/d3a_tweedie_derivation.py` and `scripts/d3_tweedie_sanity.py` can parse it.

STATUS: RESOLVED

**Resolution SCOPE (Codex review 2026-05-22):** `STATUS=RESOLVED` applies to
the **Tweedie formula identification only** — i.e. the algebra `x̂_0 = x_σ − σ · v_out`
(with σ from `scheduler.sigmas[k]`, shift=3.0 applied) is the correct
clean-target formula for ACE-Step v1. `STATUS=RESOLVED` does **NOT** imply
the STOP-B-9 adapter (`AceStepModel.predict_velocity`) is production-ready
for Phase B M-PRM training; the following parity gaps must be closed before
Phase B's first RL rung:

1. **APG / cfg_zero_star parity.** `predict_velocity` currently replicates
   only `cfg_type='cfg'`. Upstream's default `cfg_type='apg'` has a
   momentum buffer + step-index-dependent guidance schedule that
   `predict_velocity(z, σ, prompt)` cannot match without those inputs.
   Either force `cfg_type='cfg'` end-to-end in Phase B or extend the method.
2. **ERG path parity.** Upstream `__call__` defaults `use_erg_tag=True`,
   `use_erg_lyric=True`, `use_erg_diffusion=True`. These install forward
   hooks that weaken attention via a temperature factor; the captured v_out
   during sampling includes their effect but `_build_condition_cache` does
   NOT. Either disable ERG end-to-end in Phase B or replicate the hooks.
3. **Captured-v parity test.** No automated check verifies that
   `predict_velocity(z_k, σ_k, prompt)` matches the trajectory's captured
   `model_output[k]` under identical settings. Add this as a Phase-B
   preflight (cosine similarity or relative-error threshold).

**Resolution evidence (2026-05-22, STOP-B-9 closure):** both halves of the
PI-required gate (source verification AND empirical sanity check) are now
satisfied for formula identification:

1. **Source verification.** §8 confirms the formula at line level in the
   installed ACE-Step source (commit `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`):
   - `scheduling_flow_match_euler_discrete.py:167` — σ=0 data / σ=1 noise via
     `sample = σ·noise + (1−σ)·sample`.
   - `:316-326` — Euler integrator implies `x̂_0 = x_σ − σ·v_out`.
   - `pipeline_ace_step.py:711` — literal `zt_edit_denoised = zt_edit - t_i * V_delta_avg`
     with `t_i = t / 1000 = σ` at line 663.

2. **Empirical sanity check (§9).** `python scripts/d3_tweedie_sanity.py
   --candidate-formula ace_step_paper` (8 prompts × K=3 σ checkpoints on
   Paratera A800, 2026-05-22) decisively beats the rectified-flow baseline at
   every checkpoint: LSD is 1.7–2.7× lower; aesthetic Spearman ρ goes from
   +0.690 (σ=0.5) → +0.833 (σ=0.3) → +0.905 (σ=0.1) under `ace_step_paper`
   vs +0.476 / +0.429 / +0.238 under `rectified_flow` (where the trend
   goes the wrong way at small σ).

3. **Implementation cross-reference.** §9 enumerates the STOP-B-9 adapter
   methods in `src/mprm/inference/ace_step.py` and the updated
   `scripts/d3_tweedie_sanity.py`. The `interface.py:tweedie_clean` base-class
   formula (`x̂_1 = z_τ + (1−τ)·v`) is still rectified-flow form and SHOULD
   NOT be used for ACE-Step; the `AceStepModel.tweedie_clean` override is the
   correct path.

**Phase B / M2 hard gate: PARTIALLY UNBLOCKED.** D3 reconstruction sanity
(formula identification) may now run in production mode without
`--allow-unresolved`. **However**, Phase B M-PRM training (the M2 / Phase C
rung set) remains gated on (a) the Phase B.1 reliability calibration
(64 × 3 calibration prompts at ρ ≥ 0.5 binary gate per R2 #6), and (b) the
STOP-B-9 parity items listed in the "Resolution SCOPE" block above
(APG/cfg_zero_star parity, ERG parity, captured-v parity test). Item (b) is
the Codex-review-2026-05-22 carry-over and must be addressed before any
Phase B rung that depends on `predict_velocity` (i.e. M-PRM training, as
opposed to D3 sanity which uses captured v).

---

## D3a auto-found references (do not edit by hand; rerun the script to refresh)

- Module: `acestep`
- Source dir: `/home/yehaocun23s/source/ACE-Step/acestep`
- Git SHA: `1bee4c9f5b43e30995f8d4d33b3919197ce1bd68`

Pattern matches in source (use these as starting points for §2 + §3 + §4 + §5):

### `ACEStepPipeline` matches

- acestep/pipeline_ace_step.py:94: class ACEStepPipeline

### `ACEStepTransformer2DModel` matches

- acestep/models/ace_step_transformer.py:204: class ACEStepTransformer2DModel

### `AceStepPipeline` matches

- acestep/pipeline_ace_step.py:94: class ACEStepPipeline

### `dcae` matches

- acestep/music_dcae/music_dcae_pipeline.py:28: class MusicDCAE

### `decode` matches

- acestep/models/ace_step_transformer.py:413: def decode
- acestep/models/lyrics_utils/lyric_tokenizer.py:703: def decode
- acestep/models/lyrics_utils/lyric_tokenizer.py:714: def batch_decode
- acestep/music_dcae/music_dcae_pipeline.py:115: def decode
- acestep/music_dcae/music_dcae_pipeline.py:147: def decode_overlap
- acestep/music_dcae/music_vocoder.py:559: def decode

### `encode` matches

- acestep/models/ace_step_transformer.py:362: def forward_lyric_encoder
- acestep/models/ace_step_transformer.py:375: def encode
- acestep/models/lyrics_utils/lyric_encoder.py:584: class ConformerEncoderLayer
- acestep/models/lyrics_utils/lyric_encoder.py:902: class ConformerEncoder
- acestep/models/lyrics_utils/lyric_tokenizer.py:694: def encode
- acestep/music_dcae/music_dcae_pipeline.py:77: def encode
- acestep/music_dcae/music_vocoder.py:186: class ConvNeXtEncoder
- acestep/music_dcae/music_vocoder.py:565: def encode
- acestep/pipeline_ace_step.py:1090: def forward_encoder_with_temperature

### `sampler` matches

- acestep/data_sampler.py:8: class DataSampler

### `scheduler` matches

- acestep/schedulers/scheduling_flow_match_euler_discrete.py:31: class FlowMatchEulerDiscreteSchedulerOutput
- acestep/schedulers/scheduling_flow_match_euler_discrete.py:42: class FlowMatchEulerDiscreteScheduler
- acestep/schedulers/scheduling_flow_match_heun_discrete.py:31: class FlowMatchHeunDiscreteSchedulerOutput
- acestep/schedulers/scheduling_flow_match_heun_discrete.py:42: class FlowMatchHeunDiscreteScheduler
- acestep/schedulers/scheduling_flow_match_pingpong.py:31: class FlowMatchPingPongSchedulerOutput
- acestep/schedulers/scheduling_flow_match_pingpong.py:42: class FlowMatchPingPongScheduler

### `step` matches

- acestep/models/ace_step_transformer.py:204: class ACEStepTransformer2DModel
- acestep/pipeline_ace_step.py:94: class ACEStepPipeline
- acestep/schedulers/scheduling_flow_match_euler_discrete.py:96: def step_index
- acestep/schedulers/scheduling_flow_match_euler_discrete.py:175: def set_timesteps
- acestep/schedulers/scheduling_flow_match_euler_discrete.py:221: def index_for_timestep
- acestep/schedulers/scheduling_flow_match_euler_discrete.py:235: def _init_step_index
- acestep/schedulers/scheduling_flow_match_euler_discrete.py:243: def step
- acestep/schedulers/scheduling_flow_match_heun_discrete.py:89: def step_index
- acestep/schedulers/scheduling_flow_match_heun_discrete.py:142: def set_timesteps
- acestep/schedulers/scheduling_flow_match_heun_discrete.py:182: def index_for_timestep
- ... (7 more)
