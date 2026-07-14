#!/usr/bin/env python3
"""Validate T7 PI ratings and materialize the frozen count-only judge top-up."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
DEFAULT_INPUT = PAPER / "pi_ratings_20260713/t7_judge_gold_negatives.json"
ADMIN = PAPER / "rater_admin_keys_20260712/t7_judge_gold_negatives/T7_JUDGE_GOLD_NEGATIVES_ADMIN.csv"
BASE_GOLD = PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_EVALUATION_MANIFEST.csv"
CALIBRATION_SELECTION = PAPER / "w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_MANIFEST.csv"
PRIOR_JUDGE_GOLD = PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_GOLD_SPLIT.csv"
OUT = PAPER / "t7_judge_gold_20260713/ratings_ingest"
OFFICIAL = OUT / "T7_OFFICIAL_RATINGS.csv"
TOPUP = OUT / "T7_TOPUP_GOLD_MANIFEST.csv"
ALL_GOLD = OUT / "T7_ALL_DISJOINT_GOLD_MANIFEST.csv"
AUDIT = OUT / "T7_RATINGS_INGEST_AUDIT.json"
REPORT = OUT / "T7_TOPUP_INGEST_REPORT.md"
EXPECTED_SOURCE = "pi:Richard"
REQUIRED_ADDITIONAL_NEGATIVES = 23


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_hash_disjointness(admin: list[dict]) -> dict:
    selected_hashes = {row["media_sha256"] for row in admin}
    if len(selected_hashes) != len(admin):
        raise ValueError("T7 admin contains duplicate media hashes")
    detector_hashes = {
        row["media_sha256"]
        for row in read_csv(CALIBRATION_SELECTION)
        if row.get("media_sha256")
    }
    prior_judge_hashes = {
        row["media_sha256"]
        for row in read_csv(PRIOR_JUDGE_GOLD)
        if row.get("media_sha256")
    }
    detector_overlap = selected_hashes & detector_hashes
    prior_judge_overlap = selected_hashes & prior_judge_hashes
    if detector_overlap or prior_judge_overlap:
        raise ValueError(
            "T7 media are not hash-disjoint: "
            f"detector={len(detector_overlap)}, prior_judge={len(prior_judge_overlap)}"
        )
    for row in admin:
        path = Path(row["media_path"])
        if not path.is_file() or sha256_file(path) != row["media_sha256"]:
            raise ValueError(f"T7 source-media checksum mismatch: {row['rating_id']}")
    return {
        "selected_unique_hashes": len(selected_hashes),
        "detector_selection_promotion_hashes": len(detector_hashes),
        "prior_judge_gold_hashes": len(prior_judge_hashes),
        "detector_selection_promotion_overlap": 0,
        "prior_judge_gold_overlap": 0,
        "source_media_checksums_verified": len(admin),
    }


def load_export(path: Path) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("responses"), list):
        raise ValueError("T7 export must be an object with a responses list")
    if payload.get("bundle_id") != "t7_judge_gold_negatives":
        raise ValueError(f"unexpected T7 bundle_id: {payload.get('bundle_id')!r}")
    if payload.get("rating_source") != EXPECTED_SOURCE:
        raise ValueError("T7 top-level rating_source must be pi:Richard")
    return payload, [dict(row) for row in payload["responses"]]


def validate(path: Path) -> tuple[list[dict], list[dict], dict]:
    payload, ratings = load_export(path)
    admin = read_csv(ADMIN)
    if len(admin) != 40 or len(ratings) != 40:
        raise ValueError(f"T7 requires 40 admin and rating rows: {len(admin)}/{len(ratings)}")
    admin_ids = {row["rating_id"] for row in admin}
    rating_ids = [str(row.get("rating_id", "")) for row in ratings]
    if len(set(rating_ids)) != 40 or set(rating_ids) != admin_ids:
        raise ValueError("T7 rating/admin ID set mismatch or duplicate")
    admin_index = {row["rating_id"]: row for row in admin}
    normalized = []
    errors = []
    for row in ratings:
        rating_id = str(row.get("rating_id", ""))
        key = admin_index[rating_id]
        label_a = str(row.get("label_a_voice_presence", "")).strip().lower()
        label_b = str(row.get("label_b_constraint", "")).strip().lower()
        vocal_type = str(row.get("perceived_vocal_type", "")).strip().lower()
        extent = str(row.get("vocal_extent", "")).strip().lower()
        confidence = str(row.get("confidence_1_to_5", "")).strip()
        source = str(row.get("rating_source", "")).strip()
        request_mode = str(row.get("request_mode", "")).strip().lower()
        try:
            reveal_sequence = int(row.get("reveal_sequence", 0))
        except (TypeError, ValueError):
            reveal_sequence = 0
        if label_a not in {"yes", "no", "unsure"}:
            errors.append(f"{rating_id}: invalid Label A")
        if label_b not in {"", "satisfied", "violated", "unsure"}:
            errors.append(f"{rating_id}: invalid Label B")
        if not vocal_type or not extent:
            errors.append(f"{rating_id}: incomplete blind Label-A annotations")
        if confidence not in {"", "1", "2", "3", "4", "5"}:
            errors.append(f"{rating_id}: confidence must be blank or 1-5")
        if source != EXPECTED_SOURCE:
            errors.append(f"{rating_id}: invalid provenance")
        if request_mode != key["request_mode"] or request_mode != "instrumental":
            errors.append(f"{rating_id}: request mode mismatch")
        if reveal_sequence != int(key["reveal_sequence"]):
            errors.append(f"{rating_id}: reveal sequence mismatch")
        normalized.append(
            {
                "rating_id": rating_id,
                "label_a_voice_presence": label_a,
                "perceived_vocal_type": vocal_type,
                "vocal_extent": extent,
                "label_b_constraint": label_b,
                "confidence_1_to_5": confidence,
                "notes": str(row.get("notes", "")),
                "request_mode": request_mode,
                "label_a_amended": str(row.get("label_a_amended", False)).lower(),
                "reveal_sequence": reveal_sequence,
                "rating_source": source,
            }
        )
    if errors:
        raise ValueError("; ".join(errors[:20]))
    hash_audit = audit_hash_disjointness(admin)
    audit = {
        "T7_RATINGS_INGESTION": "PASS",
        "rows": len(normalized),
        "exact_id_set_match": True,
        "rating_source": EXPECTED_SOURCE,
        "required_label_a_blanks": 0,
        "optional_label_b_blanks": sum(not row["label_b_constraint"] for row in normalized),
        "optional_label_b_blank_ids": [
            row["rating_id"] for row in normalized if not row["label_b_constraint"]
        ],
        "optional_confidence_blanks": sum(not row["confidence_1_to_5"] for row in normalized),
        "label_a_counts": dict(Counter(row["label_a_voice_presence"] for row in normalized)),
        "label_b_counts": dict(Counter(row["label_b_constraint"] for row in normalized)),
        "exported_at": payload.get("exported_at", ""),
        "hash_disjointness": hash_audit,
    }
    return normalized, admin, audit


def materialize_all_gold(ratings: list[dict], admin: list[dict]) -> list[dict]:
    rating_index = {row["rating_id"]: row for row in ratings}
    output = []
    for key in sorted(admin, key=lambda row: int(row["topup_order"])):
        rating = rating_index[key["rating_id"]]
        label = rating["label_a_voice_presence"]
        if label == "unsure":
            continue
        output.append(
            {
                "rating_id": key["rating_id"],
                "clip_id": f"t7_{key['rating_id']}",
                "clip_path": key["media_path"],
                "media_sha256": key["media_sha256"],
                "true_label": label,
                "rating_source": rating["rating_source"],
                "gold_source": "t7_all_hash_disjoint_pi_gold",
                "judge_role": "judge_evaluation_topup",
                "calibration_stratum": "t7_far_below_predicted_absent",
                "inclusion_probability": key["inclusion_probability"],
                "topup_order": key["topup_order"],
            }
        )
    return output


def materialize_topup(ratings: list[dict], admin: list[dict]) -> tuple[list[dict], dict]:
    rating_index = {row["rating_id"]: row for row in ratings}
    ordered = sorted(admin, key=lambda row: int(row["topup_order"]))
    if [int(row["topup_order"]) for row in ordered] != list(range(1, 41)):
        raise ValueError("T7 top-up order is not exactly 1..40")
    consumed = []
    negative_count = 0
    for row in ordered:
        rating = rating_index[row["rating_id"]]
        consumed.append((row, rating))
        negative_count += int(rating["label_a_voice_presence"] == "no")
        if negative_count >= REQUIRED_ADDITIONAL_NEGATIVES:
            break
    status = (
        "PASS_TOPUP_READY"
        if negative_count >= REQUIRED_ADDITIONAL_NEGATIVES
        else "BLOCKED_NEGATIVE_COUNT_SHORTFALL"
    )
    output = []
    human_unsure = 0
    for key, rating in consumed:
        label = rating["label_a_voice_presence"]
        if label == "unsure":
            human_unsure += 1
            continue
        output.append(
            {
                "rating_id": key["rating_id"],
                "clip_id": f"t7_{key['rating_id']}",
                "clip_path": key["media_path"],
                "media_sha256": key["media_sha256"],
                "true_label": label,
                "rating_source": rating["rating_source"],
                "gold_source": "t7_count_only_negative_topup",
                "judge_role": "judge_evaluation_topup",
                "calibration_stratum": "t7_far_below_predicted_absent",
                "inclusion_probability": key["inclusion_probability"],
                "topup_order": key["topup_order"],
            }
        )
    baseline = read_csv(BASE_GOLD)
    baseline_negatives = sum(row["true_label"] == "no" for row in baseline)
    result = {
        "T7_RATINGS_STATUS": status,
        "baseline_rows": len(baseline),
        "baseline_negatives": baseline_negatives,
        "consumed_t7_presentations": len(consumed),
        "consumed_t7_decided_rows": len(output),
        "consumed_t7_human_unsure": human_unsure,
        "additional_decided_negatives": negative_count,
        "combined_decided_negatives": baseline_negatives + negative_count,
        "required_combined_negatives": 50,
        "unused_t7_presentations": 40 - len(consumed),
        "selection_rule": "ascending frozen topup_order until 23 additional human no labels",
    }
    return output, result


def run(path: Path) -> dict:
    ratings, admin, audit = validate(path)
    topup, result = materialize_topup(ratings, admin)
    all_gold = materialize_all_gold(ratings, admin)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OFFICIAL, ratings)
    if topup:
        write_csv(TOPUP, topup)
    write_csv(ALL_GOLD, all_gold)
    combined = {
        **audit,
        **result,
        "all_t7_decided_gold_rows": len(all_gold),
        "all_t7_decided_gold_counts": dict(Counter(row["true_label"] for row in all_gold)),
        "input_path": str(path),
        "topup_manifest": str(TOPUP),
        "all_disjoint_gold_manifest": str(ALL_GOLD),
    }
    AUDIT.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# T7 Ratings And Count-Only Top-Up\n\n"
        f"`T7_RATINGS_STATUS = {result['T7_RATINGS_STATUS']}`\n\n"
        f"- Ratings validated: {audit['rows']}/40, exact IDs, zero required Label-A blanks, `{EXPECTED_SOURCE}`.\n"
        f"- Optional Label-B blanks recorded: {audit['optional_label_b_blanks']} ({', '.join(audit['optional_label_b_blank_ids'])}).\n"
        f"- Optional confidence blanks recorded: {audit['optional_confidence_blanks']}.\n"
        f"- Hash overlap with detector selection/promotion: {audit['hash_disjointness']['detector_selection_promotion_overlap']}.\n"
        f"- Hash overlap with prior judge gold: {audit['hash_disjointness']['prior_judge_gold_overlap']}.\n"
        f"- Frozen-order presentations consumed: {result['consumed_t7_presentations']}.\n"
        f"- Additional decided human negatives: {result['additional_decided_negatives']}.\n"
        f"- Combined baseline+T7 negatives: {result['combined_decided_negatives']}/50 required.\n"
        f"- Human-unsure rows consumed but excluded from judge truth: {result['consumed_t7_human_unsure']}.\n"
        f"- Judge manifest: `{TOPUP}`.\n",
        encoding="utf-8",
    )
    return combined


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.input), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
