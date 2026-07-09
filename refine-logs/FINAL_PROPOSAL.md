# Final Proposal v4.0 — Axis-Deferred Speculative Restart for Flow-Matching Music Generation

| Field | Value |
|---|---|
| Title | **When to Continue: Axis-Deferred Speculative Restart for Flow-Matching Music Generation** |
| Short name | **ADSR** |
| Subtitle | *When can we decide whether a music-generation trajectory is worth continuing, and which quality axes must be deferred until later in the flow trajectory?* |
| Backbone | ACE-Step v1.5 (primary). Stable Audio Open is a high-priority, Phase-1-parallel cross-backbone replication target with a graceful fallback (does not gate submission). |
| Budget | 5,400 GPU-h on 8× A800 (≈4,860 GPU-h remaining as of 2026-06-04). |
| Project window | 148 days. |
| Status | `STOP_A_READY_FOR_PI_APPROVAL` — v4.0 supersedes v3.0 (ETV) per the PI-frozen plan `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`. This is the project's third framing: M-PRM → ETV → **ADSR**. |
| Version stamp | **v4.0 ADSR reframe, 2026-06-04** |
| Frozen source plan | `/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/ADSR_Research_Plan_FINAL_EN_2026-05-29.md` |
| Reframe brief | `refine-logs/ADSR_REFRAME_BRIEF.md` |
| Pre-ADSR snapshot | `orbit-research/archive/etv_pre_adsr_20260604/refine-logs_FINAL_PROPOSAL.md` (the v3.0 ETV proposal). |
| Companion contracts | `refine-logs/METHOD_SPEC.md` (ADSR section), `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0, `orbit-research/CONTROL_DESIGN.md`, `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum". |

---

## 0. Executive abstract

Inference-time scaling for flow-matching music generation today relies on
Best-of-N (BoN): draw N independent seeds, run every one of them to a full
denoising trajectory, then select. This is expensive, and — as we show below —
it is also *low-stakes selection*: on ACE-Step v1.5 the same-prompt candidates
are near-tied (median selection regret ≈ 0; raw Early-Tweedie pruning at 50 %
compute beats BoN-4 by only ≈ +0.0036 robust-LCB). The interesting lever is not
*which of a fixed pool to keep* but *when a trajectory is worth continuing at
all*, so that wasted compute can be **reallocated to new independent seeds**.

We propose **Axis-Deferred Speculative Restart (ADSR)**: use early Tweedie-clean
estimates to **terminate low-promise trajectories early and restart new seeds**
(RESTART), while **deferring** decisions for late-observable axes (lyric
intelligibility, fine semantic alignment) to later in the trajectory (DEFER),
and otherwise continuing (CONTINUE). The scientific core is **axis-dependent
observability**: different quality axes become predictable at different noise
levels, with aesthetic/production cleanliness and **vocal presence** observable
early, semantic alignment in the middle, and **lyric intelligibility latest**.
A second, conceptually distinct move is the **presence-vs-content split**:
detecting *whether a voice is present* is coarse and early-decidable, whereas
judging *which words are sung and whether they are intelligible* is fine and
late-decidable. This lets ADSR early-reject the high-stakes, categorical failure
of a **prompt-type mismatch** (an instrumental rendering for a vocal prompt, or
vice versa) without violating the rule "defer lyric" — early rejection judges
*presence*, not *content*.

ADSR is realized with **two distinct learned components**: (a) a lightweight
**quality verifier** on scalar early features (near-saturated; ridge within-prompt
NDCG ≈ 0.995 — capacity is not the bottleneck), and (b) an **Early Vocal-Presence
Detector (EVPD)** — a *learned audio model* (small CNN / fine-tuned pretrained
audio encoder) that predicts FINAL vocal presence from the EARLY Tweedie-clean
mel-spectrogram. The EVPD warrants a real neural network because perceiving audio
under heavy early-σ noise is a genuine learning problem and is out-of-distribution
for off-the-shelf detectors trained on clean audio.

**Evidence honesty (read this first).** This is a **plan-stage proposal for a new
method**, anchored on an existing empirical foundation. The foundation evidence is
real and repurposed: H1/H2 early-quality persistence (Phase A headroom
`delta_sigma_bon_vs_base = 0.7549`; H2 `STRONG_PASS` on 128 prompts; Track B
globalness 0.861); Track A raw-Early-Tweedie pruning (Schedule A recovers
**0.9864** of full-BoN-8 reward at **0.500** compute, regenerated 2026-06-04 on
the lyric-fix dataset — was 0.9858 on 2026-05-28, within noise; bottom-prune σ=0.7
false-negative 0.0195); the lyric axis scored EN-vocal-only (**0.682** ETP@50,
**n=282**, 248/282 = 88 % carrying signal; instrumental 1.0 sentinel masked,
non-EN excluded); and the C1 RL boundary (no clear first-wave common-metric gain).
But the *new* ADSR machinery is **not yet run**: the **EVPD is not trained** (E3),
**restart / the full ADSR loop is not run** (E6 — only offline-simulatable on the
existing 4096-candidate pool), **final vocal-presence labels are not yet derived**,
and the **H2b presence/content split is unmeasured**. We do not claim ADSR results
that do not exist.

> **Abstract core sentence.** *We show that final music quality in flow-matching
> generation becomes observable axis-by-axis at different points in the denoising
> trajectory — vocal presence and production quality early, lyric content late —
> and we use this to decide when a trajectory is worth continuing, terminating
> low-promise trajectories early and reallocating their compute to new seeds
> (axis-deferred speculative restart), while deferring late-observable axes and
> early-rejecting high-stakes prompt-type errors with a learned vocal-presence
> detector.*

---

## 1. Reframed problem

Flow-matching music generators have inference-time headroom: BoN-style search
produces measurably better outputs than the base sampler
(`delta_sigma_bon_vs_base = 0.7549` on Phase A held-out; CFG and S7 sampler-control
controls negative). But two facts reshape the question:

1. **BoN is expensive and runs every candidate to completion.** Each candidate
   needs a full denoising trajectory regardless of how unpromising it looks early.
