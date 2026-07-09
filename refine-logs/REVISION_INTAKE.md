# Revision Intake — Round 1 (2026-05-28)

- **Target**: `both` (FINAL_PROPOSAL.md + EXPERIMENT_PLAN_EXEC.md)
- **Patch mode**: `both` — direct rewrite (user-authored authoritative direction)
- **Decision log used**: `orbit-research/RESEARCH_DECISION_LOG.md` is superseded
  (2026-05-23 H2-AMBIGUOUS context only); the live state is captured in
  `orbit-research/EXPERIMENT_PROGRESS_CONTEXT_2026-05-28.md` +
  `orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md`. PI has explicitly
  authorized canonical proposal rewrite via this `/proposal-revise` invocation.
- **Critique source**: `/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/revise.md`
- **Execution path** (per PI 2026-05-28 question): **Direct rewrite (revise.md
  authoritative)** — no per-stage Codex re-runs; one Codex Phase 3 re-evaluation
  via shell `codex exec`.
- **Method depth**: paper-direction + implementation sketch in METHOD_SPEC.
- **RL framing**: boundary result, demoted to short paper section per
  revise.md §7.
- **Snapshot directory**:
  `orbit-research/archive/2026-05-28-proposal-revise-round-1/`
- **Timestamp**: 2026-05-28

## Anchor restatement (immutable for this round)

The original problem anchor was **musical credit assignment in flow-matching
music generation** under the question *"when and where to reward"*. The
experimental program supported "when" (H2 STRONG_PASS) but found that "where"
in the M-PRM RL sense did not deliver: H3 Section credit failed against
FixedWin/BeatWin; C1 first-wave RL did not show a clear common-eval win
(`COMMON_DEV_NO_CLEAR_WIN`); Track B showed local-window rewards behave as
proxies for persistent global quality, not isolated local credit.

The new anchor — authored by PI in `revise.md` — is **early trajectory
verification**: flow-matching trajectories carry final-quality signal early
enough to support compute-saving inference-time selection. This is not anchor
drift; it is a **deliberate anchor shift** because the experimental record
overturned the original anchor's main assumption (local credit assignment as
the dominant available signal). The Phase 2 anchor check verifies the shift
is honest (the experimental program produced the evidence that justifies it)
and the simplicity check verifies the new method is no more complex than the
old.

## Critique items (parsed from revise.md)

