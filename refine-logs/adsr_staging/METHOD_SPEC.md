# METHOD_SPEC — Axis-Deferred Speculative Restart (ADSR) Implementation Contract

**v4.0 ADSR reframe, 2026-06-04**

> *Implementation-level method contract for the PI-frozen research direction
> **Axis-Deferred Speculative Restart (ADSR)** — "When to Continue: Axis-Deferred
> Speculative Restart for Flow-Matching Music Generation". ADSR uses early
> Tweedie-clean estimates to **terminate low-promise trajectories early and
> restart new seeds** (compute *reallocation*, not prune/select), while
> **deferring** decisions for late-observable axes (lyric intelligibility, fine
> semantics), and treats **prompt-type match (vocal vs. instrumental presence)**
> as a high-stakes early-reject axis with its own learned audio detector (EVPD).*
>
> This document is the bridge between `refine-logs/FINAL_PROPOSAL.md` v4.0 and
> the downstream `EXPERIMENT_PLAN.md` / `EXPERIMENT_PLAN_EXEC.md`. It is
> authoritatively scoped by the PI-frozen plan
> `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` and the reframe brief
> `refine-logs/ADSR_REFRAME_BRIEF.md`.
>
> **Method history (M-PRM → ETV → ADSR).** v2.x was *Headroom-Gated M-PRM*
> (musically-structured process-reward RL). v3.0 pivoted to *Early Trajectory
> Verifier (ETV)* — prune/select a fixed candidate pool with a learned
> verifier `V_σ`. The **2026-06-04 ADSR reframe** is the project's third major
> framing: ADSR is about **compute reallocation via RESTART/DEFER/CONTINUE**,
> not pool selection. ETV-pruning (Track A raw Early-Tweedie pruning, "raw
> ETP") is demoted from headline to a **same-compute baseline**; the learned
> `V_σ` verifier is retained as the **lightweight quality verifier** component
> of ADSR; the M-PRM RL stack (§§1–11 below, originally §§1–11) is **boundary
> evidence only**. The new ADSR method contract is §§13–16. See
> `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` for the frozen full spec.

**Status:** Plan-stage contract for the new ADSR method, anchored on existing
foundation evidence.

- **Foundation evidence (exists, repurposed):** H1/H2 early-quality persistence
  (Phase A headroom `delta_sigma_bon_vs_base = 0.7549`; H2 `STRONG_PASS` on 128
  prompts; Track B globalness 0.861); Track A raw-ETP pruning (Schedule A
  **0.9864** reward_fraction @ 0.500 compute, regenerated 2026-06-04 on the
  lyric-fix dataset; bottom-prune σ=0.7 false-negative 0.0195); lyric axis now
  scored EN-vocal-only (**0.682** ETP@50, n=282, 248/282 = 88 % carry signal);
  C1 RL boundary (no clear first-wave common-metric gain).
- **NOT yet run (ADSR is forward-looking here):** the **EVPD audio detector is
  NOT trained** (E3); **restart / ADSR is NOT run** (E6 — only offline-simulable
  on the 4096-candidate pool); **final vocal-presence labels are NOT yet
  derived**; H2b presence/content split is **unmeasured**; cross-backbone not
  started. This contract therefore specifies the implementation the
  `/experiment-bridge` pass must build; it does **not** report ADSR results that
  do not exist.

This contract reframes the **method**, not the **infra**. The reward harness
(§2), the headroom audit (§3), the ACE-Step σ convention + effective-velocity
Tweedie-clean derivation (§4.1), the prompt-level splits, the calibration/gate
policy (`configs/eval/gate_v2.yaml.draft`), and the canonical reward set
`orbit-research/trajectory_candidate_dataset.jsonl` are all preserved.

---

## 0. How to read this document

| §§ | Content | Status under ADSR |
|---|---|---|
| **1–2** | Targets, model interfaces, prompt sets, reward functions, anti-hacking probes, feature cache | **VALID INFRA — preserved.** Reused unchanged by ADSR. |
| **3** | Phase A headroom audit | **VALID INFRA — preserved.** Source of the H1 persistence evidence ADSR anchors on. |
| **4.1** | Tweedie-clean intermediate audio, ACE-Step σ convention, effective-velocity contract | **VALID INFRA — preserved.** ADSR's early estimate `x̂₀` uses exactly this derivation. |
| **4.2–11** | M-PRM RL stack (reliability gate, credit-unit comparison, action-localized advantage, Lagrangian lyric guard, CVaR, GRPO loop, Phase C/D) | **SUPERSEDED — boundary reference.** Cited only for the C6 RL boundary paragraph. No new RL is launched. Not deleted. |
| **12** | ETV verifier+pruning contract (v3.0) | **SUPERSEDED — repurposed.** The learned `V_σ` survives as the §14 lightweight quality verifier; raw-ETP pruning becomes a §15 baseline. Not deleted; see §12 header note. |
| **13–16** | **ADSR implementation contract** (decision logic, EVPD, quality verifier, decision thresholds, compute accounting §4.5-equivalent §16.4, offline-first, data fields, baselines, audit checklist) | **ACTIVE — paper-bearing.** This is the v4.0 method. |

Read §§13–16 as the active contract. §§1–4.1 and §2 are live infra dependencies.
§§4.2–12 are preserved boundary/superseded reference and must not be deleted
(doc-durability).

---

## 1. Targets and interfaces

### 1.1 Target models

| Role | Model | Source | Interface | License |
|---|---|---|---|---|
| **Primary** | ACE-Step v1.5 | GitHub `ace-step/ACE-Step-1.5`; `ACE-Step/acestep-v15-sft` (arXiv:2602.00744) | LM + DiT hybrid; flow matching; lyric-to-song | Apache 2.0 |
| **Primary (legacy)** | ACE-Step v1 | GitHub `ace-step/ACE-Step` (arXiv:2506.00045) | DCAE + linear DiT; flow matching head; lyric-to-song | Apache 2.0 |
| **Cross-backbone (E9; parallel, non-gating)** | Stable Audio Open 1.0 | `stabilityai/stable-audio-open-1.0` (arXiv:2407.14358) | `stable-audio-tools`; DiT-based FM in latent VAE; 44.1 kHz stereo | non-commercial |

**Scope decision (PI).** ACE-Step v1.5 is the centerpiece; the
when-to-continue / axis-observability question is intrinsically about *musical
structure*, *lyrics*, *vocal presence*, and *long-range song coherence*. Stable
Audio Open is the **cross-backbone replication target (E9)** — pursued
**Phase-1-parallel** with a graceful fallback, elevating an ACE-Step fact to a
flow-matching principle. It does **not gate submission**; if it is not ready,
ADSR submits with an honest target-regime limitation.

Per `ASSUMPTION_LEDGER.md` A1, A2, A22 — verify checkpoint loadability in
pre-experiment audit.

### 1.2 Required model interfaces

Every target must expose:
- Forward velocity / flow prediction `v_θ(z_σ, σ, c)` at arbitrary `σ`.
- ODE step (Euler / DPM-Solver / model default).
- SDE step with configurable noise injection (for restart-seed independence checks).
- Latent-to-waveform decoder `D` at native sample rate (needed to decode the
  early Tweedie-clean estimate for EVPD).
- CFG-conditional inference.
- **Independent-seed sampling** (load-bearing for ADSR: a RESTART draws a NEW
  independent seed, not a rollback or repair of the terminated trajectory).
- **`Tweedie-clean` decode at intermediate σ**: given `x_σ`, produce an estimate
  of the clean audio latent `x̂₀` then decode via `D` to a candidate waveform
  `â = D(x̂₀ | x_σ, σ)`. The exact formula depends on the FM/RF parameterization;
  *must be validated by reconstruction sanity checks* (§4.1, A26), not assumed
  from a generic diffusion identity.
- (Boundary-only) Policy-ratio statistics along the reverse trajectory for the
  M-PRM RL boundary runs (§§4.2–11). Current backend uses a documented
  `flow_matching_surrogate` estimator, not exact diffusion logprob. ADSR's
  active method does **not** require this interface.

### 1.3 Prompt sets

- **Development set:** 256 prompts, stratified.
- **Held-out set:** 256 prompts, stratified.
- **Achieved candidate pool (offline-first base):** 512 prompts / BoN-8 /
  **4096 candidates**, canonicalized as
  `orbit-research/trajectory_candidate_dataset.jsonl`.

Strata (both sets): genre · tempo · **vocal vs. instrumental** · lyric density ·
structural complexity · language · prompt specificity · expected song length.

**Split policy (load-bearing).** Split by **prompt_id, never candidate_id** —
the BoN-8 candidates of one prompt must never straddle the train/eval boundary
(prevents same-prompt candidate leakage). This is cross-prompt-not-cross-content
and is reported per-specificity-stratum.

**Lyric-bearing subset (new for ADSR).** 200–300 lyric-bearing vocal prompts;
**English clean core**; ≥3 lyric lines where possible; separate
calibration/evaluation split. Report separately on three nested populations:
**clean-English-core** / **broader lyric-bearing-vocal** /
**multilingual-or-thin-lyric stress arm**. **Never mix instrumental prompts into
headline lyric metrics** (no instrumental-sentinel pollution).

For ACE-Step: prompts include metadata, lyrics, and song-structure hints. For
the Stable Audio Open cross-backbone replication: T2A/T2M prompts without lyric
guard.

### 1.4 Song length policy

- Pilots: 30–60 s.
- Achieved candidate pool: ACE-Step 30–40 s short-form (the regime the Track A /
  H2 / globalness evidence was generated on).
- **Do not claim 4-minute or 10-minute long-song optimization** unless explicitly
  evaluated.

---

## 2. Reward functions (VALID INFRA — preserved)

### 2.1 Reward axes (calibrated on small human-rated validation set)

| Axis | Signal | Notes |
|---|---|---|
| Aesthetic / production | Meta Audiobox Aesthetics (`facebookresearch/audiobox-aesthetics`, arXiv:2502.05139) | per-axis (PQ/PC/CE/CU); **early-observable** under ADSR |
| Semantic fit | LAION-CLAP or M2D-CLAP cosine | check prompt leakage + genre bias; **mid-observable** |
| **Lyric intelligibility** | **Whisper-large-v3 WER on vocal stem** | **late-observable, late-deferred axis; EN-vocal subset only** (§2.5) |
| Musical coherence | MERT section embeddings / recurrence consistency | proxy for section continuity; degenerate dynamic range, diagnostic |
| **Vocal presence (NEW)** | **final vocal-presence label** (source separation; §2.5) | **early-observable, high-stakes early-reject axis** (the EVPD target) |
| Diversity / anti-collapse | Vendi / FAD / embedding spread | guardrail, NOT optimized directly |

### 2.2 Robust aggregate reward (used in Track A audit + verifier training)

For each sample `x` and prompt `c`, score under reward ensemble and benign audio
perturbations Π = {crop, loudness, codec round-trip, fold-down, time-shift}:

```
R_axes(x, c, π)            ∈ ℝ^K     over K axes, perturbation π ∈ Π ∪ {identity}
mean_R, std_R              = aggregate over axes + Π
probe_pen(x, c)            = Σ_p max(probe_p(x, c) − threshold_p, 0)   # anti-hacking hinges
R_robust(x, c)             = mean_R − β_robust · std_R − λ_probe · probe_pen
```

Pre-registered: `β_robust = 0.5`, `λ_probe` per-probe, calibrated on held-out
small human-labeled subset (per A16). `common_robust_lcb` is the primary axis
ADSR's quality verifier (§14) regresses/ranks against.

### 2.3 Anti-hacking probes (versioned)

| Probe | Definition | Threshold (initial) |
|---|---|---|
| `silence_fraction(x)` | Fraction of 20 ms windows with `|x| < 1e-3` | ≥ 0.30 |
| `autocorr_repetition(x)` | Max normalized autocorr at lag ≥ 0.5 s | ≥ 0.6 |
| `off_prompt_distance(x, c)` | `R_CLAP(base(c), c) − R_CLAP(x, c)` | > 0.10 |
| `hf_artifact_score(x)` | Normalized energy above 18 kHz vs. clean baseline | > 2.5× |
| `broken_section_indicator(x, c)` | per-section min R_axes drops below per-genre base-policy floor | per-axis |

Probe library versioned as `probes/v0.1/`. λ defaults are 0; calibrated from
Phase A hacking severity. Preserved unchanged.

### 2.4 Reward harness feature caching (preserved — load-bearing for offline-first)

Engineering optimization to reduce per-prompt reward-scoring cost. **Required
for ADSR's offline-first protocol** (§16.4): the 4096-candidate pool's early-σ
decoded audio and axis scores are cached, so offline ADSR simulation needs no
GPU re-decoding.

- **`BaseAudioFeatures` cache layer** under `src/mprm/rewards/`. Caches
  safely-shareable intermediates: waveform hash (key) + sample rate + resampling
  outputs + Demucs vocal stem + mel/STFT features + other shared intermediates.
  **The cached Demucs vocal stem is reused to derive the new vocal-presence
  label (§2.5) without re-separation.**
- **Consumers** (read cache when safe; compute + write back otherwise): CLAP,
  Audiobox-aesthetics-4, MERT, Whisper, **EVPD mel-spectrogram extraction**.
- **Cache key** MUST include: waveform hash, sample rate, reward-model version,
  config hash, stem model version. Mis-keyed entries → cache miss; never serve
  stale.
- **Validation requirement**: 32-sample parity test comparing pre-cache vs
  post-cache reward outputs across all axes. Out-of-tolerance → cache disabled
  until parity restored.
- **Audit trail**: per-call cache hits/misses logged to `RUN_LEDGER.jsonl`.

### 2.5 Vocal-presence label and the lyric EN-vocal subset (NEW, ADSR data infra)

**Final vocal-presence label (new field; not yet derived — E3/Phase 1 task).**
Derive a per-candidate FINAL vocal-presence label via:
1. **Primary:** source separation (Demucs htdemucs / Spleeter) **vocal-energy
   ratio** thresholding on the final waveform (reuse the cached Demucs vocal
   stem from §2.4), or a dedicated singing-voice-detection (SVD) model.
2. **Coarse pre-filter only:** Whisper `no_speech_prob` — use only to narrow
   candidates, **never as ground truth** (Whisper targets speech not singing;
   instrumental audio can false-trigger).

**Relabel the existing 4096 candidates retroactively** so vocal presence is
available for the offline ADSR studies. The label feeds: (a) EVPD ground truth
(§13), (b) prompt-type-match computation, (c) the presence-vs-content
disentanglement of lyric-zero candidates (E3).

**Lyric intelligibility — EN-vocal subset only (lyric-fix R2, preserved).** The
Whisper WER scorer is English-only, so non-EN vocal prompts floor regardless of
audio; instrumental prompts carry a constant 1.0 sentinel and are masked (never
pooled). The honest population is the **`vocal_scorable` EN-vocal stratum,
n=282**; after the 2026-06-03 lyric regen, **248/282 = 88 %** of EN-vocal
prompts carry signal, and the honest **ETP@50 reward_fraction on this subset is
0.682** (the prior 0.8432 over all 512 prompts was contaminated by the
instrumental sentinel). See
`orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`.

---

## 3. Phase A — Headroom-First Audit (VALID INFRA — preserved; foundation of H1)

Track A / Phase A is **already executed**; this section documents the audit that
produced the H1 persistence evidence ADSR anchors on. No new Phase A run is
launched by ADSR.

| Run | Purpose | Compute (per model) |
|---|---|---|
| Base sampling | default-quality reference | ~50 GPU-h |
| CFG sweep | cheap inference-time ceiling | ~80 GPU-h |
| BoN-4 / 8 / 16 | inference-time headroom | ~200 GPU-h |
| BoN+CFG | strong inference-time ceiling | ~120 GPU-h |
| Robust BoN | tests raw-reward hackability | ~120 GPU-h |
| S7 sampler-control-only | falsifies weight-update necessity | ~60 GPU-h |

**Headroom evidence (achieved).** Phase A established inference-time headroom
(`delta_sigma_bon_vs_base = 0.7549`; CFG / S7 sampler controls negative). This is
the empirical license for inference-time compute allocation that ADSR builds on.
Under ADSR the BoN candidate pool is reinterpreted: instead of "select the best
of a fixed pool", ADSR draws the next independent pool candidate as a RESTART —
the same 4096 candidates support the offline-first simulation (§16.4).

---

## 4.1 Tweedie-clean intermediate audio (VALID INFRA — preserved; ADSR's early estimate)

ADSR's early decision features come from the **Tweedie-clean estimate `x̂₀`**
decoded to early audio. The derivation below is the velocity-of-record and is
reused unchanged.

**ACE-Step σ convention (source-confirmed at
`acestep/schedulers/scheduling_flow_match_euler_discrete.py:167,316–326` per
`orbit-research/TWEEDIE_DERIVATION_NOTE.md` §8):** ACE-Step uses **σ = 0 is data,
σ = 1 is noise** (opposite of the rectified-flow convention some prior text
used). The shift=3.0 schedule means per-step σ stored in `scheduler.sigmas[k]` is
non-linear in step index; pull σ from `scheduler.sigmas[k]`, not a uniform τ. The
clean-target formula in ACE-Step coordinates is:

```
x̂_0 = x_σ − σ · v_out(x_σ, σ·1000, condition)
```

where the model receives `timestep = σ·1000` (a float in [1, 1000];
`scheduler.timesteps[k]`). **Line-confirmed at `pipeline_ace_step.py:711`**
(`zt_edit_denoised = zt_edit - t_i * V_delta_avg`, with `t_i = t / 1000` per line
663).

**Effective-velocity contract.** Clean-target reconstruction uses the
**effective velocity actually applied by the sampler at step k** (CFG-mixed
inside `[start_idx, end_idx)`, cond-only outside, per the `guidance_interval =
0.5` upstream default):

```
v_effective(k) = trajectory_model_outputs[k]            # captured
              ≡ CFG-mixed v at step k    if trajectory_cfg_active[k] is True
              ≡ cond-only v at step k    otherwise
x̂_0(k) = z_k − σ_k · v_effective(k)
```

Any code that *recomputes* `v` at a perturbed latent MUST pass
`cfg_active=trajectory_cfg_active[k]` to `AceStepModel.predict_velocity`; the
adapter raises `ValueError` if omitted while `cfg_scale > 1.0`. ADSR's early
estimate reuses the **captured** `trajectory_model_outputs[k]` directly — no
recomputation, so this contract is satisfied by construction. Reconstruction
sanity (decode `â` for known good final states; expect non-trivial similarity to
`a_final` for late σ, degrading gracefully for early σ) must pass before any
ADSR early-σ feature is trusted.

**Early-σ checkpoint set for ADSR.** The decision checkpoints are the early-σ
set the Track A cached records carry: **σ ∈ {0.9, 0.8, 0.7}** (the
`primary_nontrivial` band; the early decision frontier). σ ∈ {0.5, 0.3} are
`late_reference` (nearly clean — trivially high correlation, not decision-bearing
for early restart). The decision σ_c (the σ at which ADSR commits to
restart/defer/continue) is configurable in {0.9, 0.8, 0.7}; σ_c sensitivity is an
E6 ablation.

---

> **§§4.2–11 below are SUPERSEDED M-PRM RL boundary reference (preserved, not
> deleted).** They are the implementation contract for the **C6 RL boundary
> paragraph** only. No new RL is launched by the ADSR reframe. The active method
> resumes at §13. The M-PRM stack is retained verbatim in structure for the
> boundary citation and for doc-durability (the STOP-B fix-pass history and the
> ACE-Step LoRA/GRPO plumbing it documents remain valid).

## 4.2–4.4 Phase B — Process-Reward Reliability and Credit-Unit (SUPERSEDED — boundary)

*(M-PRM reliability gate, the five-credit-unit comparison, and the credit-unit
gate. Retained as boundary evidence: section credit is not the best default
credit unit for ACE-Step 30–40 s generations; FixedWin behaves like a
persistent-quality proxy. Cited in the C6 boundary paragraph and the
`ASSUMPTION_LEDGER.md` boundary rows. Not used by ADSR.)*

- **4.2 Reliability gate.** Per-axis-checkpoint Spearman gate `ρ_{k,axis} ≥ 0.5`
  binary; late-σ {0.5, 0.3} = `late_reference` descriptive only; primary H2
  evidence only from `primary_nontrivial` σ ∈ {0.9, 0.8, 0.7, 0.6}; late-reference
  passes MUST NOT rescue a primary FAIL. Adaptive sample size (64→128 prompts on
  ambiguity). Offline ρ ∈ {0.3, 0.5, 0.7} sensitivity. D3a Tweedie code-level
  derivation is a hard pre-Phase-B gate.
- **4.3 Credit-unit comparison.** Five units: Timestep / FixedWin (4 s) /
  BeatWin / LyricSpan / Section (MERT/CBM).
- **4.4 Credit-unit gate (H3 prescreen, EXECUTED).** Classification
  `SECTION_FAIL_WITH_INSTR_PROMPT_FIT_NUANCE`. Coverage-aware best non-section =
  **FixedWin**. M-PRM downstream primary = M-FixedWin-PRM; M-Section-PRM =
  diagnostic / negative control (one instr × prompt_fit strict-pass cell at
  +0.167 — **do NOT claim sections never work**). Finite-coverage ≥ 50 % rule;
  pre-specified same-winner rule.

*(Full equations and the per-stratum prescreen tables are preserved in the ETV
archive `orbit-research/archive/etv_pre_adsr_20260604/METHOD_SPEC.md` §§4.2–4.4
and in `ASSUMPTION_LEDGER.md` boundary rows.)*

## 5. Phase C — M-PRM training (SUPERSEDED — boundary)

*(M-FixedWin-PRM / M-Section-PRM LoRA/GRPO training: per-segment process reward,
action-localized advantage, locality probe, constrained Lagrangian lyric guard,
calibrated CVaR aggregation, headroom-weighted curriculum, the GRPO group-rollout
loop, `flow_matching_surrogate` estimator caveat, training form = LoRA. The
**C1 first-wave result is `COMMON_DEV_NO_CLEAR_WIN`** — all four methods (R8a,
R8b, M-FixedWin, M-Section) completed cleanly with deltas +0.012 to +0.014 LCB;
no clear common-metric gain.)*

This is the **C6 RL boundary result**: LoRA/GRPO process-reward RL is technically
feasible but shows no clear first-wave common-metric gain, motivating the shift
to inference-time compute allocation (ADSR). **No new RL training is launched.**
The only RL evidence cited is
`runs/phase_c1_firstwave_20260524_researcher_go_01/` +
`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`. **New σ-axis RL is future work, not
in the ADSR execution plan.**

*(Full §5 pseudocode — GRPO loop, CVaR `α=0.30/β=0`, Lagrangian `ε=0` global,
`λ_KL=0.05` static with 5.0-nat abort, `T_train=5`, the §5.8 hyperparameter
table — is preserved in the ETV archive and the v3.0 METHOD_SPEC. Anti-hacking,
robust-reward, and σ-convention infra from §§2 and 4.1 remain live and are not
boundary.)*

## 6. Phase D — M-PRM Evaluation and Ablation Suite (SUPERSEDED — boundary)

*(M-PRM primary comparisons and core ablations. The human-evaluation harness
spec — Tier-1 MUST-RUN 128 pairs × 5 raters × 5 axes ≈ 3,200 axis-judgments,
anti-fatigue ≤250 axis-judgments/session, mixed-effects analysis — is **valid
infra reused by ADSR's E2/E8 human studies** (§§E2, E8 in `FINAL_PROPOSAL.md`
v4.0). The M-PRM-specific method/ablation rows are boundary.)*

