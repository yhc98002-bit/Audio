# Codex Progress Report

Generated: 2026-07-08

Workspace:

`/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion`

## Executive Status

The publication recovery work was advanced from the previous status snapshot into
an artifact-backed reduced-claims package.

Current verified state:

- Full draft readiness: `NOT_READY`.
- Reduced draft readiness: `READY_WITH_REDUCED_CLAIMS`.
- `paper_prep/PLAN.md`: 15 claim rows, 9 `READY`, 5 `REDUCED`, 0 `BLOCKED`, 1 `REMOVED`.
- Final aggressive addendum: `paper_prep/FINAL_PREDRAFT_AUDIT_AGGRESSIVE_ADDENDUM_20260707.md`.
- Addendum final status: `FINAL_STATUS = READY_WITH_REDUCED_CLAIMS`.

The original full-strength target, `FINAL_STATUS = READY_TO_DRAFT`, is not currently
scientifically supported because A-prime and B-prime did not pass as validated gates,
and SAO did not generate second-backbone evidence. I did not rewrite those failures into
passes.

## Master Ledger

Created/appended:

- `paper_prep/execution_20260707/AGGRESSIVE_RECOVERY_LEDGER.md`

The ledger records timestamp, host/node, command/script path, input artifacts,
output artifacts, result, and next action for the major recovery actions.

## Judge Smoke Diagnosis

Produced:

- `paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_TABLE.csv`
- `paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_ANALYSIS.md`
- `paper_prep/judge_debug/judge_smoke_v2_manifest.csv`
- raw logs under `paper_prep/judge_raw/`

What changed:

- Diagnosed the previous failed negative smoke clips instead of treating the
  6/10 result as a generic model failure.
- Found that the failed negatives were not safe negatives: several were plausibly
  voice-like, contained speech/rap/humming/choir-like material, or were otherwise
  ambiguous under the model prompt.
- Built judge smoke v2 with clearer positive and conservative instrumental-negative
  examples.
- Re-ran Qwen Plus and Flash smoke v2.

Outcome:

- Qwen Plus smoke v2: 6/10.
- Qwen Flash smoke v2: 6/10.
- No A-prime/B-prime scale result was allowed to become a formal validated PASS.

## A-prime Label Validation

Produced/updated:

- `paper_prep/validation_A_prime/A_PRIME_MANIFEST.csv`
- `paper_prep/validation_A_prime/A_PRIME_JUDGEABLE_MANIFEST.csv`
- `paper_prep/validation_A_prime/A_PRIME_RAW_RESPONSES.jsonl`
- `paper_prep/validation_A_prime/A_PRIME_AGREEMENT_MATRIX.csv`
- `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md`

Execution:

- Built/repaired the A-prime manifest from existing packets and extracted packaged
  media where available.
- Ran the fallback model-judge path to completion for all judgeable rows.

Verified counts:

- Full manifest rows: 816.
- Judgeable rows: 716.
- Scored rows: 716.
- Raw per-call judge rows: 2,148.
- Missing/unjudgeable rows: 100.

Gate report status:

- `A_PRIME_STATUS = FALLBACK_READY`.

Key measured results:

- Rare-basin fallback confirmation: 15/74 = 0.202703.
- Stratified-500 disagreement versus Demucs: 363/499 = 0.727455.
- The required validated A-prime PASS criteria were not met.

Interpretation:

The A-prime package is ready for PI/human adjudication or a validated replacement
judge, but it cannot be cited as a passed label-validation gate.

## B-prime Quality Validation

Produced/updated:

- `paper_prep/validation_B_prime/B_PRIME_MANIFEST.csv`
- `paper_prep/validation_B_prime/B_PRIME_RAW_RESPONSES.jsonl`
- `paper_prep/validation_B_prime/B_PRIME_ORDER_BIAS_REPORT.md`
- `paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md`

Execution:

- Built the B-prime manifest from existing paired listening materials.
- Ran fallback model-judge calls for both A/B orders.
- Scored method preference, ties, refusals, and order-bias counts.

Verified counts:

- Pair rows: 80.
- Ordered calls: 160/160 complete.
- Q1 decided calls: 77.
- Q1 ties: 83.
- Q1 refusals/unparsed: 0.

Gate report status:

- `B_PRIME_STATUS = FALLBACK_READY`.

Key measured results:

- Method preferred: 50/77 = 0.649351.
- One-sided binomial P[X <= observed | n, p=0.5]: 0.997065.
- Order counts:
  - `ab`: method 24, baseline 14, tie 42.
  - `ba`: method 26, baseline 13, tie 41.

Interpretation:

The fallback B-prime package is numerically favorable, but the judge was not
validated by smoke/calibration. It supports reduced wording only, not a formal
B-prime PASS.

## SAO Second-Model Spike

Produced/updated:

- `paper_prep/sao/SAO_EXECUTION_PLAN_20260707.md`
- `paper_prep/sao/logs/audio_prm_direct_sao_install_20260707.log`
- `paper_prep/sao/logs/audio_prm_pip_freeze_before_sao_20260707.txt`
- `paper_prep/sao/logs/audio_prm_pip_freeze_after_sao_20260707.txt`
- `paper_prep/sao/logs/sao_hf_prefetch_20260707.log`
- `paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl`
- `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`
- `paper_prep/sao/prevalence/SAO_PREVALENCE_REPORT.md`
- `paper_prep/sao/observability/SAO_OBSERVABILITY_REPORT.md`
- `paper_prep/sao/intervention/SAO_INTERVENTION_REPORT.md`

