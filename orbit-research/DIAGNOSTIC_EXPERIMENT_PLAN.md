# Diagnostic Experiment Plan — Headroom-Gated M-PRM (PI v2.0)

> *Cheapest valid diagnostic before any expensive training.* This document specifies the
> minimal set of CPU-light / single-GPU-light runs that must pass before Wave W2 (Phase A audit)
> burns a single GPU-hour on production training.
>
> **Status.** v1.0 — Phase 1 of `/experiment-bridge`, 2026-05-15. **Replaces v1.0
> alias `TINY_RUN_PLAN.md`.**
> **Linked artifacts.** `refine-logs/METHOD_SPEC.md` §§ 1–4, `orbit-research/COMPONENT_BUNDLE_LADDER.md`,
> `orbit-research/ALGORITHMIC_FORMALIZATION.md`, `orbit-research/NULL_RESULT_CONTRACT.md`,
> `shared-references/semantic-code-audit.md` Diagnostic Run Audit prompt.

---

## 0. Why a diagnostic-run gate

Per CLAUDE.md: *"Before using GPU resources, ask: In which regime should this mechanism have
the largest headroom? Do not launch GPU experiments until this regime is clearly identified
and justified."*

This file answers that question with a finite, runnable checklist. Every M-PRM mechanism has a
documented regime; the diagnostic runs verify the implementation works **in the regime** before
we burn the 5,400 GPU-h budget. Diagnostic runs do **not** produce paper evidence — they produce
go / no-go signals for the audit wave.

---

## 1. Diagnostic envelope

| Constraint | Value |
|---|---|
| Compute cap (total) | 50 GPU-h (~5 % of Phase A budget) |
| Wall clock cap | 5 days |
| Hardware | 1× A800 (or A100), single node |
| Mode | sanity-only, no W&B paper logging |
| Output | `orbit-research/DIAGNOSTIC_RUN_REPORT.md` + audit |

---

## 2. Diagnostic runs (in order)

### D0 — Environment + dependencies smoke (no GPU)

**Purpose.** Confirm the toolchain is installed and importable.

**Steps.**
- Python venv with pinned deps.
- Import: `torch`, `torchaudio`, `transformers`, `diffusers`, `librosa`, `mir_eval`, `demucs`,
  `whisper` (or `faster_whisper`), `laion_clap`, `audiobox_aesthetics`, `mert`, ACE-Step + SAO
  inference wrappers.
- Tensor allocation on GPU: `torch.zeros(1).cuda()` succeeds.
- Audio I/O round-trip: `torchaudio.save` + `torchaudio.load` on a 1 s mono tensor recovers
  bit-equal.

**Success criterion.** All imports + tensor allocation + I/O succeed.

**Failure → action.** Surface the missing dep / version skew; fix env; rerun. Do not proceed to
D1.

**Cost.** Negligible (CPU-only).

### D1 — Model checkpoint loading (1 GPU)

**Purpose.** Confirm ACE-Step v1.5 + SAO 1.0 checkpoints load and produce *any* output.

**Steps.**
- Download / mount weights (HF cache).
- Instantiate ACE-Step v1.5 inference pipeline.
- Run 1 sample @ 30 s, default CFG, fixed seed, ACE-Step.
- Run 1 sample @ 10 s, default CFG, fixed seed, SAO.
- Save audio to `papers/diagnostic/d1_*.wav`.

**Success criterion.**
- Output audio waveform is non-silent (RMS > -40 dB).
- Output sample rate matches model spec (44.1 kHz both).
- No NaN / Inf in waveform.
- Reproducibility: same seed → bit-equal waveform across 2 runs.

**Failure → action.** Verify HF auth + license; check model card for inference snippet; if
ACE-Step v1.5 has special config, document. Halt before D2 if failure.

**Cost.** ~1 GPU-h.

### D2 — Reward harness smoke (1 GPU)

**Purpose.** Confirm each reward parser returns plausible values on known audio.

**Steps.**
- For each reward axis {CLAP-LAION, Audiobox-Aesthetics (4 axes), FAD, Whisper-WER on Demucs
  vocal stem, MERT section embedding}:
  - Run on the D1 audio outputs and on 3 publicly-shipped reference samples (from MusicCaps or
    Song-Describer).
  - Verify output is in documented range (CLAP cosine ∈ [-1, 1]; Audiobox per-axis ∈ [0, 1] or
    documented MOS scale; FAD ∈ [0, ∞); Whisper-WER ∈ [0, 1]; MERT cosine ∈ [-1, 1]).
- Compute `R_lcb(x, c)` over the perturbation set Π for one sample.

**Success criterion.**
- All reward axes produce in-range values on D1 + reference samples.
- `R_lcb` finishes within 60 s per sample (target: ≤ 30 s).
- Anti-hacking probes (silence_fraction, autocorr_repetition, off_prompt_distance,
  hf_artifact_score) return ≥ 0 and finite.

**Failure → action.** Most likely cause is mis-versioned reward model (CLAP variant, Audiobox
release, Whisper size). Document and pin to the same version used in published references.

**Cost.** ~1 GPU-h.

### D3a — Tweedie code-level derivation (STOP-B-4, pre-D3 prerequisite)

**Purpose.** D3 cannot pass by reconstruction sanity alone. Before declaring the Tweedie
identity validated, derive the *exact* formula used by ACE-Step from its training/sampler
source code (per the STOP-B-4 PI directive). The output is a saved derivation note that the
downstream `d3_tweedie_sanity.py` script consumes.

**Steps.**
1. Run `python scripts/d3a_tweedie_derivation.py` to:
   - Locate the ACE-Step / ACE-Step 1.5 install path (or warn if not installed).
   - Print the source of the flow head, sampler step(s), latent encoder/decoder, and any
     normalisation / scaling helpers.
   - Write a STUB at `orbit-research/TWEEDIE_DERIVATION_NOTE.md` if it does not exist.
2. The human (or next-bridge) fills in the four required slots in the derivation note:
   - **Flow target.** What does `v_θ` predict? (velocity field `dz/dt`, score `∇log p_t`,
     noise `ε`, or x₀-clean?)
   - **Time convention.** Is `τ ∈ [0, 1]` such that `τ = 0` is noise / `τ = 1` is data, or
     the reverse? Are inference timesteps stored increasing or decreasing?
   - **Latent scaling.** Is the latent normalised to unit variance? Is the DCAE latent
     scaled by a factor? What is the latent rate factor (Q-PRM-5)?
   - **Clean-target formula.** Express `x̂_1` (or the clean-latent estimate) as a function
     of `(z_τ, τ, v_θ)`. Default for rectified flow: `x̂_1 = z_τ + (1 − τ) · v_θ(z_τ, τ, c)`.
     Velocity-mode / score-mode / x0-mode alternatives if applicable.