**Preserved human-eval infra (live for ADSR):** the rater pool, session design,
anti-fatigue budget, sanity/attention pairs, and mixed-effects analysis from the
former §6.3 Tier-1/Tier-2 design are reused for E2 (human early→final
validation, incl. early vocal-presence listening) and E8 (32–64 blind A/B method
spot-check). **Human judgment overrides automatic reward when they conflict.**

---

## 7–11. (M-PRM contract continuation — SUPERSEDED — boundary)

§§7–11 of the v3.0/v2.2 contract (`/experiment-bridge` PLAN_CODE_AUDIT checklist
for M-PRM, open M-PRM implementation questions, method alternates/pivot routes,
the 5,400 GPU-h compute envelope, the M-PRM STOP-A checklist) are preserved as
boundary reference in the ETV archive
`orbit-research/archive/etv_pre_adsr_20260604/METHOD_SPEC.md`. The
**5,400 GPU-h compute envelope and scope-cut order remain the project's hard cap
and are reused by ADSR** (ADSR's active method is near-free offline; the GPU
budget is spent on the candidate pool, EVPD training, the cross-backbone
replication, and human eval — see §16.5). The active ADSR STOP-A checklist is
§16.7.

---

## 12. Early Trajectory Verifier (ETV) — implementation contract (v3.0; SUPERSEDED — repurposed)

