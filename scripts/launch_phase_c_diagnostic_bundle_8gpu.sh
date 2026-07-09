#!/usr/bin/env bash
# Paired Phase C diagnostic bundle launcher.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

module load anaconda3/2023.09
source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh
conda activate audio-prm
export PYTHONPATH=src

python scripts/phase_c_pairing_audit.py \
  --fixedwin configs/runs/phase_c_m_fixedwin_firstwave.yaml \
  --section configs/runs/phase_c_m_section_diagnostic.yaml \
  --out runs/phase_c_diagnostic_bundle/pairing_audit.json

set +e
python scripts/phase_c_m_fixedwin_prm.py \
  --config configs/runs/phase_c_m_fixedwin_firstwave.yaml \
  --mode firstwave \
  --output-dir runs/phase_c_m_fixedwin_firstwave \
  --pi-approved-launch \
  --shard-index 0 \
  --shard-total 8
FIXED_STATUS=$?

python scripts/phase_c_m_fixedwin_prm.py \
  --config configs/runs/phase_c_m_section_diagnostic.yaml \
  --mode firstwave \
  --output-dir runs/phase_c_m_section_diagnostic \
  --pi-approved-launch \
  --shard-index 0 \
  --shard-total 8
SECTION_STATUS=$?
set -e

if [[ "$FIXED_STATUS" -eq 2 && "$SECTION_STATUS" -eq 2 ]]; then
  echo "Both paired first-wave runs stopped before formal training with reports."
  exit 2
fi
if [[ "$FIXED_STATUS" -ne 0 || "$SECTION_STATUS" -ne 0 ]]; then
  echo "One or both paired first-wave runs failed/stopped: fixed=$FIXED_STATUS section=$SECTION_STATUS" >&2
  exit 1
fi
