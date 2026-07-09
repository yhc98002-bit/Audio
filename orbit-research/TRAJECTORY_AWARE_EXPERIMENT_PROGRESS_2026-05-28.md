# Trajectory-Aware Inference-Time Scaling: Experiment Progress

Generated: 2026-05-28

## Current Paper Center

The project has pivoted from RL post-training as the main claim to inference-time trajectory verification:

**Early Trajectory Verifiers for Flow-Matching Music Generation**

Equivalent framing:

**Trajectory-Aware Inference-Time Scaling for Flow-Matching Music Generation**

The core hypothesis is that early Tweedie-clean estimates expose trajectory quality before final generation, enabling risk-aware pruning or compute allocation that approaches full BoN quality at lower compute.

## Accepted Background Results

- Phase A established that ACE-Step has inference-time headroom.
- H2 established that intermediate Tweedie estimates carry final-quality signal in non-trivial sigma regions.
- H3 showed that section-level credit is not the best default credit unit for 30-40s ACE-Step generations.
- Time-uniform diagnostics support the mechanism view that short-form sample quality is often globally persistent rather than dominated by isolated local window failures.
- Phase C1 LoRA/GRPO training completed cleanly across R8a, R8b, M-FixedWin, and M-Section, but common downstream dev evaluation showed `COMMON_DEV_NO_CLEAR_WIN`.
- RL post-training is therefore boundary/exploratory evidence, not the current main method.

## Candidate Dataset

Canonical dataset card:

- `orbit-research/TRAJECTORY_CANDIDATE_DATASET_CARD.md`
- `orbit-research/trajectory_candidate_dataset.jsonl`

Current dataset:

- 512 prompts.
- 4096 BoN-8 candidates.
- Prompt-level split only:
  - train: 194 prompts.
  - validation: 62 prompts.
  - test/held-out: 256 prompts.
- Candidate fields include prompt metadata, seed, final robust/common and axis rewards, early sigma rewards at sigma 0.9/0.8/0.7, early ranks, final ranks, winner/top-k labels, and compute metadata.

Leakage controls:

- Split is by `prompt_id`, never candidate.
- Learned verifier training uses train prompts only.
- Threshold calibration uses validation prompts only.
- Held-out/test prompts are reserved for reporting learned-verifier and empirical risk-calibration results.

## Main BoN-8 Early-Tweedie Results

Primary outputs:

- `orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.md`
- `orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.json`
- `orbit-research/EARLY_TWEEDIE_PARETO.csv`
- `orbit-research/EARLY_TWEEDIE_AXIS_BREAKDOWN.csv`
- `orbit-research/EARLY_TWEEDIE_CROSS_AXIS_GENERALIZATION.csv`
- `orbit-research/EARLY_TWEEDIE_BON4_BOOTSTRAP.csv`

Primary robust/common metric:

| method | compute fraction | reward fraction | winner match | false-negative top1 |
|---|---:|---:|---:|---:|
| Full BoN-8 | 1.000 | 1.0000 | 1.0000 | 0.0000 |
| BoN-4 random subset | 0.500 | 0.9821 | 0.4976 | 0.5024 |
| Raw ETP Schedule A, sigma0.9 top4 -> sigma0.7 top2 | 0.500 | 0.9858 | 0.5762 | 0.4238 |
| Raw ETP Schedule B, sigma0.8 top4 -> sigma0.7 top2 | 0.583 | 0.9910 | 0.6641 | 0.3359 |
| Raw ETP Schedule C, sigma0.8 top6 | 0.850 | 0.9986 | 0.9395 | 0.0605 |
| Bottom-prune sigma0.7 remove bottom25 | 0.883 | 0.9996 | 0.9805 | 0.0195 |

Same-compute result:

- ETP@50 beats random BoN-4 on the primary robust/common metric.
- Paired bootstrap delta reward fraction: 0.0036.
- 95% CI: [0.0013, 0.0060].
- This is statistically separated but modest; it should be framed as a small early-information advantage over BoN-4, not a large quality jump.

Reviewer-risk caveat:

- Common-selected ETP preserves the primary/common and aesthetic axes better than random BoN-4.
- It does not uniformly preserve all non-primary axes.
- Semantic-fit and lyric-intelligibility cross-axis results are the main limitation and should be reported transparently.

## Learned Early Trajectory Verifier

Primary outputs:

- `orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.md`
- `orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.json`
- `orbit-research/EARLY_VALUE_FEATURE_IMPORTANCE.csv`
- `orbit-research/RISK_CONTROLLED_PRUNING_TABLE.csv`

Model:

- Lightweight ridge regressors.
- Inputs are early sigma reward vectors, early ranks, slopes, and prompt metadata.
- No large neural audio model is used.

Held-out/test prediction:

| model | Spearman with final common reward | prompt NDCG |
|---|---:|---:|
| ridge stage 0.9 | 0.6723 | 0.9871 |
| ridge stage 0.8 | 0.7892 | 0.9928 |
| ridge stage 0.7 | 0.8768 | 0.9951 |
| raw early 0.7 common | 0.7853 | 0.9946 |

