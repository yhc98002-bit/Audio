# Assumption Ledger — Stage 4 (ORBIT v1.3, PI-revised v2.0; v4.0 ADSR reframe, 2026-06-04)

> *Risk register, not a pre-proposal gate.* Each row records an assumption behind the
> proposal's central factual, method, benchmark, or paper-bearing claims. Rows
> tagged `factual` cite literature; rows tagged `working` carry a falsifiable test.
> Downstream artifacts will trace central "is/will/always" claims back to these rows (G2).
>
> **Version note.** The Critical-Hypotheses table H1–H6 was rewritten on 2026-05-15 when
> the PI revised `refine-logs/FINAL_PROPOSAL.md` from S6 (active robust elite distillation)
> to **Headroom-Gated M-PRM** (Musically Structured Process Reward Modeling). The prior
> H6 (S6's F6 mechanisms, added by Codex Phase 4 calibration) is replaced by H6 (CVaR
> reduces broken-section failures) from the PI version. New assumptions A26–A31 cover
> M-PRM-specific mechanisms (Tweedie reliability, section segmentation, lyric WER,
> vocal stem extraction, latent-time-to-audio-time mapping, reward-model ensembling).
>
> **v4.0 ADSR reframe note (2026-06-04).** The paper-bearing claim structure pivoted a
> THIRD time (M-PRM → ETV → **ADSR** / Axis-Deferred Speculative Restart) per the
> PI-frozen `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`. The live paper-bearing rows are
> now **H1–H6 (ADSR hypotheses)** + **C1–C6 (ADSR contributions)** in the
> "2026-06-04 ADSR Pivot Addendum" at the bottom of this file. **All prior tables are
> preserved as the audit trail and are NOT deleted:** the 2026-05-15 M-PRM H1–H6, the
> A1–A31 assumption table, the ETV1–ETV5 + B1–B5 rows, and the RL boundary rows all stay.
> ETV1–ETV5 are explicitly marked *superseded-by-ADSR* (the H/C rows supersede them);
> ETV's raw-pruning claim survives, but *demoted from headline to baseline*. The ETV-era
> snapshot of this file is archived at
> `orbit-research/archive/etv_pre_adsr_20260604/orbit-research_ASSUMPTION_LEDGER.md`.

**Proposal under examination:** `refine-logs/FINAL_PROPOSAL.md` v4.0 — *When to Continue: Axis-Deferred Speculative Restart (ADSR) for Flow-Matching Music Generation*. Primary backbone: ACE-Step / ACE-Step 1.5 lyric-to-song. Secondary backbone: Stable Audio Open (SAO), cross-backbone replication (Phase-1-parallel, graceful fallback, does not gate submission). 5,400 GPU-h on 8× A800. 148-day window.
**Prior-framing proposals (audit trail):** v3.0 (ETV — Early Trajectory Verification, pruning/selection); v2.0 (Headroom-Gated M-PRM).
**Related artifacts:** `orbit-research/PROBLEM_SELECTION.md`, `idea-stage/IDEA_REPORT.md`, `papers/` (36 PDFs), `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` (PI-frozen FINAL plan).
**Codex calibration:** Applied in Phase 4 (S5→S6 revision). The PI-revision of 2026-05-15 supersedes Codex's S6 selection at the contribution level (S6 demoted to baseline) but keeps the calibration findings intact for the C1 audit suite. See `orbit-research/CODEX_PHASE_4_CALIBRATION.md`.

---

## Critical Hypotheses + Ablation Dimensions (Round 2 reframing 2026-05-20, C21) — M-PRM era, historical

> **STATUS (v4.0, 2026-06-04): HISTORICAL AUDIT TRAIL.** The M-PRM H1–H3 + A1–A5 table
> below is the 2026-05-15→2026-05-20 paper-bearing set for *Headroom-Gated M-PRM*. It was
> first superseded by the ETV1–ETV5 rows (2026-05-28) and is now superseded a second time
> by the ADSR H1–H6 / C1–C6 rows (2026-06-04 ADSR Pivot Addendum). It is preserved because
> it remains the audit trail for the trajectory-aware empirical program (Phase A headroom;
> Phase B.1 Tweedie reliability; Phase B.3 section credit; Phase C1 RL) that ADSR's
> foundation evidence is drawn from. Do NOT treat these rows as live ADSR paper claims.

**Paper-level hypotheses (H1-H3)** must stay in sync with `FINAL_PROPOSAL.md` §6 "Pre-Registered Hypotheses". **Ablation dimensions (A1-A5)** characterize per-component contribution to C3 M-PRM method but are NOT independent paper-bearing hypotheses; their null results downgrade the component without pivoting the paper claim.

### Paper-level hypotheses (paper-bearing) — M-PRM era, historical

| ID  | Hypothesis | Role | Confidence | Cheapest diagnostic | If false | Linked ledger rows |
|-----|------------|------|------------|----------------------|----------|--------------------|
| **H1** (split into H1a + H1b at the M1a gate) | Headroom exists beyond base sampling, CFG, and sampler-control-only optimization (S7). H1a = reward headroom (BoN-8 OR BoN+CFG > base + 0.25 σ on R_lcb held-out). H1b = weight-update headroom (gain not captured by CFG alone OR S7 alone). | paper-breaking | MED-HIGH | M1a gate: 256-prompt canonical held-out × BoN-{4,8,16} (nested per C23: BoN-16 once, derive 4/8 post-hoc) + CFG sweep + S7 + human spot-check ≥ 32 on top-quartile gain. ~400 GPU-h. | H1a false → saturation paper (C1 only). H1b CFG-captured → "CFG sufficient" finding. H1b S7-captured → sampler-control pivot. | A4, A6, A11, A14, A17, A21 |
| **H2** (REVISED C3+C25 R2) | Tweedie-clean intermediate audio is reliably scored. Binary gate: (axis × Tweedie checkpoint) pair enters process-reward gradient target iff Spearman ρ ≥ 0.5. Pairs with ρ < 0.5 fall back to outcome reward on that axis (but ρ values still reported). **Adaptive sample size**: Stage 1 = 64 prompts × 3 checkpoints (τ ∈ {0.5, 0.3, 0.1}); escalate to 128 prompts + τ=0.7 only on ambiguous result. | paper-breaking (for the process-reward claim) | MED | Phase B reliability gate, ~150 GPU-h (Stage 1); ~200 GPU-h with escalation. **No** sign-consistency probe, **no** held-out post-RL verification (paranoia rejected in R1). D3a Tweedie code-level derivation is a hard pre-Phase-B gate. | Pivot to outcome-only / terminal-reward study (Outcome-GRPO-plain becomes central). | A26, A27, A30 |
| **H3** (REVISED C6+C32 R2) | Section-level reward gains correlate better with per-section human preference than the four non-section credit units (timestep, fixed-window, beat-window, lyric-span) plus random-window null control. **Multi-grid validity**: per-section human labels on 2 grids (MERT section + fixed-4s window); n=32 pilot mandatory + n=64 conditional expansion. Each credit-unit method scored on matching grid. | C2-central | MED | Five-credit-unit comparison on dev + canonical held-out (per C24). Phase B.3/B.4 gate: section beats best non-section by ≥ +0.08 Spearman on ≥ 2/3 axes; holds on held-out. ~250 GPU-h + ~10 listener-hours pilot. | Publish credit-unit *negative* study around C2 only. Still publishable. | A27, A28, A29 |

### Ablation dimensions (component-level, NOT paper-bearing) — M-PRM era, historical

