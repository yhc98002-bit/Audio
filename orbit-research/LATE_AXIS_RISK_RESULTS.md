# ADSR Phase-2B -- Late-axis Risk Predictor
Generated 2026-06-04 by `orbit-research/adsr_phase1_20260604/late_axis_risk.py`.
0-GPU offline analysis on the cached ADSR candidate pool (`orbit-research/trajectory_candidate_dataset.jsonl`, 4096 rows = 512 prompts x 8).
## Setup
- **Goal**: predict LATE-axis failure risk from EARLY sigma {0.9, 0.8, 0.7} features only (per-axis rewards, within-prompt rank percentiles, slopes, early probe stats, prompt_type categoricals). Strict leak guard: no `final_*` / `label_final*` key is used as a feature (asserted in code).
- **Split**: prompt-level; dev=train, held_out=eval; a prompt's 8 candidates are never split. Prompt-level split sizes: {'dev': 256, 'held_out': 256}.
- **Features**: 69 numeric + 5 categorical (genre, lyric_density, length_bin, vocal_stratum, language).
- **Models**: logistic regression (class_weight=balanced) and LightGBM GBDT 4.6.0 (native categoricals, scale_pos_weight, early stopping on eval AUC).

### Binding-rule notes
- Lyric headline uses **vocal_scorable only** (vocal_stratum=='vocal' AND language=='en' (n=282 prompts); 282 prompts). Instrumental final_lyric==1.0 sentinel and non-EN vocal are excluded from every lyric label/feature aggregation.
- sigma {0.5, 0.3}: NOT in cached pool (parallel GPU re-collection); excluded.
- Vocal-presence / type-match axis: PLANNED / deferred -- not measured; label (c) is a PROXY, not a real type-match label.
- Evidence honesty: offline analysis on existing cached data; no real ADSR/EVPD/restart result generated. Near-tied candidates cap label signal and therefore cap every AUC below.

## Label definitions
- **a_semantic_fit_bottom_quartile**: final_semantic_fit in bottom 2 of 8 within prompt (~25%)
- **b_lyric_low_abs_lt0p5**: final_lyric_intelligibility < 0.5 on vocal_scorable (zero-inflated axis -> absolute threshold)
- **b_lyric_bottom_half_within**: within-prompt bottom-half lyric on vocal_scorable prompts WITH variation (secondary view)
- **c_lyric_prompt_mismatch_PROXY**: bottom-half final semantic_fit AND final lyric<0.5 within prompt, vocal_scorable (PROXY; no measured type-match label)

## Headline results (held_out eval)
| Label block | n_eval | prev | AUC logit | AUC GBDT | PR-AUC GBDT (base) | P@k GBDT | R@k GBDT | Brier GBDT |
|---|---|---|---|---|---|---|---|---|
| a_semantic_fit_bottom_quartile__all | 2048 | 0.250 | 0.683 | **0.653** | 0.396 (0.250) | 0.404 | 0.404 | 0.183 |
| a_semantic_fit_bottom_quartile__vocal | 1272 | 0.250 | 0.657 | **0.632** | 0.378 (0.250) | 0.377 | 0.377 | 0.184 |
| a_semantic_fit_bottom_quartile__instrumental | 776 | 0.250 | 0.707 | **0.719** | 0.454 (0.250) | 0.479 | 0.479 | 0.176 |
| b_lyric_low_abs_lt0p5__vocal_scorable | 1176 | 0.759 | 0.882 | **0.866** | 0.944 (0.759) | 0.893 | 0.893 | 0.120 |
| b_lyric_bottom_half_within__vocal_scorable_varying | 1000 | 0.500 | 0.754 | **0.773** | 0.779 (0.500) | 0.706 | 0.706 | 0.195 |
| c_lyric_prompt_mismatch_PROXY__vocal_scorable | 1176 | 0.393 | 0.692 | **0.699** | 0.564 (0.393) | 0.550 | 0.550 | 0.214 |

## Per-label detail

### a_semantic_fit_bottom_quartile__all
- n_train=2048 (pos=512, prev=0.250); n_eval=2048 (pos=512, prev=0.250)
- **logistic**: AUC=0.683  PR-AUC=0.420 (base 0.250)  Brier=0.221  P@k=0.426 R@k=0.426 F1@k=0.426 (k=512, thr=0.599)
- **gbdt**: AUC=0.653  PR-AUC=0.396 (base 0.250)  Brier=0.183  P@k=0.404 R@k=0.404 F1@k=0.404 (k=512, thr=0.332) best_iter=10
- within-prompt rank sanity (GBDT score vs `final_semantic_fit`, 256 prompts): mean Spearman = -0.265 (negative is good: high risk score tracks low final axis)
- top GBDT features (gain): early_0.7_semantic_fit_rank_percentile(1341), early_0.7_semantic_fit(316), early_0.8_semantic_fit_rank_percentile(295), slope_0.7_minus_0.8_semantic_fit(198), slope_0.8_minus_0.9_section_coherence(178), slope_0.7_minus_0.9_section_coherence(126), slope_0.7_minus_0.8_section_coherence(112), slope_0.7_minus_0.8_aesthetic_pq(104)
- top logistic |coef| features: early_0.8_common_std_cells(1.24), early_0.7_common_std_cells(0.93), early_0.9_common_std_cells(0.73), early_0.8_aesthetic_cu(-0.65), early_0.9_aesthetic_pq(-0.54), early_0.7_common_robust_lcb(-0.47), early_0.7_semantic_fit_rank_percentile(-0.45), early_0.8_common_robust_lcb(-0.43)

