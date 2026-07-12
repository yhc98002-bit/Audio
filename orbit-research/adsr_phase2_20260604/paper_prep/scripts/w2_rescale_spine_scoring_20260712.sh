#!/usr/bin/env bash
set -euo pipefail

NODE=${1:?usage: w2_rescale_spine_scoring_20260712.sh an12|an29}
ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
PYTHON=${AUDIO_PRM_PYTHON:-/HOME/paratera_xy/pxy1289/.conda/envs/audio-prm/bin/python}
LOG_DIR="$ROOT/paper_prep/w2_execution_20260712/spine_reconstruction/logs"

case "$NODE" in
  an12)
    old_session=adsr_w2_spine_score_20260712_an12
    new_session=adsr_w2_spine_score16_20260712_an12
    worker_offset=0
    ;;
  an29)
    old_session=adsr_w2_spine_score_20260712_an29
    new_session=adsr_w2_spine_score16_20260712_an29
    worker_offset=8
    ;;
  *)
    echo "unsupported node: $NODE" >&2
    exit 2
    ;;
esac

tmux kill-session -t "$old_session" 2>/dev/null || true
tmux kill-session -t "$new_session" 2>/dev/null || true
sleep 3
if pgrep -f 'python paper_prep/scripts/w2_spine_reconstruct_20260712.py score' >/dev/null; then
  echo "old spine scoring process survived tmux handoff on $NODE" >&2
  exit 3
fi

first=1
for gpu in 0 1 2 3 4 5 6 7; do
  worker=$((worker_offset + gpu))
  log="$LOG_DIR/score16_${NODE}_w${worker}.log"
  command="cd $ROOT && export CUDA_VISIBLE_DEVICES=$gpu && $PYTHON paper_prep/scripts/w2_spine_reconstruct_20260712.py score --worker-index $worker --num-workers 16 2>&1 | tee -a $log; sleep 86400"
  if [ "$first" -eq 1 ]; then
    tmux new-session -d -s "$new_session" -n "w$worker" "bash -lc '$command'"
    first=0
  else
    tmux new-window -t "$new_session" -n "w$worker" "bash -lc '$command'"
  fi
done

printf '%s node=%s launched workers=%s-%s num_workers=16\n' \
  "$(date --iso-8601=seconds)" "$NODE" "$worker_offset" "$((worker_offset + 7))"
