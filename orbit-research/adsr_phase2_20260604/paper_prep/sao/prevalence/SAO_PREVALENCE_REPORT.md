# SAO Prevalence Report

Generated: 2026-07-07

SAO_PREVALENCE_STATUS = NOT_RUN_SMOKE_FAILED

## Why This Stage Did Not Run

The Stable Audio Open package path was repaired enough for imports:

- Direct install log: `paper_prep/sao/logs/audio_prm_direct_sao_install_20260707.log`
- Package diff: `paper_prep/sao/logs/audio_prm_pip_freeze_before_sao_20260707.txt` to
  `paper_prep/sao/logs/audio_prm_pip_freeze_after_sao_20260707.txt`
- Diff result: only `stable-audio-tools==0.0.20` was added to `audio-prm`.

The one-sample smoke failed before generation because model files were unavailable:

- Smoke ledger: `paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl`
- Smoke report: `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`
- an29 smoke log: `paper_prep/sao/smoke/sao_smoke_an29_20260708T052823.log`

Login-node prefetch also failed because `stabilityai/stable-audio-open-1.0` is
gated and requires authenticated Hugging Face access:

- Prefetch log: `paper_prep/sao/logs/sao_hf_prefetch_20260707.log`

## Consequence

No SAO audio was generated. No prevalence, best-of-N, or categorical-failure
rate can be claimed for SAO.

Required next action: provide an authenticated Hugging Face token with access to
`stabilityai/stable-audio-open-1.0`, prefetch the model to shared cache, then
rerun `paper_prep/sao/run_sao_smoke.sh` before launching prevalence.
