#!/usr/bin/env bash
# Phase C M-Section-PRM bounded diagnostic launcher.

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

CONFIG="configs/runs/phase_c_m_section_diagnostic.yaml"
OUT_DIR="runs/phase_c_m_section_diagnostic"

python scripts/phase_c_m_fixedwin_prm.py \
  --config "$CONFIG" \
  --mode firstwave \
  --output-dir "$OUT_DIR" \
  --pi-approved-launch \
  --shard-index 0 \
  --shard-total 8