2. **Fixed-pool selection is low-stakes.** On ACE-Step v1.5 the same-prompt
   candidates are near-tied: median selection regret ≈ 0, and raw Early-Tweedie
   pruning at 50 % compute beats BoN-4 by only ≈ +0.0036 robust-LCB (Track A).
   The win from picking the best of a *fixed* pool is small because the pool is
   full of near-optimal renderings.

So the right question is not "which candidate to keep" but:

> **When along the flow-matching trajectory can we decide that a trajectory is
> not worth continuing — so we can terminate it early and reallocate that compute
> to a fresh independent seed — and which quality axes must be deferred until
> later before any such decision is safe?**

Two sub-structures answer this.

**Axis-dependent observability (the scientific core, H2).** Different quality axes
become predictable at different σ. Expected ordering as σ decreases:
*aesthetic/production cleanliness and vocal presence (early) → semantic alignment
(mid) → lyric intelligibility (latest).* Phase B.1 (H2, 128-prompt verdict) and
Track A's 512-prompt × 4096-candidate validation jointly establish that by
σ ∈ {0.9, 0.8, 0.7} intermediate Tweedie reconstructions already carry
final-quality signal across multiple reward axes (7/7 axes have at least one
primary-σ survival). `lyric_intelligibility` is the canonical *latest* axis and is
evaluated **only** on its EN-vocal subset (n=282, 248/282 = 88 % carrying signal;
instrumental prompts hold a constant 1.0 Whisper sentinel and are masked; non-EN
vocal prompts the English-only scorer cannot rate are excluded — see
`orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`).

**Presence vs. content (H2b, new).** The conceptual move that makes early rejection
safe without violating "defer lyric": **vocal *presence* (is there singing at all?)
is coarse and early-decidable; lyric *content* (which words, sung correctly,
intelligibly?) is fine and late-decidable.** Early-rejecting a gross prompt-type
mismatch — instrumental output for a vocal prompt, or vice versa — judges
*presence*, not *content*, and is therefore legitimate even though we still defer
lyric intelligibility to late σ. A prompt-type mismatch is a *categorical, unusable*
failure, unlike near-tied aesthetic differences, which is what makes it a
high-stakes early-reject target rather than a low-stakes selection nicety.

Therefore inference-time scaling should neither generate all candidates to
completion nor blindly prune on a single early global score. Instead: early-reject
trajectories that are clearly bad on **early-observable axes** (including
prompt-type mismatch) and **reallocate** that compute to new seeds, while
**deferring** axes that only become reliable later (lyric intelligibility, fine
semantics).

---

## 2. Hypotheses

Verbatim anchor to ADSR plan §2.

- **H1 — Early trajectory quality persistence.** High/low-quality trajectories
  separate early: early low-quality candidates rarely become final winners; early
  top-k contains most final winners; bottom-prune false-negative rate is low.
  *(Foundation evidence: Phase A headroom; H2 STRONG_PASS; Track B globalness;
  Track A retention.)*
- **H2 — Axis-dependent observability (the scientific core).** Different axes
  become predictable at different σ. Expected ordering as σ decreases:
  *aesthetic/production and vocal presence (early) → semantic alignment (mid) →
  lyric intelligibility (latest).*
- **H2b — Presence-vs-content split (new).** *Vocal presence* (is there singing?)
  is early-decidable; *lyric intelligibility* (which words?) is late-decidable. The
  two must be measured and treated as separate axes. **Unmeasured to date.**
- **H3 — Restart beats fixed-pool selection.** Fixed-pool selection is low-stakes
  when same-prompt candidates are near-tied (median regret ≈ 0; raw ETP@50 over
  BoN-4 ≈ +0.0036). Speculative restart escapes this by early-stopping bad
  trajectories and reallocating compute to new seeds, exploring more useful
  trajectories under the same budget.
- **H4 — Axis-deferred restart preserves late axes.** Restart only when
  early-observable axes are bad; defer uncertain semantic/lyric decisions to later
  σ so late-observable quality is not sacrificed.
- **H5 — Type errors are high-stakes and early-catchable (new).** Generating an
  instrumental output for a vocal prompt (or vice versa) is a *categorical,
  unusable* failure — unlike near-tied aesthetic differences. Human listening
  indicates such mismatches are detectable early in the trajectory, making them a
  high-stakes early-reject target. **EVPD not yet trained; onset σ not yet measured.**
- **H6 — Human evidence (already obtained).** Large-scale human listening confirms:
  early perceptual quality predicts final perceptual quality; bad trajectories are
  uniformly bad; late-bloomers are rare; and vocal presence is identifiable early
  by ear. This is the empirical license for early rejection.

---

## 3. Six paper-bearing claims

