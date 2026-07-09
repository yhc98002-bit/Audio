#!/usr/bin/env bash
# Per-node ADSR resume generation worker. Runs on whatever GPU node we get (ai or temp).
# Reuses collect_early_tweedie_validation.py unchanged. Safe to run concurrently on multiple
# nodes (heartbeat stride-partition + original-wins merge dedups any overlap).
# Progress/completion are measured by VALID remaining candidates (seed-checked), never raw
# record lines (Codex r2 #1/#2). Usage: adsr_gpu_worker.sh [forward|reverse]
set +e +u
ORDER="${1:-forward}"
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
PYBIN=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
cd "$REPO" || exit 9
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh 2>/dev/null
conda activate audio-prm 2>/dev/null   # best-effort for env vars; PYBIN is authoritative
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1  # compute nodes have no internet; skip HF phone-home retries
export TMPDIR="/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/tmpscratch"; mkdir -p "$TMPDIR" 2>/dev/null  # redirect ACE-Step temp WAVs off the small loop0 /tmp to shared FS (avoid ENOSPC libsndfile crashes)

is_int(){ case "$1" in (''|*[!0-9]*) return 1;; (*) return 0;; esac; }
HOST=$(hostname); WID="${SLURM_JOB_ID:-ssh}_${HOST}_$$_$(date +%s)"  # unique even on requeue/PID reuse
RESUME_ROOT="runs/adsr_recollect_resume"
COORD="orbit-research/adsr_resume_coord"; HB="$COORD/heartbeats"
LOGDIR="$RESUME_ROOT/logs"; mkdir -p "$HB" "$LOGDIR"
LOG="$LOGDIR/worker_${WID}.log"
exec >>"$LOG" 2>&1
echo "{\"event\":\"worker_start\",\"wid\":\"$WID\",\"host\":\"$HOST\",\"order\":\"$ORDER\",\"ts\":\"$(date -u +%FT%TZ)\"}"

# 0a) GPU guard — confirm this node actually has GPUs (esp. an22, unverifiable while pending)
NGPU=$(nvidia-smi -L 2>/dev/null | wc -l)
echo "{\"event\":\"gpu_probe\",\"ngpu\":$NGPU,\"detail\":\"$(nvidia-smi -L 2>&1 | head -1)\"}"
if [ "${NGPU:-0}" -lt 1 ]; then echo "{\"event\":\"abort_no_gpu\",\"wid\":\"$WID\"}"; exit 3; fi

# 0b) Pre-warm OS page cache with the model + reward weights via ONE sequential reader, so the
# N per-GPU collectors load from RAM instead of N-way contending on cold NFS (a fresh node — esp.
# a 2h temp node — otherwise wastes many minutes here). One ~12GB read beats N concurrent cold reads.
echo "{\"event\":\"prewarm_start\",\"ts\":\"$(date -u +%FT%TZ)\"}"
timeout 900 bash -c 'find ~/.cache/modelscope/hub/models/ACE-Step/ ~/.cache/whisper/ ~/.cache/clap/ ~/.cache/huggingface/ -type f -print0 2>/dev/null | xargs -0 cat 2>/dev/null > /dev/null'
echo "{\"event\":\"prewarm_done\",\"rc\":$?,\"ts\":\"$(date -u +%FT%TZ)\"}"

# 1) heartbeat (refresh every 30s; TTL 180s) so concurrent workers partition R disjointly
MYHB="$HB/$WID"; : > "$MYHB"
( while :; do : > "$MYHB"; sleep 30; done ) &
HBPID=$!
cleanup(){ kill "$HBPID" 2>/dev/null; rm -f "$MYHB" 2>/dev/null; echo "{\"event\":\"worker_exit\",\"wid\":\"$WID\",\"ts\":\"$(date -u +%FT%TZ)\"}"; }
trap cleanup EXIT INT TERM

# valid global remaining candidate-gens (seed-checked); prints "" on failure (never assume 0)
global_remaining(){ $PYBIN scripts/build_resume_manifest.py --dry-run 2>/dev/null \
  | $PYBIN -c "import sys,json;print(json.load(sys.stdin)['remaining_candidate_gens'])" 2>/dev/null; }

