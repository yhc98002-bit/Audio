#!/usr/bin/env python3
"""Validate and register the amendment-compliant 2026-07-11 PI ratings."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def find_root(path: Path) -> Path:
    for candidate in path.parents:
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root(Path(__file__).resolve())
PAPER_PREP = ROOT / "paper_prep"
sys.path.insert(0, str(PAPER_PREP / "scripts"))
from rating_provenance import require_human_source, sha256_file  # noqa: E402


T1_REQUIRED = (
    "rating_id",
    "rating_source",
    "label_a_voice_presence",
    "perceived_vocal_type",
    "vocal_extent",
    "label_b_constraint",
    "confidence_1_to_5",
    "request_mode",
    "reveal_sequence",
)
T2_REQUIRED = (
    "rating_id",
    "rating_source",
    "label_a_voice_presence",
    "confidence_1_to_5",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_export(path: Path, expected_bundle: str) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("bundle_id") != expected_bundle:
        raise ValueError(f"unexpected bundle_id in {path}: {payload.get('bundle_id')!r}")
    source = require_human_source(str(payload.get("rating_source", "")))
    if source.raw != "pi:Richard":
        raise ValueError(f"unexpected top-level PI provenance in {path}: {source.raw!r}")
    rows = payload.get("responses")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"responses must be a list of objects: {path}")
    return payload, rows


def keyed_rows(
    rows: list[dict], key_path: Path, expected_rows: int
) -> tuple[list[dict], list[dict[str, str]]]:
    keys = read_csv(key_path)
    if len(keys) != expected_rows:
        raise ValueError(f"bundle key has {len(keys)} rows, expected {expected_rows}")
    mapping = {row["bundle_rating_id"]: row for row in keys}
    incoming = [str(row.get("rating_id", "")).strip() for row in rows]
    if len(rows) != expected_rows or len(incoming) != len(set(incoming)):
        raise ValueError(f"response count/uniqueness failure: expected {expected_rows}")
    if set(incoming) != set(mapping):
        raise ValueError("response ID set does not exactly match the bundle key")
    output = []
    for row in rows:
        bundle_id = row["rating_id"]
        output.append(
            {
                **row,
                "bundle_rating_id": bundle_id,
                "rating_id": mapping[bundle_id]["scorer_rating_id"],
            }
        )
    return output, keys


def require_complete(rows: list[dict], fields: tuple[str, ...], label: str) -> None:
    blanks = [
        (row.get("rating_id", "<missing>"), field)
        for row in rows
        for field in fields
        if str(row.get(field, "")).strip() == ""
    ]
    if blanks:
        raise ValueError(f"{label} has required blank cells: {blanks[:5]}")
    for row in rows:
        source = require_human_source(str(row.get("rating_source", "")))
        if source.raw != "pi:Richard":
            raise ValueError(f"{label} row has unexpected provenance: {source.raw!r}")
        if row["label_a_voice_presence"] not in {"yes", "no", "unsure"}:
            raise ValueError(f"{label} has invalid Label A")
        try:
            confidence = int(row["confidence_1_to_5"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} has invalid confidence") from exc
        if confidence not in range(1, 6):
            raise ValueError(f"{label} confidence must be 1-5")


def validate_t1(rows: list[dict], keys: list[dict[str, str]], admin: list[dict[str, str]]) -> list[dict]:
    require_complete(rows, T1_REQUIRED, "T1")
    key_by_bundle = {row["bundle_rating_id"]: row for row in keys}
    admin_by_id = {row["rating_id"]: row for row in admin}
    if len(admin_by_id) != 42 or set(admin_by_id) != {row["rating_id"] for row in rows}:
        raise ValueError("T1 scorer IDs do not exactly match the 42-row admin manifest")
    reveal = []
    inconsistencies = []
    for row in rows:
        if row["request_mode"] not in {"vocal", "instrumental"}:
            raise ValueError("T1 request_mode must be vocal or instrumental")
        expected_mode = key_by_bundle[row["bundle_rating_id"]].get("request_mode", "")
        if row["request_mode"] != expected_mode:
            raise ValueError(f"T1 request_mode/key mismatch: {row['bundle_rating_id']}")
        if row["label_b_constraint"] not in {"satisfied", "violated", "unsure"}:
            raise ValueError("T1 has invalid Label B")
        if not isinstance(row.get("label_a_amended"), bool):
            raise ValueError("T1 label_a_amended must be a JSON boolean")
        try:
            reveal.append(int(row["reveal_sequence"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("T1 reveal_sequence must be an integer") from exc
        hard_contradiction = row["label_a_voice_presence"] == "no" and (
            (row["request_mode"] == "vocal" and row["label_b_constraint"] == "satisfied")
            or (
                row["request_mode"] == "instrumental"
                and row["label_b_constraint"] == "violated"
            )
        )
        if hard_contradiction:
            admin_row = admin_by_id[row["rating_id"]]
            inconsistencies.append(
                {
                    "bundle_rating_id": row["bundle_rating_id"],
                    "rating_id": row["rating_id"],
                    "category": admin_row["category"],
                    "request_mode": row["request_mode"],
                    "label_a_voice_presence": row["label_a_voice_presence"],
                    "label_b_constraint": row["label_b_constraint"],
                    "label_a_amended": str(row["label_a_amended"]).lower(),
                    "reason": "Label B implies audible voice while Label A is no",
                    "adjudication_status": "PENDING_PI",
                }
            )
    if set(reveal) != set(range(1, 43)):
        raise ValueError("T1 reveal_sequence must be a permutation of 1..42")
    return inconsistencies


def load_merge_module():
    path = PAPER_PREP / "rater_admin_keys_20260711/t2_aprime/merge_a_prime_instruments.py"
    spec = importlib.util.spec_from_file_location("a_prime_merge_for_ingest", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("A-prime merge loader is unavailable")
    spec.loader.exec_module(module)
    return module


def relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def media_record(admin_row: dict[str, str], rating: dict, source_package: str) -> dict:
    if source_package == "t2_aprime_core":
        path = ROOT / admin_row["package_media_path"]
        expected_hash = admin_row["package_sha256"]
    else:
        path = ROOT / admin_row["package_media_path"]
        expected_hash = admin_row["sha256"]
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise ValueError(f"PI-gold media checksum mismatch: {path}")
    return {
        "clip_path": relative_or_absolute(path),
        "true_label": rating["label_a_voice_presence"],
        "rating_source": rating["rating_source"],
        "confidence": rating["confidence_1_to_5"],
        "audio_sha256": actual_hash,
        "source_package": source_package,
        "source_rating_ids": admin_row["rating_id"],
    }


def build_pi_gold(
    t1_rows: list[dict],
    t2_rows: list[dict],
    t1_admin: list[dict[str, str]],
    t2_admin: list[dict[str, str]],
    inconsistency_ids: set[str],
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    t1_index = {row["rating_id"]: row for row in t1_rows}
    t2_index = {row["rating_id"]: row for row in t2_rows}
    candidates = []
    exclusions = []
    for admin_row in t2_admin:
        if admin_row["analysis_role"] != "primary":
            continue
        rating = t2_index[admin_row["rating_id"]]
        if rating["label_a_voice_presence"] == "unsure":
            exclusions.append({"rating_id": admin_row["rating_id"], "reason": "t2_label_a_unsure"})
            continue
        candidates.append(media_record(admin_row, rating, "t2_aprime_core"))
    for admin_row in t1_admin:
        rating = t1_index[admin_row["rating_id"]]
        reasons = []
        if rating["label_a_voice_presence"] == "unsure":
            reasons.append("t1_label_a_unsure")
        if rating["label_a_amended"]:
            reasons.append("t1_label_a_amended_pre_reveal_unavailable")
        if rating["rating_id"] in inconsistency_ids:
            reasons.append("t1_internal_inconsistency")
        if reasons:
            exclusions.append({"rating_id": admin_row["rating_id"], "reason": ";".join(reasons)})
            continue
        candidates.append(media_record(admin_row, rating, "t1_decisive"))

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in candidates:
        grouped[row["audio_sha256"]].append(row)
    deduped = []
    for audio_hash, rows in sorted(grouped.items()):
        labels = {row["true_label"] for row in rows}
        if len(labels) != 1:
            raise ValueError(f"conflicting PI labels for media hash {audio_hash}")
        preferred = next(
            (row for row in rows if row["source_package"] == "t2_aprime_core"), rows[0]
        )
        deduped.append(
            {
                **preferred,
                "clip_id": f"pi_gold_{audio_hash[:16]}",
                "source_package": ";".join(sorted({row["source_package"] for row in rows})),
                "source_rating_ids": ";".join(
                    sorted(row["source_rating_ids"] for row in rows)
                ),
                "duplicate_presentations": len(rows),
            }
        )
    split = {"calibration": [], "heldout": []}
    for label in ("yes", "no"):
        label_rows = sorted(
            (row for row in deduped if row["true_label"] == label),
            key=lambda row: row["audio_sha256"],
        )
        for index, row in enumerate(label_rows):
            role = "heldout" if index % 2 == 0 else "calibration"
            split[role].append({**row, "split": role})
    for role in split:
        split[role].sort(key=lambda row: row["clip_id"])
    smoke = []
    for label in ("yes", "no"):
        values = [row for row in split["calibration"] if row["true_label"] == label]
        if len(values) < 5:
            raise ValueError(f"PI-gold calibration split has fewer than five {label} rows")
        smoke.extend(values[:5])
    smoke.sort(key=lambda row: row["clip_id"])
    return deduped, split["calibration"], split["heldout"], smoke, exclusions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=PAPER_PREP / "pi_ratings_20260711")
    parser.add_argument("--output-dir", type=Path, default=PAPER_PREP / "pi_ratings_20260711/processed")
    args = parser.parse_args()
    keys = PAPER_PREP / "rater_admin_keys_20260711"
    t1_payload, t1_raw = read_export(args.input_dir / "t1_decisive.json", "t1_decisive_v2")
    t2_payload, t2_raw = read_export(args.input_dir / "t2_aprime_core.json", "t2_aprime_core")
    t1_rows, t1_keys = keyed_rows(t1_raw, keys / "t1_decisive/T1_BUNDLE_KEY_V2.csv", 42)
    t2_rows, _t2_keys = keyed_rows(t2_raw, keys / "t2_aprime/T2_BUNDLE_KEY.csv", 190)
    t1_admin = read_csv(keys / "t1_decisive/DECISIVE_PACKET_ADMIN.csv")
    t2_admin = read_csv(keys / "t2_aprime/A_PRIME_PRIMARY_ADMIN.csv")
    inconsistencies = validate_t1(t1_rows, t1_keys, t1_admin)
    require_complete(t2_rows, T2_REQUIRED, "T2")
    merge_module = load_merge_module()
    provenance = merge_module.register_core_instrument(t2_admin, t2_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    t1_output = args.output_dir / "T1_DECISIVE_OFFICIAL.csv"
    t2_output = args.output_dir / "T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv"
    adjudication = args.output_dir / "T1_ADJUDICATION_LIST.csv"
    write_csv(t1_output, t1_rows)
    write_csv(t2_output, t2_rows)
    if inconsistencies:
        write_csv(adjudication, inconsistencies)
    else:
        adjudication.write_text(
            "bundle_rating_id,rating_id,reason,adjudication_status\n", encoding="utf-8"
        )

    gold, calibration, heldout, smoke, exclusions = build_pi_gold(
        t1_rows,
        t2_rows,
        t1_admin,
        t2_admin,
        {row["rating_id"] for row in inconsistencies},
    )
    write_csv(args.output_dir / "PI_GOLD_DEDUPLICATED.csv", gold)
    write_csv(args.output_dir / "PI_GOLD_CALIBRATION.csv", calibration)
    write_csv(args.output_dir / "PI_GOLD_HELDOUT.csv", heldout)
    write_csv(args.output_dir / "PI_GOLD_SMOKE.csv", smoke)
    write_csv(args.output_dir / "PI_GOLD_EXCLUSIONS.csv", exclusions)

    backup_candidates = sorted(
        path
        for path in args.input_dir.iterdir()
        if path.is_file()
        and path.name not in {"t1_decisive.json", "t2_aprime_core.json"}
        and ("backup" in path.name.lower() or "autosave" in path.name.lower())
    )
    amended = [row for row in t1_rows if row["label_a_amended"]]
    pre_reveal_status = "UNAVAILABLE" if amended and not backup_candidates else "REVIEW_REQUIRED"
    audit = {
        "ingestion_status": "PASS",
        "t1": {
            "rows": len(t1_rows),
            "exact_id_set": True,
            "provenance": "pi:Richard",
            "required_blanks": 0,
            "amended_rows": len(amended),
            "pre_reveal_label_a_status": pre_reveal_status,
            "backup_candidates": [str(path) for path in backup_candidates],
            "inconsistent_rows": len(inconsistencies),
        },
        "t2": {
            "rows": len(t2_rows),
            "exact_id_set": True,
            "provenance": "pi:Richard",
            "required_blanks": 0,
            "merge_registration": "REGISTERED_HUMAN_CORE_GLOBAL_500_PENDING",
            "provenance_counts": provenance,
        },
        "pi_gold": {
            "deduplicated_rows": len(gold),
            "calibration_rows": len(calibration),
            "heldout_rows": len(heldout),
            "smoke_rows": len(smoke),
            "label_counts": dict(Counter(row["true_label"] for row in gold)),
            "exclusions": len(exclusions),
        },
        "raw_inputs": {
            "t1": str(args.input_dir / "t1_decisive.json"),
            "t1_sha256": sha256_file(args.input_dir / "t1_decisive.json"),
            "t1_exported_at": t1_payload.get("exported_at"),
            "t2": str(args.input_dir / "t2_aprime_core.json"),
            "t2_sha256": sha256_file(args.input_dir / "t2_aprime_core.json"),
            "t2_exported_at": t2_payload.get("exported_at"),
        },
        "a_prime_gate_scored": False,
    }
    (args.output_dir / "PI_RATING_INGEST_AUDIT.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    registration = {
        "status": "REGISTERED_HUMAN_CORE_GLOBAL_500_PENDING",
        "official_core": relative_or_absolute(t2_output),
        "official_core_sha256": sha256_file(t2_output),
        "rows": 190,
        "provenance_counts": provenance,
        "global_bound_rows_pending": 500,
        "gate_scored": False,
        "merge_script": "paper_prep/rater_admin_keys_20260711/t2_aprime/merge_a_prime_instruments.py",
        "required_cli_flag": "--core-id-namespace scorer",
    }
    (args.output_dir / "A_PRIME_CORE_REGISTRATION.json").write_text(
        json.dumps(registration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