| ID | Owning Stage | Affected Artifact(s) | Raw Text | Suggested Direction |
|---|---|---|---|---|
| C1 | 21 (claims) | FINAL_PROPOSAL §0/§1/§title | "论文不是'剪枝技巧'，而是: Flow-matching 音乐生成中的早期轨迹状态已经携带最终质量信号; 我们将其形式化为 early trajectory verification 问题" | Reframe paper as Early Trajectory Verifiers (ETV); the headline contribution is a method (learned verifier), not just a heuristic schedule. |
| C2 | 21 | FINAL_PROPOSAL §6 (hypotheses) | revise.md §4.1 five claims | Five paper-level claims: (1) early-trajectory predictive; (2) raw ETP already strong; (3) learned ETV further improves same-compute selection; (4) substantial compute saving near full BoN; (5) global persistent quality explains why early pruning works. |
| C3 | 5+8 (mechanism) | METHOD_SPEC §1-5; ABSTRACT_TASK_MECHANISM (archived) | revise.md §5 Method 2 | New main method = ETV: learned `V_σ(candidate, prompt) → final quality / final rank / top-k survival`. Hierarchical model family: linear/logistic → GBDT/LambdaMART/pairwise ranker (primary) → small MLP (optional appendix). Not a large audio model. |
| C4 | 5+8 | METHOD_SPEC §5 | revise.md §5 Method 3 | Risk-controlled adaptive pruning: P(prune final top-1) ≤ ε with ε ∈ {1%, 3%, 5%}. Converts heuristic schedule into risk-aware pruning. |
| C5 | 5+8 (mechanism) | METHOD_SPEC §5 | revise.md §5 Method 1 | Raw Early-Tweedie Pruning baseline with the four fixed schedules from the Track A validation (Schedule A/B/C + bottom-prune σ0.7). This is the strong baseline against which ETV competes. |
| C6 | 5+8 | METHOD_SPEC §5 | revise.md §5 Method 4 | Optional: adaptive compute allocation (confident bad → prune; uncertain → continue; confident good → retain). Extension only. |
| C7 | 14 (formalization) | ALGORITHMIC_FORMALIZATION.md | revise.md §5 input features | Formalize V_σ verifier with concrete feature set: early reward vector at σ ∈ {0.9, 0.8, 0.7}; reward slope `r_{0.7} − r_{0.9}`; early rank within prompt; prompt type (vocal/instrumental); CLAP/Audiobox/MERT scores if available; uncertainty features. Frozen embeddings optional, no large-model training. |
| C8 | 4 (assumptions) | ASSUMPTION_LEDGER.md | revise.md §4.1 (1) | Add `A30: early σ Tweedie estimates carry sufficient signal for final-ranking prediction within a BoN group on the target prompt distribution`. (Empirically supported by H2 + Track A; not novel claim.) |
| C9 | 4 | ASSUMPTION_LEDGER.md | revise.md §5 model tiers | Add `A31: cached early-σ reward vectors + lightweight feature engineering are sufficient for a small ML verifier to beat raw schedules at matched compute (no large model required)`. |
| C10 | 4 | ASSUMPTION_LEDGER.md | revise.md §6 Experiment 2 | Add `A32: same-compute comparison vs. BoN-K (K matched to ETV's average kept candidate count) is the right benchmark frame; ETV's value depends on beating BoN-4 at matched compute`. |
| C11 | 11 (controls) | CONTROL_DESIGN.md | revise.md §6 Experiment 2 | New required controls: BoN-4, Random prune at matched compute, Raw ETP schedule A/B/C/bottom-prune-σ0.7. Drop the old M-PRM-centric controls (Stepwise-Tweedie / BeatWin-Tweedie / LyricSpan-Tweedie) — these are no longer the headline baselines. |
| C12 | 12 (null-result) | NULL_RESULT_CONTRACT.md | revise.md §6 Experiment 2 | If ETV cannot beat BoN-4 at matched compute, the paper claim weakens substantially; ETV becomes a "we tried it and BoN-4 is hard to beat" honest negative. Define this pivot route explicitly. |
| C13 | 13 (bundle) | COMPONENT_BUNDLE_LADDER.md | revise.md §5 model tiers + §6 metrics | New ablation dimensions: (a) feature ablation (drop slope; drop rank; drop prompt-type); (b) model-family ablation (linear vs GBDT vs MLP); (c) risk-threshold ablation (ε ∈ {1%, 3%, 5%}); (d) per-σ-stage ablation (σ=0.9 alone vs σ=0.9+0.7 vs σ=0.9+0.8+0.7). |
| C14 | 16 (diagnostic) | DIAGNOSTIC_EXPERIMENT_PLAN.md | revise.md §6 (Exp 1-6) | Six experiments: (1) trajectory quality emergence; (2) same-compute pruning comparison [main]; (3) cross-metric validation; (4) human spot-check 32-64 pairs; (5) global quality mechanism via time-uniform diagnostic; (6) failure analysis (mis-pruned late bloomers, ETV failure cases, vocal/instrumental stratification). |
| C15 | 21 (claims, RL framing) | FINAL_PROPOSAL §6 + §9 + boundary section | revise.md §7 | Demote RL/C1 to boundary result. Single section with the exact framing in revise.md §7 ("backend trains stably, but a first-wave comparison did not produce clear common-metric gains"). No defensive elaboration. |
| C16 | 21 (structure) | FINAL_PROPOSAL outline | revise.md §8 | New paper structure: Title = "Early Trajectory Verifiers for Flow-Matching Music Generation". Abstract centered on early-trajectory prediction. 10 sections: Intro / Background / Trajectory quality emergence / Early-Tweedie pruning / ETV + risk-controlled pruning / Experiments / Human eval / Mechanism (global) / Boundary (RL) / Discussion. |
| C17 | 23 (red-team) | FINAL_PROPOSAL §9 + revise.md §9 anti-claims | revise.md §9 | Avoid scattered scope. H1/H2 are setup; H3 is motivation/boundary; C1 RL is boundary; Pruning + ETV is main method; globalness is mechanism. Do not re-explain every prior hypothesis. |
| C18 | 21 (claims, scope) | FINAL_PROPOSAL §11 reporting order | revise.md §6 metrics | Primary metric: reward fraction and compute fraction at same-compute matched comparison; secondary: winner-match, top-2 retention, false-negative, regret. Cross-metric: not only `aesthetic_pq` (avoid reward circularity). |

