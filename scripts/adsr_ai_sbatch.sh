#!/bin/bash
#SBATCH -p ai
#SBATCH -N 1
#SBATCH --exclusive
#SBATCH -J adsr_resume_ai
#SBATCH -o /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/logs/slurm_ai_%j.out
#SBATCH -e /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/logs/slurm_ai_%j.out
# Plan-B unlimited-ai insurance worker: grabs any ai node that returns to idle. Unlimited time
# (no 2h cycling). Auto-exits when global remaining hits 0 (worker's all_done). HF-offline + prewarm.
bash /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/scripts/adsr_gpu_worker.sh forward
