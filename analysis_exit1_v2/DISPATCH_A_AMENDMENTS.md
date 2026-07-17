# Dispatch A Amendments

Appended 2026-07-16. Authority: Claude, final-say. These amendments supersede
conflicting parts of the earlier Dispatch A evaluator implementation.

## A1

If a prior evaluator-fix session produced outputs under `analysis_exit1/`, treat them as input evidence and supersede under `analysis_exit1_v2/`; delete nothing.

Implementation: `analysis_exit1/` is read-only evidence. Its evaluator artifacts are checksum-recorded in `analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`; all amended outputs are written under `analysis_exit1_v2/`.

## A2

Panel A must state decided positive/negative counts prominently; if PI-only decided negatives < 30, print `POWER_LIMITED` beside every Panel-A metric.

Implementation: `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md` makes PI-only held-out gold Panel A, prints both class counts, and applies the marker to every sensitivity, specificity, balanced-accuracy, and MCC cell when the frozen count rule fires.

## A3

The canonical-instrument parse must quote the exact line from `T6_PROMOTION_REPORT.md` ("Selected family: `or`") and record the SHA-256 of `T6_PROMOTION_RESULT.json`.

Implementation: the v2 parser fails closed on report/JSON disagreement. The exact report line and result SHA-256 are recorded in both the v2 comparison report and its machine-readable audit.
