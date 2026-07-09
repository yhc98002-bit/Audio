"""Write live status for the trajectory-aware phase."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ROOT = Path("runs/early_tweedie_bon16_subset_128_20260528_full01")
EXPECTED_RECORDS = 2048
EXPECTED_SHARD_RECORDS = 256
OUT_JSON = Path("orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.json")
OUT_MD = Path("orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_2026-05-28.md")
OUT_HISTORY = Path("orbit-research/TRAJECTORY_PHASE_LIVE_STATUS_HISTORY_2026-05-28.jsonl")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_utc(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _tmux_has(name: str) -> bool:
    try:
        out = subprocess.check_output(["tmux", "has-session", "-t", name], stderr=subprocess.DEVNULL)
    except Exception:
        return False
    return out == b""


def _error_matches() -> list[str]:
    patterns = ("Traceback", "RuntimeError", "CUDA out of memory", "Exception")
    matches = []
    for path in sorted(RUN_ROOT.glob("*stderr.log")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if pattern in text:
                matches.append(f"{path}:{pattern}")
    return matches


def _history_rows() -> list[dict[str, Any]]:
    if not OUT_HISTORY.exists():
        return []
    rows = []
    with OUT_HISTORY.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def main() -> int:
    shard_counts = {}
    shard_mtimes = {}
    for path in sorted(RUN_ROOT.glob("shard*/candidate_records.jsonl")):
        shard = path.parent.name
        shard_counts[shard] = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        shard_mtimes[shard] = path.stat().st_mtime
    total = sum(shard_counts.values())
    started = None
    start_path = RUN_ROOT / "launch_started_utc.txt"
    if start_path.exists():
        started = _parse_utc(start_path.read_text(encoding="utf-8"))
    now = time.time()
    history = _history_rows()
    last_increase_by_shard = {}
    previous_counts = history[-1].get("shard_counts", {}) if history else {}
    for shard, count in shard_counts.items():
        last_time = None
        last_count = None
        for row in reversed(history):
            row_counts = row.get("shard_counts") or {}
            if shard not in row_counts:
                continue
            observed = int(row_counts[shard])
            if last_count is None:
                last_count = observed
            if observed < count:
                last_time = _parse_utc(str(row.get("generated_utc", "")))
                break
        last_increase_by_shard[shard] = {
            "previous_count": int(previous_counts.get(shard, 0)) if previous_counts else None,
            "last_increase_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_time)) if last_time else None,
            "stale_hours": ((now - last_time) / 3600.0) if last_time else None,
        }
    elapsed_h = (now - started) / 3600.0 if started else None
    records_per_h = total / elapsed_h if elapsed_h and elapsed_h > 0 else None
    remaining = max(0, EXPECTED_RECORDS - total)
    eta_h = remaining / records_per_h if records_per_h and records_per_h > 0 else None
    shard_status = {}
    shard_eta_values = []
    for shard, count in shard_counts.items():
        shard_rate = count / elapsed_h if elapsed_h and elapsed_h > 0 else None
        shard_remaining = max(0, EXPECTED_SHARD_RECORDS - count)
        shard_eta = shard_remaining / shard_rate if shard_rate and shard_rate > 0 else None
        if shard_eta is not None:
            shard_eta_values.append(shard_eta)
        shard_status[shard] = {
            "records": count,
            "expected_records": EXPECTED_SHARD_RECORDS,
            "remaining_records": shard_remaining,
            "progress_fraction": count / EXPECTED_SHARD_RECORDS,
            "records_per_hour": shard_rate,
            "eta_hours": shard_eta,
            "file_mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(shard_mtimes.get(shard, 0.0))),
            "file_stale_hours": ((now - shard_mtimes[shard]) / 3600.0) if shard in shard_mtimes else None,
            **last_increase_by_shard.get(shard, {}),
        }
    slowest_shard = None
    if shard_status:
        slowest_shard = max(
            shard_status.items(),
            key=lambda item: item[1]["eta_hours"] if item[1]["eta_hours"] is not None else float("inf"),
        )[0]
    launcher_exit = None
    launcher_exit_path = RUN_ROOT / "launcher.exit"
    if launcher_exit_path.exists():
        launcher_exit = launcher_exit_path.read_text(encoding="utf-8").strip()

    payload = {
        "generated_utc": _now_utc(),
        "run_root": str(RUN_ROOT),
        "expected_records": EXPECTED_RECORDS,
        "total_records": total,
        "remaining_records": remaining,
        "progress_fraction": total / EXPECTED_RECORDS,
        "shard_counts": shard_counts,
        "shard_status": shard_status,
        "elapsed_hours": elapsed_h,
        "records_per_hour": records_per_h,
        "eta_hours": eta_h,
        "slowest_shard": slowest_shard,
        "slowest_shard_eta_hours": max(shard_eta_values) if shard_eta_values else None,
        "launcher_exit": launcher_exit,
        "tmux": {
            "bon16": _tmux_has("early_tweedie_bon16_128_20260528"),
            "finalizer": _tmux_has("trajectory_phase_finalizer_20260528"),
        },
        "error_matches": _error_matches(),
        "status": "COMPLETE" if total == EXPECTED_RECORDS and launcher_exit == "0" else "RUNNING",
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUT_HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
    lines = [
        "# Trajectory Phase Live Status",
        "",
        f"Generated UTC: `{payload['generated_utc']}`",
        f"Status: `{payload['status']}`",
        "",
        f"- BoN-16 records: `{total}/{EXPECTED_RECORDS}`",
        f"- Progress: `{payload['progress_fraction']:.3%}`",
        f"- Records/hour: `{records_per_h:.2f}`" if records_per_h is not None else "- Records/hour: `NA`",
        f"- ETA hours: `{eta_h:.2f}`" if eta_h is not None else "- ETA hours: `NA`",
        f"- Slowest shard ETA hours: `{payload['slowest_shard_eta_hours']:.2f}` ({payload['slowest_shard']})"
        if payload["slowest_shard_eta_hours"] is not None else "- Slowest shard ETA hours: `NA`",
        f"- BoN-16 tmux alive: `{payload['tmux']['bon16']}`",
        f"- Finalizer tmux alive: `{payload['tmux']['finalizer']}`",
        f"- Error matches: `{len(payload['error_matches'])}`",
        "",
        "## Shards",
        "",
        "| shard | records | progress | records/hour | eta hours | file stale hours |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for shard, status in shard_status.items():
        eta = status["eta_hours"]
        rate = status["records_per_hour"]
        stale = status.get("file_stale_hours")
        lines.append(
            f"| {shard} | {status['records']}/{EXPECTED_SHARD_RECORDS} | "
            f"{status['progress_fraction']:.3%} | "
            f"{rate:.2f}" if rate is not None else f"| {shard} | {status['records']}/{EXPECTED_SHARD_RECORDS} | {status['progress_fraction']:.3%} | NA"
        )
        lines[-1] += f" | {eta:.2f}" if eta is not None else " | NA"
        lines[-1] += f" | {stale:.2f} |" if stale is not None else " | NA |"
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "records": total, "eta_hours": eta_h, "history": str(OUT_HISTORY)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