3. The derivation note must end with `STATUS:` line that is one of `RESOLVED`, `AMBIGUOUS`,
   or `TBD`.
4. If `STATUS: AMBIGUOUS`, list the candidate formulas and run
   `d3_tweedie_sanity.py --candidate-formula <name>` for each. Pick the candidate with the
   best mean reconstruction fidelity and update the note to `STATUS: RESOLVED`. Do **not**
   advance to Phase B with `STATUS: AMBIGUOUS`.

**Success criterion.**
- `orbit-research/TWEEDIE_DERIVATION_NOTE.md` exists.
- Each of the 4 slots is filled (no TBD) and references at least one `file:function:line`
  in the ACE-Step source.
- Final line is `STATUS: RESOLVED`.

**Failure → action.**
- If D3a cannot be RESOLVED in the M0.5 wall-clock window: M1a may still proceed (M1a does
  not touch Tweedie), but Phase B / M2 is **hard-blocked**. The PI is notified.

**Cost.** ~5 GPU-h (mostly engineering wall-clock; minor GPU for candidate-formula tests).

### D3 — Tweedie-clean decode smoke + reconstruction sanity (1 GPU)

**Purpose.** Verify A26 (Tweedie identity validity).

**Steps.**
- Run 1 sample with full inference, save trajectory `{z_τ}_{τ ∈ T_inference}`.
- For each of 4 late-mid checkpoints `τ_k ∈ {0.7, 0.5, 0.3, 0.1}`:
  - Compute `z₁_hat = z_{τ_k} + (1 − τ_k) · v_θ(z_{τ_k}, τ_k, c)` (rectified-flow form).
  - Decode `â_k = D(z₁_hat)`.
  - Compute `r_aesthetic(â_k, c)`, `r_aesthetic(a_final, c)`.
  - Compute audio similarity (PESQ proxy or log-spectral distance) between `â_k` and `a_final`.

**Success criterion.**
- Spearman over 16 samples (one batch): `r_aesthetic(â_{τ=0.3}, c) vs r_aesthetic(a_final, c)`
  has positive trend (no formal gate; quantitative trend only at this scale).
- `â_k` is non-silent and audio-valid for `τ_k ∈ {0.5, 0.3, 0.1}`.
- Audio similarity to `a_final` improves monotonically as `τ_k` decreases.

**Failure → action.** Tweedie parameterization is wrong (Q-PRM-1). Try velocity-mode variant or
ACE-Step-specific formula. Repeat D3.

**Cost.** ~2 GPU-h.

### R050 — Informal mini-headroom probe (STOP-B-4, pre-M1a pause point) (~3 GPU-h)

**Purpose.** After D0–D5 pass, run a quick 32-prompt Base-vs-BoN-8 probe to confirm a
positive R_lcb trend exists *before* committing to the full ~850 GPU-h Phase A audit. This is
**informal and non-paper-bearing**; it does not replace M1a's 256-prompt authoritative gate.

**Steps.**
1. Take a stratified 32-prompt subset of the dev set.
2. For each prompt:
   - Run Base ACE-Step sampling with `seed=42`.
   - Run BoN-8 with the canonical robust LCB harness (`R_lcb` over reduced
     Π = {identity, crop}; the full Π is reserved for M1a R3).
3. Aggregate per-prompt deltas: `Δ_i = R_lcb(BoN-8_i) − R_lcb(Base_i)`.
4. Report `median Δ`, `mean Δ`, count(Δ > 0), count(Δ ≤ 0), and per-stratum medians.
5. Exit code:
   - **0** if `median Δ > 0` AND `count(Δ > 0) ≥ 16 / 32`.
   - **1** (pause-and-report) otherwise.

**Success criterion.** Median Δ > 0 AND ≥ half the prompts have positive Δ.

**Failure → action.** *Pause and report to the PI.* M1a's 256-prompt audit is still the
authoritative gate. The PI may decide to (a) proceed to M1a unchanged, (b) recalibrate
β_robust / λ_probe / Π and rerun R050, or (c) abort and pivot to a saturation-paper plan.

**Cost.** ~3 GPU-h on 1× A800.

### D4 — Section segmentation + Demucs + Whisper smoke (1 GPU)

**Purpose.** Verify A27 (MERT segmentation), A28 (Whisper WER), A29 (Demucs vocal stem).

**Steps.**
- Run MERT segmentation on D1 ACE-Step output.
  - Verify: 2–8 sections returned per ~60 s sample.
- Run Demucs htdemucs on D1 ACE-Step output.
  - Verify: vocal stem + 3 instrument stems produced, SI-SDR > 5 dB on a known reference song.
- Run Whisper-large-v3 on Demucs vocal stem.
  - Verify: transcript is non-empty; if metadata lyrics are available, WER < 1.0 (i.e., not
    pure garbage).

