# Final Proposal — Short Form (v4.0 ADSR reframe, 2026-06-04)

**When to Continue: Axis-Deferred Speculative Restart (ADSR) for Flow-Matching Music Generation**

- **Primary backbone:** ACE-Step / ACE-Step 1.5 (lyric-to-song).
- **Secondary backbone:** Stable Audio Open (high-priority, Phase-1-parallel cross-backbone; graceful fallback; does NOT gate submission).
- **Compute envelope:** 8× NVIDIA A800 80GB; offline-first on the existing 4096-candidate pool, with a small real-generation confirm.
- **Status:** `ADSR_PIVOT_STOP_A_READY_FOR_PI_APPROVAL`. This is a **plan-stage proposal for the new ADSR method**, anchored on existing foundation evidence (H1/H2 persistence, Track A raw-ETP, Track B globalness, the lyric-fix EN-vocal rescore, the human listening record, the C1 RL boundary). EVPD, restart/ADSR, and vocal-presence labels are **not yet run** — see "Evidence status".

> Full proposal: `refine-logs/FINAL_PROPOSAL.md` (v4.0). Frozen PI plan: `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`. Reframe anchor: `refine-logs/ADSR_REFRAME_BRIEF.md`. This short form supersedes the two-generations-stale M-PRM short form (archived `orbit-research/archive/etv_pre_adsr_20260604/refine-logs_FINAL_PROPOSAL_SHORT.md`).

---

## Reframed problem (one paragraph)

Inference-time scaling for flow-matching music generators (BoN over independent seeds, terminal-reward selection) spends full compute generating every candidate to completion before judging any of them, even though the early denoising trajectory already exposes partial information about the final sample. But that information is **not uniform across quality axes**: aesthetic/production cleanliness and *whether a voice is present at all* are coarse and surface early in the trajectory, whereas *which words are sung and whether they are intelligible* (lyric content) and fine semantic alignment only become reliable late. The sharp question is therefore not "can we prune candidates with an early score?" but: **when can we decide a music-generation trajectory is not worth continuing — so that we terminate it and restart compute on a fresh seed — and which axes must we defer until later in the flow trajectory before we are allowed to judge them?** Naive single-score early pruning answers the first half while silently violating the second (it can reject a trajectory on a lyric/semantic axis that is not yet observable), and fixed-pool selection (raw Early-Tweedie pruning) turns out to be low-stakes because same-prompt candidates are near-tied.

## One-sentence thesis

**ADSR (Axis-Deferred Speculative Restart) uses early Tweedie-clean estimates to terminate low-promise trajectories and reallocate their compute to new independent seeds — a restart, not a prune-and-select — while deferring decisions on late-observable axes (lyric intelligibility, fine semantics) and treating prompt-type match (vocal vs. instrumental presence) as a high-stakes, early-decidable early-reject axis served by its own learned early vocal-presence detector.**

## What is new relative to the ETV/M-PRM lineage

The project's third framing (M-PRM → ETV → **ADSR**). The pivot is from *selection over a fixed candidate pool* to *compute reallocation by restart*:

