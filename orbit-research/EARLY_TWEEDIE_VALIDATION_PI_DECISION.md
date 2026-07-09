# Early-Tweedie Validation PI Decision Summary

Verifier report: `orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json`

Decision status: `STRONG_CANDIDATE_MAIN_APPLICATION`
Verifier status: `PASS_WITH_WARNINGS`
Warnings: `17`
Errors: `0`

## Counts

- prompts observed: `512`
- candidate records observed: `4096`
- manifest prompts: `512`
- prompt split counts: `{'dev': 256, 'held_out': 256}`

## Pre-Specified Threshold

- reward_fraction >= `0.98`
- compute_fraction <= `0.5`
- bottom-prune false-negative <= `0.05`

## Robust/Common Primary Schedule Rows

| schedule | compute_fraction | reward_fraction | winner_match | false_negative | median_regret | n_prompts |
|---|---:|---:|---:|---:|---:|---:|
| full_bon8 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 512 |
| schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1 | 0.5000 | 0.9864 | 0.5703 | 0.4297 | 0.0000 | 512 |
| schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1 | 0.5833 | 0.9913 | 0.6680 | 0.3320 | 0.0000 | 512 |
| schedule_c_sigma0.8_keep_top6_final_top1 | 0.8500 | 0.9987 | 0.9434 | 0.0566 | 0.0000 | 512 |
| bottom_prune_sigma0.8_remove_bottom25_final_top1 | 0.8500 | 0.9987 | 0.9434 | 0.0566 | 0.0000 | 512 |
| bottom_prune_sigma0.7_remove_bottom25_final_top1 | 0.8833 | 0.9998 | 0.9805 | 0.0195 | 0.0000 | 512 |
| random_prune_keep4_keep2_final_top1 | 0.5000 | 0.9571 | 0.2509 | 0.7491 | 0.0706 | 10240 |

## Robust/Common Primary Retention Rows

| sigma | top1 | top2 | top4 | bottom25_false_negative | n_prompts |
|---|---:|---:|---:|---:|---:|
| 0.9 | 0.2285 | 0.4121 | 0.6660 | 0.1348 | 512 |
| 0.8 | 0.3906 | 0.6094 | 0.8242 | 0.0566 | 512 |
| 0.7 | 0.4707 | 0.6797 | 0.9102 | 0.0195 | 512 |

## Threshold Readout

Efficient non-random pruning schedules meeting reward/compute threshold:
- `schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1`: reward_fraction=0.9864, compute_fraction=0.5000, winner_match=0.5703

Best bottom25 false-negative at sigma 0.8/0.7: `0.0195`
Bottom-prune threshold pass: `True`

## Interpretation Guardrails

- Use `common_robust_lcb / all` as the primary readout.
- Treat constant-metric rows, especially lyric-intelligibility rows on instrumental prompts, as diagnostic only.
- Do not claim final main-method status without PI sign-off.
- Do not launch pruning+RL from this result.

## Warnings

- all/lyric_intelligibility/final: 258/512 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- all/lyric_intelligibility/early_0.9: 400/512 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- all/lyric_intelligibility/early_0.8: 257/512 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- all/lyric_intelligibility/early_0.7: 251/512 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- vocal/lyric_intelligibility/early_0.9: 204/316 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- instrumental/lyric_intelligibility/final: 196/196 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- instrumental/lyric_intelligibility/early_0.9: 196/196 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- instrumental/lyric_intelligibility/early_0.8: 196/196 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- instrumental/lyric_intelligibility/early_0.7: 196/196 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:dev/lyric_intelligibility/final: 129/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:dev/lyric_intelligibility/early_0.9: 199/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:dev/lyric_intelligibility/early_0.8: 132/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:dev/lyric_intelligibility/early_0.7: 127/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:held_out/lyric_intelligibility/final: 129/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:held_out/lyric_intelligibility/early_0.9: 201/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:held_out/lyric_intelligibility/early_0.8: 125/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.
- split:held_out/lyric_intelligibility/early_0.7: 124/256 prompts have constant candidate scores; tie-driven retention/false-negative rows may be diagnostic only, especially for lyric_intelligibility.

