# Appendix Runs — Conditional / Out-of-Main-Order Experiments

*Created 2026-05-20 by /proposal-revise Round 2 per critique #14: "Move SAO out of the main run order. Create or update: orbit-research/APPENDIX_RUNS.md. Put SAO under: 'Appendix-only SAO Audit / Transfer'."*

## Appendix-only SAO Audit / Transfer

**Status**: MOVED OUT of main run order per critique #14. NOT a budget-reserved main milestone.

**Activation conditions** (per critique #14, all must hold):
- ACE-Step main evidence is complete;
- `phase_a_sao_audit` is clean;
- Project time remaining > **14 days**;
- PI explicitly approves.

**Setup (if activated)**:
- Rerun M-PRM (and one matched-compute control) on Stable Audio Open with adapted prompt set (text-to-music without lyric guard).
- Metrics: SAO − ACE-Step transfer gap.

**Failure interpretation**:
- SAO transfer failure → reported as model-specificity, not a paper-killer (per FINAL_PROPOSAL §10 anti-overclaim list).

**Compute**: ~150 GPU-h, conditional. NOT pre-reserved in main 5,400 envelope; drawn from FINAL_PROPOSAL §7 optional/appendix pool only if all four activation conditions hold.

---

## Activation log

PI signs each row when activating a conditional appendix run.

| Date | Item | Triggered by | PI signature |
|------|------|--------------|--------------|
| (none yet) | — | — | — |

Add new rows when activated. Cross-reference in `MANIFEST.md` and `RUN_LEDGER.jsonl`.
