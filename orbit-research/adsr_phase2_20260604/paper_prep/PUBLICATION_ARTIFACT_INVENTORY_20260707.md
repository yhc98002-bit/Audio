# Publication Artifact Inventory

Generated: 2026-07-07

Scope: publication-prep evidence under `orbit-research/adsr_phase2_20260604/paper_prep/`.

## Stage 3 Intervention Decomposition

- Status: complete, audited, frozen evidence.
- Pre-registration: `paper_prep/STAGE3_INTERVENTION_PREREG_20260707.md`
- Ledgers: `paper_prep/stage3_intervention_20260707/ledgers/full64_w*.jsonl`
- Final audit: `paper_prep/stage3_intervention_20260707/full64_final_ledger_audit.md`
- Final summary: `paper_prep/stage3_intervention_20260707/full64_final_summary.md`
- Raw-ledger verification: 8 ledger files, 6,144 rows, 6,144 unique
  `(prompt_id, condition, seed_idx)` keys.
- Audio files under Stage 3 tree: 6,244 FLACs total including smoke artifacts;
  full-run summary reports 6,144 kept full-run FLACs.
- Audit result: PASS; 0 parse errors, 0 missing required rows, 0 duplicate keys,
  0 generation errors, 0 near-silent rows, 0 missing FLACs.

| Condition | Rows | Type-correct rate |
|---|---:|---:|
| `vocal_guidance` | 1088 | 0.781250 |
| `vocal_both` | 1088 | 0.779412 |
| `vocal_hints` | 1088 | 0.093750 |
| `instr_both` | 960 | 0.377083 |
| `instr_sampler` | 960 | 0.344792 |
| `instr_text` | 960 | 0.326042 |

## N2 Population Retry Map

- Status: complete, audited, frozen evidence.
- Pre-registration: `paper_prep/POPULATION_RETRY_PREREG_20260707.md`
- Manifest: `paper_prep/population_retry_20260707/population_retry_manifest_128.jsonl`
- Ledgers: `paper_prep/population_retry_20260707/ledgers/full128_w*.jsonl`
- Final audit: `paper_prep/population_retry_20260707/full128_final_ledger_audit.md`
- Final summary: `paper_prep/population_retry_20260707/full128_final_summary.md`
- Regime read-out: `paper_prep/population_retry_20260707/full128_regime_readout.md`
- Prompt clean rates: `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`
- Raw-ledger verification: 8 ledger files, 16,384 rows, 16,384 unique
  `(prompt_id, seed_idx)` keys, 128 prompts.
- Audio files under N2 tree: 16,434 FLACs total including smoke artifacts;
  full-run summary reports 16,384 kept full-run FLACs.
- Audit result: PASS; 0 parse errors, 0 missing required rows, 0 duplicate keys,
  0 generation errors, 0 near-silent rows, 0 missing FLACs.

| Regime | Prompts | Fraction |
|---|---:|---:|
| `easy_ge_1_in_2` | 67 | 0.523438 |
| `seed_recoverable_1_in_4_to_1_in_2` | 33 | 0.257812 |
| `low_1_in_16_to_1_in_4` | 23 | 0.179688 |
| `rare_le_1_in_16` | 5 | 0.039062 |

Strata:

- Instrumental: 47 prompts, mean clean rate 0.761137.
- Vocal: 81 prompts, mean clean rate 0.401331.

## Existing Efficiency Metrics

- Metrics report: `paper_prep/execution_20260707/T21_efficiency_metrics.md`
- CSV: `paper_prep/execution_20260707/T21_efficiency_metrics.csv`
- JSON: `paper_prep/execution_20260707/T21_efficiency_metrics.json`
- Citation note: `paper_prep/execution_20260707/T21_CITATION_NOTE.md`
- Baseline audit: `paper_prep/execution_20260707/bon256_ledger_audit.md`
- Key values already reproduced:
  - Baseline rows: 16,384 raw and 16,384 deduplicated.
  - Vocal baseline median/mean: 0.064453 / 0.088120.
  - Instrumental baseline median/mean: 0.361328 / 0.359115.
  - V3 vocal intervention mean delta: +0.685777; 17/17 prompts improved.
  - I_strong instrumental intervention mean delta: +0.005469; 9/15 prompts improved.

## Judge Status

- Original raw smoke log: `paper_prep/judge_raw/smoke_10clip_20260706.jsonl`
- Repaired manifest: `paper_prep/execution_20260707/judge_smoke_manifest_repaired.csv`
- Repaired Plus raw log: `paper_prep/judge_raw/smoke_10clip_repaired_20260707.jsonl`
- Repaired Flash raw log: `paper_prep/judge_raw/smoke_10clip_repaired_flash_20260707.jsonl`
- Plus summary: `paper_prep/execution_20260707/judge_smoke_repaired_stdout.json`
- Flash summary: `paper_prep/execution_20260707/judge_smoke_repaired_flash_stdout.json`
- Blocker: `paper_prep/execution_20260707/JUDGE_SMOKE_BLOCKED_20260707.md`
- Status: BLOCKED. Both repaired smokes failed 6/10. No A-prime or B-prime
  scale calls were run.

## Stage 4 SAO Status

- Blocker: `paper_prep/execution_20260707/STAGE4_SAO_BLOCKED_20260707.md`
- Status: BLOCKED. `stable_audio_tools` is absent; direct install into shared
  `audio-prm` would upgrade torch, torchaudio, and CUDA dependencies.
- Constraint: do not mutate shared `audio-prm`.

## Storage State

- Current quota command: `lfs quota -u pxy1289 .`
- Current usage: 251,864,920 KB of 524,288,000 KB soft quota
  (about 240.2 GiB of 500 GiB).
- Existing storage triage package: `paper_prep/storage_triage/STORAGE_TRIAGE.md`
- Top-level storage report: `paper_prep/STORAGE_TRIAGE.md`
- Existing deletion manifest: `paper_prep/storage_triage/DELETED_AUDIO_MANIFEST.csv`
- Protected keep-list: `paper_prep/storage_triage/PROTECTED_AUDIO_UNION.csv`
- No deletion was performed while creating this inventory.

## Checksum Freeze

- Checksum file: `paper_prep/FROZEN_ARTIFACT_CHECKSUMS_20260707.tsv`
- Entries: 30 Stage 3/N2 preregistration, ledger, summary, audit, manifest, and read-out files.

## Missing Publication Artifacts

- Full-guide A-prime and B-prime validation remain blocked by judge-smoke
  failure.
- A-prime label validation is blocked by failed judge smoke or missing approved fallback.
- B-prime quality validation is blocked by failed judge smoke or missing approved fallback.
- Stage 4 SAO remains blocked by missing isolated dependency environment.
- Release-day secret hygiene remains open before any public code/data release.

Completed after the initial inventory scan:

- Claim table: `paper_prep/PLAN.md`
- Judge failure analysis: `paper_prep/judge_debug/JUDGE_SMOKE_FAILURE_ANALYSIS_20260707.md`
- Figure 2 and efficiency claims: `paper_prep/figures/` and `paper_prep/analysis/`
- Stage 3 read-out: `paper_prep/stage3_intervention_20260707/STAGE3_PUBLICATION_READOUT.md`
- N2 read-out: `paper_prep/population_retry_20260707/N2_PUBLICATION_READOUT.md`
- CLAP fidelity: `paper_prep/clap_fidelity/CLAP_FIDELITY_REPORT.md`
- Router replay: `paper_prep/router_replay/ROUTER_REPLAY_REPORT.md`
- Final pre-draft audit: `paper_prep/FINAL_PREDRAFT_AUDIT_20260707.md`