| ID | Component | Role | Failure mode | Null-result handling |
|----|-----------|------|--------------|----------------------|
| **A1** (former H4, C4) | Action-localized advantage / locality. Decoder-locality probe primary (ratio ≥ 1.5). Gradient-locality probe hot-standby. | ablation dimension | LocalityRatio < 1.5 on decoder probe | Report A1 as null ablation; paper claim INTACT. |
| **A2** (former H5, C10) | Lyric guard. Constrained-Lagrangian guard at ε ∈ {0, σ_WER} + no-guard control. Tradeoff check (NOT "Pareto curve"). | ablation dimension | Guard does not improve (R_music, R_lyric) tradeoff vs no-guard | Report A2 as null ablation; paper claim INTACT. |
| **A3** (former H6, C11) | CVaR aggregation. (α=0.30, β=0) under gate_v2.yaml. β=0.5 reported as offline scoring sensitivity on saved per-section reward distributions (NO separately trained β=0.5 policy). gate_v1.yaml FROZEN; do NOT edit. | ablation dimension | Mean ≈ CVaR on worst-section reduction at similar overall preference | Report A3 as null ablation; paper claim INTACT. |
| **A4** (curriculum, C7) | Headroom-weighted prompt sampling derived from DEV-only audit. | ablation dimension | Uniform sampling matches curriculum at similar sample budget | Report A4 as null ablation; paper claim INTACT. |
| **A5** (robust reward) | Per-axis z-normalization + LCB over Π perturbation set. | ablation dimension | Raw mean(R_axes) matches LCB at similar training stability | Report A5 as null ablation; paper claim INTACT. |

**Pivot mapping** (M-PRM era, historical):
- Only H1, H2, H3 failures change paper-claim wording:
  - H1 false → saturation/audit paper (no PRM claim attempted).
  - H2 false → terminal-reward study (M-OR; no process-reward claim; A1-A3 still ablated as supporting analysis).
  - H3 false → credit-unit negative paper (C2-only; M-PRM downgraded).
  - H1 + H2 + H3 all false → saturation/audit paper using C1 baseline suite (S6/S5/S2/S3/S7 + classical baselines).
- A1, A2, A3, A4, A5 null results downgrade the component but DO NOT pivot the paper.

> **v4.0 note:** under ADSR, H1 (headroom exists) is fully absorbed into ADSR-H1 (early trajectory
> quality persistence) and ADSR-H6 (human license); H2 (Tweedie reliability) is the foundation under
> ADSR-H1/H2; H3 (section credit) is now the ADSR-C6 RL/credit **boundary** result. The M-PRM pivot
> ladder above is no longer the live decision matrix — see the ADSR Pivot Addendum failure routing.

See `refine-logs/FINAL_PROPOSAL.md` §6 Pre-Registered Decision Matrix (M-PRM-era) and the ADSR Pivot Addendum below for the live (v4.0) pivot ladder.

---

## Assumption table

> The A1–A31 assumption table below is preserved verbatim across all three framings. Most rows are
> infra/factual and carry into ADSR unchanged (backbones, prompt sets, reward/evaluator validity,
> compute, time horizon). The RL/M-PRM-mechanism rows (A1–A5 ablation, A26–A31) are now *boundary*
> assumptions, load-bearing only for the ADSR-C6 RL boundary result and the historical Tweedie
> derivation. The ADSR-specific NEW assumption rows (vocal-presence labels, EVPD, restart accounting,
> offline-first) are added as **D1–D7** in the ADSR Pivot Addendum.

### Data, benchmarks, and prompts

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| A1  | Stable Audio Open 1.0 (`stabilityai/stable-audio-open-1.0`) is a flow-matching / latent-diffusion DiT model whose weights are publicly downloadable under its non-commercial license and accept text prompts producing ~10 s 44.1 kHz stereo audio. *Now (v4.0): cross-backbone replication target for E9 (Phase-1-parallel, graceful fallback; does not gate submission).* | factual | Evans et al. 2024, arXiv:2407.14358; HF model card. |
| A2  | **ACE-Step v1 (arXiv:2506.00045) and ACE-Step 1.5 (arXiv:2602.00744) are flow-matching / DiT-based music generation foundation models with public code (`ace-step/ACE-Step`, `ACE-Step/acestep-v15-sft`), supporting lyric-to-song generation with text + lyrics + style metadata.** *Now: primary backbone.* | factual | Gong et al. 2025/2026; GitHub `ace-step/ACE-Step` and `ace-step/ACE-Step-1.5`. |
| A3  | At least one of MusicCaps (Google), AudioCaps, Song-Describer Dataset, or AudioMOS Challenge 2025 prompt set is reachable for evaluation. ACE-Step lyric-to-song prompts can be constructed using the model's own metadata/lyric format (per ACE-Step model card and demo scripts). | working | Phase A pre-flight; if blocked, fall back to MusicCaps-style synthetic prompts. |
| A4  | **Two 256-prompt sets (dev + held-out), stratified by genre/tempo/vocal-vs-instrumental/lyric-density/structural-complexity/language/specificity/length, are sufficient for trend identification with bootstrap CIs. Splits are by prompt_id, never candidate_id (no same-prompt candidate leakage).** | working | Standard practice; verify with bootstrap CIs in Phase A. Stratified sample-size formula assumes per-stratum n ≥ 8. The achieved canonical reward set is 512 prompts / BoN-8 / 4096 candidates (`orbit-research/trajectory_candidate_dataset.jsonl`). |
| A5  | Prompt distribution drift between MusicCaps (training-time-like) and Song-Describer (out-of-domain-like) lets us probe regime-dependence of headroom. | working | Apply audit on both subsets in Phase A; compare BoN ceilings. Falsified if curves overlap on all rewards. |
| A6  | The base policy of ACE-Step has nontrivial generation diversity at default CFG so BoN at N ≥ 2 produces meaningfully different samples (no near-deterministic mode). *Under ADSR this also underwrites "restart = draw a meaningfully different new independent seed".* | working | Phase A1 CFG sweep + sample similarity check. Falsified if Inception-style similarity > threshold across CFGs at N = 8. |

### Mechanism plausibility — RL post-training (Phase A audit + C1 baselines; now ADSR-C6 boundary)

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| A7  | Flow-GRPO's ODE-to-SDE conversion is well-defined for FM audio architectures (rectified-flow / conditional-flow-matching path between noise and latent data on ACE-Step and SAO). | factual / partial | Liu et al. 2025 (arXiv:2505.05470). Verify audio latent geometry doesn't violate the implicit Gaussian-noise assumption. |
| A8  | "Denoising reduction" (reduce reverse-process steps during training, keep full inference steps) is compatible with ACE-Step / SAO sampler defaults (typically ≥ 25 steps at inference). | working | Phase A pre-flight: 1-hour mini-run trains FM-GRPO with T_train=5 vs full-step. |
| A9  | Audio reward signals (CLAP cosine, Audiobox-Aesthetics MOS prediction, FAD distance) provide differentiable-enough gradient signals when used as sparse end-of-trajectory scalars via GRPO's group baseline. | factual / partial | DRAGON (2504.15217), Resonate (2603.11661), FlowSE-GRPO (2601.16483). Verify gradient magnitudes are not pathological. |
| A10 | KL anchoring (TRPO-style trust region or vanilla KL penalty) prevents catastrophic policy drift on FM audio without requiring exotic regularizers. | working | Standard FM-RL practice; verify audit-derived KL budget keeps audible quality stable. |
| A11 | The marginal value of M-PRM (or Outcome-GRPO, or Stepwise-Tweedie) over offline Flow-DPO and BoN/SFT-on-best at *matched compute* is the right comparison axis. *Under ADSR this becomes the boundary-context comparison for C6; the live comparison axis is inference-time compute reallocation at matched expected NFE.* | working | Defended in Phase 4; report both absolute and matched-compute comparisons if reviewers ask. |