1. **Restart, not prune.** A RESTART terminates a trajectory and launches a NEW independent seed (not a rollback or repair). This escapes the fixed-pool ceiling: ETV/raw-ETP selection is provably low-stakes here (median within-prompt regret ≈ 0; raw ETP@50 beats BoN-4 by only ≈ +0.0036). Raw Early-Tweedie pruning (ETV's headline) is demoted to a **strong baseline** (raw ETP).
2. **Axis-deferred decisions.** The decision rule is gated by *which axis is observable now*: never reject early on an axis (lyric, fine semantics) that is only late-decidable.
3. **Presence-vs-content split (H2b, new).** Detecting *whether* a voice is present is coarse and early-decidable; judging *which words* and whether they are intelligible is fine and late-decidable. Early-rejecting a gross type error judges presence, not content — so it does not violate "defer lyric".
4. **EVPD — a learned audio model (new).** A small early Vocal-Presence Detector reads the early Tweedie-clean mel-spectrogram to predict FINAL vocal presence; prompt-type match = compare EVPD's prediction to the requested type. This is the one genuinely learned neural component, because early-σ audio perception under heavy noise is a real learning problem and out-of-distribution for off-the-shelf clean-audio detectors.
5. **Lyric as a first-class late-observable axis (new scoping),** evaluated *only* on lyric-bearing vocal prompts — never over instrumental prompts (no sentinel pollution).

M-PRM / section-level process reward and RL post-training are now **boundary** evidence, not the method.

---

## Hypotheses (paper-bearing; verbatim anchor ADSR §2)

| ID | Statement | Evidence today |
|---|---|---|
| **H1** | Early trajectory quality persists: early low-quality candidates rarely become final winners; early top-k holds most final winners; bottom-prune false-negative is low. | Supported (foundation): Phase A headroom; Track A; Track B globalness. |
| **H2** | Axis-dependent observability — aesthetic/production & vocal-presence early → semantic mid → lyric latest. **The scientific core.** | Partially supported (H2 persistence STRONG_PASS on 128 prompts); full axis×σ ordering is E1 (planned). |
| **H2b** | **Presence-vs-content split (new):** vocal *presence* early-decidable; lyric *content* late-decidable; measured as separate axes. | Unmeasured (planned E1/E3). |
| **H3** | **Restart beats fixed-pool selection:** selection is low-stakes (median regret ≈ 0; ETP@50 over BoN-4 ≈ +0.0036); restart reallocates compute to new seeds. | Selection-is-low-stakes side supported by Track A; restart-wins side is E6 (planned). |
| **H4** | Axis-deferred restart preserves late axes: restart only on early-observable badness; defer uncertain semantic/lyric to later σ. | Planned (E6/E7). |
| **H5** | **Type errors are high-stakes and early-catchable (new):** an instrumental output for a vocal prompt (or vice versa) is a categorical, unusable failure, detectable early. | Motivated by human listening; quantified in E3 (planned). |
| **H6** | **Human evidence (obtained):** large-scale listening shows early perceptual quality predicts final, bad trajectories are uniformly bad, late-bloomers are rare, and vocal presence is identifiable early by ear. | Obtained (foundation; written up as E2). |

## Six contributions (anchor ADSR §3)

- **C1** Axis×σ observability map (ordering aesthetic/production & vocal-presence early → semantic → lyric latest) + human early→final validation.
- **C2** **ADSR** — axis-deferred speculative restart, the **main method** (compute reallocation, not selection).
- **C3** **Prompt-type match as a high-stakes early-decidable axis (new),** realized by a **learned EVPD**; catching a type error has unambiguous stakes, answering "selection is low-stakes" from a different angle.
- **C4** Compute–quality Pareto over BoN-k (same compute), Full BoN-N, random prune/restart, **raw ETP (the ex-ETV baseline)**, and learned-verifier selection.
- **C5** **Lyric as a first-class late-observable axis,** evaluated only on lyric-bearing vocal prompts (no instrumental-sentinel pollution), paired with the presence/content disentanglement, to demonstrate why deferral is necessary.
- **C6** RL post-training **boundary** result (LoRA/GRPO technically feasible but no clear first-wave common-metric gain) — motivates the shift to inference-time compute allocation.

---

## Method: ADSR (anchor ADSR §4)

**Decisions.** `RESTART` (terminate trajectory; launch a NEW independent seed — not rollback/repair) · `DEFER` (continue to a later σ before deciding) · `CONTINUE` (run to completion).

**Decision logic (type-match has priority).**
```
if EVPD predicts final-type ≠ requested-type with high confidence:
    RESTART                        # gross type error — categorical, unusable failure
elif early_quality clearly low and late_axis_risk low/irrelevant:
    RESTART
elif semantic_or_lyric(content)_risk high/uncertain:
    DEFER                          # judged at later σ; lyric is the canonical defer case
else:
    CONTINUE
```
Key distinction: **vocal *presence* and bad production can be judged early; lyric *content* cannot.**

**Two distinct learned components (§4.2) — deliberately different sizes.**
1. **Quality verifier (lightweight).** Predicts safe-restart probability, late-axis risk, final rank/survival from **scalar** features (early axis scores, within-prompt rank, score slope across σ, uncertainty/risk, prompt metadata). Models: raw early score (baseline) → ridge/logistic → GBDT/LambdaMART pairwise (primary). No large net — ridge already near-saturates within-prompt NDCG (~0.995); **capacity is not the bottleneck** (the label signal is limited by near-tied candidates).
2. **Early Vocal-Presence Detector (EVPD) — a learned AUDIO model.** A small CNN / fine-tuned pretrained audio encoder predicting FINAL vocal presence from the EARLY Tweedie-clean mel-spectrogram. This component *does* warrant a real neural net: presence detection requires reading the audio (not scalars), and the early-σ heavy-noise domain is OOD for off-the-shelf clean-audio detectors.

**Compute accounting & offline-first (§4.5).** Compare at **matched expected total NFE** with no optimistic accounting: partial cost to σ_c + surviving-trajectory full cost + restart new-seed cost + deferred-continuation cost. Validate ADSR **offline on the existing 4096-candidate pool** first ("restart" = draw the next independent pool candidate; each candidate's early scores / EVPD output is the verdict), then a small real-generation confirm.

---

## Experiments E1–E9 (run vs. planned)

| ID | Experiment | Status |
|---|---|---|
| **E1** | Axis×σ observability matrix (vocal-presence & lyric as separate rows; expect vocal-presence-onset ≪ lyric-onset; fix lyric stratum first). | Planned. |
| **E2** | Human early→final validation (license for restart; incl. early vocal-presence listening). | Foundation listening **obtained**; write-up planned. |
| **E3** | **EVPD + prompt-type-error study (new):** AUC, decidability onset σ, type-error prevalence, post-restart type-match rate; disentangle lyric-zero into type-errors vs content-failures. | **Planned — EVPD NOT trained; vocal-presence labels NOT yet derived.** |
| **E4** | Raw pruning & same-compute baselines (raw ETP vs BoN-4; known delta ≈ +0.0036 — cannot be the headline). | Offline-runnable on the 4096 pool; foundation Track-A numbers exist. |
| **E5** | Learned quality verifier (per §4.2; near-saturated). | Planned (offline). |
| **E6** | **ADSR main method** — restart/defer/continue, with/without EVPD branch, two-factor ablation (axis-awareness × restart-reallocation), strict expected-compute. | **Planned — ADSR/restart NOT run (offline-simulatable on the 4096 pool only).** |
| **E7** | Lyric-focused deferred eval on lyric-bearing vocal (lyric-decidability onset vs ASR-transcribability onset). | Planned. |
| **E8** | Human spot-check (32–64 blind A/B; human overrides reward). | Planned. |
| **E9** | Robustness + cross-backbone (Stable Audio Open, Phase-1-parallel; graceful fallback; does NOT gate submission). | Planned (parallel from Phase 1). |

## Baselines (anchor ADSR §7)

**Required:** Full BoN-8 · BoN-4 · random prune/restart · **raw ETP (ex-ETV headline, now baseline)** · learned-verifier selection · **type-match restart** · **ADSR**.
**Optional:** BoN-16 · non-Tweedie early audio proxy · late-only selection · oracle final selector · off-the-shelf (non-early-trained) vocal detector as an EVPD baseline.
**Boundary (not main comparison):** M-FixedWin-PRM · M-Section-PRM · R8a/R8b.

---

## Headline foundation numbers (FOUNDATION ONLY — no ADSR results yet)

- **H1 / Phase A headroom:** `delta_sigma_bon_vs_base = 0.7549`; CFG / S7 sampler-control controls negative. ACE-Step has real inference-time headroom.
- **H2 / Phase B.1 persistence:** `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES` on 128 prompts; 7/7 reward axes with ≥1 primary-σ survival.
- **Track A raw-ETP pruning (now the ADSR raw-ETP baseline):** Schedule A recovers **0.9864** reward_fraction at **0.500** compute (regenerated 2026-06-04 on the lyric-fix dataset; was 0.9858 on 2026-05-28, within noise); bottom-prune σ=0.7 false-negative **0.0195**.
- **Track B globalness (mechanism):** median globalness index **0.861**, sign consistency **1.000**, crossing frequency **0.000** — short-form ACE-Step quality differences are persistent across the clip, not isolated local-window failures.
- **Lyric axis, EN-vocal-only rescore:** ETP@50 = **0.682**, **n=282** EN-vocal prompts, 248/282 = **88%** with signal; instrumental 1.0 sentinel masked out, non-English excluded (`orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`). This is the corrected lyric number — **NOT** the pre-fix 0.8432.
- **C1 RL boundary:** four LoRA/GRPO methods completed cleanly; common dev eval `COMMON_DEV_NO_CLEAR_WIN` (deltas +0.012 to +0.014 LCB). No clear first-wave common-metric gain.

> All of the above is *existing* evidence repurposed as the ADSR foundation. None of it is an ADSR/restart/EVPD result.

## Evidence status (critical — do NOT overclaim)

- **Exists (foundation, repurposed):** H1/H2 early-quality persistence; Track A raw-ETP (Schedule A 0.9864 @ 0.500); Track B globalness; lyric EN-vocal rescore (0.682, n=282); the human listening record (early→final quality + early vocal-presence audibility); the C1 RL boundary.
- **NOT yet run (ADSR is forward-looking):** E3 **EVPD is NOT trained**; E6 **restart/ADSR NOT run** (only offline-simulatable on the 4096 pool); **vocal-presence labels not yet derived**; H2b presence/content split **unmeasured**; cross-backbone not started.
- **Therefore:** this is a **plan-stage proposal for the new ADSR method**, anchored on existing ETV/Track-A/H2/human evidence. We make no ADSR/EVPD/restart performance claims that do not yet exist. Raw ETP (Track A) is a **strong baseline**, not the headline.

## Success / failure (anchor ADSR §8–9)

- **Minimum:** ADSR beats same-compute BoN-k and random restart on robust/common metrics.
- **Method success:** ADSR preserves common quality while improving semantic/lyric preservation over non-deferred restart **and** improves prompt-type-match rate via the EVPD branch.
- **Strong:** ADSR approaches Full BoN-8 at substantially lower compute, no worse in human preference.
- **Top:** at matched compute, ADSR beats Full BoN-8 by exploring more effective independent seeds.
- **Failure routing (§9):** ADSR ≤ BoN-4 → fall back to an axis-observability + trajectory-analysis paper. Vocal-presence not early (EVPD onset late) → demote type-match to a later-σ check and report the onset honestly (mid-trajectory onset still saves the back half of compute). Improves common but hurts lyric → strengthen the lyric defer / restrict to non-lyric. Lyric subset too noisy → lyric stays first-class but the claim becomes "lyric observability is hard and needs better measurement." Second backbone fails → submit with an honest target-regime limitation. Human spot-check disagrees with reward → weaken the automatic claim; human overrides.

## Anti-overclaim (anchor ADSR §14 — claims we must AVOID)

Music quality is *always* globally determined · sections *never* matter · lyric can be evaluated over *all* prompts · ADSR has distribution-free guarantees · ADSR universally generalizes to *all* flow models · vocal presence is *always* trivially detectable at any σ · RL post-training *does not work*. **The narrow honest claim:** *for open flow-matching music generation, early trajectory information is best used to reallocate compute by axis-deferred speculative restart — judging early-observable axes (production, vocal presence) early and deferring late-observable content (lyric intelligibility, fine semantics) — with a learned early vocal-presence detector catching high-stakes prompt-type errors; raw early-Tweedie pruning is a baseline this method should beat, not the contribution.*

## Reading path / next gate

- **Full proposal:** `refine-logs/FINAL_PROPOSAL.md` (v4.0 ADSR).
- **Method contract:** `refine-logs/METHOD_SPEC.md` (ADSR restart/defer/continue, EVPD, compute accounting §4.5; M-PRM/ETV-pruning sections marked superseded boundary).
- **Exec plan:** `refine-logs/EXPERIMENT_PLAN_EXEC.md` (E1–E9, Phases 1–7, go/no-go gates).
- **Controls:** `orbit-research/CONTROL_DESIGN.md` (type-match / random / raw restart; EVPD vs off-the-shelf; two-factor ablation).
- **Hypotheses & claims ledger:** `orbit-research/ASSUMPTION_LEDGER.md` ("2026-06-04 ADSR Pivot Addendum"; H1–H6, C1–C6).
- **Frozen PI plan:** `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`. **Reframe anchor:** `refine-logs/ADSR_REFRAME_BRIEF.md`.

Foundation evidence (preserved, NOT modified by this reframe):
- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` — Track A canonical (raw-ETP baseline).
- `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` — Track A PI decision.
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` — Track B globalness mechanism.
- `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` — lyric EN-vocal rescore (0.682, n=282).
- `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` — C1 RL boundary canonical.

Next gate: after STOP-A sign-off on the ADSR pivot → `/experiment-bridge "refine-logs/EXPERIMENT_PLAN.md"` (STOP B, plan-code audit for the ADSR/EVPD implementation). Keep all still-valid infra: `configs/eval/gate_v2.yaml.draft` (draft; do not activate), reward definitions, prompt-level splits, calibration, compute accounting, and the canonical reward set `orbit-research/trajectory_candidate_dataset.jsonl`.

---

## Revision history

- **v2.0 (PI-revised, 2026-05-15):** Headroom-Gated M-PRM short form (musical credit-unit selection; H1/H2/H3 + A1–A3; Phase A–D gates). Archived `orbit-research/archive/etv_pre_adsr_20260604/refine-logs_FINAL_PROPOSAL_SHORT.md`.
- **v3.0 (ETV pivot, 2026-05-28):** Early Trajectory Verifiers (raw Early-Tweedie pruning + learned V_σ verifier + risk-controlled pruning; ETV1–ETV5). *(Short form was not separately re-cut at v3.0; the M-PRM short form remained the stale stand-in — hence this file lagged two generations.)*
- **v4.0 ADSR reframe (2026-06-04):** ETV→ADSR pivot per `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`. Full rewrite from the two-generations-stale M-PRM short form to Axis-Deferred Speculative Restart: restart-not-prune (raw ETP demoted to baseline), axis-deferred decisions, H2b presence-vs-content split, learned EVPD audio model, type-match early-reject, lyric as a first-class late-observable axis on the lyric-bearing vocal subset only. Hypotheses H1–H6 and contributions C1–C6 replace the M-PRM H1/H2/H3 + A1–A3. Lyric-fix R2 corrections retained (0.682 EN-vocal n=282; Track A 0.9864; cross-prompt-not-cross-content; per-specificity-stratum). EVPD, restart/ADSR, and vocal-presence labels marked NOT-yet-run; this remains a plan-stage proposal anchored on existing foundation evidence.
