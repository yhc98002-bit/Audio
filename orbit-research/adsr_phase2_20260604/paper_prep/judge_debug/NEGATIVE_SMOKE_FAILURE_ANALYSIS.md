# Negative Smoke Failure Analysis

Generated: 2026-07-07

CSV table: `paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_TABLE.csv`

## Scope

This file diagnoses the repaired-smoke clips whose original expected label was `no` but whose majority judge result was `yes` for Qwen Plus and/or Flash.

## Conclusions

- Are the negatives actually safe negatives? **No.** Four expected-negative clips were automatic-label negatives, not human-adjudicated safe negatives, and both Qwen models described voice/speech/rap-like content in them.
- Is Qwen overcalling vocals? **Not proven.** The failure set is contaminated by unsafe negative labels. Qwen may still be permissive because the prompt counts spoken word, rap, vocal chops, choir, and humming as voice, but this smoke cannot isolate that from bad negatives.
- Is the client/parser broken? **No evidence.** The raw first-line labels and parser outputs agree for the failed negatives; parser output is concrete `yes`, not abstain.
- Is the prompt too permissive? **The prompt is intentionally inclusive for A-prime.** It may overcall voice-like timbre for marginal negatives, so v2 uses ultra-clear detector-agreed negatives and records dense-instrumental probes separately.
- Is the audio conversion broken? **No evidence from this failure set.** The failed smoke sent 16 kHz mono WAV transcodes; durations, sample rates, loudness, and ffprobe validity are present. Native FLAC was not sent for these failed clips, so v2 keeps WAV and separately logs any FLAC-capable probe.
- Exact repair: **replace the unsafe negative half of the smoke with conservative detector-agreed instrumental clips**, unit-test the parser, then rerun Plus and Flash on `judge_smoke_v2_manifest.csv`.

## Failed Negative Clips

| Clip | Expected derivation | Plus | Flash | Hypothesis |
|---|---|---|---|---|
| `aprime_0019_a00fb96bef52` | automatic repaired smoke manifest; prompt_id=genreinstr_ambient; demucs_ratio=0.00741; panns=0.08209; requested_vocal=0; present=0; source_path=batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/keep/genre_instr/genreinstr_ambient/none_s56_2026800056.flac | yes | yes | bad negative label / ambiguous audio |
| `aprime_0209_99f9f4b0fa3f` | automatic repaired smoke manifest; prompt_id=held_out_0153; demucs_ratio=0.00021; panns=0.12239; requested_vocal=0; present=0; source_path=batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/keep/istrong_instr/held_out_0153/I_strong_s106_2028205106.flac | yes | yes | bad negative label / ambiguous audio |
| `aprime_0323_70e420c71e92` | automatic repaired smoke manifest; prompt_id=genreinstr_electronic; demucs_ratio=0.00097; panns=0.41048; requested_vocal=0; present=0; source_path=batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/keep/genre_instr/genreinstr_electronic/none_s32_2026600032.flac | yes | yes | bad negative label / ambiguous audio |
| `aprime_0332_2d40c0a2a223` | automatic repaired smoke manifest; prompt_id=held_out_0080; demucs_ratio=0.00662; panns=0.21979; requested_vocal=0; present=0; source_path=batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/keep/bon256/held_out_0080/none_s470_2027400470.flac | yes | yes | bad negative label / ambiguous audio |
