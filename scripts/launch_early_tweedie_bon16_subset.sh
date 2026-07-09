#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 RUN_ROOT" >&2
  exit 2
fi

run_root="$1"
manifest="orbit-research/EARLY_TWEEDIE_BON16_128_PROMPTS.json"

if [ -e "$run_root" ]; then
  echo "Refusing to reuse existing run root: $run_root" >&2
  exit 2
fi

mkdir -p "$run_root"
echo "$0 $run_root" > "$run_root/launch_command.txt"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$run_root/launch_started_utc.txt"

source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm

pids=()
for gpu in 0 1 2 3 4 5 6 7; do
  shard="$(printf 'shard%02d' "$gpu")"
  offset=$((gpu * 16))
  (
    set +e
    CUDA_VISIBLE_DEVICES="$gpu" python scripts/collect_early_tweedie_validation.py \
      --output-dir "$run_root/$shard" \
      --manifest "$manifest" \
      --prompt-offset "$offset" \
      --n-prompts 16 \
      --bon-n 16 \
      --target-sigmas 0.9 0.8 0.7 \
      --progress-every 16 \
      > "$run_root/${shard}_stdout.log" \
      2> "$run_root/${shard}_stderr.log"
    code=$?
    echo "$code" > "$run_root/${shard}.exit"
    exit "$code"
  ) &
  pid=$!
  pids+=("$pid")
  echo "$pid" > "$run_root/${shard}.pid"
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$run_root/launch_finished_utc.txt"
echo "$status" > "$run_root/launcher.exit"
exit "$status"
