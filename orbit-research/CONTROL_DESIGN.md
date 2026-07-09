# Control Design — Axis-Deferred Speculative Restart (ADSR, PI v4.0)

> *Per-claim control inventory.* For every paper-bearing claim in the experiment plan,
> this artifact lists the controls that have to run for the claim to be defensible.
> A control failure here invalidates the claim, not the mechanism. Claims without
> implemented controls are not claims.
>
> **Status.** v4.0 ADSR reframe, 2026-06-04. Reframes the per-claim control inventory
> from **ETV** (prune/select a fixed candidate pool) to **ADSR** (compute *reallocation*
> via RESTART / DEFER / CONTINUE). ETV-pruning (raw Early-Tweedie Pruning, "raw ETP")
> is preserved here as a *baseline / strong control*, not the headline. The M-PRM
> per-claim control inventory (former §§1–6) and the 2026-05-28 ETV addendum are
> retained as **superseded boundary / historical audit** at the end of this document.
> **Linked artifacts.** `refine-logs/FINAL_PROPOSAL.md` v4.0 (ADSR; C1–C6),
> `refine-logs/METHOD_SPEC.md` v4.0 (ADSR §§; M-PRM/ETV-pruning marked superseded),
> `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 (E1–E9), `orbit-research/ASSUMPTION_LEDGER.md`
> "2026-06-04 ADSR Pivot Addendum" (H1–H6 + C1–C6), `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`
> §7 (baselines) / §8 (success) / §9 (failure routing).

---

## 0. Reading guide

ADSR is a compute-**reallocation** method, not a candidate-selection method. The three
decisions are **RESTART** (terminate this trajectory and launch a NEW independent seed —
not a rollback/repair), **DEFER** (continue to a later σ before deciding), and **CONTINUE**.
The control design therefore has a structure that the ETV/M-PRM versions did not: every
"matched-compute" comparison must account for **restart cost under matched expected total
NFE** (ADSR §4.5), and the central scientific question — *which axes can be judged early
vs. must be deferred* — needs its own observability control, not just a selection control.

Each claim is listed with:
- the matched-compute / matched-data controls that defend it;
- the **isolation control** that holds everything else fixed and changes only the
  load-bearing component;
- the **anti-claim** the controls rule out;
- the **failure-of-the-control** scenario and what it implies for the claim (routed to
  ADSR §9 failure modes).

Per the user's CLAUDE.md "If the control matches the proposed method, does the paper still
have a contribution?" — for every claim below the answer is yes. The C1 (axis×σ
observability map) and C5 (lyric as a first-class late-observable axis) results stand on
their own as a measurement/observability paper even if the ADSR method (C2) ties its
same-compute baselines, per ADSR §9 failure routing ("fall back to an axis-observability +
trajectory-analysis paper").

**Evidence status (read before interpreting any control below).** Foundation evidence
*exists* and is repurposed: H1/H2 early-quality persistence (Phase A headroom
`delta_sigma_bon_vs_base=0.7549`; H2 STRONG_PASS on 128 prompts; Track B globalness 0.861);
Track A raw-ETP pruning (Schedule A **0.9864** reward_fraction @ 0.500 compute, regenerated
2026-06-04 on the lyric-fix dataset, was 0.9858 on 2026-05-28; bottom-prune σ=0.7
false-negative 0.0195); the lyric axis now scored **EN-vocal-only** (**0.682** ETP@50,
n=282, 248/282 = 88% carrying signal; instrumental 1.0 sentinel masked, non-EN excluded —
`orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`); C1 RL boundary
(no clear first-wave common-metric gain). **NOT yet run** (ADSR is forward-looking for
these): E3 **EVPD is not trained**; E6 **restart/ADSR is not run** (only offline-simulatable
on the 4096-candidate pool); **vocal-presence labels are not yet derived**; H2b presence/
content split is unmeasured; cross-backbone not started. Controls below for unrun
experiments are **planned controls** (their pass/fail is a gate to be evaluated, not a
reported result). Wherever a control number is quoted as achieved, it is foundation
evidence; wherever a control is marked *planned*, no ADSR result is being claimed.

---

## 1. Claim C1 — Axis × σ Observability Map (+ human early→final validation)

**Claim wording (proposal §3 C1):** *Different quality axes of a flow-matching music
generation become reliably observable at different points along the denoising trajectory.
The map orders aesthetic/production and vocal presence (early) → semantic alignment (mid) →
lyric intelligibility (latest), and this ordering is validated against human early→final
listening (uniform-badness, late-bloomer rarity, early vocal-presence audibility).*

This is a **measurement / observability claim** (E1 + E2). The controls are the axis grid
*itself* plus the human-validation arm; "control failure" means the map is uninterpretable
or the human evidence does not license early rejection — not that no axis is early-observable.

### 1.1 Required controls

| # | Control | Role | Failure mode that would invalidate the audit |
|---|---|---|---|
| 1 | **Per-axis, per-σ early-vs-final correlation grid** (Spearman, within-prompt NDCG, winner & top-k retention) over σ ∈ {0.9, 0.8, 0.7, 0.5, 0.3, final} | the observability matrix itself | within-prompt label signal is too weak (near-tied candidates) → no axis separates → map is null |
| 2 | **Lyric-stratum fix control** — lyric axis computed **EN-vocal-only** (n=282), instrumental 1.0 sentinel masked, non-EN excluded | removes the sentinel pollution that inflated lyric to 0.8432 | if the stratum filter is not applied, lyric onset is spuriously "early" (the original `analyze_cross_axis_generalization()` bug); the headline lyric number is 0.682, not 0.843 |
| 3 | **Vocal-presence row separated from lyric-intelligibility row** | enforces the H2b presence-vs-content split | if presence and content are collapsed into one "vocal" axis, the early-presence / late-content ordering cannot be read; expect vocal-presence-onset ≪ lyric-onset (planned — labels not yet derived) |
| 4 | **Random-σ / shuffled-label control** | tests whether early-vs-final correlation exceeds chance | shuffled-label grid shows comparable "correlation" → the observed onsets are artifacts of grid construction |
| 5 | **Human early→final validation (E2)** — early-σ perceptual quality vs final human-judged quality; uniform-badness quantified; late-bloomer rarity; early vocal-presence listening at σ=0.9/0.8/0.7 | external license for restart; defense against reward-circularity | if humans do *not* find early quality predictive of final quality, or late-bloomers are common, the restart license is withdrawn → ADSR (C2) loses its empirical foundation |
| 6 | **ASR-transcribability-onset anchor** (lyric-decidability onset vs ASR-transcribability onset) | mechanistic anchor for why lyric is latest | if lyric-decidability onset is not later than the transcribability onset, the "lyric is late-observable" mechanism is unsupported |

### 1.2 What a "control matches method" outcome means here

- If **the observability grid is null** (no axis separates early from late), C1 collapses to
  "early σ carries no usable per-axis signal" — but H1/H2 foundation evidence (early-quality
  persistence, STRONG_PASS) already contradicts a fully null grid, so the realistic failure is
  a *partial* grid (some axes early, others never resolved), which is still a publishable map.
- If **lyric-onset is not later than aesthetic/presence onset**, H2/H2b are weakened and the
  paper's central ordering claim narrows; per ADSR §9, lyric stays first-class but the claim
  becomes "lyric observability is difficult and needs better measurement" — no forced headline.
- If **human validation (control 5) disconfirms**, the entire restart premise is undermined;
  the paper retreats to a measurement paper without the ADSR method (ADSR §9: fall back to an
  axis-observability + trajectory-analysis paper).

### 1.3 Citations

- Hypotheses: **H1** (early persistence), **H2** (axis-dependent observability — scientific
  core), **H2b** (presence-vs-content split), **H6** (human evidence, already obtained).
- Experiments: **E1** (axis×σ matrix), **E2** (human early→final), **E7** (lyric onset anchor).
- Foundation evidence: Phase A `delta_sigma_bon_vs_base=0.7549`; Track B globalness 0.861;
  lyric 0.682 EN-vocal n=282.

---

## 2. Claim C2 — ADSR (main method; reallocation, not selection)

**Claim wording (proposal §3 C2):** *Axis-Deferred Speculative Restart improves the
compute–quality trade-off over same-compute candidate-selection and random-restart baselines
by terminating low-promise trajectories early and reallocating their compute to new
independent seeds, while deferring decisions for late-observable axes (lyric intelligibility,
fine semantics) so that those axes are not degraded.*

This is the **main method claim** (E6). It is a *reallocation* claim — the load-bearing
contrast is against fixed-pool selection (raw ETP, learned-verifier selection) and against
naïve restart (random, raw). Controls must isolate (a) restart-vs-selection and (b)
axis-awareness, under **strict matched expected total NFE** (ADSR §4.5: partial cost to σ_c +
surviving full cost + restart new-seed cost + deferred-continuation cost; no optimistic
accounting). **Validated offline-first on the existing 4096-candidate pool** ("restart" =
draw the next independent pool candidate), then a small real-generation confirm.

### 2.1 Required controls — same-compute baseline ladder (ADSR §7 "Required")

| # | Control | Role | What it isolates / Failure mode that would invalidate the audit |
|---|---|---|---|
| C2-b1 | **Full BoN-8** | upper-bound reference (1.0 reward fraction at 1.0 compute) | Track A reproducibility anchor; if BoN-8 reward distribution differs from the saved Track A artifact, the offline pipeline is broken. Top-tier target: ADSR ≥ Full BoN-8 at *matched* compute. |
| C2-b2 | **BoN-4 at matched compute (0.5)** | **critical control** — the no-learning, no-restart floor | if ADSR does not beat BoN-4 at matched expected NFE, it adds no value over uniform smaller-N sampling → ADSR §9 "does not beat BoN-4" routing (fall back to observability paper). |
| C2-b3 | **Random restart at matched compute** | isolates *which restarts to launch* (random vs early-informed) | tests whether ADSR's gain is from reallocating compute *at all* vs from reallocating it *intelligently*; if random restart ties ADSR, the early-quality signal is not what is buying the gain. |
| C2-b4 | **Raw restart** (early-stop on a single global early score, restart, no axis-awareness, no defer) | isolates **axis-awareness + deferral** (the "axis-deferred" half of ADSR) | if raw restart ties ADSR, the axis-deferred logic is not load-bearing → demote to "any early-informed restart works"; still publishable as a milder positive, but C2's "axis-deferred" framing weakens. |
| C2-b5 | **Raw ETP (fixed-schedule Early-Tweedie Pruning, selection only — Schedule A σ0.9→0.7→final @ 0.500)** | **the selection baseline** — fixed-pool, no restart | this is the former ETV headline, now a baseline. If raw ETP@0.500 (Track A foundation: **0.9864** reward_fraction) ties or beats ADSR at matched compute, the *restart* mechanism (H3) adds nothing over fixed-pool selection → ADSR §9 routing. |
| C2-b6 | **Learned-verifier selection** (quality verifier ranks the fixed pool; selection, no restart) | isolates **restart vs. better selection** | the strongest *selection* baseline. If learned-verifier selection ties ADSR, then "select better" suffices and "restart" is not the contribution — C2 retracts to a verifier paper (C4). Note: ridge already saturates within-prompt NDCG (~0.995), so selection headroom is small by construction; this is *why* H3 expects restart, not selection, to be the lever. |
| C2-b7 | **Type-match restart** (EVPD type-error branch only: restart on predicted prompt-type mismatch; no quality/defer logic) | isolates the **EVPD type-match contribution** (C3) within the restart family | if type-match restart alone matches full ADSR, the quality/defer machinery adds nothing beyond catching gross type errors — C2 reduces to C3; still a publishable result (type-error catching is the lever), routed honestly. |

### 2.2 The clean-isolation principle (two-factor design)

The seven rows above are arranged as a **2×2 two-factor ablation (axis-awareness × restart-
reallocation)** plus the EVPD branch, all sharing the same prompt set, early-σ scores, EVPD
outputs (when on), decision-threshold schedule, σ_c, and **matched expected total NFE**:

| | **Selection (fixed pool, no restart)** | **Restart (reallocate compute)** |
|---|---|---|
| **Axis-agnostic** | raw ETP (C2-b5) | raw restart (C2-b4) / random restart (C2-b3) |
| **Axis-aware** | learned-verifier selection (C2-b6) | **ADSR** (axis-deferred restart) |

- **Restart-reallocation factor** = (raw restart − raw ETP) and (ADSR − learned-verifier
  selection): does reallocating compute to new seeds beat fixing the pool?
- **Axis-awareness factor** = (learned-verifier selection − raw ETP) and (ADSR − raw restart):
  does axis-aware, deferral-respecting logic beat a single global early score?

This is the strongest single-variable isolation available offline: every cell consumes the
same cached 4096-candidate pool; only the decision policy differs.

### 2.3 The EVPD-branch on/off control (within ADSR)

ADSR is run **with and without the EVPD type-match branch** (ADSR §6 E6 ablation):

| # | Variant | What is held fixed | What varies |
|---|---|---|---|
| C2-e1 | **ADSR, EVPD branch ON** | quality verifier, defer logic, σ_c, thresholds, compute budget | type-match restart enabled (decision-logic priority 1) |
| C2-e2 | **ADSR, EVPD branch OFF** | as above | type-match restart disabled; only quality + defer drive restart |

This is the direct test of whether the EVPD branch adds prompt-type-match-rate beyond the
quality/defer logic, and feeds C3 (§3). It is a **planned control** — EVPD is not yet trained;
the EVPD-ON arm cannot be evaluated until E3 produces a trained detector and the vocal-presence
labels are derived.

### 2.4 Anti-claims ruled out

- **Anti-claim A** "ADSR's gain is just more effective compute" — ruled out by matched
  expected total NFE accounting (ADSR §4.5; partial + surviving + restart-new-seed + deferred
  costs all charged).
- **Anti-claim B** "ADSR is just BoN at smaller N" — ruled out by C2-b2 (BoN-4) and C2-b1
  (Full BoN-8) bracketing the compute axis.
- **Anti-claim C** "restart helps only because you restart *something*" — ruled out by C2-b3
  (random restart) and the restart-reallocation factor in §2.2.
- **Anti-claim D** "axis-deferral is decorative; a single global early score suffices" —
  ruled out by C2-b4 (raw restart) and the axis-awareness factor in §2.2.
- **Anti-claim E** "ADSR is a re-discovery of fixed-schedule pruning" — ruled out by C2-b5
  (raw ETP) and C2-b6 (learned-verifier selection); if the ADSR Pareto curve dominates both
  selection baselines, the restart mechanism is the non-trivial part.

### 2.5 Control failure modes (routed to ADSR §9)

| Control fails | Implication |
|---|---|
| **C2-b2 (BoN-4)** outperforms ADSR at matched compute | ADSR is too weak as a main ICLR claim → fall back to axis-observability + trajectory-analysis paper (ADSR §9). |
| **C2-b3 (random restart)** within noise of ADSR | the early-quality signal is not separable from chance reallocation → C2 retracts; the observability map (C1) still publishes. |
| **C2-b4 (raw restart)** ties ADSR | axis-deferral is not load-bearing → "any early-informed restart works"; C2 demoted to a milder positive, C1 holds. |
| **C2-b5 (raw ETP @0.500)** ties/beats ADSR at matched compute | restart adds nothing over fixed-pool selection (H3 falsified) → paper keeps the raw-ETP baseline result but loses the restart headline. |
| **C2-b6 (learned-verifier selection)** ties ADSR | "select better" suffices; C2 retracts to a verifier paper (C4). |
| **ADSR improves common quality but hurts lyric** | axis-deferred logic insufficient → strengthen lyric defer / use later σ for lyric / restrict to non-lyric settings (ADSR §9). |

### 2.6 Citations

- Hypotheses: **H1** (early persistence), **H3** (restart beats fixed-pool selection — note
  the low-stakes-selection evidence: median regret ≈ 0; ETP@50 over BoN-4 ≈ **+0.0036**),
  **H4** (axis-deferred restart preserves late axes).
- Experiment: **E6** (ADSR main method), **E4** (raw pruning / same-compute baselines feed
  C2-b5), **E5** (learned verifier feeds C2-b6).
- Compute accounting: ADSR §4.5 (matched expected total NFE; offline-first on the 4096-pool;
  canonical reward set `orbit-research/trajectory_candidate_dataset.jsonl`).

---

## 3. Claim C3 — Prompt-Type Match as an Early-Decidable Axis (EVPD)

**Claim wording (proposal §3 C3):** *Prompt-type match (vocal vs. instrumental presence) is a
high-stakes, early-decidable axis. A learned Early Vocal-Presence Detector (EVPD) — a small
audio model reading the early Tweedie-clean mel-spectrogram — predicts FINAL vocal presence
well before the trajectory completes, and using its prediction as a type-match early-reject
signal raises the final selected output's prompt-type-match rate.*

This is a **new method/measurement claim** (E3) and the most distinctive control block of the
ADSR design, because the proposed component is a **learned AUDIO model**, not a scalar ranker.
The central control question is: *does the EVPD warrant being a neural net, or does an
off-the-shelf detector do the job?* — and *is presence genuinely early-decidable, or is its
onset late?* **All controls in §3 are planned**: EVPD is not trained, vocal-presence labels
are not yet derived.

### 3.1 Required controls

| # | Control | Role | Failure mode that would invalidate the audit |
|---|---|---|---|
| C3-c1 | **Ground-truth vocal-presence label** (Demucs/Spleeter vocal-energy ratio, or a singing-voice-detection model; Whisper `no_speech_prob` only as a coarse pre-filter) | the EVPD target | if the label is itself unreliable (e.g., Whisper false-triggers on instrumental, or source-separation SI-SDR is poor on a genre), every downstream EVPD number is uninterpretable. Calibrate the label first. |
| C3-c2 | **Off-the-shelf vocal/singing-voice detector run on the EARLY estimate** (no early-σ training) | **the key control for "why a learned model"** | if an off-the-shelf detector matches EVPD on the early estimate, the learned audio model is not warranted → C3 demotes to "use an existing detector on the early mel"; the *axis* result still stands, the *learned component* does not. This is the EVPD-vs-off-the-shelf control. |
| C3-c3 | **Off-the-shelf detector on the FINAL audio** (upper bound for the label task on clean audio) | bounds how much of the gap is early-σ difficulty vs intrinsic detector limit | if even the final-audio detector is weak, the task is hard regardless of σ; the early-σ "OOD for off-the-shelf detectors" argument is moot. |
| C3-c4 | **EVPD decidability-onset σ sweep** (AUC at σ = 0.9 / 0.8 / 0.7 / 0.5 / 0.3) | tests H5 "type errors early-catchable" and locates the onset | if AUC only rises at late σ, presence is NOT early-decidable → ADSR §9 routing: demote the type-match branch to a later-σ check, report onset honestly (mid-onset still saves the back half of compute). |
| C3-c5 | **Type-error prevalence baseline** (rate of vocal-prompt→instrumental and instrumental-prompt→vocal errors) | establishes the stakes (a result in itself) | if type errors are vanishingly rare, the type-match branch has little to catch and C3's "high-stakes" framing weakens (though it remains a clean measurement). |
| C3-c6 | **Presence/content disentanglement of the lyric-zero stratum** (split lyric-zero candidates into *type errors* = no voice → no transcription vs *content failures* = voice present but unintelligible) | operationalizes H2b on existing data | if the split is not separable, the presence-vs-content distinction is not empirically grounded; this is the bridge from C1's lyric onset to C3's presence onset. |
| C3-c7 | **Closed-loop type-match-rate (with vs without type-match restart)** | the C3 application result | if type-match restart does not raise the final selected output's prompt-type-match rate, the EVPD branch is decorative; this is also C2-e1/e2 (§2.3). |
| C3-c8 | **False-restart rate on type** (how often EVPD restarts a *correct*-type trajectory) | guards against an over-eager detector | a high false-restart rate wastes compute and can degrade the Pareto; pre-register a tolerated false-restart ceiling. |

### 3.2 Anti-claims ruled out

- **Anti-claim "an off-the-shelf detector would do"** — ruled out by C3-c2 (and bounded by
  C3-c3). The learned-audio-model claim is only made if EVPD beats the off-the-shelf detector
  on the early estimate.
- **Anti-claim "vocal presence is trivially detectable at any σ"** (explicitly on the §14
  avoid-list) — ruled out by C3-c4: the claim is conditioned on the *measured* onset σ, not
  asserted universally.
- **Anti-claim "lyric-zero just means no lyric signal"** — to be tested by C3-c6 (H2b is
  currently UNMEASURED): C3-c6 will test whether the zero stratum splits into type errors
  (no voice) and content failures (voice present, unintelligible). Not yet established.
- **Anti-claim "EVPD just trades type errors for false restarts"** — ruled out by C3-c8
  (false-restart-on-type ceiling).

### 3.3 Control failure modes (routed to ADSR §9)

| Control fails | Implication |
|---|---|
| **C3-c1 (label)** unreliable | re-derive labels before any EVPD claim; the EVPD result is blocked, not retracted. |
| **C3-c2 (off-the-shelf ties EVPD on early estimate)** | learned audio model not warranted → C3 demotes to "use an existing detector on the early mel"; the prompt-type axis result survives. |
| **C3-c4 (onset is late)** | presence is not early-decidable → demote the type-match branch to a later-σ check, report onset honestly (ADSR §9). Mid-onset still saves back-half compute, so value likely persists, but the claim follows the measured onset. |
| **C3-c7 (no type-match-rate gain)** | the EVPD branch is decorative → run ADSR EVPD-OFF (C2-e2) as the main method; C3 reports only the *measurement* (onset, prevalence), not the application. |

### 3.4 Citations

- Hypotheses: **H2b** (presence-vs-content split), **H5** (type errors high-stakes &
  early-catchable).
- Experiment: **E3** (EVPD + type-error study). Feeds C2-e1/e2 (§2.3) and E6.
- Data: vocal-presence labels (ADSR §5) — **not yet derived**; relabel the existing 4096
  candidates retroactively.

---

## 4. Claim C4 — Compute–Quality Pareto (cross-cutting baseline-suite control)

**Claim wording (proposal §3 C4):** *ADSR yields a compute–quality Pareto improvement over the
full baseline family — BoN-k (same compute), Full BoN-N, random prune/restart, raw
Early-Tweedie pruning, and learned-verifier selection — under matched expected total NFE.*

This is a **Pareto-dominance claim** that aggregates the C2 baseline ladder (§2.1) across the
compute axis. The controls are the same baseline family, run at *multiple* compute fractions so
the Pareto frontier — not a single matched point — is the object compared.

### 4.1 Required controls

| # | Control | Role | Failure mode |
|---|---|---|---|
| C4-c1 | **Full BoN-8** at compute 1.0 | Pareto upper-right anchor (1.0, 1.0) | foundation: Track A BoN-8 reward distribution; reproducibility anchor. |
| C4-c2 | **BoN-k curve** (k ∈ {1,2,4,8}) | the no-learning, no-restart Pareto | the floor frontier ADSR must dominate. |
| C4-c3 | **Raw ETP at multiple compute fractions** (Schedules A/B/C, bottom-prune) | the fixed-pool-selection frontier | foundation: Schedule A **0.9864** @ 0.500; high-compute references 0.9986 / 0.9996 @ ≈0.85 (Track A). The **critical comparison is raw ETP@50 vs BoN-4: delta ≈ +0.0036** — within noise, which is *why* raw ETP cannot be the headline and ADSR must beat this frontier by a pre-registered margin, not tie it. |
| C4-c4 | **Random prune/restart** at multiple fractions | the chance-reallocation frontier | if random reallocation matches ADSR's frontier, the early signal is not the lever. |
| C4-c5 | **Learned-verifier selection** at multiple fractions | the best-selection frontier | the strongest selection competitor; ADSR must dominate it to claim "restart > selection". |
| C4-c6 | **Cross-metric Pareto validation** — select/restart by the ADSR decision, evaluate by {aesthetic/production, CLAP semantic, lyric WER (EN-vocal only, n=282), MERT coherence, prompt-type-match rate} | tests reward circularity | ADSR's decision is driven by early robust-LCB + EVPD; if Pareto gains do not transfer to non-robust-LCB axes, the claim is over-fit to its own training signal (E2/E8 human validation is the ultimate non-circular check). |

### 4.2 The "delta ≈ 0.0036" critical control (raw ETP@50 vs BoN-4)

This single comparison is the **load-bearing motivation for the entire pivot** and is preserved
verbatim as the critical control: on the foundation data, raw fixed-schedule ETP at 50% compute
beats BoN-4 by only **≈ 0.0036** reward fraction. Fixed-pool selection among same-prompt
candidates is therefore **low-stakes** (median regret ≈ 0). Two consequences for the control
design: (1) raw ETP — the former ETV headline — is demoted to a baseline here; (2) ADSR cannot
win by selecting better within the pool (the headroom is ~0.0036), so the contribution must come
from *restart-reallocation* and *axis-deferral*, which is exactly what the §2.2 two-factor
ablation isolates. If ADSR's Pareto gain over the raw-ETP/BoN-4 region is itself ≈ 0.0036, the
method has not escaped the low-stakes regime → ADSR §9 fallback.

### 4.3 Compute estimate for the C4 baseline suite

- C4-c1..c5 use the cached Track A candidate records — canonical merged set
  `orbit-research/trajectory_candidate_dataset.jsonl` (promoted 2026-06-04;
  `runs/early_tweedie_validation_512_bon8_20260527_full01/` +
  `runs/early_tweedie_validation_final_lyricfix_20260603/`). **0 GPU-h** (post-hoc, offline on
  cached data — the offline-first protocol of ADSR §4.5).
- C4-c6 cross-metric reuses the cached candidates' reward vectors. **0 GPU-h.**
- The small real-generation confirm (a subset of E6) and EVPD training (E3) carry the only new
  GPU cost; the Pareto baseline suite itself is essentially free, by design.

### 4.4 Citations

- Hypotheses: **H1**, **H3**.
- Experiment: **E4** (raw pruning + same-compute baselines), **E6** (ADSR frontier).
- Foundation evidence: raw ETP Schedule A 0.9864 @ 0.500; ETP@50 vs BoN-4 delta ≈ 0.0036.

---

## 5. Claim C5 — Lyric as a First-Class Late-Observable Axis (correct population)

**Claim wording (proposal §3 C5):** *Lyric intelligibility is a first-class late-observable
axis. Evaluated on the correct statistical population — lyric-bearing vocal prompts only, with
no instrumental-sentinel pollution and no non-English floor — it demonstrates why deferral is
necessary, and it disentangles into presence (early) vs content (late).*

This is a **measurement claim about a single axis** (E7), and the controls are primarily about
**population definition and aggregation correctness**, because the original failure here was a
silent aggregation bug, not a modeling error.

### 5.1 Required controls

| # | Control | Role | Failure mode that would invalidate the audit |
|---|---|---|---|
| C5-c1 | **EN-vocal-only stratum filter** (vocal ∧ English) | the headline population | without it, the 196 instrumental prompts pinned at the 1.0 sentinel inflate lyric to 0.8432 (the original `analyze_cross_axis_generalization()` bug); the honest headline is **0.682, n=282**. |
| C5-c2 | **Per-specificity-stratum report** (clean English core / broader lyric-bearing vocal / multilingual-or-thin-lyric stress arm) | prevents a single mixed number | reporting a single lyric number across heterogeneous lyric density/language mis-states decidability; report each stratum separately. |
| C5-c3 | **Split by prompt_id, never by candidate_id** (cross-prompt, not cross-content) | prevents same-prompt candidate leakage | candidate-level splits leak near-identical same-prompt candidates across train/eval; all lyric (and ADSR) splits are cross-prompt. |
| C5-c4 | **Dataset-health audit** (all-8-zero vocal prompts; EN-vocal carrying signal) | guards the population's signal content | foundation: 248/282 = 87.9% of EN-vocal prompts carry lyric signal; remaining all-zero (19.6%) dominated by 34 non-EN vocal prompts the English-only Whisper scorer cannot rate — excluded from the headline, reported as a limitation. |
| C5-c5 | **Presence/content disentanglement** (shared with C3-c6) | *tests* whether the zero stratum splits into type-errors + content-failures (H2b; UNMEASURED — planned, not a result) | binds C5 (late content) to C3 (early presence); the same lyric-zero candidates are the bridge between the two claims. |
| C5-c6 | **Lyric-decidability onset vs ASR-transcribability onset** (mechanistic anchor) | the mechanism for "lyric is latest" | if decidability does not lag transcribability, the late-observability mechanism is unsupported (shared anchor with C1 control 6). |

### 5.2 Anti-claims ruled out

- **Anti-claim "lyric can be evaluated over all prompts"** (explicitly on the §14 avoid-list) —
  ruled out by C5-c1 (instrumental sentinel masked) and C5-c4 (non-EN floor excluded).
- **Anti-claim "the 0.84 lyric number stands"** — ruled out by C5-c1; the corrected headline is
  **0.682 EN-vocal n=282**. The contaminated `all`-stratum number (~0.84 — `0.8432` pre-regen,
  `0.8434` post-regen, both pooling the 196 instrumental prompts at the constant 1.0 Whisper
  sentinel) is retained only as an audit-trail row, never as a claim.
- **Anti-claim "lyric gains are same-prompt leakage"** — ruled out by C5-c3 (prompt-id splits).

### 5.3 Control failure modes (routed to ADSR §9)

| Control fails | Implication |
|---|---|
| **Lyric subset too noisy** (signal-carrying fraction too low even after the fix) | lyric stays first-class but the claim becomes "lyric observability is difficult and needs better measurement"; do not force a headline lyric result (ADSR §9). |
| **C5-c5 (presence/content) not separable** | the presence-vs-content split (H2b) is unsupported; C3 and C5 both weaken, but each survives as an independent axis measurement. |

### 5.4 Citations

- Hypotheses: **H2** (axis-dependent observability), **H2b** (presence-vs-content split).
- Experiment: **E7** (lyric-focused deferred eval), **E1** (lyric row of the matrix).
- Foundation evidence: lyric **0.682** EN-vocal n=282 (88% signal);
  `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`.

---

## 6. Claim C6 — RL Post-Training Boundary Result

**Claim wording (proposal §3 C6):** *LoRA/GRPO RL post-training of ACE-Step is technically
feasible and stable, but the first wave shows no clear common-metric gain — which is itself the
empirical motivation for shifting effort to inference-time compute allocation (ADSR).*

This is a **boundary / negative result** (one paragraph in the paper, not the headline). The
control evidence already exists; **no new controls are required**.

### 6.1 Controls (already run; cited, not re-run)

| # | Control | Evidence |
|---|---|---|
| C6-c1 | **R8a Outcome-GRPO-plain** (terminal reward, no curriculum, no lyric guard) | first-wave common-dev delta within +0.012 to +0.014 LCB of base; no clear win. |
| C6-c2 | **R8b Outcome-GRPO-guarded** (terminal reward + Lagrangian lyric guard + optional curriculum) | same first-wave outcome; stable training. |
| C6-c3 | **M-FixedWin-PRM** (fixed-window process reward, step-1000) | within the same no-clear-win band; behaves like a persistent-quality proxy. |
| C6-c4 | **M-Section-PRM** (section-level process reward, step-1000) | section credit not supported as the best default credit unit (H3/Phase B.3 boundary). |

Canonical evidence: `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` and
`PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md`. The full M-PRM per-claim control inventory
that produced these is preserved as superseded boundary audit in §10 below.

### 6.2 Anti-claim explicitly NOT made

Per ADSR §14, the paper does **not** claim "RL post-training does not work." C6 claims only
that the *first wave* showed no clear common-metric gain in this regime, motivating the
inference-time pivot. New σ-axis RL is future work, not in the main execution plan.

### 6.3 Citations

- Hypothesis: **H3** boundary (section not the best default credit unit).
- Experiment: cited as ADSR §10 boundary; no E-number in the active E1–E9 plan.

---

## 7. Reward-evaluator and gate controls (cross-cutting)

Reward models and the gate config are the load-bearing measurement instrument; their
calibration is itself a control. These carry over unchanged from the ETV/M-PRM infra — the
*method* was reframed, not the reward/gate/split infra.

| # | Control | Failure mode |
|---|---|---|
| 1 | Human preference calibration set (E2 / E8) | reward-model ranking diverges from human ranking → the automatic-metric Pareto is uninterpretable (human overrides reward, ADSR §8/§9). |
| 2 | Reward-model ensembling (CLAP variants × Audiobox + perturbations Π) | low-ensemble-spread fails to flag uncertain reward samples. |
| 3 | Anti-hacking probe suite (silence_fraction, autocorr_repetition, off_prompt_distance, hf_artifact_score, broken_section_indicator) | probes fire on training but not held-out → calibration drift. |
| 4 | Gate policy `configs/eval/gate_v2.yaml.draft` (DRAFT — do not activate by renaming) | the common robust-LCB gate definition used for all matched-compute comparisons; if changed, every cross-method number shifts. |
| 5 | Per-axis vs scalar reward comparison | scalar reward collapses information that per-axis reveals — exactly the axes ADSR defers (lyric, semantic). |
| 6 | Vocal-presence label calibration (Demucs SI-SDR per genre; Whisper `no_speech_prob` as coarse pre-filter only) | mis-calibrated presence labels poison EVPD (C3-c1); calibrate before training EVPD. |

The audit pipeline writes per-control results to `RUN_LEDGER.jsonl`; per-control failure
descriptions live in `NULL_RESULT_CONTRACT.md`.

---

## 8. Cross-method matched-compute accounting (ADSR §4.5)

Every comparison in §2.1, §3.1, §4.1 is run at **matched expected total NFE** — *not* matched
hyperparameter-count or matched epoch-count — with **no optimistic accounting**. The ADSR
expected-NFE envelope is:

```
E[total NFE] = partial-trajectory cost to σ_c
             + surviving-trajectory full cost
             + restart (new independent seed) cost
             + deferred-continuation cost
