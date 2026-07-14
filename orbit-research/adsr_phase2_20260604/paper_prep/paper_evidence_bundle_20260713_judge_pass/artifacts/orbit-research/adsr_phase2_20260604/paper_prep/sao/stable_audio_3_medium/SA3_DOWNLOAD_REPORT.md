# SA3 Medium Download Report

Generated: 2026-07-08

SA3_DOWNLOAD_STATUS = PASS

## Proxy

- Required 3138 proxy test: FAIL on login and an29, connection refused.
- Detected working proxy: `http://127.0.0.1:7890` on login node.
- an29 direct DNS to `modelscope.cn`: FAIL, so download was performed on login and staged locally.

## ModelScope Metadata

- Primary model listed: `stabilityai/stable-audio-3-medium` public model repo.
- Fallbacks listed but not used: `stabilityai/stable-audio-3-medium-base`, `Comfy-Org/stable-audio-3`, `stabilityai/stable-audio-open-1.0`.

## Download

- Command: `modelscope download --repo-type model stabilityai/stable-audio-3-medium --local-dir model_cache/modelscope/stabilityai/stable-audio-3-medium --max-workers 4`
- Local dir: `model_cache/modelscope/stabilityai/stable-audio-3-medium`
- Files downloaded: 17
- Total bytes: 10445315301
- Log: `paper_prep/sao/stable_audio_3_medium/logs/modelscope_download_stable_audio_3_medium_20260708.log`

## Key Files

- `model_cache/modelscope/stabilityai/stable-audio-3-medium/model_config.json`
- `model_cache/modelscope/stabilityai/stable-audio-3-medium/model.safetensors`
- `model_cache/modelscope/stabilityai/stable-audio-3-medium/t5gemma-b-b-ul2/model.safetensors`

Next action: install/verify inference environment and run one-sample smoke on `an29`.
