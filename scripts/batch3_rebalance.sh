#!/usr/bin/env bash
# Rebalance: relaunch a given list of worker indices on THIS node with capped CPU threads.
# Usage: batch3_rebalance.sh "<worker_idx list>" <gpu_start>
set +e +u
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
PY=/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python
WORKERS=($1); G="${2:-0}"
cd "$REPO" || exit 9
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6
for w in "${WORKERS[@]}"; do
  CUDA_VISIBLE_DEVICES=$G nohup "$PY" scripts/batch3_online_harness.py \
    --worker-index "$w" --num-workers 16 --out-tag run \
    >>"orbit-research/adsr_phase2_20260604/batch3/online_run/w${w}.log" 2>&1 &
  G=$((G + 1))
done
echo "REBALANCED host=$(hostname) workers=${WORKERS[*]} procs=$(pgrep -fc batch3_online_harness)"
