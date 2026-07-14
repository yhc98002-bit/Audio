# CLAIMS.md — Claims-to-Evidence Table (the paper's backbone)

**Created:** 2026-07-06 (task T0.4 of `ADSR_Publication_ToDo_Guide.md` v1.0) ·
**Interim owner:** PI (YHC) until the kickoff meeting assigns the analysis lead ·
**Status of this file:** living document; update a row the moment its pending task lands.

> **RULE (guide §4, T0.4): nothing goes into the paper unless its row in this file is
> complete — exact artifact path, exact number, and owner initials, with no blank cells.**

---

## Path conventions — read before citing anything

- All paths are relative to the repository root (`…/Research/AudioDiffusion/`).
- **Two distinct `batch3/` trees exist. Do not confuse them.**
  - `PH2/` ≡ `orbit-research/adsr_phase2_20260604/` — the pre-registered program
    (phase 0 analyses, EVPD, the live 8-arm online experiment, T2I transfer).
  - `ATLAS/` ≡ `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/` — the June
    retry study / regime atlas (repo-root `batch3/`, **not** the one under `PH2/`).
- Authoritative results index: `PH2/GATE_B_FINAL_REPORT.md` (per PI authorization note in
  `CLAUDE.md`, dated 2026-07-06).

---

## Master table

Verbatim claims from guide §1.2, plus the three required columns. The original
numbers were re-checked against the named artifacts on 2026-07-06; later gate
calls and instrument-scope corrections are dated in the changelog.

