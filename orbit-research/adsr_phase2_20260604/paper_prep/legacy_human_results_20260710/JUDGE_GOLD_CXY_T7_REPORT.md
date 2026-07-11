# Legacy CXY Held-Out T7 Judge Audit

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`

## Scope

The self-hosted `qwen3-omni-judge` was evaluated with deterministic decoding and
three calls per clip against the held-out portion of the original-media CXY
legacy gold. The audit independently reconciled the manifest, every raw
clip/call key, audio SHA-256 values, parser outputs, majority votes, and summary
metrics. Embedded audio payloads were not retained in the raw ledger.

| Metric | Result |
|---|---:|
| Held-out clips | 37 |
| Positive clips | 34 |
| Negative clips | 3 |
| Raw calls | 111 |
| Decided clips | 37 |
| Abstentions | 0 |
| Sensitivity | 1.000000 |
| Specificity | 1.000000 |
| Balanced accuracy | 1.000000 |
| MCC | 1.000000 |
| Abstention rate | 0.000000 |

## Status Decision

This is a strong provisional diagnostic, not a validated scaling-instrument
gate. The gold is from one rater, predates the signed amendment, and its held-out
negative class is small. No frozen numeric T7 promotion threshold was specified,
and inter-rater agreement has not been measured. Therefore gates never
auto-pass and `JUDGE_VALIDATION_STATUS` remains `PI_BLOCKED` pending PI or a
second-rater overlap sufficient to report kappa and repeat the held-out audit.

No A-prime or B-prime status changed, and no scale calls were launched.

## Evidence

- Manifest: `paper_prep/legacy_human_results_20260710/JUDGE_GOLD_CXY_HELDOUT_MANIFEST.csv`
- Append-only raw ledger: `paper_prep/judge_raw/selfhost_qwen3_omni_legacy_cxy_heldout_20260710.jsonl`
- Runner summary: `paper_prep/legacy_human_results_20260710/JUDGE_GOLD_CXY_T7_SUMMARY.json`
- Audit script: `paper_prep/scripts/audit_legacy_cxy_t7_20260710.py`
