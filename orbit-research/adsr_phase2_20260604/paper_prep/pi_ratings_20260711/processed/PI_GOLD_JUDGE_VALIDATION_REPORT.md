# PI-Gold Self-Hosted Judge Validation

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`

## Result

The amendment-compliant `pi:Richard` labels replace the previous CXY-only
diagnostic basis. Media hashes are disjoint between the balanced smoke and the
held-out split, and the audit independently reconciled every manifest row,
audio SHA-256, raw clip/call key, parser output, majority vote, and summary.

| Metric | Balanced smoke | Held-out PI gold |
|---|---:|---:|
| Clips | 10 | 105 |
| Positive / negative | 5 / 5 | 98 / 7 |
| Calls | 30 | 315 |
| Sensitivity | 1.000000 | 1.000000 |
| Specificity | 0.600000 | 0.714286 |
| Balanced accuracy | 0.800000 | 0.857143 |
| MCC | 0.654654 | 0.836660 |
| Abstention rate | 0.000000 | 0.000000 |

## Status Decision

The held-out diagnostic is strong, but the balanced smoke is 8/10 rather than
the earlier 10/10 engineering target. The signed amendment and standing brief
do not define a numeric automatic-judge promotion threshold, and gates never
auto-pass. `JUDGE_VALIDATION_STATUS` therefore remains `PI_BLOCKED` pending a
PI decision on a promotion rule. The stratified-500 A-prime judge track was not
launched, and no A-prime status changed.

## Evidence

- Smoke manifest: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_SMOKE.csv`
- Held-out manifest: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_HELDOUT.csv`
- Smoke raw ledger: `paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_smoke_20260711.jsonl`
- Held-out raw ledger: `paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_heldout_20260711.jsonl`
- Audit JSON: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_AUDIT.json`
- Audit script: `paper_prep/scripts/audit_pi_gold_judge_20260711.py`
