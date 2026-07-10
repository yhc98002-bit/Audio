# ACE-Step 1.5 Environment And Model Provenance

`V15_ENV_STATUS = PASS`

## Official Source

- Repository: `https://github.com/ace-step/ACE-Step-1.5`
- Source commit: `6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0`
- Commit evidence: official GitHub `commits/main.atom` feed.
- Commit archive SHA256:
  `fc563d1e5c2f17733668692d2ff1a4507e44c903857b11e22108233fb3636b12`
- Initially downloaded `main` archive SHA256:
  `0ae70ce05fa38da7a73fdc75cc548acca072eca09ad2e08baff83a76259a4e17`
- Verification: both archives contain 1,217 files and have identical
  path-normalized file-content SHA256 maps (zero changed files).
- External source path:
  `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/ACE-Step-1.5`
- Declared package version: `ace-step==1.5.0`.

## Network Route

- `http://127.0.0.1:3138`: connection refused.
- `socks5h://127.0.0.1:3138`: connection refused.
- Active login-node route: `http://127.0.0.1:7890`.
- ModelScope check through active route: HTTP 200 on 2026-07-09.
- Decision: use the working login-node proxy for ModelScope. Do not silently
  switch the model download to Hugging Face.

## Environment Resolution

- The official source `.venv` was created with `uv sync --frozen --no-dev
  --python 3.11`; the complete log is `logs/uv_sync.log`.
- Importing its NFS-hosted PyTorch stack was operationally too slow for the
  bounded run. It was not used to generate reported rows.
- The selected runtime was the existing `audio-prm` environment plus an
  isolated target overlay; the shared environment itself was not modified.
- Python: 3.10.20.
- PyTorch/torchaudio: 2.7.1 / 2.7.1, CUDA 12.6.
- Transformers: 5.13.0; soundfile: 0.13.1.
- Overlay: `vector-quantize-pytorch==1.27.20`, `einx==0.3.0`,
  `pytorch-wavelets==1.3.0`, `PyWavelets==1.8.0`, and
  `frozendict==2.4.7`.
- Overlay path:
  `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/ACE-Step-1.5/py310-overlay`.
- Exact compatibility changes are frozen in `V15_COMPATIBILITY_PATCH.diff`.

Transformers 5 constructs the remote model under a meta-device context. Two
configuration-only tensor scalar reads in `vector-quantize-pytorch` were
replaced with equivalent Python checks/products. The official loader was also
made explicit with `low_cpu_mem_usage=False`. These changes do not alter model
weights, sampling equations, seeds, or detector logic.

## Checkpoint

- ModelScope repository: `ACE-Step/Ace-Step1.5`.
- Checkpoint root:
  `/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/model_cache/ACE-Step1.5`
- Primary DiT: `acestep-v15-turbo`.
- Model file hashes are frozen in `V15_MODEL_CHECKSUMS.tsv`.
- A node-local copy used for the final intervention was verified against all
  four frozen model hashes before generation.

## Runtime Outcome

- Engineering smoke: PASS, 2/2 generated, decoded, non-silent, and scored.
- Reported runtime hosts: `an12` and `an29`, NVIDIA A800 80 GB PCIe.
- Official inference settings: ODE, 8 steps, shift 3.0, bfloat16, no LM
  thinking, batch size 1.
- Node-local `/dev/shm` was used for completed audio export before atomic copy
  to evidence storage. This avoids incomplete FLAC headers on Lustre and does
  not alter waveform bytes.
- Raw ledgers preserve path/export, quota, and NaN-initialization failures.
  The final audit requires exactly one successful row per frozen key.