Held-out/test learned pruning:

| schedule | compute | reward fraction | winner match | false-negative top1 |
|---|---:|---:|---:|---:|
| ETV Schedule A | 0.500 | 0.9907 | 0.6641 | 0.3359 |
| ETV Schedule B | 0.583 | 0.9924 | 0.6797 | 0.3203 |
| ETV Schedule C | 0.850 | 0.9991 | 0.9531 | 0.0469 |
| ETV bottom-prune sigma0.7 remove bottom25 | 0.883 | 0.9998 | 0.9922 | 0.0078 |

Interpretation:

- Learned ETV gives a meaningful held-out improvement over raw early sigma scoring.
- The strongest use case is conservative bottom-pruning / risk-aware compute saving.
- The current risk control is empirical validation-calibrated risk control, not a distribution-free conformal guarantee.

## Global Quality Mechanism

Primary outputs:

- `orbit-research/GLOBAL_QUALITY_MECHANISM_FIGURES.md`
- `orbit-research/GLOBAL_QUALITY_MECHANISM_TABLES.csv`
- `orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md`

Interpretation:

- For ACE-Step short-form outputs, local-window rewards appear to track persistent global trajectory quality more than isolated local failures.
- This helps explain why early trajectory pruning works and why local-window RL credit did not produce a clear downstream win.
- This should not be overclaimed as evidence that music has no local structure or that FixedWin is causal local credit.

## BoN-16 Subset

Status:

- BoN-16 subset validation is running in tmux session `early_tweedie_bon16_128_20260528`.
- Run root: `runs/early_tweedie_bon16_subset_128_20260528_full01`.
- Design: 128 stratified prompts, 16 candidates per prompt, sigma checkpoints 0.9/0.8/0.7, full final reward.
- Analysis script prepared: `scripts/analyze_bon16_pruning_subset.py`.

Purpose:

- Test whether trajectory-aware pruning becomes more valuable as N grows.
- Compare Full BoN-16, BoN-8 same-compute proxy, random prune, raw ETP, and learned ETV.

## Human Spot-Check Packet

Prepared outputs:

- `orbit-research/human_spotcheck_packet_20260528/HUMAN_SPOTCHECK_PACKET_MANIFEST.md`
- `orbit-research/human_spotcheck_packet_20260528/human_spotcheck_pairs.jsonl`
- `orbit-research/human_spotcheck_packet_20260528/scoring_sheet_template.csv`

Status:

- Pair manifest is prepared for 32 A/B comparisons.
- Prior validation did not save audio, so deterministic audio regeneration from stored prompt IDs and candidate seeds is still needed before PI listening.
- No crowdsourcing or human evaluation has been launched.

## Claude Audits

Audit files:

- `orbit-research/CLAUDE_AUDIT_1_DATASET_LEAKAGE_2026-05-28.json`
- `orbit-research/CLAUDE_AUDIT_2_BASELINE_FAIRNESS_2026-05-28.json`
- `orbit-research/CLAUDE_AUDIT_3_LEARNED_ETV_RISK_2026-05-28.json`

Current verdicts:

- Dataset/leakage: `ACCEPT_WITH_NONBLOCKING_NOTES`.
- Same-compute baseline fairness: `ACCEPT_WITH_NONBLOCKING_NOTES`.
- Learned ETV/risk calibration: `ACCEPT_WITH_NONBLOCKING_NOTES`.

Main nonblocking notes:

- Compute fractions use diffusion step-units and do not include early-decode/reward-scoring wall-clock overhead.
- The same-compute ETP-vs-BoN-4 advantage is real but small.
- Cross-axis semantic and lyric behavior is weaker than the primary/common metric.
- Empirical risk calibration should not be described as formal distribution-free risk control.

## Current Recommendation

The strongest paper framing is:

**Trajectory-aware inference-time scaling with early trajectory verification.**

Recommended main story:

1. Full BoN has measurable headroom.
2. Early Tweedie estimates predict final trajectory quality.
3. Raw ETP gives a small but robust same-compute advantage over BoN-4 on the primary robust/common metric.
4. Learned ETV improves held-out pruning and is strongest for conservative bottom-pruning.
5. Time-uniform quality structure explains why trajectory-level early signals are useful.
6. RL post-training is useful boundary evidence but should not be the main method.

Remaining before final PI decision:

- Complete BoN-16 subset validation.
- Regenerate human spot-check audio files for PI listening.
- Decide whether the paper main method should be raw ETP, learned ETV, or a hybrid where raw ETP is the transparent baseline and learned ETV is the main risk-aware verifier.

## Safety Confirmation

- No new RL training launched.
- No pruning+RL launched.
- No Phase D launched.
- No human crowdsourcing launched.
- No `gate_v1.yaml` modification.
- No reward-definition change.
- No prompt-split change.
- No canonical proposal rewrite.