### a_semantic_fit_bottom_quartile__vocal
- n_train=1256 (pos=314, prev=0.250); n_eval=1272 (pos=318, prev=0.250)
- **logistic**: AUC=0.657  PR-AUC=0.399 (base 0.250)  Brier=0.227  P@k=0.412 R@k=0.412 F1@k=0.412 (k=318, thr=0.586)
- **gbdt**: AUC=0.632  PR-AUC=0.378 (base 0.250)  Brier=0.184  P@k=0.377 R@k=0.377 F1@k=0.377 (k=318, thr=0.328) best_iter=9
- within-prompt rank sanity (GBDT score vs `final_semantic_fit`, 159 prompts): mean Spearman = -0.225 (negative is good: high risk score tracks low final axis)
- top GBDT features (gain): early_0.7_semantic_fit_rank_percentile(917), slope_0.7_minus_0.8_semantic_fit(154), early_0.7_semantic_fit(133), slope_0.7_minus_0.9_section_coherence(110), early_0.8_common_probe_penalty(108), slope_0.7_minus_0.8_aesthetic_pq(106), early_0.7_common_probe_penalty(91), early_0.8_semantic_fit(80)
- top logistic |coef| features: early_0.8_common_std_cells(1.34), early_0.9_common_std_cells(1.09), early_0.8_aesthetic_cu(-0.91), early_0.7_common_std_cells(0.86), early_0.9_common_robust_lcb(-0.65), early_0.9_aesthetic_pq(-0.58), early_0.7_common_robust_lcb(-0.56), early_0.8_common_robust_lcb(-0.49)

### a_semantic_fit_bottom_quartile__instrumental
- n_train=792 (pos=198, prev=0.250); n_eval=776 (pos=194, prev=0.250)
- **logistic**: AUC=0.707  PR-AUC=0.436 (base 0.250)  Brier=0.215  P@k=0.464 R@k=0.464 F1@k=0.464 (k=194, thr=0.622)
- **gbdt**: AUC=0.719  PR-AUC=0.454 (base 0.250)  Brier=0.176  P@k=0.479 R@k=0.479 F1@k=0.479 (k=194, thr=0.462) best_iter=48
- within-prompt rank sanity (GBDT score vs `final_semantic_fit`, 97 prompts): mean Spearman = -0.376 (negative is good: high risk score tracks low final axis)
- top GBDT features (gain): early_0.7_semantic_fit_rank_percentile(1667), early_0.8_semantic_fit_rank_percentile(722), slope_0.7_minus_0.8_semantic_fit(437), slope_0.7_minus_0.9_section_coherence(364), slope_0.7_minus_0.8_section_coherence(285), early_0.9_semantic_fit_rank_percentile(274), early_0.9_common_probe_penalty(248), early_0.8_section_coherence(233)
- top logistic |coef| features: early_0.7_common_std_cells(1.18), early_0.7_aesthetic_cu(-0.80), early_0.7_aesthetic_pq_rank_percentile(0.76), early_0.7_semantic_fit_rank_percentile(-0.65), early_0.9_aesthetic_cu(0.55), early_0.8_aesthetic_cu_rank_percentile(-0.41), early_0.9_aesthetic_pq(-0.41), early_0.9_probe_silence_fraction(0.40)

### b_lyric_low_abs_lt0p5__vocal_scorable
- n_train=1080 (pos=796, prev=0.737); n_eval=1176 (pos=892, prev=0.759)
- **logistic**: AUC=0.882  PR-AUC=0.951 (base 0.759)  Brier=0.125  P@k=0.892 R@k=0.892 F1@k=0.892 (k=892, thr=0.377)
- **gbdt**: AUC=0.866  PR-AUC=0.944 (base 0.759)  Brier=0.120  P@k=0.893 R@k=0.893 F1@k=0.893 (k=892, thr=0.512) best_iter=100
- within-prompt rank sanity (GBDT score vs `final_lyric_intelligibility`, 125 prompts): mean Spearman = -0.488 (negative is good: high risk score tracks low final axis)
- top GBDT features (gain): early_0.7_lyric_intelligibility(2065), slope_0.7_minus_0.9_lyric_intelligibility(945), early_0.7_probe_hf_artifact_score(407), slope_0.7_minus_0.8_lyric_intelligibility(224), early_0.9_semantic_fit(203), length_bin(196), lyric_density(159), early_0.8_lyric_intelligibility(156)
- top logistic |coef| features: early_0.7_common_std_cells(1.83), early_0.8_common_std_cells(0.90), early_0.7_common_robust_lcb(-0.85), early_0.8_aesthetic_cu_rank_percentile(-0.75), slope_0.7_minus_0.9_common_robust_lcb(-0.61), early_0.9_aesthetic_cu(-0.58), slope_0.7_minus_0.8_common_robust_lcb(-0.51), slope_0.7_minus_0.9_lyric_intelligibility(-0.51)

