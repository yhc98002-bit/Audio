#!/usr/bin/env python3
"""Fail-closed merge and completeness audit for sharded W2 results."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def merge(manifest: list[dict], shards: list[list[dict]]) -> tuple[list[dict], dict]:
    expected = {
        row["record_id"]: row
        for row in manifest
        if row.get("media_available") and row.get("audio_path")
    }
    if len(expected) != sum(
        bool(row.get("media_available") and row.get("audio_path")) for row in manifest
    ):
        raise ValueError("retained manifest contains duplicate record IDs")
    stored_demucs_rows = 0
    stored_demucs_mismatches = []
    for row in manifest:
        if row.get("old_vocal_energy_ratio", "") == "":
            continue
        stored_demucs_rows += 1
        near_silent = row.get("old_near_silent", False)
        if not isinstance(near_silent, bool):
            raise ValueError("stored near-silent flag must be boolean")
        expected_present = int(
            float(row["old_vocal_energy_ratio"]) >= VOCAL_PRESENCE_THRESHOLD
            and not near_silent
        )
        if expected_present != int(row["old_present"]):
            stored_demucs_mismatches.append(row["record_id"])
    if stored_demucs_mismatches:
        raise ValueError(
            f"frozen Demucs score/label mismatch: {stored_demucs_mismatches[:5]}"
        )
    merged = {}
    failures = []
    for shard in shards:
        for row in shard:
            record_id = row.get("record_id")
            if record_id not in expected:
                raise ValueError(f"W2 result is outside retained manifest: {record_id}")
            if record_id in merged:
                raise ValueError(f"duplicate W2 result across shards: {record_id}")
            merged[record_id] = row
            if row.get("status") != "PASS":
                failures.append(row)
    missing = sorted(set(expected) - set(merged))
    if missing or failures:
        raise ValueError(f"W2 incomplete: missing={len(missing)} failures={len(failures)}")
    rows = [merged[record_id] for record_id in sorted(merged)]
    source_counts = Counter(
        row.get("demucs_score_source") or "live_recomputed_initial_pass_pre_optimization"
        for row in rows
    )
    report = {
        "status": "PASS_COMPLETE_RETAINED_AUDIO",
        "expected_rows": len(expected),
        "merged_rows": len(rows),
        "failures": 0,
        "missing": 0,
        "cohort_counts": dict(sorted(Counter(row["cohort"] for row in rows).items())),
        "instrument_counts": dict(sorted(Counter(row["instrument_id"] for row in rows).items())),
        "demucs_score_source_counts": dict(sorted(source_counts.items())),
        "stored_demucs_rows_checked": stored_demucs_rows,
        "stored_demucs_threshold_mismatches": 0,
    }
    return rows, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shards", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    rows, report = merge(read_jsonl(args.manifest), [read_jsonl(path) for path in args.shards])
    if args.output.exists() or args.report.exists():
        raise FileExistsError("refusing to overwrite W2 merged outputs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
