# SA3 Medium Smoke Report

Generated: 2026-07-08

SA3_SMOKE_STATUS = PASS

## Inputs

- Model snapshot:
  `model_cache/modelscope/stabilityai/stable-audio-3-medium/`
- Config:
  `model_cache/modelscope/stabilityai/stable-audio-3-medium/model_config.json`
- Checkpoint:
  `model_cache/modelscope/stabilityai/stable-audio-3-medium/model.safetensors`
- Text conditioner:
  `model_cache/modelscope/stabilityai/stable-audio-3-medium/t5gemma-b-b-ul2/`
- Script:
  `paper_prep/sao/stable_audio_3_medium/run_sa3_smoke_local.py`

## Prompt

```text
30-second instrumental electronic track, no vocals, no speech, clean mix, steady beat, melodic synthesizer, high quality.
```

## Attempts

1. `an29`, 8 seconds, 4 steps, fp16:
   - Status: FAIL.
   - Cause: `T5GemmaEncoderModel` import failed.
   - Exact upstream cause: `torchvision 0.20.1` was incompatible with the newly
     installed `torch 2.7.1`.
   - Ledger/log:
     `paper_prep/sao/stable_audio_3_medium/smoke/SA3_SMOKE_LEDGER.jsonl`,
     `paper_prep/sao/stable_audio_3_medium/logs/sa3_smoke_an29_seed20260708_8s_steps4.log`.

2. Runtime repair:
   - Command: `python -m pip install torchvision==0.22.1`
   - Log:
     `paper_prep/sao/stable_audio_3_medium/logs/torchvision_0221_install_20260708.log`
   - T5Gemma probe after repair: PASS.

3. `an29`, 8 seconds, 4 steps, fp16 retry:
   - Status: PASS.
   - Log:
     `paper_prep/sao/stable_audio_3_medium/logs/sa3_smoke_an29_seed20260708_8s_steps4_retry_t5fixed.log`

## Passing Output

- Audio:
  `paper_prep/sao/stable_audio_3_medium/smoke/audio/sa3_smoke_seed20260708_dur8s.wav`
- Ledger:
  `paper_prep/sao/stable_audio_3_medium/smoke/SA3_SMOKE_LEDGER.jsonl`
- Host: `an29`
- GPU: NVIDIA A800 80GB PCIe
- Sample rate: 44,100 Hz
- Channels: 2
- Duration: 8.0 seconds
- RMS: 0.18998421728610992
- Max CUDA memory allocated: 9,226,021,888 bytes
- Elapsed wall time: 200.38 seconds

## Acceptance Criteria

- Model loads: PASS.
- Output generated: PASS.
- Output duration > 5 seconds: PASS.
- File decodable by `soundfile`: PASS.
- Non-silent RMS: PASS.
- Sample rate recorded: PASS.
- GPU used: PASS.
- Ledger row written: PASS.

Next action: run a SA3 prevalence pilot when enough ADSR GPU time is available.
The smoke alone does not support a second-backbone robustness claim.