> **Status under ADSR (2026-06-04):** ETV framed inference-time scaling as
> **prune/select a fixed candidate pool** with a learned verifier `V_σ`. ADSR
> reframes this as **compute reallocation via restart**. Two parts of §12 are
> repurposed, not deleted:
> 1. The **learned `V_σ` verifier (§12.1–12.3, 12.6)** survives as ADSR's
>    **lightweight quality verifier** (§14). The features, the model tiers
>    (logistic → GBDT pairwise primary → LambdaMART), the
>    no-large-model-training bound, and the Track-A-cached-features
>    no-GPU-forward-pass property all carry over.
> 2. **Raw Early-Tweedie pruning (Schedule A/B/C, bottom-prune)** is demoted from
>    headline to a **same-compute baseline** ("raw ETP") in §15. Its known result
>    — Schedule A **0.9864** reward_fraction @ 0.500 compute; raw-ETP@50 over
>    BoN-4 ≈ **+0.0036** — is exactly *why it cannot be the headline* (selection
>    over a fixed pool is low-stakes; median regret ≈ 0). This motivates ADSR's
>    restart reallocation.
> 3. The **risk-controlled conformal pruning (§12.4, ε ∈ {1,3,5}%)** is retained
>    as an *optional* risk-controlled restart-threshold calibration in §16
>    (calibrate the restart trigger so empirical P(restart away the final top-1)
>    ≤ ε), but the headline ADSR decision is the restart/defer/continue logic of
>    §13, not conformal selection.
>
> The full §12.1–12.11 ETV contract is preserved verbatim in the ETV archive
> `orbit-research/archive/etv_pre_adsr_20260604/METHOD_SPEC.md`. Key invariants
> carried into §14:
> - Canonical reward set: `orbit-research/trajectory_candidate_dataset.jsonl`
>   (promoted 2026-06-04; merged from
>   `runs/early_tweedie_validation_512_bon8_20260527_full01/` 380 unchanged +
>   `runs/early_tweedie_validation_final_lyricfix_20260603/` 132 regenerated).
> - Features: early-σ `r_lcb` at {0.9, 0.8, 0.7}, slope, within-prompt ranks,
>   prompt_type, optional axis + uncertainty features.
> - Primary target axis: `common_robust_lcb`. Auxiliary axes
>   (`aesthetic_pq`, CLAP semantic, **`lyric_intelligibility` EN-vocal n=282
>   only**, MERT coherence) are cross-metric-validation only, never training
>   targets.
> - Train = 256 dev prompts; eval = 256 held-out; within-prompt BoN-8 groups;
>   **no candidate-level leakage**; split by prompt_id.
> - Model tiers E-R7..E-R9 (logistic / **GBDT pairwise PRIMARY** / LambdaMART);
>   ridge already near-saturates within-prompt NDCG ~0.995 — capacity is NOT the
>   bottleneck, so **no MLP / large model for the quality verifier; EVPD (§14.2)
>   is the only learned neural component**.
> - Compute: **0 GPU-h, ≤10 CPU-h** for verifier training + ablations + risk
>   calibration.

