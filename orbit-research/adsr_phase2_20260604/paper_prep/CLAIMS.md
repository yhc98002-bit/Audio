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

Verbatim claims from guide §1.2, plus the three required columns. Every number below was
re-checked against the named artifact on 2026-07-06 (not against summary prose).

| # | Claim (plain words) | Evidence we already have | Evidence still missing → task | Exact artifact path | Exact number | Owner |
|---|---|---|---|---|---|---|
| 1 | Constraint violations are common and are NOT fixed by generate-many-pick-best selection; the same pattern appears in image generation too. | Music: 23% of candidates, 19.9% of selected winners. Images (SDXL): 28.7% of pool, 24.8% after selection. | Nothing. Ready. | Music: `PH2/VOCAL_TYPE_ERROR_PREVALENCE.md` (+ `.json`; raw labels `PH2/vocal_presence_raw.jsonl`). Images: `PH2/t2i/T2I_SIGNATURES.md` (+ `.json`; ledgers `PH2/t2i/gen_ledger_w*.jsonl`, `PH2/t2i/records_w*.jsonl`) | Music: candidate type-error **0.2300** (533 vocal-req→no-vocal + 409 instr-req→has-vocal; label threshold 0.1791); survivor top-1 by common score **0.1992** (vocal 0.1867 / instr 0.2194). Images: held-out pool violation **0.287** (presence 0.218 / absence 0.356, n=250 prompts); PickScore top-1 **0.248** | YHC |
| 2 | A free final filter (check the finished audio, discard violators) solves the easy cases. The remaining hard cases are prompts where clean outputs are *rare*, so filtering leaves you with nothing to keep. | Filter-frontier analysis; oracle analysis showing at most +14.9% headroom for any detector-based selection. | Nothing. Ready. | Frontier: `PH2/phase0/P0_1_GATED_FRONTIER.json` (summary `PH2/phase0/P0_123_GATED_REPLAYS.md`). Oracle decomposition: `PH2/phase0/P0_2_ORACLE_DECOMP.json`. Oracle headroom bound: `PH2/batch3/BATCH3_PRELAUNCH_PROTOCOL.md` (endpoint-redesign paragraph, line 12; restated `PH2/GATE_B_FINAL_REPORT.md` §1.3) | Gated frontier (held_out, n=256): bon8_gated type-error **0.0117** [CI95 0.0, 0.0273] = the all-8-fail floor **0.0117** (bon4_gated 0.0391 [0.0195, 0.0625]). Oracle: gated evpd_k4 **0.0195** vs oracle_k4 **0.0117** = oracle_unconstrained **0.0117** (perfect probe closes the whole selection gap; policy structure adds 0). Oracle-probe efficiency upper bound **+14.9%** — infeasible for any detector | YHC |
| 3 | The hard failures split into two regimes by how often a fresh seed succeeds: "seed-recoverable" (retry works, ~1 in 3) vs "rare" (~1 in 16). Changing generation conditions helps enormously in the rare regime (+0.69 success per try, 17/17 prompts improved) and does nothing in the seed-recoverable regime (+0.006). | Large-scale retry study: 16,384 generations across the 32 hardest prompts, plus 4,096 paired intervention generations. | (a) Human confirmation of the vocal labels on hard prompts → **T1.2**. (b) Matched-intervention controlled test → **T3.1**. Also: T2.1 reproduces the medians and reconciles the exact generation count (see note V1) | Retry study: `ATLAS/01_core_basin_test/DECISIVE_READ.md` (+ `.json`); ledgers `ATLAS/01_core_basin_test/ledgers/bon256_w*.jsonl` (frozen: `bon256_N256_FROZEN.hash`, md5 `a0509fad5b7854c4f7e3d26e7fbcb416`, 8,192 clean rows = 32×256). Interventions: `ATLAS/01_core_basin_test/PAIRED_INTERVENTION_RESULTS.json`; ledgers `.../ledgers/v3_vocal_w*.jsonl`, `.../ledgers/istrong_instr_w*.jsonl` | Per-try clean rate (S_1, frozen read): vocal **0.0862**, instrumental **0.3583**; 0/32 prompts with zero clean outputs. Medians ≈6.4% / 36.1% (guide §3; reproduce in T2.1 → note V3). Condition change: vocal mean Δp̂ **+0.6877**, n=17, **17/17 improved**; instrumental mean Δp̂ **+0.0063**, n=15, 9/15 improved | YHC (pending: T1.2 ____, T3.1 ____) |
| 4 | An early detector + condition-changing restart wins at equal compute in a live system. B-prime found no statistically significant quality preference in either direction, but the pre-registered non-inferiority bound was not met. | Live 8-group controlled experiment, 22,825 generation attempts: violations 0.98% vs 11.5% at equal compute; more usable outputs (+30%); all automatic quality scores equal or better. B-prime: one expert rated 80 first presentations under the signed primary endpoint, followed by a PI FAIL call for non-inferiority. | No further B-prime rating or study enlargement. The human-quality statement is restricted to the reduced wording below. | Live evidence: `PH2/batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.md` (+ `.json`; blinded twin `_BLINDED.json`); ledgers `PH2/batch3/online_run/ledger_w*.jsonl`; cost `PH2/batch3/ADSR_ONLINE_COST_ACCOUNTING.md` and `PH2/batch3/COST_RECONCILIATION.json`; integrity `PH2/GATE_B_FINAL_REPORT.md` §3. B-prime: `PH2/paper_prep/validation_B_prime/B_PRIME_GATE_REPORT_20260712.md`; `PH2/paper_prep/pi_ratings_20260712/processed/T3_B_PRIME_PRIMARY_OFFICIAL.csv`; `PH2/paper_prep/pi_ratings_20260712/DROP2_STUDY_LOG.jsonl` | Online primary: restart2+ per-draw clean rate arm6−arm4 **+0.4299** CI95 [0.273, 0.5788]; selected type-error arm6 **0.0098** vs arm1 **0.1146**; clean yield **3.7108 vs 2.8614** (+29.7%). B-prime quality: method **20**, baseline **28**, ties **32**; decided preference **20/48 = 0.4167**; one-sided p **0.156163**; score LCB **0.307145** and exact LCB **0.295877**, so the required LCB >0.40 was not met. | YHC |
| 5 | We release the dataset: 4,096 full generation trajectories with mid-generation previews at 5 noise levels, all quality scores, vocal labels, and the complete logs of the live experiment. | All data exists on the cluster. | Documentation sheet + hosting decision → **T5.5** | Trajectory table: `orbit-research/trajectory_candidate_dataset.jsonl` (frozen — never modify). Detector: `PH2/batch2/evpd_sigma08_online.joblib` (frozen; threshold 0.728; card `PH2/EVPD_MODEL_CARD.md`). Ledgers: `ATLAS/01_core_basin_test/ledgers/*.jsonl` + `PH2/batch3/online_run/ledger_w*.jsonl`. Audio release keep-set: `PH2/paper_prep/storage_triage/RELEASE_KEEP_MANIFEST.csv`; protection/deletion audit: `PH2/paper_prep/storage_triage/STORAGE_TRIAGE.md` + `PH2/paper_prep/storage_triage/PROTECTED_AUDIO_UNION.csv` | **4,096** trajectory rows (verified `wc -l`, 2026-07-06); previews at 5 sigma levels; EVPD σ0.8 AUC **0.92** (held-out; `PH2/EVPD_RESULTS.md`), threshold **0.728**; vocal-label threshold **0.1791** | YHC (pending: T5.5 ____) |
| 6 (optional) | The same pattern holds on a second music model. | None. | Stage 4 (**T4.1**), hard stop 2026-08-07 — the paper ships without it if late | — (to be created: `paper_prep/T41_second_model_decision.md`) | — | ____ (assign at kickoff) |

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
- Detector-dependent statements are written as *"automatic labels agreed with human majority
  in X% of audited cases (Study A)"* — X pending T1.2.

### B-prime draft wording

Use exactly:

> no statistically significant quality preference in either direction (method
> preferred in 42% of decided pairs; one-sided p = 0.156); the pre-registered
> non-inferiority bound (LCB > 0.40) was NOT met, so no-quality-degradation is
> reported as unconfirmed, not established.

Do not use `no quality loss`, `no degradation`, or `quality preserved`.

## Limitations

- B-prime used a single expert rater.
- The primary quality endpoint had 32 ties among 80 pairs, a 40% tie rate.
- B-prime pairs were selected under the pre-W2 detector.
- The t4 reverse block was completed in the same session as t3, violating the
  later-day rule; its agreement figures are upper bounds, and the t6 hidden
  repeats supersede it as the primary rater-stability evidence.

## Changelog

- 2026-07-12 (pi:Richard): recorded
  `B_PRIME_GATE = FAIL_NONINFERIORITY_NOT_ESTABLISHED`; replaced the quality
  placeholder with reduced wording and added the four disclosed limitations.
- 2026-07-06 (YHC/PI-authorized): file created; Claim 1 and Claim 2 rows fully filled and
  verified against raw artifacts; Claims 3–5 filled for existing evidence with pending-task
  blanks; Claim 6 open. Verification notes V1–V4 recorded.
