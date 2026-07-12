# W2 Instrumental Factorial Preregistration

Preregistered: 2026-07-12, before generation  
Model: frozen ACE-Step v1, `ACE-Step/ACE-Step-v1-3.5B`  
Scheduler: Euler, shift 3.0  
Sample size: 32 prompts x 6 conditions x 16 CRN seeds = 3,072 clips

## Prompt Selection

The 32 prompt IDs are selected deterministically from the existing N2
instrumental-request frame. Instrumental prompts are ranked by ascending N2
clean rate under the frozen current detector (highest apparent risk first),
then by canonical prompt ID. The committed generation manifest records the
complete ranking and selected IDs before any new output exists. Prompt text is
copied byte-for-byte from the canonical source manifest.

## Conditions

| ID | Text intervention | Sampler |
|---|---|---|
| `plain_baseline` | canonical prompt | CFG 5.0 |
| `negative_text` | append `pure instrumental, no vocals, no singing, no voice` | CFG 5.0 |
| `positive_text` | append `instrumental arrangement led by synthesizer, drums, bass, and melodic instruments` | CFG 5.0 |
| `sampler_only` | canonical prompt | CFG 7.5 |
| `negative_sampler` | negative text above | CFG 7.5 |
| `positive_sampler` | positive text above | CFG 7.5 |

The positive-only text contains none of the vocal lexemes `vocal`, `vocals`,
`voice`, `voices`, `sing`, `singing`, `singer`, `choir`, `chant`, `speech`,
`spoken`, or `rap`. All other generation parameters are matched. Conditions
use the same 16 deterministic seeds within each prompt.

Seed formula:

`2034000000 + prompt_rank * 1000 + seed_index`

The condition is intentionally absent from the formula to implement common
random numbers. The range is registered in `paper_prep/SEED_REGISTRY.md` before
launch.

## Frozen Generation Settings

- duration: 15 seconds;
- inference steps: 30;
- scheduler: Euler, shift 3.0;
- CFG type: APG, matching the completed intervention lane;
- guidance interval: 0.5;
- precision: bfloat16;
- ERG, guidance rescale, omega scale, and manual seed-search controls: off;
- one clip per process call; and
- all audio, failed attempts, logs, and append-only ledgers retained.

## Analysis

The primary endpoint is Label-B violation under a promoted corrected
instrument. Before promotion, current/candidate detector output is explicitly
`apparent` or `sensitivity-only` and cannot change PLAN claims.

For every condition, report prompt-weighted mean violation, confidence
interval, and matched-seed difference from `plain_baseline`. Also report:

- negative wording versus positive-only wording at CFG 5.0;
- negative wording versus positive-only wording at CFG 7.5;
- sampler main effect within each wording family; and
- text-by-sampler interaction.

Inference uses prompt-cluster bootstrap with deterministic seeds and reports all
frozen contrasts. No condition is dropped or renamed after observing results.
The later 20-pair PI spot check samples baseline-versus-best-apparent pairs by a
committed rule and is reported separately from detector promotion.

`FACTORIAL_PREREGISTRATION_STATUS = FROZEN_BEFORE_GENERATION`

