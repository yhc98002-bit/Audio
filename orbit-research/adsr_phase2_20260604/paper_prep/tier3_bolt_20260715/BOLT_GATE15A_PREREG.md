# BOLT Gate 1.5A Cross-Fitted Policy-Value Preregistration

Status: `FROZEN_BEFORE_GATE15A_MODEL_FITTING`

Parent commit: `a8f3795ea18ea12c89992a24bcad0b43d90c4430`
Branch: `codex/tier3-bolt-gate15a-20260716`

## Scope

This analysis uses only the frozen 48-prompt BOLT pilot, its 96 roots, 288
persisted checkpoint tensors, and 1,440 action outcomes. It tests whether
checkpoint-state information adds cross-fitted policy value beyond prompt-only
information. It does not train a production controller, collect new action
outcomes, use held-out prompts, start Gate 1.5B, or start Gate 2.

## State-feature contract

Every one of the 288 persisted `.pt` checkpoint states must be loaded through
the Gate-0 state contract. File, latent, model-output, and RNG hashes must
match the immutable sidecar and checkpoint-state ledger. Missing or conflicting
states stop the analysis; no action outcome, root output, EVPD proxy, or other
substitute may stand in for a checkpoint tensor.

The frozen ACE-Step VAE decoder is applied directly to each saved latent. The
decoded preview is scored with the same promoted W2 Label-B instrument,
calibration model, and CLAP-to-original-prompt implementation used for Gate 1.
The feature ledger records Demucs score, PANNs score, promoted binary decision,
calibrated Label-B violation probability, CLAP-to-prompt, checkpoint index,
prefix NFE, remaining NFE under `B_NFE=90`, request direction, frozen prompt
risk variables, and request metadata. Common-quality scores are retained for
audit but are not policy features. No state-feature threshold is tuned.

## Evaluation unit and program semantics

The evaluation unit is a persisted `(prompt, root, checkpoint)` state. Its
five candidate programs are defined as the candidate action plus deterministic
`CONTINUE` from that same checkpoint. The default completion is paid once and
is the completion reserve. `CONTINUE + CONTINUE` is one physical terminal leaf.
For any other action, shared prefix cost is paid once and total program cost is:

```text
prefix_nfe + continue_edge_nfe + selected_action_edge_nfe
```

Restarts retain their measured full-generation edge cost. Programs above 90
raw transformer calls are excluded before prediction. Every evaluated program
therefore has a valid completed candidate and satisfies the frozen Gate-1
completion-reserve rule. Program success is one when either the selected action
or default completion has `CQS=1`.

Each prompt contributes six state programs (two roots by three checkpoints).
The primary population estimate averages those six states within prompt and
then applies the frozen prompt design weights. Confidence intervals resample
whole prompts within the four frozen strata.

## Cross-fitting

Six deterministic prompt-grouped folds are used. Within each frozen stratum,
prompts are ordered by SHA-256 of `2026071601|prompt_id` and assigned round-robin
to six folds, yielding two prompts per stratum and eight prompts per fold. Both
roots, every checkpoint, and all actions for a prompt remain in the same fold.
No held-out prompt outcome is used for model fitting, feature normalization,
static-program selection, or tie breaking.

## Frozen model family

Both tiers use the same low-capacity hierarchical MAP logistic action-value
model. Five action-specific intercepts receive Beta(1,1)-smoothed empirical
log-odds prior means estimated only from the training prompts. Remaining
coefficients have zero-mean Gaussian priors with fixed precision. Optimization
uses deterministic Newton updates, a maximum of 100 iterations, gradient
tolerance `1e-9`, probability clipping at `1e-8`, and no hyperparameter search.

Prompt-only tier features are action interactions with: request direction,
the three frozen pre-existing risk variables, genre, tempo bin, prompt
specificity, structure complexity, and language. Continuous features are
standardized on training prompts only. Main/action precision is `4`; metadata
interaction precision is `32`.

Prompt+state tier adds action interactions with: decoded-preview Demucs,
PANNs, calibrated violation probability, CLAP-to-prompt, promoted-present,
checkpoint fraction, and remaining-budget fraction. Their prior precision is
`16`. These values and feature sets are frozen before fitting.

At a held-out state, the feasible action with largest predicted program-success
probability is selected. Ties use lower measured program NFE, then this fixed
order: `CONTINUE`, `SWITCH_CONDITION`, `FORK_LATENT`,
`RESTART_CONDITIONED`, `RESTART_BASE`.

## Comparators and diagnostics

`BEST_STATIC_CQS` is a cross-fitted prompt-independent mapping from
`(request_direction, checkpoint)` to action. Each fold chooses that mapping on
training prompts only and evaluates it on held-out prompts under the same
program and reserve semantics.

The primary contrast is:

```text
STATE_INCREMENTAL_VALUE = PROMPTSTATE_POLICY_CQS - PROMPTONLY_POLICY_CQS
```

The one-sided 95% lower bound is the fifth percentile of 10,000 paired,
stratified prompt-bootstrap replicates with seed `2026071602`.
`CROSSFIT_NONSTATIC_SHARE` is the weighted held-out state share where the
prompt+state action differs from the fold-specific static action.

The Gate-1 oracle is restated only as an outcome-aware upper bound. Secondary
prompt-stability diagnostics fit on root A and evaluate root B, then fit on
root B and evaluate root A, always retaining prompt-grouped held-out folds.

The two Gate-1 structural claims are mechanically recomputed from canonical
action rows: fixed conditioning harmful on 13/48 prompts, and same-latent
switch beating both matched restart actions at 19 states. Exact memberships,
design-weighted rates, and prompt-cluster bootstrap intervals are reported;
disagreement with the original counts is a failed reverification, not a
reinterpretation.

## Frozen continuation rule

```text
if STATE_INCREMENTAL_VALUE_LCB95 > 0:
    GATE15A = PROCEED_GATE15B
elif STATE_INCREMENTAL_VALUE >= 0.05:
    GATE15A = PROCEED_GATE15B_POWERED_BY_REPLICATION
else:
    GATE15A = STOP_THIS_AXIS
```

No later gate is launched automatically for any result.
