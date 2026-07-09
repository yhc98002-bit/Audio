# ADSR Phase-1 Dataset Card (CURRENT)

- **Generated:** 2026-06-04 (0-GPU offline analysis)
- **Generator:** `orbit-research/adsr_phase1_20260604/adsr_dataset_card.py` (re-runnable)
- **Source:** `orbit-research/trajectory_candidate_dataset.jsonl`
- **Subset id list:** `orbit-research/adsr_phase1_20260604/lyric_bearing_subset.json`

> Evidence honesty: this is offline analysis on the existing cached candidate pool. No ADSR / EVPD / restart real result is generated here; nothing below is a method outcome.

## 1. Cardinality

- Rows: **4096** (expected 4096) — PASS
- Prompts: **512** (expected 512) — PASS
- Candidates per prompt: **[8]** (expected {8}) — PASS
- join key: `prompt_id`; group by `prompt_id` for within-prompt analysis.

## 2. Vocal vs Instrumental per split

Candidate-level counts:

| split | stratum | candidates |
|---|---|---|
| dev | instrumental | 792 |
| dev | vocal | 1256 |
| held_out | instrumental | 776 |
| held_out | vocal | 1272 |

Prompt-level counts (stratum is prompt-constant):

| split | stratum | prompts |
|---|---|---|
| dev | instrumental | 99 |
| dev | vocal | 157 |
| held_out | instrumental | 97 |
| held_out | vocal | 159 |

## 3. EN-vocal (vocal_scorable) lyric subset

Definition: `vocal_stratum=='vocal' AND language=='en'`.

- Prompts: **282** (plan n=282) — PASS
- Candidates: **2256** (= 282 x 8)
- by split: dev=135, held_out=147
- This is the ONLY valid population for the `lyric_intelligibility` headline.

## 4. Instrumental lyric sentinel (confirm + exclusion)

- Instrumental candidates: **1568**
- `final_lyric_intelligibility` unique values over instrumental: **[1.0]**
- Constant 1.0 sentinel confirmed: **PASS**
- Instrumental excluded from lyric subset: PASS
- Non-EN vocal prompts: 34 (excluded from lyric headline: PASS)

> The 1.0 value is a non-informative sentinel for instrumental tracks, NOT a perfect-intelligibility score. Including it would inflate any lyric headline. It is excluded everywhere lyric is reported.

## 5. Prompt-level split & leakage

- dev prompts: **256**, held_out prompts: **256** — 256/256 PASS
- Candidate-level leakage (prompt spanning >1 split): **0** — zero-leakage PASS
- Split / stratum / language / density are prompt-constant: split=PASS, stratum=PASS, language=PASS, density=PASS
- Grouping rule: prompt-level only; a prompt's 8 candidates never split across train/eval.

Informational — `split` x `analysis_split` (candidate counts):

| split | analysis_split | candidates |
|---|---|---|
| dev | train | 1552 |
| dev | validation | 496 |
| held_out | test | 2048 |

## 6. Lyric-bearing subset breakdown (clean-English-core vs thin vs non-EN)

Within vocal_scorable (EN vocal), by `lyric_density`. high/med = clean-English-core (>=3 measurable lyric lines); low = thin.

| class | density | prompts |
|---|---|---|
| clean-English-core | high | 92 |
| thin | low | 91 |
| clean-English-core | med | 99 |

- clean-English-core total: **191** prompts
- thin total: **91** prompts
- (excluded) non-EN vocal: 34 prompts; density breakdown {'high': 10, 'low': 12, 'med': 12}

## 7. Language distribution

| language | candidates | prompts |
|---|---|---|
| en | 3824 | 478 |
| es | 104 | 13 |
| fr | 40 | 5 |
| ja | 32 | 4 |
| zh | 96 | 12 |

## 8. Cached sigma coverage

- Present early sigmas: **['0.9', '0.8', '0.7']** + `final`.
- Absent (NOT in this cached pool): **['0.5', '0.3']** (sigma 0.5 / 0.3 come from a parallel GPU re-collection; not joined here).
- All final axes present: PASS

## 9. Axis means (offline descriptive, final_<axis>)

Non-lyric axes reported on `all` + per stratum; lyric reported on vocal_scorable ONLY (per binding rule).

| axis | all | vocal | instrumental | vocal_scorable(EN) |
|---|---|---|---|---|
| common_robust_lcb (PRIMARY) | 2.1639 | 2.1118 | 2.2478 | 2.1133 |
| aesthetic_pq | 7.3155 | 7.4357 | 7.1218 | 7.4279 |
| aesthetic_cu | 7.2487 | 7.2599 | 7.2306 | 7.2601 |
| semantic_fit | 0.3276 | 0.3151 | 0.3478 | 0.3157 |
| lyric_intelligibility | n/a (sentinel-contaminated) | see headline | 1.0 (sentinel) | 0.2453 |
| section_coherence | 0.9559 | 0.9533 | 0.9601 | 0.9532 |

**Lyric headline (vocal_scorable EN, n=282 prompts / 2256 candidates):** mean final_lyric_intelligibility = **0.2453** (clean-core mean 0.1949, thin mean 0.3510).

## 10. Deferred / not-available

- **Vocal-presence / type-match axis:** PLANNED_DEFERRED_no_measured_labels. No measured labels in this pool (keys found: []). Marked PLANNED; NOT fabricated.
- **sigma 0.5 / 0.3 early features:** not in this cached pool (parallel GPU re-collection).
- No ADSR / EVPD / restart method result is produced by this card.

## 11. Validation verdict

**ALL CHECKS PASS**

