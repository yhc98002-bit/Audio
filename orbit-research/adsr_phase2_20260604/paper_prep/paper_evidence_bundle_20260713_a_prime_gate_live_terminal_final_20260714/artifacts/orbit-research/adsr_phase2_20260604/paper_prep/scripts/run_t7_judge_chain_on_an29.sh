#!/usr/bin/env bash
set -euo pipefail

ROOT="/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion"
PAPER="${ROOT}/paper_prep"
OUT="${PAPER}/t7_judge_gold_20260713/judge_completion"
GPU_LIST="${1:?pass four comma-separated idle GPU indices}"
MODEL="/dev/shm/ADSR_QWEN3_OMNI_MODELS/Qwen3-Omni-30B-A3B-Instruct"
QWEN_ENV="/dev/shm/adsr_qwen_omni_env"
PORT=8901
SERVER_PID=""
export TZ=Asia/Shanghai

IFS=',' read -r -a GPUS <<<"${GPU_LIST}"
if [[ "${#GPUS[@]}" -ne 4 ]]; then
  echo "judge service requires exactly four GPUs on one node" >&2
  exit 2
fi

mkdir -p "${OUT}"
exec > >(tee -a "${OUT}/JUDGE_CHAIN_STDOUT.log") \
  2> >(tee -a "${OUT}/JUDGE_CHAIN_STDERR.log" >&2)
cd "${ROOT}"

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" || true
    wait "${SERVER_PID}" || true
  fi
}
trap cleanup EXIT

"${QWEN_ENV}/bin/python" - "${GPU_LIST}" <<'PY'
import subprocess, sys
required = {int(value) for value in sys.argv[1].split(',')}
rows = subprocess.check_output([
    'nvidia-smi', '--query-gpu=index,memory.used,utilization.gpu',
    '--format=csv,noheader,nounits'
], text=True).splitlines()
state = {}
for line in rows:
    index, memory, util = (int(value.strip()) for value in line.split(','))
    state[index] = (memory, util)
bad = {index: state[index] for index in required if state[index][0] > 1024 or state[index][1] > 1}
if bad:
    raise SystemExit(f'refusing occupied GPUs: {bad}')
PY

export CUDA_VISIBLE_DEVICES="${GPU_LIST}"
MODEL_PATH="${MODEL}" ENV_ROOT="${QWEN_ENV}" TP=4 PORT="${PORT}" \
  GPU_MEMORY_UTILIZATION=0.80 MAX_NUM_SEQS=1 \
  bash "${PAPER}/judge_selfhost_20260709/launch_vllm_an29.sh" \
  >"${OUT}/T7_VLLM_SERVER_STDOUT.log" 2>"${OUT}/T7_VLLM_SERVER_STDERR.log" &
SERVER_PID=$!
echo "${SERVER_PID}" >"${OUT}/T7_VLLM_SERVER.pid"

ready=0
for _ in $(seq 1 120); do
  if curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/health" >/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "vLLM exited before health PASS" >&2
    exit 3
  fi
  sleep 10
done
if [[ "${ready}" -ne 1 ]]; then
  echo "vLLM health timeout" >&2
  exit 4
fi

source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
python "${PAPER}/scripts/complete_t7_judge_aprime_20260713.py" pending \
  --manifest "${PAPER}/t7_judge_gold_20260713/ratings_ingest/T7_ALL_DISJOINT_GOLD_MANIFEST.csv" \
  --raw "${OUT}/T7_JUDGE_RAW_RESPONSES.jsonl" \
  --output "${OUT}/T7_JUDGE_PENDING_MANIFEST.csv" \
  >"${OUT}/T7_PENDING_AUDIT.json"
T7_PENDING=$(python -c "import json; print(json.load(open('${OUT}/T7_PENDING_AUDIT.json'))['pending_rows'])")
if [[ "${T7_PENDING}" -gt 0 ]]; then
  "${QWEN_ENV}/bin/python" "${PAPER}/scripts/run_selfhost_audio_judge.py" \
    --manifest "${OUT}/T7_JUDGE_PENDING_MANIFEST.csv" \
    --endpoint "http://127.0.0.1:${PORT}" \
    --raw-output "${OUT}/T7_JUDGE_RAW_RESPONSES.jsonl" \
    --summary-output "${OUT}/T7_JUDGE_RUN_SUMMARY.json" \
    --calls-per-clip 3
fi
python "${PAPER}/scripts/complete_t7_judge_aprime_20260713.py" evaluate-validation \
  >"${OUT}/POOLED_JUDGE_VALIDATION_STDOUT.json"
VALIDATION=$(python -c "import json; print(json.load(open('${OUT}/POOLED_JUDGE_VALIDATION.json'))['JUDGE_VALIDATION_STATUS'])")
if [[ "${VALIDATION}" != "PASS" ]]; then
  echo "judge validation terminal status: ${VALIDATION}; stratified-500 not launched"
  python "${PAPER}/scripts/complete_t7_judge_aprime_20260713.py" finalize-core-only \
    >"${OUT}/A_PRIME_CORE_ONLY_STDOUT.json"
  date -Iseconds >"${OUT}/JUDGE_CHAIN_COMPLETED_AT.txt"
  if [[ ! -e "${PAPER}/paper_evidence_bundle_20260713_judge_fail" ]]; then
    python "${PAPER}/scripts/build_t7_evidence_bundle_20260713.py" --label judge_fail \
      >"${OUT}/JUDGE_FAIL_EVIDENCE_BUNDLE_BUILD.json"
  fi
  exit 0
fi

python "${PAPER}/scripts/complete_t7_judge_aprime_20260713.py" pending \
  --manifest "${OUT}/A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv" \
  --raw "${OUT}/A_PRIME_STRATIFIED_500_RAW_RESPONSES.jsonl" \
  --output "${OUT}/A_PRIME_STRATIFIED_500_PENDING_MANIFEST.csv" \
  >"${OUT}/A_PRIME_STRATIFIED_500_PENDING_AUDIT.json"
GLOBAL_PENDING=$(python -c "import json; print(json.load(open('${OUT}/A_PRIME_STRATIFIED_500_PENDING_AUDIT.json'))['pending_rows'])")
if [[ "${GLOBAL_PENDING}" -gt 0 ]]; then
  "${QWEN_ENV}/bin/python" "${PAPER}/scripts/run_selfhost_audio_judge.py" \
    --manifest "${OUT}/A_PRIME_STRATIFIED_500_PENDING_MANIFEST.csv" \
    --endpoint "http://127.0.0.1:${PORT}" \
    --raw-output "${OUT}/A_PRIME_STRATIFIED_500_RAW_RESPONSES.jsonl" \
    --summary-output "${OUT}/A_PRIME_STRATIFIED_500_RUN_SUMMARY.json" \
    --calls-per-clip 3 --infrastructure-only
fi
python "${PAPER}/scripts/complete_t7_judge_aprime_20260713.py" finalize-500 \
  >"${OUT}/A_PRIME_FINALIZE_STDOUT.json"
date -Iseconds >"${OUT}/JUDGE_CHAIN_COMPLETED_AT.txt"
if [[ ! -e "${PAPER}/paper_evidence_bundle_20260713_judge_pass" ]]; then
  python "${PAPER}/scripts/build_t7_evidence_bundle_20260713.py" --label judge_pass \
    >"${OUT}/JUDGE_PASS_EVIDENCE_BUNDLE_BUILD.json"
fi