**Success criterion (smoke-level — STOP-B-2 fix #6 / #10 alignment).**
- MERT returns 2–8 sections.
- Demucs produces vocal stem with SI-SDR > 5 dB.
- Whisper produces non-empty transcript.

The smoke-level criterion above is intentionally weaker than the **production-level
3-level boundary-F1 gate** (`NULL_RESULT_CONTRACT.md` §2 Block B.2): strong pass F1 ≥ 0.7 / weak
pass 0.5–0.7 (CBM refinement on trained side, human-assisted oracle for diagnostic / human-eval
only) / fail < 0.5 (demote section credit to ablation). D4 only verifies that the segmenter
runs end-to-end — the 3-level F1 gate is exercised in Phase B (Block B.2), not at the D4
smoke level.

**Failure → action.** Try alternate segmentation (CBM); try simpler spectral mask; try Whisper
medium for speed. Document the choice in METHOD_SPEC.md update.

**Cost.** ~1 GPU-h.

### D5 — Mini Flow-GRPO smoke (1 GPU)

**Purpose.** Verify A7, A8, A9 (Flow-GRPO machinery works on ACE-Step backbone).

**Steps.**
- Take 4 prompts.
- Run mini-Flow-GRPO with `T_train = 5`, `G = 4`, `rl_steps = 8`, `λ_KL = 0.05`, `lr = 1e-6`.
- Reward = `R_lcb` with mock-up perturbations (Π reduced to `{identity, crop}`).
- Save loss, KL, reward trace.

**Success criterion.**
- Loss is finite (no NaN/Inf) for 8 RL steps.
- KL stays in [0, 5] (per `T_train`).
- Reward trace is non-monotonic but exhibits at least one upward delta.
- LoRA adapter checkpoint saves correctly.

**Failure → action.** If KL blows up: tune `λ_KL`. If NaN: switch to fp32. If reward never
moves: re-verify reward harness (D2). Document the smallest stable config.

**Cost.** ~3 GPU-h.

### D6 — Locality probe smoke (1 GPU)

**Purpose.** Verify A30 (locality measurable).

**Steps.**
- Take 4 prompts × 1 sample each.
- For each, segment with MERT, pick 1 random section.
- Compute `LocalityRatio = Δ(target section) / Δ(neighbor)` using Gaussian perturbation at
  amplitude 0.5 σ_z.

**Success criterion.**
- LocalityRatio is finite for all 4 prompts.
- Median LocalityRatio across 4 prompts is reported (not gated).
- If median < 1.0, halt the probe and report "neighbors changed more than target — perturbation
  amplitude or latent-time mapping is wrong"; otherwise proceed.

**Failure → action.** Tune perturbation amplitude; verify latent-time-to-audio-time mapping
(Q-PRM-5).

**Cost.** ~2 GPU-h.

### D7 — End-to-end mini M-PRM smoke (single GPU)

**Purpose.** Verify the full M-PRM pipeline works on a toy scale before Wave W5 burns
1,800 GPU-h.

**Steps.**
- 8 prompts × 8 RL steps × G = 4 group size.
- Tweedie decode at 2 checkpoints (one late, one middle).
- Section segmentation via MERT.
- Lagrangian lyric guard active (Whisper WER on Demucs stem).
- CVaR aggregation (α = 0.30, **β = 0** for trained policy per R2 #11; β = 0.5 reserved as offline scoring sensitivity, not a separately trained policy). DISTINCT from `beta_robust` (=0.5 in rung configs, unchanged).
- Action-localized advantage (use whatever locality probe D6 said; fall back to global if
  D6 < 1.5).

**Success criterion.**
- Full pipeline runs without crashing.
- Per-section advantage values are finite and not all zeros.
- Lagrange multiplier `λ` updates at least once over the 8 RL steps.
- LoRA checkpoint saves.

**Failure → action.** Localize the failure to one of D3–D6 + Lagrangian update; fix and rerun.

**Cost.** ~6 GPU-h.

### Summary

| Run | Purpose | Cost | Halt before |
|---|---|---:|---|
| D0 | env / deps | ~0 | D1 |
| D1 | model load + sample | 1 | D2 |
| D2 | reward harness | 1 | D3 |
| D3 | Tweedie reconstruction sanity | 2 | D4 |
| D4 | segmentation / Demucs / Whisper | 1 | D5 |
| D5 | mini Flow-GRPO | 3 | D6 |
| D6 | locality probe | 2 | D7 |
| D7 | end-to-end mini M-PRM | 6 | Wave W2 |
| **Total** | | **16 GPU-h** | < 5 days |

Reserve: ~34 GPU-h for re-runs / param sweeps within the 50 GPU-h envelope.

---

## 3. Regime checks (G12)

Per `semantic-code-audit.md` Diagnostic Run Audit §G12, before any failure is interpreted, the
audit must confirm the diagnostic regime preserved the mechanism's necessary preconditions:

| Mechanism | Necessary precondition | Regime check |
|---|---|---|
| Flow-GRPO (R8) | base policy has SDE noise variance | mini Flow-GRPO must operate in SDE mode (`η_τ > 0`); ODE mode does not test the mechanism |
| Tweedie decode (R10) | flow-matching parameterization | verify rectified-flow vs velocity vs score formula matches the backbone; reconstruction sanity check is the *gate* |
| Section segmentation (R11) | song has audible structure | use prompts with explicit chorus/verse hints; pure-noise or extremely short outputs (< 20 s) do not test this |
| Locality probe (R11 + R17) | latent rate factor is well-defined | confirm DCAE rate per ACE-Step model card; SAO uses ~64× per cite |
| Lyric guard (R18) | lyrics are present | only test on lyric-heavy prompts; instrumental prompts disable the guard by design |
| CVaR (R19) | multiple sections per sample | only test on samples with ≥ 3 sections; shorter samples cannot exercise the lower-tail mass |

The diagnostic-run audit (`DIAGNOSTIC_RUN_AUDIT.md`) verifies each regime check explicitly
before recommending PASS / FIX_BEFORE_GPU / REDESIGN_EXPERIMENT.

---

## 4. Decision rules

### 4.1 Phase A required (D0–D5 + D3a + R050) — gates Wave W2 launch

After D0–D5 + the STOP-B-4 pre-M1a checks complete:

| Verdict | Trigger | Next |
|---|---|---|
| PASS | all D0–D5 succeed; D3a derivation note STATUS=RESOLVED (or PI-acknowledged deferral with Phase-B hold); R050 median Δ > 0 with ≥ 16/32 positive prompts (or PI-acknowledged pause) | **launch M1a** Phase A.1 basic-headroom audit |
| FIX_BEFORE_GPU | one of D0–D5 failed AND fix is local (config / version / param) | local patch + re-run only the failed Dn |
| D3a UNRESOLVED but Phase B not yet started | derivation note STATUS=TBD or AMBIGUOUS | M1a may proceed in parallel; **Phase B / M2 is HARD-BLOCKED** until RESOLVED |
| R050 no positive trend (median Δ ≤ 0 or < 50 % positive) | informal probe negative | **pause-and-report to PI**; PI decides to proceed, recalibrate, or pivot |
| REDESIGN_EXPERIMENT | a regime check fails (e.g., D3a finds the Tweedie formula does not exist for this backbone, no audible structure on chosen prompts) | route back to METHOD_SPEC.md update + plan-only patch to this file |
| ERROR | audit cannot complete (Codex unreachable, regime check unanswerable) | halt; route to PI; explicit human acknowledgement before any Wave W2 launch |

### 4.2 Phase B/C required (D6, D7) — formally DEFERRED to the next `/experiment-bridge`

D6 (locality probe smoke) and D7 (end-to-end mini M-PRM smoke) exercise infrastructure that
does not exist in the current Phase A scaffold:

- D6 requires latent-span perturbation logic that is implemented as part of Phase B/C.
- D7 requires the full M-PRM pipeline (Tweedie + segmentation + locality + Lagrangian guard +
  CVaR + curriculum), all of which are part of Phase B/C.

The current bridge call therefore scopes D6 and D7 to **stub scripts** that print a clear
deferred message (see `scripts/d6_locality_probe.py` and `scripts/d7_mini_m_prm.py`). They
do not gate Wave W2 launch. They WILL gate the next bridge's main RL training (Phase C),
and the next bridge MUST replace the stubs with working implementations before any Phase C
training is allowed to launch.

Update history:
- v1.0 (Phase 1 of `/experiment-bridge`, 2026-05-15): D0–D7 all listed as required pre-W2.
- v1.1 (post-PLAN_CODE_AUDIT v1.0 CRITICAL_MISMATCH fix, 2026-05-15): D6 + D7 formally scoped
  to the next bridge per the Phase-A-only scope decision. D5 added to the required set as
  the sampling-side smoke (with deferred-real-training notice for R8).

---

## 5. Outputs

- `papers/diagnostic/d{0..7}_*.{wav,json}` — diagnostic audio + per-axis reward + per-step logs.
- `orbit-research/RUN_LEDGER.jsonl` — append start + end entries per Dn.
- `orbit-research/DIAGNOSTIC_RUN_REPORT.md` — narrative + per-Dn verdict.
- `orbit-research/DIAGNOSTIC_RUN_AUDIT.md` — independent audit verdict (PASS / FIX_BEFORE_GPU /
  REDESIGN_EXPERIMENT / ERROR).
- `MANIFEST.md` — append rows.

---

---

## 6. Document history

- **v1.0** — 2026-05-15. Phase 1 of `/experiment-bridge`. Authored against `COMPONENT_BUNDLE_LADDER.md`, `ALGORITHMIC_FORMALIZATION.md`, `NULL_RESULT_CONTRACT.md`, and `METHOD_SPEC.md` v2.0 §§ 1–4.
- **v1.1 — STOP-B-2 consistency patch.** 2026-05-15. D4 success-criterion section now explicitly states the smoke level vs the **production 3-level F1 gate** (the gate lives in Phase B Block B.2, not at the D4 smoke level). §4.1/§4.2 D0–D5 vs D6/D7 distinction already applied at STOP-B-1; no further changes here.
- **v1.2 — STOP-B-4 pre-M1a additions.** 2026-05-15. Added **D3a** (Tweedie code-level derivation; hard gate on Phase B, not M1a) between D2 and D3. Added **R050** informal mini-headroom probe (32 stratified prompts × Base vs BoN-8 with reduced Π; pause-and-report; NICE/informational; non-paper-bearing) after D5. §4.1 Decision rules table expanded with D3a UNRESOLVED and R050 no-positive-trend rows. Phase A / M1a launch preconditions now reference D3a + R050 in addition to D0–D5.
- **v1.2-restoration-note** — 2026-05-20T08:00Z. Restored from agent-error deletion. Reconstructed verbatim from conversation context.

---

## 2026-05-28 ETV Pivot Addendum (Round 3) — Six ETV experiments

The D0–D7 diagnostic gate above remains valid for the M-PRM RL backend
(now boundary-section in the paper); D3a Tweedie derivation is RESOLVED
post Track A 2026-05-28 (Track A's 4096-candidate validation is itself the
final reconstruction sanity check). The paper-bearing experimental program
now centers on the six experiments below, derived directly from
`revise.md` §6.

### E1 — Trajectory quality emergence

**Purpose**: establish that early-σ Tweedie estimates carry final-quality
signal on the same prompt set used for ETV training.

**Data**: cached Track A 4096-candidate records (`runs/early_tweedie_validation_512_bon8_20260527_full01/`), 512 prompts × 8 BoN candidates.

**Variables**: σ ∈ {0.9, 0.8, 0.7}; reward axes = primary common robust-LCB + auxiliary {aesthetic_pq, CLAP, MERT}.

**Metrics**:
- Spearman early-vs-final per (axis, σ).
- Winner-retention (early top-K contains final top-1) at K ∈ {1, 2, 4} per σ.
- Bottom-25 false-negative per σ.
- Stratified by vocal vs instrumental.

**Output**: trajectory-quality emergence curve (Spearman vs σ per axis), winner-retention table, stratified summaries.

**Status**: empirically supported by H2 (`PHASE_B1_H2_CONCLUSION_2026-05-23.md`) and Track A (`EARLY_TWEEDIE_PRUNING_VALIDATION.md`); paper-grade table re-derivation only.

**Compute**: 0 GPU-h, <1 CPU-h.

### E2 — Same-compute pruning comparison (MAIN EXPERIMENT)

**Purpose**: answer whether ETV beats BoN-K and raw Early-Tweedie Pruning at matched compute under common robust-LCB.

**Methods compared** (all run on the same 512 prompts × 8 BoN candidates cached set):
- E-R0 Full BoN-8 (reference, compute fraction 1.0).
- E-R1 BoN-4 (compute fraction 0.5).
- E-R2 Random prune (keep-4 → keep-2 → final; compute 0.5).
- E-R3 Raw ETP Schedule A (compute 0.5; Track A canonical).
- E-R4 Raw ETP Schedule B (compute 0.583).
- E-R5 Raw ETP Schedule C (compute 0.85).
- E-R6 Raw ETP bottom-prune σ0.7 (compute 0.883).
- E-R7 ETV-linear.
- **E-R8 ETV-GBDT pairwise** (PRIMARY).
- E-R9 ETV-LambdaMART.
- E-R11..E-R13 ETV-RC at ε ∈ {1 %, 3 %, 5 %}.

**Metrics**:
- reward_fraction (most important).
- compute_fraction.
- exact_winner_match.
- top_2_retention.
- false_negative.
- regret = `r_final(BoN-8 winner) − r_final(selected)`.

**Must answer**: is ETV better than BoN-4 at matched compute? If no, paper claim ETV3 retracts (raw ETP suffices; learned verifier shows no net benefit).

**Output**: same-compute Pareto curve (reward_fraction vs compute_fraction across all methods); winner-match table; false-negative table; regret distribution.

**Compute**: 0 GPU-h, ≤2 CPU-h (training + evaluation post-hoc on cached records).

### E3 — Cross-metric validation

**Purpose**: rule out reward circularity. ETV is trained on common robust-LCB; check whether the selection improvement transfers to non-robust-LCB metrics.

**Design**:
- Selection by ETV-GBDT (E-R8).
- Evaluation by {aesthetic_pq raw, CLAP semantic, lyric WER (Whisper-large-v3 on vocal stem), MERT coherence}.

**Metrics**: per evaluation-metric reward_fraction; gap vs Full BoN-8.

**Must answer**: does ETV gain at compute 0.5 persist on metrics it was NOT trained on?

**Output**: 4-row table (one per non-training metric); pass criterion = ETV ≥ Raw ETP Schedule A on at least 3 of 4 non-training metrics.

**Compute**: 0 GPU-h, <0.5 CPU-h.

### E4 — Human spot-check

**Purpose**: external validity for the matched-compute claim.

**Design**:
- 32 pairs (minimum; expand to 64 conditional).
- Comparisons: Full BoN-8 vs ETV@0.5; BoN-4 vs ETV@0.5; Random prune vs ETV@0.5; ETV vs Raw ETP Schedule A at matched compute.
- Stratified per vocal / instrumental / genre.

**Metrics**: overall preference; per-axis preference (musicality, prompt fit, vocal/lyric issue, worst-section quality).

**Must answer**: do human raters prefer ETV outputs over BoN-4 and over Raw ETP Schedule A at matched compute?

**Output**: paired preference table; Bayesian / mixed-effects analysis per pair; section-local A/B if applicable.

**Compute**: 0 GPU-h, ~10 listener-hours (32 pairs × 5 raters × 5 axes).

### E5 — Global quality mechanism

**Purpose**: explain WHY early-trajectory verification works — by demonstrating that quality differences are persistent across the clip (global, not isolated time-window defects).

**Design**: time-uniform diagnostic on cached H3 local proxy vectors and Track A candidates; reuses
`orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` analysis with light extensions:
- Top-quartile vs bottom-quartile reward-time curves per (axis, σ).
- Between-song vs within-song variance share.
- Globalness index (median between-share / (between + within) over primary cells).
- Crossing frequency.

**Metrics**: between-share, within/between ratio, sign consistency, crossing frequency, globalness index.

**Output**: top-vs-bottom reward-time curves (figure); globalness table (already canonical: median index 0.861).

**Compute**: 0 GPU-h, 0 CPU-h (already produced by Track B).

### E6 — Failure analysis

**Purpose**: increase credibility by surfacing where ETV fails.

**Sub-analyses**:
- Late bloomers: candidates that are NOT in early-σ top-K but ARE the final winner. Frequency? Common patterns (vocal vs instrumental, specific genres, prompt-type bias)?
- ETV mis-pruning: prompts where ETV-GBDT prunes the eventual top-1; analyze feature values at point of pruning.
- High-uncertainty samples: ETV's confidence calibration on different strata.
- Stratification: failure rate by vocal / instrumental / genre / song length.

**Metrics**: late-bloomer rate; mis-pruning rate; per-stratum failure rate; per-prompt-type calibration error.

**Output**: failure-case table; representative examples (3–5 cases described); per-stratum failure rate plot.

**Must answer**: are late bloomers rare (≤ 5 % overall)? If yes, supports the global-quality persistence claim.

**Compute**: 0 GPU-h, <1 CPU-h.

### Total ETV experimental budget

| Resource | Required |
|---|---|
| GPU-h | 0 (all post-hoc on cached Track A) |
| CPU-h | ≤10 (ETV training + ablations + risk calibration + all six experiments) |
| Listener-hours | ~10 (E4 human spot-check 32 pairs × 5 raters × 5 axes) |
| Wall-clock | ~3–5 days (mostly limited by human eval scheduling) |

### Boundary section (RL, demoted)

The M-PRM RL boundary-section evidence reuses cached `PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`. No new experiments.

### Linkage

- ETV ladder definition: `COMPONENT_BUNDLE_LADDER.md` "2026-05-28 ETV Pivot Addendum".
- ETV pseudocode: `ALGORITHMIC_FORMALIZATION.md` "2026-05-28 ETV Pivot Addendum".
- ETV-specific controls: `CONTROL_DESIGN.md` "2026-05-28 ETV Pivot Addendum" (ETV-c1..c8).
- Failure routes: `NULL_RESULT_CONTRACT.md` "2026-05-28 ETV Pivot Addendum".
- Assumption rows: `ASSUMPTION_LEDGER.md` "2026-05-28 ETV Pivot Addendum" (ETV1–ETV5 + B1–B5).


---

## 2026-06-04 ADSR Pivot Addendum (Round 3)

**Supersession.** This addendum **SUPERSEDES** the "2026-05-28 ETV Pivot
Addendum (Round 3) — Six ETV experiments" above. The project pivoted **ETV
(Early Trajectory Verification — prune/select a fixed candidate pool) → ADSR
(Axis-Deferred Speculative Restart — compute *reallocation* via restart)** per
the PI-frozen `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` and
`refine-logs/ADSR_REFRAME_BRIEF.md`. The ETV addendum is **retained as
historical / boundary context — do NOT delete it.** Where the two conflict,
this section governs. The six ETV experiments (E1–E6 of the ETV addendum) are
replaced by the **nine ADSR experiments E1–E9** below, staged across **Phases
1–7**.

The full ADSR mechanics and exec detail are NOT re-derived here — they live in
the promoted **v4.0 canonical stack**:

- `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 — **authoritative E1–E9 exec
  detail**, dataset construction (§0.5), prompt-level split (§0.6), offline-first
  ADSR protocol (§0.7), run-order DAG (§2), Phases 1–7 (§3), gates.
- `refine-logs/FINAL_PROPOSAL.md` v4.0 — ADSR proposal, C1–C6, H1–H6.
- `refine-logs/METHOD_SPEC.md` v4.0 — restart/defer/continue logic, EVPD,
  quality verifier, compute accounting §4.5.
- `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum" — ADSR
  baselines/controls and the two-factor (axis-awareness × restart-reallocation)
  ablation.
- `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum" —
  paper-bearing hypotheses H1–H6 and claims C1–C6.

**This file's role (domain-specific delta only).** This is the *diagnostic
experiment plan*: the cheapest-valid go/no-go checklist that precedes expensive
compute. The original **D0–D7 diagnostic gate** (§2 above) remains valid for the
M-PRM RL backend, which is now the **C6 boundary section**; D3a Tweedie
derivation stays RESOLVED post Track A (the 4096-candidate validation is itself
the final reconstruction sanity check). What changes is the *paper-bearing*
experimental program: it is no longer the six ETV experiments but the nine ADSR
experiments, with their diagnostic-grade purpose / design / metrics / gate
recorded here and the full exec detail deferred to the v4.0 exec plan.

---

### Evidence status (honor before reading any experiment below)

This is a **plan-stage diagnostic for the ADSR method**, anchored on existing
foundation evidence. Do NOT report planned work as results.

- **Foundation EXISTS (repurposed):** H1/H2 early-quality persistence (Phase A
  headroom `delta_sigma_bon_vs_base = 0.7549`; H2 STRONG_PASS, 128 prompts);
  Track B globalness `0.861`; **Track A raw-ETP Schedule-A `0.9864` @ `0.500`
  compute** (regenerated 2026-06-04 on the lyric-fix dataset; was 0.9858 on
  2026-05-28; bottom-prune σ=0.7 false-negative `0.0195`); **lyric `0.682`
  ETP@50 EN-vocal n=282** (248/282 = 88 % signal; instrumental 1.0 sentinel
  masked, non-EN excluded; `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`);
  large-scale human listening (H6); C1 RL boundary (no clear first-wave
  common-metric gain).
- **NOT yet run (forward-looking — never report as results):** **EVPD is NOT
  trained** (E3); **restart / ADSR NOT run** (E6 — offline-simulatable only on
  the existing 4096-candidate pool; real-gen confirm is new); **vocal-presence
  labels NOT yet derived** (Phase 1, §E3 / exec §0.5.6); **H2b presence-vs-content
  split UNMEASURED**; **cross-backbone NOT started** (E9; SAO appendix-only).
- ETV pruning (Track A) is now a **strong baseline (raw ETP)**, not the headline.

---

### Frozen constraints (carry into every experiment)

- **Two learned components, deliberately different sizes.** (a) The **quality
  verifier is lightweight** — scalar early features only; **ridge / GBDT /
  LambdaMART; NO MLP / no large model** (ridge already saturates within-prompt
  NDCG ~0.995; capacity is not the bottleneck). (b) **EVPD is the ONLY learned
  neural component** — a small audio model (CNN / fine-tuned pretrained audio
  encoder) reading the early Tweedie-clean mel; warranted because early-σ audio
  perception under heavy noise is a genuine, OOD learning problem.
- **Headline numbers stay frozen:** lyric `0.682` (EN-vocal, n=282); Track A
  Schedule-A `0.9864` @ `0.500` compute. Lyric-fix corrections (R2) hold:
  EN-vocal-only, cross-prompt-not-cross-content, per-specificity-stratum.
- **Splits by prompt_id, never candidate_id** (exec §0.6). Never mix instrumental
  prompts into headline lyric metrics.
- **Matched expected-NFE accounting, no optimistic accounting** (exec §0.7 /
  METHOD_SPEC §4.5): partial cost to σ_c + surviving full cost + restart
  new-seed cost + deferred-continuation cost. **Offline-first**, then a small
  real-gen confirm.

---

### ETV → ADSR experiment remap (this file's domain)

| ETV addendum (superseded) | ADSR (this addendum) | Change |
|---|---|---|
| E1 Trajectory quality emergence | **E1** Axis × σ observability matrix | Generalized: vocal-*presence* and lyric-*intelligibility* become **separate rows**; lyric stratum fixed (EN-vocal n=282). |
| E2 Same-compute pruning (ETV main) | **E4** Raw pruning & same-compute baselines | **Demoted to baseline.** Raw-ETP-over-BoN-4 ≈ +0.0036 (near-tie) now *motivates* restart, not the headline. |
| E3 Cross-metric validation | folded into **E6/E7** (semantic & lyric preservation on held axes) | Anti-circularity now carried by E2 (human) + multi-axis preservation in E6/E7. |
| E4 Human spot-check | **E8** Human spot-check (method preference) | ADSR vs BoN-k / random / raw restart; adds vocal-presence / type-correctness axis. |
| E5 Global quality mechanism | Track B globalness panel (parallel, no gate) | Stays as the mechanism panel feeding C1; no longer a numbered headline experiment. |
| E6 Failure analysis | folded into **E6** no-go tree + **E8/E9** | Late-bloomer / false-restart analysis now part of the ADSR main + robustness. |
| — | **E2** Human early→final validation (NEW headline) | License for restart; early vocal-presence listening; anti-circularity. |
| — | **E3** EVPD + prompt-type-error study (**NEW; only neural learning**) | Make-or-break with E6. |
| — | **E5** Learned quality verifier (lightweight) | Feeds the §4.4 priority-2/3 defer branches. |
| — | **E6** Axis-Deferred Speculative Restart (**MAIN METHOD**) | Restart / defer / continue; offline → small real-gen confirm. |
| — | **E7** Lyric-focused deferred eval (lyric-bearing vocal only) | C5; lyric-decidability onset vs ASR-transcribability onset. |
| — | **E9** Robustness + cross-backbone (parallel; no gate) | SAO replication; graceful fallback. |

---

### The nine ADSR experiments (diagnostic-grade summary; full detail → `EXPERIMENT_PLAN_EXEC.md` v4.0 §1)

Run-vs-planned tags: **[REUSES]** = post-hoc on cached Track A 4096-candidate
records (~0 GPU-h); **[NEW-RUN]** = new training / generation / listening.

#### E1 — Axis × σ observability matrix (FOUNDATION) [REUSES + small relabel]
- **Purpose:** establish axis-dependent observability (H2) — the scientific
  core. Rows: common/robust, aesthetic/production, **vocal presence (coarse)**,
  **lyric intelligibility (fine, lyric-bearing vocal subset)**, semantic_fit,
  coherence. Columns: σ ∈ {0.9, 0.8, 0.7, 0.5, 0.3, final}.
- **Design:** cached records; fix the lyric stratum first (sentinel pollution
  removed). Vocal-presence and lyric are **separate rows**.
- **Metrics:** Spearman early-vs-final, within-prompt NDCG, winner / top-k
  retention, axis preservation, bottom-25 false-negative.
- **Gate (make-or-break for H2b):** vocal-presence-onset **≪** lyric-onset, and
  lyric can stand as a late-observable headline axis. Pre-register early/late σ
  thresholds.
- **Status:** directionally supported by H2 + Track A; the vocal-presence row
  needs **labels not yet derived** (Phase 1). 0 GPU-h.

#### E2 — Human early→final validation (license for restart) [REUSES + small listening]
- **Purpose:** empirical license for *restart* and the defense against
  reward-circularity (H6).
- **Design:** write up the existing large-scale listening as a first-class
  result; add a small targeted early vocal-presence listening at σ ∈ {0.9, 0.8,
  0.7}. Distinct from the E8 method-preference check.
- **Metrics:** early-σ → final human-quality prediction; uniform-badness;
  late-bloomer rarity; early vocal-presence audibility.
- **Gate:** humans support early decidability (quality and presence).
- **Status:** core listening obtained (H6); early-presence listening is small new
  work. ~listener-hours.

#### E3 — Early Vocal-Presence Detector (EVPD) + prompt-type-error study (NEW) [NEW-RUN]
- **Purpose:** show vocal *presence* is early-decidable and gross prompt-type
  errors are early-catchable (C3, H5).
- **Design:** (1) ground-truth final vocal-presence per candidate (source
  separation Demucs/Spleeter vocal-energy ratio, or SVD; Whisper `no_speech_prob`
  coarse pre-filter only); (2) type-error prevalence (vocal→instrumental and
  vice versa); (3) **train EVPD** on early Tweedie-clean mel (σ ∈ {0.9,0.8,0.7});
  (4) disentangle existing lyric-zero into *type errors* (no voice) vs *content
  failures* (voice present, unintelligible) — the H2b split; (5) offline closed
  loop: does type-match restart raise prompt-type-match rate.
- **Metrics:** AUC, decidability **onset σ**, type-error prevalence, type-match
  rate after restart, false-restart-on-type, EVPD-vs-off-the-shelf gap.
- **Gate (make-or-break with E6):** EVPD AUC at some early σ is meaningfully
  above the off-the-shelf detector and above chance; else demote type-match to a
  later σ (NULL_RESULT_CONTRACT ADSR addendum §9) — ADSR can still run without
  the EVPD branch.
- **Constraint:** EVPD is the **only learned neural component** here.
- **Status:** **EVPD is NOT trained; vocal-presence labels NOT derived.** No AUC
  / onset number exists. ≤ ~30 GPU-h (mel-cache + small EVPD training).

#### E4 — Raw pruning & same-compute baselines [REUSES]
- **Purpose:** reproduce baselines and frame **why fixed-pool selection is
  low-stakes** (motivation for restart, H3).
- **Design:** Full BoN-8 / BoN-4 / random prune / raw ETP Schedules A,B,C +
  bottom-prune. Compute fractions ∈ {0.500, 0.583, 0.850, 0.883, 1.000}.
- **Metrics:** compute/reward fraction, winner_match, top-2 retention,
  false_negative, median regret.
- **Critical comparison:** raw ETP Schedule-A `0.9864` @ `0.500` vs BoN-4;
  delta ≈ **+0.0036**, median regret ≈ 0 → **raw ETP cannot be the headline**.
- **Gate to E6:** Track A canonical numbers reproduce within tolerance; the
  near-tie is confirmed as the restart motivation.
- **Status:** [REUSES] cached. 0 GPU-h.

#### E5 — Learned quality verifier (lightweight) [REUSES]
- **Purpose:** the *second* learned component; feeds the defer / safe-restart
  branches (NOT the headline).
- **Design:** targets = final robust-reward regression, final rank, top-1/2/4
  survival, safe-restart label, late-axis-risk label. Models: raw early score →
  **linear/ridge → GBDT / LambdaMART / pairwise (primary); NO MLP**. Calibrate
  thresholds on train+val 5-fold.
- **Metrics:** Spearman, NDCG, survival AUC, false-negative at calibrated
  thresholds, winner retention.
- **Framing / gate to E6:** useful iff it improves safe-restart calibration /
  late-axis defer / Pareto. Ridge already saturates within-prompt NDCG (~0.995);
  capacity is NOT the bottleneck — the explicit answer to "why not a transformer
  here" (contrast with EVPD, where audio under heavy noise IS a real learning
  problem).
- **Status:** [REUSES] cached. 0 GPU-h.

#### E6 — Axis-Deferred Speculative Restart (MAIN METHOD) [REUSES offline + NEW-RUN confirm]
- **Pre-condition:** E3 (EVPD) trained, E5 (verifier) calibrated, E1/E4
  confirmed.
- **Purpose:** the ADSR headline — compute *reallocation* via restart/defer/
  continue (C2).
- **Design:** run ADSR per METHOD_SPEC §4.4 priority logic **offline on the
  4096 pool** ("restart" = draw the next independent pool candidate), then a
  small real-gen confirm. Compare at **matched expected total NFE**: Full BoN-8 /
  BoN-4 / random restart / raw restart / learned-verifier restart / **type-match
  restart** / **full ADSR (with EVPD branch)**.
- **Metrics:** expected compute (matched-NFE, exec §0.7), final robust reward,
  semantic & lyric preservation, **prompt-type-match rate**, winner retention,
  false-restart rate, human preference (E8).
- **Ablations:** σ_c, thresholds, sequential vs batch-speculative, restart
  budget, **two-factor axis-awareness × restart-reallocation** (CONTROL_DESIGN
  headline), **with / without EVPD branch**.
- **Gate (Phase-3 make-or-break):** offline ADSR beats same-compute BoN-4 and
  random restart on `common_robust_lcb` (pre-registered ≥ 0.002 absolute
  reward_fraction gap, paired-bootstrap CI excluding zero) AND does not regress
  lyric/semantic preservation on the lyric-bearing vocal subset.
- **No-go tree** (→ NULL_RESULT_CONTRACT "2026-06-04 ADSR Pivot Addendum"):
  ADSR ≤ BoN-4 → fall back to an axis-observability + trajectory-analysis paper
  (C1 + E1 + E2 + Track B mechanism); ADSR ≤ random-restart-within-noise →
  investigate σ_c / decision logic; common-up-but-lyric-down → strengthen the
  defer branch; EVPD-branch-adds-nothing → keep type-match as a separate-axis
  C3 result, drop it from the decision headline.
- **Status:** **ADSR / restart NOT run.** No reward / Pareto number exists.
  0 GPU-h offline; ≤ ~150 GPU-h real-gen confirm on ≤ 64 stratified held-out
  prompts.

#### E7 — Lyric-focused deferred evaluation [REUSES offline + small confirm]
- **Purpose:** lyric as a first-class late-observable axis (C5).
- **Design:** on the **lyric-bearing vocal subset ONLY** (EN-core n=282 + stress
  arm), compare aesthetic-only restart / common-score restart / ADSR / Full BoN /
  BoN-k. **Never mix instrumental prompts into headline lyric metrics.**
- **Metrics:** lyric intelligibility (Whisper/ASR, EN-vocal n=282),
  **lyric-decidability onset vs ASR-transcribability onset** (mechanistic
  anchor), semantic fit, overall quality, false lyric-degradation rate; reported
  per stratum (clean-English-core / broader-lyric-bearing-vocal /
  multilingual-or-thin stress arm; multilingual uses language-matched ASR or is
  scoped).
- **Gate / success:** ADSR improves lyric/semantic preservation over naive
  (aesthetic-only) early restart while retaining most common-quality gains;
  too-noisy lyric subset → claim becomes "lyric observability is hard to
  measure", do not force a headline lyric result.
- **Status:** offline [REUSES]; lyric `0.682` anchor frozen. Folds into the E6
  real-gen budget. 0 GPU-h offline.

#### E8 — Human spot-check (method preference) [NEW-RUN listening]
- **Pre-condition:** E6 produced ADSR outputs.
- **Design:** 32–64 blind same-prompt A/B: Full BoN-8 vs ADSR; BoN-4 vs ADSR;
  random restart vs ADSR; raw restart vs axis-deferred restart (isolates
  axis-deferral). 5 raters/pair, ≤ 250 axis-judgments/rater/session. Rubric:
  overall, musicality, prompt fit, **vocal presence / type correctness**, lyric
  correctness/intelligibility, vocal artifacts.
- **Pass criterion:** mixed-effects — ADSR preference > 0.50 vs BoN-4 (CI
  excluding 0.50).
- **Gate / interpretation:** **human judgment overrides automatic reward** when
  they conflict; the automatic-pruning claim weakens to "automatic-metric Pareto
  only" (§9).
- **Status:** [NEW-RUN]. 0 GPU-h, ~10 listener-hours.

#### E9 — Robustness + cross-backbone (PARALLEL; does NOT gate submission) [NEW-RUN]
- **Design:** (a) **required cheap cross-regime within ACE-Step** [REUSES] —
  vocal vs instrumental, lyric vs non-lyric, genre buckets, BoN-8 vs BoN-16,
  easy vs hard; (b) **high-priority Phase-1-parallel cross-backbone** [NEW-RUN] —
  replicate **E1 + E3 + E6** on a second flow-matching backbone (Stable Audio
  Open), elevating an ACE-Step fact to a flow-matching principle.
- **Graceful fallback:** if SAO is not ready, fall back to cross-regime + an
  honest target-regime limitation. Cross-backbone is **pursued in parallel from
  the start and never gates submission** — not a Phase-5 afterthought.
- **Status:** cross-regime [REUSES] cached; **cross-backbone NOT started**
  (SAO appendix-only unless the parallel track delivers). Cross-backbone GPU is
  a separate parallel budget, off the critical path.

---

### Run-order constraint (load-bearing chain)

```
                 ┌──── E9 (cross-regime + cross-backbone; PARALLEL from Phase 1, no gate)
                 │
E1 ──┬── E2 ──┬── E3 (EVPD) ──┬── E6 (ADSR: offline → real-gen confirm) ──┬── E7 (lyric deferred)
     │        │               │                                          └── E8 (human spot-check)
     │        └── E4 (raw ETP baselines) ── E5 (quality verifier) ────────┘
     │
     └──────────────────────────────  (Track B globalness mechanism panel; parallel, no dependency)
```

**E1 → E3 → E6** is the load-bearing chain (observability → EVPD → ADSR). E4 +
E5 feed E6 in parallel. E2 gates the restart license but reuses existing
listening. E7/E8 follow E6. E9 runs parallel from Phase 1 and never gates.

---

### Phases 1–7 staging (ADSR §11; full detail → `EXPERIMENT_PLAN_EXEC.md` v4.0 §3)

The diagnostic-gate ordering for ADSR is the seven-phase staging below. Each
phase ends in a gate; no downstream phase commits non-trivial compute until its
gate passes.

- **Phase 1 — Repair lyric measurement, build observability, derive
  vocal-presence labels.** Fix lyric aggregation/sentinel; evaluate the
  lyric-bearing subset; **derive vocal-presence labels (NOT yet done)**; produce
  the axis×σ heatmap (E1). **Start second-backbone integration in parallel
  (long-lead).** Gate: can lyric be a late-observable headline axis, and is
  vocal-presence-onset ≪ lyric-onset?
- **Phase 2 — Human early→final validation (E2),** incl. early vocal-presence
  listening. Gate: do humans support early decidability (quality and presence)?
- **Phase 3 — Train EVPD + type-error study (E3) and ADSR offline simulation
  (E6 offline).** Gate (**make-or-break**): is vocal presence early-decidable,
  and does ADSR (with type-match) beat BoN-k / random under fair compute?
- **Phase 4 — Learned quality verifier + risk calibration (E5).** Gate: does
  the verifier improve decision quality?
- **Phase 5 — Human spot-check (E8).** Gate: does human judgment support ADSR?
- **Phase 6 — Robustness + cross-backbone replication (E9).** Gate: can we
  claim more than one narrow setting?
- **Phase 7 — Paper assembly.** Proposal/figures/method/limitations/
  reviewer-risk response.

---

### Compute envelope (diagnostic-grade)

| Resource | Required |
|---|---|
| GPU-h (offline-first core: E1, E4, E5, E6-offline, E7-offline) | ~0 (post-hoc on cached Track A 4096-candidate pool) |
| GPU-h (E3 EVPD training + relabel) | ≤ ~30 (small audio model on cached early-σ mel) |
| GPU-h (E6/E7 real-gen confirm) | ≤ ~150 (≤ 64 stratified held-out prompts) |
| GPU-h (E9 cross-backbone) | separate parallel budget; off the submission critical path |
| Listener-hours (E2 + E8) | ~10–15 |
| Wall clock | dominated by human-eval + cross-backbone scheduling |

---

### Boundary section (RL, demoted — C6)

The original D0–D7 diagnostic gate (§2 above) remains the diagnostic contract
for the M-PRM RL backend, now the **C6 boundary section** (LoRA/GRPO technically
feasible but no clear first-wave common-metric gain). It reuses cached
`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`. **No new RL experiments.** New
σ-axis RL is future work, not in the ADSR execution plan.

---

### Linkage (replaces the ETV-addendum linkage block above)

- ADSR exec detail (authoritative E1–E9, §0.5 dataset, §0.6 split, §0.7
  offline-first, §3 Phases 1–7): `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0.
- ADSR proposal / C1–C6 / H1–H6: `refine-logs/FINAL_PROPOSAL.md` v4.0.
- ADSR restart/defer/continue logic, EVPD, quality verifier, compute accounting:
  `refine-logs/METHOD_SPEC.md` v4.0 §4.
- ADSR baselines / controls / two-factor ablation:
  `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum".
- ADSR hypotheses / claims rows: `orbit-research/ASSUMPTION_LEDGER.md`
  "2026-06-04 ADSR Pivot Addendum" (H1–H6 + C1–C6).
- ADSR failure routes / no-go tree: `orbit-research/NULL_RESULT_CONTRACT.md`
  "2026-06-04 ADSR Pivot Addendum".
- Anchor sources: `refine-logs/ADSR_REFRAME_BRIEF.md` +
  `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`.
- ETV-era predecessor: the "2026-05-28 ETV Pivot Addendum" above (retained,
  historical / boundary). ETV-era canonical files archived at
  `orbit-research/archive/etv_pre_adsr_20260604/`.
