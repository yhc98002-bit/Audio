# Component Bundle Ladder — Headroom-Gated M-PRM (PI v2.0)

> *Systematic decomposition of M-PRM into incrementally-built component bundles.* Each rung is
> a runnable system with explicit inputs / outputs / control / expected signal / rollback
> condition. The plan-code audit verifies that the code respects the ladder order and that no
> rung silently merges multiple components.
>
> **Status.** v1.0 — Phase 1 of `/experiment-bridge`, 2026-05-15.
> **Linked artifacts.** `refine-logs/METHOD_SPEC.md` v2.0 §§ 3–5, `orbit-research/CONTROL_DESIGN.md`,
> `orbit-research/ALGORITHMIC_FORMALIZATION.md`, `orbit-research/ASSUMPTION_LEDGER.md` H1–H6.

---

## 0. Why this ladder

The user's CLAUDE.md instructs: **"First establish the ceiling of the simplest relevant
baselines on the benchmark... Run these baselines first, not after the proposed method."**

The ladder is the operational form of this rule. Each rung is the simplest system that
implements one additional mechanism. The decision rule "does rung k+1 outperform rung k?" tests
exactly one mechanism. The downstream paper makes claims only about mechanisms that the ladder
isolates cleanly.

---

## 1. Ladder summary

| Rung | Name | New mechanism added | Hypothesis touched | Compute (per ACE-Step Phase) | Paper role |
|---:|---|---|---|---:|---|
| **R0** | Base ACE-Step | none (reference) | reference | 50 GPU-h | reference baseline |
| **R1** | + CFG sweep | classifier-free guidance sweep | H1 | 80 | inference-time ceiling, 1-knob |
| **R2** | + BoN-N (raw reward) | inference-time search | H1 | 200 | inference-time ceiling |
| **R3** | + Robust BoN (R_lcb over Π) | robust evaluator | A17, A29 | 120 | tests reward-hackability |
| **R4** | + BoN+CFG | composite inference | H1 | 120 | combined inference ceiling |
| **R5** | + SFT-on-best (offline distillation of BoN) | offline amortization | A11 | 80 | offline-RL ceiling without reweighting |
| **R6** | + Robust Elite SFT (= former S6 Stages 0–3) | curriculum + robust LCB elite selection + weighted SFT | none specific (audit / C3 alt) | 240 | strongest offline-distillation baseline |
| **R7** | + Flow-DPO | offline preference fine-tune | A13 | 240 | offline preference ceiling |
| **R8a (STOP-B-1 split — canonical)** | + Outcome-GRPO-plain (vanilla Flow-GRPO + robust LCB reward only; **no curriculum, no lyric guard**) | online policy gradient, terminal reward only | A7, A8, A9 | 160 | online RL ceiling without process reward; **canonical matched-compute terminal control for C3** |
| **R8b (STOP-B-1 split — stronger)** | + Outcome-GRPO-guarded (R8a + Lagrangian lyric guard + optional headroom-weighted curriculum) | guard + curriculum on top of terminal RL | A7, A8, A9 + H5 hint | 160 | stronger terminal baseline; reported alongside R8a, NOT canonical |
| **R9** | + S7 sampler-control-only (frozen weights + controller) | sampler-policy controller | (no-weight-update falsifier) | 300 | weight-update necessity falsifier |
| **R10** | + Tweedie-clean intermediate decode (no PRM yet, just decode) | intermediate audio scoring | **A26**, H2 | 50 | reliability pilot |
| **R11** | + Section segmentation + locality probe (no PRM yet, just measurement) | musical structure measurement | **A27**, **A30**, H4 | 50 | mechanism gate |
| **R12** | + Stepwise-Tweedie process reward (= R8 + timestep PRM) | timestep credit unit | H3 (control) | 320 | T2I-PRM transfer baseline |
| **R13** | + FixedWin-Tweedie process reward | fixed-window credit unit | H3 (control) | 260 | temporal local credit |
| **R14** | + BeatWin-Tweedie process reward | beat-aligned credit unit | H3 (control) | 260 | rhythm-aware credit |
| **R15** | + LyricSpan-Tweedie process reward | lyric-aligned credit unit | H3 (control) | 260 | vocal-aware credit |
| **R16** | + FixedWin-Tweedie process reward (no extras) | **fixed-window credit unit** | **H3** | 350 | M-FixedWin-PRM core (no localization / guard / CVaR / curriculum) |
| **R17** | + Action-localized advantage (M-PRM with locality routing) | gradient localization | **H4** | 80 | mechanism: local credit |
| **R18** | + Constrained Lagrangian lyric guard | lyric-WER constraint | **H5** | 80 | mechanism: vocal safety |
| **R19** | + Calibrated CVaR aggregation | lower-tail aggregation | **H6** | 80 | mechanism: worst-section quality |
| **R20** | + Headroom-weighted curriculum | curriculum prompt sampling | (sample efficiency) | 50 | mechanism: efficient training |
| **R21** | **M-FixedWin-PRM full** (R20 = end of ladder) | all combined | C3 headline | 0 (already at R20) | conservative primary system |

Total per-rung compute: matches `CONTROL_DESIGN.md` §6 matched-compute accounting. The 5,400
GPU-h envelope of `FINAL_PROPOSAL.md` §7 covers the ladder plus reruns / reserve.

