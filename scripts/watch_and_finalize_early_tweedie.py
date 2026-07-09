#!/usr/bin/env python3
"""Low-frequency CPU-only watcher for Track A finalization.

This utility polls the Track A run root and invokes
``scripts/finalize_early_tweedie_validation.py`` only after the run is complete.
It does not import GPU libraries, does not start Track C, and does not write to
the Track A run directory.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, TextIO


DEFAULT_RUN_ROOT = Path("runs/early_tweedie_validation_512_bon8_20260527_full01")
DEFAULT_LOG = Path("orbit-research/codex-imports/EARLY_TWEEDIE_FINALIZER_WATCHER_2026-05-27.log")
DEFAULT_STATE = Path("orbit-research/codex-imports/EARLY_TWEEDIE_FINALIZER_WATCHER_2026-05-27.json")
DEFAULT_LOCK = Path("orbit-research/codex-imports/EARLY_TWEEDIE_FINALIZER_WATCHER_2026-05-27.lock")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{_now()} {message}\n")


def _count_records(run_root: Path) -> int:
    total = 0
    for path in sorted(run_root.glob("shard*/candidate_records.jsonl")):
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            total += sum(1 for line in f if line.strip())
    return total


def _state(run_root: Path, expected_records: int) -> dict[str, Any]:
    launcher_exit = run_root / "launcher.exit"
    launch_finished = run_root / "launch_finished_utc.txt"
    records = _count_records(run_root) if run_root.exists() else 0
    exit_value = launcher_exit.read_text(encoding="utf-8", errors="ignore").strip() if launcher_exit.exists() else None
    ready = (
        run_root.exists()
        and records == expected_records
        and launcher_exit.exists()
        and exit_value == "0"
        and launch_finished.exists()
    )
    return {
        "timestamp_utc": _now(),
        "run_root": str(run_root),
        "expected_records": expected_records,
        "records": records,
        "launcher_exit_exists": launcher_exit.exists(),
        "launcher_exit": exit_value,
        "launch_finished_exists": launch_finished.exists(),
        "ready": ready,
    }


def _write_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _acquire_lock(path: Path, log_path: Path) -> TextIO | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _append_log(log_path, f"watcher_already_running lock_path={path}")
        lock_file.close()
        return None
    lock_file.write(f"pid={os.getpid()} started_utc={_now()}\n")
    lock_file.flush()
    return lock_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--expected-records", type=int, default=4096)
    parser.add_argument("--poll-seconds", type=int, default=600)
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--once", action="store_true", help="Poll once and exit without sleeping.")
    args = parser.parse_args()

    lock_file = None if args.once else _acquire_lock(args.lock_path, args.log_path)
    if not args.once and lock_file is None:
        return 0

    _append_log(args.log_path, "watcher_start")
    while True:
        data = _state(args.run_root, args.expected_records)
        _write_state(args.state_path, data)
        _append_log(
            args.log_path,
            "poll records={records}/{expected_records} launcher_exit={launcher_exit} "
            "launch_finished={launch_finished_exists} ready={ready}".format(**data),
        )
        if data["ready"]:
            _append_log(args.log_path, "ready_run_finalizer")
            cmd = [sys.executable, "scripts/finalize_early_tweedie_validation.py"]
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as exc:
                _append_log(args.log_path, f"finalizer_failed exit_code={exc.returncode}")
                return int(exc.returncode) or 1
            _append_log(args.log_path, "finalizer_pass")
            return 0
        if args.once:
            return 0
        time.sleep(max(60, int(args.poll_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