---

# ADSR ACTIVE METHOD CONTRACT (§§13–16)

The remainder of this document is the **active, paper-bearing v4.0 ADSR
implementation contract**. It specifies what `/experiment-bridge` must build.

## 13. Decision logic: RESTART / DEFER / CONTINUE

### 13.1 The three decisions

```
RESTART  : terminate the current trajectory; launch a NEW independent seed.
           This is a compute REALLOCATION, NOT a rollback/repair of the
           terminated trajectory. The freed compute funds a fresh draw.
DEFER    : continue this candidate to a later σ before deciding (do not
           commit). The canonical defer case is lyric/fine-semantic content.
CONTINUE : continue this candidate to full generation.
```

ADSR is **not** prune/select over a frozen pool. It is **reallocation**: bad
trajectories are stopped early and the saved compute is spent exploring new
independent seeds, so more useful trajectories are visited under the same budget.

### 13.2 Decision logic (type-match has priority)

At decision σ_c, for a candidate with early Tweedie-clean estimate `â = D(x̂₀)`:

```
# (1) High-stakes, early, COARSE: prompt-type match (EVPD)
if EVPD(â).p_vocal disagrees with requested-type at confidence ≥ τ_type:
    RESTART                       # gross type error — a categorical, UNUSABLE failure

# (2) Early-observable quality clearly low, late-axis risk low/irrelevant
elif quality_verifier(â).safe_restart_prob ≥ τ_q
     and late_axis_risk(â) ≤ τ_risk:
    RESTART

# (3) Late-observable CONTENT risk high or uncertain: never reject early
elif semantic_or_lyric_content_risk(â) high/uncertain:
    DEFER                          # judged at a later σ; lyric is the canonical defer case

# (4) Otherwise
else:
    CONTINUE
```

