# Revision Report — Round 2 (lyric-intelligibility fix)

- Target: both (FINAL_PROPOSAL + EXPERIMENT_PLAN/EXEC + claim/control artifacts)
- Critique source: `refine-logs/REVISION_INTAKE_R2_lyricfix.md`
- Mode: **surgical factual correction** (NOT a full `/research-refine` regeneration). The
  critiques are factual corrections (a contaminated number, axis scoping, generalization
  wording), not methodology changes, so the proposal-revise channel was applied as targeted
  edits to the flagged sections to avoid over-rewriting the PI's canonical proposal.
- Round: 2 of MAX_ROUNDS=2 (Round 1 = ETV pivot, preserved at `REVISION_INTAKE.md` /
  `REVISION_REPORT.md`). Completed: 2026-06-04.
- Codex: precondition PASS (`CODEX_OK`); ADVERSARIAL pre-review + fresh-thread independent
  re-eval (reviewer-independence protocol).

## Critique Resolution

| ID | Owning stage | Addressed | Codex SCORE_DELTA | Notes |
|----|--------------|-----------|-------------------|-------|
| C1 | 21 (claim) | yes | +4 / 5 | lyric headline 0.8432 → 0.682 (EN-vocal n=282); 0.8432 kept only as a labeled contaminated prior |
| C2 | 4 (assumption) + 21 | yes | +4 / 5 | lyric axis scoped EN-vocal (248/282=88% signal; instrumental 1.0 sentinel masked; non-EN excluded) across FINAL_PROPOSAL/METHOD_SPEC/ASSUMPTION_LEDGER/CONTROL_DESIGN |
| C3 | 11 (control) | yes | +5 / 5 | dev/held_out reworded cross-PROMPT (not cross-content) + per-specificity-stratum reporting (rewrite confound) in EXPERIMENT_PLAN_EXEC + FINAL_PROPOSAL §13 |
| C4 | 12 (null-result) | yes | — | benign notes added to FINAL_PROPOSAL §10 Anti-overclaim (R2 clause overlap, R3 flat pool, near-dups/metal fixed) |
| C1b | 21 | yes | +4 / 5 | common-axis 0.9858 → 0.9864 in live claim rows (labeled before/after); historical snapshots preserved |

Round-1 Codex re-eval returned INSUFFICIENT on two residuals (shorthand "vocal subset"/"lyric
WER" → EN-vocal; source-record paths still pointing at pre-regen `full01`). Both were fixed in
the same round (loop-back): METHOD_SPEC ×3, EXPERIMENT_PLAN_EXEC ×2, CONTROL_DESIGN ×2.

## Files edited (live canonical only)

- `refine-logs/FINAL_PROPOSAL.md` — intro 0.9858→0.9864; "7 of 7 axes" lyric EN-vocal caveat;
  C2 anchor number; §10 anti-overclaim bullet; §13 cross-prompt + canonical-dataset pointer.
- `refine-logs/METHOD_SPEC.md` — auxiliary-axis lyric EN-vocal scope (the headline 0.682 note);
  the short axis-list "vocal subset"→EN-vocal; ETV feature-source → canonical merged dataset (×2).
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` — held-out Notes cross-prompt + per-stratum; source records
  → canonical merged dataset; reviewer-risk lyric-WER → EN-vocal.
- `orbit-research/ASSUMPTION_LEDGER.md` — ETV1 lyric EN-vocal footnote; ETV2 0.9858→0.9864.
- `orbit-research/CONTROL_DESIGN.md` — ETV-c4 0.9858→0.9864; ETV-c6 lyric WER → EN-vocal; source records.
- `CLAUDE.md` + `AGENTS.md` — current-state snapshot: 7/7 lyric EN-vocal caveat; Track A 0.9864 (was 0.9858).

## Anchor + Simplicity

- **ANCHOR_PASS** — the ETV method, problem framing, and five paper-bearing claims are unchanged;
  these are factual corrections to numbers/scope/wording. No problem drift.
- **SIMPLICITY_PASS** — no new trainable components (still ≤2), no new claims (still 5),
  no new mechanism. Nothing added that could be removed.

## DELIBERATELY NOT edited (preserved as point-in-time records / flagged for PI)

Per the doc-durability principle, dated historical snapshots were left intact (they correctly
recorded the state as of their date; they are superseded by the regenerated `*_CURRENT` /
canonical artifacts):
- `PROGRESS_REPORT_2026-05-28.md`, `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md`,
  `orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md` (its `0.8432` cross-axis caveat
  is superseded by the regenerated `TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` + the canonical
  `ICLR_REVIEWER_RISK_AUDIT.md` which already reads `0.6820 [EN-vocal n=282]`),
  `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md`, `ORBIT_EXPERIMENT_RESULTS.md`,
  `orbit-research/CURRENT_CANONICAL_FILES.md`.
- If the PI wants these dated snapshots annotated with a "superseded — see 2026-06-04 regen"
  pointer, that is a separate low-priority doc-hygiene pass.

## Next steps

- Review the edited FINAL_PROPOSAL.md / METHOD_SPEC.md / EXPERIMENT_PLAN_EXEC.md /
  ASSUMPTION_LEDGER.md / CONTROL_DESIGN.md and the LYRIC_FIX_REPORT.
- If satisfied, the STOP-A pivot package is ready for sign-off; next downstream skill is
  `/experiment-bridge "refine-logs/EXPERIMENT_PLAN.md"`.
- If more changes wanted, re-invoke `/proposal-revise` with new critique (Round 3).
