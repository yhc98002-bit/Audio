# ADSR Policy Definitions

- **full_bon8** — all 8 to final, pick best by final common (reward ceiling, compute 1.0).
- **bon4_random** — 4 random to final (compute 0.5).
- **random_keep4** — random 4 continue past σ0.7 (restart baseline).
- **common_restart** — continue top-4 by EARLY common score (= raw-ETP = **ADSR-noEVPD**).
- **evpd_only** — continue 4 prioritising EVPD non-type-mismatch.
- **adsr_evpd** — RESTART/FILTER ONLY: EVPD drops predicted type-mismatches from the continued set; final output still chosen by best-FINAL-common. (This is the restart-attributable effect, ~−7% rel.)
- **adsr_evpd_select** — adsr_evpd PLUS EVPD-aware OUTPUT selection: among the continued set, prefer EVPD type-MATCHing candidates (fallback to best-common if all flagged). **The headline −28% rel type-error win comes from THIS selection step, NOT from restart.**
- **adsr_evpd_lyric_defer** — adsr_evpd but never early-restart on lyric uncertainty alone (lyric is a late observable; deferred to final).

Final output: best-FINAL-common among the continued set for ALL policies EXCEPT `adsr_evpd_select`, which applies an EVPD type-match guard at output. Honest attribution: the strong type-error reduction is SELECTION-driven (EVPD-aware output), not restart-driven; restart-only adds little. Reported per policy: selected candidate's type-error / reward_fraction / axis values.