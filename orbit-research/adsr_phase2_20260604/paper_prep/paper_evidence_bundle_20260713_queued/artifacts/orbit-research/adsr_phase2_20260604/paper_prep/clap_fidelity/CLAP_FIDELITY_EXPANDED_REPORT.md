# CLAP Fidelity Expanded Report

Generated: 2026-07-07

Inputs:

- `paper_prep/clap_fidelity/CLAP_FIDELITY_RESULTS.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_PROMPT_PAIRED.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_MANIFEST.csv`
- `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`

Outputs:

- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_RESULTS.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_PROMPT_ROWS.csv`

## Result

CLAP_STATUS = REDUCED

Overall paired prompt delta, arm6 minus arm1:

- Prompts: 256
- Mean delta: 0.005996
- Median delta: 0.002001
- Bootstrap 95% CI: [-0.003375, 0.015661]

## Direction / Regime Breakout

| Group | Value | Prompts | Mean delta | Bootstrap 95% CI | Status |
|---|---|---:|---:|---:|---|
| overall | all | 256 | 0.005996 | [-0.003375, 0.015661] | ambiguous_ci_crosses_zero |
| direction | instrumental_leak | 97 | 0.004918 | [-0.005218, 0.015662] | ambiguous_ci_crosses_zero |
| direction | vocal_miss | 159 | 0.006654 | [-0.007347, 0.020539] | ambiguous_ci_crosses_zero |
| n2_regime | easy_ge_1_in_2 | 67 | 0.004740 | [-0.011654, 0.021066] | ambiguous_ci_crosses_zero |
| n2_regime | low_1_in_16_to_1_in_4 | 23 | 0.007684 | [-0.032346, 0.052911] | ambiguous_ci_crosses_zero |
| n2_regime | no_n2_regime | 128 | 0.006586 | [-0.006461, 0.019792] | ambiguous_ci_crosses_zero |
| n2_regime | rare_le_1_in_16 | 5 | -0.037730 | [-0.102102, 0.026642] | ambiguous_ci_crosses_zero |
| n2_regime | seed_recoverable_1_in_4_to_1_in_2 | 33 | 0.011708 | [-0.015245, 0.040333] | ambiguous_ci_crosses_zero |
| rare_basin | false | 251 | 0.006867 | [-0.002659, 0.016349] | ambiguous_ci_crosses_zero |
| rare_basin | true | 5 | -0.037730 | [-0.102102, 0.026642] | ambiguous_ci_crosses_zero |

## Paper-Safe Wording

CLAP prompt-fidelity is non-negative on average, but the bootstrap confidence interval crosses zero; claim only that no clear CLAP drop was detected.

Do not claim semantic preservation is proven. Do not claim quality preservation from CLAP alone.
