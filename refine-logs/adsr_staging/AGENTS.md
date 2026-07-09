# Project: Axis-Deferred Speculative Restart for Flow-Matching Music Generation

Music-generation research project using ACE-Step v1.5. Stable Audio Open is a
high-priority, Phase-1-parallel cross-backbone target (graceful fallback; does
not gate submission). Working title is **When to Continue: Axis-Deferred
Speculative Restart (ADSR) for Flow-Matching Music Generation**.

Framing history: *When and Where to Reward* / *Headroom-Gated M-PRM* (M-PRM) →
**Early Trajectory Verifiers (ETV)** (2026-05-28) → **Axis-Deferred Speculative
Restart (ADSR)** (frozen 2026-05-29 per PI-authored
`ADSR_Research_Plan_FINAL_EN_2026-05-29.md`; canonical reframe 2026-06-04).

**This file (v4.0 ADSR reframe, 2026-06-04).** ADSR is compute *reallocation*
via RESTART / DEFER / CONTINUE — terminate low-promise trajectories early and
launch new independent seeds — **not** prune-and-select from a fixed candidate
pool. ETV-pruning (Track A raw Early-Tweedie Pruning) is now a **baseline**, not
the headline. M-PRM / section-level credit is **boundary** evidence only.

## Current Snapshot

```yaml
stage: adsr_pivot_stop_a_ready_for_pi_approval
proposal_status: ADSR_PIVOT_STOP_A_READY_FOR_PI_APPROVAL
frozen_plan: ADSR_Research_Plan_FINAL_EN_2026-05-29.md   # PI frozen FINAL (English)
final_proposal: refine-logs/FINAL_PROPOSAL.md            # v4.0 (ADSR-centric)
final_proposal_short: refine-logs/FINAL_PROPOSAL_SHORT.md # v4.0 (ADSR short)
method_spec: refine-logs/METHOD_SPEC.md                  # ADSR implementation contract
experiment_plan: refine-logs/EXPERIMENT_PLAN_EXEC.md     # v4.0 (nine experiments E1–E9)
experiment_plan_index: refine-logs/EXPERIMENT_PLAN.md    # v4.0
revision_intake: refine-logs/REVISION_INTAKE.md          # Round 1 (ETV-era, preserved)
revision_report: refine-logs/REVISION_REPORT.md          # Round 1 (ETV-era, preserved)
current_synthesis: orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md
progress_report: PROGRESS_REPORT_2026-05-28.md
canonical_index: orbit-research/CURRENT_CANONICAL_FILES.md
run_ledger: orbit-research/RUN_LEDGER.jsonl
etv_archive: orbit-research/archive/etv_pre_adsr_20260604/
last_updated: "2026-06-04"
```

## Current Research State

ADSR is a **plan-stage proposal for a new method**. The foundation evidence
below already exists (repurposed from the ETV / Track-A / H2 / human-listening
record); the ADSR-specific components are forward-looking and **not yet run**.
Do not present planned results as obtained.

### Foundation evidence (already exists — repurposed as ADSR anchor)

- **H1 / Phase A — early trajectory quality persistence.** ACE-Step has
  inference-time headroom (`delta_sigma_bon_vs_base = 0.7549`; CFG / S7 controls
  negative). High/low trajectories separate early.
- **H2 / Phase B.1 — axis-dependent observability.** Intermediate Tweedie
  estimates at non-trivial σ carry predictive signal. Verdict:
  `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES` (128 prompts; 7/7 reward axes with at
  least one primary-σ survival — `lyric_intelligibility` scoped to its EN-vocal
  subset, n=282; see
  `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md`).
- **Track A — raw Early-Tweedie Pruning (now the ADSR "raw ETP" baseline).**
  Schedule A recovers `0.9864` reward_fraction at `0.500` compute (regenerated
  2026-06-04 on the lyric-fix dataset; was `0.9858` on 2026-05-28, within noise);
  bottom-prune σ=0.7 false-negative `0.0195`. Selection over a fixed pool is
  **low-stakes** (ETP@50 over BoN-4 ≈ `+0.0036`; median regret ≈ 0) — this is the
  H3 motivation for restart-based *reallocation* rather than selection.
- **Lyric axis (EN-vocal only).** `lyric_intelligibility` ETP@50 = `0.682`,
  n=282 (248/282 = 88% carry signal); instrumental `1.0` sentinel masked,
  non-English excluded — measured **cross-prompt, not cross-content**, and
  reported **per specificity stratum**. Foundation for C5 (lyric as a
  first-class late-observable axis on the lyric-bearing vocal subset only).
