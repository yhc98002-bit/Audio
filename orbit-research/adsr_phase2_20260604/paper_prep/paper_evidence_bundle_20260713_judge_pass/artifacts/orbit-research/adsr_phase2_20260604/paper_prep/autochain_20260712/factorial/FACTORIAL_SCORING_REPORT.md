# Instrumental Factorial Scoring

`FACTORIAL_SCORING_STATUS = COMPLETE_PROMOTED_INSTRUMENT_DRAFT`

All 3,072 preregistered clips were scored with the mechanically promoted instrument and the train-only calibrated model. Publication adoption remains blocked on both W2 signatures.

| Condition | Calibrated satisfaction | 95% prompt-bootstrap CI | Corrected hard satisfaction | CLAP | Audiobox PQ | Near silent | Diversity distance |
|---|---:|---:|---:|---:|---:|---:|---:|
| plain_baseline | 0.4384 | [0.3543, 0.5254] | 0.3398 | 0.2982 | 6.8404 | 0.0020 | 0.3249 |
| negative_text | 0.3876 | [0.3165, 0.4575] | 0.2637 | 0.2703 | 6.6923 | 0.0000 | 0.3337 |
| positive_text | 0.6608 | [0.5668, 0.7478] | 0.5527 | 0.3061 | 6.9064 | 0.0000 | 0.3437 |
| sampler_only | 0.4584 | [0.3583, 0.5607] | 0.3594 | 0.3142 | 6.9251 | 0.0020 | 0.3222 |
| negative_sampler | 0.4002 | [0.3221, 0.4796] | 0.2695 | 0.2826 | 6.7248 | 0.0000 | 0.3323 |
| positive_sampler | 0.6798 | [0.5827, 0.7688] | 0.5684 | 0.3158 | 6.9776 | 0.0000 | 0.3414 |

## Interaction Contrasts

- negative: -0.007493.
- positive: -0.001044.

Best draft calibrated condition: `positive_sampler` (0.6798). The existing 20-pair blinded PI spot-check bundle remains staged and unscored.
