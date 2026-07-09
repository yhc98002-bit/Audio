# Revision Report — Round 3 (ETV → ADSR mechanism reframe)

- **Target:** both — full canonical proposal stack (8 files).
- **Mode:** mechanism reframe (largest STOP-A revision; PI-frozen new direction).
- **Source of truth:** `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` + `refine-logs/ADSR_REFRAME_BRIEF.md`.
- **PI directive (2026-06-04):** full reframe to ADSR + section-by-section alignment (controlled,
  not autonomous research-refine regeneration). Stop at STOP-A.
- **Codex:** precondition PASS. Adversarial cross-file review (round 1) → 4 must-fixes → fixed →
  fresh-thread re-confirm (round 2) → residual outcome-presupposing wording → fixed. Numbers clean.
- **Execution:** 8 parallel drafting agents authored each file's v4.0 ADSR version into
  `refine-logs/adsr_staging/` (workflow `adsr-canonical-reframe`); Codex-reviewed; reconciled;
  promoted to canonical. ETV-era originals archived `orbit-research/archive/etv_pre_adsr_20260604/`.

## The pivot (M-PRM → ETV → ADSR)
ETV (prune/select a fixed candidate pool) → **ADSR = Axis-Deferred Speculative Restart** (compute
reallocation via RESTART/DEFER/CONTINUE). New: presence-vs-content split (H2b); learned **EVPD**
audio detector for high-stakes prompt-type errors (H5/C3); restart mechanism; lyric as a
first-class late-observable axis on the lyric-bearing vocal subset (C5). ETV raw-ETP pruning →
strong baseline; M-PRM/section credit → boundary.

## Files reframed (promoted to canonical, v4.0)
| File | New role |
|---|---|
| `refine-logs/FINAL_PROPOSAL.md` | flagship ADSR proposal: abstract, when-to-continue problem, C1-C6, ADSR method + EVPD + 2 components, E1-E9 (run-vs-planned), anti-overclaim, **evidence-status section**, STOP-A checklist |
| `refine-logs/FINAL_PROPOSAL_SHORT.md` | 1-2pp ADSR short (was 2-generations-stale M-PRM — full rewrite) |
| `refine-logs/METHOD_SPEC.md` | ADSR contract (§§13-16): restart/defer/continue, EVPD, quality verifier, compute accounting, offline-first; M-PRM §§1-11 + ETV §12 marked superseded boundary (kept) |
| `refine-logs/EXPERIMENT_PLAN_EXEC.md` | E1-E9 + Phases 1-7; offline-first ADSR sim; EVPD training; cross-backbone parallel |
| `orbit-research/CONTROL_DESIGN.md` | ADSR baselines/controls; M-PRM controls retained as superseded boundary |
| `orbit-research/ASSUMPTION_LEDGER.md` | "2026-06-04 ADSR Pivot Addendum": H1-H6 + C1-C6 (incl. D2 EVPD assumption marked FORWARD-LOOKING) |
| `CLAUDE.md` / `AGENTS.md` | current-state reframed to ADSR; hard boundaries add EVPD-training/ADSR-real-gen block + reward-set protection |

## Codex resolution
| Round-1 must-fix | Status |
|---|---|
| MLP drift (verifier offered a "small MLP" — contradicts the frozen "EVPD is the only learned neural component") | RESOLVED (METHOD_SPEC, EXPERIMENT_PLAN_EXEC, ASSUMPTION_LEDGER B3) |
| Planned H2b/presence-content stated as completed result | RESOLVED (CONTROL_DESIGN → "tests whether … (H2b UNMEASURED)") |
| EVPD/OOD "shown" wording | RESOLVED (reworded "test whether") |
| CLAUDE.md hard boundaries weaker than AGENTS.md | RESOLVED (mirrored) |
| Round-2 residual: "show that type-match restart improves" / "to show OOD" presuppose unrun outcomes | RESOLVED ("test whether"; FINAL_PROPOSAL §E3-5, EXPERIMENT_PLAN_EXEC E3-4/E3-6, METHOD_SPEC off-the-shelf baseline) |

