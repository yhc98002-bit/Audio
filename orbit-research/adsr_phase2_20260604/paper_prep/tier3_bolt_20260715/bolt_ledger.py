#!/usr/bin/env python3
"""Append a fully specified action to the BOLT execution ledger."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
LEDGER = OUT / "BOLT_EXECUTION_LEDGER.jsonl"


def git_sha() -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()


def parse_json(value: str):
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError("artifact lists must be JSON arrays")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--inputs", type=parse_json, default=[])
    parser.add_argument("--outputs", type=parse_json, default=[])
    parser.add_argument("--manifest-hash", default=None)
    parser.add_argument("--model-checkpoint-hash", default=None)
    parser.add_argument("--environment-hash", default=None)
    parser.add_argument("--worker-gpu", default="coordinator/cpu")
    parser.add_argument("--result", required=True)
    parser.add_argument("--next-action", required=True)
    args = parser.parse_args()
    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "host_node": socket.gethostname(),
        "git_sha": git_sha(),
        "script": args.script,
        "full_command": args.command,
        "input_artifacts": args.inputs,
        "output_artifacts": args.outputs,
        "manifest_hash": args.manifest_hash,
        "model_checkpoint_hash": args.model_checkpoint_hash,
        "environment_hash": args.environment_hash,
        "worker_gpu": args.worker_gpu,
        "result": args.result,
        "next_action": args.next_action,
    }
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
