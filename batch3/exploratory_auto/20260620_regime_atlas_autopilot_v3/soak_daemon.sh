#!/bin/bash
# Self-replenishing soak daemon — keeps an17 (8 GPU) busy across orchestrator context gaps.
# Runs one job spec at a time (8 workers), waits for completion, pulls the next from queue/pending.
# Job spec = queue/pending/NN_name.env setting: PROMPTS NSEEDS COND TAG LOGTAG
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
A=$REPO/batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3
CORE=$A/01_core_basin_test
QD=$A/queue
PY=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
LOG=$A/00_controller/soak_daemon.log
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
cd $REPO || exit 9
mkdir -p $QD/pending $QD/running $QD/done
echo "SOAK_DAEMON_START $(date) host=$(hostname)" >> $LOG
while true; do
  if [ "$(pgrep -fc core_largeN_worker)" -gt 0 ]; then sleep 120; continue; fi
  spec=$(ls $QD/pending/*.env 2>/dev/null | sort | head -1)
  if [ -z "$spec" ]; then echo "QUEUE_DRAINED $(date) — daemon exiting" >> $LOG; break; fi
  mv "$spec" $QD/running/ 2>/dev/null
  spec=$QD/running/$(basename "$spec")
  PROMPTS=""; NSEEDS=256; COND=none; TAG=job; LOGTAG=job
  source "$spec"
  echo "LAUNCH $LOGTAG prompts=$PROMPTS N=$NSEEDS cond=$COND tag=$TAG $(date)" >> $LOG
  for g in 0 1 2 3 4 5 6 7; do
    CUDA_VISIBLE_DEVICES=$g OMP_NUM_THREADS=6 nohup $PY $CORE/core_largeN_worker.py \
      --prompts "$PROMPTS" --n-seeds "$NSEEDS" --condition "$COND" --out "$CORE" \
      --tag "$TAG" --worker-index $g --num-workers 8 \
      >"$CORE/ledgers/${LOGTAG}_w${g}.log" 2>&1 &
  done
  sleep 30
  start=$SECONDS
  while [ "$(grep -l LARGEN_DONE $CORE/ledgers/${LOGTAG}_w*.log 2>/dev/null | wc -l)" -lt 8 ]; do
    sleep 120
    if [ $((SECONDS-start)) -gt 36000 ]; then
      echo "TIMEOUT $LOGTAG after 10h $(date)" >> $LOG
      pkill -f "core_largeN_worker.py.*--tag ${TAG} "; break
    fi
  done
  mv "$spec" $QD/done/ 2>/dev/null
  echo "DONE $LOGTAG $(date) rows=$(cat $CORE/ledgers/${TAG}_w*.jsonl 2>/dev/null|wc -l)" >> $LOG
done
echo "SOAK_DAEMON_STOP $(date)" >> $LOG
