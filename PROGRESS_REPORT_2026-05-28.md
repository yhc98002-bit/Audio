# Progress Report — When and Where to Reward
## ICLR 2026 Target — Phase A → B → C Closeout

| Field | Value |
|---|---|
| Date | 2026-05-28 |
| Project | When and Where to Reward: Music-Structured Process Rewards for Flow-Matching Song Generation |
| Backbone | ACE-Step v1.5 (Stable Audio Open kept audit-only) |
| Compute budget | 5,400 GPU-h total over 148 days |
| Compute consumed | ~540 GPU-h (~10% of budget) |
| Document status | Internal PI progress report; supersedes the two synthesis memos for decision purposes; does NOT rewrite the canonical proposal |
| Canonical proposal | `refine-logs/FINAL_PROPOSAL.md` (v2.2, 2026-05-24, untouched) |
| Author / PI | yhc (`Despaireye`) |

---

## 1. Executive Summary

The experimental program has now closed Phases A, B.1, B.3, C0, C1 and the three
follow-on tracks (A, B, C). The empirical picture has moved decisively away from the
original M-PRM-centric framing toward a trajectory-aware inference-time selection story.

Five-bullet snapshot:

1. **ACE-Step has real inference-time headroom (H1).** Phase A held-out gate passed
   with `delta_sigma_bon_vs_base = 0.7549`; CFG and S7-sampler controls do not explain
   the gain.
2. **Intermediate Tweedie estimates carry predictive reward signal in non-trivial σ
   regions (H2).** 128-prompt canonical verdict
   `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES`; 7 of 7 reward axes have at least one
   primary-σ survival; result is robust under sample-size doubling.
3. **Section is NOT the best general credit unit for ACE-Step 30–40 s short-form
   generation (H3).** Corrected held-out v2 returns FAIL on both vocal and
   instrumental strata; consensus ranking is `CU-BW > CU-MS > CU-FW > CU-NULL > CU-TS`;
   FixedWin is the conservative coverage-aware single pick.
4. **First-wave M-PRM RL training is an engineering success but a scientific
   no-clear-win.** All four methods (R8a outcome-plain, R8b outcome-guarded,
   M-FixedWin, M-Section) completed 1000 GRPO steps cleanly, but the shared
   64-prompt common dev eval shows deltas of +0.012 to +0.014 LCB over base, all
   within noise of one another.
5. **Early-Tweedie pruning (Track A) is the strongest current positive
   result.** Schedule A (σ=0.9 top-4 → σ=0.7 top-2 → final top-1) recovers
   `reward_fraction = 0.9858` at `compute_fraction = 0.500`, with bottom-prune
   false-negative `0.0195` at σ=0.7. Decision status:
   `STRONG_CANDIDATE_MAIN_APPLICATION`.

**Pivot statement.** The originally proposed M-PRM credit-assignment program has not
delivered the headline RL gain. In parallel, three new lines of empirical evidence (H2
emergence, Track A pruning, Track B global-quality structure) cohere into a different,
stronger paper direction: trajectory-aware inference-time selection grounded in early
quality emergence, with the credit-unit / RL results positioned as boundary-setting
negative evidence rather than the main contribution.

---

## 2. Compute Budget Accounting

