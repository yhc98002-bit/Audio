# Exit-1 Neutral-Control Report

`NEUTRAL_CONTROL_STATUS = COMPLETE`

The matched neutral-control cell is complete: 24 prompts × 8 newly registered seeds produced 192 retained clips, all clips passed integrity checks, all clips were scored with the mechanically parsed promoted OR instrument, and the four-cell prompt-cluster analysis completed. This report changes neither PLAN nor CLAIMS.

## Frozen design and ordering evidence

- Frozen-input commit: `c7b9501255e5a7aef29fc83e5344286e9114d913`.
- Generation/scoring evidence commit: `fd9cba693dd9f7cadd0fc9d80e38e4a19392c23d`.
- Git ancestry check: `PASS` (the frozen-input commit is a strict ancestor of the generation/scoring evidence commit).
- Canonical factorial mismatch assumption: the source has 32 prompts; the task requires 24, so pre-existing historical-N2-risk ranks 0–23 were frozen before neutral generation. Factorial-condition outcomes were not used in the 24-of-32 selection rule. This is a risk-ranked subset, so the result does not automatically generalize to ranks 24–31.
- Neutral insertion: `studio recording, carefully produced, cleanly mixed, balanced acoustics`.
- Negative reference insertion: `pure instrumental, no vocals, no singing, no voice`.
- Per-prompt tokenizer audit: all 24 neutral full prompts exactly match their negative-reference full-prompt token counts; all append deltas and actual post-structure-hint ACE-Step conditioning counts match.
- Semantic scope: the single frozen studio/recording descriptor is vocally inert by design and passes the forbidden-vocal-lexeme screen. Exact token equality does not prove generic semantic-specificity equivalence for every possible neutral text.
- Tokenizer JSON SHA-256: `20a46ac256746594ed7e1e3ef733b83fbc5a6f0922aa7480eda961743de080ef`.
- New seed range: `2071000000` through `2071023007`; formula `2071000000 + prompt_rank*1000 + seed_idx`.
- Legacy cells use frozen seed indices 0–7. Neutral seeds are independent, so the paired confound test is paired by prompt cluster, not by identical diffusion noise.

## Promoted OR instrument

Dispatch A's fail-closed parser read the canonical JSON and verified the exact report line:

```text
- Selected family: `or`.
```

- `T6_PROMOTION_RESULT.json` SHA-256: `2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2`.
- `T6_PROMOTION_REPORT.md` SHA-256: `9ab909fc301a89c5de04f53dcb3b613e4984c184f2a5bf39987ac1f97de23a9d`.
- Parsed Demucs threshold: `0.03161777090281248`.
- Parsed PANNs threshold: `0.04403413645923138`.
- Endpoint: hard vocal-presence violation = `demucs_score >= parsed threshold OR panns_score >= parsed threshold`. The near-silent flag does not suppress the canonical Demucs component.

## Four-cell comparison

Each cell has 192 observations in 24 prompt clusters. Intervals are two-sided 95% percentile intervals from 10,000 deterministic prompt-cluster bootstrap draws.
The positive row is the canonical corrected positive-v2 cohort: its source negative vocal/lyrics clause was removed before positive instrumental descriptors were added. It is therefore contextual/descriptive, not a pure same-base insertion cell.

| cell | observations | prompt clusters | promoted-OR violation rate | 95% prompt-cluster CI |
|---|---:|---:|---:|---:|
| plain | 192 | 24 | 0.744792 | [0.661458, 0.822917] |
| neutral-matched | 192 | 24 | 0.796875 | [0.713542, 0.869792] |
| negative | 192 | 24 | 0.822917 | [0.744792, 0.895833] |
| positive | 192 | 24 | 0.526042 | [0.411458, 0.635417] |

## Paired neutral-vs-negative confound test

The preregistered orientation is neutral-matched minus negative. Within each prompt, each condition is first averaged across its eight independent seeds; the 24 prompt differences are then bootstrapped as paired clusters.

- Delta: `-0.026042`.
- 95% prompt-paired bootstrap CI: `[-0.109375, 0.052083]`.
- Two-sided prompt-level sign-flip p-value: `0.637754` (100,000 Monte Carlo draws).
- Confound-test verdict: `INCONCLUSIVE_MATCHED_LENGTH_CONFOUND_TEST`.
- Interpretation: The prompt-paired 95% CI includes zero, so this cell does not rule out the matched-length/neutral-descriptor explanation within the selected subset.
- Scope qualifier: the verdict is conditional on the preregistered neutral-inertness assumption and applies to this risk-ranked 24/32 subset.

This is a completed control experiment, not a PLAN/CLAIMS amendment. The reported outcome is not upgraded beyond the evidence in this cell.

## Generation and retained evidence