**The load-bearing distinction (H2b).** Vocal *presence* ("is there singing?")
and gross production failure are **early-decidable** and may be restarted on.
Lyric *content* ("which words, sung correctly?") and fine semantics are
**late-decidable** and must be **deferred**, never early-rejected. Early-rejecting
a type error judges *presence*, not *content* — this is what lets ADSR
early-reject without violating "defer lyric".

### 13.3 Restart-seed independence

A RESTART draws a fresh independent noise seed for the same prompt (the SDE/ODE
sampler's standard independent-seed path, §1.2). In the offline-first simulation
(§16.4), "restart" = draw the *next independent candidate of the same prompt*
from the 4096-pool (the BoN-8 siblings are independent seeds). Independence must
be verified (no shared seed / no rollback) so the restart is genuinely a new
exploration, not a perturbation of the terminated trajectory.

---

## 14. Two distinct learned components

ADSR has **two deliberately different learned components**. Their capacities
differ because they solve different problems.

### 14.1 Lightweight quality verifier (scalar features; near-saturated)

**Role.** Predict, from **scalar** early features: safe-restart probability,
late-axis risk, and final rank / survival.

**Inputs (per candidate `i` of prompt `c`, from the Track A cached records — no
GPU forward pass):**

```
features(c, i) = [
  r_lcb(â_{c,i,σ=0.9}),  r_lcb(â_{c,i,σ=0.8}),  r_lcb(â_{c,i,σ=0.7}),
  r_lcb(â_{c,i,σ=0.7}) − r_lcb(â_{c,i,σ=0.9}),                            # slope
  rank_{σ=0.9}(c, i),    rank_{σ=0.8}(c, i),    rank_{σ=0.7}(c, i),
  prompt_type(c),                                                           # vocal / instrumental
  # Optional axis features (ablation):
  r_pq(â_{c,i,σ=0.7}),   r_clap(â_{c,i,σ=0.7}), r_mert(â_{c,i,σ=0.7}),
  # Optional uncertainty (ablation):
  std_axes(â_{c,i,σ=0.7})  over reward ensemble
]
```

**Model tiers (no large model; bound unchanged from §12):**

| Tier | Model | Library | Role |
|---|---|---|---|
| Q-R7 | logistic / linear / ridge regression | sklearn | floor baseline |
| **Q-R8** | **GBDT pairwise ranker** | **lightgbm.LGBMRanker(objective='lambdarank')** | **PRIMARY** |
| Q-R9 | LambdaMART listwise ranker | lightgbm.LGBMRanker(objective='lambdarank', ndcg_at=[1,2,4]) | listwise alternative |
<!-- no MLP tier: the scalar quality verifier is near-saturated (ridge NDCG ~0.995); EVPD (§14.2) is the only learned neural component. -->


**Capacity framing (anti-overclaim).** Ridge already near-saturates within-prompt
NDCG (~0.995); **capacity is NOT the bottleneck** — the label signal is limited
by near-tied same-prompt candidates (median regret ≈ 0). The verifier is useful
because it improves **safe-restart calibration** and **late-axis defer**, not
because it is complex. **Targets:** final robust-reward regression, final rank,
top-1/2/4 survival, **safe-restart label**, **late-axis risk label**.

### 14.2 Early Vocal-Presence Detector — EVPD (learned AUDIO model; NOT yet trained)

**Role.** Predict **FINAL vocal presence** from the **EARLY Tweedie-clean
mel-spectrogram** of `x̂₀` at the decision σ_c. `prompt-type match` = compare the
EVPD prediction to the prompt's requested type (vocal vs. instrumental).

**Why this is a real neural net (not scalar features).** Presence detection
requires *reading the audio*, not scalar reward axes; and the **early-σ domain
(heavy noise) is out-of-distribution** for off-the-shelf voice/SVD detectors
trained on clean audio. Early audio perception under noise is a genuine learning
problem — this is the one ADSR component that warrants a learned audio model.

**Architecture.** Small CNN over the early mel-spectrogram, **or** a fine-tuned
pretrained audio encoder (e.g. a small AST / PANNs / MERT-frontend head). Output:
`p_vocal ∈ [0,1]` = P(final output contains singing voice). Keep it small;
training data is the 4096 relabeled candidates (§2.5).

**Ground-truth label.** The final vocal-presence label from §2.5 (source
separation vocal-energy ratio / SVD; Whisper `no_speech_prob` coarse pre-filter
only). **Not yet derived** — Phase 1 / E3 task.

**Training inputs.** Early Tweedie-clean mel-spectrogram of `x̂₀` at σ ∈ {0.9,
0.8, 0.7} (extracted from the cached early-σ decoded audio via the §2.4 cache).
**Per-σ heads** so the **vocal-presence decidability onset σ** can be reported
(at which σ does AUC clear threshold?).

**Reported metrics (E3).** Detection AUC per σ; **vocal-presence-onset σ**;
type-error prevalence (vocal-prompt→instrumental and instrumental-prompt→vocal
rates); prompt-type-match rate after type-match restart; false-restart-on-type
rate. **Disentangle** existing lyric-zero candidates into *type errors* (no voice
→ no transcription) vs *content failures* (voice present but unintelligible) —
the presence/content split (H2b).

**Off-the-shelf baseline.** An off-the-shelf (non-early-trained) vocal/SVD
detector applied to the early estimate is a baseline for EVPD — expected to
underperform because it is OOD at early σ.

### 14.3 Why the two components differ in size

| Component | Input | Problem character | Right capacity |
|---|---|---|---|
| Quality verifier (§14.1) | scalar reward features | near-saturated, low-capacity (NDCG~0.995 at ridge) | GBDT/LambdaMART, **0 GPU-h** |
| EVPD (§14.2) | early mel-spectrogram | genuine OOD early audio perception | small learned audio net, **needs GPU training** |

This asymmetry is intentional and is itself a finding: scalar-feature ranking is
saturated, while early audio presence detection is a real learning problem.

---

## 15. Baselines (same as `FINAL_PROPOSAL.md` v4.0 §7 and `CONTROL_DESIGN.md`)

| Baseline | Definition | Role |
|---|---|---|
| **Full BoN-8** | generate all 8 candidates to completion, select best | upper anchor (full compute) |
| **BoN-4** | half-budget BoN | **the critical same-compute comparator** |
| **Random prune / restart** | randomly terminate + draw new seed | does ADSR's *axis-awareness* matter? |
| **Raw ETP** | raw Early-Tweedie pruning, Schedules A/B/C, bottom-prune | the **demoted ETV headline**; Schedule A 0.9864 @ 0.500; raw-ETP@50 over BoN-4 ≈ +0.0036 → **cannot be the headline** |
| **Learned-verifier selection** | §14.1 verifier used to *select* (not restart) | isolates restart vs. selection |
| **Type-match restart** | EVPD type-match branch only (no quality/defer) | isolates the §14.2 contribution |
| **ADSR (main)** | full restart/defer/continue with EVPD branch | the method |
| *Boundary (not main):* M-FixedWin-PRM, M-Section-PRM, R8a, R8b | §§5–6 RL | C6 RL boundary paragraph |
| *Optional:* BoN-16, non-Tweedie early audio proxy, late-only selection, oracle final selector, off-the-shelf vocal detector (EVPD baseline) | | extra anchors |

**Two-factor ablation (required).** axis-awareness (off/on) × restart-reallocation
(select-only / restart). ADSR is the (axis-aware × restart) cell. EVPD-branch
on/off is a third ablation knob.

---

## 16. Compute accounting, offline-first protocol, data fields, and audit

### 16.1 Data fields (canonical candidate dataset)

`orbit-research/trajectory_candidate_dataset.jsonl`, one record per candidate:

```
prompt_id            (split unit — NEVER candidate_id)
candidate_id
seed
split                (train=dev256 / eval=heldout256; lyric-subset split separate)
final_reward, final_rank
r_lcb[σ]             early-σ common_robust_lcb at σ ∈ {0.9, 0.8, 0.7}
axis_early[axis][σ]  early axis scores (aesthetic_pq, semantic_clap, mert, ...)
axis_final[axis]     final axis scores
final_vocal_presence_label   (NEW — §2.5; via source separation / SVD; NOT yet derived)
requested_type       (vocal / instrumental — from prompt)
lyric_bearing_flag
lyric_en_vocal_scorable      (the n=282 EN-vocal subset membership)
prompt_category, prompt_specificity_stratum
compute_metadata     (NFE to each σ, full NFE, decode cost)
```

**Split by prompt_id, never candidate_id.** Lyric metrics computed only on
`lyric_en_vocal_scorable = True` (n=282); instrumental sentinel masked.

### 16.2 Decision thresholds

| Threshold | Meaning | Initial | Notes |
|---|---|---|---|
| `σ_c` | decision σ (commit restart/defer/continue) | 0.7 | sweep {0.9, 0.8, 0.7} in E6 |
| `τ_type` | EVPD confidence to call a type error | calibrate on dev so false-restart-on-type ≤ target | high-stakes → conservative |
| `τ_q` | quality-verifier safe-restart prob to restart | calibrate on dev | from §14.1 |
| `τ_risk` | max late-axis risk permitting a quality restart | calibrate on dev | protects late axes |
| `ε` (optional RC) | risk-controlled restart: empirical P(restart away final top-1) ≤ ε | {0.01, 0.03, 0.05} | conformal calibration, optional |
| `restart_budget` | max restarts per prompt under the matched-NFE budget | from §16.3 | |

All thresholds are **pre-registered** and **calibrated on the dev/calibration
split only**, never on eval.

### 16.3 / §4.5-equivalent — Compute accounting (matched expected NFE; NO optimistic accounting)

ADSR is compared at **matched expected total NFE**. The expected total NFE per
prompt under ADSR is the full sum, with **no optimistic accounting**:

```
E[NFE_ADSR] =  partial-trajectory cost to σ_c                 (every candidate pays this)
            +  surviving-trajectory full-completion cost       (CONTINUE / accepted DEFER)
            +  restart new-seed cost                           (each RESTART re-pays from σ=1)
            +  deferred-continuation cost                      (DEFER candidates carried to later σ)
```

A RESTART does **not** come free: the terminated partial trajectory's cost is
**sunk and counted**, and the new seed re-pays the full forward cost. The
baselines (Full BoN-8, BoN-4) are evaluated at the *same* expected NFE.
**Forbidden:** counting only the surviving candidates' cost, ignoring sunk
partial cost, or ignoring restart re-pay. The §1 `compute_metadata` (per-σ NFE)
makes the accounting exact.

### 16.4 Offline-first protocol (on the 4096-candidate pool)

**Validate ADSR offline first, then a small real-generation confirm.**

1. **Offline simulation (primary, 0 GPU-h beyond label derivation).** Treat each
   candidate's cached early-σ scores + EVPD output as the per-step verdict. A
   "RESTART" = **draw the next independent BoN-8 sibling of the same prompt** from
   the 4096-pool. Replay the §13 decision logic over the pool under the §16.3
   matched-NFE budget; measure final robust reward, semantic & lyric preservation
   (EN-vocal n=282 only), prompt-type-match rate, winner retention,
   false-restart rate. This makes the entire E6 main-method comparison runnable
   on cached data.
2. **Small real-generation confirm.** A small live ACE-Step run where RESTART
   actually launches a fresh seed (not a pool draw), to confirm the offline
   estimate holds when restarts explore genuinely new seeds beyond the 8-sibling
   pool. This is the only GPU cost of the active method beyond EVPD training.

The offline-first property depends on the §2.4 cache (early-σ decoded audio +
axis scores already stored) and the §2.5 relabel (vocal-presence label added to
each of the 4096 records).

### 16.5 Compute envelope (ADSR active method)

| Workload | Resource | Estimate |
|---|---|---|
| Quality-verifier training + ablations + risk calibration | CPU | ≤10 CPU-h, **0 GPU-h** (inherits §12 ETV envelope) |
| Vocal-presence label derivation on 4096 candidates (source separation reuses cached Demucs stems) | GPU (light) | small; cache-bound |
| **EVPD training** (small CNN / fine-tuned encoder, per-σ heads) | GPU | the main new GPU cost; small model, 4096 examples |
| ADSR offline simulation (E6 offline) on the pool | CPU | ≤ a few CPU-h |
| Small real-generation restart confirm | GPU | small live ACE-Step run |
| E2 / E8 human eval (reuses §6.3 harness) | human | per `EXPERIMENT_PLAN_EXEC.md` |
| Cross-backbone (E9, Stable Audio Open; parallel, non-gating) | GPU | parallel long-lead item |

The project's **5,400 GPU-h cap and scope-cut order** (§10 of the boundary
contract) remain the envelope. ADSR's active method is near-free offline; GPU is
spent on label derivation, EVPD training, the small real-generation confirm, and
the cross-backbone replication.

