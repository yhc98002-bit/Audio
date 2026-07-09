#!/usr/bin/env python3
"""Build PI/human-ready A-prime and B-prime validation packages."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
from pathlib import Path

try:
    import soundfile as sf
except Exception:  # pragma: no cover - package report will show unknown audio stats.
    sf = None


ROOT = Path.cwd()
PAPER = ROOT / "paper_prep"
A_DIR = PAPER / "validation_A_prime"
B_DIR = PAPER / "validation_B_prime"
A_PKG = A_DIR / "human_package"
B_PKG = B_DIR / "human_package"
RECOVERED_A_PRIME = A_DIR / "recovered_media_20260708" / "A_PRIME_RECOVERED_MEDIA_MANIFEST.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_json(value: str) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audio_stats(path: Path) -> tuple[str, str, str]:
    if sf is None:
        return "", "", ""
    try:
        info = sf.info(str(path))
        duration = info.frames / float(info.samplerate) if info.samplerate else math.nan
        return f"{duration:.3f}", str(info.samplerate), str(info.channels)
    except Exception:
        return "", "", ""


def materialize(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst, follow_symlinks=True)
    except OSError:
        shutil.copy2(src, dst, follow_symlinks=True)


def recovered_a_prime_index() -> dict[str, dict[str, str]]:
    if not RECOVERED_A_PRIME.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with RECOVERED_A_PRIME.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") != "PASS":
                continue
            recovered = ROOT / row.get("recovered_path", "")
            if not recovered.exists():
                continue
            out[row["clip_id"]] = row
    return out


def ambiguous_truth_index() -> dict[tuple[str, int], dict[str, object]]:
    path = ROOT / "orbit-research/adsr_phase2_20260604/vocal_ambiguous_check_packet.jsonl"
    out: dict[tuple[str, int], dict[str, object]] = {}
    if not path.exists():
        return out
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            out[(row["prompt_id"], int(row["candidate_index"]))] = row
    return out


def label_from_metadata(row: dict[str, str], meta: dict, ambiguous: dict[tuple[str, int], dict[str, object]]) -> str:
    for key in ("expected_demucs_label",):
        value = row.get(key, "")
        if value in {"0", "1"}:
            return value
    for key in ("present", "demucs_present_label"):
        value = str(meta.get(key, ""))
        if value in {"0", "1"}:
            return value
        if value.lower() == "true":
            return "1"
        if value.lower() == "false":
            return "0"
    prompt_id = meta.get("prompt_id", row.get("prompt_id", ""))
    candidate = meta.get("candidate_index", "")
    try:
        cand_int = int(candidate)
    except (TypeError, ValueError):
        return ""
    amb = ambiguous.get((prompt_id, cand_int), {})
    if "present" in amb:
        return "1" if bool(amb["present"]) else "0"
    return ""


def build_a_prime() -> dict[str, object]:
    rows = read_csv(A_DIR / "A_PRIME_MANIFEST.csv")
    ambiguous = ambiguous_truth_index()
    recovered = recovered_a_prime_index()
    media_dir = A_PKG / "media"
    admin_rows: list[dict[str, object]] = []
    rater_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for idx, row in enumerate(rows, start=1):
        meta = parse_json(row.get("metadata_json", ""))
        src = ROOT / row["clip_path"]
        original_exists = src.exists()
        source_is_symlink = src.is_symlink()
        target = os.readlink(src) if source_is_symlink else ""
        recovery_row = recovered.get(row["clip_id"])
        recovery_method = ""
        recovery_source_path = ""
        src_for_package = src
        actual_exists = original_exists
        if not original_exists and recovery_row:
            candidate = ROOT / recovery_row["recovered_path"]
            if candidate.exists():
                src_for_package = candidate
                actual_exists = True
                recovery_method = recovery_row.get("recovery_method", "")
                recovery_source_path = recovery_row.get("recovered_path", "")
        expected_present = label_from_metadata(row, meta, ambiguous)
        requested_vocal = row.get("requested_vocal", "") or str(meta.get("requested_vocal", ""))
        packet_subdir = ""
        if "2c_detector_agreement_spotcheck" in row["clip_path"]:
            packet_subdir = "2c_detector_agreement_spotcheck"
        elif "2_label_adjudication" in row["clip_path"]:
            packet_subdir = "2_label_adjudication"
        elif "2b_rare_basin_audit" in row["clip_path"]:
            packet_subdir = "2b_rare_basin_audit"
        set_bucket = row["set_name"]
        if packet_subdir == "2c_detector_agreement_spotcheck":
            set_bucket = "agreement_spotcheck_30"
        elif row["set_name"] == "detector_disagreement_packet":
            set_bucket = "detector_disagreement_packet"
        elif row["set_name"].startswith("rare"):
            set_bucket = "rare_basin"
        elif row["set_name"] == "stratified_random_500":
            set_bucket = "stratified_random_500"

        rating_id = f"aprime_human_{idx:04d}"
        ext = src.suffix.lower() if src.suffix else ".wav"
        pkg_media = media_dir / f"{rating_id}{ext}"
        duration_s = sample_rate = channels = ""
        sha = ""
        package_media_path = ""
        if actual_exists:
            materialize(src_for_package, pkg_media)
            duration_s, sample_rate, channels = audio_stats(pkg_media)
            sha = sha256_file(pkg_media)
            package_media_path = str(pkg_media.relative_to(ROOT))
            rater_rows.append(
                {
                    "rating_id": rating_id,
                    "media_path": package_media_path,
                    "contains_human_voice": "",
                    "confidence_1_to_5": "",
                    "notes": "",
                }
            )
        else:
            missing_rows.append(
                {
                    "clip_id": row["clip_id"],
                    "set_name": row["set_name"],
                    "expected_clip_path": row["clip_path"],
                    "source_id": row.get("source_id", ""),
                    "source_path": row.get("source_path", ""),
                    "symlink_target": target,
                    "recovery_status": "unrecovered_dangling_symlink_or_missing_source",
                }
            )

        admin_rows.append(
            {
                "rating_id": rating_id,
                "source_clip_id": row["clip_id"],
                "set_name": row["set_name"],
                "set_bucket": set_bucket,
                    "source_path": row["clip_path"],
                    "package_media_path": package_media_path,
                    "media_available": str(actual_exists).lower(),
                    "original_media_available": str(original_exists).lower(),
                    "media_recovery_method": recovery_method,
                    "recovery_source_path": recovery_source_path,
                    "source_is_symlink": str(source_is_symlink).lower(),
                    "symlink_target": target,
                "expected_present_label": expected_present,
                "requested_vocal": requested_vocal,
                "prompt_id": row.get("prompt_id", "") or meta.get("prompt_id", ""),
                "duration_s": duration_s,
                "sample_rate": sample_rate,
                "channels": channels,
                "sha256": sha,
            }
        )

    write_csv(A_PKG / "A_PRIME_HUMAN_ADMIN_MANIFEST.csv", admin_rows)
    write_csv(A_PKG / "A_PRIME_HUMAN_RATING_TEMPLATE.csv", rater_rows)
    write_csv(
        A_DIR / "A_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv",
        missing_rows,
        [
            "clip_id",
            "set_name",
            "expected_clip_path",
            "source_id",
            "source_path",
            "symlink_target",
            "recovery_status",
        ],
    )

    synthetic_rows = []
    for row in rater_rows[:12]:
        synthetic_rows.append({**row, "contains_human_voice": "unsure", "confidence_1_to_5": "3", "notes": "synthetic"})
    write_csv(A_PKG / "A_PRIME_SYNTHETIC_RATINGS.csv", synthetic_rows, list(rater_rows[0]) if rater_rows else [])

    set_counts: dict[str, int] = {}
    set_missing: dict[str, int] = {}
    for row in admin_rows:
        set_counts[row["set_bucket"]] = set_counts.get(row["set_bucket"], 0) + 1
        if row["media_available"] != "true":
            set_missing[row["set_bucket"]] = set_missing.get(row["set_bucket"], 0) + 1

    status = "HUMAN_READY_ZERO_MISSING" if not missing_rows else "HUMAN_READY_WITH_EXACT_MISSING_ROWS"
    set_lines = "\n".join(
        f"- `{name}`: {set_counts[name]} rows, {set_missing.get(name, 0)} missing media"
        for name in sorted(set_counts)
    )
    report = f"""# A-prime Human-Ready Report

