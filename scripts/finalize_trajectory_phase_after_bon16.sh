#!/usr/bin/env bash
set -euo pipefail

run_root="runs/early_tweedie_bon16_subset_128_20260528_full01"
state="orbit-research/TRAJECTORY_PHASE_FINALIZER_STATE_2026-05-28.json"
log="orbit-research/TRAJECTORY_PHASE_FINALIZER_2026-05-28.log"
expected_records=2048
long_poll_seconds="${LONG_POLL_SECONDS:-1800}"
short_poll_seconds="${SHORT_POLL_SECONDS:-900}"

record_state() {
  local status="$1"
  local records="$2"
  python - "$state" "$status" "$records" <<'PY'
import json
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "status": sys.argv[2],
    "bon16_records": int(sys.argv[3]),
    "run_root": "runs/early_tweedie_bon16_subset_128_20260528_full01",
    "safety": {
        "rl_training_launched": False,
        "pruning_rl_launched": False,
        "phase_d_launched": False,
        "human_crowdsourcing_launched": False,
        "gate_v1_modified": False,
        "reward_definitions_changed": False,
    },
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

count_records() {
  wc -l "$run_root"/shard*/candidate_records.jsonl 2>/dev/null | awk '/ total$/ {print $1}'
}

next_poll_seconds() {
  if [ -n "${POLL_SECONDS:-}" ]; then
    echo "$POLL_SECONDS"
    return
  fi
  python - "$long_poll_seconds" "$short_poll_seconds" <<'PY'
import json
import sys
from pathlib import Path

long_poll = int(sys.argv[1])
short_poll = int(sys.argv[2])
path = Path("orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.json")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
    eta_values = [
        value for value in (
            payload.get("eta_hours"),
            payload.get("slowest_shard_eta_hours"),
        )
        if value is not None
    ]
    eta = max(float(value) for value in eta_values) if eta_values else None
except Exception:
    eta = None
print(long_poll if eta is not None and float(eta) > 3.0 else short_poll)
PY
}

{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] finalizer started"
  while true; do
    records="$(count_records || echo 0)"
    records="${records:-0}"
    record_state "WAITING_FOR_BON16" "$records"
    python scripts/write_trajectory_phase_live_status.py || true
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] bon16_records=$records/$expected_records"
    if [ -f "$run_root/launcher.exit" ]; then
      break
    fi
    sleep_seconds="$(next_poll_seconds)"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] next_poll_seconds=$sleep_seconds"
    sleep "$sleep_seconds"
  done

  launcher_exit="$(cat "$run_root/launcher.exit")"
  records="$(count_records || echo 0)"
  records="${records:-0}"
  if [ "$launcher_exit" != "0" ]; then
    record_state "BON16_FAILED" "$records"
    echo "BoN-16 launcher failed with exit=$launcher_exit"
    exit 1
  fi
  if [ "$records" -ne "$expected_records" ]; then
    record_state "BON16_INCOMPLETE" "$records"
    echo "BoN-16 record count mismatch: $records != $expected_records"
    exit 1
  fi

  record_state "RUNNING_BON16_ANALYSIS" "$records"
  python scripts/analyze_bon16_pruning_subset.py \
    --records "$run_root"/shard*/candidate_records.jsonl \
    --bon8-records runs/early_tweedie_validation_512_bon8_20260527_full01/shard*/candidate_records.jsonl \
    --run-root "$run_root"

  record_state "RUNNING_HUMAN_SPOTCHECK_AUDIO" "$records"
  scripts/launch_human_spotcheck_audio.sh

  record_state "WRITING_FINAL_REPORT" "$records"
  python scripts/write_trajectory_phase_final_report.py

  record_state "RUNNING_COMPLETION_CHECK" "$records"
  python scripts/verify_trajectory_phase_completion.py

  record_state "PASS" "$records"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] finalizer PASS"
} >> "$log" 2>&1