| Phase / Track | GPU-h consumed | Source |
|---|---:|---|
| Phase A (6-rung sweep + R050 probe + M1A) | ~170 | `runs/m1a_phase/`, `runs/r050/`, `runs/r0_base..r9/` |
| Phase B.1 H2 formal (64 prompts × 6 σ) | 0.32 | `runs/phase_b1_reliability/` |
| Phase B.1 H2 expansion (64 prompts × 6 σ) | 0.43 | `runs/phase_b1_reliability_expansion/` |
| Phase B.1 H2 smoke | 0.02 | `runs/phase_b1_reliability_smoke/` |
| Phase B.3 H3 smoke (4 prompts × 2 σ × 6 CU) | 0.02 | `runs/h3_smoke/` |
| Phase B.3 H3 dev (64 prompts × 6 CU) | ~1.0 | `runs/phase_b3_credit_unit/h3a/` |
| Phase B.3 H3 held-out v2 (256 prompts × 6 CU, 8-GPU) | ~4.0 | `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/` |
| Phase B.3 Sectionability v2 | 0 (CPU) | `…/sectionability_v2/` |
| Phase C0 backend smokes (R8a/R8b/M-FW/M-Sec) | <2 | `runs/ace_lora_grpo_backend_smoke/`, `runs/phase_c0_backend_validation_*` |
| Phase C1 four-method first-wave RL (1000 steps each) | 119.75 | `runs/phase_c1_firstwave_20260524_researcher_go_01/` |
| Phase C1 common dev eval (64 prompts × 5 targets) | ~3 | `runs/phase_c1_common_downstream_eval_20260526_helper01/` |
| Phase C1 checkpoint triage eval | ~2 | `runs/phase_c1_checkpoint_triage_eval_20260526/` |
| Track A Early-Tweedie BoN-8 validation (512 prompts, 4096 candidates) | 243.10 | `runs/early_tweedie_validation_512_bon8_20260527_full01/`; refresh-side estimate 265.91 GPU-h |
| Track B Global-Quality structure analysis | 0 (CPU) | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| Track C Bounded RL rescue | 0 (stopped) | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` |
| **Total consumed** | **~540** | |
| **Remaining** | **~4,860 (≈90% of budget)** | |

Source for consumed figures: `orbit-research/RUN_LEDGER.jsonl` (135 events) plus the
phase-level audit memos. The Phase A `~170` GPU-h figure is an upper-bound estimate that
includes the M1A oversubscribed gate run and the six paired-test sweep; ledger-side
totalling reports a smaller subset because early R050 entries pre-date the formal ledger
schema. The Track A figure (243.10) is from
`orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md`; the refresh estimate of 265.91
GPU-h reported in `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` includes
shard-side scheduling overhead. Either way, the project is at ~10% of total budget with
all primary scientific phases empirically closed.

---

## 3. Phase A — Inference-Time Headroom (H1) — PASSED

Phase A asked whether sampling-time strategies (best-of-N, CFG sweep) can move ACE-Step
final quality measurably beyond the base sampler, after ruling out trivial sampler
explanations.

### 3.1 Headroom gate verdict

From `orbit-research/HEADROOM_GATE_DECISION.json`:

| Field | Value |
|---|---|
| `pass_gate` | true |
| `delta_sigma_bon_vs_base` | 0.7549 |
| `cfg_explains_gain` | false |
| `s7_explains_gain` | false |
| `human_spot_check_confirms` | true |
| Gate policy | `gate_v1` v1.1 |
| Split | held_out |

### 3.2 Per-rung bootstrap means (n=768 each, 1000 bootstrap iterations)

| Rung | Mean `gate_r_lcb` | 95 % CI |
|---|---:|---|
| `r0_base` (baseline) | 2.0737 | [2.0523, 2.0948] |
| `r9_s7_sampler_control` | 2.0571 | [2.0358, 2.0781] |
| `r1_cfg_sweep` | 2.1312 | [2.1109, 2.1496] |
| `r2_bon` (BoN-8) | 2.2864 | [2.2734, 2.2989] |
| `r4_bon_cfg` (BoN+CFG) | 2.2962 | [2.2838, 2.3079] |

Paired-by-prompt tests (n_common=256, BH q≈0):

- `r2_bon − r0_base` = **+0.2127** (BoN-8 ceiling vs baseline)
- `r4_bon_cfg − r0_base` = **+0.2225** (composite vs baseline)
- `r1_cfg_sweep − r9_s7_sampler_control` = **+0.0741** (CFG signal is real, not a
  sampler artifact)

The R050 mini-headroom probe (pre-gate) reported median improvement +0.0413 with 21/32
positive cases.

### 3.3 Interpretation

Inference-time methods on ACE-Step move measurable quality above base, are not
explained by CFG or sampler-stride changes, and survive human spot-check. This is the
foundation that justifies asking *when* quality emerges along the trajectory (Phase B.1
H2) and *whether* selection can be made cheaper than full BoN (Track A).

---

## 4. Phase B.1 — When to Reward (H2) — STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES

Phase B.1 asked whether intermediate Tweedie estimates of the final audio at
non-trivial σ are predictive of final reward, axis-by-axis.

### 4.1 Final 128-prompt tier (merged formal 64 + expansion 64)

From `runs/phase_b1_reliability/H2_VERDICT.json` and
`orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md`:

| Field | 64-prompt (canonical) | 128-prompt (merged) |
|---|---:|---:|
| Tier | STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES | STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES |
| `n_primary_full` | 17 | 20 |
| `n_primary_strict` (excl. near-threshold) | 15 | 17 |
| `strong_holds_strict` | true | true |
| `classification_depends_on_near_threshold` | false | false |
| Axes with ≥1 primary survival | 6 / 7 | 7 / 7 |

The PI-revised tier rule (2026-05-23) treats `STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES` as
the correct classification because the STRONG criteria hold even after excluding the 3
near-threshold pairs ρ ∈ [0.50, 0.55].

### 4.2 Per-axis × σ correlations (128-prompt, Spearman ρ)

| Reward axis | σ=0.9 | σ=0.8 | σ=0.7 | σ=0.6 | Primary survivors |
|---|---:|---:|---:|---:|---|
| `aesthetic_cu` (Audiobox Content Usefulness) | **0.641** | **0.724** | **0.752** | **0.882** | 4 / 4 (strongest axis) |
| `aesthetic_pq` (Audiobox Production Quality) | 0.500† | 0.658 | 0.696 | 0.854 | 3 + 1 near-threshold |
| `aesthetic_ce` (Audiobox Content Enjoyment) | — | 0.549† | 0.673 | 0.853 | 2 + 1 near-threshold |
| `aesthetic_pc` (Audiobox Production Complexity) | — | — | — | 0.657 | 1 |
| `section_coherence` (MERT) | — | 0.639 | 0.761 | 0.818 | 3 |
| `semantic_fit` (CLAP) | — | — | — | 0.659 | 1 |
| `lyric_intelligibility` (Whisper-WER, vocal-only) | 0.514† | 0.646 | 0.753 | 0.788 | 3 + 1 near-threshold |

† = pair in the [0.50, 0.55] near-threshold band (not load-bearing).

Late-reference σ ∈ {0.5, 0.3} show ρ ∈ [0.68, 0.98] across all seven axes — these are
saturation-regime measurements and are NOT counted as primary H2 evidence.

### 4.3 Quality-stratified emergence (exploratory, must_not_influence_gate)

Top-Q4 vs bot-Q1 median `aesthetic_pq` on Tweedie-reconstructed audio:

| σ | Top-Q4 | Bot-Q1 | Gap |
|---:|---:|---:|---:|
| 0.9 | 6.068 | 5.420 | **+0.65** |
| 0.8 | 6.692 | 5.497 | +1.20 |
| 0.7 | 7.092 | 5.490 | +1.60 |
| 0.6 | 7.339 | 5.491 | +1.85 |
| 0.5 | 7.949 | 5.780 | +2.17 (late-ref) |
| 0.3 | 8.031 | 6.100 | +1.93 (late-ref) |

High-final-quality trajectories become musically interpretable earlier (higher σ, more
noise) than low-final-quality ones. The gap grows monotonically across σ. This is the
exploratory mechanism that motivates Early-Tweedie pruning (Track A).

### 4.4 Cost

Combined Phase B.1 cost: **0.75 GPU-h** (0.32 formal + 0.43 expansion), well under the
6 GPU-h plan and the 15 GPU-h hard cap.

### 4.5 Standing relative to the original proposal

H2 was the "When to Reward" hypothesis in the v2.0 / v2.2 proposal and remains
supported. This is the only hypothesis from the original proposal that the experimental
program has confirmed as headline-grade. Limitations documented honestly (per
`PHASE_B1_H2_CONCLUSION_2026-05-23.md` §6): four of the seven axes belong to one
Audiobox model family; section_coherence has small dynamic range; lyric_intelligibility
is vocal-only; 128 prompts remains moderate near ρ=0.5.

---

## 5. Phase B.3 — Where to Reward (H3) — SECTION FAILED

Phase B.3 asked whether musical sections (CU-MS) are the best credit unit for
process reward, beating timestep (CU-TS), fixed-window (CU-FW), beat-window (CU-BW),
lyric-span (CU-LS), and a random-section null (CU-NULL).

### 5.1 Held-out v2 corrected verdict

From `orbit-research/H3_CREDIT_UNIT_INTERPRETATION_2026-05-23.md` §10
(`runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/H3_VERDICT.json`):

- Tier: **FAIL on both vocal and instrumental strata**
- Combined Kendall-τ across strata: **1.000**
- Consensus ranking: **`CU-BW > CU-MS > CU-FW > CU-NULL-rand-section > CU-TS`**

Per-stratum `section_minus_best_non_section` (corrected v2, after seed-aliasing fix):

| Stratum × axis | Margin | Coverage-aware best non-section |
|---|---:|---|
| vocal × musicality | **−0.042** | CU-BW (0.496) |
| vocal × coherence | **−0.274** | CU-LS (0.881, coverage-filtered) |
| vocal × prompt_fit | **−0.082** | CU-FW (0.592) |
| instr × musicality | **+0.020** | CU-BW (0.450) |
| instr × coherence | **−0.278** | undefined (no valid non-section under filter) |
| instr × prompt_fit | **+0.167** (single strict-pass cell) | CU-FW (0.497) |

The seed-aliasing fix moved 5 of 6 cells by ≥0.026 in magnitude; the largest shift was
`instr × prompt_fit` (+0.113 vs legacy), uncovering a real strict-pass for Section on
that single cell.

### 5.2 Sectionability v2

Replacing the v1 coherence-range proxy with a librosa Foote-novelty section detector
on the 256 corrected held-out clips:

- Mean detected sections per clip: **5.01**
- Median section duration: **8.0 s**
- Fraction of clips with 3+ sections: **99.6 %**
- Vocal vs instrumental mean: 5.09 vs 4.89 (essentially the same)
- No discriminative signal between high vs low CU-MS-ρ quartiles (means 4.78 vs 5.03)

The PI's pre-launch hypothesis ("ACE-Step 30–40 s outputs are short cues / sketches /
loops with no real section structure") is **not supported at face value** by this
detector. Two readings remain defensible: (a) the detector is over-segmenting on
transient timbral changes, or (b) ACE-Step short-form has many local contrast points
but no true song-level sections at the k=4 grid CU-MS imposes. We do not adjudicate.

### 5.3 Bearing on the original proposal

The original proposal's core "Where to Reward" claim — that musical sections are the
right credit unit for M-PRM — was empirically falsified on ACE-Step short-form. In the
canonical proposal (v2.2, 2026-05-23 framing freeze) the H3 verdict was recorded as
`SECTION_FAIL_WITH_INSTR_PROMPT_FIT_NUANCE` and the downstream method was pivoted to
**M-FixedWin-PRM** as conservative primary, with **M-Section-PRM** retained only as a
diagnostic / negative control. This is the first of three places where the experimental
record reverses the original proposal.

Held-out + dev are highly concordant (Kendall-τ = 1.000 across strata on held-out;
≈+0.87 vocal, +1.000 instr between dev and held-out). The verdict is reproducible.

### 5.4 Cost

H3 dev (64 prompts) + held-out v2 (256 prompts, 8-GPU sharded) + sectionability v2
(CPU): **~5 GPU-h**, well under the 30 GPU-h hard cap.

---

## 6. Phase C0 — Backend Validation — PASSED

Before the four-method RL first-wave, every backend invariant required for fair
comparison was checked.

From `orbit-research/ACE_STEP_LORA_GRPO_BACKEND_SMOKE_REPORT.md`:

- LoRA insertion works on the ACE-Step v1.5 backbone.
- Base parameters remain frozen across optimizer steps for all four methods.
- Adapter parameters update across optimizer steps for all four methods.
- Old-vs-new policy forward path is wired correctly.
- Ratio, log-ratio and loss are finite in smoke conditions.
- Checkpoint save and resume round-trip preserve adapter digest.

This validates the RL infrastructure as engineering-correct, so any later
weak scientific result cannot be attributed to silent adapter failure, base contamination,
NaN/Inf in the ratio path, or checkpoint corruption.

---

## 7. Phase C1 — Four-Method RL First-Wave — ENGINEERING PASS, SCIENTIFIC WEAK

Four methods, 1000 GRPO steps each, on the 64-prompt dev split, evaluated on the shared
common dev eval.

### 7.1 Training completion and cost

From `orbit-research/archive/2026-05-doc-hygiene-post-c1/root-md/PHASE_C1_LEARNING_SIGNAL_AUDIT_2026-05-26.md` (archived 2026-05-28 doc-hygiene pass):

| Method | Steps | GPU-h | Status | Adapter updated | Base unchanged | Checkpoint resume |
|---|---:|---:|---|---|---|---|
| R8a (outcome-GRPO plain) | 1000 | 37.7902 | PASS | true | true | true |
| R8b (outcome-GRPO guarded) | 1000 | 41.1546 | PASS | true | true | true |
| M-FixedWin-PRM | 1000 | 21.3986 | PASS | true | true | true |
| M-Section-PRM (diagnostic) | 1000 | 19.4068 | PASS | true | true | true |
| **Total active training** | **4000** | **119.7502** | | | | |

Initial adapter digest (shared): `c088a81534…d7bd`. All four methods produced distinct
post-training adapter digests, confirming they walked different optimization paths.

### 7.2 Training-health audit

- `nonzero_grad_tensors` mean 383.81 of 384 across all methods (gradients flowed).
- Zero-variance GRPO groups: 0 for all methods.
- Reward std mean: R8a 0.905, R8b 0.896, M-FixedWin 0.543, M-Section 0.556 (terminal
  methods carry larger reward outliers, as expected).
- Max abs KL_ref stayed far below the configured abort scale.
- Loss/KL/ratio/clip logs finite throughout; no NaN/Inf observed.
- `ratio.mean=1.0`, `ratio.std=0.0`, `clip_fraction=0.0` everywhere — but this is a
  known pre-update logging-point artifact in `AceLoraGrpoBackend.update`, not a
  silent-backend failure. Post-update logprob probes should be added in any future RL
  wave.

The verdict line is: `ENGINEERING_PASS_WITH_WEAK_OR_AMBIGUOUS_LEARNING_SIGNAL`.

### 7.3 Common dev eval (64-prompt shared eval, 5 targets)

From `runs/phase_c1_common_downstream_eval_20260526_helper01`:

| Target / Checkpoint | `robust_lcb_mean` | Δ vs Base |
|---|---:|---:|
| Base (no RL) | 2.1337 | 0.0000 |
| R8a step1000 | 2.1453 | **+0.0116** |
| R8b step1000 | 2.1482 | **+0.0145** |
| M-FixedWin step1000 | 2.1458 | **+0.0121** |
| M-Section step1000 | 2.1461 | **+0.0124** |

All four deltas are positive but small (~0.5–0.7 % relative), tightly clustered, and
within noise of each other. No method wins by any meaningful margin; no method clearly
beats the terminal-reward baselines. Checkpoint triage at earlier step counts did not
find a checkpoint that beats step1000 or Base.

The cached `fixedwin_process` / `section_process` columns from the training side
(`-1.677` vs `-1.585` for `m_fixedwin`; `-1.705` vs `-1.575` for `m_section`) plus the
1000-step training-trace correlation (Pearson 0.932, Spearman 0.904 between FixedWin
and Section process reward) indicate the two process variants are **co-linear** signals,
not distinct local-credit sources, at this training scale.

### 7.4 Bearing on the original proposal

The original proposal carried an implicit downstream claim that M-PRM process rewards
would improve RL quality by ≥2 % over terminal-reward baselines. **This is not what the
common dev eval shows.** All four methods cluster within +0.012 to +0.014 LCB of Base
at first-wave scale, with no method-vs-method separation. Combined with Track B (next
section), the most defensible reading is that ACE-Step's pretraining already optimizes
the global quality signal that local-window rewards proxy; first-wave M-PRM RL at this
scale therefore does not push beyond terminal-reward outcomes.

This is the second place where the experimental record reverses the original proposal.
It is also a result the paper can keep: a clean, honest negative finding on a clearly
specified setup is useful boundary evidence, especially when paired with Track A and
Track B (sections 8 and 9).

---

## 8. Track A — Early-Tweedie Pruning Validation — STRONG_CANDIDATE_MAIN_APPLICATION

The H2 emergence finding suggests intermediate Tweedie reconstructions can be used to
*rank* candidates early, before paying the full sampling cost. Track A operationalizes
this as an inference-time pruning study.

### 8.1 Run metadata

From `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` and
`orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md`:

| Field | Value |
|---|---|
| Run root | `runs/early_tweedie_validation_512_bon8_20260527_full01/` (8 shards) |
| Prompts | 512 (256 dev + 256 held-out) |
| Candidates per prompt (BoN) | 8 |
| Total candidates | 4096 |
| σ checkpoints scored | 0.9, 0.8, 0.7 |
| Primary metric | `common_robust_lcb` |
| Verifier status | `PASS_WITH_WARNINGS` (20 warnings, 0 errors) |
| PI decision status | `STRONG_CANDIDATE_MAIN_APPLICATION` |
| GPU-h (active) | 243.10 |

The 20 warnings are constant-metric rows on `lyric_intelligibility` (many instrumental
prompts have constant WER). These rows are treated as diagnostic only and not used as
primary evidence.

### 8.2 Schedule comparison (robust/common metric, n=512)

| Schedule | Compute fraction | Reward fraction | Winner-match | False-negative |
|---|---:|---:|---:|---:|
| Full BoN-8 (reference) | 1.000 | 1.0000 | 1.000 | 0.000 |
| **Schedule A** (σ0.9 top-4 → σ0.7 top-2 → final top-1) | **0.500** | **0.9858** | 0.576 | 0.424 |
| Schedule B (σ0.8 top-4 → σ0.7 top-2 → final top-1) | 0.583 | 0.9910 | 0.664 | 0.336 |
| Schedule C (σ0.8 keep-top-6 → final top-1) | 0.850 | 0.9986 | 0.939 | 0.061 |
| Bottom-prune σ0.8 (remove bottom-25 → final top-1) | 0.850 | 0.9986 | 0.939 | 0.061 |
| Bottom-prune σ0.7 (remove bottom-25 → final top-1) | 0.883 | 0.9996 | 0.980 | **0.020** |
| Random-prune (keep-4 → keep-2 → final, control) | 0.500 | 0.9570 | 0.254 | 0.746 |

### 8.3 Early winner-retention (per σ checkpoint)

| σ | Top-1 keep | Top-2 keep | Top-4 keep | Bottom-25 false-negative |
|---:|---:|---:|---:|---:|
| 0.9 | 0.2422 | 0.4531 | 0.6836 | 0.1406 |
| 0.8 | 0.3906 | 0.6113 | 0.8125 | 0.0605 |
| 0.7 | 0.4727 | 0.6816 | 0.8965 | **0.0195** |

### 8.4 Threshold readout

PI pre-specified threshold (in the H2-driven Track A plan):

- `reward_fraction ≥ 0.98` at `compute_fraction ≤ 0.5` under robust/common metric, AND
- bottom-prune false-negative ≤ 0.05.

Both conditions are satisfied:

- **Schedule A** hits `0.9858` reward at `0.500` compute — passes the aggressive
  half-compute regime.
- **Bottom-prune σ=0.7** holds false-negative at `0.0195`, well below 0.05.

Random-prune control at matched compute (0.500) recovers only `0.9570` reward — a
clearly separable gap. The pruning signal is non-trivial.

### 8.5 Interpretation

Tweedie estimates at early σ identify low-promise candidates with enough fidelity to
recover ~98.6 % of full BoN-8 quality at half the compute, and ~99.96 % at 88 %
compute with negligible bottom-prune false-negative. This is a real, quantitative
inference-time application of the H2 emergence finding. Decision status:
`STRONG_CANDIDATE_MAIN_APPLICATION` — but main-method status is not authorized without
PI sign-off, and pruning+RL combinations are explicitly not authorized.

---

## 9. Track B — Global Quality Structure — Mechanism Insight

Track B asks the parallel question: if M-PRM RL doesn't visibly improve common-eval
quality, but local-window reward proxies clearly correlate with final quality, what
*kind* of signal are those local windows carrying?

### 9.1 Headline globalness numbers

From `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md`, using cached H3 local proxy
vectors on the 256 held-out clips:

| Metric | Value |
|---|---:|
| H3 records analyzed | 256 |
| Usable primary cells | 4 (CU-FW/CU-BW × musicality/prompt_fit) |
| Median between-prompt variance share | 0.584 |
| Median between/within ratio | 1.404 |
| Median sign consistency (top-vs-bottom curves) | 1.000 |
| Median top-vs-bottom curve crossing frequency | 0.000 |
| Median **globalness index** | **0.861** |

Per-cell globalness:

| Unit | Axis | n | Between-share | Sign cons. | Crossing freq. | Globalness |
|---|---|---:|---:|---:|---:|---:|
| CU-BW | musicality | 256 | 0.475 | 1.000 | 0.000 | 0.825 |
| CU-BW | prompt_fit | 256 | 0.600 | 1.000 | 0.000 | 0.867 |
| CU-FW | musicality | 256 | 0.591 | 1.000 | 0.000 | 0.864 |
| CU-FW | prompt_fit | 256 | 0.577 | 1.000 | 0.000 | 0.859 |

Top-vs-bottom-quartile reward-time curves stay sign-consistent across all normalized
time bins for every primary cell. Top/bottom selection is in-sample; gap magnitudes are
descriptive rather than predictive.

### 9.2 Connection to C1

The C1 common eval cross-table shows that M-FixedWin and M-Section step1000
checkpoints, scored on the *other* method's process reward, give nearly identical
process scores (M-FixedWin checkpoint: `fixedwin_process=−1.677`,
`section_process=−1.585`; M-Section checkpoint: `−1.705`, `−1.575`). Combined with the
1000-step FixedWin/Section training-trace correlation (Pearson 0.932, Spearman 0.904),
the picture is consistent: FixedWin and Section process rewards are not separating two
genuinely different *local* credit signals; they are two slightly different averages of
the same persistent-global-quality signal.

### 9.3 Bearing on the original proposal

The original proposal framed M-PRM as a *local credit assignment* method that would
isolate locally improvable segments and route gradient there. Track B says: for
ACE-Step 30–40 s short-form generations, local-window rewards in practice behave as
stable proxies for global, persistent song-level quality, not as clean local-failure
detectors. This is the third reversal: even when the credit-unit is well-defined
(FixedWin), the *information content* it carries does not match the local-credit
framing that motivated the proposal. It also explains why C1 RL did not give a clear
common-eval win — there is little local-only signal for RL to chase that wasn't already
optimized by ACE-Step pretraining.

Limitations: the H3 proxy vectors are not human ratings; CU-LS is vocal-only;
coherence vectors have limited dynamic range; no source-separation experiment was run.
Track B is mechanism evidence, not human eval.

---

## 10. Track C — Bounded RL Rescue — STOPPED

From `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md`:

- Decision marker: `STOP_TRACK_C`
- GPU-h consumed: **0.0**
- Rationale: Track A is the strong scientific direction; Track B closes out the
  mechanism analysis; C1 first-wave already showed no clear common-metric win.
  Spending the bounded RL rescue budget here would not change the trajectory-aware
  story and would not produce a publishable RL win at first-wave scale.

Boundaries confirmed by the stop decision: no Track C GPU smoke, no full 1000-step RL
rescue, no pruning+RL, no reward / sigma / prompt / credit-unit redefinition, no
`gate_v1.yaml` change.

---

## 11. Synthesis — What the Evidence Now Says

### 11.1 Three strong findings

1. **H1**: ACE-Step has real inference-time headroom (`Δ = +0.7549` σ-LCB on
   BoN-8 vs base, CFG/sampler controls negative).
2. **H2**: Intermediate Tweedie estimates at non-trivial σ predict final reward;
   STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES across 7/7 reward axes; quality-stratified
   emergence already separates at σ=0.9 (+0.65 aesthetic_pq gap).
3. **Track A**: Early-Tweedie pruning operationalizes (1) and (2) into an inference-time
   selection method — Schedule A reaches 98.58 % of BoN-8 reward at 50 % compute, with
   bottom-prune σ=0.7 false-negative ≤ 2 %.

### 11.2 Three refuted or substantially revised

1. **H3 / Section credit unit**: Section is NOT the best general credit unit for
   ACE-Step short-form. Consensus held-out ranking `CU-BW > CU-MS > CU-FW > CU-NULL >
   CU-TS`; vocal section fails on all three axes; instrumental section has only a
   single strict-pass cell (prompt_fit +0.167). FixedWin retained as conservative
   default, Section demoted to diagnostic.
2. **C1 M-PRM RL win**: First-wave M-PRM training (M-FixedWin, M-Section) does not
   beat terminal-reward baselines on the common dev eval. All four methods cluster
   within +0.012 to +0.014 LCB of Base; no method-vs-method separation.
3. **Local credit assignment framing**: Track B globalness index 0.861 + the
   FixedWin/Section co-linearity (Pearson 0.932) suggest local-window rewards in this
   regime carry persistent global quality, not isolated local failures. The "local
   credit assignment" mechanism story the proposal relied on is not what the data
   shows.

### 11.3 Coherent mechanism

ACE-Step short-form (30–40 s) outputs differ from each other primarily by *persistent*
quality across the clip, not by isolated time-local defects. Pretraining already
optimizes that persistent quality, leaving little for local-window RL to recover
(explains C1 weak win). The same persistent-quality signal, however, becomes visible
in intermediate Tweedie reconstructions early in the trajectory (explains H2 +
quality-stratified emergence), which is exactly the signal Early-Tweedie pruning
exploits (explains Track A strong result).

The original proposal was internally consistent under the assumption that local credit
exists and is exploitable. The data says, in this regime, it largely doesn't. The same
empirical program that overturned the local-credit story produced the strongest
inference-time-selection story instead.

---

## 12. Recommended ICLR 2026 Paper Direction (pending PI sign-off)

The current paper landscape supports a clean trajectory-aware paper grounded in the
three strong findings, with the three refuted findings positioned as boundary evidence.
No paper-writing or canonical-proposal rewrite is authorized; this section is a
recommendation for PI decision only.

### 12.1 Title options

- **Option A (recommended)**: *When Does Quality Emerge? Trajectory-Aware Inference-Time
  Selection for Flow-Matching Music Generation.*
- **Option B (retain historical framing)**: *When and Where to Reward: Reward
  Emergence and Musical Credit Assignment in Flow-Matching Music Generation.*

Option A foregrounds the strongest result (Track A) and matches what the evidence now
supports. Option B keeps the original framing — defensible if we want to claim both
the "when" (H2) headline and the "where" (H3) negative result as two co-equal scientific
contributions; the second contribution then reads as "where-NOT" rather than
"where-IS".

### 12.2 Core contribution

- **C1 (main)**: Early-Tweedie inference-time selection. Two-stage pruning recovers
  98.58 % of full BoN-8 reward at 50 % compute; ≥ 99.86 % at 85 % compute with
  bottom-prune false-negative ≤ 6 %. Validated on 512 prompts × 8 candidates =
  4096 records, dev+held-out split, single common robust metric, with non-trivial gap
  against random-prune control (95.70 % at matched compute).
- **C2 (supporting)**: H2 emergence analysis. Intermediate Tweedie estimates predict
  final reward at σ ∈ {0.9, 0.8, 0.7, 0.6} on 7/7 reward axes (128 prompts). Provides
  the theoretical / empirical foundation for C1.
- **C3 (supporting)**: Global quality structure (Track B). Local-window rewards
  in ACE-Step short-form behave as global-quality proxies; globalness index 0.861.
  Explains why C1 inference-time selection succeeds and why local-credit RL doesn't.

### 12.3 Boundary-setting / negative-result contribution

- **N1**: Section is NOT the best credit unit on ACE-Step short-form. Held-out v2
  FAIL on both strata; consensus ranking and per-stratum margins reported honestly;
  Section's one strict-pass cell (instrumental prompt_fit +0.167) preserved.
- **N2**: First-wave M-PRM RL does not beat terminal-reward baselines at this scale.
  Engineering pass; learning-signal audit clean; common-eval delta within noise.

These are not failures to bury. They scope the paper's claims and make C1+C2+C3
defensible against the obvious "did you try the credit-assignment story" reviewer
question.

### 12.4 Story arc

H1 motivates inference-time methods → H2 shows quality emerges early in the trajectory
→ C1 (Track A) turns that into a compute-aware selection method → Track B explains why
the *same* signal does not separate as local RL credit → Honest negative results on H3
and C1 RL keep the scope tight.

### 12.5 Explicit non-claims for the paper

- No human preference improvement.
- No held-out paper-level generalization beyond the validated prompt split + metric.
- No claim that Early-Tweedie pruning + RL combination works (not attempted).
- No claim that Section never works (one instrumental strict-pass cell retained).
- No claim that FixedWin proves local temporal credit assignment.
- No claim that M-FixedWin is better than M-Section on downstream common metric.

---

## 13. Open Decisions Requiring PI Sign-Off

Listed without recommendation; each is a real fork that affects scope, compute, or
schedule.

1. **Paper title and framing**: Option A (trajectory-aware) vs Option B (when-and-where)
   vs other.
2. **Phase D launch (scale-up + held-out validation)**: defer / launch / partial. With
   ~4,860 GPU-h remaining, this is materially affordable.
3. **Human evaluation (Tier 1 — 128 unique pairs × 5 raters × 5 axes)**: defer / launch.
   Needed for any "paper claim of quality improvement" beyond automatic metrics.
4. **H3 full credit-unit comparison launch**: `configs/runs/phase_b3_credit_unit_comparison.yaml`
   still has `pi_approved_binding: false` and `pi_approved_launch: false`. The held-out
   v2 result already gives a strong section-FAIL verdict; a full launch may be
   redundant or may be desirable as Phase D appendix evidence.
5. **Pruning + RL combination**: explore / defer / drop. Track A is inference-only
   today; combining with RL is a real follow-on but not authorized by the current
   evidence.
6. **Additional full 1000-step RL training (incl. BeatWin / LyricSpan PRM expansion)**:
   defer / new wave with revised hyperparameters / drop. C1 first-wave + Track B
   suggest a redo would need a real change of method (or a different credit unit such
   as CU-BW / CU-LS), not just longer training on the same setup.
7. **Canonical proposal rewrite**: `refine-logs/FINAL_PROPOSAL.md` v2.2 is the current
   contract. Should it be revised to formally reflect the trajectory-aware pivot, or
   kept as historical and the paper writes its own framing?
8. **Stable Audio Open (SAO) transfer scope**: currently audit-only per
   `FINAL_PROPOSAL` §4. Promote to a transfer experiment for the paper, or stay
   audit-only?

---

## 14. Boundary Preservation Audit

As of 2026-05-28, the following invariants hold and have been verified against current
artifacts (see references for each line):

- `configs/eval/gate_v1.yaml` SHA256
  `43a306753583f03563c792ac9399bb1e30b0525c98c902a1e18756d54e25b3c6` (untouched since
  2026-05-16; matches the trajectory-aware completion audit and the H1 gate decision
  prereg.). Source: `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md`,
  `orbit-research/GATE_V2_FREEZE_2026-05-23.md`.
- `configs/eval/gate_v2.yaml.draft` remains `.draft`, not activated.
- No Phase D launched.
- No human evaluation launched.
- No pruning + RL combination launched.
- No additional 1000-step RL training launched.
- No BeatWin / LyricSpan PRM expansion launched.
- No Track C GPU smoke launched.
- No reward-definition changes.
- No σ-policy changes.
- No prompt-split changes.
- No credit-unit-definition changes.
- `refine-logs/FINAL_PROPOSAL.md` not rewritten by this report.
- `refine-logs/FINAL_PROPOSAL_SHORT.md`, `refine-logs/METHOD_SPEC.md`,
  `refine-logs/EXPERIMENT_PLAN_EXEC.md` not modified.
- All raw run outputs under `runs/**` left as written; PI listening packet
  `pi_listening_packet_2026-05-22.tar.gz` (~153 MB) preserved.
- PI review tarball `pi_review_2026-05-21.tar.gz` (~183 MB) preserved.

The non-claims list in `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md`
§"Current Non-Claims" is reproduced verbatim in §12.5 above (paper-level non-claims).

---

## 15. Appendix A — Run Inventory

Phase A:

| Run | Path | GPU-h | Verdict / Output |
|---|---|---:|---|
| M0.5 gate | `runs/M0_5_GATE_PASSED.flag` | — | passed |
| M1A oversubscribed | `runs/m1a_phase/` | ~150 | spot-check verdicts in `m1a_spot_check_verdicts_2026-05-21.json` |
| R050 mini-probe | `runs/r050/` | ~5 | +0.0413 median, 21/32 positive |
| 6-rung paired sweep | `runs/r0_base, r1_cfg_sweep, r2_bon, r3_robust_bon, r4_bon_cfg, r9_s7_sampler_control/` | ~15 | `orbit-research/HEADROOM_GATE_DECISION.json` pass_gate=true |

Phase B.1 / H2:

| Run | Path | GPU-h | Verdict |
|---|---|---:|---|
| Smoke | `runs/phase_b1_reliability_smoke/` | 0.02 | expected fail (n=1) |
| Formal 64 | `runs/phase_b1_reliability/` | 0.32 | STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES |
| Expansion 64 → 128 | `runs/phase_b1_reliability_expansion/` | 0.43 | STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES (tier identical) |

Phase B.3 / H3:

| Run | Path | GPU-h | Verdict |
|---|---|---:|---|
| Smoke | `runs/h3_smoke/` | 0.02 | segmentation counts verified |
| Dev 64 | `runs/phase_b3_credit_unit/h3a/` | ~1 | FAIL on both strata |
| Held-out v1 (legacy) | `runs/phase_b3_credit_unit/h3_held_out/` | ~4 | FAIL; superseded by v2 |
| Held-out v2 (global-seed) | `runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/` | ~4 | FAIL; consensus τ=1.000 |
| Sectionability v2 | `…/sectionability_v2/` | 0 (CPU) | mean 5.01 sections per clip |

Phase C0 / C1:

| Run | Path | GPU-h | Verdict |
|---|---|---:|---|
| LoRA/GRPO backend smoke | `runs/ace_lora_grpo_backend_smoke/` | <1 | PASS |
| Backend validation (2 GPU smokes × 4 methods) | `runs/phase_c0_backend_validation_*/`, `runs/phase_c1_two_gpu_*/` | <2 | PASS |
| C1 first-wave (4 methods × 1000 steps) | `runs/phase_c1_firstwave_20260524_researcher_go_01/` | 119.75 | ENGINEERING_PASS_WITH_WEAK_OR_AMBIGUOUS_LEARNING_SIGNAL |
| C1 common dev eval (5 targets × 64 prompts) | `runs/phase_c1_common_downstream_eval_20260526_helper01/` | ~3 | COMMON_DEV_NO_CLEAR_WIN |
| C1 checkpoint triage eval | `runs/phase_c1_checkpoint_triage_eval_20260526/` | ~2 | no better checkpoint than step1000 / Base |

Tracks A / B / C:

| Run | Path | GPU-h | Verdict |
|---|---|---:|---|
| Track A early-Tweedie validation 512 BoN-8 | `runs/early_tweedie_validation_512_bon8_20260527_full01/` (8 shards) | 243.10 | STRONG_CANDIDATE_MAIN_APPLICATION |
| Track A early-Tweedie smoke | `runs/early_tweedie_validation_smoke_20260527_0105/` | <1 | verifier prep |
| Track A early-Tweedie 128 BoN collections | `runs/early_tweedie_bon_collection_20260524_128*/`, `…_clean_128/` | ~5 | preparatory |
| Track B global-quality structure | (analysis only, CPU) | 0 | COMPLETE_CPU_ONLY |
| Track C bounded RL rescue | n/a (not launched) | 0 | STOP_TRACK_C |

---

## 16. Appendix B — File Index for PI Review

| Purpose | File |
|---|---|
| Current trajectory-aware synthesis | `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md` |
| Most recent PI report (refresh-tracked) | `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md` |
| H1 headroom gate verdict | `orbit-research/HEADROOM_GATE_DECISION.json`, `orbit-research/HEADROOM_GATE_PREREG.md` |
| H2 verdict (final 128-prompt) | `runs/phase_b1_reliability/H2_VERDICT.md`, `runs/phase_b1_reliability/H2_VERDICT.json` |
| H2 PI-frozen conclusion | `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md` |
| H3 interpretation (dev + held-out v2) | `orbit-research/H3_CREDIT_UNIT_INTERPRETATION_2026-05-23.md` |
| H3 plan + config | `orbit-research/archive/2026-05-doc-hygiene-post-c1/root-md/PHASE_B3_H3_PLAN.md` (archived), `configs/runs/phase_b3_credit_unit_comparison.yaml` |
| Phase C0 backend smoke | `orbit-research/ACE_STEP_LORA_GRPO_BACKEND_SMOKE_REPORT.md`, `orbit-research/ACE_STEP_LORA_GRPO_BACKEND_SPEC.md` |
| Phase C1 learning-signal audit | `orbit-research/archive/2026-05-doc-hygiene-post-c1/root-md/PHASE_C1_LEARNING_SIGNAL_AUDIT_2026-05-26.md` (archived) |
| Phase C1 training dynamics audit | `orbit-research/PHASE_C1_TRAINING_DYNAMICS_AUDIT_2026-05-26.md` |
| Phase C1 common eval status | `orbit-research/PHASE_C1_COMMON_EVAL_STATUS_2026-05-26.md` (canonical), `orbit-research/archive/2026-05-doc-hygiene-post-c1/root-md/PHASE_C1_COMMON_EVAL_AUDIT_2026-05-26.md` (archived) |
| Phase C1 checkpoint triage | `orbit-research/PHASE_C1_CHECKPOINT_TRIAGE_EVAL_2026-05-26.md` |
| Early-Tweedie validation report | `orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md` (+ JSON, PLOT.csv, RETENTION.csv) |
| Early-Tweedie PI decision | `orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md` |
| Early-Tweedie verification report | `orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json` |
| Track B global-quality analysis | `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` |
| Track C stop decision | `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` |
| Trajectory-aware completion audit | `orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md` |
| Canonical proposal (untouched) | `refine-logs/FINAL_PROPOSAL.md` |
| Short proposal (untouched) | `refine-logs/FINAL_PROPOSAL_SHORT.md` |
| Method spec (untouched) | `refine-logs/METHOD_SPEC.md` |
| Executable plan (untouched) | `refine-logs/EXPERIMENT_PLAN_EXEC.md` |
| Canonical file index | `orbit-research/CURRENT_CANONICAL_FILES.md` |
| Run ledger (135 events) | `orbit-research/RUN_LEDGER.jsonl` |
| Gate v2 freeze record | `orbit-research/GATE_V2_FREEZE_2026-05-23.md` |
| Per-change manifest | `MANIFEST.md` |
| Open questions snapshot | `ORBIT_OPEN_QUESTIONS.md` |
| Task board | `ORBIT_TASK_BOARD.md` |

End of report.
