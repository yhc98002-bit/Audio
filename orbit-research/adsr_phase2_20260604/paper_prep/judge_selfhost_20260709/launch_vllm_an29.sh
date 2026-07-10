#!/usr/bin/env bash
set -euo pipefail

: "${MODEL_PATH:?set MODEL_PATH to the complete local Qwen3-Omni Instruct snapshot}"
ENV_ROOT="${ENV_ROOT:-/dev/shm/adsr_qwen_omni_env}"
TP="${TP:-4}"
PORT="${PORT:-8901}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.80}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"

if [[ ! -f "${MODEL_PATH}/model.safetensors.index.json" ]]; then
  echo "incomplete snapshot: missing ${MODEL_PATH}/model.safetensors.index.json" >&2
  exit 2
fi
if [[ -f "${MODEL_PATH}/STAGING_INCOMPLETE" ]]; then
  echo "incomplete snapshot: staging marker remains in ${MODEL_PATH}" >&2
  exit 2
fi
if find "${MODEL_PATH}" -maxdepth 1 -type f -name '*.incomplete' -print -quit | grep -q .; then
  echo "incomplete snapshot: unfinished weight shards remain in ${MODEL_PATH}" >&2
  exit 2
fi

exec "${ENV_ROOT}/bin/vllm" serve "${MODEL_PATH}" \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --dtype bfloat16 \
  --tensor-parallel-size "${TP}" \
  --max-model-len 32768 \
  --max-num-seqs "${MAX_NUM_SEQS}" \
  --limit-mm-per-prompt '{"audio": 1}' \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --allowed-local-media-path / \
  --served-model-name qwen3-omni-judge
