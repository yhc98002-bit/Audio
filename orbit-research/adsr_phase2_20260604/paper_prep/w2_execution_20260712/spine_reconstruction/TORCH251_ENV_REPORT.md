# W2 torch-2.5.1 Isolated Environment

`TORCH251_ENV_STATUS = PASS`

## Runtime

- Environment: `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/w2-torch251`
- Python: 3.10.20.
- torch: 2.5.1+cu121.
- torchaudio: 2.5.1+cu121.
- torchvision: 0.20.1+cu121.
- CUDA build: 12.1.
- CUDA availability: PASS on an29 A800.
- Shared `audio-prm`: unchanged at torch/torchaudio 2.7.1+cu126.

## Recovery History

1. The first network install failed at 234.4/780.4 MiB because an29 `/tmp` had only 446 MiB free. The incomplete venv is preserved as `w2-torch251_failed_20260712_nospace`.
2. The serial retry used an XYFS02 temp directory. Completed torch, torchaudio, torchvision, cufft, runtime, and cudnn wheels were preserved before the serial resolver was stopped. Its incomplete venv is preserved as `w2-torch251_serial_cancelled_parallel_stage`.
3. Eleven exact CUDA 12.1 dependencies were staged concurrently through port 3138. The final wheelhouse has 17 checksum-frozen wheels.
4. Offline installation succeeded. CUDA verification initially exposed a missing local `libnvJitLink.so.12` because pip reused shared metadata; forced local installation of `nvidia-nvjitlink-cu12==12.1.105` resolved it.

## Evidence

- Install log: `spine_reconstruction/logs/torch251_env_install_an29.log`.
- Wheel-stage log: `spine_reconstruction/logs/torch251_wheel_stage_an29.log`.
- Package freeze: `spine_reconstruction/TORCH251_ENV_FREEZE.txt`.
- Wheel checksums: `spine_reconstruction/TORCH251_WHEEL_SHA256SUMS`.
- Installer: `paper_prep/scripts/w2_install_torch251_env_20260712.sh`.
- Stager: `paper_prep/scripts/w2_stage_torch251_wheels_20260712.sh`.

Environment PASS authorizes only the preregistered 51-row fidelity probe. It does not authorize a full spine replay by itself.
