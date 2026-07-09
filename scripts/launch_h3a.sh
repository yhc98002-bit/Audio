#!/usr/bin/env bash
# Phase B.3 H3a launcher.
#
# This launcher enforces the H3a PI dual lock before delegating to the formal
# H3a driver. It intentionally refuses to proceed if the driver has not been
# implemented yet.

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

CONFIG="configs/runs/phase_b3_credit_unit_comparison.yaml"
DRIVER="scripts/phase_b3_credit_unit_comparison.py"
OUT_DIR="runs/phase_b3_credit_unit/h3a"

python scripts/h3a_preflight.py \
    --config "$CONFIG" \
    --pi-approved-launch

if [[ ! -f "$DRIVER" ]]; then
    echo "H3a preflight passed, but $DRIVER does not exist yet; refusing to launch." >&2
    exit 2
fi

mkdir -p "$OUT_DIR"

exec python "$DRIVER" \
    --config "$CONFIG" \
    --gate-policy configs/eval/gate_v2.yaml.draft \
    --output-dir "$OUT_DIR" \
    --pi-approved-launch