- **Track B — global / time-uniform quality structure.** Median globalness index
  `0.861`, sign consistency `1.000`, crossing frequency `0.000`. Short-form
  ACE-Step quality differences are persistent across the clip rather than
  isolated local-window failures. Mechanism support for early decidability.
- **C6 / C1 RL boundary.** All four LoRA/GRPO first-wave methods (R8a, R8b,
  M-FixedWin, M-Section) completed cleanly; common dev eval
  `COMMON_DEV_NO_CLEAR_WIN` (deltas +0.012 to +0.014 LCB). Technically feasible
  but no clear first-wave common-metric gain — motivates the shift to
  inference-time compute allocation.

### NOT yet run (ADSR is forward-looking for these — do NOT claim results)

- **E3 — EVPD is NOT trained.** The Early Vocal-Presence Detector (a learned
  AUDIO model predicting final vocal presence from the early Tweedie-clean
  mel-spectrogram) has not been built.
- **E6 — restart / ADSR NOT run.** Only offline-simulatable on the existing
  4096-candidate pool ("restart" = draw the next independent pool candidate); the
  real-generation confirm has not been launched.
- **Vocal-presence labels not yet derived** (Demucs/Spleeter vocal-energy ratio
  or SVD model; Whisper `no_speech_prob` only as a coarse pre-filter). The
  existing 4096 candidates are not yet relabeled.
- **H2b presence-vs-content split unmeasured**; cross-backbone (Stable Audio
  Open) replication not started.

### Boundary evidence (cited as a single paragraph, not active)

- **H3 / Phase B.3.** Section is not the best default credit unit for ACE-Step
  30-40s generations. Motivation / boundary nuance only.
- **Track C.** Bounded RL rescue explicitly stopped before GPU launch.

**Current paper direction: Axis-Deferred Speculative Restart (ADSR) for
Flow-Matching Music Generation.** Core question: *when can we decide whether a
music-generation trajectory is worth continuing, and which quality axes must be
deferred until later in the flow trajectory?* Method stack:

1. **Raw Early-Tweedie Pruning (raw ETP) — baseline** (the former ETV headline;
   selection over a fixed pool, known to be low-stakes).
2. **Learned quality verifier (lightweight)** — scalar early features (axis
   scores, within-prompt rank, slope, risk, metadata); ridge / GBDT /
   LambdaMART pairwise; near-saturated (ridge within-prompt NDCG ~0.995),
   capacity is not the bottleneck.
3. **Early Vocal-Presence Detector (EVPD) — learned AUDIO model (NEW main
   ingredient)** — small CNN / fine-tuned pretrained audio encoder predicting
   FINAL vocal presence from the EARLY Tweedie-clean mel-spectrogram; warrants a
   real neural net because early-σ audio perception under heavy noise is a
   genuine learning problem and OOD for off-the-shelf detectors. Prompt-type
   match = compare EVPD prediction to the requested type.
4. **ADSR (main method)** — RESTART (terminate trajectory, launch NEW
   independent seed — not a rollback/repair) / DEFER (continue to later σ before
   deciding) / CONTINUE. Decision priority: (1) EVPD predicts final-type ≠
   requested-type with high confidence → restart (gross type error); (2) early
   quality clearly low and late-axis risk low → restart; (3) semantic/lyric
   content risk high/uncertain → defer; (4) else continue. Matched expected
   total NFE with no optimistic accounting; offline-first validation on the 4096
   pool, then a small real-generation confirm.

Six paper-bearing claims (**C1–C6**) over six hypotheses (**H1–H6**, incl.
**H2b** presence-vs-content split and **H5** type errors high-stakes &
early-catchable); see `orbit-research/ASSUMPTION_LEDGER.md` "2026-06-04 ADSR
Pivot Addendum". Nine experiments **E1–E9** (E1 axis×σ matrix, E2 human
early→final validation, E3 EVPD + type-error study, E4 raw pruning / same-compute
baselines, E5 learned quality verifier, E6 ADSR main method, E7 lyric-focused
deferred eval, E8 human spot-check, E9 robustness + cross-backbone). RL
post-training is **boundary evidence** (C6) per `ADSR_Research_Plan §10` unless
the PI approves a new bounded triage.