| # | Claim (plain words) | Evidence we already have | Evidence still missing → task | Exact artifact path | Exact number | Owner |
|---|---|---|---|---|---|---|
| 1 | Frozen legacy-instrument labels show common apparent constraint violations that are NOT fixed by generate-many-pick-best selection; the same selection pattern appears in image generation too. | Music, legacy 0.1791 instrument: 23% apparent candidate violations, 19.9% apparent selected-winner violations. Images (SDXL): 28.7% of pool, 24.8% after selection. | Corrected-number supersession remains gated on W2 adoption. The frozen music numbers may appear only as legacy-instrument apparent rates. | Music: `PH2/VOCAL_TYPE_ERROR_PREVALENCE.md` (+ `.json`; raw labels `PH2/vocal_presence_raw.jsonl`); legacy-instrument falsification: `PH2/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`. Images: `PH2/t2i/T2I_SIGNATURES.md` (+ `.json`; ledgers `PH2/t2i/gen_ledger_w*.jsonl`, `PH2/t2i/records_w*.jsonl`) | Music, legacy-apparent: candidate type-error **0.2300** (533 vocal-req→no-vocal + 409 instr-req→has-vocal; label threshold 0.1791); survivor top-1 by common score **0.1992** (vocal 0.1867 / instr 0.2194). Images: held-out pool violation **0.287** (presence 0.218 / absence 0.356, n=250 prompts); PickScore top-1 **0.248** | YHC |
| 2 | A free final filter (check the finished audio, discard violators) solves the easy cases. The remaining hard cases are prompts where clean outputs are *rare*, so filtering leaves you with nothing to keep. | Filter-frontier analysis; oracle analysis showing at most +14.9% headroom for any detector-based selection. | Nothing. Ready. | Frontier: `PH2/phase0/P0_1_GATED_FRONTIER.json` (summary `PH2/phase0/P0_123_GATED_REPLAYS.md`). Oracle decomposition: `PH2/phase0/P0_2_ORACLE_DECOMP.json`. Oracle headroom bound: `PH2/batch3/BATCH3_PRELAUNCH_PROTOCOL.md` (endpoint-redesign paragraph, line 12; restated `PH2/GATE_B_FINAL_REPORT.md` §1.3) | Gated frontier (held_out, n=256): bon8_gated type-error **0.0117** [CI95 0.0, 0.0273] = the all-8-fail floor **0.0117** (bon4_gated 0.0391 [0.0195, 0.0625]). Oracle: gated evpd_k4 **0.0195** vs oracle_k4 **0.0117** = oracle_unconstrained **0.0117** (perfect probe closes the whole selection gap; policy structure adds 0). Oracle-probe efficiency upper bound **+14.9%** — infeasible for any detector | YHC |
| 3 | Under frozen legacy-instrument labels, hard failures split into seed-recoverable and rare regimes; changing generation conditions has a strong vocal-direction effect and a weak instrumental-direction effect. | Large-scale retry study plus matched intervention and Stage 3 decomposition. A-prime subsequently falsified the legacy instrument, so these remain legacy-apparent rates until signed corrected-number supersession. | Corrected-number adoption is pending PI 2 signature; no human-validation claim is allowed for the legacy labels. | Retry study: `ATLAS/01_core_basin_test/DECISIVE_READ.md` (+ `.json`); ledgers `ATLAS/01_core_basin_test/ledgers/bon256_w*.jsonl`. Interventions: `ATLAS/01_core_basin_test/PAIRED_INTERVENTION_RESULTS.json`; Stage 3: `PH2/paper_prep/stage3_intervention_20260707/STAGE3_PUBLICATION_READOUT.md`; A-prime: `PH2/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md` | Legacy-apparent per-try clean rate: vocal **0.0862**, instrumental **0.3583**. Condition change: vocal mean delta **+0.6877**, n=17, **17/17 improved**; instrumental mean delta **+0.0063**, n=15, 9/15 improved. Stage 3 rates: vocal guidance **0.781250**, vocal hints **0.093750**, instrumental variants **0.326042-0.377083**. | YHC |
| 4 | An early detector + condition-changing restart wins at equal compute in a live system. B-prime found no statistically significant quality preference in either direction, but the pre-registered non-inferiority bound was not met. | Live 8-group controlled experiment, 22,825 generation attempts: violations 0.98% vs 11.5% at equal compute; more usable outputs (+30%); all automatic quality scores equal or better. B-prime: one expert rated 80 first presentations under the signed primary endpoint, followed by a PI FAIL call for non-inferiority. | No further B-prime rating or study enlargement. The human-quality statement is restricted to the reduced wording below. | Live evidence: `PH2/batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.md` (+ `.json`; blinded twin `_BLINDED.json`); ledgers `PH2/batch3/online_run/ledger_w*.jsonl`; cost `PH2/batch3/ADSR_ONLINE_COST_ACCOUNTING.md` and `PH2/batch3/COST_RECONCILIATION.json`; integrity `PH2/GATE_B_FINAL_REPORT.md` §3. B-prime: `PH2/paper_prep/validation_B_prime/B_PRIME_GATE_REPORT_20260712.md`; `PH2/paper_prep/pi_ratings_20260712/processed/T3_B_PRIME_PRIMARY_OFFICIAL.csv`; `PH2/paper_prep/pi_ratings_20260712/DROP2_STUDY_LOG.jsonl` | Online primary: restart2+ per-draw clean rate arm6−arm4 **+0.4299** CI95 [0.273, 0.5788]; selected type-error arm6 **0.0098** vs arm1 **0.1146**; clean yield **3.7108 vs 2.8614** (+29.7%). B-prime quality: method **20**, baseline **28**, ties **32**; decided preference **20/48 = 0.4167**; one-sided p **0.156163**; score LCB **0.307145** and exact LCB **0.295877**, so the required LCB >0.40 was not met. | YHC |
| 5 | We release the dataset: 4,096 full generation trajectories with mid-generation previews at 5 noise levels, quality scores, frozen legacy vocal labels, and the complete logs of the live experiment. | All data exists on the cluster. | Documentation/hosting remain; the card must identify 0.1791 labels as legacy-instrument outputs that failed A-prime validation, not human-validated truth. | Trajectory table: `orbit-research/trajectory_candidate_dataset.jsonl` (frozen - never modify). Detector: `PH2/batch2/evpd_sigma08_online.joblib` (frozen; threshold 0.728; card `PH2/EVPD_MODEL_CARD.md`). A-prime decision: `PH2/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`. Ledgers: `ATLAS/01_core_basin_test/ledgers/*.jsonl` + `PH2/batch3/online_run/ledger_w*.jsonl`. | **4,096** trajectory rows; previews at 5 sigma levels; EVPD sigma0.8 AUC **0.92**; legacy vocal-label threshold **0.1791**; corrected T6 instrument held-out balanced accuracy **0.987308**. | YHC |
| 6 (optional) | The same pattern holds on a second music model. | None. | Stage 4 (**T4.1**), hard stop 2026-08-07 — the paper ships without it if late | — (to be created: `paper_prep/T41_second_model_decision.md`) | — | ____ (assign at kickoff) |
| 7 | The legacy 0.1791 Demucs-energy label instrument is not validated; a separately evaluated corrected instrument supplies the paper's label-validity evidence. | A-prime is a completed 690-row provenance-enforced falsification study. T6 selected on 60 train rows and evaluated the 100 held-out rows once, with a 20-pair hidden-repeat block. | Broad adoption of corrected-number supersession still needs the missing PI 2 signature; this does not change the validity result itself. | A-prime gate: `PH2/paper_prep/validation_A_prime/A_PRIME_GATE_REPORT_20260713.md`; audit/log: `PH2/paper_prep/validation_A_prime/A_PRIME_GATE_CALL_AUDIT_20260713.json`, `PH2/paper_prep/validation_A_prime/A_PRIME_STUDY_LOG.jsonl`; T6: `PH2/paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`, `PH2/paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md` | `A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`; legacy matches **7/112** disagreement, **16/47** rare-basin decided, **28/30** controls, **124/493** stratified global. T6: balanced accuracy **0.987308**, sensitivity **1.000000**, specificity **0.974616**, repeat agreement **20/20** for Label A and **20/20** for Label B. | pi:Richard |