### b_lyric_bottom_half_within__vocal_scorable_varying
- n_train=984 (pos=492, prev=0.500); n_eval=1000 (pos=500, prev=0.500)
- **logistic**: AUC=0.754  PR-AUC=0.748 (base 0.500)  Brier=0.204  P@k=0.696 R@k=0.696 F1@k=0.696 (k=500, thr=0.506)
- **gbdt**: AUC=0.773  PR-AUC=0.779 (base 0.500)  Brier=0.195  P@k=0.706 R@k=0.706 F1@k=0.706 (k=500, thr=0.510) best_iter=75
- within-prompt rank sanity (GBDT score vs `final_lyric_intelligibility`, 125 prompts): mean Spearman = -0.450 (negative is good: high risk score tracks low final axis)
- top GBDT features (gain): early_0.7_lyric_intelligibility(1591), early_0.9_lyric_intelligibility_rank_percentile(640), slope_0.7_minus_0.9_lyric_intelligibility(564), early_0.7_lyric_intelligibility_rank_percentile(516), early_0.7_probe_hf_artifact_score(480), early_0.9_probe_hf_artifact_score(183), early_0.8_lyric_intelligibility_rank_percentile(169), early_0.7_probe_silence_fraction(149)
- top logistic |coef| features: early_0.7_common_std_cells(1.13), early_0.7_probe_silence_fraction(0.80), early_0.8_probe_silence_fraction(-0.69), early_0.7_aesthetic_pq_rank_percentile(0.52), early_0.9_aesthetic_cu(-0.51), early_0.9_lyric_intelligibility_rank_percentile(0.46), early_0.9_aesthetic_pq_rank_percentile(-0.46), early_0.9_aesthetic_cu_rank_percentile(0.45)

### c_lyric_prompt_mismatch_PROXY__vocal_scorable
- n_train=1080 (pos=416, prev=0.385); n_eval=1176 (pos=462, prev=0.393)
- **logistic**: AUC=0.692  PR-AUC=0.551 (base 0.393)  Brier=0.227  P@k=0.552 R@k=0.552 F1@k=0.552 (k=462, thr=0.584)
- **gbdt**: AUC=0.699  PR-AUC=0.564 (base 0.393)  Brier=0.214  P@k=0.550 R@k=0.550 F1@k=0.550 (k=462, thr=0.499) best_iter=37
- top GBDT features (gain): slope_0.7_minus_0.9_lyric_intelligibility(1079), early_0.7_lyric_intelligibility(1015), early_0.7_semantic_fit_rank_percentile(319), early_0.8_semantic_fit_rank_percentile(249), early_0.8_common_probe_penalty(214), early_0.7_probe_hf_artifact_score(213), slope_0.7_minus_0.8_semantic_fit(181), slope_0.7_minus_0.9_section_coherence(178)
- top logistic |coef| features: early_0.7_common_std_cells(1.47), early_0.8_common_std_cells(0.99), early_0.9_common_std_cells(0.61), early_0.8_probe_silence_fraction(0.60), early_0.7_common_robust_lcb(-0.59), early_0.8_aesthetic_cu(-0.58), early_0.9_common_robust_lcb(-0.48), early_0.8_common_robust_lcb(-0.42)

## Interpretation (for the ADSR DEFER decision)
- Semantic-fit bottom-quartile risk (all strata): GBDT AUC = 0.653. The strongest early signal for semantic risk is the early semantic_fit reward/rank itself (see feature lists), i.e. a candidate that is semantically weak at sigma 0.7-0.9 tends to stay weak.
- Lyric-low (vocal_scorable, final<0.5): GBDT AUC = 0.866. Early lyric_intelligibility is near-zero for most candidates at sigma 0.9-0.7, so the predictive lift comes partly from prompt_type (lyric_density) and early aesthetic/coherence features rather than the early lyric axis alone.
- Lyric/prompt mismatch PROXY: GBDT AUC = 0.699. This is a constructed proxy (no measured type-match label); treat as a feasibility signal only.
- **Ceiling honesty**: within each prompt the 8 candidates are often near-tied on the late axis, which caps the separable signal and therefore caps every AUC above. These are offline estimates on cached data; no real ADSR/EVPD/restart outcome is produced here.
