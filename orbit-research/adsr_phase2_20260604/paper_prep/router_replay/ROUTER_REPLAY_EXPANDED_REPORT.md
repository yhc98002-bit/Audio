# Router Replay Expanded Report

Generated: 2026-07-07

Inputs:

- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/bon256_w*.jsonl`
- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/v3_vocal_w*.jsonl`
- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/istrong_instr_w*.jsonl`
- `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`

Outputs:

- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_RESULTS.csv`
- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv`

## Expanded Variants

The replay tested fixed policies, rare-threshold sweeps, direction-aware rules,
N2-regime-prior rules, and an outcome-informed oracle upper bound. Outcome-informed
rows are diagnostic only and are not a deployable router claim.

## Budget 8 Top Policies

| Policy | Class | Expected clean / prompt | Final violation rate | Clean yield / draw |
|---|---|---:|---:|---:|
| direction_aware_gain_prior | oracle_or_outcome_informed | 0.986547 | 0.013453 | 0.123318 |
| oracle_best_of_reseed_or_recondition | oracle_or_outcome_informed | 0.986547 | 0.013453 | 0.123318 |
| threshold_le_0.25000000 | threshold_sweep | 0.977290 | 0.022710 | 0.122161 |
| threshold_le_0.50000000 | threshold_sweep | 0.974558 | 0.025442 | 0.121820 |
| always_recondition | fixed | 0.974455 | 0.025545 | 0.121807 |
| threshold_le_0.12500000 | threshold_sweep | 0.949612 | 0.050388 | 0.118701 |
| direction_aware_vocal_rare | exploratory_rule | 0.884302 | 0.115698 | 0.110538 |
| threshold_le_0.06250000 | threshold_sweep | 0.884302 | 0.115698 | 0.110538 |
| n2_low_or_rare_prior | exploratory_rule | 0.873286 | 0.126714 | 0.109161 |
| n2_rare_prior | exploratory_rule | 0.806533 | 0.193467 | 0.100817 |

## Fixed Baselines at Budget 8

- Always reseed: 0.694678
- Always recondition: 0.974455
- Oracle best of reseed/recondition: 0.986547
- Best non-oracle policy: `threshold_le_0.25000000` = 0.977290
- Best non-oracle improvement over always-recondition: 0.002835

## Conclusion

Router claim: **reduced to negative/offline replay result**.

The simple and expanded non-oracle routers do not establish a deployable router
advantage over the strongest fixed policy in this replay. The paper-safe use is
as a negative/reduced result: existing ledgers show that a naive rare-regime
router is insufficient, and live router confirmation is not justified without a
stronger policy or new evidence.
