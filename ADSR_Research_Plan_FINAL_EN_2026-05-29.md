# When to Continue: Axis-Deferred Speculative Restart for Flow-Matching Music Generation

**FINAL (frozen, English) · 2026-05-29**

> Revisions since the confirmed plan: (1) added **E2 human early→final validation** as a first-class result (the empirical license for restart and the defense against reward-circularity); (2) restored **cross-backbone** from "optional Phase-5" to a **high-priority, parallel, Phase-1-started goal with a graceful fallback** (does not gate submission); (3) **NEW — added an early vocal-presence / prompt-type axis and a learned vocal-presence detector** as a high-stakes, early-decidable early-reject signal, motivated by human listening evidence that vocal vs. instrumental is perceptible early in the trajectory.

---

## 0. Executive Decision

The project direction is frozen as **Axis-Deferred Speculative Restart (ADSR)**. The paper is **not** framed primarily as RL post-training / M-FixedWin-PRM / section-level process reward / simple Early-Tweedie pruning.

Core research question:

> **When can we decide whether a music-generation trajectory is worth continuing, and which quality axes must be deferred until later in the flow trajectory?**

Method:

> Use early Tweedie-clean estimates to **terminate low-promise trajectories early and restart new seeds**, while **deferring decisions for late-observable axes** such as lyric intelligibility and fine semantic alignment. Among the early-observable signals, **prompt-type match (vocal vs. instrumental presence)** is treated as a high-stakes early-reject axis with its own learned detector.

Strongest supporting evidence: (1) good/bad trajectories separate early; (2) bad trajectories rarely recover (large-scale human listening); (3) aesthetic/production quality is early-observable; (4) **vocal presence is perceptible early by human listeners**; (5) lyric/fine-semantic quality is late-observable; (6) Early-Tweedie pruning is compute-effective; (7) RL post-training is healthy but currently shows no clear gain.

---

## 1. Framing

**Title:** *When to Continue: Axis-Deferred Speculative Restart for Flow-Matching Music Generation* (short: **ADSR**).

**Core thesis.** Flow-matching music generators expose partial information about the final sample before generation completes, but **different quality axes become observable at different stages of the denoising trajectory.** Crucially, we separate *presence* from *content*:

- **Early-observable:** aesthetic/production cleanliness, global musicality, **and vocal presence / prompt-type (vocal vs. instrumental) match** — these are coarse signals.
- **Late-observable:** fine semantic prompt alignment and **lyric intelligibility** (which words, sung correctly) — these are fine content.
- **Mixed/intermediate (to be confirmed by E1; claimed cautiously):** coherence, structure, rhythm/groove.

The key conceptual move enabling early rejection without violating "defer lyric": **detecting *whether a voice is present* is coarse and early-decidable, whereas judging *whether the lyrics are intelligible/correct* is fine and late-decidable.** Early-rejecting a gross type error (an instrumental rendering for a vocal prompt, or vice versa) judges *presence*, not *content*.

Therefore inference-time scaling should neither generate all candidates to completion nor blindly prune on a single early global score. Instead:

> Early-reject trajectories that are clearly bad on **early-observable axes** — including **prompt-type mismatch** — and **defer** decisions for axes that only become reliable later (lyric intelligibility, fine semantics).

---

## 2. Hypotheses

- **H1 — Early trajectory quality persistence.** High/low-quality trajectories separate early: early low-quality candidates rarely become final winners; early top-k contains most final winners; bottom-prune false-negative rate is low.
- **H2 — Axis-dependent observability.** Different axes become predictable at different noise levels. Expected ordering as σ decreases: *aesthetic/production and vocal presence (early) → semantic alignment (mid) → lyric intelligibility (latest).* **This is the scientific core.**
- **H2b — Presence vs. content split (new).** *Vocal presence* (is there singing?) is early-decidable; *lyric intelligibility* (which words?) is late-decidable. The two must be measured and treated as separate axes.
- **H3 — Restart beats fixed-pool selection.** Fixed-pool selection is low-stakes when same-prompt candidates are near-tied (median regret ≈ 0; ETP@50 over BoN-4 ≈ +0.0036). Speculative restart escapes this by early-stopping bad trajectories and reallocating compute to new seeds, exploring more useful trajectories under the same budget.
- **H4 — Axis-deferred restart preserves late axes.** Restart only when early-observable axes are bad; defer uncertain semantic/lyric decisions to later σ.
- **H5 — Type errors are high-stakes and early-catchable (new).** Generating an instrumental output for a vocal prompt (or vice versa) is a *categorical, unusable* failure — unlike near-tied aesthetic differences. Human listening indicates these are detectable early in the trajectory, so they are a high-stakes early-reject target.
- **H6 — Human evidence (already obtained).** Large-scale human listening confirms: early perceptual quality predicts final perceptual quality; bad trajectories are uniformly bad; late-bloomers are rare; **and vocal presence is identifiable early by ear.** This is the empirical license for early rejection.

