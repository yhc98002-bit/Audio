#!/bin/bash
#SBATCH -p temp
#SBATCH -w an22
#SBATCH --exclusive
#SBATCH -t 2:00:00
#SBATCH -J temp_hold
#SBATCH -o /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/logs/temp_hold_%j.out
#SBATCH -e /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/logs/temp_hold_%j.out
# Competitively-acquired 2h temp node HOLDER. When this lands, it pins the node (so we can ssh in
# and run a task within the 2h window) and drops a GRANTED marker the agent polls. It holds for
# ~1h55m then exits cleanly so the compete loop re-grabs the node for the next window.
REPO=/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion
MARK="$REPO/runs/adsr_recollect_resume/TEMP_GRANTED.json"
echo "TEMP_GRANTED node=$SLURMD_NODENAME job=$SLURM_JOB_ID gpus=$(nvidia-smi -L 2>/dev/null | wc -l) at $(date -u +%FT%TZ)"
printf '{"node":"%s","job":"%s","gpus":%s,"granted_utc":"%s"}\n' \
  "$SLURMD_NODENAME" "$SLURM_JOB_ID" "$(nvidia-smi -L 2>/dev/null | wc -l)" "$(date -u +%FT%TZ)" > "$MARK"
# hold the node, but check every 60s for a drop-in task script the agent may place; if present, run it
TASK="$REPO/runs/adsr_recollect_resume/TEMP_TASK.sh"
for i in $(seq 1 115); do
  if [ -f "$TASK" ]; then echo "running drop-in TEMP_TASK.sh @ $(date -u +%FT%TZ)"; bash "$TASK" "$SLURMD_NODENAME"; echo "TEMP_TASK done rc=$? @ $(date -u +%FT%TZ)"; rm -f "$TASK"; fi
  sleep 60
done
echo "TEMP_HOLD window ending (re-grab via compete) @ $(date -u +%FT%TZ)"
