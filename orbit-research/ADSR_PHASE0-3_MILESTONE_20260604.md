# ADSR Phases 0–3 Milestone (offline) — 2026-06-04

Researcher: claude:researcher. First full ADSR experimental phase, offline tracks, with milestone
Codex audits. **Status: Phases 0/1/2B/3 done + audited; Track-B GPU re-collection running to unblock
Phases 2A/4/5.** No paper claims; PI decision point flagged below.

## Validated results (Codex Audit 1 + 2 = ACCEPT_WITH_NONBLOCKING_NOTES)

### Phase 0 — gate PASS
`ADSR_ARTIFACT_INVENTORY.md`, `ADSR_DATASET_CARD_CURRENT.md`. 4096=512×8; vocal_scorable (EN-vocal)
= 282 prompts; instrumental `final_lyric_intelligibility`≡1.0 sentinel excluded; non-EN (34) excluded;
prompt-level split dev256/held256, 0 leakage. Codex (a): lyric subset clean in code + artifacts.

### Phase 1 — Axis × σ observability (the solid, publishable finding)
Within-prompt Spearman(early-σ → final), σ 0.9/0.8/0.7 (cached; σ{0.5,0.3} pending re-collection):
| axis | σ0.9 | σ0.8 | σ0.7 | read (Codex-corrected wording) |
|---|---|---|---|---|
| section_coherence | 0.388 | 0.583 | 0.686 | earliest-emerging, but NOT strong-early (σ0.9 top-1 FN ≈ 0.68 — do **not** over-trust for early restart) |
| common_robust_lcb (PRIMARY) | 0.247 | 0.483 | 0.652 | **mid** (usable by σ0.8/0.7; NOT early at σ0.9) |
| aesthetic_pq / cu | 0.281 / 0.285 | 0.538 / 0.512 | 0.629 / 0.617 | **mid** (not early at σ0.9 — corrects the thesis's "aesthetic early") |
| lyric_intelligibility (vocal_scorable) | 0.038 | 0.250 | 0.554 | **latest** (near-zero early, steep climb) — confirms the lyric-is-late thesis |
| semantic_fit | 0.130 | 0.204 | 0.303 | **weak late-emerging** (only ~0.30 even at σ0.7) |
Vocal-presence/type-match axis = **PLANNED** (no measured labels yet → Track-B re-collection).
→ The axis-observability map is the strongest result and stands on its own (ADSR §9 fallback paper).

### Phase 2B — late-axis risk (early features → late failure)
`LATE_AXIS_RISK_RESULTS.*`. Early-σ features predict **lyric-low risk well (held-out AUC 0.866** on
vocal_scorable), semantic moderate (0.65–0.72). Type-mismatch is a PROXY only (real type-match label
pending). Supports an early **lyric-risk DEFER gate**, but the signal is usable mainly by σ0.7.

### Phase 3 — ADSR offline simulation (honest NEGATIVE for the reduced method)
`ADSR_OFFLINE_SIM_RESULTS.*`, `ADSR_COMPUTE_QUALITY_PARETO.csv`, `ADSR_AXIS_PRESERVATION.csv`.
Matched-compute headline (PRIMARY common_robust_lcb): Full-BoN8 2.358 (cf1.0); raw-ETP-A **2.3255**
(cf0.50); common-score-restart **2.3275** (cf0.55); learned-ETV-proxy 2.325 (cf0.52); **ADSR-noEVPD
2.3160 (cf0.55)**; random-restart 2.285.
- **ADSR-noEVPD FAILS the METHOD bar:** a *simple* common-score restart dominates it on PRIMARY,
  semantic (0.333 vs 0.328) and lyric (0.346 vs 0.317 on vocal_scorable) at matched compute.
- **Mechanism:** ADSR's DEFER branch keys on semantic/lyric, which are too weak early, so deferring
  spends compute without recovering late value (consistent with H3: selection is low-stakes).
- **Codex-verified:** no final-score leakage in restart/keep rules; oracle-empty-commit bug fixed;
  BoN-4 & raw-ETP exactly cf=0.500; ADSR held at cf~0.55 (a slight compute *handicap*, not a discount
  — so its near-tie with BoN-4 is **not** a win). The negative is real, not an implementation artifact.

## THE DECISION POINT (PI)
The offline fixed-8-pool result is **necessary-not-sufficient and came back negative for the reduced
ADSR** (no EVPD, no true restart). ADSR's two remaining, untested differentiators are exactly what a
fixed pool cannot test:
1. **EVPD type-match branch** — catching *categorical, high-stakes* vocal↔instrumental type errors
   (a different value source than near-tied quality selection). Its value hinges on **type-error
   prevalence** + **early decidability** — both measured only after the re-collection (vocal-presence
   labels + EVPD, ADSR plan E3).
2. **True online restart with new seeds** — exploring more trajectories under the same budget, which a
   fixed 8-pool cannot simulate (ADSR plan E6 online; Phase 4).
If type errors are common & early-catchable → ADSR has real leverage. If rare → fall back to the
**axis-observability + trajectory-analysis paper** (ADSR §9), which Phase 1 already supports strongly.

## Codex audit non-blocking notes (applied to interpretation here)
- semantic = "weak late-emerging", not "strongly late-observable".
- section_coherence is earliest-emerging but NOT reliable for early restart (σ0.9 FN@1≈0.68).
- ADSR cf0.552 vs cf0.500 baselines = slight compute advantage to ADSR, so its +0.0005 vs BoN-4 is
  not a matched-compute win (and the verdict is FAIL-METHOD anyway).
- offline sim labeled "deterministic" but uses `hash(pid)` seeding; bootstrap CIs recommended before any claim.

## Next (gated on Track-B re-collection `adsr_recollect_20260604_full01`, ~38–40h)
vocal-presence labels (CPU source-sep on saved audio) → **type-error prevalence study + EVPD (Phase 2A)**
→ full ADSR offline (with EVPD branch) → **Phase 4 online pilot** (true restart) if promising →
Phases 5/6 → final PI report. The make-or-break is the EVPD type-match value + online restart.
