#!/bin/bash
#SBATCH -p temp
#SBATCH -w an22
#SBATCH --exclusive
#SBATCH -t 2:00:00
#SBATCH -J adsr_resume_temp
#SBATCH -o /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/logs/slurm_temp_%j.out
#SBATCH -e /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/runs/adsr_recollect_resume/logs/slurm_temp_%j.out
# Fire-and-forget temp-node resume chunk. Auto-runs on allocation; survives 2h preemption
# (records append continuously; next acquisition recomputes a smaller remaining set).
bash /HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion/scripts/adsr_gpu_worker.sh reverse