**Documented (not over-edited):** the "early-σ is OOD for off-the-shelf detectors" statements in
the EVPD *design rationale* (FINAL_PROPOSAL, FINAL_PROPOSAL_SHORT, METHOD_SPEC) are the PI's own
framing from the frozen plan §4.2, and are explicitly marked unmeasured/forward-looking by every
file's evidence-status section and by ASSUMPTION_LEDGER row D2 ("working — NOT yet trained;
FORWARD-LOOKING"); E3's off-the-shelf baseline tests OOD. So they are honest-in-context.

## Evidence honesty (the binding discipline)
- **Foundation (exists, repurposed):** H1/H2 persistence; Track A raw-ETP Schedule-A **0.9864**@0.500;
  lyric **0.682** EN-vocal n=282; Track B globalness 0.861; C1/C6 RL boundary.
- **NOT run (forward-looking; stated as planned everywhere):** EVPD training (E3), restart/ADSR (E6),
  vocal-presence labels, H2b measurement, cross-backbone. No ADSR/EVPD/restart result is claimed.
- Number hygiene: no uncaveated 0.8432/0.8434/0.9858; all labeled contaminated-prior / before-after.

## Anchor + Simplicity
- **ANCHOR_PASS** — the anchored problem (use early-trajectory information for compute-efficient
  inference-time scaling on flow-matching music) is unchanged; ADSR is a mechanism evolution
  (selection → reallocation), not problem drift.
- **SIMPLICITY_PASS (at the limit)** — exactly **2 learned components**: the lightweight quality
  verifier (near-saturated, ridge/GBDT/LambdaMART — explicitly **no MLP**) + the EVPD audio net.
  The EVPD justification (genuine early-σ audio learning, OOD for off-the-shelf) is stated; the
  count is ≤2, not silently 3.

## Index + contract files — REFRAMED (follow-up pass, 2026-06-04, PI-requested)
- `refine-logs/EXPERIMENT_PLAN.md` — fully rewritten to v4.0 ADSR index (E1-E9, Phases 1-7,
  evidence status, foundation-vs-planned, points to the v4.0 stack).
- `orbit-research/CURRENT_CANONICAL_FILES.md` — reading-path reframed to ADSR (Start-Here now points
  to the ADSR plan/brief/proposal; §2 "raw ETP baseline" 0.9864; §6 corrected — the proposal files are
  the CURRENT v4.0 ADSR canonical, no longer mislabeled "historical v2.1").
- The 4 v1.3 contracts (`COMPONENT_BUNDLE_LADDER`, `ALGORITHMIC_FORMALIZATION`,
  `DIAGNOSTIC_EXPERIMENT_PLAN`, `NULL_RESULT_CONTRACT`) — each got a "2026-06-04 ADSR Pivot Addendum"
  (4 parallel agents → staging → quality-checked → appended) that SUPERSEDES its "2026-05-28 ETV Pivot
  Addendum" (both retained per doc-durability), maps ETV→ADSR for that domain, drops the E-R10 MLP
  (EVPD = only learned neural component), and stays evidence-honest (EVPD/restart/labels PLANNED).
  Archived pre-edit at `orbit-research/archive/etv_pre_adsr_20260604/`.

## Still NOT touched (deliberate)
- Dated historical snapshots (PROGRESS_REPORT_2026-05-28, EXPERIMENT_PROGRESS_CONTEXT_2026-05-28,
  *_2026-05-28, PHASE_B1_H2_CONCLUSION_2026-05-23) — preserved as point-in-time records (doc-durability).
- `refine-logs/adsr_staging/` — drafting + addendum staging copies retained for diff/audit; deletable
  once the PI accepts the promoted canonical stack.

## Next steps
- PI reviews the reframed canonical stack + `ADSR_REFRAME_BRIEF.md`. STATE `awaiting_human_continue`.
- If satisfied → `/experiment-bridge "refine-logs/EXPERIMENT_PLAN.md"` (STOP B; will also need the
  index reframe). If more changes → `/proposal-revise` again.
