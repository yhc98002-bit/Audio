# SA3 True-Intermediate Observability Report

`SA3_INTERMEDIATE_STATUS = TRUE_INTERMEDIATE_COMPLETE`

## Design

- 96 unique prompts, one replayed historical seed per prompt.
- Request strata: 48 vocal and 48 instrumental.
- Development/test split: 48/48, balanced within request stratum.
- Same trajectory: the official ping-pong sampler callback's `denoised`
  clean-latent estimate at callback indices 0, 1, 2, and 3, decoded with the
  same SA3 autoencoder after the final sample completes.
- Reference: the final Demucs label from the same bf16 four-step trajectory.
- Comparator: independent one-step generation with the same prompt and seed.
- Detector: `htdemucs`, split=True, overlap=0.1, near-silent RMS < 1e-3,
  threshold 0.1791.

## Held-Out Results

| Method | AUROC | Balanced accuracy | Sensitivity | Specificity | MCC |
|---|---:|---:|---:|---:|---:|
| prompt_only | 0.785714 | 0.785714 | 1.000000 | 0.571429 | 0.377964 |
| independent_lowstep | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| same_trajectory_step_0 | 0.992063 | 0.988095 | 1.000000 | 0.976190 | 0.914732 |
| same_trajectory_step_1 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| same_trajectory_step_2 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| same_trajectory_step_3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| final_replay | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |


## Integrity Checks

- Final replay label agreement with the prior final: 95/96.
- The prior full scan used fp16; the callback replay follows the recovery brief's
  bf16 requirement. The single disagreement is retained as precision
  sensitivity, not silently overwritten.
- Aggregate generation wall-clock: 1765.539 seconds.
- Best pre-final same-trajectory checkpoint: `same_trajectory_step_1`.
- Best early checkpoint beats prompt-only and independent-low-step on both
  held-out AUROC and balanced accuracy: `false`.

## D7 Promotion Decision

The D7 observability-promotion criterion is not met on this pilot. Promotion
is **not authorized** unless that criterion is met, the separate SA3 human
threshold-calibration package passes, and the intervention survives calibrated
labeling plus fidelity/quality checks. This report establishes true
same-trajectory instrumentation; it does not by itself establish a
cross-backbone ADSR claim.

## Artifacts

- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_MANIFEST.jsonl`
- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_LEDGER.jsonl`
- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_DEMUCS_LEDGER.jsonl`
- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_METRICS.csv`
