# Vocal-Presence Label Reliability (Stage 1)

## Primary reliability evidence (the Demucs vocal-presence label IS reliable)
- **Request-type separation**: vocal-requested ratio median **0.3415** vs instrumental-requested median **0.0166** (separation **0.3249**) — the label cleanly tracks the requested type.
- **GMM bimodality**: {"means": [0.0003, 0.3398], "separation": 0.3394, "weights": [0.8388, 0.1612]} — two well-separated clusters (no-vocal ~0, vocal ~0.34).
- Label threshold (strata-median-midpoint): **0.1791**; margin-to-threshold {"min": -0.1791, "p10": -0.179, "median": 0.0585, "p90": 0.4809, "max": 0.8209}.
- Ambiguous (|ratio−thr|<0.05): 557 (13.6%).

## Secondary cross-check — Whisper lyric proxy (INCONCLUSIVE by construction)
- P(Demucs present | Whisper words) = **0.8017**, P(present | no words) = **0.7961** → ~equal.
- Words-but-Demucs-absent: 215 (Demucs miss OR Whisper hallucination); present-but-no-words: 933 (wordless vocals, expected).
- Demucs presence ⊥ Whisper words (different axes; Whisper hallucinates on instrumental). Whisper is NOT used to validate presence; disagreements go to the manual-check packet.

**Verdict:** clean request-type separation + bimodality => the Demucs vocal-presence label is reliable enough to be the EVPD target. The 2256-candidate EN-vocal lyric axis stays separate (Whisper, not Demucs).