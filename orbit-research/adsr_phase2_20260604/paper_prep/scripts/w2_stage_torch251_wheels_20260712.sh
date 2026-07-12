#!/usr/bin/env bash
set -euo pipefail

ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
ENV_ROOT=${MPRM_ENV_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs}
PYTHON=${AUDIO_PRM_PYTHON:-/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python}
WHEELHOUSE="$ENV_ROOT/w2_torch251_wheelhouse"
TMP_ROOT="$ENV_ROOT/w2_torch251_parallel_tmp"
SERIAL_TMP="$ENV_ROOT/pip_tmp_w2_torch251"
LOG="$ROOT/paper_prep/w2_execution_20260712/spine_reconstruction/logs/torch251_wheel_stage_an29.log"

mkdir -p "$WHEELHOUSE" "$TMP_ROOT" "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1
printf '=== W2 torch251 parallel wheel stage %s ===\n' "$(date --iso-8601=seconds)"

for pattern in \
  'torch-2.5.1+cu121*.whl' \
  'torchaudio-2.5.1+cu121*.whl' \
  'torchvision-0.20.1+cu121*.whl' \
  'nvidia_cufft_cu12-11.0.2.54*.whl' \
  'nvidia_cuda_runtime_cu12-12.1.105*.whl'; do
  source=$(find "$SERIAL_TMP" -type f -name "$pattern" -print -quit 2>/dev/null || true)
  if [ -n "$source" ]; then
    cp -n "$source" "$WHEELHOUSE/"
  fi
done

packages=(
  'nvidia-cuda-nvrtc-cu12==12.1.105'
  'nvidia-cuda-cupti-cu12==12.1.105'
  'nvidia-cudnn-cu12==9.1.0.70'
  'nvidia-cublas-cu12==12.1.3.1'
  'nvidia-curand-cu12==10.3.2.106'
  'nvidia-cusolver-cu12==11.4.5.107'
  'nvidia-cusparse-cu12==12.1.0.106'
  'nvidia-nccl-cu12==2.21.5'
  'nvidia-nvtx-cu12==12.1.105'
  'nvidia-nvjitlink-cu12==12.1.105'
  'triton==3.1.0'
)

download_one() {
  local package=$1
  local token
  token=$(printf '%s' "$package" | tr -cs 'A-Za-z0-9._-' '_')
  mkdir -p "$TMP_ROOT/$token"
  TMPDIR="$TMP_ROOT/$token" "$PYTHON" -m pip download \
    --no-cache-dir \
    --no-deps \
    --index-url https://download.pytorch.org/whl/cu121 \
    --dest "$WHEELHOUSE" \
    "$package"
}
export -f download_one
export PYTHON WHEELHOUSE TMP_ROOT
printf '%s\n' "${packages[@]}" | xargs -P 11 -I{} bash -c 'download_one "$1"' _ {}

mkdir -p "$TMP_ROOT/sympy"
TMPDIR="$TMP_ROOT/sympy" "$PYTHON" -m pip download \
  --no-cache-dir \
  --no-deps \
  --index-url https://pypi.org/simple \
  --dest "$WHEELHOUSE" \
  'sympy==1.13.1'

printf 'WHEELHOUSE_FILES=%s\n' "$(find "$WHEELHOUSE" -maxdepth 1 -type f -name '*.whl' | wc -l)"
sha256sum "$WHEELHOUSE"/*.whl
