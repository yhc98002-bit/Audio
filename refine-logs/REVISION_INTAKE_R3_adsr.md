# Revision Intake — Round 3 (ETV → ADSR mechanism reframe)

- **Target:** both — full canonical proposal stack (8 files).
- **Mode:** mechanism reframe (largest possible STOP-A revision; PI-frozen new direction).
- **Source of truth:** `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` (PI's frozen FINAL plan) +
  `refine-logs/ADSR_REFRAME_BRIEF.md` (the condensed anchor).
- **PI directive (2026-06-04):** "full reframe to ADSR (recommended)" + "section-by-section
  align to ADSR spec (recommended)" — controlled, not the heavy autonomous research-refine
  regeneration. Stop at STOP-A for sign-off.
- **Codex:** precondition PASS (`CODEX_OK`). ADVERSARIAL cross-file consistency review +
  fresh-thread independent re-eval per file role.
- **Doc-durability:** ETV-era files archived at `orbit-research/archive/etv_pre_adsr_20260604/`.

## The pivot
The project's third framing: **M-PRM → ETV → ADSR**. ETV (prune/select a fixed candidate
pool) becomes a *baseline*; the headline is now **ADSR = Axis-Deferred Speculative Restart**
(compute reallocation via RESTART/DEFER/CONTINUE), with a new **presence-vs-content split**
(H2b), a new learned **Early Vocal-Presence Detector (EVPD)** for high-stakes prompt-type
errors (H5/C3), and lyric as a first-class late-observable axis on the lyric-bearing vocal
subset (C5 — already aligned with the 2026-06-03 lyric fix).

## Critique items (reframe directives)

| ID | Owning stage | Affected artifact(s) | Directive |
|----|--------------|----------------------|-----------|
| R3-1 | 5+8 (mechanism) | FINAL_PROPOSAL, METHOD_SPEC | replace ETV-pruning method with ADSR restart/defer/continue + EVPD + 2 learned components |
| R3-2 | 4 (assumptions) | ASSUMPTION_LEDGER | new paper-bearing hypotheses H1-H6 (incl. H2b presence/content, H3 restart>selection, H5 type-errors) |
| R3-3 | 21 (claims) | FINAL_PROPOSAL, FINAL_PROPOSAL_SHORT | new contributions C1-C6 (C2 ADSR main; C3 EVPD; C5 lyric first-class) |
| R3-4 | 16 (experiments) | EXPERIMENT_PLAN_EXEC | E1-E9 (E3 EVPD, E6 ADSR restart, E7 lyric-deferred, E9 cross-backbone) + Phases 1-7 |
| R3-5 | 11 (controls) | CONTROL_DESIGN | ADSR baselines/controls (type-match restart, random/raw restart, EVPD vs off-the-shelf, two-factor ablation) |
| R3-6 | 21 (state) | CLAUDE.md, AGENTS.md | current-state snapshot reframed to ADSR; foundation vs planned evidence |

## Evidence-status discipline (binding)
- **Foundation (exists, repurposed):** H1/H2 persistence; Track A raw-ETP Schedule-A
  **0.9864** @ 0.500 (regenerated 2026-06-04); lyric **0.682** EN-vocal n=282; RL boundary.
- **NOT run (ADSR is forward-looking):** EVPD training (E3), restart/ADSR (E6), vocal-presence
  labels, H2b measurement, cross-backbone. The reframed proposal is plan-stage for the new
  method; it must not claim ADSR results that don't exist.

## Execution
Phase 1: 8 parallel drafting agents author each file's v4.0 ADSR version into
`refine-logs/adsr_staging/` (workflow `adsr-canonical-reframe`). Phase 2 anchor/simplicity:
the anchored problem is unchanged (early-trajectory information for compute-efficient
inference) — ADSR is a mechanism evolution, not problem drift; +1 learned component (EVPD)
keeps trainable-component count ≤2 (EVPD + quality verifier). Phase 3: Codex adversarial
cross-file consistency + faithfulness-to-ADSR-spec + evidence-honesty review; reconcile.
Then promote staging → canonical. Phase 4: REVISION_REPORT_R3 + STATE awaiting_human_continue.
