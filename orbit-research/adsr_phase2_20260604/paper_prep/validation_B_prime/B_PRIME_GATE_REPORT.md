# B-prime Gate Report

Generated: 2026-07-07

B_PRIME_STATUS = FALLBACK_READY

Important: Qwen smoke v2 did not pass. These rows are fallback evidence only
unless a scientifically acceptable replacement validation is approved.

## Inputs / Outputs

- Manifest: `paper_prep/validation_B_prime/B_PRIME_MANIFEST.csv`
- Raw responses: `paper_prep/validation_B_prime/B_PRIME_RAW_RESPONSES.jsonl`
- Order-bias report: `paper_prep/validation_B_prime/B_PRIME_ORDER_BIAS_REPORT.md`

## Coverage

- Pair rows: 80
- Expected ordered calls: 160
- Completed ordered calls: 160
- Q1 decided calls: 77
- Q1 ties: 83
- Q1 refusals/unparsed: 0

## Gate Shape

- Method preferred among decided Q1 calls: 50/77 = 0.649351; frozen criterion >= 0.40.
- Exact one-sided binomial P[X <= observed | n, p=0.5]: 0.997065; criterion not significantly below 50% at 5%.

By contrast:

- `arm6_vs_arm1`: method=23, baseline=13
- `arm6_vs_arm4`: method=27, baseline=14

## Interpretation

Do not claim B-prime passed unless `B_PRIME_STATUS = PASS`. This report can
support reduced wording only after the failed-smoke judge limitation is stated.
Forbidden wording remains: "proved no loss" and unqualified "no quality degradation".
