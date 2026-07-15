# BOLT Pilot Sampling Audit

`PILOT_SAMPLING_STATUS = FROZEN`

Selection seed: `2026071502`. Gate-0 prompt IDs were excluded. All source prompt IDs begin with `dev_`; no held-out/test prompt is eligible.

Risk is frozen as `0.5 * promoted-instrument candidate violation rate + 0.5 * mean corrected-EVPD violation probability` over the eight pre-existing spine candidates. Instrumental prompts are rank-tertiled before sampling.

Each stratum allocates 12 seats across genres with one mandatory seat per available genre and deterministic Webster proportional priorities for the remaining seats. Within each `(risk stratum, genre)` cell, selection is fixed-seed simple random sampling. Every row therefore has exact inclusion probability `cell allocation / eligible cell size` and inverse-probability design weight. Tempo, specificity, structure, and language are audited as secondary realized-balance dimensions.

Frozen genre allocations: `{"high_risk_instrumental": {"classical": 3, "electronic": 2, "folk": 3, "jazz": 1, "metal": 1, "pop": 1, "rock": 1}, "low_risk_instrumental": {"classical": 7, "electronic": 3, "jazz": 1, "rock": 1}, "medium_risk_instrumental": {"classical": 5, "electronic": 2, "jazz": 2, "metal": 1, "pop": 1, "rock": 1}, "vocal_request": {"classical": 1, "electronic": 1, "folk": 2, "hip_hop": 2, "jazz": 1, "metal": 2, "pop": 1, "rock": 2}}`.

Frame SHA256: `c62d1969ad79527390ef971574357fb54b30ad8faad339664ac99a05568d5946`. Manifest SHA256: `45e469914b50e16da564c2331798d8ed455f35c59b5dacfc721d32d5f530205c`.

## Realized balance

- high_risk_instrumental: genres={'folk': 3, 'pop': 1, 'classical': 3, 'electronic': 2, 'metal': 1, 'rock': 1, 'jazz': 1}; tempo={'med_90_120': 2, 'very_fast_160_plus': 6, 'fast_120_160': 4}; specificity={'broad': 9, 'medium': 2, 'specific': 1}; structure={'verse_chorus': 5, 'complex_multi_section': 3, 'simple_AB': 2, 'AABA': 2}; language={'en': 12}
- medium_risk_instrumental: genres={'rock': 1, 'pop': 1, 'classical': 5, 'electronic': 2, 'jazz': 2, 'metal': 1}; tempo={'med_90_120': 6, 'fast_120_160': 2, 'slow_60_90': 3, 'very_fast_160_plus': 1}; specificity={'specific': 4, 'medium': 3, 'broad': 5}; structure={'AABA': 5, 'simple_AB': 2, 'complex_multi_section': 2, 'verse_chorus': 3}; language={'en': 12}
- low_risk_instrumental: genres={'rock': 1, 'electronic': 3, 'classical': 7, 'jazz': 1}; tempo={'fast_120_160': 4, 'slow_60_90': 3, 'med_90_120': 3, 'very_fast_160_plus': 2}; specificity={'specific': 8, 'medium': 3, 'broad': 1}; structure={'AABA': 2, 'verse_chorus': 6, 'complex_multi_section': 4}; language={'en': 12}
- vocal_request: genres={'electronic': 1, 'pop': 1, 'hip_hop': 2, 'folk': 2, 'rock': 2, 'jazz': 1, 'metal': 2, 'classical': 1}; tempo={'very_fast_160_plus': 5, 'slow_60_90': 2, 'med_90_120': 2, 'fast_120_160': 3}; specificity={'broad': 4, 'specific': 4, 'medium': 4}; structure={'simple_AB': 2, 'verse_chorus': 3, 'complex_multi_section': 6, 'AABA': 1}; language={'en': 11, 'fr': 1}
