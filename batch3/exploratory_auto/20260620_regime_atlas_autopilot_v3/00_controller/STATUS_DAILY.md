# STATUS DAILY

## 2026-06-20 — RESUME_STATUS / DAY 0
- completed: output root + controller scaffold; control set (20); sanity_gate_worker.py; imports verified+compiled.
- active: SANITY GATE generation on an17 GPUs0-3 (160 tasks), DETACHED.
- failed: none.
- next safe action: when 4 workers emit SANITY_WORKER_DONE → run sanity_gate_analyze.py → build
  SANITY_GATE_RESULTS.md + manifest + PI_SANITY_GATE_REQUEST.md → **STOP, request PI 10-min sanity check.**
- PI interrupt needed: YES (mandatory non-self-certified sanity gate, §10/§13). Large-N blocked until pass.

## 2026-06-20 — SANITY GATE COMPLETE, AWAITING PI
- 160/160 rows, 0 errors, 0 auto-flags. type-correct: A0.90 B0.825 C0.458 D0.00 E0.375.
- artifacts: SANITY_GATE_RESULTS.{md,json}, SANITY_GATE_AUDIO_MANIFEST.csv, PI_SANITY_GATE_REQUEST.md; 160 FLAC kept.
- next safe action: **STOP. PI 10-min sanity check.** Large-N blocked until PASS.

## 2026-06-20 — HUMAN-EVAL PACKAGE READY
- /tmp/adsr_human_eval_pkg_20260620.tar.gz (3.6GB): 3 GUI tasks + 中文 README + PI-only key isolated.
- NEW sanity-inspection GUI built (was CSV-only). PI sanity PASS/FAIL via GUI now unblocks large-N.
- next: PI distributes tasks 1&2 to raters; PI does task 3 (sanity) -> PASS unlocks large-N critical path.

## 2026-06-21 — RESUME_STATUS / v3.2 LONG-HORIZON START
- **SANITY GATE PASSED (PI approved via v3.2 directive). No further generation gates.**
- mode: async-batch; human items -> HUMAN_BATCH_QUEUE/ (never block compute); spine owns attention, all else soaks compute.
- next action: launch E2 vocal-tail + instrumental-risk large-N BoN N=256 (decisive read = fraction p≈0) across 16 GPUs.
- INTERRUPT_LOG MANDATORY_SANITY_GATE -> RESOLVED(PASS).

## 2026-06-21 — PI SANITY NOTED (verified)
- PI flagged 5 B clips + noted model vocal-bias. Data: Demucs+PANNs agree 7/7 -> labels correct, genuine leak, not artifact. Pipeline OK, spine continues.
- Sharpens RQ4: instrumental-dissociation must test anti-vocal intervention ladder (action-available vs basin) + genre-dependence (S001).

## 2026-06-21 — DECISIVE READ (E2 tail BoN N=256, canonical Demucs, facts-only)
- **n_zero_clean = 0/32** → NO p≈0 strong basin at N=256 (both directions recoverable). Headline "strong escapable basin" currently DEMOTED to rare-but-recoverable (anticipated branch).
- **vocal-miss (17): median p_hat 0.055, min 0.012 = RARE_BUT_RECOVERABLE** (9/17 p≤0.10).
- **instrumental-leak (15): median p_hat 0.36, min 0.195 = SEED_RECOVERABLE** (none ≤0.10).
- CAVEAT: PANNs proxy over-fires (D010) → detector-independence unverified → human-audit queued.
- LEAD S002 (hypothesis): this dissociation may explain the Batch-3 vocal-helped/instrumental-null split.
- artifacts: 01_core_basin_test/DECISIVE_READ.{md,json}. Source: ledgers/bon256_w*.jsonl (8192 rows, 0 err).

## 2026-06-23 — an29 RELEASED (PI request), single-node an17 (8 GPU)
- an29/93896 scancelled (both nodes were idle, Wave A complete, no work lost). an17/93398 retained.
- root cause of idle: no self-replenishing queue across context gaps -> building auto-soak launcher.
- next: analyze Wave A paired interventions; relaunch next wave on an17.

## 2026-06-23 — PAIRED INTERVENTION (facts, top result)
- **VOCAL: V3 conditioning Δp_clean=+0.69 (17/17 improved)** — escapes rare basins.
- **INSTRUMENTAL: I_strong anti-vocal Δp=+0.006 (null)** — seed-recoverable, conditioning adds nothing.
- RQ4 instrumental-leak classified: SEED_RECOVERABLE. Coheres w/ Batch-3 vocal+/instr-null. (S002 candidate headline; detector-independence via human audit pending.)
- artifacts: PAIRED_INTERVENTION_RESULTS.json, V3_QUALITY_MARGIN.json

## 2026-06-23 — SOAK DAEMON LIVE on an17
- self-replenishing daemon runs queued jobs back-to-back on an17 (8 GPU), keeps it busy across context gaps.
- queue: ext512v, ext512i (tail refine N=512), genre_instr (S001 probe), bon256_general (atlas). Drop more .env specs into queue/pending to extend.

## 2026-06-23 — CODEX REVIEW CORRECTION (S002 downgraded)
- Codex BLOCKED S002 headline + caught a ledger-dup bug I introduced (soak daemon reused bon256 tag w/ 8 vs 16 workers).
- FIXED: decisive_read dedups; worker resume scans all shards; dirty ledgers quarantined; clean N=256 frozen (md5 a0509fad), n_zero_clean=0 REPRODUCED.
- DOWNGRADED: S002 to exploratory descriptive facts; V3_QUALITY_MARGIN retracted (biased subset); "conditioning beats reseeding" needs a fair utility metric (at-least-one-clean saturated).
- VALID exploratory facts retained: n_zero_clean=0@N256; p_hat vocal 0.055/instr 0.36 (Demucs label).
