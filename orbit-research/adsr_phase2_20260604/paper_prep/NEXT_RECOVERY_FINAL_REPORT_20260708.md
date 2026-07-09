# Next Recovery Final Report 20260708

Generated: 2026-07-08 13:48 CST

## Full draft readiness

NOT_READY

Full readiness still fails because A-prime and B-prime have not passed. A-prime
and B-prime are now both human-ready with zero missing media, but no actual
PI/human ratings or calibration scores are recorded.

## Reduced draft readiness

READY_WITH_REDUCED_CLAIMS

The reduced package is now stronger than the previous status: SA3 Medium was
downloaded from ModelScope, run locally, smoke-tested, scanned at guide scale,
scored, probed with a low-step observability proxy, and tested with a focused
vocal-boost intervention. `paper_prep/PLAN.md` has zero BLOCKED rows and keeps
unsupported claims reduced.

## SA3 / SAO

- Download status: `SA3_DOWNLOAD_STATUS = PASS`.
  - Artifact: `paper_prep/sao/stable_audio_3_medium/SA3_DOWNLOAD_REPORT.md`
  - Local model: `model_cache/modelscope/stabilityai/stable-audio-3-medium`
- Env status: `SA3_ENV_STATUS = PASS`.
  - Artifact: `paper_prep/sao/stable_audio_3_medium/SA3_ENV_REPORT.md`
  - Note: `audio-prm` was mutated as authorized for execution; torch/torchaudio/CUDA package diffs are recorded there.
- Smoke status: `SA3_SMOKE_STATUS = PASS`.
  - Artifact: `paper_prep/sao/stable_audio_3_medium/smoke/SA3_SMOKE_REPORT.md`
  - Output audio: `paper_prep/sao/stable_audio_3_medium/smoke/audio/sa3_smoke_seed20260708_dur8s.wav`
- Prevalence rows: `SA3_PREVALENCE_ROWS = 4000`, satisfying `SA3_PREVALENCE_ROWS >= 1024`.
  - Artifact: `paper_prep/sao/stable_audio_3_medium/prevalence_full500/SA3_PREVALENCE_REPORT.md`
  - `SA3_PREVALENCE_STATUS = FULL_GUIDE_COMPLETE`
  - `SA3_DOMINANT_FAILURE_MODE = vocal_miss`
  - Overall type-correct: 2,172/4,000 = 0.543000, Wilson CI [0.527528, 0.558389]
  - Vocal type-correct: 0.270498
  - Instrumental type-correct: 0.991402
  - Best-of-8 success: 325/500 = 0.650000, Wilson CI [0.607192, 0.690521]
- Observability status: `SA3_OBSERVABILITY_STATUS = COMPLETE`; conclusion `EARLY_OBSERVABILITY_WEAK`.
  - Artifact: `paper_prep/sao/stable_audio_3_medium/observability/SA3_OBSERVABILITY_REPORT.md`
  - Low-step proxy rows: 1,000 generated and scored
  - Matched low-step/full present agreement: 943/1,000 = 0.943000
  - Constraint: this is a low-step proxy, not true intermediate-latent decoding.
- Intervention status: `SA3_INTERVENTION_STATUS = COMPLETE`.
  - Artifact: `paper_prep/sao/stable_audio_3_medium/intervention/SA3_INTERVENTION_REPORT.md`
  - Focused vocal-boost intervention: 191/256 type-correct vs 14/256 baseline, lift +0.691406
- Second-backbone claim status: REDUCED.
  - Allowed: SA3 Medium guide-scale pilot reproduced a measurable vocal-presence constraint, and a focused prompt intervention moved the dominant detected failure mode.
  - Forbidden: full second-backbone robustness, true SA3 early observability, or full SA3 ADSR validation.

## A′