### 16.6 PLAN_CODE_AUDIT verification checklist (ADSR-specific)

When `/experiment-bridge` produces the ADSR implementation, the audit must verify:

1. **Decision logic** implements RESTART/DEFER/CONTINUE with **type-match
   priority** exactly as §13.2 (EVPD type error → restart precedes quality
   restart; content risk → defer, never early-reject).
2. **Restart = reallocation:** a RESTART launches a NEW independent seed (offline:
   the next BoN-8 sibling), with **no rollback/repair** of the terminated
   trajectory; seed independence is verified.
3. **Compute accounting is matched-expected-NFE with NO optimistic accounting**
   (§16.3): sunk partial cost + survivor full cost + restart re-pay + deferred
   continuation; baselines at the same expected NFE.
4. **Quality verifier** (§14.1) consumes ONLY §14.1 / §12.1 cached scalar
   features; **no leakage from `r_final`**; within-prompt grouping for
   pairwise/listwise; trained on dev256, evaluated on heldout256, split by
   prompt_id.
5. **EVPD** (§14.2) trains on the early Tweedie-clean mel-spectrogram with the
   §2.5 final vocal-presence label; reports per-σ AUC + **onset σ** + type-error
   prevalence; the off-the-shelf detector baseline is run; **EVPD is a learned
   audio net, not scalar features.**