- Placement: `an12`, GPUs `4,7`, TP`1`, `2` independent replicas.
- Placement justification: Two independent TP1 ACE-Step 3.5B replicas on disjoint A800 GPUs; tasks deterministically sharded for throughput, with no cross-node job.
- Exact launch command: `worker0: ssh an12 env CUDA_VISIBLE_DEVICES=4 ACE_STEP_CHECKPOINT_DIR=/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python /XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion-neutral-control-20260717/analysis_exit1_v2/neutral_control/neutral_control.py generate --worker-index 0 --num-workers 2 --freeze-commit c7b9501255e5a7aef29fc83e5344286e9114d913; worker1: ssh an12 env CUDA_VISIBLE_DEVICES=7 ACE_STEP_CHECKPOINT_DIR=/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python /XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion-neutral-control-20260717/analysis_exit1_v2/neutral_control/neutral_control.py generate --worker-index 1 --num-workers 2 --freeze-commit c7b9501255e5a7aef29fc83e5344286e9114d913`.
- Generation config SHA-256: `f111b24871aa09474f505ac8e484a7d64b650661c944fb88dd6af783846e9348`.
- Retained audio: `192` FLAC files, `286717426` bytes under `analysis_exit1_v2/neutral_control/audio/neutral_matched`.
- Audio checksum manifest: `analysis_exit1_v2/neutral_control/NEUTRAL_AUDIO_SHA256SUMS` (SHA-256 `a68493f4ef4803a503902fe72a0f396f2dc77a9ca58db3c8967d858603f98c60`).
- Generation audit: `analysis_exit1_v2/neutral_control/NEUTRAL_GENERATION_AUDIT.json` (SHA-256 `f9127900f5753b3127853ab22119fa93f8d7b3805ab87287274fc6342cba5284`).
- Scoring audit: `analysis_exit1_v2/neutral_control/NEUTRAL_SCORING_AUDIT.json` (SHA-256 `bcf476a12e0a472c1ee0270cf8312f010ec4b0afba0ded43370c111f92136db5`).
- Scoring placement: `an12`, GPUs `4,7`, TP`1`, `2` independent replicas.
- Exact scoring command: `worker0: ssh an12 env CUDA_VISIBLE_DEVICES=4 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python /XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion-neutral-control-20260717/analysis_exit1_v2/neutral_control/neutral_control.py score --worker-index 0 --num-workers 2 --freeze-commit c7b9501255e5a7aef29fc83e5344286e9114d913; worker1: ssh an12 env CUDA_VISIBLE_DEVICES=7 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false /HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python /XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion-neutral-control-20260717/analysis_exit1_v2/neutral_control/neutral_control.py score --worker-index 1 --num-workers 2 --freeze-commit c7b9501255e5a7aef29fc83e5344286e9114d913`.
- Scoring config SHA-256: `5ba9e3bc74f6c38ed9545896e78f07ee02a9a7247303e7d2b5cf760a256343e4`; run manifest `analysis_exit1_v2/neutral_control/NEUTRAL_SCORING_RUN_MANIFEST.json`.
- Four-cell rows: `analysis_exit1_v2/neutral_control/FOUR_CELL_SCORE_ROWS.csv` (SHA-256 `503af3ac1f2500c00e2d758a75eef23bf1e2bb9c8f8f3e7b2197bc6adfa881ca`).

## Tests

`TEST_SUITE_STATUS = PASS`

- Command: `/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python -m pytest --force-short-summary`.
- Result: `376 passed`, exit code `0`.
- Tested git hash: `fd9cba693dd9f7cadd0fc9d80e38e4a19392c23d` on `ln207` with Python `3.10.20`.
- Raw output: `analysis_exit1_v2/neutral_control/FULL_TEST_RESULTS.txt` (SHA-256 `1e3cbe8ed7aa30664cf7fb04ce0fc3dfe71d9e4992e43a735ba651ead03d180a`).
- Summary: `analysis_exit1_v2/neutral_control/FULL_TEST_RESULT_SUMMARY.json`.
- Supplemental exact-tree audit: `PASS`. The tested commit was mounted read-only at the historical canonical checkout path; ignored legacy evidence was mounted read-only, five known legacy write targets were redirected to temporary copies, all 376 progress markers completed with exit code `0`, redirected copies remained byte-identical, and both tracked-worktree and index diffs remained empty. See `analysis_exit1_v2/neutral_control/FULL_TEST_EXACT_TREE_AUDIT.json` and `FULL_TEST_RESULTS_EXACT_TREE.txt` (SHA-256 `082c2848f88fd900be2b86636967ecd1a10c1848c493eb7052c42b3cfbad3fef`).

## Scope

`PLAN_CLAIMS_CHANGED = NO`

No checkpoint, pre-existing generated data, canonical factorial artifact, PLAN file, or CLAIMS file was modified.