- Package status: `A_PRIME_PACKAGE_STATUS = HUMAN_READY_ZERO_MISSING`
- Artifact: `paper_prep/validation_A_prime/A_PRIME_HUMAN_READY_REPORT.md`
- Human package: `paper_prep/validation_A_prime/human_package/`
- Scoring script: `paper_prep/validation_A_prime/score_human_A_prime.py`
- Full A-prime manifest rows: 816
- Human package rows with media: 816
- Missing media count: 0
- Missing-media table: `paper_prep/validation_A_prime/A_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv`
- Recovered-media manifest: `paper_prep/validation_A_prime/recovered_media_20260708/A_PRIME_RECOVERED_MEDIA_MANIFEST.csv`
- Regenerated recovered rows used: 100
- Scored status if ratings exist: no real PI/human ratings found; only synthetic test ratings exist.
- Pass/fail if available: not available; A-prime remains not passed.

## B′

- Package status: `B_PRIME_PACKAGE_STATUS = HUMAN_READY_ZERO_MISSING`
- Artifact: `paper_prep/validation_B_prime/B_PRIME_HUMAN_READY_REPORT.md`
- Human package: `paper_prep/validation_B_prime/human_package/`
- Scoring script: `paper_prep/validation_B_prime/score_human_B_prime.py`
- Pair rows: 80
- Ordered rating rows: 160
- Calibration pairs: 24
- Missing media count: 0
- Scored status if ratings exist: no real PI/human ratings found; only synthetic test ratings exist.
- Pass/fail if available: not available; B-prime remains not passed.

## Router

- CV status: `ROUTER_CV_STATUS = COMPLETE`
- Final claim: `ROUTER_FINAL_CLAIM = REDUCED`
- Artifact: `paper_prep/router_replay/ROUTER_REPLAY_CV_REPORT.md`
- Cross-validated threshold policy: 0.970018 expected clean/prompt
- Always-recondition baseline: 0.974455 expected clean/prompt
- Delta vs always-recondition: -0.004437, bootstrap CI [-0.011659, 0.002068]
- Interpretation: router is a reduced/negative offline replay result, not a deployable live-router claim.

## PLAN.md

- Artifact: `paper_prep/PLAN.md`
- READY rows: 9
- REDUCED rows: 6
- REMOVED rows: 0
- BLOCKED rows: 0

Claim rows still unsafe as full-strength positive claims:

- A-prime label validation: REDUCED only; do not say A-prime passed.
- B-prime quality validation: REDUCED only; do not say B-prime passed or human-confirmed.
- CLAP/prompt fidelity: REDUCED only; do not claim semantic preservation is proven.
- Router replay: REDUCED only; present as negative/offline replay if included.
- SA3 / SAO second-model spike: REDUCED only; do not claim full second-backbone robustness.
- Dataset/log release: REDUCED release-engineering appendix only; do not imply all raw audio is released.

## Node utilization

- Node audit: `paper_prep/NODE_SATURATION_AUDIT_20260708.md`
- an12 ADSR-relevant work:
  - SA3 low-step observability proxy, 1,000 generated rows.
  - Demucs scoring for the 1,000 low-step rows.
  - Heartbeat: `paper_prep/heartbeat_an12.log`
- an29 ADSR-relevant work:
  - SA3 full 500-prompt prevalence scan, 4,000 generated rows.
  - Targeted recovery of the initially empty shard 1.
  - Demucs scoring for the 4,000 full rows.
  - Heartbeat: `paper_prep/heartbeat_an29.log`
- Current node state after completion: no ADSR compute jobs active; no idle gap over 30 minutes occurred during this recovery pass.
- Non-ADSR GPU jobs currently occupying an12/an29: none observed at final audit.

## PI decisions needed

- A-prime: provide/authorize PI or human ratings for the 816-row zero-missing package, then run `paper_prep/validation_A_prime/score_human_A_prime.py`.
- B-prime: provide/authorize PI or human ratings for the 80-pair package and 24-pair calibration subset, then run `paper_prep/validation_B_prime/score_human_B_prime.py`.
