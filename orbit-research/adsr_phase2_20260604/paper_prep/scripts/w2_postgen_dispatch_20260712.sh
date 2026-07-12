#!/usr/bin/env bash
set -euo pipefail

NODE=${1:?usage: w2_postgen_dispatch_20260712.sh an12|an29}
ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
PAPER="$ROOT/paper_prep/w2_execution_20260712"
LOG="$PAPER/postgen_dispatch_${NODE}.log"
PYTHON=${AUDIO_PRM_PYTHON:-/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python}
if [ ! -x "$PYTHON" ]; then
  echo "audio-prm Python is unavailable: $PYTHON" >&2
  exit 3
fi

count_unique_pass() {
  local directory=$1
  local pattern=$2
  local key=$3
  "$PYTHON" - "$directory" "$pattern" "$key" <<'PY'
import glob,json,sys
directory,pattern,key=sys.argv[1:]
values=set()
for path in glob.glob(directory+'/'+pattern):
    with open(path,encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            row=json.loads(line)
            if row.get('status')=='PASS':
                values.add(str(row[key]))
print(len(values))
PY
}

while true; do
  spine=$(count_unique_pass "$PAPER/spine_reconstruction/generation_ledgers" 'generation_w*.jsonl' task_id)
  positive=$(count_unique_pass "$PAPER/factorial/positive_correction_ledgers" 'positive_generation_w*.jsonl' task_id)
  printf '%s node=%s spine=%s/4096 positive=%s/1024\n' "$(date --iso-8601=seconds)" "$NODE" "$spine" "$positive" >> "$LOG"
  if [ "$spine" -eq 4096 ] && { [ "$NODE" = an12 ] || [ "$positive" -eq 1024 ]; }; then
    break
  fi
  sleep 60
done

source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh

if [ "$NODE" = an29 ]; then
  tmux kill-session -t adsr_w2_spine_regen_20260712_an29 2>/dev/null || true
  tmux kill-session -t adsr_w2_factorial_positive_v2_20260712 2>/dev/null || true
  spine_session=adsr_w2_spine_score_20260712_an29
  positive_session=adsr_w2_factorial_positive_score_20260712
  tmux kill-session -t "$spine_session" 2>/dev/null || true
  tmux kill-session -t "$positive_session" 2>/dev/null || true
  first=1
  for spec in 0:0 1:2 2:3 3:4 4:6 5:7; do
    worker=${spec%%:*}; gpu=${spec##*:}
    cmd="cd $ROOT && module load anaconda3/2023.09 && source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh && conda activate audio-prm && export CUDA_VISIBLE_DEVICES=$gpu && python paper_prep/scripts/w2_spine_reconstruct_20260712.py score --worker-index $worker --num-workers 7 2>&1 | tee -a paper_prep/w2_execution_20260712/spine_reconstruction/logs/score_an29_w${worker}.log; sleep 86400"
    if [ "$first" -eq 1 ]; then
      tmux new-session -d -s "$spine_session" -n "w$worker" "bash -lc '$cmd'"; first=0
    else
      tmux new-window -t "$spine_session" -n "w$worker" "bash -lc '$cmd'"
    fi
  done
  first=1
  for spec in 0:0 1:2 2:3 3:4; do
    worker=${spec%%:*}; gpu=${spec##*:}
    cmd="cd $ROOT && module load anaconda3/2023.09 && source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh && conda activate audio-prm && export CUDA_VISIBLE_DEVICES=$gpu && python paper_prep/scripts/w2_factorial_positive_correction_20260712.py score --worker-index $worker --num-workers 4 2>&1 | tee -a paper_prep/w2_execution_20260712/factorial/logs/positive_v2_score_w${worker}.log; sleep 86400"
    if [ "$first" -eq 1 ]; then
      tmux new-session -d -s "$positive_session" -n "w$worker" "bash -lc '$cmd'"; first=0
    else
      tmux new-window -t "$positive_session" -n "w$worker" "bash -lc '$cmd'"
    fi
  done
  echo "$(date --iso-8601=seconds) launched spine scoring workers 0-5 and positive scoring workers 0-3" >> "$LOG"
elif [ "$NODE" = an12 ]; then
  tmux kill-session -t adsr_w2_spine_regen_20260712_an12 2>/dev/null || true
  session=adsr_w2_spine_score_20260712_an12
  tmux kill-session -t "$session" 2>/dev/null || true
  cmd="cd $ROOT && module load anaconda3/2023.09 && source /APP/u22/ai_x86/anaconda3/2023.09/etc/profile.d/conda.sh && conda activate audio-prm && export CUDA_VISIBLE_DEVICES=5 && python paper_prep/scripts/w2_spine_reconstruct_20260712.py score --worker-index 6 --num-workers 7 2>&1 | tee -a paper_prep/w2_execution_20260712/spine_reconstruction/logs/score_an12_w6.log; sleep 86400"
  tmux new-session -d -s "$session" "bash -lc '$cmd'"
  echo "$(date --iso-8601=seconds) launched spine scoring worker 6" >> "$LOG"
else
  echo "unsupported node $NODE" >&2
  exit 2
fi