Per `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum"
(rows C1–C6). Each row marks its **evidence status**: *foundation* (existing data,
repurposed), *supported* (existing data, directly measured), or *planned* (the new
ADSR machinery, not yet run).

| # | Claim | Type | Status | Empirical anchor |
|---|---|---|---|---|
| **C1** | Axis × σ observability map: quality axes become observable at different stages — aesthetic/production & vocal presence (early) → semantic (mid) → lyric intelligibility (latest) — validated against human early→final judgments. | core scientific | foundation (axis signal) + **planned** (full map incl. presence/lyric rows, human early→final) | H2 STRONG_PASS (128 prompts); Track A retention; E1 + E2 to complete the map. |
| **C2** (main method) | **ADSR**: axis-deferred speculative restart — terminate low-promise trajectories early and **reallocate** compute to new independent seeds, deferring late-observable axes. Compute *reallocation*, not fixed-pool selection. | main contribution | **planned** (E6, offline-simulatable now; full restart not yet run) | H3 (low-stakes selection: ETP@50 over BoN-4 ≈ +0.0036) motivates restart; E6 to validate. |
| **C3** (new) | **Prompt-type match is an early-decidable, high-stakes axis,** realized by a **learned Early Vocal-Presence Detector (EVPD, an audio model)** used as a high-priority early-reject signal; type errors are unusable and so partially answer "selection is low-stakes" from a different angle. | new contribution | **planned** (EVPD not trained; labels not derived; E3) | E3 EVPD training + type-error prevalence + onset σ; vocal-presence labels to be derived. |
| **C4** | Compute–quality Pareto improvement over BoN-k (same compute), Full BoN-N, random prune/restart, **raw ETP**, and learned-verifier selection. | method evidence | foundation (raw-ETP point) + **planned** (ADSR curve) | Track A raw ETP 0.9864 @ 0.500; E4/E5/E6 to place ADSR on the Pareto. |
| **C5** | **Lyric as a first-class late-observable axis,** evaluated **only** on lyric-bearing vocal prompts (no instrumental-sentinel pollution), demonstrating why deferral is necessary; paired with the presence/content disentanglement. | supported (axis) + **planned** (deferred-eval result) | supported / planned | Lyric 0.682 ETP@50, n=282 EN-vocal; E7 deferred lyric eval. |
| **C6** | RL post-training boundary result: LoRA/GRPO technically feasible but no clear first-wave common-metric gain — supporting the shift to inference-time compute *allocation* over RL post-training. | boundary | supported | C1 RL first wave: R8a/R8b/M-FixedWin/M-Section all within +0.012 to +0.014 LCB of base. |

C1 (axis signal), C5 (lyric axis), and C6 (RL boundary) are anchored in existing
canonical evidence; the *new* method contributions C2 (ADSR restart) and C3 (EVPD /
prompt-type) are forward-looking and not yet run. C4 has one anchored point
(raw-ETP) and one planned curve (ADSR). The simplicity check (ADSR plan §3) holds:
one new *trainable audio* component (EVPD) plus a near-saturated lightweight quality
verifier; the headline novelty is the **method** (reallocation-by-restart + axis
deferral + presence/content split), not model complexity.

---

## 4. Method: ADSR

(High-level here; implementation contract in `refine-logs/METHOD_SPEC.md` "ADSR"
section and `orbit-research/ALGORITHMIC_FORMALIZATION.md` "2026-06-04 ADSR Pivot
Addendum". ETV three-tier pruning machinery from v3.0 is retained as the raw-ETP
*baseline* and superseded boundary, not the headline.)

### 4.1 Inputs and features
For each candidate trajectory: prompt, seed, current σ, latent `x_σ`, model
velocity `v_θ`, and the Tweedie-clean estimate `x̂₀ = x_σ − σ·v_θ`. Decode `x̂₀`
to an early audio/mel estimate. Features:

- **Scalar quality features** (for the lightweight quality verifier): early
  axis-wise scores (aesthetic/production, semantic) at σ ∈ {0.9, 0.8, 0.7},
  within-prompt rank at each σ, score slope across σ, uncertainty/risk, and prompt
  metadata.
- **Audio/spectrogram features** (for the EVPD): the early Tweedie-clean
  mel-spectrogram of `x̂₀` itself.
- **Flags:** vocal/instrumental requested by prompt; lyric-bearing flag.

### 4.2 Two distinct learned components (and why their sizes differ)

1. **Quality verifier (lightweight).** Predicts safe-restart probability,
   late-axis risk, and final rank/survival from **scalar** features. Model ladder:
   raw early score (baseline) → linear/ridge → logistic → GBDT / LambdaMART /
   pairwise (primary). **No large neural model:** ridge already saturates
   within-prompt NDCG (≈ 0.995); capacity is *not* the bottleneck — the label
   signal is limited by near-tied candidates. This is the v3.0 `V_σ` verifier,
   repurposed and demoted to a supporting role inside the ADSR decision logic.
2. **Early Vocal-Presence Detector, EVPD (learned AUDIO model — new).** Predicts
   **FINAL vocal presence** from the **early Tweedie-clean mel-spectrogram**. This
   component *does* warrant a learned audio network (small CNN, or a pretrained
   audio encoder fine-tuned), because presence detection requires reading the
   audio, not scalar features, and the early-σ domain (heavy-noise reconstructions)
   is out-of-distribution for off-the-shelf detectors trained on clean audio.
   **Prompt-type match** = compare EVPD's predicted final presence to the prompt's
   requested type. **Status: not yet trained; this is the central new
   experimental obligation (E3).**

> The two components are deliberately different sizes: scalar-feature ranking is a
> near-saturated, low-capacity problem; early audio perception under heavy noise is
> a genuine learning problem that justifies a real neural net.

### 4.3 Decisions (reallocation, not selection)
```
RESTART  : terminate the CURRENT trajectory; launch a NEW independent seed
           (a fresh draw — NOT a rollback, repair, or re-noising of the same seed)
DEFER    : continue this candidate to a later σ before deciding
CONTINUE : continue full generation
```
RESTART is the defining mechanism: it *reallocates* the compute that would have
been spent finishing a low-promise trajectory into exploring a new region of the
seed space. This is what distinguishes ADSR from ETV-style pruning (which only
discards within a fixed pool) and from BoN (which finishes everything).

### 4.4 Decision logic (type-match has priority)
```
# 1) High-stakes, early, coarse: prompt-type match (presence, not content)
if EVPD predicts final-type ≠ requested-type with high confidence:
    RESTART                      # gross type error — categorical, unusable failure

# 2) Early-observable quality
elif early_quality clearly low and late_axis_risk low/irrelevant:
    RESTART

# 3) Late-observable content: never reject early
elif semantic_or_lyric(content)_risk high/uncertain:
    DEFER                        # judged at later σ; lyric is the canonical defer case

else:
    CONTINUE
```
Key distinction: **vocal *presence* and bad production can be judged early; lyric
*content* cannot** — so type errors trigger RESTART early while lyric uncertainty
triggers DEFER.

### 4.5 Compute accounting and offline-first
Compare at **matched expected total NFE**, with **no optimistic accounting**:

```
expected_total_NFE =
      partial-trajectory cost to σ_c            (paid for every started candidate)
    + surviving-trajectory full cost            (CONTINUE / DEFER survivors)
    + restart new-seed cost                     (every RESTART pays a fresh trajectory)
    + deferred-continuation cost                (DEFER candidates carried to later σ)
