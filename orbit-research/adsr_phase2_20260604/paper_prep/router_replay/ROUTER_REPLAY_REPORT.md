# Router Replay Report

Generated: 2026-07-07

Inputs:

- Baseline ledgers: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/bon256_w*.jsonl`
- Vocal re-conditioning ledgers: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/v3_vocal_w*.jsonl`
- Instrumental re-conditioning ledgers: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/istrong_instr_w*.jsonl`

Outputs:

- Results: `paper_prep/router_replay/ROUTER_REPLAY_RESULTS.csv`
- Prompt policies: `paper_prep/router_replay/ROUTER_REPLAY_PROMPT_POLICIES.csv`

## Replay Rule

Classify a prompt as rare-regime if its baseline clean rate is <= 1/16.
The router re-conditions rare-regime prompts and otherwise re-seeds. Fixed
baselines are always-reseed and always-recondition at the same draw budgets.

## Prompt Mix

- Prompts: 32
- Rare-regime prompts by replay rule: 8
- Non-rare prompts by replay rule: 24

## Equal-Compute Results

| Budget | Policy | Expected clean / prompt | Final violation rate | Clean yield / draw |
|---:|---|---:|---:|---:|
| 1 | `always_reseed` | 0.215149 | 0.784851 | 0.215149 |
| 1 | `always_recondition` | 0.582031 | 0.417969 | 0.582031 |
| 1 | `rare_router` | 0.394531 | 0.605469 | 0.394531 |
| 2 | `always_reseed` | 0.359033 | 0.640967 | 0.179516 |
| 2 | `always_recondition` | 0.769005 | 0.230995 | 0.384502 |
| 2 | `rare_router` | 0.575098 | 0.424902 | 0.287549 |
| 4 | `always_reseed` | 0.533095 | 0.466905 | 0.133274 |
| 4 | `always_recondition` | 0.903006 | 0.096994 | 0.225751 |
| 4 | `rare_router` | 0.749071 | 0.250929 | 0.187268 |
| 8 | `always_reseed` | 0.694678 | 0.305322 | 0.086835 |
| 8 | `always_recondition` | 0.974455 | 0.025545 | 0.121807 |
| 8 | `rare_router` | 0.884302 | 0.115698 | 0.110538 |

## Recommendation

GO/NO-GO for live router confirmation: **NO-GO**.

At budget 8, rare-router expected clean/prompt is
0.884302 versus
0.694678 for always-reseed and
0.974455 for always-recondition.

Wording constraint: this is a counterfactual replay from existing ledgers, not
a live router confirmation. It can motivate a live confirmation run, but it
does not replace one.
