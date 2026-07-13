# T7 Continuation

Place the exported JSON at:

`paper_prep/pi_ratings_20260713/t7_judge_gold_negatives.json`

Then ingest the frozen count-only top-up:

```bash
python paper_prep/scripts/ingest_t7_judge_gold_20260713.py
```

Only when `T7_RATINGS_STATUS = PASS_TOPUP_READY`, relaunch the frozen
self-hosted judge and run three deterministic calls on
`paper_prep/t7_judge_gold_20260713/ratings_ingest/T7_TOPUP_GOLD_MANIFEST.csv`.
Combine those responses with the existing disjoint T6 judge ledger, evaluate
the frozen metric/LCB/abstention gate, and proceed to the stratified 500 only on
PASS. The 190 human core remains `pi:Richard`; the 500 rows require the exact
validated-judge source, gold-set hash, metrics, and raw-ledger hash before the
instrument merge can run.
