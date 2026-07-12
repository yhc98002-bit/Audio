# Recompute Assemble Input-Coupling Recovery

The first versioned `assemble` invocation failed closed with:

```text
ValueError: Batch-3 keep scoring incomplete: 0/1342
```

Cause: `MPRM_W2_ANALYSIS_OUT` correctly redirected new output tables, but the
same root also selected the already-complete Batch-3 input ledger directory.
The recovery output root was intentionally empty, so the completeness gate
stopped assembly. `--allow-incomplete` was not used.

Repair: `w2_recompute_suite_20260712.py` now separates
`MPRM_W2_BATCH3_SCORE_INPUT` from the output root. Its default remains the
original colocated behavior; the torch-2.5.1 rebuild explicitly reads the
frozen 1,342-row Batch-3 ledgers from the original analysis root and writes all
new tables to `analysis_torch251_recovery/`. A regression test verifies the two
roots remain distinct.

The zero-byte stdout file from the failed attempt is preserved as
`recompute_assemble_failed_missing_batch3_stdout.json`.
