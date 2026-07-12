#!/usr/bin/env python3
"""Score PI Label-A gold with Demucs and PANNs for W2 calibration."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import time
from pathlib import Path

from w2_instruments import CurrentDemucsInstrument, LivePannsInstrument, sha256_file


def read_csvs(paths: list[Path]) -> list[dict[str, str]]:
    output = []
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            output.extend(csv.DictReader(handle))
    ids = [row["clip_id"] for row in output]
    if len(ids) != len(set(ids)):
        raise ValueError("PI-gold calibration inputs have duplicate clip_id")
    return output


def completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    rows = (
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return {row["clip_id"] for row in rows if row.get("status") == "PASS"}


def select_shard(rows: list[dict[str, str]], count: int, index: int) -> list[dict[str, str]]:
    if count < 1 or index not in range(count):
        raise ValueError("invalid PI-gold shard specification")
    return [row for position, row in enumerate(sorted(rows, key=lambda row: row["clip_id"])) if position % count == index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    args = parser.parse_args()
    rows = select_shard(read_csvs(args.manifest), args.num_shards, args.shard_index)
    done = completed(args.output)
    demucs = CurrentDemucsInstrument(args.device)
    panns = LivePannsInstrument(args.device, 0.5)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for row in rows:
        if row["clip_id"] in done:
            continue
        started = time.time()
        path = Path(row["clip_path"])
        output = {
            "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "clip_id": row["clip_id"],
            "audio_path": str(path.resolve()),
            "audio_sha256": row["audio_sha256"],
            "true_label": row["true_label"],
            "split": row["split"],
            "rating_source": row["rating_source"],
            "num_shards": args.num_shards,
            "shard_index": args.shard_index,
            "status": "FAIL",
            "error": "",
        }
        try:
            if not path.is_file() or sha256_file(path) != row["audio_sha256"]:
                raise ValueError("PI-gold media missing or SHA-256 mismatch")
            demucs_result = demucs.score(path)
            panns_result = panns.score(path)
            output.update(
                {
                    "demucs_vocal_energy_ratio": demucs_result["vocal_energy_ratio"],
                    "demucs_near_silent": demucs_result["near_silent"],
                    "panns_score": panns_result["panns_score"],
                    "panns_top_vocal_class": panns_result["panns_top_vocal_class"],
                    "status": "PASS",
                }
            )
        except Exception as exc:  # noqa: BLE001
            output["error"] = f"{type(exc).__name__}: {exc}"
        output["elapsed_s"] = time.time() - started
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        print(json.dumps(output, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
