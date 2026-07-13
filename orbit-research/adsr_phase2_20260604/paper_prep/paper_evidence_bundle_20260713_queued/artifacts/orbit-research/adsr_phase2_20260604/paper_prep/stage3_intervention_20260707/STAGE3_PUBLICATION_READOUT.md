# Stage 3 Publication Read-Out

Generated: 2026-07-07

Pre-registration: `paper_prep/STAGE3_INTERVENTION_PREREG_20260707.md`

Audit status: PASS. Final audit reports 6,144 rows, 0 parse errors, 0
missing required rows, 0 duplicate `(prompt_id, condition, seed_idx)` keys,
0 generation errors, 0 near-silent rows, and 0 missing FLACs.

## Pre-Registered Question

The frozen read-out asked which condition component drives the Claim-3 rescue
effect. The expected direction was at least one vocal-side component with a
large clean-rate gain and near-zero instrumental-side gains.

## Results

| Condition | Rows | Type-correct rate | Present rate |
|---|---:|---:|---:|
| `vocal_guidance` | 1088 | 0.781250 | 0.781250 |
| `vocal_hints` | 1088 | 0.093750 | 0.093750 |
| `vocal_both` | 1088 | 0.779412 | 0.779412 |
| `instr_text` | 960 | 0.326042 | 0.673958 |
| `instr_sampler` | 960 | 0.344792 | 0.655208 |
| `instr_both` | 960 | 0.377083 | 0.622917 |

## Interpretation

- Vocal guidance drives most of the gain: `vocal_guidance` and `vocal_both`
  are both about 0.78 clean/type-correct per try.
- Vocal hints alone are weak: `vocal_hints` is 0.093750, close to the hard
  vocal baseline rather than the guided conditions.
- Instrumental variants are close and weak/near-null: `instr_text`,
  `instr_sampler`, and `instr_both` range from 0.326042 to 0.377083.
- This supports a re-conditioning mechanism, especially for vocal-miss hard
  prompts. It does not establish a universal repair mechanism and should not
  be worded as proof of no quality cost or proof of zero retryability.

Figure-ready CSV: `paper_prep/stage3_intervention_20260707/stage3_condition_rates_figure_data.csv`
