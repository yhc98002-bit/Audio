#!/usr/bin/env bash
set -euo pipefail

ROOT="/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion"
PAPER="${ROOT}/paper_prep"
OUT="${PAPER}/w2_execution_20260712/live_confirmation_20260713"
GPU_LIST="${1:?pass four comma-separated idle GPU indices}"
export TZ=Asia/Shanghai
IFS=',' read -r -a GPUS <<<"${GPU_LIST}"
if [[ "${#GPUS[@]}" -ne 4 ]]; then
  echo "frozen live launcher requires exactly four GPUs on one node" >&2
  exit 2
fi
mkdir -p "${OUT}/logs"
cd "${ROOT}"

python - "${GPU_LIST}" <<'PY'
import subprocess, sys
required = {int(value) for value in sys.argv[1].split(',')}
rows = subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader,nounits'], text=True).splitlines()
state = {int(a.strip()):(int(b.strip()),int(c.strip())) for a,b,c in (line.split(',') for line in rows)}
bad = {index:state[index] for index in required if state[index][0] > 1024 or state[index][1] > 1}
if bad: raise SystemExit(f'refusing occupied GPUs: {bad}')
PY

source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
POLICY_SHA=$(sha256sum paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_POLICY_FREEZE.json | awk '{print $1}')
MPRM_W2_EVPD_OUT=paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery \
python paper_prep/scripts/w2_evpd_liveconfirm_20260712.py launch-guard \
  --amendment paper_prep/W2_AMENDMENT_20260712.md \
  --promotion-record paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json \
  --policy-sha256 "${POLICY_SHA}" >"${OUT}/LIVE_LAUNCH_GUARD.json"

date -Iseconds >"${OUT}/ACTUAL_LAUNCH_TIMESTAMP.txt"
date -d '+48 hours' -Iseconds >"${OUT}/HARD_STOP_DEADLINE.txt"
pids=()
for worker in 0 1 2 3; do
  CUDA_VISIBLE_DEVICES="${GPUS[$worker]}" \
  python paper_prep/scripts/w2_liveconfirm_worker_20260713.py \
    --worker-index "${worker}" --num-workers 4 \
    >"${OUT}/logs/worker_${worker}.stdout.log" \
    2>"${OUT}/logs/worker_${worker}.stderr.log" &
  pids+=("$!")
done

deadline=$(( $(date +%s) + 48*60*60 ))
status=0
while ((${#pids[@]})); do
  remaining=()
  for pid in "${pids[@]}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      remaining+=("${pid}")
    else
      wait "${pid}" || status=1
    fi
  done
  pids=("${remaining[@]}")
  if (( $(date +%s) >= deadline )) && ((${#pids[@]})); then
    printf '%s\n' "${pids[@]}" >"${OUT}/CAP_MISS_RUNNING_PIDS.txt"
    kill "${pids[@]}" 2>/dev/null || true
    for pid in "${pids[@]}"; do wait "${pid}" 2>/dev/null || true; done
    echo "LIVE_CONFIRM_STATUS = CAP_MISS" >"${OUT}/LIVE_CONFIRM_TERMINAL_STATUS.txt"
    exit 124
  fi
  ((${#pids[@]})) && sleep 30
done
if [[ "${status}" -ne 0 ]]; then
  echo "LIVE_CONFIRM_STATUS = WORKER_FAIL" >"${OUT}/LIVE_CONFIRM_TERMINAL_STATUS.txt"
  exit 1
fi
echo "LIVE_CONFIRM_STATUS = GENERATION_COMPLETE_ANALYSIS_PENDING" >"${OUT}/LIVE_CONFIRM_TERMINAL_STATUS.txt"
date -Iseconds >"${OUT}/GENERATION_COMPLETED_TIMESTAMP.txt"
