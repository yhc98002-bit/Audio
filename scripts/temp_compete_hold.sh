#!/usr/bin/env bash
# Competitive temp-node acquisition (generic HOLD version). Keeps K temp sbatch jobs queued so we
# re-grab the 2h temp node (an22) the instant it frees, and resubmit after each 2h window. Runs
# indefinitely (no generation "done" condition) until the tmux/process is killed. Intended to run
# in a tmux that we DO NOT kill.
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
cd "$REPO" || exit 9
K="${1:-2}"
USER=$(whoami)
JOBNAME="temphold_$$_$(date +%s)"   # unique to this controller
LOG="runs/adsr_recollect_resume/logs/temp_compete_hold.log"; mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "{\"event\":\"compete_hold_start\",\"K\":$K,\"jobname\":\"$JOBNAME\",\"ts\":\"$(date -u +%FT%TZ)\"}"
is_int(){ case "$1" in (''|*[!0-9]*) return 1;; (*) return 0;; esac; }
while :; do
  OUT=$(squeue -u "$USER" -h -n "$JOBNAME" -o "%i" 2>/dev/null); RC=$?
  if [ "$RC" -ne 0 ]; then echo "{\"event\":\"warn_squeue\",\"rc\":$RC,\"ts\":\"$(date -u +%FT%TZ)\"}"; sleep 60; continue; fi
  CUR=$(printf '%s\n' "$OUT" | grep -c '[0-9]')
  if [ "$CUR" -lt "$K" ]; then
    for _ in $(seq 1 $((K - CUR))); do
      JID=$(sbatch -J "$JOBNAME" --parsable scripts/temp_hold_sbatch.sh 2>/dev/null)
      if is_int "$JID"; then echo "{\"event\":\"submit_temp_hold\",\"jobid\":\"$JID\",\"had\":$CUR,\"K\":$K,\"ts\":\"$(date -u +%FT%TZ)\"}"; CUR=$((CUR+1)); else echo "{\"event\":\"warn_sbatch\",\"out\":\"$JID\",\"ts\":\"$(date -u +%FT%TZ)\"}"; sleep 60; break; fi
    done
  fi
  sleep 30
done
