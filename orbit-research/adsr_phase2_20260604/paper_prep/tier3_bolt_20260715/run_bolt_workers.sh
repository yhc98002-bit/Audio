#!/usr/bin/env bash
set -euo pipefail

ROOT=/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion
PYTHON=${ROOT}_envs/w2-torch251/bin/python
BOLT=paper_prep/tier3_bolt_20260715
NODE=${1:?node must be an12 or an29}
START=${2:?prompt-slot start}
END=${3:?prompt-slot end}
WORKERS=${4:-8}
if [[ "$(hostname -s)" != "${NODE}" ]]; then
  echo "launcher node mismatch: expected ${NODE}, got $(hostname -s)" >&2
  exit 2
fi
if [[ "${WORKERS}" -lt 1 || "${WORKERS}" -gt 8 ]]; then
  echo "worker count must be 1..8" >&2
  exit 2
fi
cd "${ROOT}"
export TZ=Asia/Shanghai
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export ACE_STEP_CHECKPOINT_DIR=/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B
export BOLT_ACE_STEP_SOURCE=/XYFS01/HOME/paratera_xy/pxy1289/source/ACE-Step
export LAION_CLAP_BERT_DIR=/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/bert-base-uncased
export LAION_CLAP_ROBERTA_DIR=/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/roberta-base
export LAION_CLAP_BART_DIR=/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/facebook--bart-base
export MERT_LOCAL_PATH=/HOME/paratera_xy/pxy1289/source/mert/MERT-v1-95M
export AUDIOBOX_AES_CKPT=/HOME/paratera_xy/pxy1289/source/audiobox_aesthetics/checkpoint.pt

mkdir -p "${BOLT}/pilot_logs"
mapfile -t GPU_ROWS < <(nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits)
FREE_GPUS=()
for row in "${GPU_ROWS[@]}"; do
  IFS=',' read -r index memory util <<<"${row}"
  index=${index// /}; memory=${memory// /}; util=${util// /}
  if (( memory <= 1024 && util <= 1 )); then
    FREE_GPUS+=("${index}")
  fi
done
if (( ${#FREE_GPUS[@]} < WORKERS )); then
  echo "need ${WORKERS} free GPUs; found ${#FREE_GPUS[@]} (${FREE_GPUS[*]-})" >&2
  exit 3
fi

pids=()
for ((worker=0; worker<WORKERS; worker++)); do
  gpu=${FREE_GPUS[$worker]}
  CUDA_VISIBLE_DEVICES=${gpu} "${PYTHON}" -u "${BOLT}/bolt_pilot_worker.py" \
    --worker-index "${worker}" --num-workers "${WORKERS}" \
    --prompt-slot-start "${START}" --prompt-slot-end "${END}" \
    >"${BOLT}/pilot_logs/${NODE}_w${worker}.stdout.log" \
    2>"${BOLT}/pilot_logs/${NODE}_w${worker}.stderr.log" &
  pids+=("$!")
done
printf '%s\n' "${pids[@]}" >"${BOLT}/pilot_logs/${NODE}.pids"
status=0
for pid in "${pids[@]}"; do
  wait "${pid}" || status=1
done
exit "${status}"
