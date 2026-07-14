# SA3 Medium Environment Report

Generated: 2026-07-08

SA3_ENV_STATUS = PASS

## Environment Strategy

- Primary package path attempted first: official `stable-audio-3` from GitHub.
- Installed into the existing `audio-prm` conda environment because the PI directive authorized dependency mutation to unblock SA3 execution.
- Model weights were not fetched from Hugging Face. The model snapshot is the ModelScope download at:
  `model_cache/modelscope/stabilityai/stable-audio-3-medium/`.

## Install Command

```bash
python -m pip install 'git+https://github.com/Stability-AI/stable-audio-3.git'
```

Install log:
`paper_prep/sao/stable_audio_3_medium/logs/stable_audio_3_github_install_20260708.log`

## Runtime Versions After Install

- Python: 3.10.20 in `audio-prm`
- `stable-audio-3`: git commit `8a3ded325ec6082113dbce11620b7b25b31ce6b0`
- `torch`: 2.7.1+cu126
- `torchaudio`: 2.7.1+cu126
- `transformers`: 5.13.0
- `safetensors`: 0.8.0
- `torchvision`: 0.22.1 after runtime repair
- `huggingface_hub`: 1.22.0
- CUDA visibility on `an12`: PASS, 8 x NVIDIA A800 80GB PCIe
- CUDA visibility on `an29`: PASS, 8 x NVIDIA A800 80GB PCIe

## Dependency Diff / Conflicts

The official package install replaced the previous torch/CUDA stack and reports
these conflicts:

- `ace-step 0.2.0` expects `transformers==4.50.0`; installed version is 5.13.0.
- `torchvision 0.20.1` expects `torch==2.5.1`; installed version is 2.7.1.
- `stable-audio-tools 0.0.20` still lacks optional runtime dependencies including `torchsde`.
- `laion-clap 1.1.7` expects `numpy<2.0.0`; current environment has numpy 2.2.6.

This mutation is recorded because it may affect future ACE-Step/CLAP work in the
same conda environment. It does not affect frozen ADSR evidence files.

Runtime repair after first smoke attempt:

- First SA3 smoke failed because `transformers.T5GemmaEncoderModel` could not
  import.
- Probe showed `transformers.models.t5gemma.modeling_t5gemma` failed due the
  stale `torchvision 0.20.1` / `torch 2.7.1` mismatch.
- Command run: `python -m pip install torchvision==0.22.1`.
- Post-repair T5Gemma probe passed on `an29`.

## Import / CUDA Probe

Probe script:
`paper_prep/scripts/check_sa3_env.py`

Results:

- `stable_audio_3`: imports on `an12` and `an29`.
- `stable_audio_tools`: imports, but generation submodules requiring `torchsde`
  are not reliable.
- CUDA: available on both `an12` and `an29`.
- `flash_attn`: absent; package disables Flash Attention and continues.

## Inference Path Chosen

The smoke run uses:

- local ModelScope `model_config.json`;
- local ModelScope `model.safetensors`;
- local ModelScope `t5gemma-b-b-ul2/`;
- `stable_audio_3.loading_utils.load_diffusion_cond`;
- `stable_audio_3.model.StableAudioModel.generate`.

The smoke script patches the prompt conditioner from repo/subfolder loading to
`model_path=model_cache/modelscope/stabilityai/stable-audio-3-medium/t5gemma-b-b-ul2`
so generation does not depend on Hugging Face.

Next action: run one-sample SA3 smoke on a GPU node and record pass/fail with
exact traceback if needed.
