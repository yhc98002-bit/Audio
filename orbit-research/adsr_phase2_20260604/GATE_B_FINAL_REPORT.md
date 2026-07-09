# GATE B — Final Program Report (Phases 0–3 complete)

**Date:** 2026-06-12 · **Program:** experiment_plan_current.md (full PI authorization)
**Headline verdict (pre-registered, mechanical): `SUPPORTED_TAIL_RESCUE`**
**Recommended paper shape: restart-led method paper with a cross-modal diagnostic/motivation
section** (per the Gate-B mapping: SUPPORTED → restart-led; the T2I study replicates the
diagnostic signatures — violations survive selection, early observability, gated frontier —
but probe-gated restart did NOT beat the T2I frontier at OWLv2 quality, so T2I supports the
problem framing, not method efficacy there).

---

## 1. The validated claim chain

1. **Constraint violations are common and survive reward selection** — music: 23% of candidates,
   19.9% among common-score winners; T2I (SDXL): 28.7% pool, 24.8% after PickScore selection.
   Cross-modal signature ✓.
2. **Violations are early-observable** — observability curves: vocal-presence detectable at σ0.9
   (EVPD AUC 0.87→0.94 by σ0.7) while lyrics are late (ρ 0.06→0.68); T2I probe AUC 0.70→0.82
   across denoising. The "axis-deferred" premise, measured, in two modalities ✓.
3. **Detector quality — not policy structure — is the binding constraint** — oracle decomposition:
   a perfect σ0.8 probe closes the entire selection-gap; even so the broad-population efficiency
   endpoint is infeasible (oracle upper bound +14.9% < any honest criterion) because a free
   post-hoc gate already saturates clean populations. Pre-registered endpoint redesign followed.
4. **Conditioned respawn rescues the deterministic tail — ONLINE** (the main result):
   primary restart2+ per-draw clean rate, arm6−arm4 on the frozen n=32 tail: **+0.43
   [CI95 0.27, 0.58]** (criterion ≥+0.15; power 0.87); secondary E2a +0.38 ✓ (strict CI ✓).
   **Selected-output type-error 0.98% vs 11.5% (BoN-budget) and 6.6% (full BoN-8 at 1.43×
   compute); clean yield +30%; no observed selected-output PROXY tradeoff under the pre-registered margins (all point
   deltas positive incl. lyric +0.031; human judgment pending — packets prepared).**
   Seed-only restart ≈ BoN (offline null replicated online): the mechanism is the
   conditioning change, not the reseeding.
5. **Honest boundaries of the claim:** the effect is vocal-side (+0.76; instrumental ≈0 — the
   anti-vocal intervention did not transfer online; descriptive split, pre-registered as
   reporting). Probe overhead matters enormously: measured online, EVPD ≈0.9 s/probe vs score-probe
   ≈52 s/probe (arm-3: 52 h actual vs 2.7 h nominal) — only cheap probes are deployable.

**Scope caveats:** all descriptive type-error/yield absolutes are computed on the
risk-enriched 256-prompt population (stratified to the vocal/instrumental mix but NOT
de-enriched for risk) — relative arm comparisons are valid, absolutes are not
population-representative. Quality evidence is proxy-selected-output only; the blinded human
A/B packet (240 pairs) is prepared but not yet rated.

## 2. What did NOT survive (reported, not hidden)

- Broad-population efficiency endpoints (any form): calibrated-dead; demoted to descriptive
  RMST curves pre-launch (documented prospective retirement; Codex-verified).
- Phase-2 offline winners (probe-on-evidence −7%, portfolio −6% steps/clean) are **exploratory**:
  the 48-prompt online confirmation returned null (78.9 vs 77.8 steps/clean) — the tail-enriched
  confirm subset triggers probing immediately, erasing the clean-prompt advantage the offline
  replay exploited. Status: offline-positive, online-unconfirmed; future work.
- Instrumental-leakage interventions: dev screen +0.10 did not replicate online (≈0).

## 3. Process integrity

Pre-registration: endpoints frozen at Gate A before any generation (with documented
power-sim-driven retirement of the original E1/E2); analysis BLINDED until the Codex results
audit passed; verdict mechanical. Ledger: 3,648 units / 22,825 attempts, 0 validation
violations; budget conservation exact; CRN seeds verified. Cost gate: non-probing arms within
3–8.6% of nominal; probe overhead dual-ledgered and flagged-then-explained. Five Codex audits
total (2 plan-stage, harness, Gate-A, results), all blocking findings fixed before the
affected step ran.

## 4. Deliverables index

| Artifact | Path (under orbit-research/adsr_phase2_20260604/) |
|---|---|
| Frozen protocol + analysis plan | `batch3/BATCH3_PRELAUNCH_PROTOCOL.md`, `batch3/ANALYSIS_PLAN.md` |
| Online results (unblinded) + verdict | `batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.{md,json}` |
| Axis/type-risk/cost breakdowns | `batch3/ADSR_ONLINE_*.csv`, `batch3/ADSR_ONLINE_COST_ACCOUNTING.md`, `batch3/COST_RECONCILIATION.json` |
| Phase-0 evidence (frontier/oracle/curves/tail/labels/power) | `phase0/P0_*.{json,md}` |
| Phase-2 exploratory + confirmatory | `batch3/PHASE2_LEDGER_REPLAYS.{md,json}`, `batch3/CONFIRMATORY_ARM9_RESULTS.json` |
| T2I transfer (3 signatures) | `t2i/T2I_SIGNATURES.{md,json}` + 4,000 images/24k previews |
| Human packets (PI distributes) | `phase0/rater_packet/` (250 adjudication cases), `phase3/human_ab/` (240 blinded A/B pairs + key) |
| Respawn ladder + dev calibrations | `batch3/RESPAWN_LADDER.json`, `batch3/DEV_CALIBRATIONS.json` |
| Release: ledgers/labels/scores/scripts | this tree + `scripts/batch3_*.py`, `scripts/phase0_*.py`, `scripts/t2i_*.py`; bulk-audio release = FLAC keeps (~60 GB) + manifest (full 4,096-trajectory dataset stays on /XYFS02; datasheet TODO with paper) |

## 5. Boundary confirmation (full program)

No RL training · no pruning+RL · no Phase D · no crowdsourcing (both rater packets are
internal, blinded, PI-distributed) · gate_v1.yaml untouched (gate_v2.draft read-only, never
renamed) · no reward-definition changes (transcript persistence is additive logging) · no
prompt-split changes (dev/held_out preserved end-to-end; T2I split is a new dataset) · lyric
sentinel never pooled · `runs/**` untouched · an17/an29 only, both still held.

## 6. Recommended next actions (PI decisions)

1. **Paper-lock:** proceed to the restart-led method + framework paper
   (headline: *early constraint probes convert doomed compute into additional chances;
   conditioning-aware respawn rescues prompts where resampling provably cannot — online,
   with no observed proxy-quality tradeoff under pre-registered margins*). All claims map to artifacts above.
2. Distribute the two rater packets (adjudication n=250; A/B n=240) when convenient —
   results integrate without blocking.
3. Optional robustness (cheap): instrumental-side intervention search (the open gap);
   probe-on-evidence re-confirmation on a general-population subset.
4. Release engineering: datasheet + upload destination for the ~60 GB FLAC keep-set and
   ledgers (full WAV corpus exceeds quota headroom to duplicate — manifest provided).
