# Old vs v2 Publication Number Diff

PUBLICATION_STATS_V2_STATUS = PASS

Shared per-try quantities are compared below. The D1 deployment-success
estimand has no old counterpart; retiring `1/mean(p)` is an intentional
estimand correction, not a numerical discrepancy.

| Metric | Old | v2 | Difference | Escalate |
|---|---:|---:|---:|---|
| baseline_vocal_prompt_mean | 0.088120000 | 0.088120404 | +0.000000404 | no |
| baseline_instrumental_prompt_mean | 0.359115000 | 0.359114583 | -0.000000417 | no |
| V3_prompt_paired_delta | 0.685777000 | 0.685776654 | -0.000000346 | no |
| I_strong_prompt_paired_delta | 0.005469000 | 0.005468750 | -0.000000250 | no |
| stage3_instr_both_pooled_rate | 0.377083333 | 0.377083333 | +0.000000000 | no |
| stage3_instr_sampler_pooled_rate | 0.344791667 | 0.344791667 | +0.000000000 | no |
| stage3_instr_text_pooled_rate | 0.326041667 | 0.326041667 | +0.000000000 | no |
| stage3_vocal_both_pooled_rate | 0.779411765 | 0.779411765 | +0.000000000 | no |
| stage3_vocal_guidance_pooled_rate | 0.781250000 | 0.781250000 | +0.000000000 | no |
| stage3_vocal_hints_pooled_rate | 0.093750000 | 0.093750000 | +0.000000000 | no |
| N2_pooled_seed_rate_descriptive_only | 0.533447266 | 0.533447266 | +0.000000000 | no |

No old figure or old metrics file was modified.
Pooled seed-level rates are descriptive only; prompt-level estimands are primary.