6. **Vocal-presence labels** derived per §2.5 (source separation / SVD primary;
   Whisper `no_speech_prob` coarse pre-filter only) and **written to all 4096
   records**.
7. **Lyric metrics** computed ONLY on the EN-vocal `lyric_en_vocal_scorable`
   subset (n=282); instrumental sentinel masked; non-EN excluded; **never pooled
   into a headline number** (no recurrence of the 0.8432 contamination — the
   honest subset number is **0.682**).
8. **Offline-first** simulation runs entirely on cached
   `orbit-research/trajectory_candidate_dataset.jsonl` with no GPU re-decoding;
   the small real-generation confirm is a separate, labeled run.
9. **Tweedie-clean** early estimate uses the §4.1 effective-velocity contract
   (captured `trajectory_model_outputs[k]`), validated by reconstruction sanity.
10. **Thresholds** (`σ_c`, `τ_type`, `τ_q`, `τ_risk`, optional `ε`) are
    pre-registered and calibrated on dev/calibration only, never on eval.
11. **Two-factor ablation** (axis-awareness × restart-reallocation) and the
    **EVPD-branch on/off** ablation are reproducible (configs version-tagged).
12. **Baselines** (§15) Full BoN-8 / BoN-4 / random restart / raw ETP /
    learned-verifier selection / type-match restart all run at matched compute;
    raw-ETP@50-vs-BoN-4 ≈ +0.0036 is reported as the motivation, not a headline.
13. **Reward implementations** match published references (LAION-CLAP variant,
    Audiobox-Aesthetics, Whisper-large-v3, MERT version, Demucs htdemucs).
14. **Compute tracking** enforced against the 5,400 GPU-h cap; offline ADSR +
    verifier confirmed `0 GPU-h`.
15. **Evidence honesty:** no claimed ADSR / EVPD result is reported until E3/E6
    actually run; the contract is plan-stage for those.

Verdict `MATCHES_PLAN` requires all 15. `PARTIAL_MISMATCH` if any of
(5)/(6)/(10)/(11)/(12) deviate without scoped justification. `CRITICAL_MISMATCH`
if (1)/(2)/(3)/(4)/(7)/(15) are wrong — these are the method definition, the
no-optimistic-accounting guarantee, the no-leakage guarantee, the
lyric-population integrity, and the evidence-honesty guarantee the paper depends
on.

