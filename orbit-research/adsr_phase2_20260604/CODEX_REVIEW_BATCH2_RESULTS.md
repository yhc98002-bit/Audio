# Codex Review — Batch 2 EVPD+ADSR Results (Stage 5)

Independent read-only audit (`codex exec`, gpt-5.x). **Decision: `ADSR_CONDITIONAL`** —
targeted type-risk pilot only, after PI approval; NOT a broad online pilot.

## Audit answers
- **PASS — leakage:** prompt splits 0 overlap; sim uses held-out EVPD predictions from a dev-trained model.
- **PASS — thresholds:** EVPD operating threshold tuned on val, not test; deployed model selected by val AUC.
- **PASS — AUPRC vs prevalence:** 0.955 vs test prevalence 0.576, interpreted correctly.
- **PASS — lyric scope:** lyric means restricted to EN-vocal; instrumental 1.0 sentinel excluded. (Caveat: stratum reward_fraction is globally normalized — don't over-read stratum reward fractions.)
- **mostly PASS — compute:** 0.767 = (8·16 + 4·14)/(8·30), fair within the fixed-pool σ0.7 model; caveat = not true online restart, ignores small EVPD inference overhead.
- **nonblocking — Demucs labels:** valid enough as the EVPD proxy target (strong separation, bimodality, 13.6% near-threshold ambiguous); not human ground-truth without manual spot-check (→ ambiguous packet).
- **nonblocking — type-error prevalence 0.23:** correct (533+409=942 / 4096).
- **nonblocking — survivor-set:** top-1 0.199 / top-2 0.214 / top-4 0.213 correct; don't conflate with σ0.7 common_restart.
- **substantive result:** EVPD-select improves a high-stakes axis with tradeoffs (reward 0.998→0.994, lyric 0.400→0.368). Promising, not a broad quality win.
- **overreach risk:** "ADSR restart works" / "quality preserved without cost" overreach; "EVPD-aware type-risk control works offline" is supported.

## BLOCKING corrections — ALL APPLIED
1. **Document `adsr_evpd_select` correctly.** Fixed `ADSR_POLICY_DEFINITIONS.md`: added the policy and corrected the "every policy selects best-final-common" statement (only `adsr_evpd_select` applies the EVPD output guard).
2. **Don't attribute −28% to restart.** Restart/filter-only `adsr_evpd` = 0.168→0.156 (~−7% rel); the headline 0.168→0.121 (−28%) is SELECTION-driven. Doc + PI report now state this explicitly.
3. **Add paired prompt-level uncertainty.** Added paired bootstrap: mean abs type-error reduction 0.047, **95% CI [0.012, 0.078]** (excludes 0); 16 prompts fixed vs 4 regressed (net 12/256).

Honest claim adopted: *"EVPD-aware selection/filtering reduces vocal/instrumental type errors at matched simulated compute, with small reward/lyric tradeoffs"* — NOT "ADSR restart works."
