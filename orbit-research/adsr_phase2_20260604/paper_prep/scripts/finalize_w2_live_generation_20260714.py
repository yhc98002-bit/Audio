#!/usr/bin/env python3
"""Audit a complete W2 live run and recover terminal generation status."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import soundfile as sf


ROOT = Path(__file__).resolve().parents[4]
PAPER = ROOT / "paper_prep"
LIVE = PAPER / "w2_execution_20260712/live_confirmation_20260713"
MANIFEST = PAPER / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_MANIFEST.csv"
PROCESS_CHECK = LIVE / "POSTRUN_PROCESS_CHECK.txt"
AUDIT = LIVE / "GENERATION_COMPLETION_AUDIT.json"
TERMINAL = LIVE / "LIVE_CONFIRM_TERMINAL_STATUS.txt"
COMPLETED = LIVE / "GENERATION_COMPLETED_TIMESTAMP.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def audit() -> dict:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    expected_units = {row["unit_id"] for row in manifest}
    if len(manifest) != 512 or len(expected_units) != 512:
        raise ValueError("frozen manifest is not 512 unique units")
    rows = [
        row
        for path in sorted((LIVE / "live_ledgers").glob("live_w*.jsonl"))
        for row in read_jsonl(path)
    ]
    keys = [
        (
            row["unit_id"],
            row["record_type"],
            str(row.get("slot", "")) if row["record_type"] == "slot" else "",
        )
        for row in rows
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("live ledgers contain duplicate record keys")
    selections = [row for row in rows if row["record_type"] == "unit_selection"]
    selected_by_unit = {row["unit_id"]: row for row in selections}
    if len(selections) != 512 or set(selected_by_unit) != expected_units:
        raise ValueError("unit-selection set does not match the frozen manifest")
    worker_counts = Counter(int(row["worker_index"]) for row in selections)
    if worker_counts != Counter({0: 128, 1: 128, 2: 128, 3: 128}):
        raise ValueError(f"worker shard counts are incomplete: {worker_counts}")
    slot_rows = [row for row in rows if row["record_type"] == "slot"]
    complete_slots = [row for row in slot_rows if row["status"] == "COMPLETE"]
    slots_by_path = {row["audio_path"]: row for row in complete_slots}
    if len(slots_by_path) != len(complete_slots):
        raise ValueError("completed slot audio paths are not unique")

    decoded = 0
    near_silent = 0
    checksum_mismatches = []
    metadata_mismatches = []
    for row in complete_slots:
        path = Path(row["audio_path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_hash = sha256(path)
        if actual_hash != row.get("audio_sha256"):
            checksum_mismatches.append(str(path))
            continue
        samples, sample_rate = sf.read(path, always_2d=True, dtype="float32")
        decoded += 1
        duration = len(samples) / sample_rate
        rms = float(math.sqrt(float((samples * samples).mean())))
        near_silent += int(rms < 1e-4)
        if sample_rate != int(row["sample_rate"]) or abs(duration - float(row["duration_seconds"])) > 1e-5:
            metadata_mismatches.append(str(path))
    if checksum_mismatches or metadata_mismatches or near_silent:
        raise ValueError(
            f"audio audit failed: checksums={len(checksum_mismatches)} "
            f"metadata={len(metadata_mismatches)} near_silent={near_silent}"
        )
    for row in selections:
        selected_path = row.get("selected_audio_path")
        if row["status"] == "COMPLETE":
            if selected_path not in slots_by_path:
                raise ValueError(f"selection does not point to a completed slot: {row['unit_id']}")
        elif row["status"] == "NO_COMPLETED_SLOT" and selected_path:
            raise ValueError(f"no-output selection unexpectedly names audio: {row['unit_id']}")
    if not PROCESS_CHECK.is_file() or "NO_ACTIVE_WORKERS" not in PROCESS_CHECK.read_text(encoding="utf-8"):
        raise ValueError("post-run process check does not prove workers exited")
    resumed_logs = sorted((LIVE / "logs").glob("worker_*_20260714T171855+0800.stderr.log"))
    fatal_tokens = ("Traceback", "CUDA out of memory", "Temporary failure in name resolution")
    fatal_logs = [
        str(path)
        for path in resumed_logs
        if any(token in path.read_text(encoding="utf-8", errors="replace") for token in fatal_tokens)
    ]
    if len(resumed_logs) != 4 or fatal_logs:
        raise ValueError(f"resumed worker log audit failed: logs={len(resumed_logs)} fatal={fatal_logs}")
    result = {
        "status": "COMPLETE_AUDIT_PASS",
        "manifest_rows": len(manifest),
        "ledger_rows": len(rows),
        "unique_record_keys": len(set(keys)),
        "slot_rows": len(slot_rows),
        "unit_selection_rows": len(selections),
        "worker_unit_counts": dict(sorted(worker_counts.items())),
        "record_status_counts": dict(Counter(row["status"] for row in rows)),
        "completed_audio_rows": len(complete_slots),
        "audio_files_decoded": decoded,
        "audio_checksum_mismatches": checksum_mismatches,
        "audio_metadata_mismatches": metadata_mismatches,
        "near_silent_audio": near_silent,
        "recovered_orphan_rows": sum(bool(row.get("recovered_orphan")) for row in rows),
        "latest_ledger_timestamp": max(row["timestamp"] for row in rows),
        "completion_observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_sha256": sha256(MANIFEST),
        "amendment_sha256": sha256(PAPER / "W2_AMENDMENT_20260712.md"),
        "launcher_exit_codes_captured": False,
        "launcher_limitation": "launcher source was edited while its shell was waiting; terminal status recovered from complete ledgers, exited-process evidence, worker logs, and full audio audit",
    }
    return result


def main() -> int:
    result = audit()
    AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMPLETED.write_text(result["completion_observed_at"] + "\n", encoding="utf-8")
    TERMINAL.write_text(
        "LIVE_CONFIRM_STATUS = GENERATION_COMPLETE_ANALYSIS_PENDING\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