Generated: 2026-07-08

A_PRIME_PACKAGE_STATUS = {status}

This package is for PI/human adjudication. It does not convert A-prime to PASS
until human ratings are recorded and scored by
`paper_prep/validation_A_prime/score_human_A_prime.py`.

## Outputs

- Admin manifest: `paper_prep/validation_A_prime/human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv`
- Rater template: `paper_prep/validation_A_prime/human_package/A_PRIME_HUMAN_RATING_TEMPLATE.csv`
- Blinded media directory: `paper_prep/validation_A_prime/human_package/media/`
- Missing media table: `paper_prep/validation_A_prime/A_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv`
- Synthetic ratings: `paper_prep/validation_A_prime/human_package/A_PRIME_SYNTHETIC_RATINGS.csv`
- Scoring script: `paper_prep/validation_A_prime/score_human_A_prime.py`

## Coverage

- Full A-prime manifest rows: {len(rows)}
- Human package rater rows with media: {len(rater_rows)}
- Missing media rows: {len(missing_rows)}
- Recovered/regenerated media rows used: {sum(1 for r in admin_rows if r['media_recovery_method'])}
- Rows with expected/reference present label available: {sum(1 for r in admin_rows if r['expected_present_label'] in {'0', '1'})}

## Set Coverage

{set_lines}

