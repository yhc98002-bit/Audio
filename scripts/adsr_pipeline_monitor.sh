#!/usr/bin/env bash
set +e
cd /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
P2=orbit-research/adsr_phase2_20260604
RUN=runs/adsr_recollect_20260604_full01
WPID=$(cat "$P2/watch.pid")
TAG="${1:-cov25}"                      # which milestone snapshot to wait for (cov25|cov50|cov70|final)
TARGET="$P2/snapshots/snapshot_${TAG}.json"
LOGSTART=$(wc -l < "$P2/watch.log")   # only inspect straggler lines logged after monitor start
prev=-1; unchanged=0; STALL_POLLS=13   # 13*120s ~= 26min
echo "MONITOR_START watch=$WPID target=$TAG logstart=$LOGSTART $(date -u +%FT%TZ)"
while true; do
  # 1) milestone snapshot
  if [ -f "$TARGET" ]; then echo "EVENT=${TAG}_snapshot"; echo "---"; cat "$TARGET"; break; fi
  # 2) watch death (clean done vs crash)
  if ! ps -p "$WPID" -o pid= >/dev/null 2>&1; then
    if tail -n 25 "$P2/watch.log" | grep -q "watch_done"; then echo "EVENT=watch_done_clean"; else echo "EVENT=watch_DIED_unexpected pid=$WPID"; fi
    echo "---tail watch.log---"; tail -n 12 "$P2/watch.log"; break
  fi
  # 3) straggler flagged (non-empty set => key line ends with '{' not '{}'), only in lines after start
  if tail -n +"$LOGSTART" "$P2/watch.log" | grep -q 'stragglers_60pct_rate_and_4h_drag": {$'; then
    echo "EVENT=straggler_flagged"; echo "---"; tail -n +"$LOGSTART" "$P2/watch.log" | grep -A6 'stragglers_60pct_rate_and_4h_drag": {$' | tail -n 12; break
  fi
  # 4) generation stall
  cur=$(cat $RUN/shard0*/candidate_records.jsonl 2>/dev/null | wc -l)
  if [ "$cur" -eq "$prev" ]; then unchanged=$((unchanged+1)); else unchanged=0; prev=$cur; fi
  genprocs=$(ps aux | grep collect_early_tweedie | grep -v grep | wc -l)
  if [ "$unchanged" -ge "$STALL_POLLS" ] && [ "$cur" -lt 4096 ]; then
    echo "EVENT=generation_stall records=$cur unchanged_polls=$unchanged genprocs=$genprocs"; break
  fi
  python -c "import time; time.sleep(120)"
done
echo "MONITOR_EXIT $(date -u +%FT%TZ)"
