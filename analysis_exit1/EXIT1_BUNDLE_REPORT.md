# Exit-1 Analysis Bundle Report

EVALUATOR_TABLE_STATUS = COMPLETE
evidence: `analysis_exit1/EVALUATOR_COMPARISON_TABLE.md`; `analysis_exit1/EVALUATOR_COMPARISON_AUDIT.json`; `analysis_exit1/EVALUATOR_PREP_AUDIT.json`; `analysis_exit1/EVALUATOR_MEDIA_MANIFEST.csv`; `analysis_exit1/EVALUATOR_WHISPER_SCORES.csv`; `analysis_exit1/EVALUATOR_AUDIOSET_SCORES.csv`; `analysis_exit1/EVALUATOR_AUDIOSET_MODEL_METADATA.json`; `analysis_exit1/EVALUATOR_DETECTOR_FILL_SCORES.csv`

RECIPE_CURVES_STATUS = COMPLETE
evidence: `analysis_exit1/RECIPE_CURVES.md`; `analysis_exit1/RECIPE_CURVES.csv`; `analysis_exit1/RECIPE_CURVES_AUDIT.json`

UNCONDITIONAL_BASE_RATE_STATUS = COMPLETE
evidence: `analysis_exit1/UNCONDITIONAL_BASE_RATE.md`; `analysis_exit1/neutral_prompts.csv`; `analysis_exit1/UNCONDITIONAL_PREREGISTRATION.json`; `analysis_exit1/UNCONDITIONAL_GENERATION_MANIFEST.csv`; `analysis_exit1/UNCONDITIONAL_SCORES.csv`; `analysis_exit1/UNCONDITIONAL_AUDIO_SHA256SUMS`; `analysis_exit1/UNCONDITIONAL_RUN_MANIFEST.json`

TEST_SUITE_STATUS = PASS
evidence: `analysis_exit1/TEST_RESULTS.txt`; `analysis_exit1/TEST_RESULT_SUMMARY.json`

## Commits

- Frozen prompt/seed preregistration commit: `3e391303464d10e0f7eaafbd840d615e49da6a4c`.
- Analysis, retained-audio evidence, and test-results commit: `828280e`.

## Test result

- Command: `pytest -q`.
- Exit code: `0`.
- Passed: `362`; failed: `0`; errors: `0`.
- Output SHA-256: `d9a717aa94305e73e76a3dc582b685461d649906b4e4019e0bc715a5b9f17abd`.

## Scope

This is an Exit-1 analysis bundle. It does not change PLAN/CLAIMS or gate semantics. The unconditional estimate is labeled PRIOR EVIDENCE and is not causal proof.