## Important Caveats

- The phase-0 rater packet contains 100 `demucs_whisper_disagree` rows, not the
  112 stated in the checklist. The current deduplicated A-prime manifest has 92
  detector-disagreement rows.
- The previously unavailable rows were dangling symlinks into missing
  `runs/adsr_recollect_resume/...` or `runs/adsr_recollect_20260604_full01/...`
  targets. They are now materialized from the recovered-media manifest when
  available; admin rows record `media_recovery_method` and `recovery_source_path`.
- The rater-facing template contains only blinded media paths and empty answer
  columns; labels and source details are in the admin manifest only.
"""
    (A_DIR / "A_PRIME_HUMAN_READY_REPORT.md").write_text(report, encoding="utf-8")
    return {
        "status": status,
        "manifest_rows": len(rows),
        "rater_rows": len(rater_rows),
        "missing_media_rows": len(missing_rows),
    }


def choose_b_calibration(rows: list[dict[str, str]]) -> set[str]:
    rng = random.Random(20260708)
    by_key: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_key.setdefault((row["contrast"], row["group"]), []).append(row)
    selected: list[str] = []
    # 2 contrasts x 3 groups x 4 pairs = 24 pairs.
    for key in sorted(by_key):
        group_rows = sorted(by_key[key], key=lambda r: r["pair_id"])
        rng.shuffle(group_rows)
        selected.extend(r["pair_id"] for r in group_rows[:4])
    return set(selected[:24])


def build_b_prime() -> dict[str, object]:
    rows = read_csv(B_DIR / "B_PRIME_MANIFEST.csv")
    media_dir = B_PKG / "media"
    calibration = choose_b_calibration(rows)
    admin_rows: list[dict[str, object]] = []
    rating_rows: list[dict[str, object]] = []
    pair_admin_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for idx, row in enumerate(rows, start=1):
        pair_id = row["pair_id"]
        paths = {"orig_a": ROOT / row["path_a"], "orig_b": ROOT / row["path_b"]}
        available = all(path.exists() for path in paths.values())
        if not available:
            missing_rows.append(
                {
                    "pair_id": pair_id,
                    "path_a": row["path_a"],
                    "path_b": row["path_b"],
                    "A_exists_actual": str(paths["orig_a"].exists()).lower(),
                    "B_exists_actual": str(paths["orig_b"].exists()).lower(),
                }
            )
        pair_admin_rows.append(
            {
                "pair_id": pair_id,
                "contrast": row["contrast"],
                "group": row["group"],
                "prompt_id": row["prompt_id"],
                "A_is": row["A_is"],
                "B_is": row["B_is"],
                "in_calibration_24": str(pair_id in calibration).lower(),
                "A_exists_actual": str(paths["orig_a"].exists()).lower(),
                "B_exists_actual": str(paths["orig_b"].exists()).lower(),
            }
        )
        if not available:
            continue
        for order in ("ab", "ba"):
            rating_id = f"bprime_human_{idx:03d}_{order}"
            if order == "ab":
                src_a, src_b = paths["orig_a"], paths["orig_b"]
                presented_a_is, presented_b_is = row["A_is"], row["B_is"]
            else:
                src_a, src_b = paths["orig_b"], paths["orig_a"]
                presented_a_is, presented_b_is = row["B_is"], row["A_is"]
            dst_a = media_dir / f"{rating_id}_A{src_a.suffix.lower()}"
            dst_b = media_dir / f"{rating_id}_B{src_b.suffix.lower()}"
            materialize(src_a, dst_a)
            materialize(src_b, dst_b)
            admin_rows.append(
                {
                    "rating_id": rating_id,
                    "pair_id": pair_id,
                    "order": order,
                    "contrast": row["contrast"],
                    "group": row["group"],
                    "prompt_id": row["prompt_id"],
                    "media_a_path": str(dst_a.relative_to(ROOT)),
                    "media_b_path": str(dst_b.relative_to(ROOT)),
                    "presented_a_is": presented_a_is,
                    "presented_b_is": presented_b_is,
                    "in_calibration_24": str(pair_id in calibration).lower(),
                    "sha256_a": sha256_file(dst_a),
                    "sha256_b": sha256_file(dst_b),
                }
            )
            rating_rows.append(
                {
                    "rating_id": rating_id,
                    "media_a_path": str(dst_a.relative_to(ROOT)),
                    "media_b_path": str(dst_b.relative_to(ROOT)),
                    "quality_preference": "",
                    "constraint_preference": "",
                    "overall_preference": "",
                    "confidence_1_to_5": "",
                    "notes": "",
                }
            )

    write_csv(B_PKG / "B_PRIME_HUMAN_PAIR_ADMIN.csv", pair_admin_rows)
    write_csv(B_PKG / "B_PRIME_HUMAN_ORDERED_ADMIN_MANIFEST.csv", admin_rows)
    write_csv(B_PKG / "B_PRIME_HUMAN_RATING_TEMPLATE.csv", rating_rows)
    write_csv(B_PKG / "B_PRIME_CALIBRATION_24_PAIRS.csv", [r for r in pair_admin_rows if r["in_calibration_24"] == "true"])
    write_csv(B_DIR / "B_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv", missing_rows)

    synthetic_rows = []
    for row in rating_rows[:12]:
        synthetic_rows.append({**row, "quality_preference": "tie", "constraint_preference": "tie", "overall_preference": "tie", "confidence_1_to_5": "3", "notes": "synthetic"})
    write_csv(B_PKG / "B_PRIME_SYNTHETIC_RATINGS.csv", synthetic_rows, list(rating_rows[0]) if rating_rows else [])

    status = "HUMAN_READY_ZERO_MISSING" if not missing_rows and len(rating_rows) == 160 else "HUMAN_READY_WITH_EXACT_MISSING_ROWS"
    report = f"""# B-prime Human-Ready Report