---

## 2. Rung specifications (the contract each implementation must satisfy)

### R0 — Base ACE-Step

- **Inputs:** prompt `c`, seed, default CFG (5.0 typical for ACE-Step v1.5).
- **Outputs:** waveform `a`.
- **Control:** N/A (reference).
- **Expected signal:** per-axis reward distribution under base policy.
- **Rollback condition:** if reward parser returns out-of-range values, halt; re-verify reward
  harness before proceeding.

### R1 — CFG sweep

- **Inputs:** R0 + CFG values `w ∈ {1.5, 3, 5, 7.5, 10}`.
- **Outputs:** per-(prompt, CFG, seed) waveforms.
- **Control:** R0.
- **Expected signal:** monotonic or non-monotonic CFG effect per reward axis.
- **Rollback condition:** if CFG variance dominates between-seed variance, increase seeds before
  declaring CFG effect.

### R2 — BoN-N (raw reward)

- **Inputs:** R1 outputs, reward function `reward_fn`.
- **Outputs:** top-1 sample per prompt per N.
- **Control:** R0.
- **Expected signal:** BoN curve elasticity (gain per doubling of N).
- **Rollback condition:** if BoN-1 ≠ R0 average, re-verify seed determinism.

### R3 — Robust BoN

- **Inputs:** R2 + perturbation set Π + reward ensemble.
- **Outputs:** top-1 sample per prompt under `R_lcb`.
- **Control:** R2 (raw BoN).
- **Expected signal:** robust gain ≤ raw gain (typically); if robust gain ≈ raw gain → reward is
  not hackable in current regime.
- **Rollback condition:** if R3 < R0, reward ensemble is broken; re-check.

### R4 — BoN+CFG

- **Inputs:** R1 × R2 (BoN over CFG sweep).
- **Outputs:** top-1 sample per prompt over (CFG, N) candidates.
- **Control:** R1 (CFG alone) + R2 (BoN alone).
- **Expected signal:** R4 ≥ max(R1, R2).
- **Rollback condition:** if R4 < max(R1, R2), composite is misimplemented.

### R5 — SFT-on-best

- **Inputs:** R2 elites per prompt + SFT loop.
- **Outputs:** SFT-trained LoRA adapter.
- **Control:** R2 inference-time + R0 base policy.
- **Expected signal:** R5 (1-sample inference) recovers some fraction of R2 (BoN-N inference).
- **Rollback condition:** if R5 == R0 (no SFT learning), check SFT loop convergence.

### R6 — Robust Elite SFT (= former S6 Stages 0–3)

- **Inputs:** R3 robust elites + headroom curriculum from R1/R2 stats + weighted SFT.
- **Outputs:** S6-trained LoRA adapter.
- **Control:** R5 (SFT-on-best raw) + R0.
- **Expected signal:** R6 > R5 on `R_lcb` if robust-LCB selection + curriculum help.
- **Rollback condition:** if R6 < R5, curriculum or robust selection is mis-implemented;
  validate against `ALGORITHMIC_FORMALIZATION.md` §1.5.
- **Note:** this rung implements the Codex Stage 10 winner (S6); the M-PRM paper must beat it.

### R7 — Flow-DPO

- **Inputs:** R3 robust elites as preference winners, R2 raw losers, Flow-DPO loop.
- **Outputs:** DPO-trained LoRA.
- **Control:** R6 (offline SFT) + R0.
- **Expected signal:** R7 ≥ R6 if preference signal is stronger than weighted SFT.
- **Rollback condition:** preference pair quality (winner vs loser margin) ≥ documented
  threshold; otherwise pairs are too noisy.

### R8a — Outcome-GRPO-plain (STOP-B-1 split, canonical)

- **Inputs:** R0 base + `R_lcb` (terminal robust-LCB reward only — **no curriculum, no lyric guard**) + Flow-GRPO loop (vanilla).
- **Outputs:** Outcome-GRPO-plain-trained LoRA. Canonical matched-compute terminal control.
- **Control:** R6 + R7 + R0.
- **Expected signal:** R8a > R6 if online RL helps over offline distillation.
- **Rollback condition:** training stability — if KL diverges, tune `λ_KL` per
  `ALGORITHMIC_FORMALIZATION.md` §1.8.
- **Why canonical:** With no curriculum and no lyric guard, R8a isolates the "online weight-update
  terminal-reward RL" mechanism from M-PRM's other components. C3's headline tie scenario is
  M-PRM vs R8a per `CONTROL_DESIGN.md` §3.4.

### R8b — Outcome-GRPO-guarded (STOP-B-1 split, stronger control)

- **Inputs:** R8a + Lagrangian lyric guard + optional headroom-weighted curriculum.
- **Outputs:** Outcome-GRPO-guarded-trained LoRA. Stronger terminal baseline (not canonical).
- **Control:** R8a (for the lyric-guard + curriculum delta).
- **Expected signal:** R8b > R8a on lyric-heavy strata if H5 / curriculum help even without
  process reward.
- **Rollback condition:** same training-stability checks as R8a; additionally check the
  Lagrangian λ-update path per `ALGORITHMIC_FORMALIZATION.md` §3.2 / §3.3.