Execution:

- Tried a dedicated `audio-prm-sao` environment; this stalled in package resolution.
- Switched to the authorized direct execution route.
- Installed `stable-audio-tools==0.0.20` into `audio-prm` using `--no-deps`.
- Verified package diff: only `stable-audio-tools==0.0.20` was added; Torch,
  torchaudio, and CUDA stack were not changed by that install.
- Launched one-sample SAO smoke on `an29`.

Outcome:

- `SAO_SMOKE_STATUS = FAIL`.
- No SAO audio was generated.
- an29 could not resolve Hugging Face.
- Login-node prefetch failed with Hugging Face gated-repo 401 for
  `stabilityai/stable-audio-open-1.0`.

Interpretation:

The previous package blocker was resolved. The remaining blocker is authenticated
model access/cache availability. No second-backbone robustness claim is supported.

## CLAP / Prompt Fidelity

Produced:

- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_RESULTS.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_PROMPT_ROWS.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_REPORT.md`

Execution:

- Reanalyzed CLAP prompt-fidelity with bootstrap confidence intervals.
- Added direction/regime breakouts including vocal-miss, instrumental-leak,
  N2 regime, and rare-basin subgroup.

Status:

- `CLAP_STATUS = REDUCED`.

Key measured result:

- Overall paired arm6-arm1 delta mean: +0.005996.
- Median: +0.002001.
- Bootstrap 95% CI: [-0.003375, 0.015661].
- Rare-basin subgroup delta: -0.037730, CI [-0.102102, 0.026642].

Interpretation:

Allowed wording: no clear CLAP drop was detected. Do not claim semantic
preservation was proven.

## Router Replay

Produced:

- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_RESULTS.csv`
- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv`
- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_REPORT.md`

Execution:

- Reproduced the original CPU-only router replay.
- Added threshold sweeps, direction-aware variants, N2-regime-prior variants,
  and oracle/outcome-informed diagnostic rows.

Key measured result at budget 8:

- Original rare-router: 0.884302 expected clean/prompt.
- Always reseed: 0.694678.
- Always recondition: 0.974455.
- Expanded best non-oracle threshold policy: 0.977290.
- Improvement over always-recondition: +0.002835.

Interpretation:

Router claim is reduced to an offline negative/replay result. The expanded replay
does not support a deployable live-router claim.

## Release-Secret Hygiene

Produced:

- `paper_prep/RELEASE_SECRET_HYGIENE_20260707.md`

Execution:

- Redacted the literal DashScope key from `CLAUDE.md`.
- Kept runtime credential use environment-first via `$DASHSCOPE_API_KEY`.
- Added `.gitignore` rules for `.dashscope_key` and related secret files.
- Verified the scoped releaseable docs no longer contain literal key-pattern hits.

Status:

- `SECRET_STATUS = CLEAN`.

Important release note:

- Do not package `paper_prep/scripts/.dashscope_key`.

## PLAN.md Closure

Updated:

- `paper_prep/PLAN.md`

Verified current counts:

- Claim rows: 15.
- `READY`: 9.
- `REDUCED`: 5.
- `BLOCKED`: 0.
- `REMOVED`: 1.

Wording hygiene:

- Removed forbidden or overclaiming wording from `PLAN.md` and the final addendum.
- The plan no longer claims A-prime passed, B-prime passed, human studies confirmed,
  semantic preservation proven, loss-free quality, or second-backbone robustness.

## Node Utilization

Produced:

- `paper_prep/NODE_SATURATION_AUDIT_20260707.md`
- `paper_prep/heartbeat_an12.log`
- `paper_prep/heartbeat_an29.log`

Actions:

- Started heartbeat tmux sessions:
  - `codex_heartbeat_an12`
  - `codex_heartbeat_an29`
- Logged GPU state, tmux sessions, Python processes, and ledger line counts.
- Attempted SAO smoke on `an29`.
- Inspected atlas backlog for safe dispatch.

Important node decision:

- I did not launch the old atlas extension backlog after SAO failed because prior
  `ext512` logs and project notes documented tag-reuse / duplicate-ledger risk.
  Launching without a new seed/tag plan could have corrupted frozen atlas evidence.

Current utilization at the last checked snapshot:

- `an12`: busy with non-ADSR BlindGain/Ray and GPU profile jobs.
- `an29`: busy with non-ADSR GPU profile jobs.

## Final Artifacts of This Recovery Pass

- `paper_prep/FINAL_PREDRAFT_AUDIT_AGGRESSIVE_ADDENDUM_20260707.md`
- `paper_prep/PLAN.md`
- `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md`
- `paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md`
- `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_REPORT.md`
- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_REPORT.md`
- `paper_prep/RELEASE_SECRET_HYGIENE_20260707.md`
- `paper_prep/NODE_SATURATION_AUDIT_20260707.md`
- `paper_prep/execution_20260707/AGGRESSIVE_RECOVERY_LEDGER.md`

## Remaining Work Required For READY_TO_DRAFT

The project cannot honestly move from `READY_WITH_REDUCED_CLAIMS` to
`READY_TO_DRAFT` until one of these happens:

1. A-prime label validation passes via human/PI adjudication or a validated
   replacement judge.
2. B-prime quality validation passes via human/PI adjudication or a validated
   replacement judge.
3. SAO model access is provided and the SAO smoke, prevalence, observability,
   and intervention sequence generates usable evidence; otherwise the paper must
   keep the single-backbone limitation.

Until then, the scientifically clean state is reduced-claims draft readiness,
not full-strength draft readiness.
