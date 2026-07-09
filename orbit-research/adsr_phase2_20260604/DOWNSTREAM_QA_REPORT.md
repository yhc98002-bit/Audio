# ADSR Downstream Labeling/Mel — Strict QA Report

**ALL HARD CHECKS PASS: True**

## Hard criteria
- ✅ **1_audio_paths_resolved** — {"records_with_missing_wav": 0}
- ✅ **2_no_missing_wav_symlinks** — {"prompts_bad_8final_24early": 0}
- ✅ **3_no_duplicate_pid_cand** — {"records": 4096, "records_distinct": 4096, "labels_total": 4096, "labels_distinct": 4096, "label_set_equals_record_set": true}
- ✅ **4_vocal_presence_labels** — {"ok_labels": 4096, "expected": 4096, "with_vocal_ratio": 4096, "prompts_with_exact_0to7": 512, "missing_labels": 0}
- ✅ **5_early_sigma_mel** — {"mel_npy_files": 12288, "expected": 12288, "distinct_referenced_paths": 12288, "labels_missing_sigma_key": 0, "mel_files_referenced_missing": 0, "basename_mismatch": 0, "referenced_names_eq_expected": true}
- ✅ **6_vocal_scorable_preserved** — {"prompts": 512, "vocal": 316, "instrumental": 196, "en_vocal_scorable": 282, "expected_en_vocal": 282, "non_en_vocal_floored_excluded": 34, "rec_keys_eq_canonical_keys": true, "prompt_set_eq_canonical": true, "per_candidate_strata_drift": 0, "has_lyrics_consistent": true}
- ✅ **7_lyric_sentinel_masked** — {"instrumental_candidates": 1568, "sentinel_eq_1.0": 1568, "sentinel_frac": 1.0, "scoped_n": 2256, "expected_scoped_n": 2256, "scoped_has_instrumental_leak": false, "scoped_has_nonEN_leak": false, "lyric_headline_scoped_vocal_scorable_mean": 0.2451, "naive_pooled_mean_CONTAMINATED_do_not_use": 0.5189, "note": "headline scoped to vocal_scorable (EN-vocal); pooled value is inflated by the 1.0 instrumental sentinel. Canonical Track-A ETP@50% lyric headline = 0.682 (EN-vocal n=282)."}

## Report metrics
- **label_coverage_prompts**: 512/512
- **label_coverage_frac**: 1.0
- **candidates_labeled**: 4096
- **failure_count**: 0
- **ambiguous_count**: 557
- **ambiguous_def**: |vocal_energy_ratio - threshold(0.1791)| < 0.05
- **near_silent_count**: 0
- **gpu_hours_used**: 0.0
- **compute_note**: labeling is CPU-only (Demucs htdemucs forced device=cpu); ~0 GPU-h
- **type_error_prevalence_candidate**: 0.23
- **type_error_per_stratum**: {'vocal': {'n_cand': 2528, 'type_error_rate': 0.2108}, 'instrumental': {'n_cand': 1568, 'type_error_rate': 0.2608}}
- **early_sigma_scalar_AUC_heldout**: 0.7406
- **phase2a_ready**: True
- **phase2a_gate**: EVPD training is PI-gated (CLAUDE.md hard boundary) — DO NOT launch without explicit approval.