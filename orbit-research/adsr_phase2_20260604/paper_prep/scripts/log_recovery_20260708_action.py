#!/usr/bin/env python3
"""Append one recovery action to the 2026-07-08 execution ledger."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "paper_prep" / "execution_20260708" / "CODEX_MODEL_SCOPE_RECOVERY_LEDGER.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host-node", default=socket.gethostname())
    parser.add_argument("--command", required=True)
    parser.add_argument("--inputs", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--status", required=True)
    parser.add_argument("--next-action", required=True)
    args = parser.parse_args()

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    row = {
        "timestamp": timestamp,
        "host_node": args.host_node,
        "command": args.command,
        "input_artifacts": args.inputs,
        "output_artifacts": args.outputs,
        "status": args.status,
        "next_action": args.next_action,
        "cwd": os.getcwd(),
    }
    if not LEDGER.exists():
        LEDGER.write_text(
            "# CODEX ModelScope Recovery Ledger\n\n"
            "Append-only JSONL entries. Secrets are not recorded.\n\n"
            "```jsonl\n",
            encoding="utf-8",
        )
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
