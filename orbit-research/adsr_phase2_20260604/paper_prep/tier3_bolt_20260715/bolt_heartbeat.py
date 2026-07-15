#!/usr/bin/env python3
"""Append-only ten-minute node heartbeat for BOLT Gate 0/1 execution."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path


OUT = Path(__file__).resolve().parent


def run(command: list[str]) -> str:
    return subprocess.run(command, text=True, capture_output=True, check=False).stdout.strip()


def sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True, choices=("an12", "an29"))
    parser.add_argument("--interval-seconds", type=int, default=600)
    parser.add_argument("--stop-file", default="BOLT_HEARTBEAT_STOP")
    args = parser.parse_args()
    host = socket.gethostname().split(".")[0]
    if host != args.node:
        raise RuntimeError(f"heartbeat expected {args.node}, running on {host}")
    output = OUT / f"BOLT_HEARTBEAT_{args.node}.log"
    stop = OUT / args.stop_file
    ledgers = [
        OUT / "BOLT_GATE0_LEDGER.jsonl",
        OUT / "BOLT_ROOT_TRAJECTORY_LEDGER.jsonl",
        OUT / "BOLT_CHECKPOINT_STATE_LEDGER.jsonl",
        OUT / "BOLT_ACTION_ATLAS_PILOT_LEDGER.jsonl",
    ]
    while not stop.exists():
        record = {
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "node": args.node,
            "gpu": run(["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"]).splitlines(),
            "bolt_processes": run(["pgrep", "-af", "bolt_(gate0|pilot_worker|heartbeat)"]).splitlines(),
            "ledger_line_counts": {path.name: line_count(path) for path in ledgers},
            "ledger_sha256": {path.name: sha(path) for path in ledgers},
        }
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
