# EVPD Training/Evaluation Plan (Batch 2 Stage 2)

**EVPD = Early Vocal-Presence Detector.** Predict the FINAL vocal-presence (and thus type-match)
from EARLY-σ Tweedie-clean audio, so ADSR can restart type-mismatched trajectories early.

## Target labels (from Demucs final vocal-presence, Stage-1 verified reliable)
- **Primary:** `final_present ∈ {0,1}` = `(vocal_energy_ratio ≥ THR=0.179) and not near_silent`.
- **Derived (not separate models):** type-match = `(pred_present == requested)`, where
  `requested = (vocal_stratum=='vocal')`. Error kinds: vocal-req→no-vocal, instr-req→has-vocal.

## Inputs (EARLY only — no final leakage)
- Early log-mels at **σ0.9 / σ0.8 / σ0.7** (64×T, the 12288 precomputed `.npy`). Per-σ models + fusion.
- **Audio-only is the primary model** (genuinely detect presence from early audio). Prompt-type
  metadata (`requested`) is an **ablation only** — NOT in the primary model, because feeding the
  request lets the model echo the prior instead of detecting mismatch.
- Optional cheap early SCALAR features (already in records: early-σ aesthetic_pq, section_coherence,
  probe_silence_fraction, common_robust_lcb) for the scalar/GBDT baselines.

## Forbidden inputs (leakage)
final audio/mel, final reward, final `vocal_energy_ratio`, the Demucs label itself, `candidate_id`,
σ0.5/σ0.3 (not saved as audio anyway), and **test labels for threshold tuning**.

## Split discipline (prompt-level, 8 candidates never cross)
- Canonical project split: **dev (256 prompts) / held_out (256 prompts)**.
- **test = held_out (256 prompts, untouched).** **dev → train (~205) + val (~51)** by a deterministic
  prompt-level hash. Threshold + early-stopping tuned ONLY on val. Held-out reported once.
- Report split sizes by prompt and candidate; assert 0 prompt overlap across splits.

## Models (lightweight only; no from-scratch audio transformer)
0. Scalar-proxy baseline (early scalar features → logistic) — the existing AUC≈0.74 reference.
1. Logistic on mel-summary features (per-band mean/std/max + global stats).
2. LightGBM GBDT on mel-summary features.
3. Small **log-mel CNN** per σ (2–3 conv blocks → GAP → FC; ~10–50k params).
4. Multi-σ fusion (concat σ0.9/0.8/0.7 features OR average per-σ CNN logits).
- Best lightweight models: **≥3 seeds**, run in parallel across an17's 8 GPUs. Report mean±std.

## Metrics (per σ and per model; AUC alone insufficient)
AUC, AUPRC (vs prevalence baseline), precision/recall, **recall@precision≥0.8**, **precision@recall≥0.8**,
balanced accuracy, calibration (reliability curve / Brier), confusion matrix, val-selected threshold,
held-out performance, **vocal vs instrumental stratum breakdown**, **type-error detection** (does
flagging predicted-mismatch catch true type errors), and **survivor-set type-error detection**
(type errors among common-score top-1/2/4 — the cases ADSR must catch).

## Onset-σ question
Report held-out AUC/AUPRC/recall@P0.8 at σ0.9, σ0.8, σ0.7 separately → is EVPD usable by **σ≤0.7**?

## Decision bands (pre-registered)
- **Strong:** usable by σ≤0.7, AUC≳0.85, AUPRC ≫ prevalence, nontrivial recall@P0.8, works on survivors.
- **Moderate:** clearly beats scalar proxy; reduces high-stakes type errors but not perfect.
- **Weak:** ≈ scalar proxy; fails on survivor-set type errors; usable only very late.

## Outputs
`EVPD_RESULTS.{md,json}`, `EVPD_SPLIT_REPORT.md`, `EVPD_MODEL_CARD.md`, saved models, reproducible command log.
