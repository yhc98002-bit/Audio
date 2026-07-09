#!/usr/bin/env bash
# Phase C M-FixedWin-PRM tiny GPU smoke.

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

exec python scripts/phase_c_m_fixedwin_prm.py \
  --config configs/runs/phase_c_m_fixedwin_firstwave.yaml \
  --mode smoke \
  --backend real \
  --output-dir runs/phase_c_m_fixedwin_smoke \
  --pi-approved-launch