# Loop until VALID global remaining hits 0 (Codex #3: never permanently skip a stripe a dead peer
# left behind). The unlimited ai node thus guarantees completion; a temp node loops until its 2h
# preemption. Completion is only concluded on a SUCCESSFUL dry-run==0 (Codex r2 #1); stall is
# measured by valid-remaining not decreasing (Codex r2 #2) and exits nonzero so the caller knows.
ATTEMPT=0; STALL=0
while :; do
  GREM=$(global_remaining)
  if ! is_int "$GREM"; then echo "{\"event\":\"warn_remaining_unreadable\",\"ts\":\"$(date -u +%FT%TZ)\"}"; sleep 60; continue; fi
  if [ "$GREM" -eq 0 ]; then echo "{\"event\":\"all_done\",\"wid\":\"$WID\"}"; break; fi

  ATTEMPT=$((ATTEMPT+1))
  sleep 3   # settle so simultaneously-starting workers see each other
  NOW=$(date +%s)
  mapfile -t LIVE < <(for f in "$HB"/*; do [ -e "$f" ] || continue; m=$(stat -c %Y "$f" 2>/dev/null||echo 0); [ $((NOW-m)) -le 180 ] && basename "$f"; done | sort)
  N=${#LIVE[@]}; [ "$N" -lt 1 ] && N=1
  IDX=0; for i in "${!LIVE[@]}"; do [ "${LIVE[$i]}" = "$WID" ] && IDX=$i; done

  MAN="$COORD/rescue_${WID}_a${ATTEMPT}.json"
  if ! $PYBIN scripts/build_resume_manifest.py --out "$MAN" --order "$ORDER" --num-workers "$N" --worker-index "$IDX" >/dev/null 2>&1; then
    echo "{\"event\":\"warn_build_failed\",\"attempt\":$ATTEMPT}"; sleep 30; continue
  fi
  NP=$($PYBIN -c "import json;print(json.load(open('$MAN'))['n_prompts'])" 2>/dev/null)
  if ! is_int "$NP"; then echo "{\"event\":\"warn_parse_failed\",\"attempt\":$ATTEMPT}"; sleep 30; continue; fi
  if [ "$NP" -lt 1 ]; then
    # my stride is empty. Only mop up the whole remainder if I'm the ONLY live worker (Codex r2 #3:
    # never grab the full set while a peer may be working a slice). Otherwise wait + re-partition.
    if [ "$N" -le 1 ]; then
      $PYBIN scripts/build_resume_manifest.py --out "$MAN" --order "$ORDER" --num-workers 1 --worker-index 0 >/dev/null 2>&1
      NP=$($PYBIN -c "import json;print(json.load(open('$MAN'))['n_prompts'])" 2>/dev/null||echo 0)
      [ "${NP:-0}" -lt 1 ] && { echo "{\"event\":\"stride_empty_solo_none\",\"wid\":\"$WID\"}"; sleep 30; continue; }
    else
      echo "{\"event\":\"stride_empty_wait\",\"num_workers\":$N,\"idx\":$IDX}"; sleep 30; continue
    fi
  fi
  echo "{\"event\":\"partition\",\"attempt\":$ATTEMPT,\"num_workers\":$N,\"worker_index\":$IDX,\"my_prompts\":$NP,\"global_remaining_gens\":$GREM,\"live\":\"${LIVE[*]}\"}"

  CHUNK=$(( (NP + NGPU - 1) / NGPU ))
  PIDS=()
  for g in $(seq 0 $((NGPU-1))); do
    OFF=$((g*CHUNK)); [ "$OFF" -ge "$NP" ] && break
    OUT="$RESUME_ROOT/${WID}_a${ATTEMPT}_gpu${g}"   # unique per worker+attempt+gpu (Codex #5)
    CUDA_VISIBLE_DEVICES=$g nohup $PYBIN scripts/collect_early_tweedie_validation.py \
      --output-dir "$OUT" --manifest "$MAN" \
      --prompt-offset "$OFF" --n-prompts "$CHUNK" --bon-n 8 \
      --target-sigmas 0.9 0.8 0.7 0.5 0.3 --save-audio --progress-every 16 \
      >"$LOGDIR/${WID}_a${ATTEMPT}_gpu${g}.log" 2>&1 &
    PIDS+=($!)
    echo "{\"event\":\"gpu_launch\",\"attempt\":$ATTEMPT,\"gpu\":$g,\"offset\":$OFF,\"chunk\":$CHUNK,\"out\":\"$OUT\",\"pid\":$!}"
  done
  wait "${PIDS[@]}"

  AFTER=$(global_remaining); is_int "$AFTER" || AFTER=$GREM
  echo "{\"event\":\"attempt_done\",\"attempt\":$ATTEMPT,\"remaining_before\":$GREM,\"remaining_after\":$AFTER}"
  # progress == VALID remaining decreased (Codex r2 #2). Persistent no-progress => stop NONZERO.
  if [ "$AFTER" -ge "$GREM" ]; then STALL=$((STALL+1)); else STALL=0; fi
  if [ "$STALL" -ge 2 ]; then echo "{\"event\":\"stop_no_progress\",\"wid\":\"$WID\",\"remaining\":$AFTER}"; exit 4; fi
done
echo "{\"event\":\"worker_done\",\"wid\":\"$WID\",\"ts\":\"$(date -u +%FT%TZ)\"}"
