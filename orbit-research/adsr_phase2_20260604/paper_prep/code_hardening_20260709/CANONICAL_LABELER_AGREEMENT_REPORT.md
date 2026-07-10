# Canonical Labeler Cross-Implementation Audit

`CANONICAL_LABELER_AGREEMENT_STATUS = PASS`

Two independent project call paths were compared under identical per-clip RNG
seeds: `scripts.batch3_online_harness.GateLabeler` and
`mprm.rewards.demucs.DemucsVocalStem.vocal_energy_ratio`.

| Measure | Result |
|---|---:|
| Original clips | 200 |
| Label agreement | 200/200 |
| Near-silent agreement | 200/200 |
| Maximum absolute ratio delta | 0.000000060507 |
| Device | cuda |
| Torch | 2.7.1+cu126 |

The audit verifies implementation agreement, not human validity of the Demucs
construct. A-prime remains human-gated.
