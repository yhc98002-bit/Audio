# Null Result Contract — Headroom-Gated M-PRM (PI v2.0)

> *Pre-registered interpretation of every diagnostic outcome.* For every experiment block, this
> document specifies: (a) what a null result tells us, (b) which hypothesis it falsifies,
> (c) what paper pivot it triggers, (d) what implementation or regime check must happen first
> before declaring a true null. **A null result that cannot be localized to a specific cause is
> a failed experiment design, not a finding.**
>
> **Status.** v1.0 — Phase 1 of `/experiment-bridge`, 2026-05-15.
> **Linked artifacts.** `refine-logs/FINAL_PROPOSAL.md` v2.0 §9 (Expected Outcomes), §6
> (Pre-Registered Hypotheses); `refine-logs/METHOD_SPEC.md` §9 (Method alternates / pivot routes);
> `orbit-research/ASSUMPTION_LEDGER.md` H1–H6; `orbit-research/CONTROL_DESIGN.md` §§5.1–5.3;
> `orbit-research/ALGORITHM_TOURNAMENT.md` "Failure pivots that revive earlier sketches".

---

## 0. The null-result discipline (CLAUDE.md guidance)

From the user's global CLAUDE.md:

> *"Before running an experiment, ask: 'What would a null result tell us?' If the answer is
> merely 'I would not know whether the mechanism, the benchmark, or the implementation failed,'
> stop and redesign the experiment until a null result can localize the failure to a specific
> cause."*

For each block below the question is answered explicitly. Where the answer is ambiguous, the
block is **not run** as paper-bearing — it is either demoted to a regime / control change or
deferred to a follow-up experiment plan after the cause-localization gap is closed.

---

## 0.5. Pre-M1a checks (M0.5 milestone — STOP-B-4)

The STOP-B-4 fix-pass added two pre-M1a checks between M0 and M1a. Their null-result
interpretation:

### Block M0.5a: R050 informal mini-headroom probe

**Hypothesis tested:** none formally — R050 is **informal**, non-paper-bearing. It is an
early-warning instrument for the PI before committing to the full ~850 GPU-h Phase A.

**Decision rule:** 32 stratified prompts × {Base seed=42, BoN-8 with R_lcb under reduced
Π = {identity, crop}}. Pass iff median Δ > 0 AND ≥ 16/32 prompts have positive Δ.

| Outcome | What it tells us | Falsified | Action |
|---|---|---|---|
| Positive trend (median Δ > 0; ≥ 50 % positive) | Reward signal moves the right direction at small scale; M1a is likely to find headroom | none | proceed to M1a |
| No positive trend (median Δ ≤ 0 or < 50 % positive) | Early warning that the reward harness may not move with BoN, OR the prompt subset is unusually saturated | none formally; H1a is unaffected because R050 is informal | **PAUSE and report to PI** before launching M1a. PI options: (a) proceed to M1a anyway because M1a's 256-prompt audit is the authoritative gate; (b) recalibrate β_robust / λ_probe / Π and rerun R050; (c) abort and pivot to saturation paper without M1a |

**Important null-pattern discipline.** R050 is *not* a hypothesis test. A negative R050 does
not falsify H1a — it only flags that M1a is more likely to surface saturation. Conversely a
positive R050 does not pre-commit H1a; the 256-prompt M1a audit is still authoritative.

### Block M0.5b: D3a Tweedie code-level derivation

**Hypothesis tested:** A26 (Tweedie identity validity for ACE-Step).

**Decision rule:** `orbit-research/TWEEDIE_DERIVATION_NOTE.md` final line is `STATUS: RESOLVED`,
each of the 4 slots ({flow target, time convention, latent scaling, clean-target formula})
is filled with non-TBD content and references at least one `file:function:line` in the
ACE-Step source.

| Outcome | What it tells us | Falsified | Action |
|---|---|---|---|
| STATUS: RESOLVED | Tweedie formula is derived + audited; D3 reconstruction sanity may run in production | none (A26 supported pending D3 confirmation) | proceed to D3 in production mode; Phase B / M2 is unblocked from the Tweedie angle |
| STATUS: AMBIGUOUS | Multiple plausible formulas remain after source inspection | none yet | run `d3_tweedie_sanity.py --candidate-formula <name>` for each candidate; pick the winner by reconstruction fidelity; update note to RESOLVED |
| STATUS: TBD | Note has not been filled in | none yet | M1a may still proceed; Phase B / M2 is HARD-BLOCKED until RESOLVED |
| ACE-Step source inspection reveals the model is NOT predicting velocity / score / noise / x0 in any standard form | The rectified-flow assumption underlying `tweedie_clean()` is wrong; A26 falsified | **A26 falsified** | **Phase B blocker**: no PRM claim can be made on ACE-Step without a corrected formula. Pivot to terminal-reward study (R8a Outcome-GRPO-plain as headline) per §6 H2 row |

**Important null-pattern discipline.** D3a is a *prerequisite verification*, not a primary
hypothesis test. A clean STATUS: RESOLVED does *not* confirm A26 — D3 reconstruction sanity at
real scale is still required. But STATUS: TBD or AMBIGUOUS *blocks* the production reconstruction
test from running, so the only way to confirm A26 is via the full D3a → D3 chain.

---

## 1. Phase A — Headroom audit (split into M1a + M1b per STOP-B-1)

### Block A.1: M1a basic-headroom audit (gates M1b)

