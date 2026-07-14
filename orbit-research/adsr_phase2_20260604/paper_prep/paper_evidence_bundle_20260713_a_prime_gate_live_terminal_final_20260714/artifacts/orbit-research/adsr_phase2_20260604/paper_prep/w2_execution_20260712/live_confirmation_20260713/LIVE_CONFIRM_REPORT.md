# W2 Live Confirmation Report

`LIVE_CONFIRM_RESULT = CRITERIA_NOT_ALL_MET`

No PASS is issued automatically. The table and frozen condition booleans are presented for PI call.

| Policy | n | Final Label-B violation | No completed output | Mean actual steps | Nominal steps |
|---|---:|---:|---:|---:|---:|
| `no_probe_reseed` | 128 | 0.265625 | 0.000000 | 60.000 | 60.000 |
| `corrected_probe_abort_reseed` | 128 | 0.492188 | 0.390625 | 38.906 | 60.000 |
| `always_direction_condition` | 128 | 0.164062 | 0.000000 | 60.000 | 60.000 |
| `corrected_probe_direction_action` | 128 | 0.312500 | 0.000000 | 45.938 | 60.000 |

## Frozen Conditions

- `primary_reduction_lcb_positive = false`
- `policy4_noninferior_to_policy3 = false`
- `nominal_compute_within_one_percent = true`
- `vocal_sanity_excess_within_005 = true`
- `runtime_cap_met = true`

## Prompt-Cluster Bootstrap

- Policy 4 vs policy 1 violation-reduction one-sided 95% LCB: -0.109375.
- Policy 4 vs policy 3 excess-violation one-sided 95% UCB: 0.203125.
- Deterministic bootstrap: 20000 prompt-cluster resamples, seed `2026071406`.

## Audit

- Manifest/unit selections: 512/512.
- Raw/deduplicated ledger rows: 1536/1536.
- Recovered orphan rows: 4.
- Missing/extra unit IDs: 0/0.
- A missing selected output is conservatively counted as a final violation.
- Results are instrument-scoped to the promoted T6 Label-B instrument.
