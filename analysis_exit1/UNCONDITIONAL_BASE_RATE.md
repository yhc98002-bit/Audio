# Exit-1 Unconditional Base Rate

Evidence role: PRIOR EVIDENCE

This analysis estimates vocal presence under the preregistered empty and neutral prompt distribution. It is PRIOR EVIDENCE for the vocal-bias discussion and is not causal proof of vocal bias.

Overall, the promoted Demucs AND PANNs instrument marked 171/256 clips as voice-present: 0.6680 (Wilson 95% CI [0.6082, 0.7228]).

| Natural stratum | n | Voice-present | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|
| `empty` | 128 | 91 | 0.7109 | [0.6272, 0.7824] |
| `neutral_text` | 128 | 80 | 0.6250 | [0.5386, 0.7041] |

## Frozen execution

- 256 retained 15-second clips: 128 empty-prompt and 128 neutral-text outputs.
- Seeds: `2036000000` through `2036000255`.
- Placement: `an12`, GPUs 0-7, TP1, eight independent replicas.
- Instrument: Demucs >= `0.0386395287` AND PANNs >= `0.0318181422`.
- All audio paths and SHA-256 values are retained in the tracked manifest and checksum file.

Prompt-level rows remain available in `UNCONDITIONAL_SCORES.csv`; the table above limits subgroup claims to the two preregistered natural strata.