## Active Next Step

No experiment is authorized by this file.

PI-facing next step is **STOP-A sign-off** on the ADSR pivot. PI must inspect and
approve:

- `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` (the PI's frozen FINAL plan — the
  anchor all reframed canonical files must match).
- `refine-logs/FINAL_PROPOSAL.md` v4.0 (ADSR-centric proposal; C1–C6, ADSR
  method, E1–E9 with run-vs-planned status, anti-overclaim §14, evidence-status
  honesty).
- `refine-logs/FINAL_PROPOSAL_SHORT.md` v4.0 (1–2 page ADSR short).
- `refine-logs/METHOD_SPEC.md` (ADSR implementation contract: restart/defer/
  continue logic, EVPD, quality verifier, decision thresholds, compute
  accounting §4.5, offline-first protocol, vocal-presence label derivation;
  M-PRM / ETV-pruning sections marked superseded boundary).
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` v4.0 (E1–E9 with go/no-go gates;
  Phases 1–7; offline-first ADSR simulation; EVPD training; cross-backbone
  parallel).
- `refine-logs/EXPERIMENT_PLAN.md` v4.0 (index; active run order = E1–E9).
- `orbit-research/CONTROL_DESIGN.md` (ADSR baselines/controls: type-match
  restart, random restart, raw restart, axis-deferred; EVPD vs off-the-shelf
  detector; two-factor ablation axis-awareness × restart-reallocation).
- `orbit-research/ASSUMPTION_LEDGER.md` (H1–H6 + C1–C6 paper-bearing rows;
  "2026-06-04 ADSR Pivot Addendum").
- `orbit-research/PROPOSAL_REVISE_STATE.json` (state machine —
  `awaiting_human_continue`).

If satisfied, next downstream skill is
`/experiment-bridge "refine-logs/EXPERIMENT_PLAN.md"` (begins STOP B,
PLAN_CODE_AUDIT for the ADSR implementation).

For empirical context, see:

- `PROGRESS_REPORT_2026-05-28.md` (full project snapshot; ETV-era, foundation
  evidence still valid).
- `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md` (synthesis).
- `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` (Track A / raw-ETP
  baseline canonical).
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` (Track B mechanism).
- `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` (lyric
  EN-vocal n=282, 0.682; sentinel-pollution fix).
- `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` (C6 RL boundary).

## Hard Boundaries

Do not launch without explicit PI approval:

- Phase D
- human evaluation (incl. E2 / E8 listening sessions)
- pruning+RL
- additional full 1000-step RL training
- BeatWin/LyricSpan PRM expansion
- EVPD training runs or ADSR real-generation runs (offline simulation only until
  STOP B)
- canonical proposal rewrite beyond this approved ADSR reframe

Do not modify:

- `configs/eval/gate_v1.yaml`
- raw run outputs under `runs/**`
- PI review packages under `_pi_review_pkg/**`
- listening packets or tarballs
- calibration/parity/gate evidence files
- the canonical reward set `orbit-research/trajectory_candidate_dataset.jsonl`
- archived ETV-era files under `orbit-research/archive/etv_pre_adsr_20260604/`

`configs/eval/gate_v2.yaml.draft` remains a draft. Do not activate it by
renaming.

## Environment

```bash
module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
```

## Key Artifact Index

