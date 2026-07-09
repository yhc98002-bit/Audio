# ADSR+EVPD Offline Simulation Results (Batch 2 Stage 4)

Fixed-pool offline sim, **256 held-out prompts** (out-of-fold EVPD trained on dev). Compute: σ0.7=16, FULL=30; σ0.7-decision policies continue 4 → matched **0.767**. reward_fraction vs oracle best-of-8 common.

> Caveat: fixed-pool offline sim, NOT true online restart. **Honest attribution: the type-error win is EVPD-aware SELECTION, not restart.**

| policy | compute | reward_frac | type-error | winner_ret |
|---|---|---|---|---|
| full_bon8 | 1.0 | 1.0 | 0.1836 | 1.0 |
| bon4_random | 0.5 | 0.9825 | 0.1719 | 0.4648 |
| random_keep4 | 0.7667 | 0.9814 | 0.2148 | 0.4727 |
| common_restart | 0.7667 | 0.9982 | 0.168 | 0.9023 |
| evpd_only | 0.7667 | 0.9963 | 0.1562 | 0.8203 |
| adsr_evpd | 0.7667 | 0.9963 | 0.1562 | 0.8203 |
| adsr_evpd_select | 0.7667 | 0.9936 | 0.1211 | 0.7656 |
| adsr_evpd_lyric_defer | 0.7667 | 0.9963 | 0.1562 | 0.8203 |

## Key comparisons (matched compute 0.767)

- **adsr_evpd_select vs common_restart:** type-error 0.168→0.1211 (−0.0469 abs / 27.9% rel), reward Δ -0.0046.
- **Paired prompt-level uncertainty:** mean reduction 0.0469, 95% CI [0.0117, 0.0782]; 16 fixed vs 4 regressed (net 12/256).
- **restart-only (adsr_evpd) vs common:** −0.0118 abs (marginal — restart adds little).
- **vs full BoN-8** (type-error 0.1836 @ compute 1.0): adsr_evpd_select reaches 0.1211 at 0.767×.
- **type-risk prompts:** common 0.281 → select 0.2026.

## Lyric-bearing EN-vocal (vocal_scorable; instrumental sentinel excluded)

- common_restart: type-error 0.1633, reward_frac 0.976, lyric(EN-vocal) 0.4
- adsr_evpd: type-error 0.1429, reward_frac 0.9738, lyric(EN-vocal) 0.3791
- adsr_evpd_select: type-error 0.0884, reward_frac 0.97, lyric(EN-vocal) 0.3678

**Read:** EVPD's leverage is on the TYPE-MATCH axis via EVPD-aware SELECTION; restart alone adds little; common reward preserved (not improved); lyric mean dips slightly. Promising type-safety control, not a broad quality win.