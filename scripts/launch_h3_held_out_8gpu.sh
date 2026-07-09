#!/usr/bin/env bash
# Launch the held-out 256 H3 run across 8 GPUs (round-robin sharding).
#
# Each shard processes ~32 prompts (256/8). Per-prompt rate from dev run
# was ~13.5 s/prompt → 32 * 13.5 = ~7 min/shard wallclock + ~1 min model
# load = ~8 min total. Total GPU-h = 8 GPUs * 8 min = ~1.1 GPU-h. Hard cap
# 10 GPU-h.
#
# Usage:
#   bash scripts/launch_h3_held_out_8gpu.sh
#
# Each shard logs to runs/phase_b3_credit_unit/h3_held_out/shard_N.log
# Outputs the partial JSONL: results_shard{N}of08.jsonl
# Run scripts/merge_h3_shards.py after all shards complete.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT_DIR="runs/phase_b3_credit_unit/h3_held_out"
mkdir -p "$OUT_DIR"

SHARD_TOTAL=8
PIDS=()
for i in $(seq 0 $((SHARD_TOTAL - 1))); do
    LOG="$OUT_DIR/shard_${i}.log"
    echo "[launch] starting shard $i on GPU $i → $LOG"
    (
        module load anaconda3/2023.09
        source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
        conda activate audio-prm
        export HF_ENDPOINT=https://hf-mirror.com
        export PYTHONPATH=src
        export LAION_CLAP_BERT_DIR="$HOME/HDD_POOL/source/laion_clap_tokenizers/bert-base-uncased"
        export LAION_CLAP_ROBERTA_DIR="$HOME/HDD_POOL/source/laion_clap_tokenizers/roberta-base"
        export LAION_CLAP_BART_DIR="$HOME/HDD_POOL/source/laion_clap_tokenizers/facebook--bart-base"
        export AUDIOBOX_AES_CKPT="$HOME/HDD_POOL/source/audiobox_aesthetics/checkpoint.pt"
        export MERT_LOCAL_PATH="$HOME/HDD_POOL/source/mert/MERT-v1-95M"
        export CUDA_VISIBLE_DEVICES="$i"
        # Engineering fix 2026-05-23: limit per-process CPU threading to avoid
        # CPU oversubscription when running 8 shards in parallel. The 8x
        # reward stacks (Audiobox+CLAP+MERT+Demucs+Whisper) each spawn ~13
        # threads by default → load average 250+. Capping to 2 threads per
        # process keeps total threads ≤ 32, well within node CPU capacity.
        export OMP_NUM_THREADS=2
        export MKL_NUM_THREADS=2
        export NUMEXPR_NUM_THREADS=2
        export TORCH_NUM_THREADS=2
        export OPENBLAS_NUM_THREADS=2
        export VECLIB_MAXIMUM_THREADS=2
        exec python scripts/phase_b3_credit_unit_comparison.py \
            --config configs/runs/phase_b3_credit_unit_comparison.yaml \
            --output-dir "$OUT_DIR" \
            --pi-approved-launch \
            --prompts-mode held_out \
            --shard-index "$i" \
            --shard-total "$SHARD_TOTAL" \
            --skip-verdict
    ) > "$LOG" 2>&1 &
    PIDS+=($!)
    sleep 2   # Stagger model-load to avoid I/O thrash
done

echo "[launch] all ${#PIDS[@]} shards spawned: ${PIDS[*]}"
echo "[launch] waiting for shards to finish..."
FAILED=0
for i in $(seq 0 $((SHARD_TOTAL - 1))); do
    PID="${PIDS[$i]}"
    if wait "$PID"; then
        echo "[launch] shard $i (PID $PID) done"
    else
        echo "[launch] shard $i (PID $PID) FAILED"
        FAILED=$((FAILED + 1))
    fi
done

if [ "$FAILED" -ne 0 ]; then
    echo "[launch] $FAILED shards failed; aborting merge"
    exit 1
fi

echo "[launch] all shards done; running merge + verdict"
# Engineering fix 2026-05-23: parent shell does not inherit the conda env
# activated inside per-shard subshells. Re-activate before the merge invocation
# so `python` resolves to the audio-prm interpreter rather than failing with
# "command not found".
module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
export PYTHONPATH=src
python scripts/merge_h3_shards.py \
    --config configs/runs/phase_b3_credit_unit_comparison.yaml \
    --shard-dir "$OUT_DIR" \
    --shard-glob 'results_shard*of*.jsonl' \
    --prompts-mode held_out \
    --pi-approved-launch
