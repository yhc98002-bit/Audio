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
