#!/usr/bin/env bash
set -euo pipefail

NODE=${1:?usage: w2_launch_spine_recovery_20260712.sh an12|an29 generate|score}
PHASE=${2:?usage: w2_launch_spine_recovery_20260712.sh an12|an29 generate|score}
ROOT=${MPRM_REPO_ROOT:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion}
PYTHON=${MPRM_TORCH251_PYTHON:-/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/w2-torch251/bin/python}
OUT_REL=${MPRM_W2_SPINE_OUT:-paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery}
OUT="$ROOT/$OUT_REL"
PROBE="$ROOT/paper_prep/w2_execution_20260712/spine_torch251_fidelity_probe/SPINE_TORCH251_FIDELITY_AUDIT.json"
MIN_FREE_MIB=${MPRM_MIN_FREE_MIB:-10000}

case "$NODE" in
  an12) offset=0 ;;
  an29) offset=8 ;;
  *) echo "unsupported node: $NODE" >&2; exit 2 ;;
esac
case "$PHASE" in
  generate|score) ;;
  *) echo "unsupported phase: $PHASE" >&2; exit 2 ;;
esac

if [ ! -x "$PYTHON" ]; then
  echo "torch-2.5.1 Python is unavailable: $PYTHON" >&2
  exit 3
fi
"$PYTHON" - <<'PY'
import torch
import torchaudio
assert torch.__version__ == "2.5.1+cu121", torch.__version__
assert torchaudio.__version__ == "2.5.1+cu121", torchaudio.__version__
assert torch.cuda.is_available()
PY

"$PYTHON" - "$PROBE" "$OUT/SPINE_RECONSTRUCTION_MANIFEST.csv" "$OUT" "$PHASE" <<'PY'
import csv, glob, json, os, sys
probe_path, manifest_path, out, phase = sys.argv[1:]
probe = json.load(open(probe_path, encoding="utf-8"))
if probe.get("full_replay_authorized_by_probe") is not True:
    raise SystemExit("51-row fidelity probe has not authorized full replay")
with open(manifest_path, newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
if len(rows) != 4096 or len({row["task_id"] for row in rows}) != 4096:
    raise SystemExit("recovery manifest is not exactly 4096 unique tasks")
if phase == "score":
    latest = {}
    failures = []
    for path in glob.glob(os.path.join(out, "generation_ledgers", "generation_w*.jsonl")):
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            if row.get("status") == "PASS":
                latest[row["task_id"]] = row
            else:
                failures.append(row.get("task_id", "UNKNOWN"))
    if len(latest) != 4096 or failures:
        raise SystemExit(f"generation gate failed: pass={len(latest)}, failures={len(failures)}")
PY

mapfile -t free_memory < <(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
if [ "${#free_memory[@]}" -ne 8 ]; then
  echo "expected eight GPUs, found ${#free_memory[@]}" >&2
  exit 4
fi
for gpu in 0 1 2 3 4 5 6 7; do
  value=${free_memory[$gpu]// /}
  if [ "$value" -lt "$MIN_FREE_MIB" ]; then
    echo "GPU $gpu has ${value} MiB free, below ${MIN_FREE_MIB} MiB" >&2
    exit 5
  fi
done

session="adsr_w2_spine_torch251_${PHASE}_${NODE}"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "session already exists: $session" >&2
  exit 6
fi
mkdir -p "$OUT/logs"
first=1
for gpu in 0 1 2 3 4 5 6 7; do
  worker=$((offset + gpu))
  log="$OUT/logs/${PHASE}_${NODE}_w${worker}.log"
  command="cd $ROOT && export CUDA_VISIBLE_DEVICES=$gpu MPRM_W2_SPINE_OUT=$OUT_REL && $PYTHON paper_prep/scripts/w2_spine_reconstruct_20260712.py $PHASE --worker-index $worker --num-workers 16 2>&1 | tee -a $log; sleep 86400"
  if [ "$first" -eq 1 ]; then
    tmux new-session -d -s "$session" -n "w$worker" "bash -lc '$command'"
    first=0
  else
    tmux new-window -t "$session" -n "w$worker" "bash -lc '$command'"
  fi
done

printf '%s node=%s phase=%s workers=%s-%s min_free_mib=%s\n' \
  "$(date --iso-8601=seconds)" "$NODE" "$PHASE" "$offset" "$((offset + 7))" "$MIN_FREE_MIB"
