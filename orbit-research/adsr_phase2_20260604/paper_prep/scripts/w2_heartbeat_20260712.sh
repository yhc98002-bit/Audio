#!/usr/bin/env bash
set -u

ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
NODE=${1:-$(hostname)}
LOG="$ROOT/paper_prep/heartbeat_${NODE}.log"

while true; do
  {
    printf '\n=== W2 HEARTBEAT %s node=%s ===\n' "$(date --iso-8601=seconds)" "$NODE"
    echo '--- nvidia-smi ---'
    nvidia-smi --query-gpu=index,uuid,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>&1 || true
    echo '--- tmux sessions ---'
    tmux ls 2>&1 || true
    echo '--- ADSR Python processes ---'
    pgrep -af 'w2_|W2_|acestep|ACE-Step|stable_audio|judge_selfhost' 2>&1 || true
    echo '--- W2 ledger line counts ---'
    find "$ROOT/paper_prep/w2_execution_20260712" -type f -name '*.jsonl' -print0 2>/dev/null \
      | xargs -0 -r wc -l 2>&1 | tail -30
    echo '--- current ADSR job status ---'
    if pgrep -af 'w2_|W2_' >/dev/null 2>&1; then
      echo 'ADSR_RELEVANT_PROCESS_ACTIVE'
    else
      echo 'NO_ADSR_RELEVANT_PROCESS_ACTIVE'
    fi
  } >> "$LOG"
  sleep 600
done
