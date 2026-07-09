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
   restart, not better selection). MLP is optional-appendix at most.
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
| **E-R10 ETV-MLP** | **DROPPED from main ladder** (violates the lightweight-verifier freeze) | optional appendix only — NOT a main rung |
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
