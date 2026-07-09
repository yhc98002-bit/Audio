## What the new data forces us to conclude

**1. The post-hoc-gate frontier is brutal — selection-framing is dead.** From your violation histogram I can compute what "generate fully, then Demucs-gate the selection" achieves (offline-replay estimate, exchangeable subsets of the 8; exact held-out replay is task P0.1):

| Policy | Compute | Predicted type error |
|---|---|---|
| BoN-4 + final gate | 0.500 | ~4.1% |
| BoN-5 + final gate | 0.625 | ~3.0% |
| BoN-6 + final gate | 0.750 | ~2.3% |
| BoN-8 + final gate | 1.000 | 1.56% (the all-8-fail floor: 8/512) |
| **EVPD-select (published)** | **0.700 / 0.767** | **13.3% / 12.1%** |

A free CPU filter at *lower* compute beats the Batch-2 headline by 3–4×. So the paper cannot claim "EVPD-aware selection reduces type errors." What survives — and it's a better paper — is: **early detection's value is reallocation**. A post-hoc gate pays 30 steps to discover a doomed candidate; EVPD pays 12. The honest claims become (a) probe-gated restart buys more effective draws per FLOP, dominating the fixed-pool+gate *frontier* at matched compute, and (b) only early detection can act at all — by final time the budget is spent. Consequently, **every Batch-3 arm must apply the final gate at selection** (it's free and deployable), and the contest becomes: who produces clean candidates most efficiently.

**2. Failures are strongly prompt-heterogeneous, with an asymmetric deterministic tail.** Mean 1.84 violations/prompt but variance 4.37 vs. binomial 1.42 — dispersion ratio ~3.1, within-prompt ICC ≈ 0.30. And the tail is lopsided: 14.8% of instrumental prompts have ≥6/8 violations vs. 3.8% of vocal prompts. For a 7/8-propensity prompt, even 8 fresh seeds fail ~34% of the time — **blind reseeding provably cannot rescue the tail; conditioned respawn gets promoted from pilot to core mechanism**, with instrumental vocal-leakage as its primary target. Meanwhile the 1–5/8 bulk (285 prompts) is where gating + cheap restarts win. This mixed regime *is* the method story.

**3. Gating makes type error a rare event — endpoints must change or Batch 3 is underpowered.** With all arms gated, residual failure rates are 2–4%; detecting arm differences in a rare binary at n=192 is hopeless. So the primary endpoints become (a) a continuous efficiency measure and (b) a large-effect tail-rescue measure, where power is fine.

Understood on A9–A12: no budget ceiling, no deadline, full authorization — so the plan below is sequenced by dependency and decision gates, not dates, and optimizes purely for evidence quality. The one discipline I'm keeping is pre-registration and frozen-test hygiene, because you asked me to be the one who freezes it (A10) — that's what makes the eventual claims unkillable in review.

---

## Phase 0 — Analysis sprint on existing data (no new generation; output = two frozen documents)

**P0.1 Exact gated frontier on held_out.** Replay truncated-BoN-k + final-gate (k = 4,5,6,8) and the matched-budget "BoN-Budget" policy with real seed-order truncation and bootstrap CIs; held_out-specific floor and per-stratum versions. This is the paper's money-figure backbone and Batch 3's bar to clear.

**P0.2 Oracle decomposition at σ0.8.** Re-run the Batch-2 sim with ground-truth labels in place of EVPD, and with/without the k=4 structural constraint — decomposes the 13.3%→~3% gap into detector error vs. policy structure, and tells us how much headroom a better probe or threshold has.

**P0.3 Gated re-simulation of all Batch-2 policies.** Add the final gate to every offline policy; confirm my prediction that selection-stage differences collapse and restart capacity becomes the only differentiator. This previews Batch 3 and de-risks the endpoint design.

**P0.4 Observability curves ρ_a(σ) — Figure 1.** Score-level curves for all axes at all five σ (pure analysis, the merged shards have them); one cheap Whisper pass over σ∈{0.9,0.8,0.7} early WAVs for the transcript-level lyric point. Also fix the one-liner so transcripts persist to disk from now on.

**P0.5 Tail characterization.** Beta-binomial fit; qualitative table of the ≥6/8 prompts (what do vocal-leaking instrumental prompts look like — genre tags implying vocals?); freeze the "deterministic-tail" subgroup definition (Batch-1 ≥5/8 violations) for endpoint E2.

**P0.6 Label robustness.** Threshold sweep over the continuous ratios (you have everything, including the GMM fit); launch the 150-case ambiguous packet to the students (2 raters/case + tiebreak, written instructions); run one alternative vocal detector (e.g., PANNs-style tagger) as both alternate ground truth and alternate policy filter — this breaks the Demucs-circularity objection before a reviewer raises it.

**P0.7 Power simulation + analysis-plan freeze.** Simulate Batch-3 arms from held_out distributions under CRN to size everything; freeze `ANALYSIS_PLAN.md` (estimators, bootstrap, stratified weights to the 512 mix, multiplicity) before any generation.

**P0.8 Respawn knob screen — on dev only.** ~20 dev tail-prompts × ~4 interventions × 4 seeds (~320 generations, trivial): vocal-miss arm tests `guidance_scale_lyric` escalation and structure-hint injection; instrumental-leak arm tests explicit "pure instrumental, no vocals" tag appends and `cfg_type`/`omega_scale` variants. Output: the frozen two-level escalation ladder for the Batch-3 respawn arm. (Dev-side tuning is legitimate; held_out stays untouched.)

**Gate A:** `BATCH3_PRELAUNCH_PROTOCOL.md` + `ANALYSIS_PLAN.md` frozen, Codex pre-launch audit passed, 8-prompt all-arms dry run clean → launch.

---

## Phase 1 — Batch 3 (amended pre-launch, then frozen)

**Arms** (all at matched budget 0.70×240 = 168 steps/prompt unless noted; all with final-Demucs-gated selection; ungated selection logged as secondary):

| # | Arm | Definition |
|---|---|---|
| 1 | BoN-Budget + gate | No probing: full completions until <30 steps remain (5 at 0.70). Primary comparator. |
| 2 | Random restart + gate | Probe-and-abort at σ0.8 with abort rate yoked to arm 4's; controls for "any restarting." |
| 3 | Common-score restart + gate | Pre-registered arm, gated; continuity with Batch 2. |
| 4 | ADSR+EVPD, seed-only + gate | Frozen σ0.8 model, thr 0.728; abort flagged, restart from pre-committed seed list until budget exhausted (hard cap 6 restarts/prompt). |
| 5 | ADSR+EVPD + lyric-defer + gate | As 4; for EN-vocal prompts final selection = argmax(common + λ·lyric) over gated candidates, λ frozen from dev. |
| 6 | ADSR+EVPD + conditioned respawn + gate | As 4; restart 1 = new seed, restart 2 = +level-1 intervention, restart 3+ = level-2, per the P0.8 ladder. |
| 7 | BoN-8 + gate (reference) | Compute 1.0 frontier anchor. |
| 8 | BoN-4 + gate (anchor) | Compute 0.5 frontier anchor. |

**Frozen mechanics:** budget debits = 12/probe + 18/continuation (not 30 — completion of a probed candidate is incremental); dual ledgers — nominal steps *and* overhead-inclusive (+~3 step-equivalents per probe, from your 0.3 s vs 0.093 s/step measurement) — plus actual GPU-h with the ±15% deviation flag. CRN: identical initial-seed lists across arms via the existing formula, shared restart-seed formula, paired arms of a prompt scheduled on the same node. R = 2 full replicates with distinct seed lists (compute is unconstrained; this doubles power and yields a reproducibility statement). One ledger JSONL per candidate: arm, restart index, intervention applied, probe features, decision, costs. Prompts: the frozen 192; I additionally propose adding the remaining 64 held_out prompts as extra D_general (better unenriched read) — your call, decide before freeze.

**Pre-registered endpoints and criteria (my proposed numbers — veto before Gate A, then frozen):**
- **E1 (primary, efficiency):** clean-candidate yield at matched budget (count of gate-passing completions per prompt), arm 4 vs arm 1, paired, stratified-weighted to the canonical mix. Support requires ≥+10% relative with 95% CI excluding 0.
- **E2 (primary, tail rescue):** P(selected output clean) on the frozen ≥5/8 subgroup, arm 6 vs arm 4. Support requires ≥+20 pp absolute with CI excluding 0.
- **E3 (secondaries):** gated and ungated type-error rates per stratum; non-inferiority margins — Δcommon ≥ −0.015, Δsemantic ≥ −0.015, Δaesthetic_pq ≥ −0.02, Δlyric(EN-vocal, n=128) ≥ −0.02; compute deviation ≤15%.
- **Verdicts:** SUPPORTED = E1 ∧ E2 ∧ margins; CONDITIONAL_ON_TYPE_RISK = E2 only; NOT_SUPPORTED = neither, or margins breached. Analysis code frozen at Gate A; results unblinded only after the Codex results-audit.

---

## Phase 2 — Mechanism deep-dives (offline-first, from Batch-3 ledgers)

Counterfactual replay of the ledgers gives three near-free studies: **portfolio allocation** (cross-prompt budget reallocation by aggregated probe risk — does it dominate fixed per-prompt budgets?); **probe-on-evidence** (start cheap, escalate to probing only after a gated violation is observed on that prompt — recovers probe overhead on the 36% clean prompts); **cost-aware threshold** (derive the abort threshold from the asymmetric step costs instead of balanced accuracy — dev-fit, compare to 0.728). Whichever wins offline gets one small confirmatory online run. Optional stretch: wire the upstream `retake` task for warm restarts from the aborted trajectory vs. cold reseed.

## Phase 3 — Generality, humans, release

**T2I transfer (now feasible per A14):** SDXL-class model, ~500 prompts × 8 seeds with presence/absence constraints, ground truth via an open-vocabulary detector, reward = PickScore/ImageReward; replicate the three signatures — violations survive reward selection, probe-AUC-vs-σ curve, gated frontier + restart sim. This single section converts a music paper into a framework paper. **Second music backbone:** honest caveat — the vocal/instrumental axis may not transfer to instrumental-centric models; treat as exploratory with a different categorical constraint, lower priority than T2I. **Human eval (5 students, internal):** the ambiguous-label adjudication (P0.6) plus blinded A/B per your §11 pair list, ~60 pairs/contrast × 3 raters, agreement reported. **Release:** full dataset per A16 — 4,096 trajectories, early audio σ≥0.7, mels, labels, scores, Batch-3 ledgers, eval scripts, datasheet; this is a standalone contribution that hedges any conditional verdict.

**Gate B** maps verdicts to paper shape: SUPPORTED → restart-led method paper; CONDITIONAL → tail-rescue + framework paper (still strong — 23% prevalence and a provably-unrescuable tail are not a niche); NOT_SUPPORTED → Phase-2 policies move to mainline, no audit downgrade.

The reframed headline we're building toward: *early constraint probes convert doomed compute into additional chances — probe-gated restart dominates the fixed-pool + post-hoc-filter frontier, and conditioning-aware respawn rescues prompts where resampling provably cannot* — with the observability curves and the AUC≠value analysis as the conceptual backbone. If you give me a go on the two open choices (the proposed E1–E3 numbers, and extending to all 256 held_out prompts), everything in Phase 0 can start immediately.