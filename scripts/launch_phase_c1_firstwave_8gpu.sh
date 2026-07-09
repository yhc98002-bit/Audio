#!/usr/bin/env bash
# Bounded Phase C1 first-wave launcher.
#
# Usage:
#   bash scripts/launch_phase_c1_firstwave_8gpu.sh \
#     [configs/runs/phase_c1_firstwave.yaml] \
#     [runs/phase_c1_firstwave_<stamp>]
#
# Preconditions are external to this launcher:
#   - real R8a/R8b C0 smokes passed;
#   - M-FixedWin/M-Section smokes remain valid;
#   - Claude Code audit returned ACCEPT or ACCEPT_WITH_NONBLOCKING_NOTES;
#   - ETA report is <= 240 GPU-h.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

CONFIG="${1:-configs/runs/phase_c1_firstwave.yaml}"
OUT_ROOT="${2:-runs/phase_c1_firstwave_$(date +%Y%m%d_%H%M%S)}"

module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export PYTHONPATH=src
export LAION_CLAP_BERT_DIR="${LAION_CLAP_BERT_DIR:-$HOME/HDD_POOL/source/laion_clap_tokenizers/bert-base-uncased}"
export LAION_CLAP_ROBERTA_DIR="${LAION_CLAP_ROBERTA_DIR:-$HOME/HDD_POOL/source/laion_clap_tokenizers/roberta-base}"
export LAION_CLAP_BART_DIR="${LAION_CLAP_BART_DIR:-$HOME/HDD_POOL/source/laion_clap_tokenizers/facebook--bart-base}"
export AUDIOBOX_AES_CKPT="${AUDIOBOX_AES_CKPT:-$HOME/HDD_POOL/source/audiobox_aesthetics/checkpoint.pt}"
export MERT_LOCAL_PATH="${MERT_LOCAL_PATH:-$HOME/HDD_POOL/source/mert/MERT-v1-95M}"
export TOKENIZERS_PARALLELISM=false
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTHONUNBUFFERED=1
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

python scripts/phase_c1_grpo.py --config "$CONFIG" --mode preflight

python scripts/phase_c_pairing_audit.py \
  --fixedwin configs/runs/phase_c_m_fixedwin_firstwave.yaml \
  --section configs/runs/phase_c_m_section_diagnostic.yaml \
  --out "$OUT_ROOT/pairing_audit.json"

mkdir -p "$OUT_ROOT/logs" "$OUT_ROOT/pids"

declare -A GPU_FOR_METHOD=(
  [r8a]=0
  [r8b]=1
  [m_fixedwin]=2
  [m_section]=3
)

echo "Phase C1 launch root: $OUT_ROOT"
echo "Parallelism: one method per GPU. Prompt-sharding one method is intentionally not used because it would train separate adapters."

pids=()
methods=(r8a r8b m_fixedwin m_section)
for method in "${methods[@]}"; do
  gpu="${GPU_FOR_METHOD[$method]}"
  log="$OUT_ROOT/logs/${method}.log"
  echo "Launching $method on GPU $gpu; log=$log"
  CUDA_VISIBLE_DEVICES="$gpu" python scripts/phase_c1_grpo.py \
    --config "$CONFIG" \
    --mode train \
    --method "$method" \
    --output-root "$OUT_ROOT" \
    --pi-approved-launch \
    >"$log" 2>&1 &
  pid="$!"
  echo "$pid" > "$OUT_ROOT/pids/${method}.pid"
  pids+=("$pid")
done

status=0
for idx in "${!pids[@]}"; do
  pid="${pids[$idx]}"
  method="${methods[$idx]}"
  if wait "$pid"; then
    echo "$method PASS"
  else
    rc=$?
    echo "$method FAIL rc=$rc" >&2
    status=1
  fi
done

exit "$status"
