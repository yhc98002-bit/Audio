#!/usr/bin/env bash
# Competitive temp-node acquisition: keep K temp sbatch jobs queued so we re-grab an22 the
# instant it frees, and auto-resubmit after each 2h window. Stops when generation is complete.
# Uses a UNIQUE per-controller job name so squeue/scancel only ever touch our own jobs (Codex r2 #4).
# Intended to run inside a tmux session (survives terminal exit).
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
PYBIN=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
cd "$REPO" || exit 9
K="${1:-3}"                      # how many temp jobs to keep in flight (pending+running)
USER=$(whoami)
JOBNAME="adsr_rt_$$_$(date +%s)" # unique to THIS controller instance
LOG="runs/adsr_recollect_resume/logs/compete.log"; mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "{\"event\":\"compete_start\",\"K\":$K,\"jobname\":\"$JOBNAME\",\"ts\":\"$(date -u +%FT%TZ)\"}"

is_int(){ case "$1" in (''|*[!0-9]*) return 1;; (*) return 0;; esac; }

while :; do
  # --- valid remaining work? if unreadable (squeue/python hiccup) back off; never assume 0 (Codex #6) ---
  REM=$($PYBIN scripts/build_resume_manifest.py --dry-run 2>/dev/null | $PYBIN -c "import sys,json;print(json.load(sys.stdin)['remaining_candidate_gens'])" 2>/dev/null)
  if ! is_int "$REM"; then echo "{\"event\":\"warn_remaining_unreadable\",\"ts\":\"$(date -u +%FT%TZ)\"}"; sleep 120; continue; fi
  if [ "$REM" -eq 0 ]; then
    scancel --name="$JOBNAME" -u "$USER" 2>/dev/null   # cancel ONLY our own leftover queued temp jobs (Codex r2 #4)
    echo "{\"event\":\"compete_done_all_generated\",\"jobname\":\"$JOBNAME\",\"ts\":\"$(date -u +%FT%TZ)\"}"; break
  fi
  # --- our temp jobs in flight? if squeue errors, back off instead of runaway-submitting (Codex #6) ---
  OUT=$(squeue -u "$USER" -h -n "$JOBNAME" -o "%i" 2>/dev/null); RC=$?
  if [ "$RC" -ne 0 ]; then echo "{\"event\":\"warn_squeue_failed\",\"rc\":$RC,\"ts\":\"$(date -u +%FT%TZ)\"}"; sleep 120; continue; fi
  CUR=$(printf '%s\n' "$OUT" | grep -c '[0-9]')
  if [ "$CUR" -lt "$K" ]; then
    NEED=$((K - CUR))
    for _ in $(seq 1 "$NEED"); do
      JID=$(sbatch -J "$JOBNAME" --parsable scripts/adsr_temp_sbatch.sh 2>/dev/null); RC=$?
      if [ "$RC" -ne 0 ] || ! is_int "$JID"; then
        echo "{\"event\":\"warn_sbatch_failed\",\"rc\":$RC,\"out\":\"$JID\",\"ts\":\"$(date -u +%FT%TZ)\"}"; sleep 60; break
      fi
      echo "{\"event\":\"submit_temp\",\"jobid\":\"$JID\",\"jobname\":\"$JOBNAME\",\"had\":$CUR,\"target\":$K,\"remaining_gens\":$REM,\"ts\":\"$(date -u +%FT%TZ)\"}"
      CUR=$((CUR+1))
    done
  fi
  sleep 30
done