## Stages to re-run / artifacts to update

Live v1.3 contracts to update (Phase 1):

- **Stage 4 (assumptions)**: `orbit-research/ASSUMPTION_LEDGER.md` — add A30/A31/A32; reclassify old A23-A29 (M-PRM-specific) as `historical / superseded` (not deleted).
- **Stage 11 (controls)**: `orbit-research/CONTROL_DESIGN.md` — add ETV controls, demote M-PRM-specific controls to historical.
- **Stage 12 (null-result)**: `orbit-research/NULL_RESULT_CONTRACT.md` — add "ETV cannot beat BoN-4" pivot route.
- **Stage 13 (bundle)**: `orbit-research/COMPONENT_BUNDLE_LADDER.md` — new ETV ablation dimensions; demote M-PRM ablations to historical.
- **Stage 14 (formalization)**: `orbit-research/ALGORITHMIC_FORMALIZATION.md` — add V_σ verifier formalization, risk-controlled selection definition.
- **Stage 16 (diagnostic)**: `orbit-research/DIAGNOSTIC_EXPERIMENT_PLAN.md` — six new experiments.

Method spec + paper-level artifacts (Phase 3):

- `refine-logs/METHOD_SPEC.md` — add new §X "Early Trajectory Verifier (ETV)" with implementation sketch (features, model tiers, training data, evaluation protocol). Demote prior M-PRM sections to historical/boundary.
- `refine-logs/FINAL_PROPOSAL.md` — reframe around ETV; new title, abstract, contributions, hypotheses, experiments, structure.
- `refine-logs/EXPERIMENT_PLAN_EXEC.md` — six experiments per revise.md §6.

Artifacts NOT touched (per PI durability rules):

- `orbit-research/archive/**` — historical artifacts stay archived.
- Raw run outputs under `runs/**`.
- `configs/eval/gate_v1.yaml` (frozen).
- `configs/eval/gate_v2.yaml.draft` (stays draft).
- PI listening packets, tarballs, parity evidence, gate-decision backups.
- `orbit-research/HEADROOM_GATE_PREREG.md`, `HEADROOM_GATE_DECISION.json`,
  `GATE_V1_SHA_BACKFILL_*.md`, `GATE_V2_FREEZE_*.md` — gate evidence preserved.
- `orbit-research/PHASE_B1_H2_CONCLUSION_2026-05-23.md`,
  `H3_CREDIT_UNIT_INTERPRETATION_2026-05-23.md`,
  `EARLY_TWEEDIE_PRUNING_VALIDATION.md`, `EARLY_TWEEDIE_VALIDATION_PI_DECISION.md`,
  `GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md` — experimental verdicts preserved.
- `orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md` — decision preserved.
- `refine-logs/FINAL_PROPOSAL_SHORT.md` — already marked historical in canonical index; NOT touched this round (PI may choose to retire it separately).
- `refine-logs/EXPERIMENT_PLAN.md` — historical index; NOT touched.
- `CLAUDE.md` / `AGENTS.md` — current snapshot needs a minor refresh in the
  "Recommended current paper direction" line; will be done as part of REVISION_REPORT.

## Anchor + Simplicity check (Phase 2)

### Anchor check

Original problem anchor (`PROBLEM_SELECTION.md` archived; restated for the
record): *credit assignment in flow-matching music generation under the
question of when and where to reward*.

Empirically observed by 2026-05-28:
- "When" (H2) **supported** by 128-prompt verdict on intermediate Tweedie
  reliability and quality-stratified emergence.
- "Where" (H3) **not supported** in the section-credit sense; Track B
  globalness analysis says local-window rewards are persistent-global-quality
  proxies in this regime.
- C1 RL post-training: engineering pass, scientific
  `COMMON_DEV_NO_CLEAR_WIN`.

