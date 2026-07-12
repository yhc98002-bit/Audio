#!/usr/bin/env python3
"""Run a W2 instrument over a frozen retained-audio manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w2_instruments import (
    THRESHOLD,
    CalibratedCompositeInstrument,
    CurrentDemucsInstrument,
    DemucsPannsEnsembleInstrument,
    HumanCalibratedThresholdInstrument,
    ValidatedJudgeInstrument,
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row["record_id"] for row in read_jsonl(path) if row.get("status") == "PASS"}


def make_instrument(args: argparse.Namespace):
    if args.instrument == "current_demucs":
        return CurrentDemucsInstrument(args.device)
    if args.instrument == "human_calibrated_threshold":
        return HumanCalibratedThresholdInstrument(
            args.device, args.threshold, args.calibration_artifact
        )
    if args.instrument == "demucs_panns":
        return DemucsPannsEnsembleInstrument(
            args.device, args.panns_scores, args.panns_threshold, args.decision_rule
        )
    if args.instrument == "validated_judge":
        return ValidatedJudgeInstrument(args.judge_labels, args.judge_metadata)
    if args.instrument == "calibrated_auto":
        return CalibratedCompositeInstrument(args.device, args.calibration_artifact)
    raise ValueError(args.instrument)


def select_rows(
    rows: list[dict],
    max_rows: int,
    cohorts: set[str],
    num_shards: int = 1,
    shard_index: int = 0,
) -> list[dict]:
    if num_shards < 1 or shard_index not in range(num_shards):
        raise ValueError("invalid W2 shard specification")
    selected = [
        row
        for row in rows
        if row.get("media_available")
        and row.get("audio_path")
        and (not cohorts or row.get("cohort") in cohorts)
    ]
    selected.sort(key=lambda row: (row.get("cohort", ""), row["record_id"]))
    selected = [row for index, row in enumerate(selected) if index % num_shards == shard_index]
    return selected[:max_rows] if max_rows else selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--instrument",
        choices=["current_demucs", "human_calibrated_threshold", "demucs_panns", "validated_judge", "calibrated_auto"],
        required=True,
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--cohort", action="append", default=[])
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--dry-run-only", action="store_true")
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    parser.add_argument("--calibration-artifact", type=Path)
    parser.add_argument("--panns-scores", type=Path)
    parser.add_argument("--panns-threshold", type=float, default=0.5)
    parser.add_argument("--decision-rule", choices=["or", "and"], default="or")
    parser.add_argument("--judge-labels", type=Path)
    parser.add_argument("--judge-metadata", type=Path)
    args = parser.parse_args()
    rows = select_rows(
        read_jsonl(args.manifest),
        args.max_rows,
        set(args.cohort),
        args.num_shards,
        args.shard_index,
    )
    if not rows:
        raise ValueError("no available retained media selected")
    instrument = make_instrument(args)
    done = completed_ids(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for row in rows:
        if row["record_id"] in done:
            continue
        started = time.time()
        output = {
            "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "record_id": row["record_id"],
            "cohort": row["cohort"],
            "audio_path": row["audio_path"],
            "old_present": row.get("old_present", ""),
            "instrument": args.instrument,
            "num_shards": args.num_shards,
            "shard_index": args.shard_index,
            "dry_run_only": bool(args.dry_run_only),
            "status": "FAIL",
            "error": "",
        }
        try:
            score_row = getattr(instrument, "score_row", None)
            if score_row is not None:
                output.update(score_row(Path(row["audio_path"]), row))
            else:
                output.update(instrument.score(Path(row["audio_path"])))
            output["status"] = "PASS"
        except Exception as exc:  # noqa: BLE001 - exact failure belongs in ledger.
            output["error"] = f"{type(exc).__name__}: {exc}"
        output["elapsed_s"] = time.time() - started
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, sort_keys=True) + "\n")
        print(json.dumps(output, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