- **Critical:** R8b ≈ M-PRM means the lyric guard + curriculum machinery is doing the work,
  not the process-reward + section credit. This demotes C3 to a weaker claim per
  `CONTROL_DESIGN.md` §3.4 R8b-tie scenario.

### R9 — S7 sampler-control-only

- **Inputs:** R0 frozen + controller search.
- **Outputs:** controller `ψ` (no weight changes).
- **Control:** R1 / R4 (best fixed CFG).
- **Expected signal:** R9 > R1 if learned sampler schedule beats fixed CFG.
- **Rollback condition:** controller search budget exhausted; if R9 ≈ R1, sampler control adds
  nothing beyond a single CFG knob.
- **Critical:** if R9 ≈ R21 (M-PRM), this is the major pivot per `ALGORITHM_TOURNAMENT.md`.

### R10 — Tweedie-clean intermediate decode (measurement only)

- **Inputs:** R0 trajectories + Tweedie formula + decoder D.
- **Outputs:** per-checkpoint intermediate waveforms `â_k`.
- **Control:** R0 final waveform.
- **Expected signal:** `Spearman(r(â_k), r(a_final)) ≥ 0.5` (REVISED 2026-05-20 R2 #6 from prior 0.35; binary gate) per axis at late / mid k.
- **Rollback condition:** if all axis-checkpoint pairs fail, pivot to terminal-reward study
  (H2 false) per `NULL_RESULT_CONTRACT.md` §2 Block B.1.
- **Reconstruction sanity check** is mandatory before rung is declared functional.

### R11 — Section segmentation + locality probe (measurement only)

- **Inputs:** R0 / R10 outputs + MERT/CBM segmenter + locality probe.
- **Outputs:** per-prompt segmentation + LocalityRatio distribution.
- **Control:** beat-tracker (sanity), fixed-window (sanity).
- **Expected signal (3-level MERT F1 gate per STOP-B-1 / STOP-B-2):**
  - **F1 ≥ 0.7 (strong pass)** → MERT-based section credit is primary in B.3 / Phase C.
  - **0.5 ≤ F1 < 0.7 (weak pass)** → proceed with CBM refinement on the trained-system side
    (Q-PRM-2); human-assisted oracle segmentation is reserved for Block D.hum / diagnostic
    appendix only (STOP-B-2 fix #7), never as a feature inside the trained policy.
  - **F1 < 0.5 (fail)** → demote section credit to ablation-only; fixed/beat/lyric-span become
    the credit-unit primary set in B.3.
  - median LocalityRatio ≥ 1.5 → action-localized advantage; ≥ 2.0 → strict masked gradients;
    < 1.5 → H4 fallback to global advantage.
- **Rollback condition:** see the 3-level branches above and `NULL_RESULT_CONTRACT.md` §2
  Block B.2 + §3 Block C.1.

### R12 — Stepwise-Tweedie process reward

- **Inputs:** R8 + R10 + per-checkpoint Tweedie reward at sampler-timestep unit.
- **Outputs:** Stepwise-Tweedie-trained LoRA.
- **Control:** R8 (outcome-only) + R10 (reliability gate).
- **Expected signal:** R12 ≥ R8 if process reward at timestep level helps.
- **Rollback condition:** if R12 < R8 and reliability gate passed, process-reward
  implementation is wrong; re-audit `ALGORITHMIC_FORMALIZATION.md` §3.1.

### R13 — FixedWin-Tweedie process reward

- Same as R12, but with `unit = "fixed_4s"`. Control: R12 (timestep PRM).

### R14 — BeatWin-Tweedie process reward

- Same as R12, but with `unit = "beat_window"` (beat-tracker). Control: R12 / R13.

### R15 — LyricSpan-Tweedie process reward

- Same as R12, but with `unit = "lyric_span"` (forced alignment on vocal stem). Control: R14.
- **Note:** lyric guard is active in this rung as well; the credit unit is lyric-span aligned.

### R16 — FixedWin-Tweedie process reward (= M-FixedWin-PRM core, no extras)

- Same as R12, but with `unit = "fixed_window"` (4 s non-overlapping windows). Control: R12 / R13 / R14 / R15.
- **Expected signal:** R16 is the conservative downstream credit-unit path selected by H3 for ACE-Step 30-40 s short-form generations.
- **Section diagnostic:** `unit = "section_window"` (MERT/CBM) remains a diagnostic / negative-control substitute, not the Phase C primary.

### R17 — + Action-localized advantage

- **Inputs:** R16 + locality probe decision (from R11) + action-localized GRPO loss.
- **Outputs:** action-localized-M-PRM-trained LoRA.
- **Control:** R16 (global advantage), R11 (locality probe).
- **Expected signal:** R17 ≥ R16 if H4 holds.
- **Rollback condition:** if locality probe failed (R11), this rung skips to global advantage
  (per `METHOD_SPEC.md` §9 H4-fallback).

### R18 — + Constrained Lagrangian lyric guard

- **Inputs:** R17 + Whisper-WER pipeline + Lagrangian update.
- **Outputs:** guard-active M-PRM LoRA.
- **Control:** R17 (no guard, R_music dominant).
- **Expected signal:** R18 ≥ R17 on lyric-heavy strata; R18 ≥ R17 on (R_music × R_lyric)
  Pareto frontier.
- **Rollback condition:** if R18 == R17 on lyric strata, H5 falsified; drop guard to ablation.

### R19 — + Calibrated CVaR aggregation

- **Inputs:** R18 + per-section advantages + CVaR formula (α = 0.30, **β = 0** for trained policy per R2 #11; β = 0.5 is offline scoring sensitivity only on saved per-section reward distributions, NOT a separately trained policy). NOTE: this CVaR β is DISTINCT from `beta_robust` (=0.5 in every rung config, unchanged) which weights the robust-reward LCB.
- **Outputs:** CVaR-active M-PRM LoRA.
- **Control:** R18 (mean aggregation).
- **Expected signal:** R19 ≥ R18 on broken-section rate.
- **Rollback condition:** if R19 == R18 on broken-section rate, H6 falsified; drop CVaR to
  ablation.

### R20 — + Headroom-weighted curriculum

- **Inputs:** R19 + audit stats from Phase A (rungs R0–R8).
- **Outputs:** curriculum-active M-PRM LoRA.
- **Control:** R19 (uniform `q(c)`).
- **Expected signal:** R20 ≥ R19 with fewer training steps; sample-efficiency claim.
- **Rollback condition:** if R20 < R19, curriculum is overfitting hard prompts; check
  `w_min` / `w_max` per `ALGORITHMIC_FORMALIZATION.md` §3.6.

### R21 — M-FixedWin-PRM full

- = R20. End of ladder. The full method.

---

## 3. Ladder run order

The ladder is **not** all-rungs-in-sequence. Some rungs are parallel-trainable (R12–R15 are
parallel; R6, R7, R8 are parallel; R17–R20 are sequential because each builds on the previous).

| Wave | Rungs | Reason | Halt gate before next wave |
|---|---|---|---|
| W1 (Days 1–10) | R0 + harness | env setup, reward parsers, prompt sets | env smoke (`DIAGNOSTIC_EXPERIMENT_PLAN.md` D0–D5) |
| W2 (Days 11–28) | R1, R2, R3, R4, R5, R6, R7, R8, R9 | Phase A audit | **Headroom gate** (`NULL_RESULT_CONTRACT.md` Block A) |
| W3 (Days 29–45) | R10, R11 | Phase B reliability + locality probe | **Reliability gate** (`NULL_RESULT_CONTRACT.md` Block B.1) + **Locality probe** (Block C.1) |
| W4 (Days 46–55) | R12, R13, R14, R15, R16 | Phase B credit-unit comparison | **Credit-unit gate** (`NULL_RESULT_CONTRACT.md` Block B.3) |
| W5 (Days 56–85) | R17, R18, R19, R20 → R21 | Phase C M-PRM training | training convergence; reward-pre-RL vs post-RL drift check |
| W6 (Days 86–105) | core ablations (per `CONTROL_DESIGN.md` §3.2) | Phase D ablations | each ablation interpretable; null-result discipline |
| W7 (Days 106–120) | human eval on R6, R8, R12, R16, R21 (top-3 + baselines) | Phase D human | rater agreement ≥ 0.6 |
| W8 (Days 121–134) | held-out reruns + SAO transfer | Phase D held-out + cross-model | held-out variance ≤ dev variance |
| W9 (Days 135–148) | paper writing + appendix | submission | paper claim wording stays inside `FINAL_PROPOSAL.md` §10 anti-overclaim list |

Each wave halts at its gate. **Do not** launch wave W3 if the W2 headroom gate fails (pivot to
saturation paper instead).

---

## 4. Rung-to-ablation map

The Phase D ablations (`CONTROL_DESIGN.md` §3.2) are each a **rung removal**:

| Ablation | Rung removed | Comparison |
|---|---|---|
| M-PRM w/o action localization | R17 removal | R21 vs R16 (R21 minus R17, R18, R19, R20 minus localization) |
| M-PRM w/o lyric guard | R18 removal | R21 vs (R17 + R19 + R20) |
| M-PRM w/o CVaR | R19 removal | R21 vs (R17 + R18 + R20) |
| M-PRM Section diagnostic | R16 substitution | R21 with the FixedWin component replaced by Section only for diagnostic interpretation |
| M-PRM w/o curriculum | R20 removal | R19 |
| M-PRM w/o robust reward | reward swap in all rungs from R8 onward | R21 with `R_lcb` → `mean(R_axes)` |

This is the cleanest single-variable isolation: each ablation is one rung removed or
substituted while all others stay fixed.

---

## 5. Audit checklist (for `PLAN_CODE_AUDIT.md`)

- [ ] Each rung's specification (§2) maps to a runnable script in `src/baselines/` or `src/m_prm/`.
- [ ] Each rung uses the same reward harness, prompt set, config schema, RUN_LEDGER format.
- [ ] Ladder order in code (`scripts/run_ladder.sh`) matches §3.
- [ ] No rung silently merges two components (e.g., R17 must not include CVaR; R18 must not
      include curriculum).
- [ ] Each ablation script is exactly one rung removal/substitution per §4.
- [ ] The ladder rung index appears in each rung's RUN_LEDGER entry.

A `PARTIAL_MISMATCH` is allowed if the missing pieces are scoped to the *current* probe / wave.
A `CRITICAL_MISMATCH` results from rungs being silently merged or skipped.

---

---

## 6. Document history

- **v1.0** — 2026-05-15. Phase 1 of `/experiment-bridge`. Authored against `METHOD_SPEC.md` §§ 3–5, `CONTROL_DESIGN.md`, `ALGORITHMIC_FORMALIZATION.md`, and the v2.0 H1–H6 + A26–A31 risk register.
- **v1.1 — STOP-B-2 consistency patch.** 2026-05-15. Rung **R8 split into R8a (Outcome-GRPO-plain canonical) + R8b (Outcome-GRPO-guarded stronger)**. §1 ladder summary row updated. §2 rung spec replaced single R8 section with R8a + R8b sub-sections. The wave assignment (§3) and rung-to-ablation map (§4) implicitly carry the split because they refer to R8 generically; consumers reading the ladder summary now see the split rungs directly.
- **v1.1-restoration-note** — 2026-05-20T08:00Z. Restored from agent-error deletion. Reconstructed verbatim from conversation context.

---

## 2026-05-28 ETV Pivot Addendum (Round 3)

Per the ETV pivot (`refine-logs/REVISION_INTAKE.md` Round 1), the R0–R21
ladder above remains the historical M-PRM RL bundle (now boundary-section in
the paper). The new paper's main ladder is the **inference-time selection
ladder** below. Each rung is a runnable selection method evaluated at
matched compute; the decision rule "does rung k+1 beat rung k at matched
compute under common robust-LCB?" tests exactly one mechanism.

### ETV ladder summary

| Rung | Name | New mechanism added | Hypothesis touched | Compute (per evaluation pass) | Paper role |
|---:|---|---|---|---:|---|
| **E-R0** | Full BoN-8 | upper-bound reference | n/a | cached Track A | reference |
| **E-R1** | BoN-4 (uniform random keep-4) | naive smaller-N | n/a | cached Track A subsample | matched-compute control (≈0.5) |
| **E-R2** | Random prune (keep-4 → keep-2 → final-top-1) | random schedule | n/a | cached Track A | random-prune control |
| **E-R3** | Raw ETP Schedule A (σ0.9 top-4 → σ0.7 top-2 → final) | early-σ ranking by raw reward | ETV2 | cached Track A | hand-designed schedule baseline |
| **E-R4** | Raw ETP Schedule B (σ0.8 top-4 → σ0.7 top-2 → final) | alternative σ entry | ETV2 | cached Track A | alternative schedule |
| **E-R5** | Raw ETP Schedule C (σ0.8 keep top-6 → final) | softer pruning | ETV2 | cached Track A | high-compute schedule |
| **E-R6** | Raw ETP bottom-prune σ0.7 (remove bottom-25 % → final) | bottom-tail pruning | ETV2 | cached Track A | conservative high-compute |
| **E-R7** | ETV-linear (logistic regression on early reward vector) | learned ranking, smallest model | ETV3 | <1 CPU-h | model-family floor |
| **E-R8** | ETV-GBDT (gradient-boosted decision trees, pairwise ranker) | learned ranking, primary head | ETV3 | <1 CPU-h | **PRIMARY ETV CONTRIBUTION** |
| **E-R9** | ETV-LambdaMART (listwise ranker) | within-prompt listwise objective | ETV3 + B4 | <1 CPU-h | listwise alternative head |
| **E-R10** | ETV-MLP (small MLP on same features) | nonlinear extension | ETV3 (optional) | <2 CPU-h | optional appendix |
| **E-R11** | ETV-RC-1% (risk-controlled, ε=1 %) | risk-aware pruning | ETV4 | <1 CPU-h | risk-control floor |
| **E-R12** | ETV-RC-3% | risk-aware pruning | ETV4 | <1 CPU-h | recommended setting |
| **E-R13** | ETV-RC-5% | risk-aware pruning | ETV4 | <1 CPU-h | aggressive setting |
| **E-R14** | ETV-AdaptiveCompute (confident-bad → prune; uncertain → continue; confident-good → retain) | adaptive σ-stage | ETV4 (extension) | <2 CPU-h | optional extension |

### ETV ablation dimensions (NEW)

| Ablation | What is dropped or varied | Question answered | Cost |
|---|---|---|---|
| Feature ablation: drop slope `r_{0.7} − r_{0.9}` | the rate-of-emergence feature | does emergence rate carry independent signal? | <0.5 CPU-h |
| Feature ablation: drop within-prompt rank | rank feature | does rank within prompt carry independent signal vs raw score? | <0.5 CPU-h |
| Feature ablation: drop prompt type (vocal/instrumental) | type feature | is the verifier regime-conditional? | <0.5 CPU-h |
| Feature ablation: drop CLAP/Audiobox/MERT individual scores | per-axis features | which reward axis carries the most predictive signal? | <0.5 CPU-h |
| Model-family ablation: linear vs GBDT vs LambdaMART vs MLP | model family | what is the minimum-complexity model that beats Raw ETP? | <2 CPU-h total |
| Risk-threshold ablation: ε ∈ {1 %, 3 %, 5 %} | risk tolerance | what is the Pareto curve between compute saved and false-negative? | <1 CPU-h |
| Per-σ-stage ablation: σ=0.9 alone vs σ=0.9+0.7 vs σ=0.9+0.8+0.7 | early σ checkpoints used | how many early σ checkpoints are needed? | <1 CPU-h |
| Stratification: vocal vs instrumental | prompt regime | is the verifier regime-conditional? | <0.5 CPU-h |

### Wave assignment (ETV ladder)

The ETV ladder runs entirely post-hoc on the cached Track A 4096-candidate
records. No new GPU work required. Total CPU compute: ≤10 CPU-h across all
rungs + ablations + risk-control sweep. Human eval (32–64 pairs) is the
only additional cost, separate from compute.

### Linkage

- Rungs E-R0..E-R6 reuse cached Track A schedules (`orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md`).
- Rungs E-R7..E-R14 are NEW; their formal pseudocode is in `ALGORITHMIC_FORMALIZATION.md` "2026-05-28 ETV Pivot Addendum".
- Failure routes per rung are in `NULL_RESULT_CONTRACT.md` "2026-05-28 ETV Pivot Addendum".
- Required controls per claim are in `CONTROL_DESIGN.md` "2026-05-28 ETV Pivot Addendum".

The R0–R21 ladder above is preserved as the M-PRM bundle and remains valid
for the boundary-section RL evidence (`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`).


---

## 2026-06-04 ADSR Pivot Addendum (Round 3)

> **Status.** v4.0 ADSR reframe, 2026-06-04. This addendum **SUPERSEDES** the
> "2026-05-28 ETV Pivot Addendum (Round 3)" above for the purpose of the
> component/ablation ladder. The ETV addendum and the R0–R21 M-PRM ladder are
> **retained** as historical / boundary material (do not delete): the R0–R21
> ladder remains the M-PRM RL bundle behind the C6 boundary result, and the ETV
> selection ladder (E-R0..E-R14) survives — but the *selection* rungs are now
> **baselines**, not the headline. The project pivoted ETV → **ADSR**
> (Axis-Deferred Speculative Restart): the lever is compute *reallocation* via
> **restart/defer/continue**, not pruning/selection within a fixed candidate pool.
>
> **Authoritative full specs live in the v4.0 stack — this addendum gives the
> domain-specific deltas + pointers only, not a re-derivation:**
> - `refine-logs/FINAL_PROPOSAL.md` v4.0 §3 (C1–C6), §4 (ADSR method, two learned components), §6 (E1–E9, esp. E6 ablation line: σ_c, thresholds, sequential vs. batch-speculative, restart budget, two-factor, EVPD on/off).
> - `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 (E3 EVPD study; E4/E5/E6 offline-first; go/no-go gates; matched expected-NFE accounting).
> - `orbit-research/CONTROL_DESIGN.md` v4.0 §2.1 (C2 baseline ladder C2-b1..b7), §2.2 (two-factor 2×2), §2.3 (EVPD-branch on/off), §3 (EVPD vs off-the-shelf controls), §8 (compute accounting), §10.B (ETV→ADSR control mapping).
> - `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum" (H1–H6, C1–C6).
> - Frozen plan: `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`; reframe brief: `refine-logs/ADSR_REFRAME_BRIEF.md`.

### A. What survives, what changes for this contract's domain (component/ablation ladder)

The ETV addendum's ladder is **two kinds of rung mixed under one label**: (i)
fixed-pool selection methods (BoN/random/raw-ETP — E-R0..E-R6) and (ii) learned
*ranking* heads on scalar features (E-R7..E-R14). Under ADSR these become two
distinct strata of a larger ladder, and three new strata are added on top:

1. **Selection rungs survive as baselines** (the fixed-pool, no-restart floor),
   not the headline. They are exactly the C2/C4 baseline family.
2. **Quality-verifier rungs survive** with the **frozen-constraint correction**:
   the verifier is **lightweight — ridge / GBDT / LambdaMART only. The MLP rung
   (former E-R10) is DROPPED from the main ladder** (ridge already saturates
   within-prompt NDCG ≈ 0.995; capacity is not the bottleneck — selection
   headroom is small *by construction*, which is precisely why ADSR bets on
   restart, not better selection). **No MLP** — the quality verifier stays
   ridge/GBDT/LambdaMART; EVPD is the only learned neural component.
3. **NEW: the only learned neural component is the EVPD** (Early Vocal-Presence
   Detector — a small CNN / fine-tuned audio encoder on the early Tweedie-clean
   mel). It gets its own architecture/baseline/onset ablations.
4. **NEW: restart rungs** (the actual ADSR mechanism: σ_c, thresholds,
   sequential vs. batch-speculative, restart budget).
5. **NEW: the two-factor ablation** (axis-awareness × restart-reallocation) and
   the **EVPD-branch on/off** control.

### B. ETV-rung → ADSR-ladder mapping (supersedes the ETV ladder summary table)

| ETV rung (2026-05-28) | ADSR role | Lives as / pointer |
|---|---|---|
| E-R0 Full BoN-8 | baseline (Pareto upper-bound) | C2-b1 / C4-c1 |
| E-R1 BoN-4 @ 0.5 | **critical no-learning, no-restart floor** | C2-b2 / C4-c2 |
| E-R2 Random prune | random-reallocation control | C2-b3 / C4-c4 |
| E-R3 Raw ETP Schedule A (σ0.9→0.7→final @ 0.500) | **the selection baseline** (former ETV headline; Track A **0.9864** reward fraction @ 0.500 compute) | C2-b5 / C4-c3 |
| E-R4..E-R6 Raw ETP B / C / bottom-prune σ0.7 | high-compute selection references (bottom-prune σ0.7 false-negative 0.0195) | C4-c3 |
| E-R7 ETV-linear / ridge | quality-verifier floor (lightweight) | E5 verifier family (C2-b6) |
| E-R8 ETV-GBDT (pairwise) | quality verifier — **was "PRIMARY ETV CONTRIBUTION", now a learned-*selection* baseline** | E5 verifier family (C2-b6) |
| E-R9 ETV-LambdaMART (listwise) | quality verifier (listwise head) | E5 verifier family (C2-b6) |
| **E-R10 ETV-MLP** | **DROPPED entirely** (violates the lightweight-verifier freeze; ridge NDCG ≈ 0.995, capacity is not the bottleneck) | removed — EVPD is the only learned neural component in ADSR |
| E-R11..E-R13 ETV-RC-{1,3,5}% | risk-controlled *selection* thresholds | survive as a verifier-side ε sweep; the headline risk knobs are now the ADSR restart thresholds (§C below) |
| E-R14 ETV-AdaptiveCompute | the seed of the ADSR decision logic (confident-bad→prune, uncertain→continue) | **generalizes into ADSR restart/defer/continue** (§C); now reallocates, not just prunes |

The single most load-bearing legacy number — **raw ETP@50 over BoN-4 ≈ +0.0036**
— is why selection cannot be the headline: it is the explicit motivation for the
restart-reallocation lever (`CONTROL_DESIGN.md` §4.2; `FINAL_PROPOSAL.md` §4).

### C. NEW ADSR rung strata (full specs in the v4.0 stack; deltas + run conditions here)

Each rung is a runnable system at **matched expected total NFE** (`CONTROL_DESIGN.md`
§8 / ADSR §4.5: partial cost to σ_c + surviving full cost + restart new-seed cost +
deferred-continuation cost; no optimistic accounting). All are **first validated
offline on the cached 4096-candidate pool** ("restart" = draw the next independent
pool candidate; 0 new GPU-h), then a small real-generation confirm (E6). Decision
priority is EVPD type-mismatch → early-quality-low → defer → continue.

**C.1 — Restart rungs (the ADSR mechanism; H3/H4).** Map to E6 (`FINAL_PROPOSAL.md`
§6 E6; `EXPERIMENT_PLAN_EXEC.md` E6; controls `CONTROL_DESIGN.md` §2.1).

| ADSR rung | New mechanism | Control / question | Pointer |
|---|---|---|---|
| A-R0 Random restart | chance reallocation | does reallocating compute *at all* help? | C2-b3 |
| A-R1 Raw restart (single global early score, restart, no axis-awareness, no defer) | restart on one scalar | isolates **axis-awareness + deferral** | C2-b4 |
| A-R2 Learned-verifier *selection* (no restart) | best fixed-pool selection | isolates **restart vs. better selection** (NDCG ≈ 0.995 ceiling) | C2-b6 |
| A-R3 Type-match restart (EVPD branch only; no quality/defer) | restart on predicted prompt-type mismatch | isolates the EVPD type-match lever (C3) | C2-b7 |
| **A-R4 ADSR (axis-deferred restart, full)** | restart/defer/continue + axis-awareness + EVPD branch | **the main method (C2)** | C2-b… / §2.2 |

**C.2 — ADSR restart-hyperparameter ablations** (replace the ETV per-σ / risk-threshold
rungs as the headline knobs; full grid in `FINAL_PROPOSAL.md` §6 E6 + `EXPERIMENT_PLAN_EXEC.md`):

| Ablation | Varied | Question |
|---|---|---|
| σ_c (restart-decision noise level) | early checkpoint at which the restart/defer call is made (σ ∈ {0.9, 0.8, 0.7, …}) | how early can restart be decided without sacrificing the late axes? |
| Decision thresholds | early-quality cutoff + EVPD-confidence cutoff + defer trigger | calibration of the restart/defer/continue boundaries |
| Sequential vs. batch-speculative restart | one-at-a-time vs. speculative parallel new seeds | which restart schedule is compute-optimal at matched NFE? |
| Restart budget | max number of new seeds drawn per prompt | the compute ceiling of reallocation |

**C.3 — Two-factor ablation (axis-awareness × restart-reallocation).** The 2×2
that isolates the two ADSR levers; the cells reuse the rungs above
(`CONTROL_DESIGN.md` §2.2):

| | Selection (fixed pool, no restart) | Restart (reallocate) |
|---|---|---|
| **Axis-agnostic** | raw ETP (A-R… = C2-b5) | raw / random restart (A-R1 / A-R0) |
| **Axis-aware** | learned-verifier selection (A-R2 = C2-b6) | **ADSR** (A-R4) |

- Restart-reallocation factor = (raw restart − raw ETP) and (ADSR − learned-verifier selection).
- Axis-awareness factor = (learned-verifier selection − raw ETP) and (ADSR − raw restart).

**C.4 — EVPD-branch on/off (within ADSR).** Run ADSR **with** and **without** the
EVPD type-match branch (decision-logic priority 1) on the same prompt set / early-σ
scores / σ_c / thresholds; the direct test of whether EVPD adds prompt-type-match
rate beyond quality + defer (`CONTROL_DESIGN.md` §2.3; maps to E6 ablation + C3).

**C.5 — EVPD component ablations (the one neural component; C3 / E3).** Full specs
in `EXPERIMENT_PLAN_EXEC.md` E3 and `CONTROL_DESIGN.md` §3.1:

| Ablation | Varied | Question |
|---|---|---|
| EVPD architecture | small CNN vs. fine-tuned pretrained audio encoder | minimal architecture that detects presence early |
| **Off-the-shelf detector on the EARLY estimate** (no early-σ training) | learned-vs-pretrained | **the key "why a learned model" control** — if it ties EVPD, demote to "use an existing detector on the early mel" |
| Off-the-shelf detector on the FINAL audio | upper bound on the clean-audio label task | how much of the gap is early-σ difficulty vs. intrinsic detector limit |
| EVPD onset-σ sweep | AUC at σ ∈ {0.9, 0.8, 0.7, 0.5, 0.3} | locates the **vocal-presence decidability onset**; tests H5 "type errors early-catchable" |

### D. Surviving feature/stratification ablations (verifier side, lightweight)

The ETV addendum's feature-ablation dimensions survive **for the lightweight
quality verifier only** (ridge / GBDT / LambdaMART — NO MLP): drop slope
`r_{0.7} − r_{0.9}`, drop within-prompt rank, drop per-axis (CLAP / Audiobox /
MERT) scores, drop prompt-type feature; model-family ablation now reads **ridge
vs. GBDT vs. LambdaMART (MLP removed)**; per-σ-stage ablation (σ0.9 vs σ0.9+0.7
vs σ0.9+0.8+0.7); and the vocal-vs-instrumental stratification — note the
type feature is now also realized as the *learned* EVPD axis (C3), so the
former "is the verifier regime-conditional?" question is partly answered by the
EVPD branch, not only by a scalar flag. Full list: `FINAL_PROPOSAL.md` §6 E5.

### E. Compute and wave assignment

The ADSR ablation core is **offline-first** on the cached Track A 4096-candidate
pool: the selection baselines, the restart simulation (E6-offline), the
verifier (E5), and most ablations require **no new GPU forward passes**. The
**only** new compute is (i) EVPD training (E3, ≤ ~30 GPU-h on cached early-σ mel +
vocal-presence relabeling) and (ii) the small real-generation confirm for E6/E7
(≤ ~150 GPU-h). Cross-backbone (E9) is parallel and does **not** gate submission.
Wave/gate structure: `EXPERIMENT_PLAN_EXEC.md` (Phases 1–7; E3/E6 are the
make-or-break gate).

### F. Evidence honesty (binding — do NOT report as results)

These rungs/ablations are **PLANNED**, not run:

- **EVPD is NOT trained** — no AUC, no onset σ, no EVPD-vs-off-the-shelf gap may be
  reported as existing. EVPD is the **only** learned neural component.
- **Restart / ADSR is NOT run** — A-R0..A-R4 are offline-simulatable on the 4096
  pool but the simulation has not been executed; no restart Pareto point exists yet.
- **Vocal-presence labels are NOT yet derived** — the EVPD ground truth (Demucs /
  Spleeter vocal-energy ratio / SVD; Whisper `no_speech_prob` coarse pre-filter
  only) and the retroactive relabel of the 4096 candidates are pending.
- **H2b (presence-vs-content split) is UNMEASURED** — the type-error vs.
  content-failure disentanglement of the lyric-zero candidates has not been computed.

The only foundation numbers that exist (and may be cited): Track A raw-ETP
Schedule A **0.9864** reward fraction @ 0.500 compute (regenerated 2026-06-04 on
the lyric-fix dataset; was 0.9858 on 2026-05-28; bottom-prune σ0.7 false-negative
0.0195); the lyric axis scored **EN-vocal only, 0.682 ETP@50, n=282** (248/282 =
88 % carrying signal; instrumental 1.0 sentinel masked, non-EN excluded); raw
ETP@50 over BoN-4 ≈ **+0.0036**; H1/H2 persistence; Track B globalness 0.861; the
C1/C6 RL boundary. **Do NOT claim ADSR results that do not exist.**

### G. Frozen constraints carried into this ladder

- Quality verifier = lightweight **ridge / GBDT / LambdaMART only**; **no MLP rung**
  in the main ladder; no large-model training.
- **EVPD is the only learned neural component** (small CNN / fine-tuned audio encoder).
- Numbers are frozen: lyric **0.682** EN-vocal **n=282**; Track A **0.9864**;
  cross-prompt-not-cross-content splits; per-specificity-stratum reporting.

The R0–R21 M-PRM ladder and the 2026-05-28 ETV selection ladder above remain
valid as boundary / baseline material and are not modified by this addendum.
