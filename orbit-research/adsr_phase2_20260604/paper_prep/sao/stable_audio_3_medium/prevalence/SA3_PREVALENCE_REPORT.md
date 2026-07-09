# SA3 Medium Prevalence Pilot Report

Generated: 2026-07-08

SA3_PREVALENCE_STATUS = PILOT_COMPLETE

SA3_PREVALENCE_ROWS = 1024

SA3_DOMINANT_FAILURE_MODE = vocal_miss

## Inputs

- Generation manifest: `paper_prep/sao/stable_audio_3_medium/prevalence/SA3_PREVALENCE_MANIFEST.jsonl`
- Generation ledger: `paper_prep/sao/stable_audio_3_medium/prevalence/SA3_PREVALENCE_LEDGER.jsonl`
- Demucs scoring ledger: `paper_prep/sao/stable_audio_3_medium/prevalence/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
- Summary CSV: `paper_prep/sao/stable_audio_3_medium/prevalence/SA3_PREVALENCE_DEMUCS_SUMMARY.csv`
- Generation script: `paper_prep/sao/stable_audio_3_medium/run_sa3_prevalence.py`
- Demucs scoring script: `paper_prep/sao/stable_audio_3_medium/score_sa3_prevalence_demucs.py`

## Generation

- Prompt set: first 128 prompts from `orbit-research/adsr_phase2_20260604/batch3/batch3_selected_prompts_256.jsonl`, resolved against `configs/prompts/held_out.jsonl` and `configs/prompts/dev.jsonl`.
- Seeds: 8 deterministic seeds per prompt.
- Rows requested: 1,024.
- Rows generated with `PASS`: 1024.
- WAV files present: 1024.
- Duration per clip: 8 seconds.
- Steps: 4.
- Model: ModelScope `stabilityai/stable-audio-3-medium`, local weights.

## Demucs Vocal-Presence Scoring

- Detector: `htdemucs` vocal-energy ratio.
- Fixed threshold: 0.1791, matching current paper-prep workers.
- Scored rows: 1024.
- Overall type-correct rows: 440 / 1024 = 0.429688.
- 95% Wilson CI: [0.399685, 0.460215].

## Failure Mode

- Vocal misses: 582.
- Instrumental leaks: 2.
- Other type failures: 0.

The dominant detected categorical failure mode is **vocal_miss**. This is a
first-pass detector readout, not a human validation of all possible SA3 musical
failure modes.

## By Requested Vocal Stratum

| Vocal stratum | Rows | Type-correct rate | 95% CI | Present rate |
|---|---:|---:|---:|---:|
| `instrumental` | 248 | 0.991935 | [0.971077, 0.997786] | 0.008065 |
| `vocal` | 776 | 0.250000 | [0.220815, 0.281648] | 0.250000 |

## Best-of-8 Selection

- Prompts: 128.
- Prompts with at least one type-correct seed: 69.
- Prompts with zero type-correct seeds: 59.
- Best-of-8 success rate: 0.539062.
- 95% Wilson CI: [0.452828, 0.623020].
- Mean per-prompt clean rate: 0.429688.
- Median per-prompt clean rate: 0.125000.

## Interpretation

This pilot clears the generation acceptance threshold of at least 1,024 SA3 rows.
It does **not** support a broad second-backbone robustness claim. Instead, it
shows that SA3 Medium can be executed locally and that the same vocal/instrumental
constraint family remains measurable on a second backbone, with vocal-miss as the
dominant detected failure mode under the fixed Demucs detector.

Second-backbone paper wording should therefore be limited to a pilot/follow-up
claim unless additional SA3 intervention and observability runs are completed.
