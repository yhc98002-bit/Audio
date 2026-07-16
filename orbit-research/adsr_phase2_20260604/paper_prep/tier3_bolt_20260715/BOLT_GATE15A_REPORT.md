# BOLT Gate 1.5A Cross-Fitted Policy Value

STATE_FEATURE_STATUS = PASS
CROSSFIT_STATUS = PASS
BEST_STATIC_CQS = 0.776084869
PROMPTONLY_POLICY_CQS = 0.783717358
PROMPTSTATE_POLICY_CQS = 0.783717358
STATE_INCREMENTAL_VALUE = 0.000000000
STATE_INCREMENTAL_VALUE_LCB95 = 0.000000000
CROSSFIT_NONSTATIC_SHARE = 0.103913850
OUTCOME_AWARE_ORACLE_CQS60_UPPER_BOUND = 0.931451613
ROOT_SYMMETRY_STATUS = PASS
STRUCTURAL_REVERIFICATION_STATUS = PASS
CONDITIONING_HARMFUL_PROMPTS = 13
SWITCH_BEATS_RESTART_STATES = 19
GATE15A = STOP_THIS_AXIS
TEST_SUITE_STATUS = PASS

evidence: `BOLT_GATE15A_STATE_AUDIT.md`, `BOLT_GATE15A_FEATURE_AUDIT.md`, `BOLT_GATE15A_CROSSFIT_PREDICTIONS.csv`, `BOLT_GATE15A_BOOTSTRAP.csv`, `BOLT_GATE15A_MODEL_AUDIT.json`, `BOLT_GATE15A_STRUCTURAL_REVERIFY.csv`, `BOLT_GATE15A_TEST_REPORT.md`, `BOLT_GATE15A_CHECKSUMS.tsv`

Branch: `codex/tier3-bolt-gate15a-20260716`. Analysis parent: `a8f3795ea18ea12c89992a24bcad0b43d90c4430`. Gate 1.5B and Gate 2 were not started.

## Evidence and leakage controls

All 288 persisted checkpoint tensors were decoded and scored before model fitting. The state-feature extractor does not import the action atlas. Six folds hold out entire prompts, including both roots and all checkpoints/actions. Fold membership is in `BOLT_GATE15A_FOLDS.csv`; coefficients, priors, training IDs, held-out IDs, scaling, and convergence diagnostics are in `BOLT_GATE15A_MODEL_AUDIT.json`.

Each selected action is paired with deterministic CONTINUE from the same state. Shared prefix NFE is paid once, `CONTINUE+CONTINUE` is deduplicated, programs above 90 measured NFE are excluded before prediction, and every evaluated program retains a completion.

## Cross-fitted values

The cross-fitted static 95% interval is `[0.636819616, 0.890066433]`; prompt-only is `[0.644032698, 0.897684730]`; prompt+state is `[0.644032698, 0.897684730]`. The paired state increment has two-sided interval `[0.000000000, 0.000000000]` and frozen one-sided lower bound `0.000000000`. The Gate-1 oracle value `0.931451613` is outcome-aware development-set information and remains only an upper bound.

Prompt+state selected a different action from prompt-only at `25/288` states,
but none of those changes altered program CQS; 16 changed measured program
NFE. Thus the zero incremental value is an observed held-out-policy result,
not an artifact of the two tiers choosing identical actions.

## Root symmetrization

Prompt-only root-A-to-root-B CQS is `0.748335893` and root-B-to-root-A is `0.796921403`; symmetrized CQS is `0.772628648`. Prompt+state root-A-to-root-B CQS is `0.762192780` and root-B-to-root-A is `0.796921403`; symmetrized CQS is `0.779557092`. This is a secondary prompt-stability diagnostic, not the primary continuation statistic.

## Structural-claim reverification

Conditioning-harmful membership reverified at `13/48`; the design-weighted rate is `0.541186636` with prompt-bootstrap 95% interval `[0.381211547, 0.671261465]`. Same-latent switch beat both matched restart actions at `19/288` states; the design-weighted state rate is `0.041775474` with prompt-cluster 95% interval `[0.021582983, 0.067513571]`. Per-prompt memberships are in `BOLT_GATE15A_STRUCTURAL_REVERIFY.csv`.

## Continuation rule

The frozen rule maps the observed point and lower bound mechanically to `STOP_THIS_AXIS`. No later gate was launched.

## Tests

Focused Gate 1.5A and full repository test commands, pass counts, runtimes, and logs are recorded in `BOLT_GATE15A_TEST_REPORT.md`.
