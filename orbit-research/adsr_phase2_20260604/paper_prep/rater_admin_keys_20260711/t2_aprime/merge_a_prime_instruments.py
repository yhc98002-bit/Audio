#!/usr/bin/env python3
"""Fail-closed merge of human-core and human/validated-judge A-prime ratings."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def find_root(path: Path) -> Path:
    for candidate in path.parents:
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from rating_provenance import (  # noqa: E402
    parse_judge_metrics,
    parse_rating_source,
    require_human_source,
    sha256_file,
    validate_a_prime_rating_provenance,
)
from bundle_response_io import remap_bundle_rows  # noqa: E402


JUDGE_OUTPUT_FIELDS = (
    "judge_validation_status",
    "judge_model_id",
    "judge_gold_set_hash",
    "judge_calibration_metrics",
    "judge_raw_response_ledger",
    "judge_raw_response_ledger_sha256",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def unique_index(rows: list[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    output = {}
    for row in rows:
        value = row.get(key, "").strip()
        if not value or value in output:
            raise ValueError(f"{label} has blank or duplicate {key}: {value!r}")
        output[value] = row
    return output


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("refusing to write an empty A-prime merge")
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_judge_metadata(records: list[dict]) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for record in records:
        if record.get("validation_status") != "PASS":
            raise ValueError("judge metadata validation_status must be PASS")
        model_id = str(record.get("model_id", "")).strip()
        gold_hash = str(record.get("gold_set_hash", "")).strip()
        source = parse_rating_source(f"judge:{model_id}:validated:{gold_hash}")
        metrics = parse_judge_metrics(record.get("calibration_metrics", {}))
        raw_ledger = Path(str(record.get("raw_response_ledger", "")).strip()).resolve()
        if not raw_ledger.is_file():
            raise ValueError("judge metadata raw_response_ledger does not exist")
        prepared = {
            "judge_validation_status": "PASS",
            "judge_model_id": source.identity,
            "judge_gold_set_hash": source.gold_set_hash,
            "judge_calibration_metrics": json.dumps(metrics, sort_keys=True),
            "judge_raw_response_ledger": str(raw_ledger),
            "judge_raw_response_ledger_sha256": sha256_file(raw_ledger),
        }
        if source.raw in output:
            raise ValueError(f"duplicate judge metadata for {source.raw}")
        output[source.raw] = prepared
    return output


def register_core_instrument(
    admin: list[dict[str, str]], core_ratings: list[dict[str, str]]
) -> dict[str, int]:
    """Validate and register the exact human-only 190-row A-prime core."""
    roles = Counter(row.get("analysis_role") for row in admin)
    if roles != Counter({"primary": 190, "global_bound": 500}):
        raise ValueError(f"A-prime admin must contain 190 core and 500 global rows: {roles}")
    core_ids = {row["rating_id"] for row in admin if row["analysis_role"] == "primary"}
    core_index = unique_index(core_ratings, "rating_id", "A-prime core ratings")
    if set(core_index) != core_ids:
        raise ValueError("A-prime core rating IDs must exactly match the 190 primary rows")
    counts = {"pi": 0, "human": 0}
    for rating_id, row in core_index.items():
        source = require_human_source(row.get("rating_source", ""))
        label = row.get("label_a_voice_presence", "").strip().lower()
        if label not in {"yes", "no", "unsure"}:
            raise ValueError(f"invalid A-prime core Label A for {rating_id}: {label!r}")
        counts[source.kind] += 1
    return counts


def merge_instruments(
    admin: list[dict[str, str]],
    core_ratings: list[dict[str, str]],
    global_ratings: list[dict[str, str]],
    judge_metadata: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], dict]:
    admin_index = unique_index(admin, "rating_id", "A-prime admin")
    roles = Counter(row.get("analysis_role") for row in admin)
    if roles != Counter({"primary": 190, "global_bound": 500}):
        raise ValueError(f"A-prime admin must contain 190 core and 500 global rows: {roles}")
    core_ids = {row["rating_id"] for row in admin if row["analysis_role"] == "primary"}
    global_ids = {row["rating_id"] for row in admin if row["analysis_role"] == "global_bound"}
    core_index = unique_index(core_ratings, "rating_id", "A-prime core ratings")
    global_index = unique_index(global_ratings, "rating_id", "A-prime global ratings")
    if set(core_index) != core_ids:
        raise ValueError("A-prime core rating IDs must exactly match the 190 primary rows")
    if set(global_index) != global_ids:
        raise ValueError("A-prime global rating IDs must exactly match the 500 global rows")
    register_core_instrument(admin, core_ratings)

    merged_index: dict[str, dict[str, str]] = {}
    for rating_id, row in core_index.items():
        require_human_source(row.get("rating_source", ""))
        merged_index[rating_id] = {**row, **{field: "" for field in JUDGE_OUTPUT_FIELDS}}
    used_judges: dict[str, dict[str, str]] = {}
    for rating_id, row in global_index.items():
        source = parse_rating_source(row.get("rating_source", ""))
        if source.kind in {"pi", "human"}:
            merged_index[rating_id] = {**row, **{field: "" for field in JUDGE_OUTPUT_FIELDS}}
            continue
        metadata = judge_metadata.get(source.raw)
        if metadata is None:
            raise ValueError(f"validated judge metadata is missing for {source.raw}")
        merged_index[rating_id] = {**row, **metadata}
        used_judges[source.raw] = metadata

    merged = [merged_index[row["rating_id"]] for row in admin]
    provenance_counts = validate_a_prime_rating_provenance(admin, merged)
    report = {
        "status": "IMPLEMENTED_TESTED_INPUT_READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "admin_rows": len(admin),
        "core_rows": len(core_ratings),
        "global_rows": len(global_ratings),
        "provenance_counts": provenance_counts,
        "judge_instruments": [
            {"rating_source": source, **metadata}
            for source, metadata in sorted(used_judges.items())
        ],
        "gate_status_computed": False,
    }
    return merged, report


def read_metadata(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    records = value if isinstance(value, list) else [value]
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("judge metadata must be an object or list of objects")
    return normalize_judge_metadata(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    keys = ROOT / "paper_prep/rater_admin_keys_20260711/t2_aprime"
    parser.add_argument("--admin", type=Path, default=keys / "A_PRIME_PRIMARY_ADMIN.csv")
    parser.add_argument("--core-ratings", type=Path, required=True)
    parser.add_argument("--core-bundle-key", type=Path, default=keys / "T2_BUNDLE_KEY.csv")
    parser.add_argument(
        "--core-id-namespace", choices=["bundle", "scorer"], default="bundle"
    )
    parser.add_argument("--global-ratings", type=Path, required=True)
    parser.add_argument("--judge-validation-metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    core_ratings = read_csv(args.core_ratings)
    if args.core_id_namespace == "bundle":
        core_ratings = remap_bundle_rows(
            core_ratings, args.core_bundle_key, scorer_id_field="rating_id"
        )
    merged, report = merge_instruments(
        read_csv(args.admin),
        core_ratings,
        read_csv(args.global_ratings),
        read_metadata(args.judge_validation_metadata),
    )
    write_csv(args.output, merged)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(merged), "provenance": report["provenance_counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
