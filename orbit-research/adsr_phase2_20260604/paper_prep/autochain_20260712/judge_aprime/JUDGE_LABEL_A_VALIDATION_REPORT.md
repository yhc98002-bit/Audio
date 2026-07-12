# Disjoint T6 Label-A Judge Validation

`JUDGE_VALIDATION_STATUS = BLOCKED_CLASS_COUNT_TOPUP_REQUIRED`

The judge prompt/model were frozen before this evaluation. T1/T2 are tuning-only; the fresh T6 evaluation media are SHA-256-disjoint from them.

| Metric | Point | One-sided 95% LCB | Frozen minimum | Met |
|---|---:|---:|---:|---:|
| balanced_accuracy | 0.947982 | 0.900360 | 0.80 | `true` |
| sensitivity | 0.991421 | 0.975793 | 0.75 | `true` |
| specificity | 0.904543 | 0.813256 | 0.75 | `true` |

- Decided PI positives/negatives: 149/27 (required >=30/>=50).
- Judge abstention: 0.000000 (required <=0.10).
- All available t1+t2+t6 PI gold contains only 43 Label-A negatives, so the frozen negative class count cannot pass without new human gold.
- No stratified-500 calls were launched and no A-prime gate changed.
