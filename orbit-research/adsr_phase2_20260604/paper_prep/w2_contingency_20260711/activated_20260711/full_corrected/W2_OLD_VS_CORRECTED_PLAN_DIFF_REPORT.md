# W2 Old-Versus-Corrected Headline Diff

`W2_ADOPTION_STATUS = REVIEW_REQUIRED_NO_AUTOMATIC_PLAN_CHANGE`

This report is generated only after a corrected instrument is selected. It does not relabel frozen evidence or change any gate/status line by itself.

| Metric | Cohort | Condition | N | Old | Corrected | Delta |
|---|---|---|---:|---:|---:|---:|
| clean_rate | n2_population_retry | none | 16384 | 0.533447265625 | 0.77886962890625 | 0.24542236328125 |
| clean_rate | stage3_intervention | instr_both | 960 | 0.3770833333333333 | 0.078125 | -0.2989583333333333 |
| clean_rate | stage3_intervention | instr_sampler | 960 | 0.34479166666666666 | 0.20729166666666668 | -0.13749999999999998 |
| clean_rate | stage3_intervention | instr_text | 960 | 0.3260416666666667 | 0.17708333333333334 | -0.14895833333333333 |
| clean_rate | stage3_intervention | vocal_both | 1088 | 0.7794117647058824 | 0.9926470588235294 | 0.21323529411764708 |
| clean_rate | stage3_intervention | vocal_guidance | 1088 | 0.78125 | 0.9898897058823529 | 0.20863970588235292 |
| clean_rate | stage3_intervention | vocal_hints | 1088 | 0.09375 | 0.6553308823529411 | 0.5615808823529411 |
| n2_clean_rate_by_request | n2_population_retry | instrumental | 6016 | 0.7611369680851063 | 0.6067154255319149 | -0.1544215425531914 |
| n2_clean_rate_by_request | n2_population_retry | vocal | 10368 | 0.40133101851851855 | 0.8787615740740741 | 0.4774305555555555 |
| n2_regime_prompt_count | n2_population_retry | easy_ge_1_in_2 | 128 | 67 | 110 | 43 |
| n2_regime_prompt_count | n2_population_retry | seed_recoverable_1_in_4_to_1_in_2 | 128 | 33 | 9 | -24 |
| n2_regime_prompt_count | n2_population_retry | low_1_in_16_to_1_in_4 | 128 | 23 | 9 | -14 |
| n2_regime_prompt_count | n2_population_retry | rare_le_1_in_16 | 128 | 5 | 0 | -5 |
