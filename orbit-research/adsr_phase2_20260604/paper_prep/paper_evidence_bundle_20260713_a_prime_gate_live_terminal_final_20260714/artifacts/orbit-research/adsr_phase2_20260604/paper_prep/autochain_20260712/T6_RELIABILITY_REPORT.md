# T6 Reliability Report

`RELIABILITY_STATUS = PASS`

- Export/admin exact ID match: 201/201.
- Provenance: `pi:Richard`.
- Required answer blanks: 0.
- Optional confidence annotations missing: 181/201.
- Staged reveal: `PASS_UI_INVARIANT_PLUS_REVEAL_SEQUENCE`.
- Export limitation: the UI does not export Label-A/B answer timestamps; order is
  verified through the fail-closed UI state machine and each row's reveal event.

| Construct | Exact | Agreement | Cohen's kappa |
|---|---:|---:|---:|
| Label A | 20/20 | 1.000000 | 1.000000 |
| Label B | 20/20 | 1.000000 | 1.000000 |

Satisfied-to-violated or violated-to-satisfied reversals: 0/20.

Reliability was computed and written before train or held-out labels were
joined to instrument scores.
