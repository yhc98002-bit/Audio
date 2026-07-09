# EVPD Model Card (Batch 2)

**Task.** Early Vocal-Presence Detector: predict FINAL Demucs vocal-presence (binary) from
EARLY-σ Tweedie-clean log-mels, enabling early type-mismatch detection for ADSR.

**Data.** 4096 candidates / 512 prompts (8 each). Prompt-level split: test = held_out
(256 prompts / 2048 cands); dev → train (210 prompts / 1680) + val (46 / 368) by prompt hash.
Test presence prevalence 0.576. 0 prompt overlap across splits (asserted).

**Inputs.** Early log-mels σ0.9/0.8/0.7 → per-band summary (mean/std/max/p25/p75 = 320/σ) and a
64×128 adaptive-pooled mel for the CNN. Scalar baseline uses early {aesthetic_pq, section_coherence,
probe_silence_fraction, common_robust_lcb}. NO final audio/reward/label/candidate_id/prompt_id/
split/lyric/Whisper features (asserted). Prompt-type used only downstream for mismatch, never as input.

**Models / held-out AUC.** scalar-proxy 0.68–0.74; mel-summary logistic **0.872 (σ0.9) → 0.916
(σ0.8) → 0.940 (σ0.7)**; mel-summary GBDT similar; small log-mel CNN 0.81–0.90; mel-summary fused
GBDT 0.938. **Deployed = best-on-val (mel-summary GBDT fused), held-out AUC 0.938, AUPRC 0.955**,
bootstrap 95% CI (prompt-level) AUC [0.876, 0.912].

**Onset σ.** Usable by σ≤0.7 (AUC 0.94); even σ0.9-only is strong (0.87). EVPD ≫ scalar proxy (0.74).

**Type-error / survivor detection (deployed, val-tuned threshold).** type-error detection
precision 0.61 / recall 0.64; survivor-top-1 type-error catch 0.47 (22/47); restart-rate 0.23,
false-restart 0.087 (39% of restarts). Strong presence detector; MODERATE on the hardest survivor
type-mismatches.

**Threshold discipline.** Threshold + early-stopping + model selection on VAL only; held-out
reported once. Multi-seed (0/1/2) for CNN; mean reported.

**Limitations.** Demucs label is the target (reliable per Stage-1 bimodality, but near-threshold
ambiguity exists); small train set (1680) limits the CNN; Whisper lyric axis is separate and not
an EVPD input. Reproduce: `scripts/batch2_stage3_evpd.py` (+ cache npz).
