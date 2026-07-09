# Codex Review — EVPD Training/Eval Plan (Batch 2 Stage 2)

Model: gpt-5.x via `codex exec` (read-only). Verdict: **plan sound; no critical flaw.**

## Codex findings (BLOCKING = implementation must honor the plan)
1. No label leakage in the plan (early mels + early scalars only; final/label/candidate_id/later-σ/test-threshold forbidden). **Fix applied:** added hard asserts that `prompt_id`, file path, split name, and any lyric/Whisper field can never be a model feature (`FEATURE LEAK` assert on SCALAR_KEYS; features built only from early mels + {aesthetic_pq, section_coherence, probe_silence_fraction, common_robust_lcb}).
2. Prompt-level split correct. **Fix applied:** hard-fail unless each prompt's 8 candidates are in exactly one split and train/val/test prompt overlaps are all 0.
3. Final labels are targets only — confirmed.
4. Threshold/early-stopping val-only. **Fix applied:** threshold + CNN early-stop on val; detection model `cnn_fused` chosen a priori (NOT by test performance); held-out reported once.

## Codex NONBLOCKING / confirmations (applied where useful)
5. Instrumental lyric 1.0 sentinel irrelevant to EVPD (it's a Whisper lyric-axis issue, not vocal presence). Confirmed — no lyric/Whisper field in EVPD features.
6. Add uncertainty + policy cost. **Applied:** prompt-level bootstrap 95% CIs for fused-CNN held-out AUC/AUPRC (500 reps); restart-rate + false-restart-rate at the operating point.
7. Exclude prompt-type from the primary model (ablation only) — confirmed; request type used downstream to compute mismatch, never as a presence-prediction input.
8. Model scope (logistic/GBDT/small CNN, no transformer) defensible for 4096 candidates — confirmed.
9. No flaw invalidates onset-σ / survivor-set conclusions if implementation honors the plan. Residual risks (near-threshold ambiguity, small survivor subsets, loader metadata leakage) handled by the frozen-label rule, prompt-level CIs, and the feature/split asserts above.

All BLOCKING items are implemented as runtime asserts in `scripts/batch2_stage3_evpd.py`.
