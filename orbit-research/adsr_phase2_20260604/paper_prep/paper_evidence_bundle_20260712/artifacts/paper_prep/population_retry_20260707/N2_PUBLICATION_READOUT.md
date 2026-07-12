# N2 Population Retry Publication Read-Out

Generated: 2026-07-07

Pre-registration: `paper_prep/POPULATION_RETRY_PREREG_20260707.md`

Audit status: PASS. Final audit reports 16,384 rows, 128 prompts, 128 seeds
per prompt, 0 parse errors, 0 missing required rows, 0 duplicate
`(prompt_id, seed_idx)` keys, 0 generation errors, 0 near-silent rows, and
0 missing FLACs.

## Regime Counts

| Regime | Prompts | Fraction |
|---|---:|---:|
| `easy_ge_1_in_2` | 67 | 0.523438 |
| `low_1_in_16_to_1_in_4` | 23 | 0.179688 |
| `rare_le_1_in_16` | 5 | 0.039062 |
| `seed_recoverable_1_in_4_to_1_in_2` | 33 | 0.257812 |

## Strata

- Instrumental: 47 prompts,
  mean clean rate 0.761137.
- Vocal: 81 prompts,
  mean clean rate 0.401331.

## Interpretation

The selected held-out retry map separates retry-recoverable prompts from rare
regime prompts. In this selected sample, 67
prompts were easy at >=1 clean in 2 tries, 33
were seed-recoverable at 1 in 4 to 1 in 2, 23
were low but not rare, and 5 were rare
at <=1 clean in 16 tries.

Population caveat: these 128 prompts were deterministically selected and
stratified by baseline violation-count bins from the held-out set. Treat the
rates as selected/difficult held-out rates, not generic population estimates,
unless a separate sampling argument is added.

Figure-ready CSV: `paper_prep/population_retry_20260707/n2_regime_figure_data.csv`
Prompt-level CSV: `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`
