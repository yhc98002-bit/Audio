# BOLT Gate 0/1 Preregistration

Status: `FROZEN_BEFORE_BOLT_OUTPUT`

Branch: `codex/tier3-bolt-gate01-20260715`

## Primary endpoint and budget

The primary endpoint is population-design-weighted `CQS@B`, where CQS is the
joint binary outcome in `BOLT_METHOD_SPEC.md` and `B` is twice the directly
measured transformer-forward count of one frozen 30-step ACE-Step generation.
Raw forward calls are primary; scheduler-step equivalents and timing are
secondary accounting diagnostics.

Quality and CLAP floors are request-direction-specific 10th percentiles among
pre-existing, promoted-instrument-satisfied development baseline outputs. The
source rows, split, inclusion criteria, quantile implementation, and artifact
hash are frozen in `BOLT_QUALITY_FLOORS.json` before any BOLT output is scored
or inspected.

## Gate 0

The three checkpoints are post-step 6, 12, and 18. Resume testing uses eight
development prompts, two root seeds, and three checkpoints (48 controls).
Pass requires 48 valid completions, exact latent save/load hashes, no Label-B
or quality-floor flips, aligned waveform NRMSE at most `1e-6`, audio-audio CLAP
cosine at least `0.999999`, and identical sample rate and duration. A floating-
point discrepancy is a STOP for PI review, not grounds to relax thresholds.

Condition switching requires different conditioning hashes, identical model
and latent prefix, remaining-NFE-only continuation, valid non-silent audio, and
fully ledgered parameters. Fork eta is selected from `0.025, 0.05, 0.10` as the
smallest value on eight calibration roots with at least 90% nonidentical audio
hashes, no invalid or near-silent outputs, and mean deterministic-branch
audio-audio CLAP cosine in `[0.80, 0.999)`. The selected eta is then frozen.

Direct transformer-call accounting, shared-prefix accounting, two-abort true
rollover, completion-reserve rejection, and zero-score selection must pass.
Gate 0 passes only if every listed component passes.

## Pilot design

The sampling frame is development-only and excludes held-out/test prompts and
Gate-0 calibration prompts. Risk is frozen as `0.5 * promoted-instrument
candidate violation rate + 0.5 * mean corrected-EVPD violation probability`
over each prompt's eight pre-existing spine candidates. Instrumental prompts
are rank-tertiled by this score with prompt-hash tie breaking. The frozen sample is 48 prompts: 12 high-risk
instrumental, 12 medium-risk instrumental, 12 low-risk instrumental, and 12
vocal. Within strata, deterministic balanced sampling covers genre, tempo,
prompt specificity, structure complexity, and language as far as the frame
permits. Frame size, inclusion probability, and design weight are retained.

The atlas has 48 prompts, two root seeds, three checkpoints, and five actions,
for exactly 96 roots, 288 checkpoint states, and 1,440 action outcomes. Root
prefixes are generated once. Keys are `(prompt_id, root_seed, checkpoint_step,
action)`. Missing, duplicate, conflicting, or failed rows block Gate 1.

## Static and oracle programs

The frozen static search includes at least: two base generations; two
direction-conditioned generations; one base plus one conditioned generation;
fixed continue-and-switch branches at each checkpoint; fixed deterministic-
plus-fork branches at each checkpoint; true-rollover corrected-EVPD threshold
policy; and the frozen W2 two-slot policy. Selection uses pilot development
data only and is reported as descriptive Gate-1 evidence, never held-out
performance.

The corrected-EVPD programs apply the already frozen W2 sigma-0.8 model and
threshold to `x0 = x_sigma - sigma * v` at the first measured transformer
evaluation whose scheduler sigma is at most 0.8. There is no BOLT-data
retuning. The W2 two-slot replay leaves abort savings unused. The true-rollover
variant returns measured NFE to the global budget and, only when feasible,
spends the remainder on a step-18 same-root direction switch after completing
the second base root. Conditioned-restart outputs are charged their measured
full-generation calls; their discarded prefixes are charged only in programs
that actually inspect those prefixes.

Oracle analyses are the per-state action oracle, per-root feasible subset, and
full measured-cost tree-knapsack oracle. The empirical oracle does not assume
independence. `sum(-log(1-p_i))` is reported separately as an option-value
approximation for independent estimated candidate probabilities.

Primary reporting uses design-weighted CQS, with equal-stratum and each-stratum
diagnostics, prompt-cluster bootstrap intervals, completion probability,
measured NFE, floor failures, and selected actions. The prompt bootstrap is
clustered by prompt; the one-sided 95% lower bound is the 5th percentile of the
paired oracle-minus-best-static distribution. The compute-saving lower bound
uses the same paired prompt bootstrap.

## Frozen Gate 1 rule

Gate 1 returns `GO_ACTION_VALUE_LEARNING` only when Gate 0 passed, the 1,440-row
audit passed, and:

- `ORACLE_CQS60 - BEST_STATIC_CQS60 >= 0.05` with one-sided 95% prompt-bootstrap lower bound greater than zero; or
- `ORACLE_COMPUTE_SAVING_AT_MATCHED_CQS >= 0.20` with a positive one-sided 95% lower bound;

and in either case `ORACLE_NONSTATIC_PROMPT_SHARE >= 0.20`.

Otherwise it returns `STOP_NO_STRUCTURAL_HEADROOM`. If Gate 0 fails it returns
`STOP_GATE0_FAILED`. No threshold, stratum, floor, action, or baseline is
changed after outputs are observed. Gate 2 is not launched automatically.
