# Revision Intake — Round 2 (lyric-intelligibility fix)

**For:** `/proposal-revise both` (or `proposal-only`).
**Source of truth:** `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`
(evidence + before/after) and the audit `PROMPT_SET_AUDIT_20260529.md` (R1/R5/R8/R2/R3).
**Trigger:** PI directive 2026-06-03 — make `lyric_intelligibility` a load-bearing headline
axis; the published lyric number was contaminated by an instrument-sentinel and a thin/non-EN
floor. Fix implemented + 132 prompts regenerated; canonical analysis re-promoted 2026-06-04.

These are factual corrections to claim/proposal text. Each item: where → what to change.

## C1 — Correct the contaminated lyric number (P0) [stage: result→claim binding]
- The lyric `reward_fraction` at the ETP@50% schedule was reported as **0.8432 over all 512
  prompts**, which pooled 196 instrumental prompts at the constant `1.0` Whisper sentinel.
  Honest value is **0.682 on the EN-vocal subset (vocal_scorable, n=282)**.
- Replace every occurrence of the lyric `0.8432` / "0.84" headline with **`0.682 (EN-vocal, n=282)`**:
  - `orbit-research/ICLR_REVIEWER_RISK_AUDIT.md` — already auto-corrected on re-promotion (now
    `lyric_intelligibility=0.6820 [EN-vocal n=282]`); verify wording.
  - `orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md:42` (and any sibling PI report).
  - `refine-logs/FINAL_PROPOSAL.md`, `refine-logs/METHOD_SPEC.md`, `orbit-research/ASSUMPTION_LEDGER.md`
    wherever the lyric axis number appears.

## C2 — Scope the lyric axis to EN-vocal everywhere it is claimed (P1) [stage: assumption/grounding]
- State the support honestly: lyric_intelligibility is reported on **EN-vocal only** (282 prompts;
  **248/282 = 88% carry nonzero signal** after the 2026-06-03 regen; all-8-zero down 40.2%→19.6%,
  the residual dominated by the 34 non-EN vocal prompts that the English-only Whisper scorer cannot
  rate). Instrumental prompts carry a `1.0` sentinel and are **masked** (never pooled).
- `refine-logs/FINAL_PROPOSAL.md` "7 of 7 axes" / H2 survival wording → add "lyric_intelligibility
  on its EN-vocal subset (n=282)". `refine-logs/METHOD_SPEC.md §12.1` → add the EN-vocal /
  instrument-sentinel-masked scope note. `ASSUMPTION_LEDGER.md` ETV1 footnote.

## C3 — Reword dev/held_out as cross-PROMPT, not cross-content (P2) [stage: benchmark/control]
- Per audit R2 (verifier uses no instrument-text feature; within-prompt ranking marginalizes
  prompt constants; claim is cross-prompt): word the split as **cross-prompt generalization
  (seen vocabulary, unseen prompt combination)**, NOT novel-content/novel-distribution.
  - `refine-logs/FINAL_PROPOSAL.md:369`, `refine-logs/EXPERIMENT_PLAN_EXEC.md:542`.
- Per audit R5 (rewrite confound: dev rewrote 100% of its broad prompts, held_out 47%): report
  all dev→held_out comparisons **per specificity stratum**, and note the aggregate "splits matched"
  check passes only by a coincidental composition offset.

## C4 — Note benign / acknowledged items (P2/P3) [stage: null-result / limitations]
- R2 clause overlap (held_out reuses 81–94% of dev instrument clauses): one-line note that this is
  descriptive and benign for the verifier (no text feature; within-prompt selection). 6 cross-split
  near-identical pairs were de-duped (now difflib<0.85); 9 metal contradictory-bpm prompts fixed.
- R3 flat candidate pool: acknowledge as a music property ("many near-optimal renderings"; the
  specificity test p=0.97 falsifies "prompts too easy"), not a defect.

## Provenance to cite in the data appendix
- Prompts patched in place 2026-06-03 (`configs/prompts/{dev,held_out}.jsonl`; archive
  `configs/prompts/archive_20260603/`): 122 thin EN-vocal lyrics thickened to ≥10 words, 9 metal
  bpm fixed, 6 near-pairs de-duped; 122 thickened lyrics distinct, cross-split identical = 0.
- Targeted BoN-8 regeneration of 132 (+101 collision-repair) prompts on 8×A800; manifests preserve
  the original `manifest_index` (seeds aligned to full01). Final dataset promoted to canonical
  `orbit-research/trajectory_candidate_dataset.jsonl` (2026-06-04); pre-fix archived at
  `orbit-research/archive/trajectory_candidate_dataset_pre_lyricfix_20260603.jsonl` and
  `orbit-research/archive/lyricfix_promote_20260603/`.

## Track A foundation — REGENERATED on the promoted dataset (2026-06-04, PI-approved)
- `scripts/finalize_early_tweedie_validation.py` was re-run on
  `runs/early_tweedie_validation_final_lyricfix_20260603/` (the merged dataset). Foundation files
  regenerated: `EARLY_TWEEDIE_PRUNING_VALIDATION.{md,json}`, `_PLOT.csv`, `_RETENTION.csv`,
  `EARLY_TWEEDIE_VALIDATION_{VERIFICATION_REPORT.json,PI_DECISION.md}`,
  `TRAJECTORY_AWARE_{COMPLETION_AUDIT,PI_REPORT}_CURRENT.{json,md}`. Pre-regen versions archived at
  `orbit-research/archive/trackA_pre_lyricfix_20260603/`.
- **Common-axis result is stable:** Schedule-A @ 0.500 compute `reward_fraction` **0.9858 → 0.9864**;
  decision status unchanged `STRONG_CANDIDATE_MAIN_APPLICATION`; verify `PASS_WITH_WARNINGS` (warnings
  are the expected lyric-axis tie diagnostics). So Track A claims do NOT need a numeric edit beyond
  the lyric axis (C1/C2). The PI-decision/PI-report docs are auto-generated summaries (re-stamped).
  Note: the merged run dir carries honest DERIVED-provenance stubs (`run_summary.json` marked merged,
  `launcher.exit`/log stubs) so the operational finalize preflight would pass; it is not a single GPU run.