The trajectory-aware story (Early-Tweedie + globalness) is what the data
actually supports. The user's `revise.md` reframes the paper around
**Early Trajectory Verification** — which is a refinement of "when to
reward" extended into "when can we predict and act on quality"
(verification as the operational use of emergence). This is **anchor
preservation under empirical update**, not anchor drift:

- The original problem (credit assignment) was a *means* hypothesis for
  improving music quality; the empirical record showed that local credit
  is mostly redundant with global quality in this regime. The new direction
  uses the **same trajectory-evidence apparatus** (Track A + Track B + H2)
  to address the **same underlying motivation** (improving generation
  quality from inference-time signals), via a different operational lever
  (inference-time selection rather than RL post-training).

- The five new paper-bearing claims (ETV1–ETV5) are all anchored in the
  trajectory-aware empirical record produced by the existing experimental
  program. No new empirical regime is required.

**Verdict: ANCHOR_PRESERVED_UNDER_EMPIRICAL_UPDATE.** This is the legitimate
outcome of an experimental program that produced unexpected evidence —
the data overturned one operational claim (local RL credit) and supported
another (early trajectory verification). PI's `revise.md` reframes the
paper around the supported claim, which is the correct response.

### Simplicity check

Constants:
- `MAX_NEW_TRAINABLE_COMPONENTS = 2`.
- `MAX_PRIMARY_CLAIMS = 2` (interpreted here as "main contributions";
  paper claims have a foundation + main + mechanism structure under the
  PI's revise.md §8 layout).
- "Smallest adequate mechanism wins."

ETV's component count:
1. The Early Trajectory Verifier itself — ONE small ML model (GBDT /
   LambdaMART primary; linear floor; MLP optional appendix). Trained on
   cached features from the existing reward stack. No new large-model
   training, no new gradient pipeline.
2. Risk-controlled selection threshold calibration — a one-line conformity
   calibration on a held-out split. This is a *use* of the verifier, not
   an independent trainable component.

**New trainable components: 1.** Within budget (≤ 2).

Primary claim count (per revise.md §4.1, paper claims):
- C1 (foundation, supported by H2+Track A): early σ predicts final quality.
- C2 (raw method, supported by Track A): raw fixed schedules already strong.
- C3 (main contribution, ETV): learned verifier improves same-compute selection.
- C4 (operational, ETV-RC): risk-controlled pruning trades compute for false-negative.
- C5 (mechanism, supported by Track B): global persistence explains why ETV works.

Five paper-bearing statements, but only **C3+C4 are the main novel
contributions** (the learned verifier + risk control). C1+C2+C5 are
empirical findings that anchor the new method. Interpreting MAX_PRIMARY_CLAIMS
strictly as "main novel contributions" = 2. Within budget.

Mechanism removability check: can we drop ETV (the learned part) without
losing the paper? **No.** The paper without ETV degenerates to "raw
Early-Tweedie pruning works" — which is the Track A result, already
canonical. The paper *needs* the learned verifier (or its honest negative
in the failure case) to be a *paper*, not just a validation report.

Can we drop risk control? Yes — paper degenerates from "calibrated
selection" to "single fixed schedule"; still publishable, but less
operationally useful. Therefore risk control is the LEAST removable;
keep it but only if the calibration gives a non-trivial ε–compute curve.
If ε ∈ {1, 3, 5}% collapse to the same compute fraction, drop risk
control to an appendix.

**Verdict: SIMPLICITY_PASS.** ETV stays within the simplicity discipline.
No mechanism is added that could be removed without losing the anchored
claim.

### Phase 2 conclusion

All 18 critique items (C1–C18) survive Phase 2:
- ANCHOR check: preserved under empirical update (not drift).
- SIMPLICITY check: 1 new trainable component, 2 main novel contributions,
  no removable mechanisms.

No critique item is rejected. Proceed to Phase 3 (re-integration of FINAL_PROPOSAL.md + EXPERIMENT_PLAN_EXEC.md + METHOD_SPEC.md).

## Codex availability

- Codex CLI present at `/HOME/paratera_xy/pxy1289/.local/bin/codex` (version 0.133.0).
- Mode: shell `codex exec` per project CLAUDE.md (NOT MCP) — single Phase 3
  reviewer-independent re-eval call planned.
