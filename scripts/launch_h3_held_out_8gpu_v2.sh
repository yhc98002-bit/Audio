#!/usr/bin/env bash
# Launch the held-out 256 H3 run across 8 GPUs (round-robin sharding).
#
# v2 (PI directive 2026-05-23 Phase 2): corrected held-out with
#   - GLOBAL-INDEX seeding (fixes shard-seed aliasing reported by Codex
#     Review #1; 256 unique seeds instead of 32 repeated 8x)
#   - audio persisted to <out>/audio/<prompt_id>.wav so Phase 3
#     sectionability audit can run actual section detection on the
#     final clips.
#
# Each shard processes ~32 prompts (256/8). Per-prompt rate ~15 s →
# 32 * 15 = ~8 min/shard wallclock + 1 min model load = ~9 min total.
# Total GPU-h = 8 GPUs * 9 min / 60 ≈ 1.2 GPU-h. Hard cap 30 GPU-h
# per PI directive.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT_DIR="runs/phase_b3_credit_unit/h3_held_out_v2_global_seed"
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
        # CPU thread caps (see v1 launcher for rationale).
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
            --skip-verdict \
            --save-audio
    ) > "$LOG" 2>&1 &
    PIDS+=($!)
    sleep 2
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

# Verify global-seed uniqueness post-merge.
python3 -c "
import json
seeds = []
gpis = []
for line in open('$OUT_DIR/results.jsonl'):
    rec = json.loads(line)
    seeds.append(rec['seed'])
    gpis.append(rec.get('global_prompt_index', -1))
n_unique_seeds = len(set(seeds))
n_unique_gpi = len(set(gpis))
print(f'[verify] total prompts: {len(seeds)}')
print(f'[verify] unique seeds: {n_unique_seeds} (expect 256)')
print(f'[verify] unique global_prompt_index: {n_unique_gpi} (expect 256)')
assert n_unique_seeds == 256, f'SEED ALIASING DETECTED: only {n_unique_seeds} unique seeds!'
assert n_unique_gpi == 256, f'GLOBAL INDEX BROKEN: only {n_unique_gpi} unique global indices!'
print('[verify] global-index seeding confirmed.')
"

echo "[launch] DONE. Outputs in $OUT_DIR"