---

## 3. Contributions

- **C1** Axis×σ observability map, including the **fine-grained ordering aesthetic/production & vocal-presence (early) → semantic → lyric-intelligibility (latest)**, plus human early→final validation (uniform-badness, late-bloomer rarity, early vocal-presence audibility).
- **C2** **ADSR**: axis-deferred speculative restart — the main method (compute reallocation, not selection).
- **C3** **Prompt-type match as a high-stakes, early-decidable axis (new),** realized by a **learned early vocal-presence detector**, used as a high-priority early-reject signal. Because catching a type error has unambiguous stakes (the output is unusable), this partially answers the "selection is low-stakes" concern from a different angle.
- **C4** Compute–quality Pareto improvement over BoN-k (same compute), Full BoN-N, random prune/restart, raw Early-Tweedie pruning, and learned-verifier selection.
- **C5** **Lyric as a first-class late-observable axis,** evaluated only on the correct statistical population (lyric-bearing vocal prompts; no instrumental-sentinel pollution), used to demonstrate why deferral is necessary; paired with the presence/content disentanglement.
- **C6** RL post-training boundary result (LoRA/GRPO technically feasible but no clear first-wave common-metric gain), supporting the shift to inference-time compute allocation.

---

## 4. Method: ADSR

### 4.1 Inputs and features
For each candidate trajectory: prompt, seed, current σ, latent x_σ, model velocity v_θ, and the Tweedie-clean estimate `x̂₀ = x_σ − σ·v_θ`. Decode x̂₀ to an early audio/mel estimate. Features:
- **Scalar quality features** (for the quality ranker): early axis-wise scores (aesthetic/production, semantic), within-prompt rank, score slope across σ, uncertainty/risk, prompt metadata.
- **Audio/spectrogram features** (for the vocal-presence detector): the early mel-spectrogram of x̂₀ itself.
- **Flags:** vocal/instrumental requested by prompt, lyric-bearing flag.

### 4.2 Two distinct learned components (and why their sizes differ)
1. **Quality verifier (lightweight).** Predicts safe-restart probability, late-axis risk, final rank/survival from **scalar** features. Models: raw early score (baseline) → linear/ridge, logistic → GBDT/LambdaMART/pairwise (primary). No large neural model — ridge already saturates within-prompt NDCG (~0.995); capacity is not the bottleneck (the label signal is limited by near-tied candidates).
2. **Early Vocal-Presence Detector, EVPD (learned audio model).** Predicts **final vocal presence** from the **early Tweedie-clean mel-spectrogram**. This component *does* warrant a learned audio network (small CNN / pretrained audio encoder fine-tuned), because presence detection requires reading the audio, not scalar features, and the early-σ domain is out-of-distribution for off-the-shelf detectors trained on clean audio. **Prompt-type match** = compare EVPD's predicted presence to the prompt's requested type.

> The two components are deliberately different: scalar-feature ranking is a near-saturated, low-capacity problem, while early audio perception under heavy noise is a genuine learning problem.

### 4.3 Decisions
```
RESTART  : terminate the current trajectory; launch a NEW independent seed (not a rollback/repair)
DEFER    : continue this candidate to a later σ before deciding
CONTINUE : continue full generation
```

### 4.4 Decision logic (type-match has priority)
```
# 1) High-stakes, early, coarse: prompt-type match
if EVPD says final-type ≠ requested-type with high confidence:
    restart                      # gross type error — categorical failure

# 2) Early-observable quality
elif early_quality clearly low and late_axis_risk low/irrelevant:
    restart

# 3) Late-observable content: never reject early
elif semantic_or_lyric(content)_risk high/uncertain:
    defer                        # judged at later σ; lyric is the canonical defer case

else:
    continue
```
Key distinction: **vocal *presence* and bad production can be judged early; lyric *content* cannot.**

