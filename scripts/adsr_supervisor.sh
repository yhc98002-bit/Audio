#!/usr/bin/env bash
# Supervisor for the ADSR resume run. Self-heals the configured worker node (default an12 for
# the current allocation), periodically clears leaked temp WAVs (/tmp + scratch), and exits
# (=> notifies the agent) on completion or loss of that allocation.
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
PYBIN=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
cd "$REPO" || exit 9
HB=orbit-research/adsr_resume_coord/heartbeats
AI_JOB="${1:-96931}"; AI_NODE="${2:-an12}"
is_int(){ case "$1" in (''|*[!0-9]*) return 1;; (*) return 0;; esac; }
remaining(){ $PYBIN scripts/build_resume_manifest.py --dry-run 2>/dev/null | $PYBIN -c "import sys,json;print(json.load(sys.stdin)['remaining_candidate_gens'])" 2>/dev/null; }
echo "SUPERVISOR_START ai=$AI_JOB/$AI_NODE $(date -u +%FT%TZ)"
loop=0; last_relaunch=0; prevrem=-1; stall=0
while :; do
  loop=$((loop+1))
  REM=$(remaining)
  if is_int "$REM" && [ "$REM" -eq 0 ]; then echo "EVENT=generation_complete $(date -u +%FT%TZ)"; break; fi
  AIST=$(squeue -j "$AI_JOB" -h -o "%T" 2>/dev/null)
  if [ -n "$AIST" ] && [ "$AIST" != "RUNNING" ]; then echo "EVENT=${AI_NODE}_alloc_lost state=$AIST remaining=$REM $(date -u +%FT%TZ)"; break; fi
  if [ -z "$AIST" ]; then echo "EVENT=${AI_NODE}_alloc_gone remaining=$REM $(date -u +%FT%TZ)"; break; fi

  # self-heal: if the allocation is RUNNING but no fresh worker heartbeat (>240s), relaunch it
  NOW=$(date +%s); fresh_node=0
  for f in "$HB"/ssh_${AI_NODE}_* "$HB"/*_${AI_NODE}_*; do
    [ -e "$f" ] || continue
    m=$(stat -c %Y "$f" 2>/dev/null||echo 0); [ $((NOW-m)) -le 240 ] && fresh_node=1
  done
  if [ "$fresh_node" -eq 0 ] && [ $((NOW-last_relaunch)) -ge 300 ]; then
    echo "{\"event\":\"auto_relaunch_${AI_NODE}\",\"ts\":\"$(date -u +%FT%TZ)\"}"
    timeout 20 ssh -o StrictHostKeyChecking=no "$AI_NODE" "cd $REPO && setsid bash scripts/adsr_gpu_worker.sh forward </dev/null >runs/adsr_recollect_resume/logs/launch_${AI_NODE}_auto.out 2>&1 &" </dev/null >/dev/null 2>&1
    last_relaunch=$NOW
  fi

  # periodic temp cleanup (every ~8 loops ≈ 12 min): leaked WAVs on each running node's /tmp + scratch
  if [ $((loop % 8)) -eq 0 ]; then
    for n in $(squeue -u "$(whoami)" -h -t RUNNING -o "%N" 2>/dev/null | tr ',' '\n' | grep -E '^an[0-9]+' | sort -u); do
      timeout 20 ssh "$n" 'find /tmp -maxdepth 1 -name "tmp*" -mmin +6 -delete 2>/dev/null' </dev/null >/dev/null 2>&1
    done
    find runs/adsr_recollect_resume/tmpscratch -name 'tmp*' -mmin +6 -delete 2>/dev/null
  fi

  if is_int "$REM"; then
    if [ "$REM" -eq "$prevrem" ]; then stall=$((stall+1)); else stall=0; prevrem=$REM; fi
  fi
  WK=$(ls "$HB" 2>/dev/null | wc -l)
  echo "TICK remaining=$REM live_workers=$WK node=$AI_NODE state=$AIST fresh_hb=$fresh_node stall=$stall loop=$loop $(date -u +%FT%TZ)"
  sleep 90
done
echo "SUPERVISOR_EXIT $(date -u +%FT%TZ)"