```

**Offline-first protocol.** First validate ADSR **offline on the existing
4096-candidate pool** (`orbit-research/trajectory_candidate_dataset.jsonl`): treat
each candidate's early scores and EVPD output as the verdict, and define "RESTART =
draw the next independent pool candidate for that prompt." This makes E6 runnable
with **0 new GPU-h** as a simulation. Only then confirm with a small real-generation
run where restart actually launches a fresh seed. The 4096-candidate pool, the
prompt-level split (by `prompt_id`, never `candidate_id`), the reward definitions,
the gate policy (`configs/eval/gate_v2.yaml.draft`), and the compute-accounting
conventions are all carried over unchanged from the ETV-era infra — only the method
is reframed.

---

## 5. Data plan

**Main candidate dataset fields** (`orbit-research/trajectory_candidate_dataset.jsonl`,
canonical reward set, promoted 2026-06-04 after the lyric-fix regen):
`prompt_id`, `candidate_id`, `seed`, `split`, final reward & rank, early-σ scores
(0.9/0.8/0.7), axis-wise early & final scores, **final vocal-presence label (new)**,
vocal/instrumental flag (requested), lyric-bearing flag, prompt category, compute
metadata. **Split by `prompt_id`, never by `candidate_id`** (prevents same-prompt
candidate leakage). Source per-shard records:
`runs/early_tweedie_validation_512_bon8_20260527_full01/` (380 unchanged prompts) +
`runs/early_tweedie_validation_final_lyricfix_20260603/` (132 regenerated).

**Vocal-presence labels (new — not yet derived).** Derive final vocal-presence per
candidate via source separation (Demucs / Spleeter) vocal-energy-ratio thresholding,
or a dedicated singing-voice-detection (SVD) model. Whisper `no_speech_prob` is a
*coarse pre-filter only* — Whisper targets speech, not singing, and instrumental
audio can false-trigger, so it cannot be the ground-truth label. **Relabel the
existing 4096 candidates** retroactively so vocal presence is available for the
offline studies. This relabeling is a prerequisite for E3/E6 and is currently
**outstanding**.

**Scale.** Achieved: 512 prompts / BoN-8 / 4096 candidates. Next: BoN-16 subset
≥128 prompts (256 if compute allows).

**Lyric-bearing subset.** 200–300 lyric-bearing vocal prompts; English clean core;
≥3 lyric lines where possible; separate calibration/evaluation split. Report
**separately**: (a) clean English core, (b) broader lyric-bearing vocal, (c)
multilingual-or-thin-lyric stress arm. **Never mix instrumental prompts into
headline lyric metrics.** Split by `prompt_id`. The lyric axis is currently scored
EN-vocal-only (0.682 ETP@50, n=282; per
`orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`).

---

## 6. Experiments

Nine experiments (anchor: ADSR plan §6). Each is explicitly marked **[RUN]**
(executed; foundation evidence repurposed), **[PARTIAL]** (foundation point exists,
new analysis required), or **[PLANNED]** (the new ADSR machinery; not yet run).

### E1 — Axis × σ observability matrix  **[PARTIAL]**
Axes (rows): common/robust quality, aesthetic/production, **vocal presence
(coarse)**, **lyric intelligibility (fine) on the lyric-bearing vocal subset**,
semantic_fit, coherence. σ (columns): 0.9 / 0.8 / 0.7 / 0.5 / 0.3 / final. Metrics:
Spearman early-vs-final, within-prompt NDCG, winner & top-k retention, axis
preservation, false-negative. **Fix the lyric stratum first** (sentinel pollution
already removed — see lyric-fix report). **Vocal presence and lyric intelligibility
are separate rows; we expect vocal-presence-onset ≪ lyric-onset.** Foundation: the
σ ∈ {0.9,0.8,0.7} signal across 7/7 axes already exists (H2/Track A); the
presence/lyric rows and the full σ-grid are **new analysis to complete**. Output:
`AXIS_OBSERVABILITY_MATRIX.{md,csv}` + heatmap. Pre-register early/late thresholds.

### E2 — Human early→final validation (license for restart)  **[RUN, repurposed]**
Write up the large-scale human listening as a first-class result: (a) early-σ
perceptual quality predicts final **human-judged** quality; (b) uniform-badness
quantified; (c) late-bloomer rarity; (d) **humans can identify vocal presence
early** (small targeted listening on early estimates at σ = 0.9/0.8/0.7). The
existing human-listening evidence (H6) is repurposed here; the early
vocal-presence listening sub-check is **new**. Distinct from the method-preference
spot-check (E8). This is the core defense against reward-circularity and "what if
you restart a late-bloomer?"

### E3 — Early Vocal-Presence Detector and prompt-type-error study  **[PLANNED — new, not yet run]**
**Goal:** establish that vocal presence is early-decidable and that type errors are
catchable early. **EVPD is not yet trained and vocal-presence labels are not yet
derived — this is the central new experimental obligation.**
1. **Ground truth:** final vocal-presence per candidate (source separation / SVD).
2. **Prevalence:** rate of vocal-prompt→instrumental and instrumental-prompt→vocal
   errors (a useful result in itself).
3. **Detector:** train EVPD on early Tweedie-clean mel-spectrograms with the final
   vocal-presence label; report early-detectability AUC and the **vocal-presence
   decidability onset σ**. For error cases, test whether the early estimate already
   shows the wrong type.
4. **Disentangle existing data:** split the current lyric-zero candidates into
   *type errors* (no voice → no transcription) vs *content failures* (voice present
   but unintelligible) — exactly the H2b presence/content distinction.
5. **Closed loop:** test whether type-match restart improves the final selected
   output's **prompt-type-match rate** vs no restart (E3 — not yet run).
Metrics: AUC, onset σ, type-error prevalence, prompt-type-match rate after restart,
false-restart rate on type.

### E4 — Raw pruning and same-compute baselines  **[RUN, repurposed as baseline]**
Compare Full BoN-8 / BoN-4 (same compute) / random prune / **raw Early-Tweedie
pruning (raw ETP)**. Schedules: A (σ0.9 top4 → σ0.7 top2 → top1, compute 0.500),
B (σ0.8 top4 → σ0.7 top2 → top1, 0.583), C (σ0.8 top6 → top1, 0.850), bottom-prune
(remove bottom-25 % at σ0.7/0.8). Metrics: compute/reward fraction, winner_match,
top-2 retention, false_negative, regret. **Critical comparison: raw ETP@50 vs
BoN-4** — the known delta is ≈ +0.0036, which is *why raw ETP cannot be the
headline* and ADSR (reallocation) is needed. Track A canonical: Schedule A recovers
**0.9864** reward fraction at **0.500** compute (regenerated 2026-06-04 on the
lyric-fix dataset; was 0.9858 on 2026-05-28, within noise); random pruning at
matched compute recovers only 0.9570; bottom-prune σ=0.7 false-negative 0.0195.

### E5 — Learned quality verifier  **[PLANNED — extends existing feature cache]**
Targets: final robust-reward regression, final rank, top-1/2/4 survival,
safe-restart label, late-axis risk label. Models per §4.2 (lightweight: ridge →
GBDT / LambdaMART). Metrics: Spearman, NDCG, survival AUC, false-negative at
calibrated thresholds, winner retention, reward_fraction under pruning. **Framing:**
the verifier is useful only if it improves *safe-restart calibration* / *late-axis
defer* / the *Pareto* — not because it is complex (ridge NDCG ≈ 0.995 shows capacity
is saturated). Runs on the cached feature set (CPU-only).

### E6 — Axis-Deferred Speculative Restart (main method)  **[PLANNED — offline-simulatable now, full restart not yet run]**
Compare Full BoN-8 / BoN-4 / random restart / raw restart / learned-verifier
restart / **type-match restart** / **axis-deferred restart (full ADSR, including the
EVPD type-match branch)**. Decisions: RESTART / DEFER / CONTINUE. Metrics: expected
compute, final robust reward, semantic & lyric preservation, **prompt-type-match
rate**, winner retention, false-restart rate, human preference. **Strict
expected-compute accounting (§4.5).** Ablations: σ_c, thresholds, sequential vs.
batch-speculative restart, restart budget; **two-factor ablation
(axis-awareness × restart-reallocation)**; and **with/without the EVPD type-match
branch**. **First run offline on the 4096-candidate pool** (restart = draw next
independent pool candidate; 0 new GPU-h), then a small real-generation confirm.
This is the make-or-break experiment for C2.

### E7 — Lyric-focused deferred evaluation  **[PLANNED — anchored on the lyric-fix axis]**
Data: lyric-bearing vocal (clean English core + stress arm). Compare aesthetic-only
restart / common-score restart / axis-deferred restart / Full BoN / BoN-k. Metrics:
lyric intelligibility (Whisper/ASR-based), **lyric-decidability onset vs.
ASR-transcribability onset (mechanistic anchor)**, semantic prompt fit, overall
quality, false lyric-degradation rate. **Success:** ADSR improves lyric/semantic
preservation over naive early restart while retaining most common-quality gains.
Multilingual arm uses language-matched ASR or is clearly scoped. Foundation: the
lyric axis is already scored EN-vocal-only at 0.682 (n=282); the deferred-eval
comparison is new.

### E8 — Human spot-check (method preference)  **[PLANNED]**
32–64 blind A/B comparisons, same prompt: Full BoN vs ADSR / BoN-4 vs ADSR / random
restart vs ADSR / raw restart vs axis-deferred restart. Rubric: overall, musicality,
prompt fit, **vocal presence / type correctness**, lyric correctness/intelligibility,
vocal artifacts. **Human judgment overrides automatic reward in framing when they
conflict.** Pilot 32 pairs; expand to 64 conditional on signal.

### E9 — Robustness and generality  **[PARTIAL / PLANNED]**
**Required (cheap) cross-regime within ACE-Step:** vocal vs instrumental,
lyric-bearing vs non-lyric, genre/style buckets, BoN-8 vs BoN-16, easy vs hard
prompts. **High-priority, Phase-1-parallel-started cross-backbone:** replicate
E1 + E3 + E6 on a second flow-matching audio/music backbone (Stable Audio Open),
elevating the finding from an ACE-Step fact to a flow-matching principle.
**Graceful fallback:** if the second backbone is not ready in time, fall back to
cross-regime + an honest target-regime limitation — it is pursued in parallel from
the start and **does not gate submission**, not a Phase-5 afterthought.
**Cross-backbone is not started.**

---

## 7. Baselines

**Required (main comparison):** Full BoN-8, BoN-4, random prune/restart, **raw ETP**,
learned-verifier selection, **type-match restart**, **ADSR**.
**Optional:** BoN-16, non-Tweedie early audio proxy, late-only selection, oracle
final selector, **off-the-shelf (non-early-trained) vocal detector as a baseline for
EVPD**.
**Boundary (not main comparison):** M-FixedWin-PRM, M-Section-PRM, R8a/R8b. These are
the demoted ETV-era / M-PRM RL comparisons; they appear as a single boundary
paragraph, not a defended chapter.

| Method | Compute fraction | Role |
|---|---:|---|
| Full BoN-8 | 1.000 | reference |
| BoN-4 (uniform smaller-N) | 0.500 | **critical control** |
| Random prune / random restart | 0.500 | floor |
| Raw ETP Schedule A | 0.500 | strong baseline (Track A canonical; **was the v3.0 headline, now a baseline**) |
| Raw ETP Schedule B / C / bottom-prune | 0.583 / 0.850 / 0.883 | alt-σ / high-compute references |
| Learned-verifier selection | 0.500 | supporting |
| **Type-match restart (EVPD)** | matched | new contribution |
| **ADSR (axis-deferred speculative restart)** | matched | **main method** |

---

## 8. Success criteria

- **Minimum:** ADSR beats same-compute BoN-k and random restart on robust/common
  metrics.
- **Method success:** ADSR preserves common quality while improving semantic/lyric
  preservation over non-deferred restart, **and improves prompt-type-match rate via
  the EVPD branch.**
- **Strong:** ADSR approaches Full BoN-8 at substantially lower compute and is no
  worse in human preference.
- **Top-tier:** at matched compute, ADSR outperforms Full BoN-8 by exploring more
  effective independent seeds.

---

## 9. Failure modes and interpretation

(Anchor: ADSR plan §9; full routing in `orbit-research/NULL_RESULT_CONTRACT.md`
"2026-06-04 ADSR Pivot Addendum".)

| Null result | Retracts | Paper still has / fallback |
|---|---|---|
| **ADSR ≤ BoN-4** (E6) | C2 main-method headline | fall back to an **axis-observability + trajectory-analysis paper** (C1 + C5 + C6), or a workshop/audio venue. |
| Improves common quality but **hurts lyric** (E7) | C4 lyric-preservation claim | axis-deferred logic insufficient → strengthen lyric defer / use later σ for lyric / restrict to non-lyric settings. |
| **Vocal presence NOT early-decidable** (EVPD onset late, E3) | C3 early-reject framing | demote the type-match branch to a later-σ check; **report onset honestly**. A mid-trajectory onset still saves the back half of compute, so value likely persists — but the claim must follow the measured onset. |
| **Lyric subset too noisy** (E7) | headline lyric result | lyric stays first-class but the claim becomes "lyric observability is difficult and needs better measurement"; do not force a headline lyric number. |
| **Second backbone fails** (E9) | cross-backbone generality | submit with a target-regime limitation if ACE-Step results are strong (does not gate submission). |
| **Human disagrees with reward** (E8) | automatic-metric headline | weaken the automatic claim; **human result overrides**. |

The paper has multiple honest landing zones; the worst-case headline (axis
observability + presence/content + human early→final validation) remains
publishable even if the restart mechanism underperforms.

---

## 10. Prior RL / credit experiments (boundary — C6)

Summarized as boundary evidence: section credit not supported as the best default
unit; FixedWin behaves like a persistent-quality proxy; LoRA/GRPO first-wave stable
but **no clear common-metric gain** (R8a +0.0116, R8b +0.0145, M-FixedWin +0.0121,
M-Section +0.0124 LCB — all within noise). Track B explains the result: short-form
quality differences are persistent-global (globalness 0.861, sign consistency 1.000,
crossing frequency 0.000), leaving little local-credit residue for RL to exploit at
first-wave scale. **Interpretation:** the most reliable current use of early
trajectory information is inference-time compute *allocation* (ADSR), not RL
post-training. Do not hide these, but do not center the paper on them. New σ-axis RL
is future work, not in the main execution plan.

---

## 11. Execution plan (ample compute → parallel; ADSR plan §11)

- **Phase 1 — Repair lyric measurement, build observability, add vocal-presence
  labels.** Lyric aggregation/sentinel fix is **done** (lyric-fix report); generate/
  evaluate the lyric-bearing subset; **derive vocal-presence labels (outstanding)**;
  produce the axis × σ heatmap (E1). **Start second-backbone engineering integration
  in parallel** (long-lead item). Gate: can lyric be a late-observable headline axis,
  and is vocal-presence-onset ≪ lyric-onset?
- **Phase 2 — Human early→final validation (E2),** including the early
  vocal-presence listening check. Gate: do humans support early decidability
  (quality and presence)?
- **Phase 3 — Train EVPD + type-error study (E3) and ADSR offline simulation
  (E6 offline).** Gate: is vocal presence early-decidable, and does ADSR (with
  type-match) beat BoN-k/random under fair compute? **(make-or-break)**
- **Phase 4 — Learned quality verifier and risk calibration (E5).** Gate: does the
  verifier improve decision quality (safe-restart / late-axis defer)?
- **Phase 5 — Human spot-check (E8).** Gate: does human judgment support ADSR?
- **Phase 6 — Robustness + cross-backbone replication (E9).** Gate: can we claim
  more than one narrow setting?
- **Phase 7 — Paper assembly.** Rewrite proposal, figures, method, limitations,
  reviewer-risk response.

---

## 12. Compute envelope (5,400 GPU-h on 8× A800)

| Phase / Track | Status | GPU-h used | GPU-h remaining |
|---|---|---:|---:|
| Phase A headroom audit | done | ~170 | — |
| Phase B.1 H2 reliability | done | 0.77 | — |
| Phase B.3 H3 prescreen | done | ~5 | — |
| Phase C0 backend smoke | done | <2 | — |
| Phase C1 first-wave RL (C6 boundary evidence) | done | 119.75 | — |
| Track A Early-Tweedie validation (raw-ETP baseline) | done | 243.10 | — |
| Track B global-quality structure | done | 0 (CPU) | — |
| Track C bounded RL rescue | stopped | 0 | — |
| **Subtotal consumed** | — | **~540** | — |
| **Remaining for ADSR program** | — | — | **~4,860** |

ADSR program forward cost:
- E1 observability matrix, E5 verifier, E6 **offline** ADSR simulation, E7 deferred
  lyric eval: post-hoc on cached candidates → **≤ ~15 CPU-h, 0 GPU-h**.
- E3 EVPD training: small audio model on cached early mel-spectrograms; GPU-light
  (single-GPU, ≤ a few dozen GPU-h budgeted for training + relabeling-separation
  passes).
- E6 real-generation confirm (small restart run): bounded — mirrors a fraction of
  Track A scope; budget ≤ ~250 GPU-h.
- E2 / E8 human eval: ~10–20 listener-hours, 0 GPU-h.
- E9 cross-backbone (Stable Audio Open): parallel, long-lead engineering;
  does not gate submission.
- Reserve: ≥ 4,000 GPU-h.

The expensive foundation work (Phase A, H2, Track A, Track B, C1) is already done;
the new ADSR machinery (EVPD training, restart) is modest in compute. The honest
caveat is *experimental, not budgetary*: the new components are unrun.

---

## 13. Figures

- **Fig 1** Axis × σ observability matrix (concept figure; rows include
  vocal-presence and lyric-intelligibility as **separate** axes; mark
  vocal-presence and lyric/transcribability onsets; vocal-presence-onset ≪
  lyric-onset).
- **Fig 2** ADSR algorithm flowchart: sample → early Tweedie estimate → EVPD
  type-match + scalar score axes → RESTART / DEFER / CONTINUE.
- **Fig 3** Compute–quality Pareto (x: compute fraction; y: reward fraction / human
  preference; curves: BoN-k, random, raw ETP, learned-verifier selection, type-match
  restart, **ADSR**).
- **Fig 4** Lyric and prompt-type preservation (methods vs. lyric / prompt / type
  preservation; **lyric-bearing subset only**).
- **Fig 5** Failure cases (late bloomers, false restarts, type errors caught/missed,
  lyric failures; presence vs content disentanglement).

---

## 14. Anti-overclaim (ADSR plan §14)

Claims we must **avoid**:

- Music quality is *always* globally determined.
- Sections *never* matter.
- Lyric can be evaluated over *all* prompts (it is reported EN-vocal-only, n=282;
  instrumental prompts carry a masked 1.0 sentinel; non-EN vocal prompts are
  excluded — held-out generalization is **cross-prompt, not cross-content**, and is
  reported **per specificity stratum**).
- ADSR has **distribution-free guarantees**.
- ADSR **universally generalizes** to all flow models.
- Vocal presence is **always trivially detectable at any σ** (the onset σ is to be
  measured by E3, not assumed; EVPD is not yet trained).
- **RL post-training does not work** (only first-wave LoRA/GRPO on this shared
  backend showed no common-metric gain).

The narrow stronger claim we *can* make if experiments succeed: *for flow-matching
music generation with ACE-Step v1.5, quality axes become observable at different
points in the denoising trajectory — vocal presence and production early, lyric
content late; this licenses terminating low-promise trajectories early and
reallocating their compute to new seeds (axis-deferred speculative restart), with a
learned early vocal-presence detector catching high-stakes prompt-type errors, while
late-observable axes are deferred.*

---

## 15. Honest evidence-status summary

Because this is a **plan-stage proposal for a new method**, the evidence ledger is
split explicitly. Reviewers and the PI should read this section as the single source
of truth on what exists vs. what is proposed.

**Foundation evidence that EXISTS and is repurposed:**
- **H1/H2 early-quality persistence:** Phase A headroom
  `delta_sigma_bon_vs_base = 0.7549` (CFG / S7 controls negative); H2 STRONG_PASS on
  128 prompts (7/7 axes with ≥1 primary-σ survival); Track B globalness 0.861, sign
  consistency 1.000, crossing frequency 0.000.
- **Track A raw-ETP pruning (now a baseline, not the headline):** Schedule A recovers
  **0.9864** of full-BoN-8 reward at **0.500** compute (regenerated 2026-06-04 on the
  lyric-fix dataset; was 0.9858 on 2026-05-28, within noise, decision unchanged);
  random at matched compute 0.9570; bottom-prune σ=0.7 false-negative 0.0195.
- **Lyric axis:** scored EN-vocal-only, **0.682** ETP@50, **n=282** (248/282 = 88 %
  carrying signal); instrumental 1.0 sentinel masked, non-EN excluded
  (`prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`).
- **Human listening (H6):** large-scale listening already obtained — early perceptual
  quality predicts final; bad trajectories uniformly bad; late-bloomers rare; vocal
  presence audible early.
- **C1 RL boundary (C6):** no clear first-wave common-metric gain across four methods.

**The NEW ADSR machinery that is NOT yet run (forward-looking):**
- **EVPD is NOT trained** (E3); final **vocal-presence labels are NOT yet derived**
  (Demucs/Spleeter/SVD relabeling of the 4096 pool outstanding).
- **The restart mechanism / full ADSR loop is NOT run** (E6) — only
  offline-simulatable on the 4096-candidate pool; the small real-generation confirm
  is unrun.
- **The H2b presence-vs-content split is unmeasured** (lyric-zero candidates not yet
  partitioned into type-errors vs content-failures).
- **Cross-backbone (Stable Audio Open) is not started** (E9; does not gate
  submission).

We do **not** claim ADSR results that do not exist. Every C2/C3 row in §3 is marked
*planned*; every figure showing an ADSR curve (Fig 2/3) is contingent on E3/E6.

---

## 16. STOP-A checklist for `/experiment-bridge`

- [ ] PI signs off on FINAL_PROPOSAL v4.0 (ADSR).
- [ ] PI signs off on `METHOD_SPEC.md` ADSR section (restart/defer/continue logic,
  EVPD audio model + label derivation + onset σ, quality verifier, decision
  thresholds, §4.5 compute accounting, offline-first protocol, vocal-presence data
  fields).
- [ ] PI signs off on `EXPERIMENT_PLAN_EXEC.md` v4.0 (E1–E9 with go/no-go gates,
  Phases 1–7).
- [ ] PI approves the **EVPD as a learned audio model** (small CNN / fine-tuned
  pretrained encoder) and the GPU-light training budget for E3.
- [ ] PI approves **deriving final vocal-presence labels** (Demucs/Spleeter
  vocal-energy ratio or SVD model; Whisper `no_speech_prob` coarse pre-filter only)
  and **retroactively relabeling the existing 4096 candidates**.
- [ ] Held-out vs dev split reuses Track A's 256/256 prompt-level split (no
  resampling). This is **cross-prompt** generalization (seen vocabulary, unseen
  prompt combination), **NOT cross-content**; dev→held-out comparisons reported
  **per specificity stratum** to control the rewrite-rate confound (prompt-set audit
  R5). Split by `prompt_id`, never `candidate_id`.
- [ ] Canonical reward set is `orbit-research/trajectory_candidate_dataset.jsonl`
  (promoted 2026-06-04 after the lyric-fix regen; pre-regen archived under
  `orbit-research/archive/`). Source shards:
  `runs/early_tweedie_validation_512_bon8_20260527_full01/` +
  `runs/early_tweedie_validation_final_lyricfix_20260603/`.
- [ ] ADSR validated **offline-first** on the 4096-candidate pool before any
  real-generation restart run; expected-compute accounting per §4.5 (no optimistic
  accounting).
- [ ] Human eval interface designed for both E2 (early→final + early vocal-presence
  listening) and E8 (32-pair method preference, expand to 64 conditional).
- [ ] Quality verifier bounded to lightweight scalar-feature models (ridge / GBDT /
  LambdaMART); **only the EVPD is a neural audio model.** No large-model fine-tuning
  beyond the EVPD encoder.
- [ ] Boundary RL section (C6) uses only cached
  `PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` — **no new RL training**.

---

## 17. Hard boundaries (preserved across revisions)

Per `CLAUDE.md` Hard Boundaries, unchanged by this reframe:

- `configs/eval/gate_v1.yaml` — frozen (untouched since 2026-05-16; SHA256
  `43a306753583f03563c792ac9399bb1e30b0525c98c902a1e18756d54e25b3c6`).
- `configs/eval/gate_v2.yaml.draft` — stays `.draft`; do not activate by renaming.
- No new RL training, no Phase D, no pruning+RL, no additional 1000-step RL training,
  no BeatWin/LyricSpan PRM expansion launched by this proposal.
- Human evaluation requires explicit PI approval before launch.
- Raw evidence under `runs/**`, PI review packages under `_pi_review_pkg/**`,
  listening packets, tarballs, calibration/parity/gate evidence — **preserved in
  place, not modified.**

ADSR's offline studies (E1, E5, E6-offline, E7) run on **CPU only** with cached
features. The only new GPU work is the GPU-light EVPD training (E3) and the bounded
small real-generation restart confirm (E6); both require explicit PI sign-off via
the STOP-A checklist above.

---

## 18. Method history (audit trail)

The original v2.0 proposal (`/idea-to-proposal` 2026-05-15) was framed as
*Headroom-Gated M-PRM*. It went through v2.1 (STOP-B-2 consistency patches,
2026-05-15) and v2.2 (Phase C0 backend-smoke update, 2026-05-24). On 2026-05-28 it
pivoted to **Early Trajectory Verifiers (ETV)** — v3.0 — recorded in
`refine-logs/REVISION_INTAKE.md` (Round 1) and `refine-logs/REVISION_REPORT.md`.

On 2026-06-04 the project pivoted again, to **Axis-Deferred Speculative Restart
(ADSR)** — v4.0 — per the PI-frozen plan
`ADSR_Research_Plan_FINAL_EN_2026-05-29.md` and the reframe brief
`refine-logs/ADSR_REFRAME_BRIEF.md`. Under ADSR: ETV's raw fixed-schedule
Early-Tweedie pruning is demoted from the headline to a **strong baseline (raw
ETP)**; the M-PRM / section-credit / RL post-training material is demoted to a
single **boundary** result (C6); and the new headline is **compute reallocation via
restart** plus **axis-dependent observability**, the **presence-vs-content split
(H2b)**, the **learned EVPD audio model (C3)**, and **lyric as a first-class
late-observable axis on the lyric-bearing vocal subset only (C5)**.

The six paper-bearing claims (C1–C6) and superseded rows (ETV1–ETV5, H3, A-series)
are recorded in `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot
Addendum". The ETV-era canonical files are archived at
`orbit-research/archive/etv_pre_adsr_20260604/`.

---

## 19. Cross-references

Live contracts (v4.0 ADSR):
- `refine-logs/METHOD_SPEC.md` — ADSR implementation contract (restart/defer/
  continue, EVPD, quality verifier, §4.5 accounting, offline-first); M-PRM/ETV
  sections marked superseded boundary.
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 — E1–E9 with go/no-go gates,
  Phases 1–7.
- `orbit-research/CONTROL_DESIGN.md` "2026-06-04 ADSR Pivot Addendum" — type-match
  restart, random/raw restart, axis-deferred restart, EVPD vs off-the-shelf
  detector, two-factor ablation (axis-awareness × restart-reallocation), EVPD-branch
  on/off.
- `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR Pivot Addendum" — H1–H6,
  C1–C6.
- `orbit-research/ALGORITHMIC_FORMALIZATION.md` "2026-06-04 ADSR Pivot Addendum" —
  ADSR decision pseudocode + EVPD + compute accounting.
- `orbit-research/COMPONENT_BUNDLE_LADDER.md` / `DIAGNOSTIC_EXPERIMENT_PLAN.md` /
  `NULL_RESULT_CONTRACT.md` — "2026-06-04 ADSR Pivot Addendum".

Canonical evidence (preserved, NOT modified by this reframe):
- `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` — Track A canonical (raw-ETP
  baseline).
- `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` — PI decision.
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` — Track B mechanism.
- `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md` — H2 canonical.
- `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` — lyric-fix
  (0.682 EN-vocal n=282; cross-prompt-not-cross-content; per-specificity-stratum).
- `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` — C1 RL boundary (C6).
- `orbit-research/HEADROOM_GATE_DECISION.json` / `HEADROOM_GATE_PREREG.md` — Phase A
  H1.

Frozen source plan & brief:
- `/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/ADSR_Research_Plan_FINAL_EN_2026-05-29.md`
- `refine-logs/ADSR_REFRAME_BRIEF.md`

Pre-ADSR snapshot:
- `orbit-research/archive/etv_pre_adsr_20260604/` — entire pre-ADSR (v3.0 ETV) state.

---

## Revision history

- **v2.0** (2026-05-15, `/idea-to-proposal`) — Headroom-Gated M-PRM.
- **v2.1** (2026-05-15) — STOP-B-2 consistency patches.
- **v2.2** (2026-05-24) — Phase C0 backend-smoke update.
- **v3.0** (2026-05-28) — M-PRM → ETV pivot (Early Trajectory Verifiers); raw
  Early-Tweedie pruning as headline, learned `V_σ` verifier, risk-controlled pruning;
  five claims ETV1–ETV5.
- **v4.0 ADSR reframe (2026-06-04): ETV→ADSR pivot per
  `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`.** Reframed from prune/select (ETV) to
  compute *reallocation via restart* (Axis-Deferred Speculative Restart). Raw ETP
  demoted to baseline; M-PRM/section/RL demoted to boundary (C6). New: H2b
  presence-vs-content split; H5 high-stakes early-catchable type errors; learned EVPD
  audio model (C3); restart/defer/continue mechanism; lyric as first-class
  late-observable axis on the lyric-bearing vocal subset only (C5). Six claims C1–C6;
  nine experiments E1–E9 marked run-vs-planned. Lyric-fix corrections preserved
  (0.682 EN-vocal n=282; Track A 0.9864; cross-prompt-not-cross-content;
  per-specificity-stratum). Honest evidence-status section added (§15): EVPD not
  trained, restart/ADSR not run, vocal-presence labels not derived — this is a
  plan-stage proposal for the new method, anchored on existing ETV/Track-A/H2/
  human-listening foundation evidence.
