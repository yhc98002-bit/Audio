# Publication Statistics v2

PUBLICATION_STATS_V2_STATUS = PASS

## Frozen Estimands

Primary deployment success is `S_N = mean_prompt[1-(1-p_hat_i)^N]`
for N in {4, 5, 8, 16}. The legacy `1/mean(p)` quantity is retired.
Two-stage cluster-bootstrap intervals use 10,000 replicates, resampling
prompts within vocal/instrumental and selection-bin strata and then seeds
within prompts. N2 source-population cell weights are reapplied in every
replicate. Prompt-only intervals are provided as robustness checks.

## Integrity Checks

- ATLAS baseline: 32 prompts x 512 seeds.
- ATLAS V3: 17 prompts x 128 seeds; I-strong: 15 x 128.
- Stage 3: 6,144 successful rows across the six frozen conditions.
- N2: 128 prompts x 128 seeds; sampling cells reconstructed from all 256 held-out prompts.
- Duplicate keys and failed rows are fatal; none were accepted.

## N2 Regimes

Frozen plug-in counts: `{'easy_ge_1_in_2': 67, 'low_1_in_16_to_1_in_4': 23, 'rare_le_1_in_16': 5, 'seed_recoverable_1_in_4_to_1_in_2': 33}`. Bootstrap membership is
uncertain (<0.80 maximum membership probability) for 25/128 prompts.
The primary Figure 2 object is the ECDF plus per-prompt Wilson forest, not
a pooled seed-rate bar chart.

## Secondary Draw Metrics

There are 2 zero-success prompt-condition cells. Each is
reported as `0/m` with a one-sided 95% upper confidence bound on p. The
package never converts those observations into an 'expected draws > m' claim.

## SA3 Threshold Sensitivity

SA3 instrumental/vocal median Demucs ratios are 0.000002
and 0.000022; their midpoint is 0.000012.
This is model-specific sensitivity analysis. It is not a calibrated human threshold,
and all pooled SA3 seed rates are labeled descriptive-only.

## Wording Constraints

- These are selected/difficult-test-set rates, not generic population rates.
- Use 'rare / impractical to retry', never 'impossible'.
- Do not write `1/mean(p)` as expected draws.
- Do not infer human label validity from the automatic detector.

## Artifacts

- `paper_prep/analysis_v2/deployment_success_metrics.csv`
- `paper_prep/analysis_v2/deployment_success_paired_deltas.csv`
- `paper_prep/analysis_v2/prompt_secondary_draw_metrics.csv`
- `paper_prep/analysis_v2/n2_regime_membership_bootstrap.csv`
- `paper_prep/analysis_v2/n2_regime_bin_edge_sensitivity.csv`
- `paper_prep/analysis_v2/atlas_n2_replication_scatter.csv`
- `paper_prep/analysis_v2/sa3_threshold_sensitivity.csv`
- `paper_prep/figures_v2/fig2_retry_regime_ecdf_forest.{png,pdf}`
- `paper_prep/figures_v2/atlas_n2_replication_scatter.{png,pdf}`
