# Exit-1 Unconditional Base Rate v2

**Evidence role: PRIOR EVIDENCE, NOT CAUSAL PROOF.**

This analysis re-scores the retained preregistered empty/neutral outputs. It estimates vocal presence under those prompt cells; it does not establish a causal vocal-generation bias.

## Primary - promoted OR

Overall: **187/256 voice-present** and **69/256 voice-absent**; rate 0.7305, Wilson 95% CI [0.6730, 0.7811].

| Natural stratum | n | Voice-present | Voice-absent | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| `empty` | 128 | 98 | 30 | 0.7656 | [0.6852, 0.8306] |
| `neutral_text` | 128 | 89 | 39 | 0.6953 | [0.6108, 0.7684] |

Canonical parse:

> - Selected family: `or`.

- Demucs threshold: `0.03161777090281248`.
- PANNs threshold: `0.04403413645923138`.
- T6 result SHA-256: `2ec9f12fd9008dae0e32675fcdaaf9e7a22fe0ed7006dd310b665b1e82be2ff2`.

## Sensitivity only - historical AND

These rows reproduce the earlier operationalization and are not the primary v2 estimate.

| Natural stratum | n | Voice-present | Voice-absent | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| `overall` | 256 | 171 | 85 | 0.6680 | [0.6082, 0.7228] |
| `empty` | 128 | 91 | 37 | 0.7109 | [0.6272, 0.7824] |
| `neutral_text` | 128 | 80 | 48 | 0.6250 | [0.5386, 0.7041] |

Historical rule: Demucs >= `0.038639528676867485` AND PANNs >= `0.03181814216077328`.

## Frozen source

No music was generated for this v2 analysis. It uses the 256 retained clips and their frozen Demucs/PANNs scores from `analysis_exit1/`.
The frozen 256-row universe includes one source row flagged near-silent (`exit1_uncond_111`). It remains in the denominator to preserve the preregistered source universe; this is an explicit validity limitation, not an unreported exclusion.
