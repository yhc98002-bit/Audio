# Exit-1 v2 Final Report

ITEM_1_EVALUATOR_COMPARISON_V2_STATUS = COMPLETE
evidence: `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md` (SHA-256 `34e7fd38918854e2a1701631605a5b73ed6c15d0e33305ff4f5eaa4ac90c28f8`); `analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json` (SHA-256 `5e8c4efc2466471aa6bf7be128b4edb5464f050e34d794ebfc79d3022ee705fe`)

ITEM_2_UNCONDITIONAL_BASE_RATE_V2_STATUS = COMPLETE
evidence: `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.md` (SHA-256 `3301e3b0510f764dd7160d026cb78a5e4d1681532c8a4220187c85593d611609`); `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.csv` (SHA-256 `ce4f9ea9a55eaac28639d4d02c3b2ef8b3868b86fef4c0ee96a48afda414d862`); `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2_AUDIT.json` (SHA-256 `d2b5082c2dc6be4530bb084f8090462dbd6581d6284d34a17930b3c2a8cfda34`)

ITEM_3_EVALUATOR_PANEL_UNIVERSE_STATUS = COMPLETE
evidence: `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md` (SHA-256 `34e7fd38918854e2a1701631605a5b73ed6c15d0e33305ff4f5eaa4ac90c28f8`); `analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json` (SHA-256 `5e8c4efc2466471aa6bf7be128b4edb5464f050e34d794ebfc79d3022ee705fe`)

ITEM_4_AUDIOSET_HUMAN_VOICE_WHITELIST_STATUS = PASS
evidence: `analysis_exit1_v2/EVALUATOR_AUDIOSET_HUMAN_VOICE_SCORES.csv` (SHA-256 `30dc3e07443a7a9f441b5dfe49dfb61f98f371cf04e6ce21b71506f995e2c2be`); `analysis_exit1_v2/EVALUATOR_AUDIOSET_HUMAN_VOICE_AUDIT.json` (SHA-256 `854b861a4e8047b6314ce8c7cd490bbf4bd2823820c055678dc0ff99682b20c0`); `analysis_exit1_v2/exit1_evaluator_v2.py` (SHA-256 `3ae073d782e3fbed2eb81dafb20f78e0f9c35d2ceba13a9d9433fa67ebfdb15e`); `tests/test_exit1_evaluator_v2.py` (SHA-256 `9457b3b2c65f342c4c6ecf69402967556de7d852d85efab4e59fccdf45f3898e`)

ITEM_5_RECIPE_CURVES_V2_STATUS = COMPLETE
evidence: `analysis_exit1_v2/RECIPE_CURVES_V2.md` (SHA-256 `3250cb9ca5974d1eb486818affd93e1bb53d4ac4512d5fdcaf615f1f25317fcb`); `analysis_exit1_v2/RECIPE_CURVES_V2.csv` (SHA-256 `6d3e4299cec7d00bedba54cfd7609885835f2d2f4c3fa505b44bbd83240aa5b9`); `analysis_exit1_v2/RECIPE_CURVES_V2_AUDIT.json` (SHA-256 `cb812bd753ec3d90dd8fb96bb899e6a613c64ee85a74762a264b0d47a3dc8b97`)

ITEM_6_MATCHED_NEUTRAL_CONTROL_STATUS = COMPLETE
evidence: `analysis_exit1_v2/neutral_control/NEUTRAL_CONTROL_REPORT.md` (SHA-256 `2f38287c973a7f62cd806d16eeefeaaf4dc63ee4f8200a91651398125c1f6af8`); `analysis_exit1_v2/neutral_control/FOUR_CELL_RESULTS.csv` (SHA-256 `384747b71631ef9be39950adad0f7bf060dbbba99c9cf675cfed09cfb0b93ae9`)

ITEM_7_EXIT1_V2_FINAL_REPORT_STATUS = COMPLETE
evidence: `analysis_exit1_v2/EXIT1_V2_FINAL_REPORT.md`

NEW_MUSIC_GENERATION = 0
evidence: `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2_AUDIT.json`; `analysis_exit1_v2/RECIPE_CURVES_V2_AUDIT.json`; `analysis_exit1_v2/EVALUATOR_AUDIOSET_HUMAN_VOICE_AUDIT.json`

TEST_SUITE_STATUS = PASS
evidence: `analysis_exit1_v2/DISPATCH_A_TEST_RESULTS.txt` (SHA-256 `c99c7628e1af8a8f54abddc7de884f1af8fef351b06d29d60d6b3db10790966c`); `tests/test_exit1_dispatch_a_completion.py` (SHA-256 `d18bb6c28f3ccd6d9ba73506bdbff19a25ccc1e84bc6ed8c976923490511e4f3`)

## Evaluator panel universes

- Panel A (primary): PI-only held-out Label-A gold; exact n=126 (117 decided positive, 9 decided negative, 0 unsure in metric rows). Power status: POWER_LIMITED.
- Panel B (supplemental): merged PI plus validated-judge held-out Label-A gold; exact n=451 (416 decided positive, 35 decided negative, 0 unsure in metric rows).

Panel B remains instrument-qualified and does not replace Panel A. Every Panel-A metric carries `POWER_LIMITED` because PI-only decided negatives are below 30.

## Item 4 clarification

The corrected AudioSet comparator is embodied in `analysis_exit1_v2/exit1_evaluator_v2.py` as the exact `HUMAN_VOICE_AUDIOSET_LABELS` whitelist and `audioset_human_voice_indices`. The regression tests are `test_audioset_human_voice_whitelist_uses_exact_labels` and the parametrized `test_audioset_nonhuman_or_synthetic_labels_are_excluded`, which explicitly cover speech synthesizer, synthetic singing, bird vocalization, whale vocalization, and singing bowl.

## Scope and provenance

- Branch: `codex/exit1-analysis-shared-20260716`.
- Implementation/evidence commit: `0265723`.
- The commit containing this report is the report-delivery commit and is stated in the delivery response; a Git commit cannot self-embed its own hash.
- This completion generated zero new music. Item 6's previously completed 192-clip neutral-control run remains separate, preserved evidence and was not rerun here.
- `analysis_exit1/` and `analysis_exit1_v2/superseded_1af4a8a/` are preserved.
- No PLAN, CLAIMS, W2, BOLT, checkpoint, or frozen ledger was modified.
