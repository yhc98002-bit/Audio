# Experiment Plan — Index (v4.0 ADSR)

**Purpose**: this file is an **index**. The actual execution plan is
`refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0; downstream skills read this index and
follow the cross-references.

**Project**: **Axis-Deferred Speculative Restart (ADSR) for Flow-Matching Music
Generation** on **ACE-Step v1.5** (primary, lyric-to-song). Stable Audio Open is a
**high-priority, Phase-1-parallel cross-backbone replication target with a graceful
fallback** (E9; does not gate submission). **Budget**: 5,400 GPU-h on 8× A800 over
148 days; ≈4,860 GPU-h remaining. **Venue**: ICLR / NeurIPS / ICML / ISMIR.
**Status**: `STOP_A_READY_FOR_PI_APPROVAL` — **v4.0 ADSR reframe (2026-06-04)**
supersedes v3.0 (ETV) per the PI-frozen plan
`ADSR_Research_Plan_FINAL_EN_2026-05-29.md` + `refine-logs/ADSR_REFRAME_BRIEF.md`.
This is the project's third framing: **M-PRM → ETV → ADSR**.

> ADSR = compute **reallocation** via RESTART / DEFER / CONTINUE (terminate
> low-promise trajectories early, launch new independent seeds), with a
> **presence-vs-content split** (vocal *presence* early-decidable, lyric *content*
> late-decidable), a learned **Early Vocal-Presence Detector (EVPD)** for high-stakes
> prompt-type errors, and lyric as a first-class late-observable axis. ETV
> Early-Tweedie pruning is now the **"raw ETP" baseline**; M-PRM/section credit is
> **boundary** evidence.

## Evidence status (read before any claim)

**Foundation evidence (exists; repurposed as ADSR's anchor):**
- H1 / Phase A: ACE-Step inference-time headroom (`delta_sigma_bon_vs_base = 0.7549`).
- H2 / Phase B.1: intermediate Tweedie estimates carry predictive signal
  (`STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`, 128 prompts).
- Track A raw-ETP pruning (now the baseline): Schedule A **0.9864** reward_fraction @
  0.500 compute (regenerated 2026-06-04 on the lyric-fix dataset; was 0.9858 on
  2026-05-28, within noise); bottom-prune σ=0.7 false-negative 0.0195. The known
  raw-ETP@50-vs-BoN-4 delta ≈ **+0.0036** is why fixed-pool selection cannot be the
  headline (median regret ≈ 0) and motivates ADSR's restart reallocation.
- Lyric axis (EN-vocal only): **0.682** ETP@50, n=282, 248/282 = 88 % carrying signal
  (instrumental 1.0 sentinel masked, non-EN excluded;
  `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`).
- Track B globalness (mechanism): median 0.861, sign consistency 1.000.
- C6 / RL boundary: `COMMON_DEV_NO_CLEAR_WIN` — no clear first-wave common-metric gain.

**NOT yet run (ADSR is forward-looking; never report as results):** EVPD training
(E3); restart / the full ADSR loop (E6 — only offline-simulatable on the
4096-candidate pool); final vocal-presence labels; H2b presence/content measurement;
cross-backbone (E9).

## Files

| Stage | File | What it contains | When to read |
|---|---|---|---|
| Frozen source plan | `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` | PI-frozen FINAL ADSR spec (authoritative) | always |
| Reframe anchor | `refine-logs/ADSR_REFRAME_BRIEF.md` | single-source ADSR anchor (method, H1-H6, C1-C6, E1-E9, EVPD, evidence status, versioning) | always |
| Proposal | `refine-logs/FINAL_PROPOSAL.md` **v4.0** | ADSR proposal: C1-C6, ADSR method + EVPD + 2 learned components, E1-E9 (run-vs-planned), evidence-status section, anti-overclaim, STOP-A checklist | always |
| Proposal (short) | `refine-logs/FINAL_PROPOSAL_SHORT.md` **v4.0** | 1-2pp ADSR short | when a compact view is needed |
| Method spec | `refine-logs/METHOD_SPEC.md` **v4.0** | ADSR contract §§13-16 (restart/defer/continue, EVPD, quality verifier, compute accounting, offline-first); §§1-11 M-PRM + §12 ETV-pruning kept as **superseded boundary** | always |
| **Main exec plan** | **`refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0** | **E1-E9 with go/no-go gates; Phases 1-7; prompt-level cross-prompt splits + per-specificity-stratum reporting; offline-first ADSR simulation; EVPD training; cross-backbone parallel; PLAN_CODE_AUDIT; compute at matched expected NFE** | **always** |
| Assumption ledger | `orbit-research/ASSUMPTION_LEDGER.md` ("2026-06-04 ADSR Pivot Addendum") | H1-H6 + C1-C6 paper-bearing rows (incl. D2 EVPD assumption, marked FORWARD-LOOKING); ETV1-ETV5 + M-PRM rows kept as superseded | always |
| Control design | `orbit-research/CONTROL_DESIGN.md` ("2026-06-04 ADSR Pivot Addendum") | per-claim controls for C1-C6 (type-match restart, random/raw restart, EVPD vs off-the-shelf, two-factor ablation, EVPD-branch on/off); ETV/M-PRM controls kept as boundary | when designing baselines |
| Algorithmic formalization | `orbit-research/ALGORITHMIC_FORMALIZATION.md` ("2026-06-04 ADSR Pivot Addendum") | ADSR decision-logic + EVPD + matched-NFE compute-accounting pseudocode; quality-verifier tiers (linear/GBDT/LambdaMART — **no MLP**); ETV/M-PRM pseudocode kept as boundary | when implementing/auditing code |
| Diagnostic experiment plan | `orbit-research/DIAGNOSTIC_EXPERIMENT_PLAN.md` ("2026-06-04 ADSR Pivot Addendum") | E1-E9 detailed (purpose/design/metrics/gates); ETV E1-E6 + legacy diagnostics kept as boundary | before launching E1 |
| Null-result contract | `orbit-research/NULL_RESULT_CONTRACT.md` ("2026-06-04 ADSR Pivot Addendum") | ADSR failure routing (per ADSR §9: ADSR≤BoN-4 → observability paper; EVPD onset late → demote type-match; lyric noisy → "observability is hard"; etc.); ETV/M-PRM routes kept as boundary | when any ADSR block fails or ties |
| Component bundle ladder | `orbit-research/COMPONENT_BUNDLE_LADDER.md` ("2026-06-04 ADSR Pivot Addendum") | ADSR ablation ladder (verifier feature/model-family; EVPD architecture/off-the-shelf/onset; restart σ_c/threshold/budget; two-factor; EVPD-branch on/off); ETV/M-PRM rungs kept as boundary | when ordering runs |
| Revision trail | `refine-logs/REVISION_INTAKE_R3_adsr.md`, `refine-logs/REVISION_REPORT_R3_adsr.md` | Round-3 (ETV→ADSR) intake + report. Round-1 (ETV) and Round-2 (lyric fix) trails preserved in their own files. | pivot history |
| Run ledger | `orbit-research/RUN_LEDGER.jsonl` | append-only run provenance | every run |
| ETV pre-ADSR snapshot | `orbit-research/archive/etv_pre_adsr_20260604/` | the full v3.0 ETV canonical stack (reference; do not lose) | audit only |

