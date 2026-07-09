# SAO Observability Report

Generated: 2026-07-07

SAO_OBSERVABILITY_STATUS = NOT_RUN_SMOKE_FAILED

The SAO observability curve was not run because the one-sample SAO model-load
smoke failed before generation:

- `paper_prep/sao/smoke/SAO_SMOKE_REPORT.md`
- `paper_prep/sao/smoke/SAO_SMOKE_LEDGER.jsonl`
- `paper_prep/sao/logs/sao_hf_prefetch_20260707.log`

The blocker is model access/cache availability, not the prior
`stable_audio_tools` package absence. `stable-audio-tools==0.0.20` is now
installed in `audio-prm` with no Torch/torchaudio/CUDA package changes.

No SAO early-checkpoint observability claim is supported.
