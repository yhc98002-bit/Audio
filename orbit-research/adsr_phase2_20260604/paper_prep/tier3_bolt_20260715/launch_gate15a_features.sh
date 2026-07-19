#!/usr/bin/env bash
set -euo pipefail

root=/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion
base=orbit-research/adsr_phase2_20260604/paper_prep/tier3_bolt_20260715
hosts=(an12 an12 an12 an12 an12 an12 an29 an29)
gpus=(1 2 3 5 6 7 6 7)
pids=()

for worker in "${!hosts[@]}"; do
    host=${hosts[$worker]}
    gpu=${gpus[$worker]}
    log="${base}/gate15a_logs/feature_worker_${worker}_of_8_${host}_gpu${gpu}.log"
    used=$(ssh "${host}" "nvidia-smi -i ${gpu} --query-gpu=memory.used --format=csv,noheader,nounits")
    if (( used > 100 )); then
        printf 'refusing occupied device: host=%s gpu=%s used_mib=%s\n' "${host}" "${gpu}" "${used}" >&2
        exit 2
    fi
    ssh "${host}" "bash -lc 'cd ${root} && module load anaconda3/2023.09 && CUDA_VISIBLE_DEVICES=${gpu} conda run -n audio-prm python ${base}/bolt_gate15a_features.py extract --worker-index ${worker} --num-workers 8 > ${log} 2>&1'" &
    pids+=("$!")
    printf 'launched worker=%s host=%s gpu=%s pid=%s log=%s\n' \
        "${worker}" "${host}" "${gpu}" "${pids[-1]}" "${log}"
done

status=0
for index in "${!pids[@]}"; do
    if wait "${pids[$index]}"; then
        printf 'completed worker=%s host=%s gpu=%s status=PASS\n' \
            "${index}" "${hosts[$index]}" "${gpus[$index]}"
    else
        printf 'completed worker=%s host=%s gpu=%s status=FAIL\n' \
            "${index}" "${hosts[$index]}" "${gpus[$index]}" >&2
        status=1
    fi
done
exit "${status}"
