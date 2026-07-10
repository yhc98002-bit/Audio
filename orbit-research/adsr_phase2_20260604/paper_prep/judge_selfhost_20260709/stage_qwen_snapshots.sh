#!/usr/bin/env bash
set -euo pipefail

MODEL_CACHE_ROOT="${MODEL_CACHE_ROOT:-/tmp/ADSR_QUOTA_QUARANTINE_20260710/model_cache}"
REMOTE_ROOT="${REMOTE_ROOT:-/dev/shm/ADSR_QWEN3_OMNI_MODELS}"
CONDA_SH="${CONDA_SH:-/APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh}"
LOG_ROOT="${LOG_ROOT:-$(cd "$(dirname "$0")/logs" && pwd)}"
INSTRUCT="Qwen3-Omni-30B-A3B-Instruct"
CAPTIONER="Qwen3-Omni-30B-A3B-Captioner"

stage_snapshot() {
  local name="$1"
  local source="${MODEL_CACHE_ROOT}/${name}"
  local remote="${REMOTE_ROOT}/${name}"
  local log="${LOG_ROOT}/${name}_complete_transfer_an29.log"

  ssh an29 "set -euo pipefail; mkdir -p '$remote'; touch '$remote/STAGING_INCOMPLETE'; for partial in '$remote'/*.incomplete; do [[ -e \"\$partial\" ]] || continue; final=\"\${partial%.incomplete}\"; if [[ -e \"\$final\" ]]; then mv \"\$partial\" \"\${partial}.preserved\"; else mv \"\$partial\" \"\$final\"; fi; done"
  rsync -a --partial --append-verify --info=progress2 "${source}/" "an29:${remote}/" >"${log}" 2>&1
  ssh an29 "set -euo pipefail; test -f '$remote/model.safetensors.index.json'; ! find '$remote' -maxdepth 1 -type f -name '*.incomplete' -print -quit | grep -q .; mv '$remote/STAGING_INCOMPLETE' '$remote/STAGING_COMPLETE'"
}

while tmux has-session -t adsr_qwen_instruct_download_login_retry 2>/dev/null; do
  sleep 20
done
grep -q 'DOWNLOAD_EXIT=0' "${LOG_ROOT}/modelscope_instruct_download_retry_login.log"
stage_snapshot "${INSTRUCT}"

source "${CONDA_SH}"
conda activate audio-prm
export HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7890}"
export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7890}"
export http_proxy="${http_proxy:-${HTTP_PROXY}}"
export https_proxy="${https_proxy:-${HTTPS_PROXY}}"
modelscope download "Qwen/${CAPTIONER}" \
  --local-dir "${MODEL_CACHE_ROOT}/${CAPTIONER}" \
  --max-workers 4 >"${LOG_ROOT}/modelscope_captioner_download_retry_login.log" 2>&1
printf '\nDOWNLOAD_EXIT=0\n' >>"${LOG_ROOT}/modelscope_captioner_download_retry_login.log"
stage_snapshot "${CAPTIONER}"
printf 'ORCHESTRATION_EXIT=0\n' >"${LOG_ROOT}/model_stage_orchestration.status"
