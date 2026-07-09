#!/usr/bin/env bash
# Batch-3 node launcher: starts 8 harness workers on this node (one per GPU).
# Usage: batch3_node_launcher.sh <worker_offset>   (an12 -> 0, an29 -> 8)
# Current split: an12 handles Stage 3 generation; an29 handles Stage 4 second-model work.
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
PY=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
OFF="${1:-0}"
cd "$REPO" || exit 9
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
rm -rf /dev/shm/batch3_adsr 2>/dev/null
mkdir -p orbit-research/adsr_phase2_20260604/batch3/online_run
for g in 0 1 2 3 4 5 6 7; do
  w=$((g + OFF))
  CUDA_VISIBLE_DEVICES=$g nohup "$PY" scripts/batch3_online_harness.py \
    --worker-index "$w" --num-workers 16 --out-tag run \
    >"orbit-research/adsr_phase2_20260604/batch3/online_run/w${w}.log" 2>&1 &
done
echo "LAUNCHED offset=$OFF host=$(hostname) procs=$(pgrep -fc batch3_online_harness)"
