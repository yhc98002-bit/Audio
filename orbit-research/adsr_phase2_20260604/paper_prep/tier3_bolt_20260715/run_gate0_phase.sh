#!/usr/bin/env bash
set -euo pipefail

ROOT=/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion
PYTHON=${ROOT}_envs/w2-torch251/bin/python
BOLT=paper_prep/tier3_bolt_20260715
NODE=${1:?node}
PHASE=${2:?root, resume, switch, fork_eta, or score_phase}
WORKERS=${3:-8}
if [[ "$(hostname -s)" != "${NODE}" ]]; then
  echo "launcher node mismatch" >&2
  exit 2
fi
cd "${ROOT}"
export TZ=Asia/Shanghai HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export ACE_STEP_CHECKPOINT_DIR=/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B
export BOLT_ACE_STEP_SOURCE=/XYFS01/HOME/paratera_xy/pxy1289/source/ACE-Step
export LAION_CLAP_BERT_DIR=/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/bert-base-uncased
export LAION_CLAP_ROBERTA_DIR=/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/roberta-base
export LAION_CLAP_BART_DIR=/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/facebook--bart-base
export MERT_LOCAL_PATH=/HOME/paratera_xy/pxy1289/source/mert/MERT-v1-95M
export AUDIOBOX_AES_CKPT=/HOME/paratera_xy/pxy1289/source/audiobox_aesthetics/checkpoint.pt
mkdir -p "${BOLT}/gate0_logs"
FREE_GPUS=()
while IFS=',' read -r index memory util; do
  index=${index// /}; memory=${memory// /}; util=${util// /}
  if (( memory <= 1024 && util <= 1 )); then FREE_GPUS+=("${index}"); fi
done < <(nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits)
if (( ${#FREE_GPUS[@]} < WORKERS )); then
  echo "need ${WORKERS} free GPUs; found ${#FREE_GPUS[@]} (${FREE_GPUS[*]-})" >&2
  exit 3
fi

case "${PHASE}" in
  root) base=(root) ;;
  resume|switch) base=(continue --phase "${PHASE}") ;;
  fork_0.025|fork_0.05|fork_0.10)
    eta=${PHASE#fork_}; base=(fork --eta "${eta}" --seed-base 2060000000) ;;
  score_*) base=(score --phase "${PHASE#score_}") ;;
  *) echo "unknown phase ${PHASE}" >&2; exit 2 ;;
esac
pids=()
for ((worker=0; worker<WORKERS; worker++)); do
  gpu=${FREE_GPUS[$worker]}
  CUDA_VISIBLE_DEVICES=${gpu} "${PYTHON}" -u "${BOLT}/bolt_gate0.py" "${base[@]}" \
    --worker-index "${worker}" --num-workers "${WORKERS}" \
    >"${BOLT}/gate0_logs/${NODE}_${PHASE}_w${worker}.stdout.log" \
    2>"${BOLT}/gate0_logs/${NODE}_${PHASE}_w${worker}.stderr.log" &
  pids+=("$!")
done
printf '%s\n' "${pids[@]}" >"${BOLT}/gate0_logs/${NODE}_${PHASE}.pids"
status=0
for pid in "${pids[@]}"; do wait "${pid}" || status=1; done
exit "${status}"