### 16.7 STOP-A checklist (ADSR)

- [ ] ACE-Step v1.5 checkpoint + inference path stable; **independent-seed
      (restart) sampling** available.
- [ ] Stable Audio Open cross-backbone path available but **not blocking**.
- [ ] Reward models run reproducibly and batched (CLAP, Audiobox, Whisper-large-v3,
      MERT, Demucs).
- [ ] Prompt set stratified and versioned; **lyric-bearing EN-vocal subset
      (n≈282) split out**; split by prompt_id.
- [ ] Canonical candidate pool
      `orbit-research/trajectory_candidate_dataset.jsonl` (4096) loadable.
- [ ] Tweedie-clean early estimate validated by reconstruction sanity (§4.1).
- [ ] **Vocal-presence label derivation** pipeline (source separation / SVD)
      designed; Whisper `no_speech_prob` used only as coarse pre-filter.
- [ ] **EVPD** training pipeline (early mel → final vocal presence; per-σ heads)
      specified; off-the-shelf baseline available.
- [ ] Quality-verifier (§14.1) training reuses cached features; 0 GPU-h path
      confirmed.
- [ ] Matched-expected-NFE compute accounting (§16.3) implemented;
      offline-first simulation harness on the pool implemented.
- [ ] Human-eval interface (E2 early vocal-presence listening + E8 blind A/B)
      reuses the §6.3 harness; supports type-correctness and lyric judgments.
- [ ] Compute tracking enforced from day 1 against the 5,400 GPU-h cap.

### 16.8 Cross-references

- `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` — PI-frozen full ADSR spec (the
  authority for this contract).
- `refine-logs/ADSR_REFRAME_BRIEF.md` — the reframe anchor (pivot, H1–H6, C1–C6,
  E1–E9, baselines, evidence status, claims-to-avoid).
- `refine-logs/FINAL_PROPOSAL.md` v4.0 — flagship ADSR proposal (claim chain).
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 — E1–E9 exec plan + go/no-go gates
  (Phases 1–7).
- `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum" — baselines /
  controls (type-match restart, random restart, raw restart, axis-deferred;
  EVPD-vs-off-the-shelf; two-factor ablation; EVPD-branch on/off).
- `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum" —
  hypotheses H1–H6 + claims C1–C6.
- `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` — the
  lyric-fix (0.682 EN-vocal n=282; instrumental sentinel masked).
- ETV archive `orbit-research/archive/etv_pre_adsr_20260604/METHOD_SPEC.md` —
  the full v3.0 ETV §12 contract + the verbatim M-PRM §§4.2–11 boundary stack.

### 16.9 Claims this contract must NOT support (anti-overclaim, ADSR §14)

This implementation must never be used to claim: music quality is always globally
determined; sections never matter; lyric can be evaluated over all prompts; ADSR
has distribution-free guarantees; ADSR universally generalizes to all flow
models; vocal presence is always trivially detectable at any σ; RL post-training
does not work. In particular: lyric numbers are EN-vocal-subset-only (0.682,
n=282), the EVPD onset σ is reported honestly (vocal presence may not be early at
every σ — if onset is late, the type-match branch is demoted to a later σ), and
no ADSR/EVPD result is reported before E3/E6 run.

---

## Document history

> ⚠️ The original v1.0 ~14-line version-history section was deleted in error
> during agent-driven doc-cleanup on 2026-05-20T07:30Z; full content not
> recoverable from conversation context. Subsequent entries are durable and must
> not be removed.

- **v1.0** — 2026-05-15 (estimated). Initial method specification.
- **v2.0** — 2026-05-15 PI-revised. Headroom-Gated M-PRM (Musically Structured
  Process Reward Modeling) — replaced S6 method.
- **v2.x patches (lost)** — content not recoverable; STOP-B-1 through STOP-B-4
  fix-passes referenced in `MANIFEST.md` rows. Substantive `/proposal-revise`
  Round 1 (2026-05-20) method changes: see `refine-logs/REVISION_REPORT.md`
  C2–C5 (H2/H4/H5/H6).
- **v2.2 backend-smoke update** — 2026-05-24. Accepted H3 FixedWin primary pivot,
  ACE-Step LoRA/GRPO backend smoke status, `flow_matching_surrogate` estimator
  caveat, Phase C0/C1 launch contract.
- **v3.0 — ETV pivot** — 2026-05-28. After C1 RL first-wave
  `COMMON_DEV_NO_CLEAR_WIN` and Track A `STRONG_CANDIDATE_MAIN_APPLICATION`, the
  paper-bearing method pivoted to **Early Trajectory Verifier (ETV)** — a learned
  `V_σ` verifier over a fixed candidate pool with risk-controlled pruning
  (ε ∈ {1,3,5}%). The §§1–11 M-PRM contract became the boundary-section
  implementation contract; the ETV contract was appended as §12.
- **v4.0 ADSR reframe (2026-06-04): ETV→ADSR pivot per
  `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`.** The project's third major
  framing (M-PRM → ETV → **ADSR**). Method reframed from prune/select to
  **compute reallocation via RESTART/DEFER/CONTINUE** (Axis-Deferred Speculative
  Restart). New: H2b presence-vs-content split; the learned **EVPD audio model**
  (early mel → final vocal presence; vocal-presence label via source separation;
  reported onset σ); type-match early-reject with priority; lyric as a
  first-class late-observable axis on the EN-vocal subset only (0.682, n=282).
  The ETV §12 `V_σ` verifier survives as the §14.1 lightweight quality verifier;
  raw Early-Tweedie pruning (Schedule A 0.9864 @ 0.500; raw-ETP@50 over BoN-4 ≈
  +0.0036) is demoted to a §15 same-compute baseline; the M-PRM §§4.2–11 RL stack
  is preserved as C6 boundary reference. Valid infra preserved: reward harness
  (§2) + `BaseAudioFeatures` cache, headroom audit (§3), ACE-Step σ convention +
  effective-velocity Tweedie-clean derivation (§4.1), prompt-id splits,
  `configs/eval/gate_v2.yaml.draft` calibration, the 5,400 GPU-h envelope, and
  the canonical reward set `orbit-research/trajectory_candidate_dataset.jsonl`.
  **Evidence status: plan-stage for the new method** — EVPD NOT trained,
  restart/ADSR NOT run (offline-simulable only), vocal-presence labels NOT yet
  derived; anchored on existing H1/H2/Track-A/Track-B/human/RL-boundary evidence.
  Pre-ADSR (ETV-era) version archived at
  `orbit-research/archive/etv_pre_adsr_20260604/METHOD_SPEC.md`.
