# PI SANITY GATE REQUEST — 10-minute inspection (MANDATORY, non-self-certified)

Large-N ACE-Step generation is **blocked** until you pass this gate (§10/§13).

## Please inspect
1. A few audio files (paths below), 2. the labels/scores table in `SANITY_GATE_RESULTS.md`, 3. whether trivial controls behave as expected, 4. any obvious detector mismatch.

## Headline numbers
| category | n | type-correct | mean ratio | D↔PANNs |
|---|---|---|---|---|
| A_trivial_vocal | 40 | 0.9 | 0.4098 | 0.85 |
| B_trivial_instrumental | 40 | 0.825 | 0.0825 | 0.75 |
| C_contradictory | 24 | 0.458 | 0.187 | 0.458 |
| D_e2_vocal_tail | 32 | 0.0 | 0.0528 | 0.125 |
| E_instrumental_risk | 24 | 0.375 | 0.257 | 0.792 |

## Suggested clips to listen to (path · req-type · ratio · type-correct)
- [A_trivial_vocal] `keep/ctlA_rock_vocal/seed2_2026300002.flac` · req=vocal · ratio=0.10115 · type_correct=0
- [A_trivial_vocal] `keep/ctlA_folk_vocal/seed3_2026400003.flac` · req=vocal · ratio=0.40963 · type_correct=1
- [A_trivial_vocal] `keep/ctlA_rnb_vocal/seed4_2026500004.flac` · req=vocal · ratio=0.86694 · type_correct=1
- [B_trivial_instrumental] `keep/ctlB_piano_instr/seed7_2026700007.flac` · req=instrumental · ratio=0.0 · type_correct=1
- [B_trivial_instrumental] `keep/ctlB_ambient_instr/seed2_2026900002.flac` · req=instrumental · ratio=0.00965 · type_correct=1
- [B_trivial_instrumental] `keep/ctlB_classical_instr/seed4_2027000004.flac` · req=instrumental · ratio=0.54544 · type_correct=0
- [C_contradictory] `keep/ctlC_contra1/seed1_2027200001.flac` · req=vocal · ratio=0.04487 · type_correct=0
- [C_contradictory] `keep/ctlC_contra2/seed6_2027300006.flac` · req=vocal · ratio=0.17244 · type_correct=0
- [C_contradictory] `keep/ctlC_contra3/seed0_2027400000.flac` · req=vocal · ratio=0.42964 · type_correct=1
- [D_e2_vocal_tail] `keep/held_out_0016/seed6_2027700006.flac` · req=vocal · ratio=0.00249 · type_correct=0
- [D_e2_vocal_tail] `keep/held_out_0016/seed3_2027700003.flac` · req=vocal · ratio=0.04135 · type_correct=0
- [D_e2_vocal_tail] `keep/held_out_0016/seed5_2027700005.flac` · req=vocal · ratio=0.16325 · type_correct=0
- [E_instrumental_risk] `keep/held_out_0043/seed0_2028100000.flac` · req=instrumental · ratio=0.0 · type_correct=1
- [E_instrumental_risk] `keep/held_out_0035/seed6_2027900006.flac` · req=instrumental · ratio=0.23562 · type_correct=0
- [E_instrumental_risk] `keep/held_out_0041/seed4_2028000004.flac` · req=instrumental · ratio=0.89123 · type_correct=0

## Auto-flags
- none

## Your decision (reply with one)
- **PASS** → I proceed autonomously to large-N critical path + concurrent exploration.
- **FAIL / FIX** → tell me what looks wrong; I hold large-N and fix.

_Manifest: `SANITY_GATE_AUDIO_MANIFEST.csv`. Audio kept as FLAC under `keep/`._