**Hypothesis tested (STOP-B-2 fix #5 — H1 decomposed):** the umbrella H1 ("headroom exists
beyond base / CFG / S7") is operationally tested in M1a as **two sub-hypotheses**, both of
which must pass for the gate to succeed:

- **H1a — reward headroom.** BoN-8 or BoN+CFG beats base on `R_lcb` (held-out) by ≥ +0.25 σ.
  Falsified means the reward axis itself is saturated at the base policy.
- **H1b — weight-update headroom.** The H1a gain is not fully captured by CFG alone OR by S7
  sampler-control alone. Falsified means inference-time knobs already capture the available
  reward; weight updates are unnecessary.

The umbrella H1 register in `FINAL_PROPOSAL.md` §6 and `ASSUMPTION_LEDGER.md` is unchanged;
H1a/H1b are the operational decomposition.

**Compared systems:** R0 Base, R1 CFG sweep, R2 BoN-{4,8,16} (BoN-32 optional only if BoN-16 is
not saturated — STOP-B-2 fix #1), R3 Robust BoN, R4 BoN+CFG, R9 S7 sampler-control + Block
A.aux reward-human spot-check (n ≥ 32 on top-quartile gain).

**Decision rule:** Pass iff **H1a true AND H1b true AND human spot-check confirms**.

| Outcome | What it tells us | Hypothesis falsified | Paper pivot | Confirm before declaring |
|---|---|---|---|---|
| Pass — H1a true AND H1b true AND human confirms | Basic headroom + weight-update headroom both exist; reward-human alignment confirmed | none | continue to M1b | seed variance < between-method variance; CFG sweep saturates within budget; human spot-check on top quartile completed |
| Fail: H1a false (BoN-8 ≤ base + 0.25 σ) | True reward saturation: no measurable post-training gain available regardless of method | **H1a** | **Saturation/audit paper (C1 only).** Halt **M1b**. Headline: "no measurable RL/PT headroom on open FM audio/music beyond CFG / BoN / S7." | reward-model calibration validated; BoN curve plotted up to N=16 to confirm asymptote; BoN-32 considered only if BoN-16 is not saturated |
| Fail: H1b false via CFG (H1a true, gain captured by CFG sweep) | Reward headroom exists but CFG knob captures it; weight updates unnecessary | **H1b partial (CFG)** | "CFG sweep is sufficient" finding paper. Halt M1b. | CFG sweep granularity ≥ 5 values; per-prompt-stratum CFG variance checked |
| Fail: H1b false via S7 (H1a true, gain captured by S7 sampler-control) | Reward headroom exists but S7 sampler-control captures it; weight updates unnecessary | **H1b (sampler)** | "Sampler-control-only headroom dominates" — major paper pivot per `ALGORITHM_TOURNAMENT.md`. Halt M1b. | S7 search budget exhausted; matched-inference-compute confirmed |
| Fail: human spot-check disconfirms (H1a + H1b numerically pass but human-MOS does not agree) | Reward gains do not correspond to audible improvements | **A16 / A17** (reward-model trustworthiness) | reward-model recalibration loop before re-running M1a; do not start M1b | calibration set size ≥ 32; per-axis spot-check; cross-rater agreement |

**Implementation-side localization first.** Before declaring any failure mode:
1. Verify env smoke test passed (`DIAGNOSTIC_EXPERIMENT_PLAN.md` D0–D5).
2. Verify reward parsers return expected ranges on known audio.
3. Verify CFG-sweep granularity matches plan (`EXPERIMENT_PLAN_EXEC.md` Block A.1).
4. Verify prompt stratification matches metadata.
5. Verify seeds are deterministic across runs (variance ≤ documented tolerance).

If any of these fail, the experiment is rerun before any pivot decision.

### Block A.2: M1b post-training baselines (only if M1a passes)

**Hypothesis tested:** none directly. M1b produces strong baseline outputs (R5 SFT-on-best, R6
Robust Elite SFT, R7 Flow-DPO, **R8a Outcome-GRPO-plain**, **R8b Outcome-GRPO-guarded**) that
feed Phase D matched-compute comparisons.

**Outcome-GRPO split (STOP-B-1):**
- **R8a Outcome-GRPO-plain** = terminal robust-LCB reward only; *no curriculum, no lyric guard*.
  Canonical terminal-reward baseline. Used as the matched-compute terminal control in Block C /
  D.abl.
- **R8b Outcome-GRPO-guarded** = terminal reward + Lagrangian lyric guard + optional curriculum.
  Stronger terminal baseline; reported alongside R8a but NOT the canonical control.

**Decision rule:** No gate — M1b is a corpus-building wave. A failure here is an
implementation-side concern, not a hypothesis null.

| Outcome | What it tells us | Falsified | Action | Confirm before declaring |
|---|---|---|---|---|
| All rungs converge with stable trace, bounded reward-drift, no probe firing | M1b corpus ready for Phase D matched-compute controls | none | proceed to M2 | KL ∈ documented budget; reward-pre/post drift < threshold; anti-hacking probes do not fire post-RL |
| R8a (plain) or R8b (guarded) diverges / NaN | Implementation defect (KL blow-up / mixed-precision) | none (not a hypothesis null) | patch loop per §3 Block C.3; rerun the failed rung only | gradient norm logged; `λ_KL` tuned; FP32 fallback if needed |
| R8a converges, R8b diverges | Guard + curriculum interaction destabilises training | none | tune `λ_growth` / curriculum caps; rerun R8b | guard activation rate documented |
| R8a converges but R6 Robust-Elite-SFT crashes | Codex-era S6 5-stage pipeline misconfigured | none | local fix; rerun R6 | per-stage validation per `ALGORITHMIC_FORMALIZATION.md` §1.5 |

M1b cannot fail the headroom gate (the gate is M1a's job). If M1b results are unusable, the
fix is implementation-side, not a paper pivot.

---

## 2. Phase B — Tweedie reliability + Credit-unit comparison

### Block B.1: Tweedie reliability gate

**Hypothesis tested:** H2 (Tweedie-clean intermediate audio is reliably scored).

**Decision rule** (REVISED 2026-05-20 R2 #6 from prior 0.35): Keep an `(axis, k)` pair iff `Spearman(r_axis(â_k), r_axis(a_final)) ≥ 0.5` (binary gate) on a 64–128-prompt calibration set. Pass iff ≥ 2 useful axis-checkpoint pairs survive. Offline ρ ∈ {0.3, 0.5, 0.7} sensitivity reported on existing data per audit Fix #4 (0 GPU-h).

| Outcome | What it tells us | Falsified | Pivot | Confirm before declaring |
|---|---|---|---|---|
| Pass: ≥ 2 (axis, k) pairs survive across axes | Tweedie scoring is reliable enough for process reward | none | continue to Block B.2 | reconstruction sanity check (Tweedie decode on known-good final states produces audible audio at late-mid `k`); CLAP/Audiobox not artifact-firing on Tweedie audio |
| Fail: only lyric WER survives | Lyric reward is reliable but music axes are not | **H2 partial** | "Late-checkpoint-only process reward" — M-PRM degrades to lyric-axis-only PRM | A28 validated; Audiobox calibration on Tweedie audio re-run |
| Fail: only aesthetic survives | Aesthetic axis is reliable but coherence + semantic are not | **H2 partial** | Reduce process-reward axes; report "PRM only viable on aesthetic axis" | per-axis calibration set checked |
| Fail: 0 or 1 (axis, k) pair survives | Intermediate audio is not informative | **H2** | **Terminal/late-reward study (no PRM)**. Outcome-GRPO becomes central method per `METHOD_SPEC.md` §9 H2-fallback | Tweedie parameterization re-validated (Q-PRM-1); checkpoint timestep grid checked for late/middle bias |

### Block B.2: Section segmentation reliability (3-level gate per STOP-B-1)

**Hypothesis tested:** A27 (MERT/CBM segmentation reliability on ACE-Step output).

**Decision rule (3-level gate):** measure boundary F1 on 32 hand-labeled samples (5 raters,
genre-stratified). Don't kill the central M-PRM question solely because the segmenter is noisy.

| Outcome | What it tells us | Falsified | Pivot | Confirm before declaring |
|---|---|---|---|---|
| **Strong pass: F1 ≥ 0.7** | MERT segmentation is reliable | none | continue to Block B.3 with **MERT-based section credit as primary unit** | hand-labeling rater agreement ≥ 0.7; sample stratified by genre |
| **Weak pass: 0.5 ≤ F1 < 0.7** | Segmentation is noisy but usable | none for the C3 headline; A27 is partially supported | continue to Block B.3 with **CBM refinement applied on the trained-system side** (Q-PRM-2). **Human-assisted segmentation is reserved for oracle / diagnostic use only** (per-section human-eval rating in Block D.hum, methodological appendix) — *never* as a feature inside the trained policy or the credit-unit study's measurement pipeline (STOP-B-2 fix #7). M-PRM is *not* killed solely because the segmenter is noisy. | CBM segmenter loaded + benchmarked on trained-side; oracle-segmentation budget reserved separately for human-eval (≤ 20 rater-h, no compute); per-genre F1 reported |
| **Fail: F1 < 0.5** | MERT and CBM both under-perform | **A27** | Demote section credit to **ablation-only**. Block B.3 runs with **fixed/beat/lyric-span as the credit-unit primary set**, and "section as a fourth competitor" becomes a small-print row in the C2 study. C3 section-credit headline is demoted; C2 credit-unit study survives. | re-verify with whisper-vocal-stem-aware segmentation; check vocal-stem availability per A29; document the fallback in the paper as a positive finding (segmenter-noise sensitivity) |

### Block B.3: Credit-unit comparison

**Hypothesis tested:** H3 (section credit beats other units).

**Decision rule:** Section beats best non-section control by ≥ +0.08 Spearman on ≥ 2 of 3 axes
(musicality / coherence / prompt fit), identifies broken sections better than mean terminal,
holds on held-out.

| Outcome | What it tells us | Falsified | Pivot | Confirm before declaring |
|---|---|---|---|---|
| Pass: section wins ≥ 2 / 3 axes + held-out | Section credit is the right unit | none | continue to Block C (M-PRM training) | within-axis dev/held-out gap < 0.05 Spearman; random-window control loses to section |
| Fail: timestep ties / wins | Timestep credit is sufficient (image-domain PRM transfers) | **H3** | **Credit-unit negative study** — C2 becomes the headline contribution (still publishable) per `FINAL_PROPOSAL.md` §9 | timestep checkpoint grid checked; matched compute confirmed |
| Fail: fixed-window ties / wins | Local credit matters but segmentation does not | **H3 partial** | Report "any local credit works"; section-credit framing demoted | random-window control checked (must lose to fixed); matched compute |
| Fail: lyric-span wins (on lyric-heavy strata) | Lyric credit is the right unit on lyric-heavy strata; section credit wins on instrumental | **H3 partial** | Conditional H3: section unit on instrumental; lyric span on lyric-heavy. Paper reports the regime split. | stratum cross-tabulation confirms |
| Fail: random-window matches section | Credit-unit framing is invalidated entirely | **H3 strongly falsified** | C2 is not viable. Paper degrades to C1 + Outcome-GRPO methods note | random-window seed-controlled; matched mean width; reproduced across 2 seeds |

---

## 3. Phase C — M-PRM training and locality probe

### Block C.1: Locality probe

**Hypothesis tested:** H4 (latent locality holds; action-localized advantage is justified).

**Decision rule:** Median LocalityRatio ≥ 1.5 (action-localized) or ≥ 2.0 (strict masked).

| Outcome | What it tells us | Falsified | Pivot | Confirm before declaring |
|---|---|---|---|---|
| Pass: median ≥ 2.0 | Strong locality | none | use strict masked gradients | perturbation method ablation (Gaussian / resample / interpolate) confirms; per-genre check |
| Pass: 1.5 ≤ median < 2.0 | Moderate locality | none | use action-localized advantage (soft mask) | as above |
| Fail: median < 1.5 | Locality does not hold | **H4** | **Global advantage fallback** — M-PRM still defensible as aggregation/selection signal per `METHOD_SPEC.md` §9 H4-fallback | latent-time-to-audio-time mapping verified (Q-PRM-5); perturbation amplitude calibrated |

### Block C.2: M-PRM training and primary comparison

**Hypothesis tested:** C3 (M-PRM beats matched-compute baselines on per-section human
preference + worst-section quality with no lyric WER regression).

**Decision rule:** M-PRM > best non-M-PRM matched-compute control on (a) per-section human
preference (≥ 5 % preference rate) AND (b) broken-section rate (≥ 20 % relative reduction) AND
(c) lyric WER ≤ base + ε.

| Outcome | What it tells us | Falsified | Pivot | Confirm before declaring |
|---|---|---|---|---|
| Pass on all three | M-PRM is the headline method | none | continue to Block D ablations | matched-compute confirmed; reward-pre-RL ≠ reward-post-RL distribution drift bounded; anti-hacking probes do not fire on M-PRM output |
| Pass on (a) only | M-PRM helps preference but not broken-section or lyric | **H6** (if broken-section fails) or **H5** (if lyric regresses) | Pull the failing component to an ablation only | per-component contribution check |
| Tie with Outcome-GRPO | Process reward adds nothing over terminal | **C3** | C2 + C1 hold; method demoted | Outcome-GRPO compute-budget matched; lyric guard active in both |
| Tie with Stepwise-Tweedie | Section credit doesn't beat timestep credit at training time | **H3 (training)** | Credit-unit negative study at the training level; C2 (correlation-level) may still hold | Spearman vs training-time gain consistency check |
| Tie with Robust Elite SFT (S6) | Offline distillation matches online process-RL | **C3 vs S6** | S6 is headline alternate; paper compares both | matched compute; S6 5-stage pipeline correctly implemented |
| Tie with Flow-DPO | Offline preference matches online process-RL | **C3 vs offline** | Flow-DPO becomes headline alternate; preference-pair construction quality is the contribution | preference-pair quality validated |
| Tie with S7 | Sampler control matches weight-update RL | **major pivot** | "Sampler-control headroom dominates"; HMBC re-review at Stage 11 per `ALGORITHM_TOURNAMENT.md` | S7 search budget exhausted; matched inference compute |
| Lyric WER regresses | Lyric guard ineffective | **H5** | If guard was active: re-tune `λ_growth` / `ε`; if inactive in this ablation: report H5 confirmed in the no-guard ablation, drop confounded headline | guard implementation per `ALGORITHMIC_FORMALIZATION.md` §3.2 verified |
| Anti-hacking probe fires post-RL | M-PRM is reward-hacking | **A17 / robust-reward calibration** | recalibrate `λ_probe`; re-run training | probe versioned; threshold per-genre |

### Block C.3: M-PRM training fails to converge / diverges

| Outcome | Cause | Confirm |
|---|---|---|
| KL anchor diverges | `λ_KL` too small or `T_train` too short | tune per GRPO-Guard practice; rerun |
| Training loss NaN | gradient clipping / mixed-precision issue | full-precision rerun; LoRA rank check |
| Reward collapses | reward model out-of-distribution under M-PRM output | reward calibration; CVaR off (sanity); revert to base policy and check |
| Lagrange multiplier oscillates | `λ_growth` / `λ_decay` mis-tuned | tune update step; check rolling-window length |

These are *implementation* failures, not hypothesis nulls. They are routed via
`/experiment-bridge` patch loop, not via paper pivot.

---

## 4. Phase D — Ablations

Each ablation removes exactly one M-PRM component (per `ALGORITHMIC_FORMALIZATION.md` §5). The
null pattern is component-specific:

| Ablation | Hypothesis | Null result | Pivot |
|---|---|---|---|
| No action localization | H4 | locality matters less than global advantage | drop action-localization from the headline; it becomes a small-print finding |
| No lyric guard | H5 | lyric guard does nothing measurable | demote lyric guard to safety ablation; not a central claim |
| No CVaR (mean only) | H6 | CVaR adds nothing | drop CVaR from final method; mean aggregation |
| Fixed-window instead of section | H3 (training) | section unit doesn't beat fixed at training | C2 demoted; see Block B.3 above |
| Raw reward instead of robust LCB | none specific | calibration matters / does not | use whichever wins; document |
| No curriculum | none specific | curriculum gains nothing | drop curriculum from method; report as sample-efficiency note |

**Important null-pattern discipline.** A single-ablation negative result does NOT invalidate
the C3 headline as long as the ablation is removing something with an internally consistent
falsifier (e.g., H5 false means lyric guard is not needed, not that M-PRM is not needed). The
C3 headline survives any combination of H4 / H5 / H6 falsifications individually; it falls
only if H1a, H1b, H2, or H3 fail (the gates), or if the matched-compute baselines tie M-PRM.

---

## 5. Phase D — Human evaluation

**Hypothesis tested:** the M-PRM gain is human-perceptible at the per-section level.

**Decision rule:** M-PRM wins ≥ 55 % of pairwise comparisons against the second-best
matched-compute method on overall preference + worst-section quality, with at least 1,200
pairwise comparisons and 5 raters per pair.

| Outcome | What it tells us | Falsified | Pivot | Confirm before declaring |
|---|---|---|---|---|
| Pass | Automatic and human metrics agree | none | finalize paper claim | rater agreement (Krippendorff α ≥ 0.6); per-genre balance |
| Fail: automatic wins but human ties | Reward models are not aligned with human at the per-section level | **A16 / A17** | Recalibrate reward models; possibly retrain with new reward signal | calibration set; per-axis spot check |
| Fail: human wins but automatic ties | Automatic metrics under-credit M-PRM | none (claim holds) | report human-only headline with automatic as appendix | human-eval interface validated |
| Both tie | M-PRM is not human-perceptible | **C3** | Demote to C2 + C1; or report as conditional finding | matched-compute confirmed; human eval not under-powered |

---

## 6. Cascading failure pivots (when multiple gates fail)

This table is the canonical map from `FINAL_PROPOSAL.md` §9 to the published paper variant:

| Failed gates | Paper variant | Headline | Required artifacts |
|---|---|---|---|
| H1a only (saturation) | Saturation/audit paper (C1) | "No measurable reward headroom on open FM audio/music beyond CFG / BoN / S7" | C1 baseline suite + S6 + S7; reproducibility; reward-calibration audit |
| H1b only (no weight-update headroom) | Inference-time-only finding paper | "CFG / S7 captures the available reward headroom; weight-update post-training adds nothing" | C1 baseline suite + S7 controller search; matched-inference-compute confirmation |
| H2 only | Terminal-reward study | "Outcome-GRPO-plain (R8a, with constrained lyric guard via R8b control) improves FM music post-training; process reward is not viable due to Tweedie unreliability" | R8a + R8b + S6 + S7 baselines; Tweedie reliability null documented as the *finding* |
| H3 only | Credit-unit negative study (C2) | "Timestep / fixed / beat / lyric / section credit units are empirically equivalent at matched compute on open FM song generation" | All five Tweedie variants + section M-PRM at matched compute; per-axis correlation table |
| **A1 null** (former H4 only) | M-PRM with global advantage | Same headline as C3 but with "section reward as aggregation signal" rather than "local credit". **Paper claim INTACT** (component-only outcome per R2 C21). | M-PRM globally + locality probe documented as the falsifier |
| **A2 null** (former H5 only) | Drop lyric guard | Same headline as C3 but lyric guard becomes "we tested a lyric constraint; it was unnecessary" appendix. **Paper claim INTACT** (component-only outcome per R2 C21). | per-prompt-stratum lyric WER trace + vocal-presence red-flag alarm per audit Fix #12 |
| **A3 null** (former H6 only) | Drop CVaR | Same headline as C3 but with mean aggregation. **Paper claim INTACT** (component-only outcome per R2 C21). | broken-section rate appears as descriptive metric, not central claim |
| H2 + H3 | Fall back to S6 | "Active robust elite distillation is the right offline recipe for FM music; process reward is not yet viable" — S6 becomes the headline method per Codex Stage 10 audit | S6 5-stage pipeline + C1 + C2 (now negative) |
| **H1a + H3** (saturation + credit-unit negative — STOP-B-2 fix #9) | **C1 saturation/audit paper with Outcome-GRPO-plain (R8a) as a negative / control baseline**, not as the headline method | "Open FM music generation is at the inference-time ceiling; credit-unit choice is not the binding constraint. R8a is reported as a documented negative baseline to substantiate the saturation claim, not as a positive method." | C1 baseline suite + R8a (no curriculum, no guard) as the documented negative control + (B.3) negative |
| **All attempted mechanism hypotheses fail (STOP-B-2 fix #8)** | Pure measurement / reproduction paper | "An audit of the open FM music post-training literature on ACE-Step + SAO." State explicitly which hypotheses were *tested* (typically the prefix-subset of {H1a, H1b, H2, H3, H4, H5, H6} reached before the cascade halted upstream) vs which were *not reached* (because an earlier gate failed). Do **not** claim "all H1–H6 fail" — gate cascades commonly leave later hypotheses untested. | C1 baseline suite + reward-calibration audit + per-hypothesis tested-vs-not-reached note |

---

## 7. Implementation-failure exclusion

Per `semantic-code-audit.md` G12 (regime check), a "failed" experiment is only a hypothesis
null if the regime preserved the mechanism's necessary preconditions. The following are
*implementation / regime* failures and route through `/experiment-bridge` patch loop:

| Failure | Cause | Route |
|---|---|---|
| Sanity / config failure | implementation issue | local patch + re-audit |
| Diagnostic cannot exercise H<n> | regime mismatch | redesign diagnostic via `/experiment-plan` patch mode |
| Reward parser returns garbage | reward harness bug | fix + re-audit |
| Compute budget overruns by > 2× | misestimated compute | scope cut per `FINAL_PROPOSAL.md` §7 scope-cut order |
| Tweedie decode produces silence / noise | wrong parameterization (Q-PRM-1 unverified) | re-verify reconstruction sanity check |
| Demucs extraction fails per-genre | A29 violated | per-genre disable lyric guard; document |
| MERT segmentation produces > 8 or < 2 sections | A27 violated | parameter check before fallback to CBM (Q-PRM-2) |

None of these are paper pivots. They are coding tasks tracked in `EXPERIMENT_TRACKER.md`.

---

## 8. Final checklist

- [x] Every experiment block in `EXPERIMENT_PLAN_EXEC.md` has a null-result interpretation row.
- [x] Every hypothesis H1–H6 maps to at least one block null and one paper pivot.
- [x] Every paper pivot is grounded in `FINAL_PROPOSAL.md` §9 (Expected Outcomes).
- [x] Implementation / regime failures are routed via the patch loop, not via paper pivot.
- [x] Matched-compute scenarios preserve at least C1 publishability.
- [x] Cascading failures map to a still-publishable paper variant in §6 above.

---

---

## 9. Document history

- **v1.0** — 2026-05-15. Phase 1 of `/experiment-bridge`. Authored against `METHOD_SPEC.md` §§ 1–6 + `ASSUMPTION_LEDGER.md` H1–H6.
- **v1.1 — STOP-B-1 fix-pass.** 2026-05-15. §1 Block A.1 split into Block A.1 (M1a basic-headroom gate; halts M1b on fail) + Block A.2 (M1b post-training corpus; not gated; failures here are implementation-side). Outcome-GRPO split into R8a-plain (canonical terminal control) + R8b-guarded (stronger terminal baseline) documented in Block A.2. §2 Block B.2 promoted from single F1 ≥ 0.7 gate to a 3-level gate (strong / weak / fail) so a noisy segmenter does not alone kill the central M-PRM question. Pivot routes for H1–H6 and §6 cascading-failure pivots are unchanged.
- **v1.2 — STOP-B-2 consistency patch.** 2026-05-15. §1 Block A.1 now decomposes H1 into **H1a (reward headroom)** + **H1b (weight-update headroom)** at the operational level; umbrella H1 in FINAL_PROPOSAL §6 and ASSUMPTION_LEDGER unchanged. §2 Block B.2 weak-pass row clarified that **human-assisted segmentation is restricted to oracle / diagnostic use** (never as a feature inside the trained policy). §6 cascading-failure table reworded per fixes #8 and #9: "All H1–H6 fail" → "all attempted mechanism hypotheses fail" with the tested-vs-not-reached caveat; "H1 + H3 → C1 + Outcome-GRPO methods paper" → "H1a + H3 → C1 saturation/audit paper with Outcome-GRPO-plain (R8a) as a negative/control baseline". Added a new row for H1b-only-false (inference-time-only finding paper). The C3-survival discipline updated to reference H1a / H1b instead of umbrella H1.
- **v1.3 — STOP-B-4 pre-M1a additions.** 2026-05-15. Added new **§0.5 Pre-M1a checks** with decision rules for **R050 informal mini-headroom probe** (informal pause-and-report; NOT a hypothesis test) and **D3a Tweedie code-level derivation** (prerequisite for D3 reconstruction sanity; hard gate on Phase B / M2; not on M1a). Added a falsification row for A26 inside D3a (if ACE-Step source inspection rules out all standard flow targets, the rectified-flow formula assumption is wrong → Phase B blocked, pivot to terminal-reward study). No changes to §1–§9.
- **v1.3-restoration-note** — 2026-05-20T08:00Z. Restored from agent-error deletion (incorrectly removed during doc-cleanup pass). Restored content reconstructed verbatim from conversation context.

---

## 2026-05-28 ETV Pivot Addendum (Round 3) — ETV null-result routes

The H1/H2/H3 + A1–A5 null-result table above is retained as historical /
boundary-section routing. The paper-bearing claim chain now centers on ETV
(see `ASSUMPTION_LEDGER.md` "2026-05-28 ETV Pivot Addendum" ETV1–ETV5). The
table below specifies the null-result routing for each ETV-bearing claim
following the same null-result discipline: every null result must be
localizable to a specific cause before being declared a true null.

### ETV null-result routing

#### Block ETV-E2-c2 — ETV cannot beat BoN-4 at matched compute

**Hypothesis tested**: ETV3 (learned verifier beats uniform smaller-N sampling at matched compute).

**Null wording**: ETV-GBDT (E-R8) reward fraction ≤ BoN-4 (E-R1) reward fraction at compute fraction = 0.5 (within statistical noise).

**Pre-mortem causes a null could mean**:
- (a) The cached features (early reward vector + slope + rank + type) carry no learnable signal beyond uniform random keep-K.
- (b) The training set (256 prompts dev + 256 held-out) is too small for the model class.
- (c) The pairwise/listwise objective is wrong; pointwise regression might work better.
- (d) The within-prompt ranking task is fundamentally noise-dominated for this BoN size.

**Pre-localization required before declaring null**:
1. Run all four model tiers E-R7..E-R10 (linear/GBDT/LambdaMART/MLP). If MLP also fails, cause is NOT model class.
2. Run feature ablations. If dropping individual features doesn't reduce performance, cause is NOT feature subset.
3. Run E1 (trajectory quality emergence) sanity check. If E1 has Spearman ≥ 0.5 at σ=0.7, the signal IS there; ETV failure is a learning gap, not a signal gap.
4. Try inverse — does BoN-4 with a top-of-BoN-4 retention rule beat ETV? If yes, the task is genuinely degenerate.

**Pivot if all four checks pass and ETV still loses**:

→ **Paper claim retracts ETV3**. Headline becomes "Raw Early-Tweedie Pruning matches BoN-4 at matched compute; learned verifier shows no net benefit at this feature scale on this prompt distribution. Future work: richer features (frozen embeddings) or larger training corpus." The paper still has ETV1 + ETV2 + ETV5 as main claims (~4–6 pages) plus a "negative learned-verifier" section.

#### Block ETV-E2-c3 — ETV within noise of random prune

**Hypothesis tested**: ETV3.

**Null wording**: ETV reward fraction within statistical noise of Random prune (E-R2) at the same compute (≈0.5).

**Pre-mortem causes**: same as above plus (e) randomness in early-σ scoring is large relative to ETV's predictions.

**Pre-localization required**: same checks as above. Plus: report the test-set Spearman of ETV predictions vs final reward. If Spearman ≤ 0.1, ETV is learning nothing useful — escalate to feature scope review.

**Pivot if null persists**: same as Block ETV-E2-c2 — ETV3 retracts.

#### Block ETV-E2-c4 — Raw ETP Schedule A beats ETV at matched compute

**Hypothesis tested**: ETV3 (learned verifier beats hand-designed schedule).

**Null wording**: Raw ETP Schedule A (E-R3) reward fraction ≥ ETV-GBDT (E-R8) at compute fraction = 0.5.

**Pre-mortem causes**: (a) the hand-designed schedule already exploits the dominant signal (within-prompt early ranking); (b) the cached features add nothing beyond the σ=0.9 top-4 → σ=0.7 top-2 schedule.

**Pre-localization**: report feature importance from GBDT. If `r_lcb(σ=0.9)` carries >70 % of the importance, the model is mostly learning the schedule. Verify the schedule fits as a simple rule.

**Pivot if null persists**:

→ **Paper claim retracts ETV3 partially**. Keep ETV1 + ETV2 as main claims. Discuss in a "we tried to learn beyond the hand-designed schedule and could not match it" section — honest negative on the learned part. Still publishable as raw ETP main + ETV negative.

#### Block ETV-E3 — ETV gain reward-circular

**Hypothesis tested**: ETV3 transfer.

**Null wording**: ETV-GBDT (E-R8) beats Raw ETP Schedule A on robust-LCB (training axis) but underperforms on ≥ 2 of {aesthetic_pq, CLAP semantic, lyric WER, MERT coherence}.

**Pre-mortem causes**: (a) ETV overfit to robust-LCB peculiarities; (b) reward axes are misaligned with perceptual quality.

**Pre-localization**: report ETV vs Raw ETP per non-training metric; if ETV is within noise on 3 of 4 axes, the transfer is acceptable.

**Pivot if null persists**:

→ Paper claim narrows: "ETV improves robust-LCB selection but does not transfer cross-axis. Future work: multi-objective ETV training." Still publishable but narrower headline.

#### Block ETV-E4 — Human raters disagree with automatic metric

**Hypothesis tested**: ETV3 perceptual validity.

**Null wording**: in E4 paired comparisons, human preference for ETV@0.5 over BoN-4 is at or below chance (50 % ± 5 %).

**Pre-mortem causes**: (a) automatic robust-LCB does not correlate with perceptual quality at the small differences ETV achieves; (b) rater noise dominates the difference at 32 pairs.

**Pre-localization**: expand to 64 pairs conditional on borderline result; per-rater preference scatter to localize rater outliers.

**Pivot if null persists**:

→ Paper claim retracts to "automatic-metric selection improvement; perceptual benefit not established." This is the most expensive failure — re-running the paper around this null requires reframing the contribution as "automatic-metric Pareto" rather than "useful Pareto". Honest but narrow.

#### Block ETV-E6 — Late-bloomer rate is large (>10 %)

**Hypothesis tested**: ETV5 (global persistent quality).

**Null wording**: late-bloomer rate (final-top-1 candidates not in early-top-K at σ=0.7) > 10 % overall, OR > 20 % in any single stratum.

**Pre-mortem causes**: (a) some prompts have genuine late emergence; (b) some genres are time-local rather than globally persistent.

**Pre-localization**: stratify late-bloomer rate by vocal/instrumental/genre. Examine 5 representative late-bloomer prompts.

**Pivot if null persists**:

→ Modify the ETV3 risk-control target: ε ∈ {1 %, 3 %, 5 %} → ε ∈ {5 %, 10 %, 15 %} for affected strata. Add a stratum-conditional fallback: large-late-bloomer strata get a conservative bottom-prune schedule rather than aggressive ETV pruning. Paper claim ETV5 narrows: "for most strata, quality is globally persistent; for {stratum X}, quality is time-local — we recommend conservative pruning there." Honest stratified claim.

### Boundary RL section nulls (cited only, no new pivots)

The M-PRM RL boundary section reports `COMMON_DEV_NO_CLEAR_WIN` as a known
existing finding (`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`). No new null
routing required.

### Linkage

- ETV pivot anchor and simplicity discipline: `refine-logs/REVISION_INTAKE.md` "Anchor restatement".
- ETV ladder rungs E-R0..E-R14: `COMPONENT_BUNDLE_LADDER.md` "2026-05-28 ETV Pivot Addendum".
- ETV pseudocode: `ALGORITHMIC_FORMALIZATION.md` "2026-05-28 ETV Pivot Addendum".
- ETV controls: `CONTROL_DESIGN.md` "2026-05-28 ETV Pivot Addendum" (ETV-c1..c8).
- ETV experiments: `DIAGNOSTIC_EXPERIMENT_PLAN.md` "2026-05-28 ETV Pivot Addendum" (E1–E6).


---

## 2026-06-04 ADSR Pivot Addendum (Round 3)

> **Status.** v4.0 ADSR reframe, 2026-06-04. This addendum **SUPERSEDES the
> "2026-05-28 ETV Pivot Addendum (Round 3)"** above as the live null-result
> routing for the paper-bearing claim chain. The ETV addendum (Blocks
> ETV-E2-c2 … ETV-E6) and the §0–§7 M-PRM null tables are **retained as
> historical / boundary routing and are NOT deleted** — they remain the audit
> trail and the source of the foundation evidence (Phase A/B + Track A/B) on
> which ADSR anchors. Where an ETV null route still applies, it is re-pointed
> here, not re-derived.
>
> **What this file owns.** Null-result routing only: for each ADSR experiment
> block, what a null tells us, which hypothesis/contribution it retracts, what
> must be localized before a null is declared, and the still-publishable
> landing zone. The **full ADSR mechanics** live in the v4.0 canonical stack —
> do not re-derive them here:
> - method / decision logic / compute accounting: `refine-logs/METHOD_SPEC.md`
>   (ADSR contract), `refine-logs/FINAL_PROPOSAL.md` §4.
> - hypotheses H1–H6, contributions C1–C6, assumptions D1–D7:
>   `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum".
> - controls / two-factor ablation / EVPD-branch on/off:
>   `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum".
> - the canonical failure table this file expands:
>   `refine-logs/FINAL_PROPOSAL.md` §9 + ADSR plan
>   `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` §9.

### A. ETV → ADSR null-route remapping (one line each)

The ETV null routes do not vanish; they are re-homed onto ADSR's failure
modes. ETV was a fixed-pool **selection/pruning** story, so its nulls were all
variants of "the verifier does not beat a cheaper selector." Under ADSR
selection is known to be low-stakes (raw ETP@50 ≈ BoN-4 + 0.0036), so those
nulls are no longer paper-breaking — they are *expected* and *motivating*.

| ETV null block (above) | ADSR re-home |
|---|---|
| ETV-E2-c2 / ETV-E2-c3 (ETV ≤ BoN-4 / ≈ random) | **No longer paper-breaking.** This is the *premise* of ADSR-H3 (selection is low-stakes). The learned verifier is now the *lightweight* quality-verifier baseline (E5), not the headline. Re-homed to Block ADSR-E5 below. |
| ETV-E2-c4 (raw ETP ≥ ETV) | Same: confirms selection is saturated → motivates restart. Re-homed to Block ADSR-E5 / ADSR-E4. |
| ETV-E3 (ETV gain reward-circular cross-axis) | Re-homed to Block ADSR-E7 (lyric/semantic preservation) + the E2 human early→final license (anti-circularity). |
| ETV-E4 (humans disagree with automatic metric) | Re-homed to Block ADSR-E8 (human spot-check overrides reward). |
| ETV-E6 (late-bloomer rate large) | Re-homed to Block ADSR-E1/E6 (persistence H1; restart-license) — late bloomers now threaten the **restart** license, not just pruning. |

### B. ADSR null-result routing (live, paper-bearing)

The headline now rests on **C2 (ADSR restart — main method)** and **C3 (EVPD
type-match — second lever)**, with **C1 (axis×σ observability) + C5 (lyric
late-axis) + C6 (RL boundary)** as the always-publishable floor. Evidence
honesty (mandatory, ADSR brief "EVIDENCE STATUS"): **EVPD is NOT trained;
restart/ADSR is NOT run (offline-simulatable only on the 4096 pool);
vocal-presence labels are NOT yet derived; H2b presence/content split is
UNMEASURED.** Every block below is therefore a *pre-registered* null route for
a forward-looking experiment — none of these nulls have been observed, and no
ADSR result may be reported as obtained until the block runs. The only
already-obtained numbers carried in are foundation evidence: Track A raw-ETP
Schedule A **0.9864** @ 0.500 compute and the EN-vocal lyric **0.682** ETP@50
(n=282).

#### Block ADSR-E1 — Axis ordering flat / persistence weak

**Hypotheses tested:** H1 (early persistence), H2 (axis-dependent
observability — the scientific core), D5 (early/late assignment determinable).

**Null wording:** (a) *flat ordering* — Spearman early-vs-final and
winner/top-k retention are not materially higher for aesthetic/production &
vocal-presence than for semantic/lyric across σ ∈ {0.9, 0.8, 0.7}; no clean
early/late split emerges. (b) *weak persistence* — bottom-prune false-negative
materially exceeds the Track A 0.0195 baseline, or top-k retention is low.

**Pre-localization required before declaring null:**
1. Confirm the lyric stratum is the fixed EN-vocal subset (instrumental 1.0
   sentinel masked, non-EN excluded) — a flat ordering driven by sentinel
   pollution is an implementation failure, not a hypothesis null (route via §7).
2. Confirm vocal-presence and lyric-intelligibility are scored as **separate
   rows** (H2b); collapsing them masks the expected vocal-presence-onset ≪
   lyric-onset gap.
3. Re-derive the Track A persistence numbers on the same lyric-fix dataset to
   confirm the foundation has not drifted.

**Pivot if null persists:**
- *Flat ordering* → no axis-deferral benefit. Demote to a **single-threshold
  early-pruning paper** (fall back toward the raw-ETP baseline). C2's
  axis-deferred framing weakens; C1 still publishes as a (negative)
  observability map. (Anchor: FINAL_PROPOSAL §9 row "H2 ordering flat";
  ASSUMPTION_LEDGER H2/D5 falsification.)
- *Weak persistence* → the **restart license collapses** (H1). Fall back to
  per-candidate selection only — still publishable as observability +
  trajectory analysis (the H3 "selection is low-stakes" route). This is the
  ETV-E6 late-bloomer null re-homed: a large late-bloomer rate now means a
  restart could discard a future winner, so it threatens C2's license, not
  just pruning. Stratify late-bloomer rate by vocal/instrumental/genre and
  inspect 5 representative late-bloomer prompts before declaring.

#### Block ADSR-E3 — Vocal presence NOT early-decidable (EVPD onset late / AUC low)

**Hypotheses/contributions tested:** C3 (prompt-type match as early-decidable
axis), H2b (presence vs content split), H5 (type errors early-catchable), D1
(vocal-presence label derivable), D2 (EVPD audio model).

**Null wording:** EVPD AUC at early σ ∈ {0.9, 0.8, 0.7} is low (near an
off-the-shelf clean-audio detector or chance), OR the **vocal-presence
decidability onset σ is late** (only resolves near the lyric onset), OR the
presence/content split of the lyric-zero candidates does not separate *type
errors* (no voice → no transcription) from *content failures* (voice present,
unintelligible).

**Evidence-honesty guard:** EVPD is **NOT trained** and vocal-presence labels
are **NOT yet derived**. This block cannot run until D1 (label derivation pass:
Demucs/Spleeter vocal-energy ratio or SVD on the 4096 pool; Whisper
`no_speech_prob` is a coarse pre-filter only) and D2 (EVPD training) complete.
Until then, no AUC / onset σ may be reported.

**Pre-localization required before declaring null:**
1. **Label first.** A low AUC against noisy labels is a label problem, not a
   detector problem. Spot-validate the D1 labels against the E2
   early-vocal-presence human listening before blaming EVPD. Falsified label
   reliability → scope the type-match claim to high-confidence labels (D1
   falsification route), not a C3 retraction.
2. **EVPD is the only learned neural component** (small CNN / fine-tuned
   pretrained audio encoder). Confirm the training actually exercised the
   early-σ-OOD regime (early Tweedie-clean mel input, not clean audio); an
   underfit/clean-trained EVPD is an implementation failure (route via §7), not
   a hypothesis null. **Do not** substitute an MLP or any heavier quality-side
   model — the frozen constraint keeps the quality verifier lightweight
   (ridge/GBDT/LambdaMART, no MLP); EVPD is the one sanctioned neural net, and
   "EVPD failed" must mean the audio-perception problem is genuinely hard at
   early σ, not that the wrong model class was used.
3. Report the off-the-shelf-clean-audio-detector baseline alongside EVPD; if
   the off-the-shelf detector also fails early, the cause is the early-σ
   regime, not the EVPD design.

**Pivot if null persists:**
→ **Demote the type-match branch to a later-σ check; report the onset
honestly.** A mid-trajectory onset still saves the back half of compute, so
the value likely persists — but the C3 claim must follow the *measured* onset,
never assert "vocal presence is trivially detectable at any σ" (explicit
anti-overclaim, ADSR plan §14). If presence is not separable-early from content
(H2b null), collapse vocal-presence into the late lyric axis and route via the
C3-demotion path. The closed-loop type-match-rate result (E3 step 5 / control
C3-c7 = C2-e1/e2) is the application check: if type-match restart does not raise
the final selected output's prompt-type-match rate, the EVPD branch is
decorative — C2 reduces to C3 or C3 is dropped, both still honestly publishable.
(Anchor: FINAL_PROPOSAL §9 row "Vocal presence NOT early-decidable"; CONTROL_DESIGN
§2.3 EVPD-branch on/off + §C3 controls.)

#### Block ADSR-E4 — Raw ETP barely beats BoN-4 (expected; NOT a failure)

**Contribution tested:** C4 (compute–quality Pareto; raw-ETP baseline point).

**Null wording:** raw Early-Tweedie pruning @50 compute ≈ BoN-4 (known delta
≈ +0.0036).

**Interpretation:** this is **expected, not a null.** It is the empirical
premise of ADSR-H3 (selection is low-stakes) and the reason ETV's headline was
demoted to ADSR's raw-ETP baseline. The carried-in foundation numbers (Schedule
A 0.9864 @ 0.500; random 0.9570 @ 0.500) already establish this point. No pivot:
a small raw-ETP-over-BoN-4 delta *motivates* the restart contribution rather
than threatening it. (This re-homes ETV-E2-c4.)

**Only an actual problem if:** raw ETP fails to recover ≥98% full-BoN-8 reward
at ≤50% compute (i.e., the foundation baseline itself does not reproduce on the
lyric-fix dataset). That would be an implementation/regime concern routed via
§7, re-checking the schedule and the matched-compute accounting.

#### Block ADSR-E5 — Learned quality verifier shows no net benefit

**Hypotheses/contributions tested:** C4 (learned-verifier baseline), the
lightweight quality-verifier component (ADSR §4.2).

**Null wording:** the lightweight quality verifier (ridge / GBDT / LambdaMART
pairwise on scalar early features — axis scores, within-prompt rank, slope,
risk, metadata) does not improve safe-restart calibration / late-axis defer /
Pareto over the raw fixed schedule or random keep-K (within noise). This
re-homes ETV-E2-c2 / ETV-E2-c3 / ETV-E2-c4.

**Frozen-constraint guard:** the quality verifier is **lightweight by design,
not by accident** — ridge already near-saturates within-prompt NDCG (~0.995);
capacity is **not** the bottleneck (the label signal is limited by near-tied
candidates). A null here is therefore **not** "we need a bigger model." Do
**not** add an MLP or any heavy neural verifier to chase it (frozen
constraint: EVPD is the only learned neural component). The honest reading of a
null is "scalar-feature selection is near-saturated; the verifier is a useful
lightweight calibrator at best."

**Pre-localization required before declaring null:**
1. Report test-set Spearman of verifier predictions vs final reward. If
   Spearman is high but the Pareto gain is small, the verifier *works* but
   selection is simply low-stakes (the ADSR premise) — not a verifier failure.
2. Report GBDT feature importance. If `r_lcb(σ=0.9)` carries most of the
   importance, the verifier is mostly re-learning the hand schedule — honest
   negative on the learned part.

**Pivot if null persists:**
→ **No paper-breaking effect under ADSR.** The verifier was never the headline.
Keep it as a *lightweight* safe-restart/defer calibrator inside ADSR (E6) and
report "raw ETP suffices for selection; the learned verifier adds only marginal
calibration at this feature scale" — an honest, narrow, already-anticipated
negative. The headline (C2 restart + C3 EVPD) is unaffected. (Anchor:
ASSUMPTION_LEDGER ETV3 → ADSR-C4/E5 row; CONTROL_DESIGN §2.2 axis-awareness
factor.)

#### Block ADSR-E6 — ADSR does not beat BoN-4 / random restart (the make-or-break)

**Contribution tested:** C2 (ADSR main method — restart/defer/continue),
supported by H3 (restart beats selection), H4 (axis-deferred restart preserves
late axes), D3 (offline-first validation), D4 (matched-NFE accounting), D7
(restart = new independent seed).

**Null wording:** ADSR final robust reward ≤ same-compute BoN-4, OR ≤ random
restart, at matched **expected total NFE** (D4: partial cost to σ_c + surviving
full cost + restart new-seed cost + deferred-continuation cost).

**Evidence-honesty guard:** ADSR has **NOT been run.** It is offline-simulatable
on the existing 4096-candidate pool (D3: "restart" = draw the next independent
pool candidate for the same prompt), then confirmed with a small real-generation
run. No ADSR reward number may be reported until E6 runs; the offline simulation
and the real-generation confirm are distinct artifacts.

**Pre-localization required before declaring null (use the §2.2 two-factor
ablation in CONTROL_DESIGN):**
1. **Random-restart control (C2-b3).** If random restart ties ADSR, the
   early-quality signal is not what buys the gain → C2 retracts but C1
   observability still publishes.
2. **Raw-restart control (C2-b4).** If raw restart (single global early score,
   no axis-awareness, no defer) ties ADSR, the **axis-deferred** logic is not
   load-bearing → demote to "any early-informed restart works"; a milder
   positive, C1 holds.
3. **D7 diversity check.** Confirm new seeds are meaningfully different (A6
   CFG-sweep diversity). If restart explores nothing useful, restart collapses
   to a re-draw — H3/D7 null, not an E6 design failure.
4. **Compute accounting.** Verify no optimistic accounting (the new-seed and
   deferred-continuation cost terms are charged). An ADSR "win" under optimistic
   accounting is an implementation failure (route via §7), not a result.
5. **Offline-vs-real gap.** The offline pool caps restart budget at 8
   candidates/prompt; confirm the real-generation confirm reproduces the offline
   verdict before declaring either a win or a null.

**Pivot if null persists:**
→ **Fall back to the axis-observability + trajectory-analysis paper** (C1 + C5
+ C6 + the E2 human early→final validation). This is the worst-case but always
publishable landing zone: the observability map, the presence/content split,
and the human early→final license stand even if the restart mechanism
underperforms. (Anchor: FINAL_PROPOSAL §9 row "ADSR ≤ BoN-4"; ADSR plan §9
first bullet; CONTROL_DESIGN §2.2/§2.4 two-factor isolation.)

#### Block ADSR-E7 — Improves common quality but hurts lyric / lyric subset too noisy

**Contributions tested:** C4 (lyric-preservation under restart), C5 (lyric as a
first-class late-observable axis), H4 (axis-deferred restart preserves late
axes).

**Null wording:** (a) *hurts lyric* — ADSR improves common/robust reward but
degrades lyric intelligibility (Whisper/ASR-based) on the lyric-bearing vocal
subset relative to non-deferred restart or Full BoN. (b) *too noisy* — the
lyric-bearing subset is too noisy to yield a stable lyric-decidability onset.

**Evidence-honesty guard:** the lyric axis is scored **EN-vocal-only** (0.682
ETP@50, n=282, 248/282 = 88% with signal; instrumental 1.0 sentinel masked,
non-EN excluded — `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`). The
deferred-eval E7 result and the lyric-decidability-vs-ASR-transcribability onset
are **forward-looking**, not obtained. Splits are by prompt_id, never
candidate_id; report per specificity stratum (clean-EN core / broader
lyric-bearing / multilingual-or-thin stress arm). This re-homes ETV-E3
(cross-axis transfer).

**Pre-localization required before declaring null:**
1. Confirm headline lyric metrics use **only** the lyric-bearing vocal
   population (no instrumental-sentinel pollution). A lyric "regression" driven
   by sentinel mixing is an implementation failure (§7), not a hypothesis null.
2. Report ADSR vs raw/non-deferred restart per non-training axis; if ADSR is
   within noise on 3 of 4 late axes, the deferral is working (ETV-E3
   acceptable-transfer reading).
3. For *too noisy*: report inter-stratum variance and the lyric-decidability
   onset stability across the clean-EN core vs stress arm.

**Pivot if null persists:**
- *Hurts lyric* → axis-deferred logic insufficient → **strengthen lyric defer
  / use later σ for lyric / restrict to non-lyric settings.** Retracts the C4
  lyric-preservation claim, not the whole method.
- *Too noisy* → **lyric stays first-class but the claim becomes "lyric
  observability is difficult and needs better measurement"; do not force a
  headline lyric number** (explicit anti-overclaim: lyric is NOT evaluable over
  all prompts). (Anchor: FINAL_PROPOSAL §9 rows "hurts lyric" / "lyric subset
  too noisy"; ASSUMPTION_LEDGER C5/D6 falsification.)

#### Block ADSR-E8 — Human raters disagree with automatic metric

**Tested:** C2/C3 perceptual validity; the E2/E8 human-override principle.

**Null wording:** in the 32–64 blind A/B comparisons (Full BoN vs ADSR / BoN-4
vs ADSR / random restart vs ADSR / raw vs axis-deferred restart), human
preference for ADSR is at or below chance on overall / musicality / prompt-fit /
vocal-presence-correctness / lyric-correctness. This re-homes ETV-E4.

**Pre-localization required:** expand to 64 pairs conditional on a borderline
result; per-rater preference scatter to localize rater outliers; confirm the
A/B interface is validated and not under-powered.

**Pivot if null persists:**
→ **Weaken the automatic-pruning claim; the human result overrides** (mandatory:
"Human judgment overrides automatic reward in framing when they conflict," ADSR
plan §8/§9). Reframe the contribution as automatic-metric Pareto with an honest
note that the perceptual benefit at these small differences is not established —
honest but narrow. (Anchor: FINAL_PROPOSAL §9 row "Human disagrees with reward".)

#### Block ADSR-E9 — Second backbone fails / cross-regime narrow

**Tested:** cross-backbone generality (Stable Audio Open; E9 replicates E1 + E3
+ E6).

**Null wording:** the second backbone is not ready in time, or E1/E3/E6 do not
replicate on it.

**Evidence-honesty guard:** cross-backbone is **not started.** It is pursued in
parallel from Phase 1 (long-lead integration) with a graceful fallback, and it
**does not gate submission.**

**Pivot if null persists:**
→ **Submit with an honest target-regime limitation** if the ACE-Step results are
strong; do **not** claim "ADSR universally generalizes to all flow models"
(explicit anti-overclaim, ADSR plan §14). (Anchor: FINAL_PROPOSAL §9 row "Second
backbone fails"; ADSR plan §9.)

### C. Cascading-failure landing zones (which ADSR variant survives which nulls)

This replaces the §6 M-PRM cascade table for the live (v4.0) claim chain; the
§6 table is retained as historical routing.

| Failed block(s) | Surviving paper | Headline | Floor preserved |
|---|---|---|---|
| ADSR-E6 (restart) only | Axis-observability + trajectory-analysis paper | "Quality axes become observable at different σ; presence early, content late; humans confirm early→final" | C1 + C5 + C6 + E2 human license |
| ADSR-E3 (EVPD) only | ADSR (restart) without the type-match branch | "Axis-deferred restart improves compute allocation" + honest "vocal-presence onset is later than hoped" | C2 + C1 + C5; C3 demoted to measured-onset note |
| ADSR-E5 (verifier) only | ADSR with a *lightweight* calibrator | unchanged ADSR headline; "learned verifier adds marginal calibration; selection is near-saturated" | C2 + C3 + C1 intact (verifier never headline) |
| ADSR-E7 (lyric) only | ADSR with restricted/strengthened lyric defer | unchanged on common/semantic; "lyric observability is hard / restrict to non-lyric" | C2 + C3 + C1; C4 lyric-preservation retracted |
| ADSR-E1 flat-ordering | Single-threshold early-pruning paper | "early quality is one global signal; axis-deferral gives no extra lift" | raw-ETP baseline (C4) + C1 negative map |
| ADSR-E1 weak-persistence | Per-candidate selection / observability paper | "selection is low-stakes; restart license does not hold" | C1 + C5 + C6 |
| ADSR-E8 (human) only | Automatic-metric Pareto paper | "automatic-metric improvement; perceptual benefit not established" | C1 + C2 framed automatic-only; human override noted |
| ADSR-E9 (backbone) only | ACE-Step-scoped ADSR paper | full ADSR headline with an honest target-regime limitation | everything; backbone is non-gating |

The worst case (E6 + E3 both null) still leaves the **axis-observability +
presence/content + human early→final** paper — publishable per FINAL_PROPOSAL §9.

### D. Implementation / regime exclusions (unchanged discipline; ADSR additions)

§7 above still governs: a block is a hypothesis null only if the regime
preserved the mechanism's preconditions. New ADSR-specific exclusions that route
via `/experiment-bridge` patch loop, **not** a paper pivot:

| Failure | Cause | Route |
|---|---|---|
| EVPD trained on clean audio instead of early-σ Tweedie-clean mel | regime mismatch (OOD precondition violated) | retrain EVPD on the correct early-σ input; re-audit (D2) |
| Vocal-presence labels noisy / Demucs fails per-genre | A29 / D1 violated | per-genre SVD fallback; scope type-match to high-confidence labels; document |
| Optimistic compute accounting (new-seed or defer cost omitted) | D4 violated | re-charge all NFE terms; re-run E6 accounting |
| Offline restart budget cap mistaken for a real-generation null | D3 simulation bound | run the small real-generation confirm before declaring an E6 result |
| Lyric metric contaminated by instrumental sentinel | D6 violated | re-filter to lyric-bearing vocal; re-score |
| Quality verifier "underperforms" with an MLP added to chase capacity | frozen-constraint violation | revert to ridge/GBDT/LambdaMART; the verifier is lightweight by design |

### E. Linkage

- Live hypotheses/contributions/assumptions: `orbit-research/ASSUMPTION_LEDGER.md`
  "2026-06-04 ADSR Pivot Addendum" (H1–H6 / C1–C6 / D1–D7).
- Controls and the two-factor (axis-awareness × restart-reallocation) +
  EVPD-branch on/off ablations: `orbit-research/CONTROL_DESIGN.md`
  "2026-06-04 ADSR Pivot Addendum".
- Canonical failure table this file expands: `refine-logs/FINAL_PROPOSAL.md` §9.
- Method / decision logic / compute accounting: `refine-logs/METHOD_SPEC.md`
  (ADSR contract), `refine-logs/EXPERIMENT_PLAN_EXEC.md` (E1–E9 go/no-go gates).
- Frozen plan and §9 failure routing source of truth:
  `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` §9; ADSR brief
  `refine-logs/ADSR_REFRAME_BRIEF.md` "EVIDENCE STATUS".
- ETV-era null routing (superseded, retained as audit trail): the
  "2026-05-28 ETV Pivot Addendum (Round 3)" above; ETV-era snapshot
  `orbit-research/archive/etv_pre_adsr_20260604/`.