### 4.5 Compute accounting and offline-first
Compare at **matched expected total NFE**, with no optimistic accounting: partial-trajectory cost to σ_c + surviving-trajectory full cost + restart (new-seed) cost + deferred-continuation cost. First validate ADSR **offline on the existing 4096-candidate pool** (treat each candidate's early scores/EVPD output as the verdict; "restart" = draw the next independent pool candidate); then confirm with a small real-generation run.

---

## 5. Data Plan

**Main candidate dataset fields:** prompt_id, candidate_id, seed, split, final reward & rank, early σ scores (0.9/0.8/0.7), axis-wise early & final scores, **final vocal-presence label**, vocal/instrumental flag (requested), lyric-bearing flag, prompt category, compute metadata. **Split by prompt_id, never by candidate_id** (prevents same-prompt candidate leakage).

**Vocal-presence labels (new).** Derive final vocal-presence per candidate via source separation (Demucs/Spleeter) vocal-energy ratio thresholding, or a dedicated singing-voice-detection model; a cheap proxy is Whisper `no_speech_prob` (use only as a coarse pre-filter — Whisper targets speech, not singing, and instrumental audio can false-trigger). **Relabel existing candidates** so vocal presence is available retroactively for offline studies.

**Scale.** Achieved: 512 prompts / BoN-8 / 4096 candidates. Next: BoN-16 subset ≥128 prompts (256 if compute allows).

**Lyric-bearing subset.** 200–300 lyric-bearing vocal prompts; English clean core; ≥3 lyric lines where possible; separate calibration/evaluation split. Report separately: clean English core / broader lyric-bearing vocal / multilingual-or-thin-lyric stress arm. Never mix instrumental prompts into headline lyric metrics.

---

## 6. Experiments

### E1 — Axis × σ observability matrix
Axes (rows): common/robust quality, aesthetic/production, **vocal presence (coarse)**, **lyric intelligibility (fine) on lyric-bearing vocal subset**, semantic_fit, coherence. σ (columns): 0.9 / 0.8 / 0.7 / 0.5 / 0.3 / final. Metrics: Spearman early-vs-final, within-prompt NDCG, winner & top-k retention, axis preservation, false-negative. Fix the lyric stratum first (remove sentinel pollution). **Vocal presence and lyric intelligibility are separate rows; we expect vocal-presence-onset ≪ lyric-onset.** Output: `AXIS_OBSERVABILITY_MATRIX.{md,csv}` + heatmap. Pre-register the early/late thresholds.

### E2 — Human early→final validation (license for restart)
Write up the large-scale human listening as a first-class result: (a) early-σ perceptual quality predicts final **human-judged** quality; (b) uniform-badness quantified; (c) late-bloomer rarity; (d) **humans can identify vocal presence early** (small targeted listening on early estimates at σ=0.9/0.8/0.7). Distinct from the method-preference spot-check (E8). This is the core defense against reward-circularity and "what if you restart a late-bloomer."

### E3 — Early Vocal-Presence Detector and prompt-type-error study (new)
**Goal:** establish that vocal presence is early-decidable and that type errors are catchable early.
1. **Ground truth:** final vocal-presence per candidate (source separation / SVD).
2. **Prevalence:** rate of vocal-prompt→instrumental and instrumental-prompt→vocal errors (a useful result in itself).
3. **Detector:** train EVPD on early Tweedie-clean mel-spectrograms with the final vocal-presence label; report early-detectability AUC and the **vocal-presence decidability onset σ**. For error cases specifically, test whether the early estimate already shows the wrong type.
4. **Disentangle existing data:** split the current lyric-zero candidates into *type errors* (no voice → no transcription) vs *content failures* (voice present but unintelligible) — exactly the presence/content distinction.
5. **Closed loop:** show that type-match restart improves the final selected output's **prompt-type-match rate** vs no restart.
Metrics: AUC, onset σ, type-error prevalence, prompt-type-match rate after restart, false-restart rate on type.

### E4 — Raw pruning and same-compute baselines
Compare Full BoN-8 / BoN-4 (same compute) / random prune / raw Early-Tweedie pruning. Schedules A (σ0.9 top4 → σ0.7 top2 → top1), B (σ0.8 top4 → σ0.7 top2 → top1), C (σ0.8 top6 → top1), bottom-prune (remove bottom-25 at σ0.7/0.8). Metrics: compute/reward fraction, winner_match, top-2 retention, false_negative, regret. **Critical comparison: Raw ETP@50 vs BoN-4 — if raw ETP barely beats BoN-4, it cannot be the headline (known delta ≈ 0.0036).**

### E5 — Learned quality verifier
Targets: final robust-reward regression, final rank, top-1/2/4 survival, safe-restart label, late-axis risk label. Models per §4.2 (lightweight). Metrics: Spearman, NDCG, survival AUC, false-negative at calibrated thresholds, winner retention, reward_fraction under pruning. **Framing:** the verifier is useful if it improves safe-restart calibration / late-axis defer / Pareto — not because it is complex.

### E6 — Axis-Deferred Speculative Restart (main method)
Compare Full BoN-8 / BoN-4 / random restart / raw restart / learned-verifier restart / **type-match restart** / axis-deferred restart (full ADSR, including the EVPD type-match branch). Decisions restart/defer/continue. Metrics: expected compute, final robust reward, semantic & lyric preservation, **prompt-type-match rate**, winner retention, false-restart rate, human preference. **Strict expected-compute accounting (§4.5).** Ablations: σ_c, thresholds, sequential vs. batch-speculative, restart budget; two-factor ablation (axis-awareness × restart-reallocation); and **with/without the EVPD type-match branch**.

### E7 — Lyric-focused deferred evaluation
Data: lyric-bearing vocal (clean English core + stress arm). Compare aesthetic-only restart / common-score restart / axis-deferred restart / Full BoN / BoN-k. Metrics: lyric intelligibility (Whisper/ASR-based), **lyric-decidability onset vs. ASR-transcribability onset (mechanistic anchor)**, semantic prompt fit, overall quality, false lyric-degradation rate. **Success:** ADSR improves lyric/semantic preservation over naive early restart while retaining most common-quality gains. Multilingual arm uses language-matched ASR or is clearly scoped.

### E8 — Human spot-check (method preference)
32–64 blind A/B comparisons, same prompt: Full BoN vs ADSR / BoN-4 vs ADSR / random restart vs ADSR / raw restart vs axis-deferred restart. Rubric: overall, musicality, prompt fit, **vocal presence / type correctness**, lyric correctness/intelligibility, vocal artifacts. **Human judgment overrides automatic reward in framing when they conflict.**

### E9 — Robustness and generality
**Required (cheap) cross-regime within ACE-Step:** vocal vs instrumental, lyric-bearing vs non-lyric, genre/style buckets, BoN-8 vs BoN-16, easy vs hard prompts.
**High-priority, Phase-1-parallel-started cross-backbone:** replicate E1 + E3 + E6 on a second flow-matching audio/music backbone (e.g., Stable Audio Open), elevating the finding from an ACE-Step fact to a flow-matching principle.
**Graceful fallback:** if the second backbone is not ready in time, fall back to cross-regime + an honest target-regime limitation — but it is **pursued in parallel from the start and simply does not gate submission**, not a Phase-5 afterthought.

---

## 7. Baselines

**Required:** Full BoN-8, BoN-4, random prune/restart, raw ETP, learned-verifier selection, type-match restart, ADSR.
**Optional:** BoN-16, non-Tweedie early audio proxy, late-only selection, oracle final selector, off-the-shelf (non-early-trained) vocal detector as a baseline for EVPD.
**Boundary (not main comparison):** M-FixedWin-PRM, M-Section-PRM, R8a/R8b.

---

## 8. Success Criteria

- **Minimum:** ADSR beats same-compute BoN-k and random restart on robust/common metrics.
- **Method success:** ADSR preserves common quality while improving semantic/lyric preservation over non-deferred restart, **and improves prompt-type-match rate via the EVPD branch.**
- **Strong:** ADSR approaches Full BoN-8 at substantially lower compute and is no worse in human preference.
- **Top-tier:** at matched compute, ADSR outperforms Full BoN-8 by exploring more effective independent seeds.

---

## 9. Failure Modes and Interpretation

- **ADSR does not beat BoN-4** → too weak as a main ICLR claim; fall back to an axis-observability + trajectory-analysis paper, or a workshop/audio venue.
- **Improves common quality but hurts lyric** → axis-deferred logic insufficient; strengthen lyric defer / use later σ for lyric / restrict to non-lyric settings.
- **Vocal presence is NOT early-decidable (EVPD onset is late)** → demote the type-match branch to a later-σ check; report onset honestly. Even a mid-trajectory onset still saves the back half of compute, so value likely persists; but the claim must follow the measured onset.
- **Lyric subset too noisy** → lyric stays first-class but the claim becomes "lyric observability is difficult and needs better measurement"; do not force a headline lyric result.
- **Second backbone fails** → submit with a target-regime limitation if ACE-Step results are strong.
- **Human spot-check disagrees with reward metrics** → weaken the automatic-pruning claim; human result overrides.

---

## 10. Prior RL / Credit Experiments (boundary)

Summarized as boundary evidence: section credit not supported; FixedWin behaves like a persistent-quality proxy; LoRA/GRPO first-wave stable but no clear common-metric gain. Interpretation: the most reliable current use of early trajectory information is inference-time compute allocation, not RL post-training. Do not hide these, but do not center the paper on them. **New σ-axis RL is future work, not in the main execution plan.**

---

## 11. Execution Plan (ample compute → parallel)

- **Phase 1 — Repair lyric measurement, build observability, and add vocal-presence labels.** Fix lyric aggregation/sentinel; generate/evaluate the lyric-bearing subset; derive vocal-presence labels; produce the axis×σ heatmap. **Start the second-backbone engineering integration in parallel (long-lead item).** Gate: can lyric be a late-observable headline axis, and is vocal-presence-onset ≪ lyric-onset?
- **Phase 2 — Human early→final validation (E2),** including the early vocal-presence listening check. Gate: do humans support early decidability (quality and presence)?
- **Phase 3 — Train EVPD + type-error study (E3)** and **ADSR offline simulation** (E6 offline). Gate: is vocal presence early-decidable, and does ADSR (with type-match) beat BoN-k/random under fair compute? (make-or-break)
- **Phase 4 — Learned quality verifier and risk calibration (E5).** Gate: does the verifier improve decision quality?
- **Phase 5 — Human spot-check (E8).** Gate: does human judgment support ADSR?
- **Phase 6 — Robustness + cross-backbone replication (E9).** Gate: can we claim more than one narrow setting?
- **Phase 7 — Paper assembly.** Rewrite proposal, figures, method, limitations, reviewer-risk response.

---

## 12. Figures

- **Fig 1** Axis × σ observability matrix (concept figure; rows include vocal-presence and lyric-intelligibility as separate axes; mark vocal-presence and lyric/transcribability onsets).
- **Fig 2** ADSR algorithm flowchart: sample → early estimate → EVPD type-match + score axes → restart/defer/continue.
- **Fig 3** Compute–quality Pareto (x: compute fraction; y: reward fraction / human preference; curves: BoN-k, random, ETP, ETV, type-match restart, ADSR).
- **Fig 4** Lyric and prompt-type preservation (methods vs. lyric/prompt/type preservation; lyric-bearing subset only).
- **Fig 5** Failure cases (late bloomers, false restarts, type errors caught/missed, lyric failures).

---

## 13. Claims We Can Make (if experiments succeed)

(1) Early flow trajectories contain actionable quality information. (2) Quality axes become observable at different stages, with vocal *presence* early and lyric *content* late. (3) Naive early pruning preserves early-observable quality but can harm late-observable axes. (4) A learned early vocal-presence detector catches high-stakes prompt-type errors early. (5) Axis-deferred restart improves compute allocation while protecting late axes and prompt-type correctness. (6) In this regime, inference-time trajectory management is more reliable than current RL post-training.

## 14. Claims We Must Avoid

Music quality is always globally determined; sections never matter; lyric can be evaluated over all prompts; ADSR has distribution-free guarantees; ADSR universally generalizes to all flow models; vocal presence is always trivially detectable at any σ; RL post-training does not work.

---

## 15. Final Recommendation

This is not a faster BoN heuristic, a failed-RL story, a section-credit paper, or a broad audit. It is:

> **A method paper about when a flow-matching music trajectory is worth continuing — grounded in axis-dependent observability (with vocal *presence* early and lyric *content* late), and implemented as axis-deferred speculative restart with a learned early vocal-presence detector for high-stakes prompt-type errors.**
