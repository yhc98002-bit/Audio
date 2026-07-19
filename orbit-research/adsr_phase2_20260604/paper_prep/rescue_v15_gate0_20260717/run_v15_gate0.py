#!/usr/bin/env python3
"""Phase CLI for the frozen ACE-Step v1.5 Gate-0 bundle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from v15_gate0_runtime import (
    TASK_DIR,
    collect_provenance,
    finalize_reports,
    process_main_continuations,
    record_test_results,
    run_fork_calibration,
    run_reference_worker,
    run_true_rollover,
)


def rank_world(args: argparse.Namespace) -> tuple[int, int]:
    return int(os.environ.get("LOCAL_RANK", args.rank)), int(os.environ.get("WORLD_SIZE", args.world_size))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("provenance", "calibrate", "reference-worker", "continuation-worker", "rollover", "record-tests", "finalize"),
    )
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--world-size", type=int, default=1)
    parser.add_argument("--focused-log", type=Path)
    parser.add_argument("--full-log", type=Path)
    parser.add_argument("--focused-rc", type=int)
    parser.add_argument("--full-rc", type=int)
    args = parser.parse_args()

    if args.phase == "provenance":
        result = collect_provenance()
    elif args.phase == "calibrate":
        result = run_fork_calibration()
    elif args.phase == "reference-worker":
        rank, world = rank_world(args)
        run_reference_worker(rank, world)
        result = {"phase": args.phase, "rank": rank, "world_size": world, "status": "PASS"}
    elif args.phase == "continuation-worker":
        rank, world = rank_world(args)
        process_main_continuations(rank, world)
        result = {"phase": args.phase, "rank": rank, "world_size": world, "status": "PASS"}
    elif args.phase == "rollover":
        result = run_true_rollover()
    elif args.phase == "record-tests":
        if None in (args.focused_log, args.full_log, args.focused_rc, args.full_rc):
            parser.error("record-tests requires both logs and return codes")
        record_test_results(args.focused_log, args.full_log, args.focused_rc, args.full_rc)
        result = {"status": "PASS" if args.focused_rc == 0 and args.full_rc == 0 else "FAIL"}
    else:
        result = finalize_reports()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

