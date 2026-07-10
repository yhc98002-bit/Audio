# SA3 Intervention Fidelity Audit

## Matched Design Audit

- Rows reconciled: 256/256.
- Prompts: 32/32; seeds per prompt: 8.
- Prompt ID, seed index, seed, duration, steps, and CFG match for every pair.
- Baseline present: 14/256.
- Intervention present: 191/256.

## Paired Prompt-Cluster Bootstrap

| Delta (intervention - baseline) | Mean | 95% CI |
|---|---:|---:|
| Demucs present | 0.691406 | [0.578125, 0.796875] |
| CLAP to original prompt | -0.028321 | [-0.063965, 0.008950] |
| Loudness dBFS | -0.677559 | [-1.417210, 0.084518] |
| Within-prompt embedding diversity | 0.046238 | [0.014146, 0.078150] |

Near-silent baseline/intervention rows: 0/0.

## D7 Interpretation

The categorical intervention effect is mechanically verified under matched
budgets. Human SA3 label calibration is still pending, so this audit cannot
promote the second-backbone claim by itself. A 20-pair blinded packet is staged
for optional PI fidelity/quality review. Any prompt-fidelity delta whose
interval includes a material negative effect must remain an explicit wording
constraint.

## Artifacts

- `paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_FIDELITY_RESULTS.csv`
- `paper_prep/sao/stable_audio_3_medium/intervention_fidelity/SA3_INTERVENTION_THRESHOLD_SENSITIVITY.csv`
- `paper_prep/sao/stable_audio_3_medium/intervention_fidelity/blinded_pairs/`