| Layer | Path |
|---|---|
| PI frozen FINAL plan (ADSR anchor) | `ADSR_Research_Plan_FINAL_EN_2026-05-29.md` |
| Reframe brief (single source of truth) | `refine-logs/ADSR_REFRAME_BRIEF.md` |
| Canonical reading path | `orbit-research/CURRENT_CANONICAL_FILES.md` |
| Progress report | `PROGRESS_REPORT_2026-05-28.md` |
| Current synthesis | `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md` |
| Trajectory-aware PI report | `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` |
| Active proposal v4.0 (ADSR) | `refine-logs/FINAL_PROPOSAL.md` |
| Active short proposal v4.0 (ADSR) | `refine-logs/FINAL_PROPOSAL_SHORT.md` |
| Active method spec (ADSR contract; M-PRM/ETV-pruning marked boundary) | `refine-logs/METHOD_SPEC.md` |
| Active exec plan v4.0 (E1–E9) | `refine-logs/EXPERIMENT_PLAN_EXEC.md` |
| Active plan index v4.0 | `refine-logs/EXPERIMENT_PLAN.md` |
| Revision intake (Round 1, ETV-era preserved) | `refine-logs/REVISION_INTAKE.md` |
| Revision report (Round 1, ETV-era preserved) | `refine-logs/REVISION_REPORT.md` |
| Revision state | `orbit-research/PROPOSAL_REVISE_STATE.json` |
| Raw Early-Tweedie Pruning (Track A → ADSR "raw ETP" baseline) | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` |
| Early-Tweedie PI decision | `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` |
| Global quality analysis (Track B, mechanism) | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| Lyric-fix report (EN-vocal n=282, 0.682; C5 foundation) | `orbit-research/prompt_set_audit_20260529/LYRIC_FIX_REPORT_20260603.md` |
| C6 / C1 common eval (RL boundary) | `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` |
| C1 dynamics audit (boundary) | `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md` |
| RL rescue stop (boundary) | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` |
| Canonical reward set | `orbit-research/trajectory_candidate_dataset.jsonl` |
| Gate policy (draft, do not activate) | `configs/eval/gate_v2.yaml.draft` |
| v1.3 contracts with ADSR addendums | `orbit-research/{ASSUMPTION_LEDGER,CONTROL_DESIGN,COMPONENT_BUNDLE_LADDER,ALGORITHMIC_FORMALIZATION,DIAGNOSTIC_EXPERIMENT_PLAN,NULL_RESULT_CONTRACT}.md` "2026-06-04 ADSR Pivot Addendum" |
| ETV-era pre-ADSR archive | `orbit-research/archive/etv_pre_adsr_20260604/` |
| Pre-revise snapshot | `orbit-research/archive/2026-05-28-proposal-revise-round-1/` |
| Run ledger | `orbit-research/RUN_LEDGER.jsonl` |

## Doc Hygiene Notes

Historical method-review, revision, PI-decision prose, and C1 intermediate
reports are preserved under archive directories. ETV-era canonical files (the
pre-ADSR versions of this stack) are preserved at:

`orbit-research/archive/etv_pre_adsr_20260604/`

Earlier cleanup archive:

`orbit-research/archive/2026-05-doc-hygiene-post-c1/`

Raw evidence remains in place:

- `runs/**`
- `_pi_review_pkg/**`
- `papers/diagnostic/**`
- `pi_review_2026-05-21*.tar.gz`
- `pi_listening_packet_2026-05-22.tar.gz`
- gate/calibration/parity JSON files under `orbit-research/`

<!-- ORBIT:BEGIN -->
## ORBIT Skill Scope
ORBIT skills installed in this project: 73 entries.
Manifest: `.aris/installed-skills.txt`.
For ORBIT workflows, prefer project-local skills under `.claude/skills/` over global skills.
Do not modify or delete files under the ORBIT skill target.
<!-- ORBIT:END -->

## Claude Code CLI Review

Use this non-interactive protocol from Codex:

```bash
claude -p \
  --dangerously-skip-permissions \
  --output-format json \
  --model opus \
  --effort max \
  "your prompt"
```

Use `-p` for non-interactive output and `--output-format json` for scriptable
results. For parallel review, launch multiple shell commands with narrower
prompts by module or task, then merge the JSON findings.

## Revision History

- **v3.0 ETV pivot (2026-05-28):** snapshot reframed to Early Trajectory
  Verifiers (ETV) per PI-authored `revise.md` and `/proposal-revise both`
  Round 1; three-tier ETV method stack; ETV1–ETV5 claims.
- **v4.0 ADSR reframe (2026-06-04):** ETV→ADSR pivot per
  `ADSR_Research_Plan_FINAL_EN_2026-05-29.md`. Snapshot, method stack, claims,
  and hypotheses reframed to Axis-Deferred Speculative Restart (compute
  reallocation via restart/defer/continue, not prune/select). ETV raw-ETP
  pruning demoted to baseline; M-PRM/section credit to boundary. Added EVPD
  (learned audio model), H2b presence-vs-content split, H5 type-error axis,
  C1–C6 / H1–H6, E1–E9. Foundation evidence preserved (H1/H2 persistence,
  Track A 0.9864@0.500, lyric 0.682 EN-vocal n=282, RL boundary); ADSR-specific
  components (EVPD training, restart/ADSR runs, vocal-presence labels) flagged
  NOT yet run. ETV-era files archived at
  `orbit-research/archive/etv_pre_adsr_20260604/`.
