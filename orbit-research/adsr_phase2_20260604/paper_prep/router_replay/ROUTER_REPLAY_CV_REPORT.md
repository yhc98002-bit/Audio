# Router Replay Cross-Validation Report

Generated: 2026-07-08

ROUTER_CV_STATUS = COMPLETE

ROUTER_FINAL_CLAIM = REDUCED

## Inputs

- Prompt policy rows: `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv`
- Script: `paper_prep/scripts/router_replay_cv.py`

## Outputs

- Fold selections: `paper_prep/router_replay/ROUTER_REPLAY_CV_FOLDS.csv`
- Cross-validated results: `paper_prep/router_replay/ROUTER_REPLAY_CV_RESULTS.csv`

## Method

Prompts were split into five deterministic folds. Rare-threshold and
direction-aware thresholds were selected on train folds only and evaluated on
held-out prompts. Fixed policies and the oracle upper bound were evaluated on
the same held-out prompts for comparison. Bootstrap confidence intervals resample
prompts, not ordered calls.

## Results

| Policy | Expected clean / prompt | 95% CI | Delta vs always-recondition | Delta 95% CI |
|---|---:|---:|---:|---:|
| oracle_upper_bound | 0.986547 | [0.975618, 0.994350] | 0.012092 | [0.002834, 0.023730] |
| always_recondition | 0.974455 | [0.955013, 0.989659] | 0.000000 | [0.000000, 0.000000] |
| cv_threshold | 0.970018 | [0.950094, 0.985903] | -0.004437 | [-0.011659, 0.002068] |
| cv_direction_threshold | 0.966294 | [0.944872, 0.984116] | -0.008161 | [-0.019007, 0.000721] |
| direction_aware_vocal_rare | 0.884302 | [0.827284, 0.934510] | -0.090154 | [-0.151210, -0.036496] |
| n2_low_or_rare_prior | 0.873286 | [0.786952, 0.944966] | -0.101170 | [-0.191251, -0.025147] |
| always_reseed | 0.694678 | [0.587805, 0.795583] | -0.279778 | [-0.394959, -0.167749] |

## Conclusion

The router claim remains **REDUCED**. A deployable router is not supported
unless a held-out policy beats always-recondition by a nontrivial margin with a
positive prompt-bootstrap interval. This run should be cited as a reduced or
negative replay result if included.
