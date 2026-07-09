# Batch 2 — Stage 0 Pre-flight Verification

**ALL PRE-FLIGHT CHECKS PASS: True**

Dataset: `adsr_recollect_20260604_full01_merged` + `orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl` + `orbit-research/adsr_phase2_20260604/mel`

| # | Check | Pass | Detail |
|---|---|---|---|
| 1 | 1_4096_distinct_records | ✅ | {"records": 4096, "distinct": 4096} |
| 2 | 2_512_prompts | ✅ | {"prompts": 512} |
| 3 | 3_final_vocal_labels_all_4096 | ✅ | {"ok_labels": 4096, "cover_records": true} |
| 4 | 4_early_mels_present | ✅ | {"mel_npy_files": 12288, "distinct_pid_ci_sigma_present": 12288, "expected": 12288, "labels_missing_sigma_key": 0} |
| 5 | 5_vocal_scorable_en_vocal_282 | ✅ | {"en_vocal": 282, "expected": 282, "keys_eq_canonical": true} |
| 6 | 6_instrumental_sentinel_maskable | ✅ | {"instrumental_prompts": 196, "instr_candidates": 1568, "all_sentinel_1.0": true} |
| 7 | 7_non_en_vocal_excluded_identifiable | ✅ | {"non_en_vocal_prompts": 34, "expected": 34} |
| 8 | 8_prompt_level_split_preserved | ✅ | {"splits": {"dev": 256, "held_out": 256}, "split_consistent_within_prompt": true} |