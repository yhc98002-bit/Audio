# SA3 Medium Full 500-Prompt Prevalence Report

Generated: 2026-07-08

SA3_PREVALENCE_STATUS = FULL_GUIDE_COMPLETE

SA3_PREVALENCE_ROWS = 4000

SA3_DOMINANT_FAILURE_MODE = vocal_miss

## Inputs

- Generation manifest: `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_MANIFEST.jsonl`
- Generation ledger: `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_LEDGER.jsonl`
- Demucs scoring ledger: `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl`
- Summary CSV: `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_DEMUCS_SUMMARY.csv`
- Generation script: `paper_prep/sao/stable_audio_3_medium/run_sa3_prevalence.py`
- Demucs scoring script: `paper_prep/sao/stable_audio_3_medium/score_sa3_prevalence_demucs.py`

## Generation

- Prompt set: prompt rows from the run manifest, resolved against `configs/prompts/held_out.jsonl` and `configs/prompts/dev.jsonl`.
- Seeds: 8 deterministic seeds per prompt.
- Rows requested: 4000 generated `PASS` rows plus any failed rows in the ledger.
- Rows generated with `PASS`: 4000.
- WAV files present: 4000.
- Duration per clip: 8 seconds.
- Steps: 4.
- Model: ModelScope `stabilityai/stable-audio-3-medium`, local weights.

## Demucs Vocal-Presence Scoring

- Detector: `htdemucs` vocal-energy ratio.
- Fixed threshold: 0.1791, matching current paper-prep workers.
- Scored rows: 4000.
- Overall type-correct rows: 2172 / 4000 = 0.543000.
- 95% Wilson CI: [0.527528, 0.558389].

## Failure Mode

- Vocal misses: 1815.
- Instrumental leaks: 13.
- Other type failures: 0.

The dominant detected categorical failure mode is **vocal_miss**. This is a
first-pass detector readout, not a human validation of all possible SA3 musical
failure modes.

## By Requested Vocal Stratum

| Vocal stratum | Rows | Type-correct rate | 95% CI | Present rate |
|---|---:|---:|---:|---:|
| `instrumental` | 1512 | 0.991402 | [0.985345, 0.994969] | 0.008598 |
| `vocal` | 2488 | 0.270498 | [0.253407, 0.288298] | 0.270498 |

## Best-of-8 Selection

- Prompts: 500.
- Prompts with at least one type-correct seed: 325.
- Prompts with zero type-correct seeds: 175.
- Best-of-8 success rate: 0.650000.
- 95% Wilson CI: [0.607192, 0.690521].
- Mean per-prompt clean rate: 0.543000.
- Median per-prompt clean rate: 0.750000.

## Interpretation

This run clears the full guide target of at least 4,000 SA3 rows.
It does **not** support a broad second-backbone robustness claim. Instead, it
shows that SA3 Medium can be executed locally and that the same vocal/instrumental
constraint family remains measurable on a second backbone, with vocal-miss as the
dominant detected failure mode under the fixed Demucs detector.

Second-backbone paper wording should therefore be limited to a guide-scale
pilot/follow-up claim and should be interpreted together with the SA3
observability and intervention reports.
