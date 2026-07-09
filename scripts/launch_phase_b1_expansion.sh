#!/usr/bin/env bash
# Phase B.1 128-prompt expansion launcher (PI directive 2026-05-23 §3)
#
# Cost: ~0.32 GPU-h (linear extrapolation from canonical run on A800).
# Hard cap: 2 GPU-h.
#
# Run sequence:
#   1. Driver runs the new 64 expansion prompts → produces
#      runs/phase_b1_reliability_expansion/{results.jsonl, ...}
#   2. After driver exits 0, the merge-and-reclassify step
#      (scripts/phase_b1_reanalyze.py --merge-with) is invoked separately
#      to produce the 128-prompt verdict.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

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
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

mkdir -p runs/phase_b1_reliability_expansion

exec python scripts/phase_b1_reliability.py \
    --config configs/runs/phase_b1_reliability_expansion.yaml \
    --gate-policy configs/eval/gate_v2.yaml.draft \
    --output-dir runs/phase_b1_reliability_expansion/ \
    --pi-approved-launch
