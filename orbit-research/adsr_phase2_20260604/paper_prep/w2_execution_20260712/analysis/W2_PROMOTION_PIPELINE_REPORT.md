# W2 Promotion Pipeline

`PROMOTION_PIPELINE_STATUS = READY_BLOCKED_ON_RATINGS`

The mechanical pipeline is implemented in
`paper_prep/scripts/w2_promotion_pipeline_20260712.py`. It remains fail-closed
until `W2_AMENDMENT_20260712.md` records both PI signatures and a complete t6
rating CSV with PI/human provenance exists.

Implemented order:

1. require exact admin/rating ID equality and PI/human provenance;
2. evaluate all 20 hidden repeats before exposing training labels;
3. stop for clarification/rerating unless exact Label-B agreement is at least
   0.85 and satisfied-versus-violated reversals are at most 2/20;
4. tune only the six frozen instrument families on the 60 training rows;
5. require the frozen class-count top-up before any held-out metrics are
   exposed;
6. evaluate the held-out rows once with design weights and stratified,
   one-sided bootstrap lower bounds; and
7. emit `SENSITIVITY_ONLY` on any failed criterion. A mechanical PASS emits
   `AWAITING_DUAL_PI_PROMOTION_RECORD` and cannot modify `PLAN.md`.

Regression coverage proves that unvalidated judges cannot enter calibration,
reliability failure blocks held-out evaluation, class-count top-up occurs
before metrics are exposed, and a synthetic mechanical PASS has no PLAN side
effect. Real ratings have not been supplied, so no promotion result exists and
no corrected instrument has been promoted.
