# ACE-Step v1.5 Gate-0 Environment

ENVIRONMENT_STATUS = PASS

- Node: `an29`; physical placement command selected an29 GPU 0; TP1; one replica for bounded calibration.
- GPU: `NVIDIA A800 80GB PCIe`, capability `[8, 0]`, memory `85174583296` bytes.
- Python: `3.10.20 (main, Mar 11 2026, 17:46:40) [GCC 14.3.0]`.
- torch: `2.7.1+cu126`; CUDA runtime `12.6`; cuDNN `90501`.
- transformers: `5.13.0`; torchaudio: `2.7.1`; diffusers: `0.38.0`.
- Dtype: `torch.bfloat16`; attention: `sdpa`.
- Source: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/ACE-Step-1.5`; exact runtime code hashes are in `V15_TERMINAL_DIAGNOSIS.json`.

The initial wrong cache resolution stopped before model load. The repaired offline initializer loaded the exact local non-Turbo XL-SFT, VAE, and Qwen encoder without compute-node acquisition.
