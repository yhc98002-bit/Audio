# Vocal Threshold Migration Resolution

`VOCAL_THRESHOLD_GAP_AUDIT_STATUS = FAIL_7_ROWS`

The broad audit did **not** confirm the hoped-for zero-row result. It found
seven ledger rows with vocal-energy ratios in `[0.179, 0.1791)`. The failed
audit is retained in `VOCAL_THRESHOLD_GAP_AUDIT.{json,md}`; it is not being
silently converted to a pass.

## Impact Analysis

- One row is in the quarantined dirty-run ledger and duplicates the same
  prompt/seed in the clean ATLAS ledger.
- Six rows are in clean ATLAS, Stage 3, or N2 ledgers.
- All seven rows already store `present = 0`, exactly matching the canonical
  0.1791 threshold. Frozen ledgers and summaries therefore require no relabel.
- The three historical scripts that used 0.179 consume
  `vocal_presence_raw.jsonl`. Its 4,096 rows contain zero ratios in the gap, so
  centralizing those scripts at 0.1791 changes none of their source labels.
- The completed ATLAS, Stage 3, and N2 workers already used 0.1791 when the six
  clean gap rows were written.

## Resolution

Runtime and analysis code now imports `VOCAL_PRESENCE_THRESHOLD` from
`src/mprm/common/thresholds.py`. Frozen artifacts are not rewritten. The
broad-corpus exception remains visible because the literal claim "no candidate
ratio lies in the interval" would be false; the narrower migration claim is
supported: no historical source label changes, and all later gap rows were
already labeled under 0.1791.
