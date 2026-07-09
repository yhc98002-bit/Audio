#!/usr/bin/env bash
# Allocation watcher. Exits (=> notifies the agent) when the ai node 93398 starts RUNNING
# (so the agent can ssh in and launch the worker), or when generation is fully complete.
# Also logs temp-job state transitions for visibility.
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
PYBIN=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
cd "$REPO" || exit 9
AI_JOB="${1:-93398}"
echo "WATCH_START ai_job=$AI_JOB $(date -u +%FT%TZ)"
while :; do
  # ai node allocated?
  read -r ST NODE < <(squeue -j "$AI_JOB" -h -o "%T %N" 2>/dev/null)
  if [ "$ST" = "RUNNING" ] && [ -n "$NODE" ]; then
    echo "EVENT=ai_allocated job=$AI_JOB node=$NODE $(date -u +%FT%TZ)"
    echo "ACTION: ssh $NODE then: bash scripts/adsr_gpu_worker.sh forward"
    break
  fi
  if [ -z "$ST" ]; then echo "NOTE ai_job $AI_JOB not in queue (finished/cancelled?) $(date -u +%FT%TZ)"; fi
  # generation complete?
  REM=$($PYBIN scripts/build_resume_manifest.py --dry-run 2>/dev/null | $PYBIN -c "import sys,json;print(json.load(sys.stdin)['remaining_candidate_gens'])" 2>/dev/null)
  if [ "${REM:-1}" = "0" ]; then echo "EVENT=generation_complete remaining=0 $(date -u +%FT%TZ)"; break; fi
  # heartbeat of progress
  DONE=$(cat runs/adsr_recollect_20260604_full01/shard0*/candidate_records.jsonl runs/adsr_recollect_resume/*/candidate_records.jsonl 2>/dev/null | wc -l)
  TEMP=$(squeue -u "$(whoami)" -h -n adsr_resume_temp -o "%T" 2>/dev/null | sort | uniq -c | tr '\n' ' ')
  echo "TICK ai=$ST/${NODE:-none} records~$DONE/4096 remaining_gens=$REM temp_jobs=[$TEMP] $(date -u +%FT%TZ)"
  sleep 60
done
echo "WATCH_EXIT $(date -u +%FT%TZ)"
