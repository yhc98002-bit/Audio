# Exit-1 Evaluator Comparison

The common comparison uses the provenance-enforced 690-row Label-A instrument (238 decided train rows; 451 decided held-out rows; 1 unsure row excluded from metric denominators). Prompt clusters and duplicate media are disjoint across the deterministic split. Only PANNs-only, Whisper, and AudioSet thresholds were selected on train; the two existing Demucs operationalizations were applied unchanged.
Historical detector scores were preserved; 125 unique media item(s) without a historical score were evaluated by the unchanged frozen W2 Demucs/PANNs backend. This supplemental scoring introduced no human labels.

| Instrument | Frozen operationalization | Sensitivity (95% CI) | Specificity (95% CI) | Balanced accuracy (95% CI) | MCC (95% CI) |
|---|---|---:|---:|---:|---:|
| Legacy Demucs energy ratio | Demucs >= 0.1791 | 0.202 [0.153, 0.264] | 0.829 [0.667, 0.971] | 0.515 [0.436, 0.594] | 0.020 [-0.084, 0.127] |
| Demucs AND PANNs | Demucs >= 0.0386395287 AND PANNs >= 0.0318181422 | 0.825 [0.768, 0.892] | 0.886 [0.771, 0.973] | 0.855 [0.792, 0.917] | 0.451 [0.320, 0.613] |
| PANNs only | PANNs >= 0.04879267 (train-selected) | 0.969 [0.946, 0.988] | 0.857 [0.727, 0.963] | 0.913 [0.848, 0.968] | 0.752 [0.625, 0.875] |
| Whisper transcript | non-empty AND confidence >= 0.28481825 (train-selected) | 0.498 [0.429, 0.572] | 0.829 [0.708, 0.939] | 0.663 [0.595, 0.732] | 0.175 [0.098, 0.257] |
| AudioSet tagger | speech/singing max >= 0.05733276 (train-selected) | 0.957 [0.933, 0.977] | 0.771 [0.565, 0.958] | 0.864 [0.761, 0.957] | 0.650 [0.478, 0.810] |

## Locked historical restatement

The earlier 105-row PI-gold held-out record is restated, not re-tuned: legacy Demucs sensitivity/specificity/balanced accuracy/MCC = 0.295918/0.571429/0.433673/-0.071886; Demucs AND PANNs = 0.897959/0.714286/0.806122/0.436436.

## Inference and uncertainty

Whisper is the checksum-frozen `large-v3` model. A transcript counts only when at least one alphanumeric segment is non-empty and the maximum segment `exp(avg_logprob) * (1 - no_speech_prob)` clears the train-selected floor. The AudioSet row uses a separate AST-family audio classifier and the maximum probability across frozen speech/singing-class tags and overlapping windows. All intervals are percentile 95% prompt-cluster bootstraps with 10,000 replicates and seed `2026071602`.

No new human labels were collected. The gold contains 190 `pi:Richard` rows and 500 rows from the provenance-enforced, disjoint-gold-validated judge instrument.
