# T6 Corrected-Instrument Promotion Report

`CORRECTED_INSTRUMENT_STATUS = PROMOTED`

- Selected family: `or`.
- Demucs threshold: `0.03161777090281248`.
- PANNs threshold: `0.04403413645923138`.
- Candidate count searched on train only: 7566.
- Amendment signatures: `SIGNED_BY_BOTH_PIS` (recorded after the mechanical
  promotion evaluation; publication adoption remains separately gated).
- PLAN/CLAIMS changed: `false`.

## Held-Out Evaluation

Held-out labels were exposed once after reliability and train selection. Decided positives: 31; decided negatives: 67; abstentions: 2.

| Metric | Design-weighted point | One-sided 95% LCB | Unweighted point | Unweighted LCB | Required point / LCB |
|---|---:|---:|---:|---:|---:|
| `balanced_accuracy` | 0.987308 | 0.972272 | 0.940299 | 0.920290 | 0.80 |
| `sensitivity` | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.75 |
| `specificity` | 0.974616 | 0.944544 | 0.880597 | 0.840580 | 0.75 |

## Mechanical Conditions

- `decided_positives_at_least_30`: `true`.
- `decided_negatives_at_least_50`: `true`.
- `reliability`: `true`.
- `balanced_accuracy_point_at_least_0.8`: `true`.
- `balanced_accuracy_lcb_at_least_0.8`: `true`.
- `sensitivity_point_at_least_0.75`: `true`.
- `sensitivity_lcb_at_least_0.75`: `true`.
- `specificity_point_at_least_0.75`: `true`.
- `specificity_lcb_at_least_0.75`: `true`.

## Transport Audit

- Rows: 20.
- Overall balanced-accuracy delta versus held-out: -0.023778.
- Any source-specific correction flag: `false`.
- N2: BA 0.952627; delta -0.034681; flag `false`.
- Stage3: BA 1.000000; delta 0.012692; flag `false`.
- Batch3_keep: BA 1.000000; delta 0.012692; flag `false`.

This result is mechanical. Publication adoption and any direct PLAN/CLAIMS
update remain blocked until both W2 adoption signatures are recorded.