Generated: 2026-07-08

B_PRIME_PACKAGE_STATUS = {status}

This package is for PI/human B-prime quality validation and calibration. It does
not convert B-prime to PASS until ratings are recorded and scored by
`paper_prep/validation_B_prime/score_human_B_prime.py`.

## Outputs

- Pair admin manifest: `paper_prep/validation_B_prime/human_package/B_PRIME_HUMAN_PAIR_ADMIN.csv`
- Ordered admin manifest: `paper_prep/validation_B_prime/human_package/B_PRIME_HUMAN_ORDERED_ADMIN_MANIFEST.csv`
- Rater template: `paper_prep/validation_B_prime/human_package/B_PRIME_HUMAN_RATING_TEMPLATE.csv`
- Calibration subset: `paper_prep/validation_B_prime/human_package/B_PRIME_CALIBRATION_24_PAIRS.csv`
- Blinded media directory: `paper_prep/validation_B_prime/human_package/media/`
- Missing media table: `paper_prep/validation_B_prime/B_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv`
- Synthetic ratings: `paper_prep/validation_B_prime/human_package/B_PRIME_SYNTHETIC_RATINGS.csv`
- Scoring script: `paper_prep/validation_B_prime/score_human_B_prime.py`

## Coverage

- Pair rows: {len(rows)}
- Ordered rating rows: {len(rating_rows)}
- Calibration pairs: {len(calibration)}
- Missing-media pairs: {len(missing_rows)}

## Randomization / Leakage

- Each pair is presented in both `ab` and `ba` order.
- Rater-facing filenames use opaque rating IDs and A/B letters only.
- Arm identities and source paths are restricted to admin manifests.
"""
    (B_DIR / "B_PRIME_HUMAN_READY_REPORT.md").write_text(report, encoding="utf-8")
    return {
        "status": status,
        "pairs": len(rows),
        "ordered_rows": len(rating_rows),
        "missing_pairs": len(missing_rows),
        "calibration_pairs": len(calibration),
    }


def main() -> int:
    A_PKG.mkdir(parents=True, exist_ok=True)
    B_PKG.mkdir(parents=True, exist_ok=True)
    result = {"a_prime": build_a_prime(), "b_prime": build_b_prime()}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
