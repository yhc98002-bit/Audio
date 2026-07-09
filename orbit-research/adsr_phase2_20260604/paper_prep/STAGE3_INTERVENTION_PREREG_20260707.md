# Stage 3 Intervention Decomposition Pre-Registration

Status: frozen before the 2026-07-07 smoke/full Stage 3 launch.

## Goal

Measure which condition component drives the Claim-3 rescue effect.

## Prompt Sets

- Vocal side: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/E2_VOCAL.jsonl`
  with 17 hard vocal-request prompts.
- Instrumental side: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/E2_INSTR.jsonl`
  with 15 hard instrumental-request prompts.

## Conditions

- `vocal_guidance`: raise text/lyric guidance only.
- `vocal_hints`: add a default structure hint only when the prompt lacks one.
- `vocal_both`: combine vocal guidance and structure-hint injection.
- `instr_text`: append an anti-vocal text edit and remove lyrics.
- `instr_sampler`: sampler-only variant via higher CFG.
- `instr_both`: combine strong anti-vocal text edit, lyric removal, and higher CFG.

## Seeds

For all runs:

`seed = 2030000000 + prompt_index * 100000 + condition_index * 1000 + seed_idx`

Condition indices:

- `vocal_guidance`: 1
- `vocal_hints`: 2
- `vocal_both`: 3
- `instr_text`: 4
- `instr_sampler`: 5
- `instr_both`: 6

## Readout

Primary readout is per-try type-correct/clean rate by prompt and condition.
Expected direction before launch: at least one vocal-side component has a large
clean-rate gain; instrumental-side components are near zero. Either result is
reportable.

## Launch Gate

Run a 50-clip smoke before full launch. Audit schema, duplicate keys, silence
rate, label-prior drift, and ledger paths. Full launch only after the smoke
audit is clean.
