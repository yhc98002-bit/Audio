# Canonical Changes — 2026-05-23 H3-Prescreen Pivot

> PI-approved amendment of canonical proposal + plan + method spec
> per `PI_REPORT_H3_AUTONOMOUS_v2_2026-05-23.md` decisions 1-8.

## Files touched

| File | Sections amended | Backup |
|---|---|---|
| `refine-logs/FINAL_PROPOSAL.md` | §3 C2, §3 C3, §6 H3 | `orbit-research/canonical_backups_2026-05-23/FINAL_PROPOSAL.md.pre-h3-pivot` |
| `refine-logs/FINAL_PROPOSAL_SHORT.md` | C2/C3, Phase B gate semantics, failure-resilient route H3 | `…/FINAL_PROPOSAL_SHORT.md.pre-h3-pivot` |
| `refine-logs/METHOD_SPEC.md` | Header v2.1→v2.2, §4.4 credit-unit gate, §5 Phase C M-PRM training intro + §5.1 per-segment process reward | `…/METHOD_SPEC.md.pre-h3-pivot` |
| `refine-logs/EXPERIMENT_PLAN_EXEC.md` | Block B.3, Block C C3 cell, Block C main paper table (row 7 + 8) | `…/EXPERIMENT_PLAN_EXEC.md.pre-h3-pivot` |

## PI decisions implemented

1. ✓ **H3 label = `SECTION_FAIL_WITH_INSTR_PROMPT_FIT_NUANCE`** — adopted in FINAL_PROPOSAL §6 H3 + EXPERIMENT_PLAN_EXEC Block B.3 + METHOD_SPEC §4.4.
2. ✓ **M-FixedWin-PRM = conservative primary; M-Section-PRM = diagnostic / negative control** — in FINAL_PROPOSAL §3 C3 + FINAL_PROPOSAL_SHORT C3 + METHOD_SPEC §5 intro + §5.1 + EXPERIMENT_PLAN_EXEC Block C main table.
3. ✓ **Pivot wording**: "credit unit should be empirically selected for the target generation regime; for ACE-Step 30-40 s short-form generations, FixedWin is the conservative default" — applied verbatim spirit in FINAL_PROPOSAL §3 C2 + §6 H3 + FINAL_PROPOSAL_SHORT C2. Explicit "do NOT claim sections never work" preserved.
4. ✓ **Plan-patch to EXPERIMENT_PLAN_EXEC + METHOD_SPEC**: Phase C primary = M-FixedWin-PRM; Section-PRM = diagnostic; BeatWin = descriptive/optional (coverage caveat); LyricSpan = vocal-specific optional. All four credit-unit roles named in METHOD_SPEC §4.4 + EXPERIMENT_PLAN_EXEC Block B.3.
5. ✓ **Finite-coverage rule (≥ 50 %) adopted** as pre-registered rule for headline-winner candidacy. Encoded in FINAL_PROPOSAL §6 H3 + EXPERIMENT_PLAN_EXEC Block B.3 + METHOD_SPEC §4.4.
6. ✓ **Sectionability v2 honest framing accepted**: detector finds many local novelty boundaries (mean 5.01/clip, 99.6 % have 3+ sections, median 8 s) but does not validate them as song-level sections. CU-MS underperformance attributed to **fixed-grid (k=4) misalignment** (82/256 match k=4, 145/256 have >4, 29/256 have <4), not absence of sectionability. Documented in FINAL_PROPOSAL §6 H3 + EXPERIMENT_PLAN_EXEC Block B.3 + sectionability report.
7. ✓ **Phase D pair design accepted**: primary = M-FixedWin-PRM vs R8a/R8b; M-Section-PRM diagnostic. Reflected in EXPERIMENT_PLAN_EXEC Block C main paper table rows 7+8.
8. ✓ **Phase C NOT launched**, M-PRM training NOT launched, no new H3 experiments. Hard boundaries preserved.

## Diff highlights (semantic)

### FINAL_PROPOSAL.md §3 C2 — Credit-Unit Selection Study

- "Musical sections are a better credit unit … than naive timestep or fixed-window rewards" → "The appropriate process-reward credit unit should be empirically selected for the target generation regime, not assumed a priori. … FixedWin is the conservative downstream default."
- Section retained as tested-and-mostly-negative hypothesis with explicit one strict-pass cell on instr × prompt_fit (+0.167); "we explicitly do NOT claim that sections never work".

