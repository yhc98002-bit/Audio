#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 RUN_ROOT" >&2
  exit 2
fi

run_root="$1"
manifest="orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"

if [ -e "$run_root" ]; then
  echo "Refusing to reuse existing run root: $run_root" >&2
  exit 2
fi

mkdir -p "$run_root"
echo "$0 $run_root" > "$run_root/launch_command.txt"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$run_root/launch_started_utc.txt"

pids=()
for gpu in 0 1 2 3 4 5 6 7; do
  shard="$(printf 'shard%02d' "$gpu")"
  offset=$((gpu * 64))
  (
    set +e
    CUDA_VISIBLE_DEVICES="$gpu" python scripts/collect_early_tweedie_validation.py \
      --output-dir "$run_root/$shard" \
      --manifest "$manifest" \
      --prompt-offset "$offset" \
      --n-prompts 64 \
      --bon-n 8 \
      --target-sigmas 0.9 0.8 0.7 \
      --progress-every 32 \
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

if [ "$status" -eq 0 ]; then
  python scripts/merge_early_tweedie_validation.py \
    --records "$run_root"/shard*/candidate_records.jsonl \
    --run-root "$run_root" \
    --manifest "$manifest" \
    --output-md orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md \
    --output-json orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json \
    --plot-csv orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv \
    --retention-csv orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv \
    --expected-bon-n 8 \
    > "$run_root/merge_stdout.log" \
    2> "$run_root/merge_stderr.log"
  status=$?
fi

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$run_root/launch_finished_utc.txt"
echo "$status" > "$run_root/launcher.exit"
exit "$status"
