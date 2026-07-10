# Batch-3 Results V2

`BATCH3_REANALYSIS_STATUS = PASS`

## Frozen Endpoints

- Primary restart2+ delta: 0.429880, 95% CI [0.274549, 0.578490], n=30, pass=true.
- Secondary full-trajectory delta: 0.382907, one-sided alpha=.025 lower=0.246480, pass=true.
- Secondary two-sided 97.5% sensitivity: [0.226782, 0.540690], pass=true.
- Mechanical verdict: `SUPPORTED_TAIL_RESCUE`.

Frozen sentence: "Secondary (E2a, Bonferroni alpha=0.025): same construction over ALL completions per trajectory."

The primary reading is one-sided because the frozen rule asks whether a lower
bound exceeds zero. The stricter two-sided reading is shown as sensitivity;
neither reading changes the gate.

## Integrity

- 16 ledgers parsed line-by-line with no invalid JSON.
- 22,825 unique attempt rows and 3,648 unique unit-selection rows.
- Expected 256-prompt x arm x replicate cells, including exactly 32 rep-2
  tail cells for arms 4 and 6, were asserted.
- Every recorded selection matched the fail-closed recomputation.
- Arm 5 was reconstructed as the frozen lyric-defer selection over arm-4
  candidates without adding generation cost.
- Population weights are joined by prompt ID. Weighted and unweighted selected
  summaries are both retained in the JSON.