### FINAL_PROPOSAL.md §3 C3 — M-PRM Method

- "M-PRM — a method for musical credit assignment … musical-section process rewards" → "process rewards over the empirically selected credit-unit grid. Provisional primary: M-FixedWin-PRM; M-Section-PRM diagnostic; M-BeatWin-PRM descriptive (coverage caveat); M-LyricSpan-PRM vocal-stratum-specific optional."

### FINAL_PROPOSAL.md §6 H3 — Where to Reward

- "Section-level reward gains correlate better with per-section human preference than four non-section credit units" → "Empirical credit-unit selection … pre-specified same-winner rule on dev AND corrected held-out … finite-coverage ≥ 50 % required for headline candidacy."
- Added: explicit 2026-05-23 prescreen result (classification `SECTION_FAIL_WITH_INSTR_PROMPT_FIT_NUANCE`); explicit sectionability v2 caveat; explicit "we do NOT claim sections never work".
- Cross-stratum Kendall-τ ≥ 0.5 escape hatch REMOVED.

### METHOD_SPEC.md §4.4 — Credit-unit gate

- Title: "must hold for section credit to be the M-PRM signal" → "REVISED 2026-05-23 post-H3-prescreen: empirical selection, not section-only".
- Added: same-winner pass rule, finite-coverage ≥ 50 % rule, CU-TS structural NaN footnote, 2026-05-23 prescreen result, role assignments (FixedWin primary / Section diagnostic / BeatWin descriptive / LyricSpan vocal-specific).

### METHOD_SPEC.md §5 — Phase C M-PRM Training

- Title: "Phase C — M-PRM Training" → "REVISED 2026-05-23: M-FixedWin-PRM primary".
- Added: explicit "Phase C NOT YET LAUNCHED" status; primary credit unit = FixedWin; M-Section-PRM diagnostic role; §5.1 per-segment reward rewritten for FixedWin grid (with diagnostic Section-grid reference).

### EXPERIMENT_PLAN_EXEC.md Block B.3

- "Credit-unit comparison" → "Credit-unit selection (REVISED 2026-05-23 post-H3-prescreen, PI-approved pivot)".
- Status changed from MUST-RUN-planned to EXECUTED 2026-05-23.
- Added: pre-specified same-winner rule, finite-coverage ≥ 50 % rule, full 2026-05-23 prescreen result, sectionability v2 audit summary, cross-references to corrected held-out artifacts.
- Compute envelope corrected: ~500 GPU-h planned → ~4.5 GPU-h actual (per-section human eval moves to Phase D Tier 1).

### EXPERIMENT_PLAN_EXEC.md Block C — Main paper table

- Row 7: "Best non-section local credit unit (best of FixedWin / BeatWin / LyricSpan Tweedie per H3 sub-results)" → "M-Section-PRM (diagnostic / negative-control comparison)".
- Row 8: "M-PRM full" → "M-FixedWin-PRM full (provisional primary per H3 coverage-aware result)".

## Files NOT touched (per PI hard rules)

- `configs/eval/gate_v1.yaml` — UNTOUCHED, mtime preserved (2026-05-16 22:35:35).
- `configs/runs/phase_b3_credit_unit_comparison.yaml` — unchanged (only used for replays).
- `configs/runs/phase_b1_reliability.yaml` — unchanged.
- Reward / σ / credit-unit / prompt-split definitions — unchanged.

## Audit trail

- `git diff orbit-research/canonical_backups_2026-05-23/FINAL_PROPOSAL.md.pre-h3-pivot refine-logs/FINAL_PROPOSAL.md` shows the exact changes.
- `orbit-research/RUN_LEDGER.jsonl` has a `canonical_h3_pivot_applied` event entry timestamped at this update.
- This file (`CANONICAL_CHANGES_2026-05-23.md`) is the human-readable summary.

## Remaining PI decisions (not yet addressed)

None blocking. Optional follow-ups:
1. Phase D pair design final lock-in: confirm 12-method matched-compute matrix updated with M-Section-PRM as diagnostic (currently row 7 of main table).
2. Phase D human eval Tier 1 protocol update: confirm M-FixedWin-PRM as primary in the pair-construction script (when Phase D scripts are drafted).
3. Phase C launch readiness: PI decides timing (currently NOT YET LAUNCHED per hard rule of this directive).
4. Codex v2 reviews already on file: should they be tar-archived for the PI-listening packet?