## Phased flow (v4.0 — ADSR program; ADSR plan §11)

```text
ADSR program (offline-first on the cached 4096-candidate pool, then small real-gen confirm)
  Phase 1  Repair lyric measurement (DONE 2026-06-03) + build axis×σ observability (E1)
           + derive vocal-presence labels. Start cross-backbone integration in parallel.
           Gate: can lyric be a late-observable headline axis, and is vocal-presence-onset ≪ lyric-onset?
  Phase 2  Human early→final validation (E2, incl. early vocal-presence listening).
           Gate: do humans support early decidability (quality and presence)?
  Phase 3  Train EVPD + type-error study (E3) + ADSR offline simulation (E6 offline).  [make-or-break]
           Gate: is vocal presence early-decidable, and does ADSR (with type-match) beat BoN-k/random under fair compute?
  Phase 4  Learned quality verifier + risk calibration (E5).   Gate: does the verifier improve decision quality?
  Phase 5  Human spot-check (E8).                               Gate: does human judgment support ADSR?
  Phase 6  Robustness + cross-backbone replication (E9).        Gate: more than one narrow setting?
  Phase 7  Paper assembly.

Experiments: E1 axis×σ observability · E2 human early→final · E3 EVPD + type-error (NEW)
  · E4 raw pruning / same-compute baselines · E5 learned quality verifier · E6 ADSR main (restart)
  · E7 lyric-focused deferred eval · E8 human spot-check · E9 robustness + cross-backbone.

Boundary (cited, no new compute): M-PRM/section credit; raw ETP is the strong baseline (E4).

Hard stops
  STOP A: PI sign-off on the ADSR reframe (FINAL_PROPOSAL v4.0 / METHOD_SPEC / EXPERIMENT_PLAN_EXEC v4.0).
  STOP B: /experiment-bridge PLAN_CODE_AUDIT (no EVPD training / no ADSR real-gen before this).
  STOP C: pre-paper-draft verification on E1/E2/E3/E6 results.
```

