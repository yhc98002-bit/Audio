#!/usr/bin/env bash
set -u

ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
NODE=${1:-$(hostname)}
LOG="$ROOT/paper_prep/heartbeat_${NODE}.log"

while true; do
  adsr_python_processes=$(
    ps -eo pid=,args= \
      | awk -v root="$ROOT" '
          index($0, root) &&
          $0 ~ /\/python([0-9.]*)? / &&
          $0 ~ /paper_prep\/scripts\/w2_[^ ]*\.py/ {
            print
          }
        '
  )
  {
    printf '\n=== W2 HEARTBEAT %s node=%s ===\n' "$(date --iso-8601=seconds)" "$NODE"
    echo '--- nvidia-smi ---'
    nvidia-smi --query-gpu=index,uuid,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>&1 || true
    echo '--- tmux sessions ---'
    tmux ls 2>&1 || true
    echo '--- ADSR Python processes ---'
    if [ -n "$adsr_python_processes" ]; then
      printf '%s\n' "$adsr_python_processes"
    else
      echo 'NONE'
    fi
    echo '--- W2 ledger line counts ---'
    find "$ROOT/paper_prep/w2_execution_20260712" -type f -name '*.jsonl' -print0 2>/dev/null \
      | xargs -0 -r wc -l 2>&1 | tail -30
    echo '--- current ADSR job status ---'
    if [ -n "$adsr_python_processes" ]; then
      echo 'ADSR_RELEVANT_PROCESS_ACTIVE'
    else
      echo 'NO_ADSR_RELEVANT_PROCESS_ACTIVE'
    fi
  } >> "$LOG"
  if [ "${MPRM_HEARTBEAT_ONCE:-0}" = "1" ]; then
    break
  fi
  sleep 600
done