---

## Verification notes (discrepancies found while filling this table — resolve before drafting)

- **V1 — Retry-study denominator.** Guide §1.2/§3 says "16,384 generations across the 32
  hardest prompts"; the hash-frozen core read is **8,192 rows** (32×256, md5 above; the hash
  file records 128 duplicate rows dropped and 58 ext512 rows ≥256 excluded, with `ext512*`
  extension-wave logs present in `ATLAS/01_core_basin_test/ledgers/`). T2.1 must reconcile
  the exact count from the ledgers before any total is printed in the paper. Until then,
  cite "8,192 frozen draws (32 prompts × 256 tries)".
- **V2 — Probe cost.** `PH2/GATE_B_FINAL_REPORT.md` §1.5 reports measured-online EVPD
  ≈0.9 s/probe vs score-probe ≈52 s/probe; `PH2/batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.md`
  quotes ≈0.3 s / ≈40 s (nominal) with arm-3 actual 52 h vs 2.7 h nominal. The Fig-5 owner
  must pin the measured wall-clock number from `PH2/batch3/ADSR_ONLINE_COST_ACCOUNTING.md`
  before the 0.9 s figure is used.
- **V3 — Medians.** The clean-rate medians 6.4% (vocal-hard) / 36.1% (instrumental-hard)
  appear in guide §3 but are not yet in a machine-readable artifact; T2.1's spot-check
  reproduces them into `paper_prep/T21_efficiency_metrics.csv`, which then becomes the
  citable artifact for Claim 3's regime constants ("~1 in 3" vs "~1 in 16").
- **V4 — Study-B pair count.** The prepared A/B packet contains 240 blinded pairs
  (`PH2/phase3/human_ab/response_sheet.csv`); guide T1.3 defines the gate on 80 pairs
  (40 G6-vs-G1 + 40 G6-vs-G4). The gate is evaluated on the pre-registered primary subset;
  see the note in `paper_prep/HUMAN_STUDY_CRITERIA_FROZEN.md`.

## Standing caveats that must travel with these numbers (guide §10.7)

- Every absolute rate from the live experiment (0.98%, 11.5%, 6.6%, …) carries: *"on a test
  set deliberately weighted toward failure-prone prompts; between-group comparisons are the
  valid reading."*
- Never imply that the legacy 0.1791 Demucs-energy detector was validated. A-prime
  falsified it: 7/112 disagreement matches, 16/47 rare-basin matches among
  decided rows, and 28/30 control matches. Frozen rates derived from it are
  called `legacy-instrument apparent rates`.
- Positive label-validity wording is instrument-scoped to T6: the corrected
  instrument achieved held-out design-weighted balanced accuracy 0.987308,
  sensitivity 1.000000, and specificity 0.974616, with 20/20 hidden-repeat
  agreement on both Label A and Label B. Do not call this an A-prime PASS.

### B-prime draft wording

Use exactly:

> no statistically significant quality preference in either direction (method
> preferred in 42% of decided pairs; one-sided p = 0.156); the pre-registered
> non-inferiority bound (LCB > 0.40) was NOT met, so no-quality-degradation is
> reported as unconfirmed, not established.

Do not use `no quality loss`, `no degradation`, or `quality preserved`.

## Limitations

- A-prime tests Label A (perceived voice presence), while the signed amendment's
  paper-primary endpoint is request-conditional Label B.
- The legacy 0.1791 instrument failed A-prime. Frozen results that use it are
  retained as legacy-instrument apparent rates; they are not human-validated truth.
- The T6 split/evaluation supplies corrected-instrument validity, but its broad
  corrected-number supersession remains gated on the missing PI 2 adoption signature.
- B-prime used a single expert rater.
- The primary quality endpoint had 32 ties among 80 pairs, a 40% tie rate.
- B-prime pairs were selected under the pre-W2 detector.
- The t4 reverse block was completed in the same session as t3, violating the
  later-day rule; its agreement figures are upper bounds, and the t6 hidden
  repeats supersede it as the primary rater-stability evidence.

## Changelog

- 2026-07-14 (pi:Richard decision dated 2026-07-13): recorded
  `A_PRIME_GATE = FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED`; closed A-prime as a
  690-row falsification of the legacy 0.1791 instrument and moved the positive
  label-validity basis to the separate T6 held-out corrected-instrument result.
- 2026-07-12 (pi:Richard): recorded
  `B_PRIME_GATE = FAIL_NONINFERIORITY_NOT_ESTABLISHED`; replaced the quality
  placeholder with reduced wording and added the four disclosed limitations.
- 2026-07-06 (YHC/PI-authorized): file created; Claim 1 and Claim 2 rows fully filled and
  verified against raw artifacts; Claims 3–5 filled for existing evidence with pending-task
  blanks; Claim 6 open. Verification notes V1–V4 recorded.
