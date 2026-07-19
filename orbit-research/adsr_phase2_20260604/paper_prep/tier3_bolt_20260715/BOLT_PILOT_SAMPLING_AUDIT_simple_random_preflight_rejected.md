# BOLT Pilot Sampling Audit

`PILOT_SAMPLING_STATUS = FROZEN`

Selection seed: `2026071502`. Gate-0 prompt IDs were excluded. All source prompt IDs begin with `dev_`; no held-out/test prompt is eligible.

Risk is frozen as `0.5 * promoted-instrument candidate violation rate + 0.5 * mean corrected-EVPD violation probability` over the eight pre-existing spine candidates. Instrumental prompts are rank-tertiled before sampling.

Each stratum uses a fixed-seed simple random sample of 12, so every eligible prompt in a stratum has inclusion probability `12 / frame_size` and design weight `frame_size / 12`. Balance variables were not used to tune outcomes; their realized distributions are audited below.

Frame SHA256: `2d91cc86a5c669fb28ed45e741ff0e2dd11c0c2397c0a2df2c31f3b1db7aa319`. Manifest SHA256: `7882d92ecb346e259f8c71d0be0045ac6357bfd75d2f1965865558115484d456`.

## Realized balance

- high_risk_instrumental: genres={'classical': 5, 'folk': 4, 'electronic': 2, 'rock': 1}; tempo={'very_fast_160_plus': 7, 'fast_120_160': 3, 'slow_60_90': 2}; specificity={'broad': 10, 'medium': 1, 'specific': 1}; structure={'complex_multi_section': 6, 'simple_AB': 3, 'verse_chorus': 2, 'AABA': 1}; language={'en': 12}
- medium_risk_instrumental: genres={'classical': 4, 'rock': 1, 'pop': 2, 'jazz': 3, 'electronic': 1, 'metal': 1}; tempo={'slow_60_90': 3, 'med_90_120': 5, 'fast_120_160': 3, 'very_fast_160_plus': 1}; specificity={'broad': 5, 'specific': 4, 'medium': 3}; structure={'AABA': 2, 'simple_AB': 3, 'verse_chorus': 4, 'complex_multi_section': 3}; language={'en': 12}
- low_risk_instrumental: genres={'jazz': 1, 'electronic': 3, 'classical': 8}; tempo={'slow_60_90': 1, 'very_fast_160_plus': 4, 'fast_120_160': 4, 'med_90_120': 3}; specificity={'medium': 5, 'specific': 6, 'broad': 1}; structure={'AABA': 3, 'complex_multi_section': 5, 'verse_chorus': 3, 'simple_AB': 1}; language={'en': 12}
- vocal_request: genres={'pop': 2, 'rock': 3, 'hip_hop': 3, 'jazz': 2, 'metal': 2}; tempo={'fast_120_160': 4, 'very_fast_160_plus': 5, 'slow_60_90': 3}; specificity={'medium': 1, 'specific': 7, 'broad': 4}; structure={'verse_chorus': 4, 'complex_multi_section': 2, 'AABA': 3, 'simple_AB': 3}; language={'en': 10, 'es': 1, 'zh': 1}
