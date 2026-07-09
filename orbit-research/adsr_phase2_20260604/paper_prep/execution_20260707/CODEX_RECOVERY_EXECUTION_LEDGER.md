# Codex Recovery Execution Ledger

Workspace: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion`

## 2026-07-07T12:37:47-07:00

- Node/host: login host
- Command/script path: shell probe, `test -f orbit-research/adsr_phase2_20260604/paper_prep/execution_20260707/CODEX_RECOVERY_EXECUTION_LEDGER.md`
- Input artifacts: expected ledger path
- Output artifacts: none
- Status: PASS
- Result: ledger was missing before recovery execution began.
- Next action: create this ledger, then read required project context before making publication-package changes.

## 2026-07-07T12:38:40-07:00

- Node/host: login host
- Command/script path: read-only context scan via `rg --files`, `find`, `sed`, and `ls -ld`
- Input artifacts: `ADSR_Publication_ToDo_Guide.md`, `CLAUDE.md`, `WHAT_HAVE_I_DONE_20260707.md`, expected `PLAN.md`, publication-prep artifact trees
- Output artifacts: none
- Status: PASS_WITH_CONFLICT_NOTE
- Result: `paper_prep/` is a symlink to `orbit-research/adsr_phase2_20260604/paper_prep/`; no current `PLAN.md` was present; `CLAUDE.md` contains a literal DashScope API key, which must not be copied into releaseable artifacts.
- Next action: locate missing transcript if present, read final preregistration/audit/summary/blocker files, then verify frozen Stage 3 and N2 evidence from disk.

## 2026-07-07T12:42:53-07:00

- Node/host: login host
- Command/script path: raw-ledger verification via Python one-off; checksum freeze via `sha256sum`; Markdown artifact creation via `apply_patch`
- Input artifacts: Stage 3/N2 full-run ledgers, final audits, final summaries, preregistrations, storage triage manifests, judge blocker files
- Output artifacts: `paper_prep/PUBLICATION_ARTIFACT_INVENTORY_20260707.md`, `paper_prep/FROZEN_ARTIFACT_CHECKSUMS_20260707.tsv`, `paper_prep/STORAGE_TRIAGE.md`
- Status: PASS
- Result: Stage 3 verified at 6,144 unique full-run rows with expected condition rates; N2 verified at 16,384 unique full-run rows with expected regime counts; 30 frozen-artifact checksums written; current quota recorded at 251,864,920 KB of 524,288,000 KB soft quota. No deletion was performed in this recovery pass.
- Next action: create judge smoke failure-analysis table from raw logs and audio metadata.

## 2026-07-07T12:46:02-07:00

- Node/host: login host
- Command/script path: `paper_prep/scripts/judge_smoke_failure_analysis.py`; `paper_prep/scripts/judge_format_probe.py`
- Input artifacts: repaired smoke manifest, repaired Plus/Flash raw JSONL logs, repaired Plus/Flash smoke summaries, fixed positive/negative smoke clips
- Output artifacts: `paper_prep/judge_debug/JUDGE_SMOKE_FAILURE_ANALYSIS_20260707.md`, `paper_prep/judge_debug/JUDGE_SMOKE_FAILURE_ANALYSIS_20260707.csv`, `paper_prep/judge_debug/JUDGE_SMOKE_METADATA_20260707.csv`, `paper_prep/judge_debug/JUDGE_FORMAT_PROBE_20260707.json`, `paper_prep/judge_raw/format_probe_20260707.jsonl`
- Status: BLOCKED
- Result: both repaired smokes remain FAIL at 6/10. Parser failure was ruled out for the repaired smoke; local audio metadata shows no near-silent clips; FLAC and WAV transport both worked on a fixed positive/negative format probe. The remaining unresolved issue is four expected-negative labels that both Qwen models unanimously judged as vocal/voice.
- Next action: keep A-prime/B-prime scale calls blocked; proceed with non-judge analysis packaging from existing ledgers.

## 2026-07-07T13:09:18-07:00

- Node/host: login host and an29
- Command/script path: `paper_prep/scripts/build_publication_analysis_package.py`; `paper_prep/scripts/clap_fidelity_score.py`; `paper_prep/scripts/router_replay.py`; Markdown edits via `apply_patch`
- Input artifacts: T21 metrics, Stage 3 final summary/audit, N2 final readout/audit, CLAP fidelity input manifest, held-out prompts, online-run selected FLACs, ATLAS baseline/intervention ledgers
- Output artifacts: `paper_prep/figures/fig2_regime_data.csv`, `paper_prep/figures/fig2_regime_plot.png`, `paper_prep/figures/fig2_regime_plot.pdf`, `paper_prep/analysis/expected_draws_metrics.csv`, `paper_prep/analysis/efficiency_claims.md`, `paper_prep/stage3_intervention_20260707/STAGE3_PUBLICATION_READOUT.md`, `paper_prep/population_retry_20260707/N2_PUBLICATION_READOUT.md`, `paper_prep/clap_fidelity/CLAP_FIDELITY_REPORT.md`, `paper_prep/router_replay/ROUTER_REPLAY_REPORT.md`, `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md`, `paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md`, `paper_prep/PLAN.md`, `paper_prep/FINAL_PREDRAFT_AUDIT_20260707.md`
- Status: READY_WITH_REDUCED_CLAIMS
- Result: efficiency/Figure 2, Stage 3 read-out, N2 read-out, CLAP scoring, router replay, PLAN closure, and final audit were produced. CLAP scored 1,261/1,261 rows with 0 errors; paired arm6-arm1 mean delta was +0.005996 with CI crossing zero, so wording is reduced/ambiguous. Router replay was NO-GO for live rare-router confirmation under the tested rule. A-prime and B-prime remain BLOCKED by judge-smoke failure.
- Next action: refresh final checksums and report reduced-claim package status.