### Mechanism plausibility — M-PRM core (Phase B + Phase C; now ADSR boundary / foundation)

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| **A26** | **Tweedie-clean intermediate audio decoding (`â_k = D(TweedieClean(x_{t_k}, t_k))`) produces semantically meaningful audio at Stage-1 K=3 late/middle checkpoints (τ ∈ {0.5, 0.3, 0.1}; K=4 only on escalation per R2 #25) for FM/rectified-flow models. For ACE-Step (σ=0 data, σ=1 noise) the clean-target formula is `x̂_0 = x_σ − σ · v_out` with model input `timestep = σ · 1000`, source-confirmed at `pipeline_ace_step.py:711` (2026-05-21 audit-round; see `TWEEDIE_DERIVATION_NOTE.md` §8). Rectified-flow `x̂₁ = z_τ + (1−τ)v_θ` is algebraically equivalent only after both σ↔τ relabel AND sign flip on v.** *Under ADSR this is the foundation that the early Tweedie-clean estimate (decoded to early mel for both the quality ranker and EVPD) is meaningful at the early σ ∈ {0.9, 0.8, 0.7} checkpoints — RESOLVED by Track A validation; see superseded-rows note.* | working / resolved | Phase B.1 sanity check: decode `â_k` for known-good final states and compare to `a_final` via PESQ / MOS proxy. **Spearman ρ ≥ 0.5 binary gate** (REVISED 2026-05-20 R2 #6 from prior 0.35) against final reward is the H2 reliability gate. |
| **A27** | **Section/phrase segmentation of generated audio via MERT (`m-a-p/MERT-v1-95M` or successor) or CBM-style detectors is reliable enough on generated music to produce 2–8 sections per ~60 s sample with confidence ≥ threshold. The segmentation is also robust to early-trajectory Tweedie audio.** | working | Phase B.2 segmentation validation: hand-label section boundaries on a small (~32) audio subset and measure boundary F1 against **the 3-level gate** (STOP-B-1 / STOP-B-2 fix #2): **F1 ≥ 0.7 strong pass** → MERT primary; **0.5 ≤ F1 < 0.7 weak pass** → CBM refinement on trained-system side, human-assisted oracle segmentation reserved for diagnostic / human-eval only (STOP-B-2 fix #7); **F1 < 0.5 fail** → demote section credit to ablation-only, fixed/beat/lyric become the credit-unit primary set. The single-gate `F1 ≥ 0.7` wording is superseded by this 3-level gate. *Under ADSR: boundary-only (section credit refuted; see RL-bd-1).* |
| **A28** | **Whisper-large-v3 (or whisper-medium for training-loop probes) on Demucs-htdemucs-extracted vocal stems produces lyric WER that correlates with human intelligibility judgments for ACE-Step-generated singing within an acceptable error band (target: WER off by ≤ 15 % vs. human annotator on a small calibration set).** *Under ADSR this is load-bearing for ADSR-C5 (lyric as a late-observable axis on the lyric-bearing vocal subset) AND, paired with source separation, for deriving the vocal-presence label of ADSR-D1.* | working | Phase A.4 sub-audit: 32 ACE-Step samples with human-rated intelligibility vs. Whisper WER on vocal stems. Falsified → use Whisper as a coarse signal only; lyric guard ε increased. **ADSR caveat:** Whisper `no_speech_prob` is a *coarse pre-filter only* for vocal presence (Whisper targets speech, not singing; instrumental audio can false-trigger) — the headline vocal-presence label uses source separation / SVD per D1. |
| **A29** | **Demucs-v4 (htdemucs) vocal stem extraction is reliable on ACE-Step generation across diverse genres / vocal styles. For prompts where vocal separation is unreliable, fall back to no-separation Whisper on the mix (degraded WER quality acceptable for ablation/probe but not for headline).** *Under ADSR this underwrites the source-separation vocal-energy-ratio route to the final vocal-presence label (D1) and the EVPD ground truth (D2).* | working | Phase A.4 vocal-stem sanity check on per-genre subsets; measure separation SI-SDR or SDR-improvement against base policy. Falsified per-genre → lyric guard inactive for that genre; vocal-presence label uses SVD-model fallback. |
| **A30** | **The latent-time-to-audio-time mapping for ACE-Step's DCAE and SAO's VAE is uniform-stride (or piecewise-stride with a documented factor) so that perturbing a latent token span `[τ_a, τ_b]` causally affects a corresponding audio time span `[t_a, t_b]` more than neighboring spans. This is the *locality* H4 (M-PRM) assumes; the locality probe Phase C.4 measures it.** *Under ADSR: boundary-only (locality matters for local credit, not for inference-time trajectory-level restart/defer).* | working | Phase B / C: latent-span perturbation locality probe; measure `LocalityRatio = Δ(target)/Δ(neighbor)` on a calibration batch; required medians ≥ 1.5 (action-localized) or ≥ 2.0 (strict masked gradient). Falsified → global advantage fallback. |
| **A31** | **Reward-model ensembling (CLAP variants × Audiobox-axes × perturbations Π) combined with calibration produces an uncertainty estimate `std_R` whose magnitude correlates with reward-hacking susceptibility. CVaR over per-section advantages further isolates broken-section failures from mean reward gains.** *Under ADSR: the robust-LCB reward stack (the cached per-axis reward) carries over as the common metric and as the quality ranker's primary scalar feature; the CVaR / per-section part is boundary-only.* | working / partial | Phase D ablation: mean-only vs. robust LCB vs. CVaR. Falsified for the CVaR part → drop CVaR (H6 false); the robust LCB part is independently testable. |

### Baselines and headroom

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| A12 | Best-of-N with N ≤ 16–32 is a *strong* baseline against any reward used in the audit; paper claims will be calibrated against BoN-N, not against base policy. *Under ADSR: Full BoN-8 and BoN-4 (same compute) are required baselines; ADSR must beat same-compute BoN-k.* | working / methodological | Standard practice in LM-RL ("Best-of-N is a strong baseline"). Phase A.2 verifies empirically. |
| A13 | Flow-DPO ported via arXiv:2501.13918 ("Improving Video Gen w/ Human Feedback") provides a strong offline-RL baseline against which the M-PRM contribution is measured. *Under ADSR: boundary baseline only.* | working | Apply same recipe to ACE-Step; compare to Tango 2 (2404.09956) DPO numbers as sanity check. |
| A14 | At least one of the Phase A rewards has non-zero headroom on ACE-Step in at least one prompt regime (= H1's affirmative). *Under ADSR: confirmed; Phase A `delta_sigma_bon_vs_base = 0.7549`; this underwrites ADSR-H1.* | working | This is H1 (M-PRM). Cheapest diagnostic in H1 (M-PRM) row. |
| A15 | The set of published FM-RL add-ons (GRPO-Guard, Chunk-GRPO, SuperFlow, Smart-GRPO, D²-Align) and process-reward variants (Stepwise-Tweedie, Outcome-GRPO, FixedWin/BeatWin/LyricSpan-Tweedie) is applicable to FM audio without architectural redesign. *Under ADSR: boundary context for C6.* | working | Confirmed by reading each add-on's interface; most operate at sampling-loop / reward-shaping level. |

### Evaluator validity (reward / metric correctness)

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| A16 | Meta Audiobox-Aesthetics (arXiv:2502.05139, code `facebookresearch/audiobox-aesthetics`) is a trustworthy proxy for human-judged audio quality at the granularity we will use (10–60 s segments). *Under ADSR: the aesthetic/production axis (early-observable) draws on this; E2/E8 human listening is the circularity defense.* | factual / partial | Tjandra et al. 2025 reports MOS agreement; institutionalized in AudioMOS Challenge 2025. Verify on held-out human-labelled subset. |
| A17 | CLAP-LAION text-audio cosine similarity is a trustworthy proxy for prompt adherence, but is prone to gaming (silence padding, repetition, off-prompt high-CLAP modes). *Under ADSR: the semantic-fit axis (mid-observable) draws on this.* | factual / partial | DRAGON 2504.15217 documents this. Mitigation = anti-hacking probe set (METHOD_SPEC §2.3). |
| A18 | FAD is a distributional fidelity metric poorly suited as a direct RL reward but useful as a side metric. | factual | Standard practice; AudioMOS 2025 reports moderate human-MOS correlation. |
| A19 | The MusicEval-aligned / MAUVE-audio metric (arXiv:2503.16669) is more reliable than raw FAD for cross-method comparison on music. | factual / partial | Huang et al. 2025; verify on Phase A2 outputs. |
| A20 | Audiobox four axes (PQ / PC / CE / CU) are empirically distinct on our prompt set (was H4 in v1.0; merged into the Phase D evaluation as a calibration check, not a critical hypothesis). | working | Reward correlation matrix on 256 base + BoN-8 samples. |

### Scale, compute, and infrastructure

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| A21 | **The 5,400 GPU-h envelope on 8× NVIDIA A800 (PI-specified) is sufficient for the ADSR execution plan: Phase 1 lyric-repair + observability + vocal-presence labels + cross-backbone integration start; Phase 2 human early→final validation (E2); Phase 3 EVPD training + ADSR offline simulation (E3 + E6 offline); Phase 4 learned quality verifier + risk calibration (E5); Phase 5 human spot-check (E8); Phase 6 robustness + cross-backbone (E9); Phase 7 paper assembly — with reserve.** Offline-first ADSR simulation on the existing 4096-candidate pool makes the main-method validation compute-cheap; the EVPD audio net and a small real-generation confirm run are the main new GPU costs. | working | Detailed in `FINAL_PROPOSAL.md` §7 and `EXPERIMENT_PLAN_EXEC.md` (E1–E9). `/experiment-bridge` will refine. The original M-PRM budget breakdown (Phase A 850 + Phase B/credit-unit 650 + Phase C RL 1,800 + Phase D 600 + harness 350 + reruns 450 + reserve ~620) is now boundary-only (RL is C6, not main). |
| A22 | ACE-Step (v1 and v1.5) and SAO expose checkpoint-loadable interfaces from public repos that support controlled inference (CFG, prompt, seed, timestep) and (with a tooling layer) gradient access for LoRA + GRPO updates. *Under ADSR the load-bearing part is per-σ controlled inference + Tweedie-clean decode + new-seed restart; gradient access is needed only for the C6 boundary RL.* | working | Verify in pre-experiment audit. ACE-Step ships training code; SAO ships `stable-audio-tools`. |
| A23 | Implementing M-PRM (Tweedie decode + section reward + action-localized advantage + Lagrangian guard + CVaR + curriculum) on top of ACE-Step's training code is feasible within `/experiment-bridge`'s implementation phase. *Under ADSR: superseded by the much smaller ADSR implementation surface (offline pool replay + decision logic + EVPD audio net + quality ranker); see D-rows.* | working | Re-evaluate after `/experiment-bridge` produces `PLAN_CODE_AUDIT.md`. LoRA + reward harness reduce implementation surface vs. full FT. |

### Time horizon and concurrent work

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| A24 | **The 148-day project window (PI-specified) is sufficient for the ADSR seven-phase plan (Phase 1 lyric-repair/observability/vocal-labels + cross-backbone start → Phase 2 human early→final → Phase 3 EVPD + ADSR offline → Phase 4 verifier/risk → Phase 5 human spot-check → Phase 6 robustness/cross-backbone → Phase 7 writing).** | working | Detailed in `FINAL_PROPOSAL.md` §8 / `EXPERIMENT_PLAN_EXEC.md` §11. User can adjust by passing `— venue:` flag on rerun. |
| A25 | Concurrent work risk is bounded by the rate at which T2I/T2V FM-RL methods are being ported to audio + the rate at which audio process-reward / inference-time-scaling papers emerge. **The ADSR framing (axis-dependent observability + presence/content split + speculative restart + learned early vocal-presence detector) is robust to one or two overlapping precedents on early-pruning or PRM, but not to an exact axis-deferred-restart-with-early-vocal-presence paper on the same open backbones.** | working | Maintain `CONCURRENT_WORK_WATCHLIST.md`. Reopen on STRONG_BLOCKER per `research-posture.md`. The ETV-era early-pruning precedent risk is reduced by ADSR demoting raw pruning to a baseline. |

---

## Sanity-check coverage (PI v2.0; v4.0 ADSR addendum extends)

- **Data availability** ✅ — A1, A2, A3, A4, A5, A6.
- **Mechanism plausibility (RL-side, now C6 boundary)** ✅ — A7, A8, A9, A10, A11.
- **Mechanism plausibility (M-PRM-side, now boundary/foundation)** ✅ — A26, A27, A28, A29, A30, A31.
- **Mechanism plausibility (ADSR-side)** ✅ — D1, D2, D3, D4, D5, D6, D7 (ADSR Pivot Addendum).
- **Baseline behaviour** ✅ — A12, A13, A14, A15.
- **Evaluator validity** ✅ — A16, A17, A18, A19, A20.
- **Scale / compute / infra** ✅ — A21, A22, A23.
- **Time horizon** ✅ — A24, A25.

## G2 reminder

Central factual, method, benchmark, and paper-bearing "is/will/always" claims downstream (`FINAL_PROPOSAL.md`, `EXPERIMENT_PLAN.md` post-bridge, `CLAIM_CONSTRUCTION.md` post-experiment) must trace back to a row in this ledger or be demoted. For the v4.0 ADSR paper the live paper-bearing rows are **H1–H6 + C1–C6 in the ADSR Pivot Addendum** (supported by D1–D7). Background context (literature summaries, narrative paragraphs) stays readable without row-by-row tracing.

## Version notes

- **v1.0 (S5-anchored)** — 2026-05-14. H1–H5 surfaced; A1–A25.
- **v1.1 (S6-anchored, Codex Phase 4)** — 2026-05-15 early. H6 added (S6's F6 mechanisms).
- **v2.0 (M-PRM-anchored, PI revision)** — 2026-05-15 PI revision. H1–H6 replaced by the M-PRM hypothesis set; A26–A31 added for M-PRM-specific mechanisms. The Codex Phase 4 calibration audit trail is preserved in `orbit-research/archive/CODEX_PHASE_4_CALIBRATION.md`.
- **v2.1 — STOP-B-2 consistency patch** — 2026-05-15. **H1 row annotated with H1a / H1b decomposition** at the operational level for the M1a gate (umbrella H1 statement unchanged). **A27 row updated** to reference the **3-level MERT F1 gate** (strong / weak / fail) with human-assisted segmentation restricted to oracle / diagnostic use.
- **v2.2** — 2026-05-20 (`/proposal-revise` Round 1, C2/C3/C4/C5/C6 in REVISION_REPORT.md). H2/H3/H4/H5/H6 rows rewritten: H2 ρ≥0.5 binary gate (C3); H3 multi-grid labels MERT+fixed-4s, n=32 pilot+n=64 conditional (C6); H4 dual-probe (decoder primary + gradient hot-standby, C4); H5 tradeoff check ε∈{0,σ_WER} not "Pareto curve" (C5); H6 CVaR β=0 main + β=0.5 offline scoring sensitivity (C2). Pivot mappings unchanged.
- **v2.2-restoration-note** — 2026-05-20T08:00Z. Version notes block restored from agent-error deletion during doc-cleanup. Reconstructed verbatim.
- **v3.0 (ETV pivot, Round 3)** — 2026-05-28. Paper-bearing claim structure pivoted from M-PRM credit assignment to **Early Trajectory Verification (ETV)**. ETV1–ETV5 + B1–B5 added as the live rows; M-PRM H1–H6 + A1–A5 + A26–A31 preserved as audit trail; RL demoted to boundary (RL-bd-1, RL-bd-2). See the 2026-05-28 ETV Pivot Addendum.
- **v3.0.1 (lyric-fix R2)** — 2026-06-03/04. Lyric axis rescored EN-vocal-only (0.682 ETP@50, n=282; instrumental 1.0 sentinel masked, non-EN excluded; `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`); Track A Schedule A regenerated to 0.9864 @ 0.500 on the lyric-fix dataset (was 0.9858 on 2026-05-28, within noise).
- **v4.0 ADSR reframe (2026-06-04): ETV→ADSR pivot per `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`.** Paper-bearing claim structure pivoted a THIRD time (M-PRM → ETV → **ADSR**, Axis-Deferred Speculative Restart). Added the **2026-06-04 ADSR Pivot Addendum** with live paper-bearing hypotheses **H1–H6 (ADSR)** + contributions **C1–C6** and new assumption rows **D1–D7** (vocal-presence labels, EVPD audio model, restart accounting, offline-first, presence/content split, lyric-bearing population, restart-as-new-seed). The ETV1–ETV5 rows are kept but marked *superseded-by-ADSR* (the H/C rows supersede them); ETV's raw-pruning claim survives as ADSR's raw-ETP **baseline** (ETV2 → ADSR-C4 baseline), not the headline. All prior tables (M-PRM, A1–A31, ETV/B-rows, RL boundary) preserved as audit trail. ETV-era snapshot archived at `orbit-research/archive/etv_pre_adsr_20260604/orbit-research_ASSUMPTION_LEDGER.md`.

---

## 2026-05-28 ETV Pivot Addendum (Round 3 — SUPERSEDED-BY-ADSR 2026-06-04; preserved as audit trail and as the source of the foundation evidence)

> **STATUS (v4.0, 2026-06-04): SUPERSEDED-BY-ADSR.** The ETV1–ETV5 + B1–B5 rows below were the
> live paper-bearing set for the *Early Trajectory Verification (ETV)* framing (pruning / selecting a
> fixed candidate pool). Per `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`, these are now superseded by
> the ADSR H1–H6 / C1–C6 rows in the 2026-06-04 ADSR Pivot Addendum. They are NOT deleted: they remain
> the audit trail, and — critically — they record the **foundation evidence that ADSR is anchored on**.
> The mapping ETV→ADSR is given per-row below. The single substantive demotion: **ETV's raw fixed-schedule
> pruning (ETV2) is now a *baseline* (raw ETP), not the headline** — ADSR's headline is compute
> *reallocation* via restart/defer/continue, not prune/select.

Per `refine-logs/REVISION_INTAKE.md` Round 1 (2026-05-28) and the PI-authored
`revise.md`, the paper-bearing claim structure pivoted from M-PRM credit
assignment to **Early Trajectory Verification (ETV)**. The H1–H6 + A1–A5 +
A26–A31 rows above are NOT deleted — they remain the audit trail for the
trajectory-aware empirical program (Phase A H1; Phase B.1 H2; Phase B.3 H3;
Phase C1 + Track A/B/C). For ETV-era paper-level claims the live rows were
ETV1–ETV5 + B1–B5 below; for v4.0 these are superseded by ADSR H1–H6 / C1–C6.

### Paper-level hypotheses (ETV pivot) — SUPERSEDED-BY-ADSR

| ID | Hypothesis | Role | Confidence | Cheapest diagnostic | If false | Linked ledger rows | ADSR mapping (v4.0) |
|---|---|---|---|---|---|---|---|
| **ETV1** | Early-σ Tweedie estimates carry final-quality signal for flow-matching music generation. | paper-bearing (foundation) | HIGH (H2 STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES on 128 prompts + Track A 4096-candidate validation) — NOTE: the `lyric_intelligibility` axis is scoped to the EN-vocal subset (n=282, 248/282=88 % with signal after the 2026-06-03 lyric regen; instrumental 1.0 sentinel masked, non-EN excluded; see `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`). | already done | n/a — supported | B1 | **→ ADSR-H1 / ADSR-H2 / ADSR-C1** (foundation; persistence + axis observability). Supported. |
| **ETV2** | Raw fixed-schedule Early-Tweedie pruning recovers ≥98 % full-BoN-8 reward at ≤50 % compute under the common robust-LCB metric, beating random pruning by a non-trivial margin. | paper-bearing (strong baseline) | HIGH (Track A: Schedule A 0.9864 @ 0.500; random 0.9570 @ 0.500 — regenerated 2026-06-04 on the lyric-fix dataset, was 0.9858 on 2026-05-28, within noise) | already done | n/a — supported | B1, B2 | **→ ADSR-C4 raw-ETP BASELINE** (demoted from headline to baseline; raw ETP ≈ BoN-4 + 0.0036 is exactly why selection is low-stakes → ADSR-H3 restart). Supported as baseline. |
| **ETV3** | A small ML verifier trained on cached early-σ trajectory features (early-reward vector, slope, within-prompt rank, prompt type, optional CLAP/Audiobox/MERT) improves SAME-COMPUTE selection over raw fixed schedules AND beats BoN-K at matched compute. | paper-bearing (main contribution, ETV) | MED (not yet trained; design is feature-engineering + GBDT/LambdaMART) | E2 same-compute pruning comparison | If ETV cannot beat BoN-4 at matched compute, the paper claim weakens substantially; downgrade to "raw ETP suffices; learned verifier shows no net benefit at this feature scale" — honest negative still publishable. | B2, B3, B4 | **→ ADSR-C4 learned-verifier baseline + ADSR-E5 quality verifier** (the verifier survives, but as a *lightweight* component, NOT the headline; near-saturated, ridge NDCG ~0.995; capacity is not the bottleneck). The ETV "main contribution" status moves to ADSR-C2 (restart) + ADSR-C3 (EVPD). |
| **ETV4** | Risk-controlled adaptive pruning (`P(prune final top-1) ≤ ε` with `ε ∈ {1%, 3%, 5%}`) converts the heuristic schedule into a calibrated trade-off curve between compute saving and false-negative risk. | paper-bearing (operational contribution, ETV) | MED | E2 + E6 risk-curve ablation | If risk-control adds no information beyond raw schedules, demote to engineering ablation. | B4 | **→ ADSR-E5 risk calibration / safe-restart threshold** (the calibrated false-negative curve becomes the safe-restart-probability calibration for the restart decision; ADSR-D4 compute accounting). Survives as operational support, not a standalone headline. |
| **ETV5** | Short-form ACE-Step quality differences are persistent across the clip (globalness index ≥ 0.5; sign consistency ≥ 0.9; crossing frequency ≈ 0), which is the *mechanism explanation* for why early-trajectory verification works. | paper-bearing (mechanism) | HIGH (Track B 2026-05-28: median globalness 0.861, sign consistency 1.000, crossing frequency 0.000) | already done | n/a — supported | B5 | **→ ADSR-H1 mechanism / ADSR-C1** (persistence is the mechanism that licenses early restart of bad trajectories). Supported. |

### Boundary hypotheses (RL post-training; demoted per revise.md §7; carried into ADSR-C6)

| ID | Hypothesis | Role | Status |
|---|---|---|---|
| **RL-bd-1** (former H3 Section credit) | Musical sections are the best credit unit for M-PRM RL on ACE-Step short-form. | boundary / refuted | FAILED 2026-05-23 (`H3_CREDIT_UNIT_INTERPRETATION_2026-05-23.md`); short-form is not section-credit-bearing under the H3 prescreen. Reported as motivation/boundary evidence in the ADSR paper (C6 + §10), not as a paper claim. |
| **RL-bd-2** (former C3 M-PRM RL win) | M-PRM RL post-training beats terminal-reward baselines on the common robust-LCB metric. | boundary / refuted | First-wave 2026-05-26 `COMMON_DEV_NO_CLEAR_WIN` (`PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md`). All four methods within +0.012 to +0.014 of base. Reported as the ADSR-C6 boundary result (LoRA/GRPO feasible but no clear first-wave common-metric gain), motivating the shift to inference-time compute allocation. |

### Assumption rows (ETV-specific) — carried into ADSR

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| **B1** | Early σ Tweedie reconstructions carry sufficient signal for final-ranking prediction within a BoN group on the target prompt distribution. *Under ADSR: foundation for H1/H2/C1.* | factual (already validated) | H2 128-prompt verdict + Track A 4096-candidate validation. |
| **B2** | The same-compute comparison frame — method at compute fraction `c` vs. BoN-K with K matched to the expected kept-candidate count — is the right benchmark for inference-time selection. *Under ADSR: extended to matched **expected total NFE** including restart new-seed cost + deferred-continuation cost (D4), since restart changes the cost model beyond pruning.* | factual / methodological | Standard inference-time selection literature; not a novel claim. ADSR adds the restart-cost terms. |
| **B3** | Cached early-σ reward vectors (CLAP / Audiobox / MERT-Whisper outputs computed once during the BoN trajectory) + lightweight engineered features (early rank, slope, prompt type) are sufficient to train a small ML verifier without large-model fine-tuning. *Under ADSR: this is the **scalar quality verifier** of §4.2 — confirmed near-saturated (ridge NDCG ~0.995); capacity is not the bottleneck. The genuinely-learned component is the EVPD audio net (D2), a separate problem.* | working | E5 — if linear/GBDT does not beat raw schedules, increase feature scope, then conclude "verifier adds no net value" (an honest negative). Bound: **no MLP / no large model for the *quality* head** — it is near-saturated; EVPD is the only deliberate audio-net exception. |
| **B4** | A within-prompt pairwise / listwise ranker (LambdaMART-style) is a stronger primary head than a per-candidate regressor for this selection task. | working | E5 model-family ablation. |
| **B5** | Short-form music quality differences are persistent across the clip (global rather than time-local). *Under ADSR: mechanism for H1 (license to early-restart bad trajectories).* | factual (validated) | Track B globalness index 0.861, sign consistency 1.000, crossing frequency 0.000. |

### Superseded rows (as of the 2026-05-28 ETV pivot; status re-confirmed under ADSR)

The following rows in the M-PRM table above remained in the ledger as historical
audit trail and were NOT load-bearing for the ETV paper's claim chain. Under ADSR
their status is unchanged unless noted:

- **H3 (M-PRM)** (musical section credit unit) — refuted; cited only as ADSR-C6 boundary motivation.
- **A1** (action-localized advantage / locality) — relevant only if RL is reconsidered later (future σ-axis RL, not in the ADSR main plan).
- **A2** (lyric guard) — relevant only if RL is reconsidered later. (Note: lyric is now a first-class *late-observable axis* in ADSR-C5, but the *RL guard mechanism* is boundary.)
- **A3** (CVaR aggregation) — relevant only if RL is reconsidered later.
- **A4** (headroom-weighted curriculum) — relevant only if RL is reconsidered later.
- **A5** (robust reward) — partial transfer: robust-LCB remains the common metric for ADSR evaluation and the quality ranker's primary scalar feature, but the per-axis ablation is no longer headline.
- **A23** (latent-to-audio time mapping) — relevant only for local credit; not for ADSR inference-time restart/defer.
- **A26** (Tweedie formula correctness) — RESOLVED via Track A validation 2026-05-28 (the Tweedie clean-target formula is empirically correct enough to support 0.9864 reward fraction at 0.500 compute). Under ADSR this is the foundation that the early Tweedie-clean estimate is meaningful for both the quality ranker and the EVPD.
- **A27** (section segmentation quality) — relevant only as boundary explanation.
- **A28** (lyric WER / Whisper) — **promoted under ADSR**: load-bearing for ADSR-C5 (lyric late-observable axis) and for deriving the vocal-presence label (D1) and EVPD ground truth (D2); Whisper `no_speech_prob` is a coarse pre-filter only.
- **A29** (vocal stem extraction) — **promoted under ADSR**: underwrites the source-separation route to the final vocal-presence label (D1) and EVPD ground truth (D2).
- **A31** (reward-model ensembling) — partially preserved: ADSR's primary scalar feature is the cached robust-LCB from the existing reward stack, so the calibration carries over.

Cross-references:
- `refine-logs/REVISION_INTAKE.md` — Round 1 critique inventory (ETV era).
- `refine-logs/REVISION_REPORT.md` — Round 1 outcome (ETV era).
- `refine-logs/METHOD_SPEC.md` — implementation contract (ETV §"Early Trajectory Verifier" superseded by the ADSR §; see v4.0).
- `refine-logs/FINAL_PROPOSAL.md` — v4.0 ADSR paper-direction claim chain (v3.0 ETV chain archived).
- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` — Track A canonical evidence (raw-ETP baseline).
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` — Track B mechanism evidence (globalness).

---

## 2026-06-04 ADSR Pivot Addendum (Round 4 — LIVE paper-bearing set; supersedes ETV1–ETV5)

Per the PI-frozen `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`, the paper-bearing claim
structure pivots a THIRD time (M-PRM → ETV → **ADSR**, Axis-Deferred Speculative Restart).
ADSR is **compute *reallocation* via RESTART / DEFER / CONTINUE — not prune/select**. Raw
ETV pruning (Track A) is now a *baseline* (raw ETP), not the headline; M-PRM / section credit
is *boundary*. The **live** paper-bearing rows are the ADSR hypotheses **H1–H6** and
contributions **C1–C6** below, supported by the new assumption rows **D1–D7**. The
ETV1–ETV5 + B1–B5 rows and the M-PRM tables above remain the audit trail.

**Evidence-status honesty (binding — do NOT overclaim).** Foundation evidence *exists* and is
repurposed: H1/H2 early-quality persistence (Phase A headroom `delta_sigma_bon_vs_base = 0.7549`;
H2 STRONG_PASS on 128 prompts; Track B globalness 0.861); Track A raw-ETP pruning (Schedule A
**0.9864** @ 0.500 compute, regenerated 2026-06-04 on the lyric-fix dataset, was 0.9858 on
2026-05-28; bottom-prune σ=0.7 false-negative 0.0195); lyric axis scored EN-vocal-only (**0.682**
ETP@50, n=282, 248/282 = 88 % signal; instrumental 1.0 sentinel masked, non-EN excluded;
`prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`); C1 RL boundary (no clear first-wave
common-metric gain). **NOT yet run / forward-looking:** E3 **EVPD is NOT trained**; E6
**restart/ADSR NOT run** (offline-simulatable only on the 4096-candidate pool); vocal-presence
labels **not yet derived**; H2b presence/content split **unmeasured**; cross-backbone not started.
**This is a plan-stage proposal for the new ADSR method, anchored on existing ETV/Track-A/H2/
human-listening evidence.** Confidence labels below carry an explicit evidence-status tag
(SUPPORTED / FORWARD-LOOKING-PLAN).

### Paper-level hypotheses (ADSR — LIVE, paper-bearing)

| ID | Hypothesis | Role | Confidence (evidence status) | Cheapest diagnostic | If false | Linked ledger rows |
|---|---|---|---|---|---|---|
| **H1** (ADSR — early trajectory quality persistence) | High/low-quality trajectories separate early: early low-quality candidates rarely become final winners; early top-k contains most final winners; bottom-prune false-negative rate is low. *This is the empirical license for early restart.* | paper-bearing (foundation) | HIGH (SUPPORTED) — Phase A `delta_sigma_bon_vs_base = 0.7549`; H2 STRONG_PASS 128 prompts; Track A bottom-prune σ=0.7 false-negative 0.0195; Track B globalness 0.861 / sign consistency 1.000 / crossing 0.000. | already done (E1 winner/top-k retention + Track A/B) | persistence weak → restart license collapses → fall back to per-candidate selection only (the H3 "selection is low-stakes" route still publishable as observability + trajectory analysis). | B1, B5, D7, A14, A26 (resolved); supersedes ETV1, ETV5 |
| **H2** (ADSR — axis-dependent observability; **the scientific core**) | Quality axes become predictable at different σ. Expected ordering as σ decreases: aesthetic/production & **vocal presence (early)** → semantic alignment (mid) → **lyric intelligibility (latest)**. | paper-bearing (scientific core) | MED-HIGH (PARTIAL: ordering FORWARD-LOOKING; lyric-latest already indicated by EN-vocal lyric 0.682 @50 weaker/later than common-quality 0.9864; vocal-presence onset NOT yet measured) | E1 axis×σ observability matrix (vocal-presence and lyric as SEPARATE rows; expect vocal-presence-onset ≪ lyric-onset); Spearman early-vs-final + within-prompt NDCG + winner/top-k retention + false-negative per axis per σ. | ordering flat (all axes equally early/late) → no axis-deferral benefit → demote to a single-threshold early-pruning paper (i.e., fall back toward raw-ETP baseline). | B1, D5, D6, A16, A17, A28; supersedes ETV1 |
| **H2b** (ADSR — presence vs. content split, **NEW**) | *Vocal presence* (is there singing?) is early-decidable; *lyric intelligibility* (which words?) is late-decidable. The two must be measured and treated as separate axes. | paper-bearing (NEW, enabling H5/C3/C5) | MED (FORWARD-LOOKING: vocal-presence labels not yet derived; presence/content split of lyric-zero candidates unmeasured) | E3 step 4: split current lyric-zero candidates into *type errors* (no voice → no transcription) vs *content failures* (voice present but unintelligible); E1 separate vocal-presence vs lyric-intelligibility rows. | presence not separable-early from content → collapse vocal-presence into the late lyric axis; type-match branch demoted to a later-σ check (H5 failure routing). | D1, D2, D5, D6 |
| **H3** (ADSR — restart beats fixed-pool selection) | Fixed-pool selection is low-stakes when same-prompt candidates are near-tied (median regret ≈ 0; raw ETP@50 over BoN-4 ≈ +0.0036). Speculative restart escapes this by early-stopping bad trajectories and reallocating compute to NEW seeds, exploring more useful trajectories under the same budget. | paper-bearing (main-method motivation) | MED (PARTIAL: the "selection is low-stakes" premise is SUPPORTED by Track A raw-ETP ≈ BoN-4 + 0.0036; the "restart beats selection" claim is FORWARD-LOOKING — E6 NOT run) | E6 offline ADSR simulation on the 4096 pool ("restart" = draw the next independent pool candidate) vs same-compute BoN-k / random restart, at matched expected total NFE (D4). | restart ≤ BoN-4 at matched compute → ADSR too weak as headline; fall back to axis-observability + trajectory-analysis paper (per ADSR §9). | B2, D3, D4, D7; supersedes ETV2 (raw ETP → baseline), ETV3 (selection → low-stakes) |
| **H4** (ADSR — axis-deferred restart preserves late axes) | Restart only when early-observable axes are bad; defer uncertain semantic/lyric decisions to later σ so late-observable quality is not destroyed by early rejection. | paper-bearing (safety of the method) | MED (FORWARD-LOOKING: E6/E7 deferral not yet run) | E6 two-factor ablation (axis-awareness × restart-reallocation) + E7 lyric-focused deferred eval: ADSR vs naive (non-deferred) early restart on lyric/semantic preservation. | axis-deferral does not protect lyric (improves common quality but hurts lyric) → strengthen defer / use later σ for lyric / restrict to non-lyric settings (ADSR §9). | D5, D6, A28; supersedes (extends) ETV4 |
| **H5** (ADSR — type errors high-stakes & early-catchable, **NEW**) | Generating an instrumental output for a vocal prompt (or vice versa) is a categorical, unusable failure (unlike near-tied aesthetic differences), and is detectable early in the trajectory → a high-stakes early-reject target. | paper-bearing (NEW, the C3 engine) | MED (FORWARD-LOOKING: EVPD NOT trained; type-error prevalence & onset σ not yet measured) | E3 EVPD study: type-error prevalence (vocal→instrumental, instrumental→vocal), EVPD early-detectability AUC, vocal-presence decidability onset σ, type-match rate after restart, false-restart-on-type rate. | vocal presence NOT early-decidable (EVPD onset late) → demote type-match branch to a later-σ check; report onset honestly (even mid-σ onset still saves the back half → value likely persists, but the claim follows the measured onset). | D1, D2, D5; new |
| **H6** (ADSR — human evidence, **already obtained**) | Large-scale human listening confirms: early perceptual quality predicts final perceptual quality; bad trajectories are uniformly bad; late-bloomers are rare; and vocal presence is identifiable early by ear. *The empirical license for early rejection and the defense against reward-circularity.* | paper-bearing (license / circularity defense) | HIGH (SUPPORTED for quality persistence from existing large-scale listening; the early-vocal-presence listening sub-check is a small targeted FORWARD-LOOKING addition in E2) | E2 human early→final validation: early-σ perceptual quality predicts final human-judged quality; uniform-badness quantified; late-bloomer rarity; targeted early-vocal-presence listening at σ = 0.9/0.8/0.7. | human listening contradicts early-decidability → weaken the early-rejection claim; human result overrides automatic reward (ADSR §9). | B5, D7 |

### Contributions (ADSR — LIVE, paper-bearing)

| ID | Contribution | Role | Status / evidence | Cheapest diagnostic | If false / weak | Linked ledger rows |
|---|---|---|---|---|---|---|
| **C1** | Axis×σ observability map (aesthetic/production & vocal-presence early → semantic mid → lyric-intelligibility latest) + human early→final validation (uniform-badness, late-bloomer rarity, early vocal-presence audibility). | analysis contribution (the scientific core) | PARTIAL — common-quality early-observability & persistence SUPPORTED (Track A/B); full axis ordering + human early→final = E1/E2 FORWARD-LOOKING. | E1 + E2. | ordering flat → the map is still a useful negative/null observability result; paper pivots to it as the standalone result (ADSR §9). | H1, H2, H2b, H6, B1, B5, D5, D6 |
| **C2** | **ADSR — axis-deferred speculative restart: the main method (compute REALLOCATION via restart/defer/continue, NOT selection).** | main method | FORWARD-LOOKING — E6 NOT run; offline-simulatable on the 4096 pool (D3, D4). | E6 (offline first, then small real-generation confirm) vs same-compute BoN-k / random restart / raw restart / learned-verifier restart / type-match restart. | ADSR ≤ BoN-4 → fall back to observability + trajectory-analysis paper (ADSR §9). | H3, H4, D3, D4, D7; supersedes ETV3 as the "main contribution" slot |
| **C3** | **Prompt-type match as a high-stakes, early-decidable axis (NEW),** realized by a **learned Early Vocal-Presence Detector (EVPD)** used as a high-priority early-reject signal. | NEW contribution (the second main lever) | FORWARD-LOOKING — EVPD NOT trained; vocal-presence labels NOT derived. | E3 (EVPD AUC, onset σ, type-error prevalence, type-match rate after restart). | vocal presence not early-decidable → demote to later-σ check; report onset honestly (H5 failure routing). | H2b, H5, D1, D2, D5 |
| **C4** | Compute–quality Pareto over BoN-k (same compute), Full BoN-N, random prune/restart, **raw Early-Tweedie pruning (the ex-ETV headline, now a baseline)**, and learned-verifier selection. | Pareto / baseline contribution | PARTIAL — raw-ETP point SUPPORTED (Schedule A 0.9864 @ 0.500; random 0.9570 @ 0.500); full Pareto incl. restart curves = E4/E6 FORWARD-LOOKING. | E4 (raw pruning & same-compute baselines; critical raw-ETP@50 vs BoN-4 ≈ +0.0036) + E6 (restart curves). | raw ETP barely beats BoN-4 (≈ +0.0036) → confirms it cannot be the headline → motivates restart (this is *expected*, not a failure). | B2, B3, B4, D4; absorbs ETV2 (baseline) + ETV3 (verifier baseline) + ETV4 (risk calibration) |
| **C5** | **Lyric as a first-class late-observable axis,** evaluated only on the correct statistical population (lyric-bearing vocal prompts; **no instrumental-sentinel pollution**); paired with the presence/content disentanglement; demonstrates why deferral is necessary. | late-axis contribution | PARTIAL — lyric rescored EN-vocal-only SUPPORTED (0.682 ETP@50, n=282, 88 % signal; instrumental 1.0 sentinel masked, non-EN excluded); deferred-eval E7 + lyric-decidability-vs-ASR-transcribability onset = FORWARD-LOOKING. | E7 lyric-focused deferred eval on lyric-bearing vocal (clean-EN core + stress arm); lyric-decidability onset vs ASR-transcribability onset. | lyric subset too noisy → lyric stays first-class but the claim becomes "lyric observability is difficult and needs better measurement"; do not force a headline lyric result (ADSR §9). | H2, H2b, H4, A28, A29, D6; refines ETV1 lyric scoping |
| **C6** | RL post-training **boundary** result (LoRA/GRPO technically feasible but no clear first-wave common-metric gain), supporting the shift to inference-time compute allocation. | boundary result | SUPPORTED (boundary) — `COMMON_DEV_NO_CLEAR_WIN`; section credit refuted. | already done (Phase C1 + H3 credit-unit study). | n/a — reported as a boundary section (ADSR §10), NOT a headline; do NOT claim "RL post-training does not work". | RL-bd-1, RL-bd-2, A7–A11, A26–A31 (boundary) |

### New assumption rows (ADSR-specific) — D1–D7

| ID  | Assumption | Tag | Source / Test |
|-----|------------|-----|---------------|
| **D1** | **A reliable FINAL vocal-presence label per candidate can be derived from the existing audio** via source separation (Demucs/Spleeter) vocal-energy-ratio thresholding, or a dedicated singing-voice-detection (SVD) model. Whisper `no_speech_prob` is a **coarse pre-filter only** (Whisper targets speech, not singing; instrumental audio can false-trigger), never the headline label. The existing 4096 candidates can be **relabeled retroactively** so vocal presence is available for offline studies. | working (NOT yet derived — FORWARD-LOOKING) | Phase 1 label-derivation pass: source separation vocal-energy ratio + SVD on the 4096 pool; spot-validate against human listening (E2 early-vocal-presence check). Falsified → use SVD model primary / report label noise; type-match claim scoped to high-confidence labels. Leans on A28/A29 (Demucs/Whisper reliability). |
| **D2** | **A learned Early Vocal-Presence Detector (EVPD) — a real audio neural net (small CNN or fine-tuned pretrained audio encoder) — can predict FINAL vocal presence from the EARLY Tweedie-clean mel-spectrogram** with useful AUC at early σ ∈ {0.9, 0.8, 0.7}. This warrants a learned audio net (unlike the near-saturated scalar quality ranker) because early-σ audio perception under heavy noise is a genuine learning problem and is OOD for off-the-shelf detectors trained on clean audio. | working (NOT yet trained — FORWARD-LOOKING; the central new modeling risk) | E3: train EVPD on (early Tweedie-clean mel → final vocal-presence label D1); report AUC, vocal-presence decidability onset σ, and an off-the-shelf-clean-audio-detector baseline. Falsified (EVPD onset late / AUC low) → demote type-match branch to later-σ; report onset honestly (H5/C3 failure routing). |
| **D3** | **ADSR can be validated offline-first on the existing 4096-candidate pool**: "restart" = draw the next independent pool candidate for the same prompt; early scores / EVPD output serve as the decision verdict; a small real-generation run confirms the offline result. The pool is large enough (8 candidates/prompt × 512 prompts) to simulate restart budgets without new generation for the main result. | working (FORWARD-LOOKING for the simulation; the pool exists) | E6 offline simulation; confirm with a small real-generation run. Bound: offline restart can only draw from the existing 8-candidate pool per prompt → restart budget per prompt is capped; the real-generation confirm removes this cap for a subset. |
| **D4** | **Compute is accounted at matched expected total NFE with no optimistic accounting:** partial-trajectory cost to σ_c + surviving-trajectory full cost + restart (new-seed) cost + deferred-continuation cost. This is the right benchmark frame for restart (it changes the cost model beyond pruning, where there is no new-seed cost). | factual / methodological | §4.5 of the ADSR plan; `METHOD_SPEC.md` ADSR compute-accounting contract. Extends B2 (same-compute frame) with the restart-cost terms. Not a novel claim, but must be enforced so ADSR is not over-credited. |
| **D5** | **Early-observable vs late-observable axis assignment is empirically determinable from the axis×σ matrix** (vocal-presence & aesthetic/production early; semantic mid; lyric-intelligibility late), and the early/late thresholds can be pre-registered before they gate the decision logic. | working (FORWARD-LOOKING — E1 fixes the assignment) | E1: pre-register early/late σ thresholds; the decision logic (restart on early-observable bad incl. type mismatch; defer on late-observable uncertain) consumes them. Falsified (no clean early/late split) → single-threshold pruning fallback (H2 failure routing). |
| **D6** | **The lyric-bearing vocal subset (200–300 prompts; English clean core, ≥3 lyric lines; broader-lyric-bearing & multilingual-or-thin stress arms) is the correct statistical population for headline lyric metrics**, and instrumental prompts must NEVER be mixed into headline lyric metrics (the 1.0 instrumental sentinel is masked). Splits are by prompt_id, never candidate_id (cross-prompt, not cross-content), and reported per specificity stratum. | working (SUPPORTED for the EN-vocal rescoring 0.682 @50 n=282; the 200–300 dedicated subset assembly is FORWARD-LOOKING) | `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`; E7 lyric-bearing subset assembly + separate clean-EN / broader / stress-arm reporting. Falsified → lyric stays first-class but claim becomes "lyric observability needs better measurement" (do not force a headline). |
| **D7** | **"Restart" means launching a NEW independent seed (a fresh trajectory), NOT a rollback / repair / partial-resample of the current trajectory.** This is what makes ADSR a reallocation-of-compute method rather than a refinement method, and it relies on base-policy diversity (A6) so a new seed is meaningfully different. | working / factual | A6 (CFG-sweep diversity check) underwrites it; E6 measures whether restart-explored new seeds beat retained candidates at matched compute. Falsified (new seeds not meaningfully different / restart explores nothing useful) → restart collapses to re-draw with no gain → H3/C2 failure routing. |

### Pivot mapping (ADSR — LIVE failure routing; replaces the M-PRM pivot ladder)

Only the following ADSR-hypothesis failures change the paper-claim wording:

- **H1 false** (persistence weak) → restart license collapses → axis-observability + trajectory-analysis paper (no restart headline).
- **H2 false** (axis ordering flat) → no axis-deferral benefit → single-threshold early-pruning paper (toward the raw-ETP baseline); the observability *null* is still a result.
- **H2b / H5 false** (vocal presence not early-decidable / EVPD onset late) → demote the type-match branch (C3) to a later-σ check; report onset honestly. Even a mid-σ onset saves the back half of compute → value likely persists, but the claim follows the measured onset.
- **H3 false** (restart ≤ BoN-4 at matched compute) → ADSR too weak as the main ICLR claim → fall back to the axis-observability + trajectory-analysis paper, or a workshop/audio venue (ADSR §9).
- **H4 false** (deferral does not protect lyric) → strengthen lyric defer / use later σ / restrict to non-lyric settings.
- **H6 / human spot-check disagrees with reward metrics** → weaken the automatic-pruning claim; the human result overrides.
- **C5 lyric subset too noisy** → lyric stays first-class but the claim becomes "lyric observability is difficult and needs better measurement"; do not force a headline lyric result.
- **C6 / cross-backbone (E9) fails** → submit with a target-regime limitation if ACE-Step results are strong (cross-backbone does NOT gate submission).

The component-level ablations (quality-ranker model family per B4, σ_c / threshold sweeps,
EVPD-branch on/off, two-factor axis-awareness × restart-reallocation) downgrade the affected
component on a null but do NOT pivot the paper claim.

### Claims to AVOID (ADSR §14 — binding anti-overclaim list)

Do NOT state, in any downstream artifact, that: music quality is always globally determined;
sections never matter; lyric can be evaluated over all prompts; ADSR has distribution-free
guarantees; ADSR universally generalizes to all flow models; vocal presence is always trivially
detectable at any σ; RL post-training does not work. (ADSR-C6 reports RL as a *boundary* result —
feasible-but-no-clear-first-wave-gain — never as "RL fails".)

Cross-references (ADSR live set):
- `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` — PI-frozen FINAL plan (the source of truth for H1–H6 / C1–C6 / E1–E9).
- `refine-logs/ADSR_REFRAME_BRIEF.md` — condensed reframe anchor.
- `refine-logs/FINAL_PROPOSAL.md` v4.0 — flagship ADSR proposal.
- `refine-logs/METHOD_SPEC.md` v4.0 — ADSR implementation contract (restart/defer/continue, EVPD, quality verifier, compute accounting §4.5, offline-first).
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 — E1–E9 exec plan (Phases 1–7).
- `orbit-research/CONTROL_DESIGN.md` v4.0 — ADSR baselines/controls (type-match restart, random restart, raw restart, axis-deferred; EVPD vs off-the-shelf; two-factor ablation; EVPD-branch on/off).
- `orbit-research/trajectory_candidate_dataset.jsonl` — canonical 4096-candidate reward set (the offline ADSR simulation substrate).
- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` — Track A raw-ETP baseline evidence.
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` — Track B globalness mechanism.
- `prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` — lyric EN-vocal rescoring (0.682 @50, n=282).
