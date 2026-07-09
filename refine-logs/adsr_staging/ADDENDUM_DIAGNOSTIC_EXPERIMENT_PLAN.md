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
