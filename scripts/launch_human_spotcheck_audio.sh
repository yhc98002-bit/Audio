#!/usr/bin/env bash
set -euo pipefail

packet_dir="orbit-research/human_spotcheck_packet_20260528"
log_dir="$packet_dir/audio_generation_logs"
mkdir -p "$log_dir"

source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm

pids=()
for gpu in 0 1 2 3 4 5 6 7; do
  (
    set +e
    CUDA_VISIBLE_DEVICES="$gpu" python scripts/generate_human_spotcheck_audio.py \
      --shard-index "$gpu" \
      --num-shards 8 \
      > "$log_dir/shard${gpu}_stdout.log" \
      2> "$log_dir/shard${gpu}_stderr.log"
    code=$?
    echo "$code" > "$log_dir/shard${gpu}.exit"
    exit "$code"
  ) &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

python scripts/generate_human_spotcheck_audio.py --merge-only --num-shards 8 \
  > "$log_dir/merge_stdout.log" \
  2> "$log_dir/merge_stderr.log"

exit "$status"
