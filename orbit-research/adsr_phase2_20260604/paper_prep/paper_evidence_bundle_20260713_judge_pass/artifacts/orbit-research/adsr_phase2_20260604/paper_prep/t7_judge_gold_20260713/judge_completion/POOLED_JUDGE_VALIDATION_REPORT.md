# Pooled Disjoint-Gold Label-A Judge Validation

`JUDGE_VALIDATION_STATUS = PASS`

The held-out pool contains 149 human `yes` positives from the existing disjoint T6 set and 67 human `no` negatives: 27 existing plus all 40 T7 rows. T7 is intentionally all-negative; sensitivity therefore comes from pooled existing positives and specificity from all pooled negatives. No evaluation row was used to tune the judge.

| Metric | Point | One-sided 95% LCB | Frozen minimum | Met |
|---|---:|---:|---:|---:|
| balanced_accuracy | 0.950705 | 0.941113 | 0.80 | `true` |
| sensitivity | 0.991421 | 0.982743 | 0.75 | `true` |
| specificity | 0.909989 | 0.893122 | 0.75 | `true` |

- MCC: 0.946184.
- Abstention: 0/216 = 0.000000; maximum 0.10.
- Class-count checks: positives 149/30; negatives 67/50.
- Pooled gold SHA-256: `2b2008a63ff4a9e95c20384062baa510575c292bfa3809fc33abac128d380594`.
