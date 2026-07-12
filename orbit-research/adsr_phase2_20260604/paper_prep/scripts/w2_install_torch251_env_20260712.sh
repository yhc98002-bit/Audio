#!/usr/bin/env bash
set -euo pipefail

ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
ENV_ROOT=${MPRM_ENV_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs}
BASE_PYTHON=${AUDIO_PRM_PYTHON:-/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python}
TARGET="$ENV_ROOT/w2-torch251"
TMP="$ENV_ROOT/pip_tmp_w2_torch251"
LOG="$ROOT/paper_prep/w2_execution_20260712/spine_reconstruction/logs/torch251_env_install_an29.log"

mkdir -p "$TMP" "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

printf '\n=== RETRY_WITH_XYFS02_TMP %s ===\n' "$(date --iso-8601=seconds)"
if [ -e "$TARGET" ]; then
  echo "target environment already exists: $TARGET" >&2
  exit 2
fi

export http_proxy=${http_proxy:-http://127.0.0.1:3138}
export https_proxy=${https_proxy:-http://127.0.0.1:3138}
export HTTP_PROXY=${HTTP_PROXY:-$http_proxy}
export HTTPS_PROXY=${HTTPS_PROXY:-$https_proxy}
export TMPDIR="$TMP"
export PIP_NO_CACHE_DIR=1

"$BASE_PYTHON" -m venv --system-site-packages "$TARGET"
"$TARGET/bin/python" -m pip install \
  --no-cache-dir \
  --index-url https://download.pytorch.org/whl/cu121 \
  torch==2.5.1+cu121 \
  torchaudio==2.5.1+cu121 \
  torchvision==0.20.1+cu121

"$TARGET/bin/python" - <<'PY'
import torch
import torchaudio
import torchvision

assert torch.__version__ == "2.5.1+cu121", torch.__version__
assert torchaudio.__version__ == "2.5.1+cu121", torchaudio.__version__
assert torchvision.__version__ == "0.20.1+cu121", torchvision.__version__
assert torch.cuda.is_available()
print(
    "W2_TORCH251_ENV_PASS",
    torch.__version__,
    torchaudio.__version__,
    torchvision.__version__,
    torch.version.cuda,
    torch.cuda.get_device_name(0),
)
PY
