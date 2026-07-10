# Current Canonical Files (ADSR publication recovery state, 2026-07-09)

This index is the current reading path for the project. Files not listed here are
either raw evidence, archived history, package snapshots, or intermediate agent
outputs.

**Current framing: Axis-Deferred Speculative Restart (ADSR)** — the project's third
framing (M-PRM → ETV → ADSR). ADSR = compute reallocation via
RESTART/DEFER/CONTINUE; presence-vs-content split; learned EVPD; lyric as a
first-class late-observable axis. ETV Early-Tweedie pruning remains the **baseline
(raw ETP)**; M-PRM/section credit is **boundary** evidence.

**PI authorization note (2026-07-06):** the PI has reviewed and authorized the June
ADSR program and its results. The previous "awaiting STOP-A approval" status is
superseded. The current authoritative results index is
`orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md`, with retry-study
logs under `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/`.

Current scientific state:

- **Foundation evidence (exists; ADSR's anchor):** H1 headroom; H2 Tweedie predictive
  signal; Track A raw-ETP pruning `STRONG_CANDIDATE` (now the baseline); Track B
  globalness (mechanism); lyric axis fixed to EN-vocal (0.682, n=282); C6 RL boundary
  (`COMMON_DEV_NO_CLEAR_WIN`).
- **Gate-B ADSR result state (authorized):** see
  `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` for the validated
  claim chain, process-integrity notes, scope caveats, and deliverables index.
- **Retry / robustness work:** logs and compact artifacts live under
  `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/`.
- **Backbone identity:** frozen Batch 1/2/3, Stage 3, N2, and ATLAS evidence is
  ACE-Step v1. The misleading adapter logical name is not evidence of v1.5.
- **Publication recovery:** Stage 3, N2, Batch-3 reanalysis v2, publication
  statistics v2, and the SA3 pilot are complete. A-prime and B-prime remain
  unrated human gates. The bounded ACE-Step v1.5 replication is tracked under
  `paper_prep/v15_replication_20260709/`.
- **Operational node split:** `an12` runs ACE-Step v1.5 replication; `an29`
  runs ADSR detector/calibration and SA3 follow-up. `an17` is not allocated.

## 1. Start Here

| File | Role |
|---|---|
| `orbit-research/adsr_phase2_20260604/paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md` | **Current publication/code-review recovery status contract.** |
| `orbit-research/adsr_phase2_20260604/paper_prep/GATE_B_SUPERSESSION_NOTE_20260709.md` | Explains which later audits refine Gate-B without rewriting frozen evidence. |
| `Code_Review_Guide.md` | Concise source and evidence review path. |
| `orbit-research/adsr_phase2_20260604/GATE_B_FINAL_REPORT.md` | **Authoritative current results index for the PI-authorized June ADSR program.** |
| `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/` | Retry-study logs and compact artifacts for the current robustness line. |
| `experiment_plan_current.md` | Current execution plan following Gate-B authorization. |
| `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` | **PI-frozen FINAL ADSR plan (authoritative current direction).** |
| `refine-logs/ADSR_REFRAME_BRIEF.md` | Single-source ADSR reframe anchor (method, H1-H6, C1-C6, E1-E9, evidence status). |
| `refine-logs/FINAL_PROPOSAL.md` **v4.0** | Current ADSR proposal (C1-C6, E1-E9, evidence-status section). |
| `refine-logs/EXPERIMENT_PLAN.md` **v4.0** | Current experiment-plan index (E1-E9; points to EXPERIMENT_PLAN_EXEC.md v4.0). |
| `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` | Lyric fix (0.682 EN-vocal n=282) + the 2026-06-03 prompt regen. |
| `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md` | English synthesis of foundation experiment progress (ETV-era; foundation evidence). |
| `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` | Current PI report for the trajectory-aware cycle. |
| `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md` | Completion audit for Track A / B / C and boundary checks. |
| `orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.md` | Machine-readable-ish current goal status summary. |

## 2. Foundation result (now the ADSR baseline): Early-Tweedie Pruning ("raw ETP")

Under ADSR this is the **strong baseline**, not the headline — fixed-pool selection is
low-stakes (median regret ≈ 0; raw-ETP@50 over BoN-4 ≈ +0.0036), which is *why* ADSR
reallocates compute via restart. Regenerated 2026-06-04 on the lyric-fix dataset.

| File | Role |
|---|---|
| `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` | 512-prompt / 4096-candidate BoN-8 pruning validation report (raw-ETP baseline). |
| `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json` | Validation metrics. |
| `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv` | Plot-ready schedule table. |
| `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv` | Plot-ready winner-retention table. |
| `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` | PI decision memo (raw-ETP baseline; regenerated 2026-06-04). |
| `orbit-research/trajectory_candidate_dataset.jsonl` | **Canonical reward set** (4096 candidates; promoted 2026-06-04 after lyric fix). |
| `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` | Lyric axis fix (0.682 EN-vocal n=282) + regen provenance. |

Primary robust/common results (foundation; now the baseline ADSR must beat via restart):

- Schedule A, sigma0.9 top4 -> sigma0.7 top2 -> final top1: reward fraction `0.9864` at compute fraction `0.5000` (regenerated 2026-06-04; was `0.9858` on 2026-05-28, within noise).
- Bottom-prune sigma0.7 remove bottom25: false-negative `0.0195`.
- Lyric axis (EN-vocal only): `0.682` ETP@50, n=282 (instrumental 1.0 sentinel masked, non-EN excluded).
- Random pruning at matched compute is much worse.

## 3. Mechanism Result: Global / Time-Uniform Quality

| File | Role |
|---|---|
| `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` | Current Track B analysis and interpretation. |
| `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.json` | Structured Track B metrics. |
| `orbit-research/global_quality_structure_analysis_20260527/` | Plot-ready CSV tables. |

Primary readout:

- median between-share `0.5839`
- between/within ratio `1.4038`
- crossing frequency `0.0000`
- globalness index `0.8613`

Interpretation: FixedWin is more consistent with a stable local proxy for global
quality than with true isolated local temporal credit.

## 4. C1 RL First-Wave Evidence

| File | Role |
|---|---|
| `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` | Shared common dev eval. Current verdict: no clear common-metric winner. |
| `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md` | C1 training health and ratio/KL/adapter dynamics audit. |
| `orbit-research/PHASE_C1_CHECKPOINT_TRIAGE_EVAL_2026-05-26.md` | Small checkpoint triage eval; no checkpoint rescue. |
| `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` | Explicit decision to stop bounded RL rescue before GPU launch. |
| `runs/phase_c1_firstwave_20260524_researcher_go_01/` | Raw C1 training run root. |
| `runs/phase_c1_common_downstream_eval_20260526_helper01/` | Common downstream dev eval run root. |
| `runs/phase_c1_checkpoint_triage_eval_20260526/` | Checkpoint triage eval run root. |

Common dev robust-LCB means:

| Target | robust_lcb_mean | Delta vs Base |
|---|---:|---:|
| Base | 2.133676 | 0.000000 |
| R8a step1000 | 2.145297 | +0.011621 |
| R8b step1000 | 2.148166 | +0.014490 |
| M-FixedWin step1000 | 2.145825 | +0.012149 |
| M-Section step1000 | 2.146055 | +0.012379 |

Interpretation: C1 is an engineering success, not a scientific method-ranking win.

## 5. Prior Hypothesis Evidence

| File | Role |
|---|---|
| `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md` | Canonical H2 conclusion. |
| `runs/phase_b1_reliability/H2_VERDICT.md` | Markdown view of canonical H2 verdict. |
| `runs/phase_b1_reliability/H2_VERDICT.json` | Canonical H2 verdict data. |
| `runs/phase_b1_reliability/figures/` | H2 merged figure JSON/CSV/MD outputs. |
| `orbit-research/H3_CREDIT_UNIT_INTERPRETATION_2026-05-23.md` | Canonical H3 interpretation after corrected held-out v2. |
| `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/` | H3 held-out v2 run root. |
| `orbit-research/R050_SUMMARY.md` | Historical R050 mini-headroom probe summary. |

## 6. Governance And Method Contracts (CURRENT — ADSR v4.0)

These are the **current** canonical proposal/method/contract files (reframed to ADSR
v4.0 on 2026-06-04). The pre-ADSR (v3.0 ETV) versions are archived at
`orbit-research/archive/etv_pre_adsr_20260604/`; each v1.3 contract carries a
"2026-06-04 ADSR Pivot Addendum" that supersedes its earlier "2026-05-28 ETV Pivot
Addendum" (both retained).

| File | Role |
|---|---|
| `refine-logs/FINAL_PROPOSAL.md` **v4.0** | **Current ADSR proposal** (C1-C6, ADSR method + EVPD, E1-E9, evidence-status, anti-overclaim). |
| `refine-logs/FINAL_PROPOSAL_SHORT.md` **v4.0** | Current 1-2pp ADSR short. |
| `refine-logs/METHOD_SPEC.md` **v4.0** | Current ADSR implementation contract (§§13-16; M-PRM/ETV-pruning = superseded boundary). |
| `refine-logs/EXPERIMENT_PLAN.md` **v4.0** | Current experiment-plan index (E1-E9). |
| `refine-logs/EXPERIMENT_PLAN_EXEC.md` **v4.0** | Current executable plan (E1-E9, Phases 1-7). |
| `orbit-research/ASSUMPTION_LEDGER.md` | Assumption/hypothesis ledger ("2026-06-04 ADSR Pivot Addendum": H1-H6 + C1-C6). |
| `orbit-research/HEADROOM_GATE_PREREG.md` | Locked Phase A gate and claim-decision matrix (foundation). |
| `orbit-research/NULL_RESULT_CONTRACT.md` | Positive/null/tie routing ("2026-06-04 ADSR Pivot Addendum"). |
| `orbit-research/COMPONENT_BUNDLE_LADDER.md` | Component bundling/ablation ("2026-06-04 ADSR Pivot Addendum"). |
| `orbit-research/CONTROL_DESIGN.md` | Required controls ("2026-06-04 ADSR Pivot Addendum"). |
| `orbit-research/ALGORITHMIC_FORMALIZATION.md` | Method formalization ("2026-06-04 ADSR Pivot Addendum"; quality verifier = no MLP). |
| `orbit-research/TWEEDIE_DERIVATION_NOTE.md` | Tweedie formula status and caveats (foundation infra). |

## 7. Runtime Configs And Frozen Gates

| File | Role |
|---|---|
| `configs/eval/gate_v1.yaml` | Frozen Phase A / R050 historical gate. Do not edit. |
| `configs/eval/gate_v2.yaml.draft` | Draft gate policy. Do not rename to live gate. |
| `configs/prompts/dev.jsonl` | 256 dev prompts. |
| `configs/prompts/held_out.jsonl` | 256 held-out prompts. |
| `orbit-research/GATE_V1_SHA_BACKFILL_2026-05-21.md` | Historical gate v1 provenance. |
| `orbit-research/GATE_V2_FREEZE_2026-05-23.md` | Gate/config/script freeze record. |
| `orbit-research/RUN_LEDGER.jsonl` | Append-only run provenance. |
| `MANIFEST.md` | Historical per-change manifest. |

## 8. Preserved Raw Evidence

These stay in place and are not cleaned by prose hygiene passes:

- `runs/**`
- `_pi_review_pkg/**`
- `papers/diagnostic/**`
- `pi_review_2026-05-21*.tar.gz`
- `pi_listening_packet_2026-05-22.tar.gz`
- gate decision backups and calibration/parity JSON files under `orbit-research/`

## 9. Archive Map

| Archive | Contents |
|---|---|
| `orbit-research/archive/2026-05-doc-hygiene-post-c1/` | C1 intermediate reports, old H3 prompt/audit docs, Early-Tweedie prep/smoke docs, trajectory-aware drafts, superseded derived-analysis directories, AND (followup pass 2026-05-28) the 21 orphan `.json` / `.csv` data files whose `.md` siblings were archived in the first pass. |
| `papers/explainers/archive/2026-05-method-review/` | Dated method-review, red-team, literature, PI-brief, and audit-round prose. |
| `refine-logs/archive/2026-05-revision/` | Dated revision briefs/intake/report/critic files. |
| `orbit-research/archive/2026-05-superseded-state/` | Completed skill state files and content-loss stubs. |
| `orbit-research/archive/PARATERA_MIGRATION_AUDIT_2026-05-19.md` | Historical Paratera migration audit. |

## 10. Boundaries For Future Cleanup

- Do not delete or rewrite raw evidence.
- Do not edit frozen gate configs in place.
- Prefer archive moves over hard deletion for research prose.
- If a dated document is moved, keep an archive README or canonical index entry
  with current replacement.
- Do not use archived intermediate files as default state unless explicitly
  auditing history.
