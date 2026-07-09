# Trajectory Candidate Dataset Card

Generated UTC: `2026-06-03T22:20:36Z`

## Source

- Existing Early-Tweedie BoN-8 validation artifacts only.
- No new generation, training, pruning+RL, Phase D, human evaluation, or reward-definition change was launched by dataset construction.

## Files

- Dataset JSONL: `orbit-research/etv_lyricfix_final_20260603/trajectory_candidate_dataset.jsonl`
- Source record files: `['runs/early_tweedie_validation_final_lyricfix_20260603/shard00/candidate_records.jsonl']`

## Size

- Candidate records: `4096`
- Prompts: `512`
- BoN candidates per prompt: `8`
- Original split prompts: `{'dev': 256, 'held_out': 256}`
- Analysis split prompts: `{'train': 194, 'validation': 62, 'test': 256}`
- Vocal/instrumental prompts: `{'vocal': 316, 'instrumental': 196}`

## Split Rule

- Splits are by `prompt_id`, never by candidate.
- `held_out` prompts are used only as `test` for learned-verifier evaluation.
- `dev` prompts are deterministically split into train/validation by prompt hash.

## Main Fields

- prompt/candidate metadata: `prompt_id`, `candidate_id`, `candidate_uid`, `split`, `analysis_split`, `vocal_stratum`, `genre`, `candidate_seed`.
- final labels: final reward axes, `final_common_robust_lcb`, final rank, top1/top2/top4 labels.
- early features: sigma 0.9/0.8/0.7 reward vectors, robust axes, probes, ranks within prompt, and step metadata.
- compute metadata: full BoN-8 step units and per-candidate early step units.

## Leakage Controls

- Learned models may use only early sigma features and prompt metadata.
- Final labels are used only as offline training targets or evaluation labels.
- Risk thresholds are calibrated on validation prompts and evaluated on held-out/test prompts.
