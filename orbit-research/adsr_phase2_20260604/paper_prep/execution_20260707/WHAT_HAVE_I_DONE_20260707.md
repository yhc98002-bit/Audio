# What I Have Done

Date: 2026-07-07

Workspace: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion`

Execution root:
`orbit-research/adsr_phase2_20260604/paper_prep/execution_20260707/`

## Execution Framework

- Created the execution ledger:
  `orbit-research/adsr_phase2_20260604/paper_prep/execution_20260707/EXECUTION_LEDGER.md`
- Added reusable scripts for:
  - JSONL ledger/schema/duplicate-key audits.
  - Publication metric reproduction.
  - Judge-smoke manifest repair.
  - Stage 3 intervention generation.
  - Generation output summaries.
  - Population retry manifest construction.
  - Population retry generation.
  - Population regime read-out.
- Kept new artifacts under `orbit-research/adsr_phase2_20260604/paper_prep/`.
- Did not modify frozen `runs/**`, Gate-B evidence, `configs/eval/gate_v1.yaml`,
  listening packets, tarballs, or archives.

## Existing Evidence Reproduction

- Recomputed publication metrics from existing retry-study ledgers.
- Produced:
  - `execution_20260707/T21_efficiency_metrics.csv`
  - `execution_20260707/T21_efficiency_metrics.json`
  - `execution_20260707/T21_efficiency_metrics.md`
  - `execution_20260707/T21_CITATION_NOTE.md`
- Audited the baseline retry ledger:
  - 16,384 rows.
  - No duplicate `(prompt_id, condition, seed_idx)` keys.
- Reproduced key values:
  - Vocal median clean rate: `0.064453`
  - Vocal mean clean rate: `0.088120`
  - Instrumental median clean rate: `0.361328`
  - Instrumental mean clean rate: `0.359115`
  - V3 vocal intervention mean delta: `+0.685777`
  - V3 vocal intervention improved prompts: `17/17`
  - I_strong instrumental intervention mean delta: `+0.005469`
  - I_strong instrumental intervention improved prompts: `9/15`

## Judge Pipeline

- Built a repaired 10-clip judge-smoke manifest:
  `execution_20260707/judge_smoke_manifest_repaired.csv`
- Patched the judge client so the model can be selected via `DASHSCOPE_MODEL`,
  defaulting to `qwen3.5-omni-plus`.
- Ran repaired judge smoke with:
  - `qwen3.5-omni-plus`
  - `qwen3.5-omni-flash`
- Both repaired smokes failed at `6/10`.
- Did not run A'/B' scale judge calls.
- Recorded blocker:
  `execution_20260707/JUDGE_SMOKE_BLOCKED_20260707.md`

## Compute And Environment

- Recovered and checked active allocations on `an12` and `an29`.
- Verified both nodes had:
  - torch `2.5.1+cu121`
  - CUDA available
  - 8 A800 GPUs visible
- Ran ACE-Step one-sample smoke on `an12`; it passed.
- Checked Stage 4 SAO path on `an29`.
- Found `stable_audio_tools` missing.
- Dry-run showed installing `stable-audio-tools` into shared `audio-prm` would
  upgrade torch, torchaudio, and CUDA dependencies.
- Did not mutate the shared `audio-prm` environment.
- Recorded blocker:
  `execution_20260707/STAGE4_SAO_BLOCKED_20260707.md`

## Stage 3 Intervention Decomposition

- Wrote and froze the Stage 3 pre-registration:
  `paper_prep/STAGE3_INTERVENTION_PREREG_20260707.md`
- Implemented the Stage 3 intervention worker:
  `paper_prep/scripts/stage3_intervention_worker.py`
- Implemented six intervention conditions:
  - `vocal_guidance`
  - `vocal_hints`
  - `vocal_both`
  - `instr_text`
  - `instr_sampler`
  - `instr_both`
- Used seed policy:
  `2030000000 + prompt_index * 100000 + condition_index * 1000 + seed_idx`
- Ran an initial smoke. It was clean but invalid as a launch gate because it
  only covered one prompt/condition.
- Fixed smoke limiting to round-robin across conditions.
- Ran balanced smoke `smoke50_balanced`:
  - 50 rows.
  - All six conditions represented.
  - 0 errors.
  - 0 near-silent clips.
  - 0 missing FLACs.
  - Duplicate-key audit PASS.
- Launched full run `full64` on `an12`.
- Completed full run:
  - 6,144 rows.
  - 6,144 kept FLACs.
  - 8 ledgers x 768 rows.
- Final audit:
  `paper_prep/stage3_intervention_20260707/full64_final_ledger_audit.md`
- Final summary:
  `paper_prep/stage3_intervention_20260707/full64_final_summary.md`
- Final Stage 3 integrity result:
  - 0 parse errors.
  - 0 missing required rows.
  - 0 duplicate `(prompt_id, condition, seed_idx)` keys.
  - 0 generation errors.
  - 0 near-silent rows.
  - 0 missing FLACs.
- Stage 3 final type-correct rates:
  - `vocal_guidance`: `0.781250`
  - `vocal_both`: `0.779412`
  - `vocal_hints`: `0.093750`
  - `instr_both`: `0.377083`
  - `instr_sampler`: `0.344792`
  - `instr_text`: `0.326042`

## N2 Population Retry Map

- Built deterministic 128-prompt population retry manifest from:
  - `configs/prompts/held_out.jsonl`
  - `orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl`
- Derived baseline violation counts using threshold `0.1791`.
- Selected 128 of 256 held-out prompts, stratified by 8-candidate baseline
  violation-count histogram.
- Wrote and froze the N2 pre-registration:
  `paper_prep/POPULATION_RETRY_PREREG_20260707.md`
- Manifest:
  `paper_prep/population_retry_20260707/population_retry_manifest_128.jsonl`
- Manifest histogram:
  - `0`: 51 prompts
  - `1`: 24 prompts
  - `2`: 17 prompts
  - `3`: 8 prompts
  - `4`: 11 prompts
  - `5`: 8 prompts
  - `6`: 5 prompts
  - `7`: 2 prompts
  - `8`: 2 prompts
- Implemented the population retry worker:
  `paper_prep/scripts/population_retry_worker.py`
- Used seed policy:
  `2030000000 + original_heldout_prompt_index * 100000 + seed_idx`
- Ran N2 smoke `smoke50`:
  - 50 rows.
  - All violation bins represented.
  - 0 errors.
  - 0 near-silent rows.
  - 0 missing FLACs.
  - Duplicate-key audit PASS.
- Launched full run `full128` on `an12`.
- Completed full run:
  - 128 prompts.
  - 128 seeds per prompt.
  - 16,384 rows.
  - 16,384 kept FLACs.
  - 8 ledgers x 2,048 rows.
- Ran checkpoint audits at:
  - first 500 rows
  - about 1k rows
  - about 4k rows
  - bin-0 boundary
  - bin-1 boundary
  - bin-2 boundary
  - late-bin checkpoint
  - final completion
- Final audit:
  `paper_prep/population_retry_20260707/full128_final_ledger_audit.md`
- Final summary:
  `paper_prep/population_retry_20260707/full128_final_summary.md`
- Final regime read-out:
  `paper_prep/population_retry_20260707/full128_regime_readout.md`
- Prompt-level clean rates:
  `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`
- Final N2 integrity result:
  - 16,384 rows.
  - 16,384 OK rows.
  - 0 parse errors.
  - 0 missing required rows.
  - 0 duplicate `(prompt_id, seed_idx)` keys.
  - 0 generation errors.
  - 0 near-silent rows.
  - 0 missing FLACs.

## N2 Regime Results

Regime counts over 128 selected held-out prompts:

| Regime | Prompts | Fraction |
|---|---:|---:|
| `easy_ge_1_in_2` | 67 | 0.523438 |
| `seed_recoverable_1_in_4_to_1_in_2` | 33 | 0.257812 |
| `low_1_in_16_to_1_in_4` | 23 | 0.179688 |
| `rare_le_1_in_16` | 5 | 0.039062 |

Stratum results:

- Instrumental: 47 prompts, mean clean rate `0.761137`.
- Vocal: 81 prompts, mean clean rate `0.401331`.

## Storage And Resource State

- Stage 3 output directory size:
  `paper_prep/stage3_intervention_20260707` uses about 33 GB.
- Population retry output directory size:
  `paper_prep/population_retry_20260707` uses about 73 GB.
- Final quota state:
  about `251.9 GB / 500 GB` soft quota used.
- Final `an12` GPU state:
  GPUs idle after the completed runs.
- `an29` was not repurposed.
- `an17` was not targeted.

## Remaining Blockers

- Judge A'/B' scale calls remain blocked because both repaired judge smokes
  failed `6/10`.
- Stage 4 SAO remains blocked because `stable_audio_tools` is absent and direct
  installation into shared `audio-prm` would mutate torch, torchaudio, and CUDA
  dependencies.
- I checked the next backlog tail-deepening area after `an12` became idle.
  Existing `ext512*` artifacts in the authoritative retry-study tree were logs
  only and ambiguous relative to current frozen evidence, so I did not launch a
  new backlog run without a fresh scoped artifact plan.

## Final Status

- Stage 3 intervention decomposition: complete and audited.
- N2 population retry map: complete and audited.
- Judge scale calls: blocked.
- Stage 4 SAO: blocked.
- `an17`: not targeted.