```

**Offline-first protocol.** ADSR and all selection/restart baselines are first validated
**offline on the existing 4096-candidate pool** (`orbit-research/trajectory_candidate_dataset.jsonl`):
each candidate's cached early scores / (planned) EVPD output is the verdict, and "restart" =
draw the next independent pool candidate. Only after the offline Pareto is established does a
**small real-generation confirm** run, to verify the offline simulation tracks live restart
behaviour.

**Compute envelope (plan-time estimates; `EXPERIMENT_PLAN_EXEC.md` / `EXPERIMENT_TRACKER.md`
record actuals).**

| Control / experiment block | Compute | Notes |
|---|---:|---|
| C2 baseline ladder (offline on 4096 pool) | **0 GPU-h** | post-hoc on cached candidates; offline-first |
| C4 Pareto suite (multi-fraction, offline) | **0 GPU-h** | reuses cached reward vectors |
| C4-c6 cross-metric validation | **0 GPU-h** | reuses cached per-axis rewards |
| C3 EVPD training (E3) | small GPU-h (CNN / fine-tuned audio encoder) | planned — not yet run |
| C3-c1 vocal-presence label derivation (Demucs/Spleeter/SVD) | source-separation CPU/GPU pass over 4096 candidates | planned — labels not yet derived |
| E6 small real-generation confirm | bounded GPU-h subset | confirm only; offline simulation is the main result |
| E2 / E8 human listening | ~10–15 listener-hours | early vocal-presence + method-preference A/B |
| Cross-backbone (E9, Stable Audio Open) | Phase-1-parallel; does NOT gate submission | graceful fallback to target-regime limitation |

The quality verifier (C2-b6 / E5) trains on CPU (ridge/GBDT/LambdaMART on cached scalar
features). **Bound preserved: no large-model training.** The only new neural training is the
EVPD audio model (deliberately small, per ADSR §4.2 — the one component that genuinely warrants
a learned audio net).

---

## 9. Control implementation checklist (for `PLAN_CODE_AUDIT.md`)

The plan-code audit verifies that for each row of §1.1, §2.1, §2.3, §3.1, §4.1, §5.1:

- [ ] the control script exists in `src/baselines/`, `src/eval/`, or `src/adsr/`;
- [ ] it consumes the same prompt set, reward harness, gate config (`gate_v2.yaml.draft`),
      **prompt-id split**, and config schema as ADSR;
- [ ] it charges restart/defer cost under matched expected total NFE (§8) — no optimistic
      accounting;
- [ ] its compute budget is logged to `RUN_LEDGER.jsonl`;
- [ ] its output is parsed into the same metric schema as ADSR
      (incl. prompt-type-match rate and per-stratum lyric on EN-vocal n=282);
- [ ] its failure-of-control interpretation is cross-referenced from `NULL_RESULT_CONTRACT.md`
      and routed to ADSR §9.

Any unchecked row means the corresponding claim (C1–C6) is **not defensible** and must be
either demoted to a hypothesis or removed from the paper plan. For **planned** controls (EVPD
branch, vocal-presence labels, E6 restart), the checklist item is a *gate to evaluate*, not a
claim to assert — no ADSR result is reported until the corresponding experiment runs.

---

## 10. Superseded boundary / historical control audit

> The two sections below — the M-PRM per-claim control inventory (authored 2026-05-15, PI v2.0)
> and the 2026-05-28 ETV Pivot Addendum — are **retained verbatim as historical audit and
> doc-durability record.** They are no longer the active control design. The M-PRM RL controls
> survive as the boundary-result evidence for **C6** (§6); the ETV addendum's raw-ETP and
> BoN-4 controls survive as ADSR **baselines** (C2-b2, C2-b5, C4-c2, C4-c3). Do not delete:
> the STOP-B fix-pass history and the pre-serialized control numbers are the audit trail.

### 10.A M-PRM per-claim control inventory (superseded — boundary, see §6)

*(Authored v1.0, 2026-05-15, Phase 1 of `/experiment-bridge`; the primary claim "M-PRM beats
Outcome-GRPO at matched compute" is no longer paper-bearing. Preserved as the C6 boundary
evidence and the source of the R8a/R8b/M-FixedWin/M-Section controls.)*

**C1 (M-PRM) — Headroom Measurement.** Baseline suite as the control: base sampling (seeds ×
CFG), CFG sweep, BoN-{4,8,16}, Robust BoN (R_lcb over Π), BoN+CFG, SFT-on-best-of-N, Robust
Elite SFT (S6), Flow-DPO, **R8a Outcome-GRPO-plain (canonical, STOP-B-1 split)**, **R8b
Outcome-GRPO-guarded (stronger, STOP-B-1 split)**, S7 sampler-control-only, human spot-check.
Matched-control outcomes were designed to remain publishable (CFG/BoN saturation → audit paper;
S6 tie → offline-distillation headline; S7 tie → sampler-control pivot; R8a tie → strongest
negative for the process-reward claim; R8b tie → weaker negative, ablation ladder still
informative). [Now: superseded by C1 (ADSR observability) + C6 (RL boundary).]

**C2 (M-PRM) — Credit-Unit Study.** Stepwise-Tweedie / FixedWin-Tweedie / BeatWin-Tweedie /
LyricSpan-Tweedie / Random-window controls, each differing from section-unit M-PRM *only* in
the segmentation function inside `section_process_reward` (clean single-variable isolation per
`COMPONENT_BUNDLE_LADDER.md`), at matched wall-clock GPU-hours. Verdict carried into ADSR:
section is **not** the best default credit unit (H3/Phase B.3 boundary → C6). [Now: superseded;
section credit is boundary evidence only.]

**C3 (M-PRM) — M-PRM Method.** Full C1 audit suite re-run plus mechanism ablations (w/o action
localization = A1; w/o lyric guard = A2; w/o CVaR = A3; fixed-window substitution = H3; w/o
robust LCB = A5; w/o curriculum = A4) and model/regime controls (SAO secondary audit, per-genre
and per-stratum cross-tabs, long-song extension). R8a-tie = strongest negative; R8b-tie = weaker
negative. [Now: the entire M-PRM method claim is demoted to the C6 boundary paragraph; ADSR §10
"section credit not supported; FixedWin behaves like a persistent-quality proxy; LoRA/GRPO
first-wave stable but no clear common-metric gain."]

**Reward-evaluator, gate (Phase A/B/C.4), and matched-compute accounting** controls from M-PRM
v1.0 carry forward into §7 / §8 above (reward ensembling, anti-hacking probes, reliability gate
ρ ≥ 0.5, segmentation F1 ≥ 0.7, locality probe ≥ 1.5). The Phase-A/B/C.4 GPU-hour budget table
(850 / 650 / 1800 / ~600 + reruns + reserve = 5400 GPU-h plan-time estimate) reflected the
weight-update RL regime; ADSR's compute is overwhelmingly **offline (0 GPU-h on the cached
4096-pool)**, so the active budget is governed by §8, not by the M-PRM table.

### 10.B 2026-05-28 ETV Pivot Addendum (Round 3 — superseded by ADSR; raw-ETP controls survive as baselines)

*(The ETV primary claim — "ETV beats raw Early-Tweedie Pruning and BoN-K at matched compute" —
is itself now superseded: under ADSR, raw ETP and learned-verifier *selection* are baselines,
and the headline is **restart-reallocation**, not better selection within a fixed pool. The
control numbers below are preserved and re-cited above.)*

**C-ETV controls → ADSR mapping:**

| ETV control (2026-05-28) | Number | Now lives as |
|---|---|---|
| ETV-c1 Full BoN-8 | 1.0 @ 1.0 compute | **C2-b1 / C4-c1** (Pareto upper-bound) |
| ETV-c2 BoN-4 @ 0.5 | no-learning floor | **C2-b2 / C4-c2** (critical floor) |
| ETV-c3 Random prune @ 0.5 | ≈0.957 reward fraction | **C2-b3 / C4-c4** (random reallocation) |
| ETV-c4 Raw ETP Schedule A @ 0.500 | **0.9864** (regen 2026-06-04 on lyric-fix data; was 0.9858 on 2026-05-28) | **C2-b5 / C4-c3** (selection baseline) |
| ETV-c5 Raw ETP Schedule C / bottom-prune σ0.7 @ ≈0.85 | 0.9986 / 0.9996; bottom-prune σ0.7 false-negative 0.0195 | **C4-c3** (high-compute reference) |
| ETV-c6 Cross-metric validation | lyric WER now **EN-vocal only, n=282** | **C4-c6** (reward-circularity test) |
| ETV-c7 Human spot-check ≥32–64 pairs | ~10 listener-hours | **E2 / E8** (human override) |
| ETV-c8 Failure-case audit (late-bloomers, vocal vs instrumental) | late-bloomer rarity | **E2 / Fig 5**; vocal-vs-instrumental split now formalized as **H2b / C3** |

The **critical control** survives unchanged and is now §4.2: raw ETP@50 over BoN-4 ≈ **+0.0036**
— the explicit reason fixed-pool selection cannot be the headline and ADSR must win via
restart-reallocation. ETV training (GBDT/LambdaMART on cached features, CPU) survives as the
ADSR **quality verifier** (C2-b6 / E5), still bound by "no large-model training"; the **EVPD
audio model** (C3) is the new, deliberately-different learned component the ETV inventory did
not have.

ETV cross-references (preserved): `refine-logs/REVISION_INTAKE.md` Round 1 items C11/C12;
`orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` (canonical Track A validation, source of the
baseline numbers); `orbit-research/COMPONENT_BUNDLE_LADDER.md` ETV/ADSR addendums;
`orbit-research/ASSUMPTION_LEDGER.md` ETV1–ETV5 + B1–B5, now superseded by the ADSR H1–H6 / C1–C6
rows ("2026-06-04 ADSR Pivot Addendum").

---

## 11. Document history

- **v1.0** — 2026-05-15. Phase 1 of `/experiment-bridge`. Authored against `METHOD_SPEC.md`
  v2.0, `BASELINE_CEILING.md` §10 (PI v2.0 addendum), and `ASSUMPTION_LEDGER.md` v2.0. (M-PRM
  per-claim control inventory; now §10.A boundary.)
- **v1.1 — STOP-B-2 consistency patch.** 2026-05-15. §3.1 control #1 "Outcome-GRPO" split into
  **#1a R8a-plain (canonical)** + **#1b R8b-guarded (stronger)**. §3.4 tie-scenarios expanded to
  distinguish R8a-tie (strong negative for C3) from R8b-tie (weaker negative; demotes C3 but
  preserves the M-PRM ablation ladder).
- **v1.1-restoration-note** — 2026-05-20T08:00Z. Restored from agent-error deletion.
  Reconstructed verbatim from conversation context.
- **2026-05-28 ETV Pivot Addendum (Round 3).** Added the C-ETV control inventory (ETV-c1..c8);
  primary claim moved to "ETV beats raw ETP and BoN-K at matched compute". (Now §10.B,
  superseded; raw-ETP/BoN-4 controls retained as ADSR baselines.)
- **v4.0 ADSR reframe (2026-06-04): ETV→ADSR pivot per `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`.**
  Reframed the per-claim control inventory from selection (ETV) to compute reallocation (ADSR).
  New active §§1–9: C1 axis×σ observability + human validation; **C2 ADSR main method** with the
  §2.1 same-compute baseline ladder (Full BoN-8 / BoN-4 / random restart / raw restart / raw ETP
  / learned-verifier selection / type-match restart / ADSR), the §2.2 **two-factor ablation
  (axis-awareness × restart-reallocation)**, and the §2.3 **EVPD-branch on/off** control; **C3
  EVPD** with the **EVPD-vs-off-the-shelf-detector** control (C3-c2) and the onset-σ / type-error
  block; C4 compute–quality Pareto with the **raw-ETP@50-vs-BoN-4 ≈ 0.0036 critical control**
  (§4.2); C5 lyric as a first-class late axis (EN-vocal n=282, per-specificity-stratum,
  cross-prompt-not-cross-content); C6 RL boundary. Evidence-status honesty added throughout
  (foundation evidence exists: H1/H2 persistence, Track A raw-ETP 0.9864 @ 0.500, lyric 0.682
  EN-vocal n=282, RL boundary; EVPD not trained, restart/ADSR not run, vocal-presence labels not
  derived → planned controls flagged). Numbers corrected/preserved: lyric **0.682** EN-vocal
  n=282 (not 0.8432); Track A **0.9864** (was 0.9858); cross-prompt-not-cross-content;
  per-specificity-stratum. Kept all valid infra (gate `gate_v2.yaml.draft`, reward defs, prompt-id
  splits, compute accounting, canonical reward set `orbit-research/trajectory_candidate_dataset.jsonl`).
  M-PRM (§10.A) and ETV (§10.B) inventories retained as superseded boundary / historical audit.
  ETV-era file archived at `orbit-research/archive/etv_pre_adsr_20260604/orbit-research_CONTROL_DESIGN.md`.
