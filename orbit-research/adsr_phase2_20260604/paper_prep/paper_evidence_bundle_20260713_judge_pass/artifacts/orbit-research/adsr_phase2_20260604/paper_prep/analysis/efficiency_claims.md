# Efficiency Claims

Generated: 2026-07-07

Sources:

- `paper_prep/execution_20260707/T21_efficiency_metrics.json`
- `paper_prep/execution_20260707/T21_efficiency_metrics.csv`
- `paper_prep/stage3_intervention_20260707/full64_final_summary.json`
- `paper_prep/population_retry_20260707/full128_regime_readout.json`

## Ready Numbers

- Baseline vocal-hard clean rate: mean 0.088120, median 0.064453.
- Baseline instrumental-hard clean rate: mean 0.359115, median 0.361328.
- Vocal intervention lift from existing V3 paired intervention: mean delta +0.685777, 17/17 prompts improved.
- Instrumental strong intervention from existing paired intervention: mean delta +0.005469, 9/15 prompts improved.
- Stage 3 controlled decomposition: `vocal_guidance` 0.781250, `vocal_both` 0.779412, `vocal_hints` 0.093750.
- N2 selected held-out mean clean rate: 0.533447.

## Figure Outputs

- Data: `paper_prep/figures/fig2_regime_data.csv`
- PNG: `paper_prep/figures/fig2_regime_plot.png`
- PDF: `paper_prep/figures/fig2_regime_plot.pdf`
- Expected draws: `paper_prep/analysis/expected_draws_metrics.csv`

## Wording Constraint

These are difficult-test-set rates unless explicitly tied to the selected N2
held-out sample. Do not describe them as generic population rates. Use
"rare / impractical to retry" rather than zero-success wording. Do not make
absolute no-loss claims.