## Key constraints

- **STOP-A gate.** Do not enter E1 without PI sign-off on the v4.0 ADSR stack.
- **Offline-first.** ADSR is first validated offline on the cached 4096-candidate
  pool ("restart" = draw the next independent pool candidate); a small
  real-generation run (≤64 prompts) confirms the proxy. EVPD training and ADSR
  real-generation are **not launched before STOP B**.
- **Matched expected-NFE accounting.** Every "same-compute" comparison charges the
  four-term cost (partial-to-σ_c + surviving-full + restart-new-seed +
  deferred-continuation); no optimistic accounting.
- **Two learned components, ≤2.** Lightweight quality verifier (ridge/GBDT/LambdaMART
  — **no MLP**) + EVPD audio net (the only learned neural component).
- **Critical E4/E6 comparison.** Raw ETP@50 vs BoN-4 ≈ +0.0036 (selection is
  near-tied) — the leverage is restart **reallocation**, not selection; ADSR's
  same-compute win over BoN-k / random restart is the make-or-break (E6).
- **Lyric axis EN-vocal only.** Never mix instrumental (1.0 sentinel) or non-EN into
  headline lyric metrics. Cross-prompt splits; per-specificity-stratum reporting.
- **Evidence honesty.** EVPD/restart/ADSR/vocal-presence-labels are PLANNED — no
  result claimed until run.
- **`configs/eval/gate_v1.yaml` frozen; `gate_v2.yaml.draft` stays `.draft`.**
- **Canonical reward set** `orbit-research/trajectory_candidate_dataset.jsonl` (promoted
  2026-06-04) and the ETV-era archive are not to be modified.
- **Anti-overclaim list** (ADSR §14 / FINAL_PROPOSAL anti-overclaim) enforced.

## Downstream skill

`/experiment-bridge "refine-logs/EXPERIMENT_PLAN.md"` reads this index, follows the
cross-references, and implements the E1-E9 ADSR experiments in
`EXPERIMENT_PLAN_EXEC.md` v4.0 order. It **must not** launch any experiment past a
hard stop (esp. EVPD training or ADSR real-generation before STOP B) without explicit
human approval. The current next gate is **STOP-A PI sign-off**.

---

## Document history

- **v1.0–v2.2** (2026-05-15 → 2026-05-24): M-PRM era (Headroom-Gated M-PRM; credit-unit
  ladder). Historical; preserved in archives.
- **v3.0** (2026-05-28): ETV pivot — Early Trajectory Verifiers; six experiments E1-E6 on
  cached Track A candidates. Now superseded by v4.0; pre-v4.0 index archived at
  `orbit-research/archive/etv_pre_adsr_20260604/refine-logs__EXPERIMENT_PLAN.md`.
- **v4.0 ADSR reframe** (2026-06-04): total rewrite around the PI-frozen ADSR direction
  (`ADSR_Research_Plan_FINAL_EN_2026-05-29.md`). Project retitled to "Axis-Deferred
  Speculative Restart (ADSR) for Flow-Matching Music Generation". Active main plan is now
  `EXPERIMENT_PLAN_EXEC.md` v4.0 (E1-E9, Phases 1-7). ETV raw-Tweedie pruning demoted to
  baseline; M-PRM/section credit demoted to boundary. Evidence honesty: foundation evidence
  carried forward; EVPD/restart/ADSR/vocal-presence-labels marked PLANNED, not run. Trigger:
  `/proposal-revise both` Round 3.
