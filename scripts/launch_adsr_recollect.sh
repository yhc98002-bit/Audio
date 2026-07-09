#!/bin/bash
# ADSR data-collection v2: full 512-prompt BoN-8 re-collection capturing
# sigma {0.9,0.8,0.7,0.5,0.3,final} + early(>=0.7) & final audio, across 8 GPUs.
set +e +u
cd /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion || exit 9
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh 2>/dev/null
conda activate audio-prm 2>/dev/null

# make sure no leftover collect/smoke procs hold the GPUs
pkill -9 -f adsr_recollect_smoke 2>/dev/null
sleep 3

RUN=runs/adsr_recollect_20260604_full01
MAN=orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json
rm -rf "$RUN" 2>/dev/null
mkdir -p "$RUN"

for g in 0 1 2 3 4 5 6 7; do
  off=$((g*64))
  sh=$(printf 'shard%02d' "$g")
  CUDA_VISIBLE_DEVICES=$g nohup python scripts/collect_early_tweedie_validation.py \
    --output-dir "$RUN/$sh" --manifest "$MAN" \
    --prompt-offset "$off" --n-prompts 64 --bon-n 8 \
    --target-sigmas 0.9 0.8 0.7 0.5 0.3 --save-audio --progress-every 16 \
    > "$RUN/${sh}.log" 2>&1 &
  echo "launched $sh GPU$g offset=$off pid=$!"
done
echo "all shards launched to $RUN"
