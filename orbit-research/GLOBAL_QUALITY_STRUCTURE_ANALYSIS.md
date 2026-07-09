# Global Quality Structure Analysis

Generated UTC: `2026-05-26T17:09:04.430753Z`

## Verdict

Track B status: `COMPLETE_CPU_ONLY`.

For ACE-Step short-form outputs, local-window rewards appear to track persistent global quality more than isolated local failures.

This is a cautious mechanism read from cached H3 local proxy vectors and C1 common-eval summaries. It is not a new held-out run, not human eval, and not source-separation evidence.

## Source Artifacts

- `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/results.jsonl`
- `orbit-research/TIME_UNIFORM_QUALITY_DIAGNOSTIC.json`
- `runs/phase_c1_common_downstream_eval_20260526_helper01`
- `runs/phase_c1_checkpoint_triage_eval_20260526`
- `orbit-research/phase_c1_learning_signal_audit_20260526/fixedwin_section_stepwise.csv`

## Primary H3 Globalness Summary

| metric | value |
|---|---:|
| h3_records | 256.000 |
| usable_primary_cells | 4.000 |
| primary_median_between_share | 0.584 |
| primary_median_between_within_ratio | 1.404 |
| primary_median_sign_consistency | 1.000 |
| primary_median_crossing_frequency | 0.000 |
| primary_median_globalness_index | 0.861 |
| primary_cells_between_share_ge_0_5 | 3.000 |
| primary_cells_crossing_frequency_zero | 4.000 |

Primary cells are CU-FW/CU-BW musicality and prompt-fit using the cached `human_pref_proxy_vector`. Coherence cells are treated cautiously because several cached local coherence vectors are degenerate. Human-pref proxy rows are de-duplicated by unit/axis/source in the summary because musicality appears under both sigma keys with the same proxy vector.

| unit | axis | sigma | n | between_share | ratio | sign_consistency | crossing_frequency | globalness_index |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| CU-BW | musicality | 0.6 | 256 | 0.475 | 0.904 | 1.000 | 0.000 | 0.825 |
| CU-BW | prompt_fit | 0.6 | 256 | 0.600 | 1.499 | 1.000 | 0.000 | 0.867 |
| CU-FW | musicality | 0.6 | 256 | 0.591 | 1.445 | 1.000 | 0.000 | 0.864 |
| CU-FW | prompt_fit | 0.6 | 256 | 0.577 | 1.362 | 1.000 | 0.000 | 0.859 |

## Top-Vs-Bottom Reward-Time Curves

Top and bottom quartiles are selected by each prompt's mean local proxy value. Across the primary cells, top-minus-bottom gaps keep the same positive sign across normalized time bins; crossing frequency is 0.0 for those cells. This favors a persistent-quality interpretation over a few isolated bad windows.

Caveat: top/bottom selection is in-sample, so gap magnitudes are descriptive rather than predictive. Also, because sign consistency is 1.0 and crossing frequency is 0.0 for all primary cells, the composite globalness index is a monotone transform of between-share in these data.

Plot-ready curve table:

- `orbit-research/global_quality_structure_analysis_20260527/top_bottom_reward_time_curves.csv`

## FixedWin Interpretation

CU-FW does not look like a clean isolated local-credit signal in the cached H3 vectors. Its primary musicality/prompt-fit cells have high between-song share and zero top-bottom curve crossings, close to CU-BW. This makes FixedWin more consistent with a stable local proxy for global quality than with true local failure localization.

C1 training traces also show FixedWin and Section process rewards move together over 1000 steps (Pearson 0.932, Spearman 0.904). This trace is training-time evidence, not a within-song local-failure test.

## C1 Common Eval Connection

| target | n | robust_lcb_mean | delta_vs_base | fixedwin_process | section_process |
|---|---:|---:|---:|---:|---:|
| base__base | 64 | 2.133676 | NA | NA | NA |
| m_fixedwin__step1000 | 64 | 2.145825 | 0.012149 | -1.677325 | -1.584986 |
| m_section__step1000 | 64 | 2.146055 | 0.012379 | -1.704717 | -1.575054 |
| r8a__step1000 | 64 | 2.145297 | 0.011621 | NA | NA |
| r8b__step1000 | 64 | 2.148166 | 0.014490 | NA | NA |

C1 common eval is not itself a time-local diagnostic, but it is consistent with the mechanism: Section and window-local PRM variants do not separate strongly on common downstream robust-LCB when evaluated with the same sampler and metric. This helps explain why Section/window-local PRM training may not yield strong improvement if local rewards mostly mirror persistent song-level quality.

## Demucs / Stem Features

No cached Demucs/stem feature files were found. No source separation or heavy Demucs job was launched.

## Output Tables

- `orbit-research/global_quality_structure_analysis_20260527/globalness_by_unit_axis_source.csv`
- `orbit-research/global_quality_structure_analysis_20260527/top_bottom_reward_time_curves.csv`
- `orbit-research/global_quality_structure_analysis_20260527/c1_common_eval_summary.csv`
- `orbit-research/global_quality_structure_analysis_20260527/c1_fixedwin_section_training_alignment.csv`

## Limitations

- Cached H3 proxy vectors are not human ratings.
- CU-LS is only applicable to vocal prompts and is exploratory.
- CU-FW coherence vectors are entirely constant; CU-BW coherence has near-zero within-prompt dynamic range. Coherence should not carry the conclusion.
- CU-MS and CU-NULL-rand-section have identical musicality/coherence value sets in the cached H3 artifact, so CU-NULL is informative mainly for prompt_fit.
- The globalness index adds no independent information beyond between-share for the primary cells because sign consistency is 1.0 and crossing frequency is 0.0.
- C1 common eval supports mechanism interpretation but is not a local-window failure test.
- No Phase D, human eval, pruning+RL, RL training, reward-definition change, sigma-policy change, or gate_v1 edit was performed.

## Recommendation

Use the result as Track B mechanism support: local-window rewards appear to be stable proxies for global quality in ACE-Step short-form outputs. Do not overclaim that all local failures are absent, or that PRM variants are proven ineffective.
