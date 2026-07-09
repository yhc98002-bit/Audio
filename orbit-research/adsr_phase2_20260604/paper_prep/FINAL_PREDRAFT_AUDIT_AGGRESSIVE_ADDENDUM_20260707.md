# Final Predraft Audit Aggressive Addendum

Generated: 2026-07-07

## 1. Final Status

Full-strength draft readiness: NOT_READY.

Reduced-claims draft readiness: READY_WITH_REDUCED_CLAIMS.

Reason: Stage 3, N2, efficiency/Figure 2, CLAP reduced evidence, router reduced evidence,
release-secret hygiene, and `PLAN.md` closure are artifact-backed. A-prime and B-prime did
not pass because the judge smoke failed; they are fallback-ready only. SAO package execution
was attempted, but second-backbone generation is blocked by gated model access.

## 2. What Changed Since Previous Audit

- Diagnosed failed negative smoke clips:
  `paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_TABLE.csv`,
  `paper_prep/judge_debug/NEGATIVE_SMOKE_FAILURE_ANALYSIS.md`.
- Built and ran judge smoke v2; Plus and Flash still failed 6/10:
  `paper_prep/judge_debug/judge_smoke_v2_manifest.csv`,
  raw logs under `paper_prep/judge_raw/`.
- Completed fallback A-prime scoring for 716/716 judgeable clips:
  `paper_prep/validation_A_prime/A_PRIME_RAW_RESPONSES.jsonl`.
- Completed fallback B-prime scoring for 80 pairs / 160 ordered calls:
  `paper_prep/validation_B_prime/B_PRIME_RAW_RESPONSES.jsonl`.
- Repaired SAO package blocker by installing `stable-audio-tools==0.0.20`
  into `audio-prm` with no Torch/torchaudio/CUDA diff, then attempted smoke:
  `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`.
- Expanded CLAP analysis:
  `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_REPORT.md`.
- Expanded router replay:
  `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_REPORT.md`.
- Fixed release-secret hygiene:
  `paper_prep/RELEASE_SECRET_HYGIENE_20260707.md`.
- Closed `PLAN.md` to 15 mandatory rows with zero BLOCKED rows:
  `paper_prep/PLAN.md`.

## 3. A-prime Status

A_PRIME_STATUS = FALLBACK_READY

- Full manifest rows: 816.
- Judgeable rows: 716.
- Scored rows: 716.
- Missing/unjudgeable rows: 100.
- Rare-basin confirmation by fallback judge: 15/74 = 0.202703; required >= 0.90.
- Detector-disagreement frozen criterion was not satisfied: the manifest did not provide
  112 scored detector-disagreement rows with usable Demucs truth labels.
- Stratified-500 disagreement versus Demucs: 363/499 = 0.727455.

Artifacts:

- `paper_prep/validation_A_prime/A_PRIME_MANIFEST.csv`
- `paper_prep/validation_A_prime/A_PRIME_RAW_RESPONSES.jsonl`
- `paper_prep/validation_A_prime/A_PRIME_AGREEMENT_MATRIX.csv`
- `paper_prep/validation_A_prime/A_PRIME_GATE_REPORT.md`

Remaining blocker: PI/human adjudication or a validated replacement judge is required before
any A-prime pass claim.

## 4. B-prime Status

B_PRIME_STATUS = FALLBACK_READY

- Pairs: 80.
- Ordered calls: 160/160 complete.
- Q1 decided calls: 77; ties: 83; refusals/unparsed: 0.
- Method preferred: 50/77 = 0.649351.
- One-sided binomial P[X <= observed | n, p=0.5]: 0.997065.
- Order bias: `ab` method/baseline/tie 24/14/42; `ba` 26/13/41.

Artifacts:

- `paper_prep/validation_B_prime/B_PRIME_MANIFEST.csv`
- `paper_prep/validation_B_prime/B_PRIME_RAW_RESPONSES.jsonl`
- `paper_prep/validation_B_prime/B_PRIME_ORDER_BIAS_REPORT.md`
- `paper_prep/validation_B_prime/B_PRIME_GATE_REPORT.md`

Remaining blocker: judge validation/calibration is absent because Qwen smoke did not pass.

## 5. SAO Status

SAO_STATUS = PARTIAL

- Environment used: `audio-prm`.
- Package change: only `stable-audio-tools==0.0.20` was added.
- Package diff:
  `paper_prep/sao/logs/audio_prm_pip_freeze_before_sao_20260707.txt` to
  `paper_prep/sao/logs/audio_prm_pip_freeze_after_sao_20260707.txt`.
- Smoke result: FAIL, return code 1, no audio generated.
- Smoke artifact: `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`.
- Model access artifact: `paper_prep/sao/logs/sao_hf_prefetch_20260707.log`
  shows Hugging Face gated-repo 401 for `stabilityai/stable-audio-open-1.0`.
- Prevalence/observability/intervention were not run because smoke failed:
  `paper_prep/sao/prevalence/SAO_PREVALENCE_REPORT.md`,
  `paper_prep/sao/observability/SAO_OBSERVABILITY_REPORT.md`,
  `paper_prep/sao/intervention/SAO_INTERVENTION_REPORT.md`.

Second-model robustness cannot be claimed.

## 6. CLAP/Fidelity Status

CLAP_STATUS = REDUCED

- Original paired delta: +0.005996, CI [-0.003555, 0.015548].
- Expanded paired delta: +0.005996, median +0.002001,
  bootstrap 95% CI [-0.003375, 0.015661].
- Rare-basin subgroup: -0.037730, CI [-0.102102, 0.026642].

Allowed wording: no clear CLAP drop was detected. Do not claim semantic preservation is proven.

## 7. Router Status

Router final claim: reduced.

- Original budget-8 replay: rare-router 0.884302, always-reseed 0.694678,
  always-recondition 0.974455.
- Expanded budget-8 replay: best non-oracle threshold policy 0.977290, only
  +0.002835 over always-recondition and not live-deployable.

Artifact: `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_REPORT.md`.

## 8. Node Utilization

Artifacts:

- `paper_prep/NODE_SATURATION_AUDIT_20260707.md`
- `paper_prep/heartbeat_an12.log`
- `paper_prep/heartbeat_an29.log`

an12:

- Heartbeat session: `codex_heartbeat_an12`.
- Current state: busy with non-ADSR BlindGain/Ray and GPU profile jobs.
- Recovery note: unknown/non-ADSR jobs were not killed.

an29:

- Heartbeat session: `codex_heartbeat_an29`.
- Current state: busy with non-ADSR GPU profile jobs.
- Recovery note: SAO was attempted on an29 and failed at model-access/cache boundary.

Idle-gap handling:

- SAO work was dispatched when the package path became usable.
- The old atlas backlog was inspected but not launched because prior tag reuse and
  duplicate-ledger risk made immediate dispatch unsafe without a new seed/tag plan.

## 9. PLAN.md Closure

- READY rows: 9.
- REDUCED rows: 5.
- BLOCKED rows: 0.
- REMOVED rows: 1.

Artifact: `paper_prep/PLAN.md`.

`READY_TO_DRAFT` is not allowed because A-prime/B-prime did not pass and SAO did not
generate second-backbone evidence. The reduced draft can proceed only with the wording
constraints in `PLAN.md`.

## 10. Remaining PI Decisions

- Provide authenticated Hugging Face access for `stabilityai/stable-audio-open-1.0` if
  SAO second-backbone evidence is still required.
- Decide whether to run PI/human adjudication for A-prime labels and B-prime quality,
  or accept reduced automatic/fallback wording.

FINAL_STATUS = READY_WITH_REDUCED_CLAIMS
