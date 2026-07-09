#!/usr/bin/env bash
# Phase B.1 formal launcher.
#
# Invoked via `/diagnostic-to-review "bash scripts/launch_phase_b1.sh"` (autonomous
# AFK execution 2026-05-23). Activates the audio-prm conda env, exports the
# reward-model env vars to point at the local SHA-pinned checkpoints (see
# `configs/eval/gate_v2.yaml.draft sha_pinned`), and runs the Phase B.1 driver
# with PI-approved-launch dual-lock satisfied.
#
# Pre-conditions (driver enforces internally; this comment is documentation only):
#   - configs/eval/gate_v2.yaml.draft `reliability_curve.pi_approval_status` = PI_APPROVED_*
#   - configs/runs/phase_b1_reliability.yaml `pi_approved_binding: true`
#   - configs/runs/phase_b1_reliability.yaml `pi_approved_launch: true`
#   - `--pi-approved-launch` CLI flag (passed below)
#
# Frozen-policy SHAs (see orbit-research/GATE_V2_FREEZE_2026-05-23.md):
#   gate_v2.yaml.draft   34db933b67d06f3acc3780e70b2f492a20d685ef710777fc81eaffba1d2806e9
#   phase_b1.yaml         365d67c9f605fb99704c2461930bca6d5c48e59f9584a2bf1577d4f503d1d28a
#   driver.py             690bd5afff19745df309671a8ecc0805c2f760e312701a9637bce7f47c2e7bb2

set -euo pipefail

# Move to project root regardless of where bash was invoked.
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

mkdir -p runs/phase_b1_reliability

exec python scripts/phase_b1_reliability.py \
    --config configs/runs/phase_b1_reliability.yaml \
    --gate-policy configs/eval/gate_v2.yaml.draft \
    --output-dir runs/phase_b1_reliability/ \
    --pi-approved-launch
