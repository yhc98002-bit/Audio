# BOLT Method Specification

## Scope

Budgeted Option-value Latent Tree Search (BOLT) is a new inference-time
experiment over ACE-Step v1 development prompts. This Gate 0/1 run implements
and validates trajectory actions, collects a frozen 48-prompt Counterfactual
Action Atlas pilot, and measures structural oracle headroom. It does not train
a controller, use held-out prompts, run transfer, alter W2 evidence, or proceed
to Gate 2.

## State and actions

A BOLT state is a post-scheduler-step ACE-Step state. The persisted contract
contains the latent, scheduler step index and timestep, current and next sigma,
the most recent model output, conditioning-cache identity, prompt identity,
root seed, relevant RNG state, model/checkpoint identity, latent SHA256, dtype,
and shape. Gate checkpoints are post-step 6, 12, and 18 of a 30-step root.

The frozen action set is:

| Action | Semantics |
| --- | --- |
| `CONTINUE` | Resume the captured latent under the original condition. |
| `SWITCH_CONDITION` | Resume the same latent under the frozen direction-specific condition. |
| `FORK_LATENT` | Add deterministic seed-keyed checkpoint noise at the Gate-0-calibrated eta and continue under the original condition. |
| `RESTART_BASE` | Pay a full-generation cost for an independent base seed. |
| `RESTART_CONDITIONED` | Pay a full-generation cost for an independent seed under the direction-specific condition. |

Instrumental switching uses positive-only instrumental text with no negative
vocal lexemes and the frozen sampler setting. Vocal switching uses the frozen
vocal text/lyric guidance settings and adds a structure hint only when absent.
A condition-hash change is mandatory. Silent fallback is fatal.

## Outcome

`CQS = 1` only if all of the following hold:

1. the promoted W2 Label-B instrument says the request constraint is satisfied;
2. common robust LCB meets the frozen request-direction quality floor;
3. CLAP-to-original-prompt meets the frozen request-direction fidelity floor;
4. the audio decodes, has the expected sample rate and duration, and is not near-silent.

Otherwise `CQS = 0`. The instrument and floors are immutable after the first
BOLT output is inspected. A scientific score of `0.0` is valid and is never
converted to missing or negative infinity.

## Compute budget

Compute is measured by direct transformer `decode` forward calls. One ordinary
30-step generation is measured in the frozen environment before the pilot.
The primary budget is `B_NFE = 2 * STANDARD_GENERATION_NFE`. Every edge records
raw transformer calls, scheduler steps, prefix cost, continuation or restart
cost, wall time, and CUDA-event time where available.

Tree accounting pays a shared prefix once. A restart pays a complete generation
cost. Static programs, per-state actions, per-root feasible subsets, and the
full tree-knapsack oracle are all constrained by the same measured `B_NFE`.
Repeated deterministic `CONTINUE` terminal leaves are retained as state-action
records but counted once in oracle success.

## Budget invariants

The budget manager is global, not attempt-indexed. It returns unused measured
NFE after aborts. Under a two-generation budget, two step-12 aborts leave enough
budget for one complete 30-step generation. If no valid completed candidate
exists, an action plan that would consume the completion reserve is rejected
before model execution.

## Gate boundaries

Gate 0 requires environment parity, 48/48 strict cross-process resume controls,
valid condition switching, a frozen diverse fork eta, direct NFE accounting,
true rollover, completion reserve, and zero-score regression tests. Every
component must pass before pilot generation.

Gate 1 requires an exact audit of 96 roots, 288 checkpoint states, and 1,440
action outcomes. It returns GO only if either weighted oracle CQS headroom over
the best static program is at least 0.05 with one-sided prompt-bootstrap 95%
lower bound above zero, or matched-CQS oracle compute saving is at least 0.20
with a positive lower bound, and weighted oracle-nonstatic prompt share is at
least 0.20. Thresholds are not changed after observing pilot results.

## Frozen exclusions

No policy learning, full atlas, prospective live pilot, held-out evaluation,
transfer, W2 modification, quality-floor tuning on BOLT output, or unrelated
GPU work is part of this execution.
