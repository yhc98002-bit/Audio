#!/usr/bin/env bash
# Fix the oversubscription concurrent-write race on rung-level aggregates.
#
# Background (2026-05-19): scripts/m1a_run_parallel_rungs.py spawns one
# `launch_baseline.py --seeds <single>` subprocess per (rung, seed). Each
# subprocess at line 776 of launch_baseline.py writes the rung-level
# aggregate `<rung_dir>/<split>/results.jsonl` containing ONLY its own
# seed's data. Last-writer-wins → the aggregate ends up with one seed's
# 256 rows instead of 3 seeds × 256 = 768 rows. The per-seed dirs
# `<rung_dir>/<split>/seed<N>/results.jsonl` are intact.
#
# This script repairs each rung's aggregate by concatenating per-seed
# files. Safe to run multiple times. Should be called after every M1a
# orchestrator invocation (i.e., once after dev and once after held-out)
# AND before compute_headroom_gate.py.
#
# Usage:
#   bash tools/merge_perseed_results.sh dev
#   bash tools/merge_perseed_results.sh held_out

set -euo pipefail
SPLIT="${1:-dev}"

RUNS_ROOT="${RUNS_ROOT:-runs}"
shopt -s nullglob

echo "=== merge per-seed → rung aggregate for split=${SPLIT} ==="
fixed=0
skipped=0
for rung_dir in "${RUNS_ROOT}"/*/"${SPLIT}"; do
    [[ -d "${rung_dir}" ]] || continue
    rung=$(basename "$(dirname "${rung_dir}")")
    seed_files=( "${rung_dir}"/seed*/results.jsonl )
    if (( ${#seed_files[@]} == 0 )); then
        printf "  skip %-35s no seed*/results.jsonl found\n" "${rung}"
        skipped=$((skipped+1))
        continue
    fi
    target="${rung_dir}/results.jsonl"
    tmp="${target}.merge.$$"
    cat "${seed_files[@]}" > "${tmp}"
    rows=$(wc -l < "${tmp}")
    mv -f "${tmp}" "${target}"
    printf "  fix  %-35s %d per-seed → %d rows → %s\n" "${rung}" "${#seed_files[@]}" "${rows}" "${target}"
    fixed=$((fixed+1))
done
echo "=== done: fixed=${fixed} skipped=${skipped} ==="
