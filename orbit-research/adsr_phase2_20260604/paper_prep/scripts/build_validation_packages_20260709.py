#!/usr/bin/env python3
"""Build amended, fail-closed A-prime and B-prime PI rating packages."""
from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path


def find_repo_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
A_DIR = PAPER / "validation_A_prime"
B_DIR = PAPER / "validation_B_prime"
KEYS = PAPER / "rater_admin_keys_20260711"
SHUFFLE_SEED = 20260709

LABEL_A = (
    "Do you hear any sound a reasonable listener would perceive as a human voice or vocalization? "
    "Includes singing, rap, speech, chant, humming, wordless vocals, choir, ooh/ah, vocal chops. "
    "Answer Yes / No / Unsure; then select perceived vocal type and whether it is isolated, "
    "intermittent, or sustained."
)
QUALITY_INSTRUCTION = (
    "Judge musical/audio quality while setting aside whether the clip correctly contains or omits vocals. "
    "Consider production quality, artifacts, musical coherence, naturalness, and listening quality."
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_fail_closed(source: Path, destination: Path, expected_sha256: str = "") -> str:
    if not source.is_file():
        raise FileNotFoundError(source)
    source_hash = sha256_file(source)
    if expected_sha256 and source_hash != expected_sha256:
        raise ValueError(f"source hash drift: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != source_hash:
            raise ValueError(f"stale package file hash mismatch: {destination}")
        return source_hash
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    if sha256_file(destination) != source_hash:
        raise ValueError(f"materialized package hash mismatch: {destination}")
    return source_hash


def prompt_requests() -> dict[str, str]:
    output = {}
    for path in (ROOT / "configs/prompts/dev.jsonl", ROOT / "configs/prompts/held_out.jsonl"):
        for row in read_jsonl(path):
            output[row["prompt_id"]] = row.get("strata", {}).get("vocal_vs_instrumental", "")
    return output


def blind_id(prefix: str, source_id: str, index: int, nonce: str) -> str:
    digest = hmac.new(nonce.encode(), source_id.encode(), hashlib.sha256).hexdigest()[:12]
    return f"{prefix}_{index:04d}_{digest}"


def build_a_prime(nonce: str) -> dict:
    package = A_DIR / "primary_package_20260709"
    media = package / "media"
    request_index = prompt_requests()
    reconciliation = read_csv(A_DIR / "A_PRIME_CARDINALITY_RECONCILIATION.csv")
    disagreement = [row for row in reconciliation if row["analysis_role"] == "primary"]
    if len(disagreement) != 112 or any(row["media_class"] != "original" for row in disagreement):
        raise ValueError("reconciled disagreement primary must be 112 originals")

    old_admin = read_csv(A_DIR / "human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv")
    regenerated_rare_ids = {
        row["sample_id"]
        for row in read_csv(PAPER / "storage_triage/RARE_CLEAN_PROTECTED/manifest.csv")
        if row["source_family"] == "regenerated_from_frozen_seed"
    }
    rare = [row for row in old_admin if row["set_bucket"] == "rare_basin" and row["source_clip_id"] not in regenerated_rare_ids]
    agreement = [row for row in old_admin if row["set_bucket"] == "agreement_spotcheck_30"]
    global_bound = [row for row in old_admin if row["set_bucket"] == "stratified_random_500"]
    if (len(rare), len(agreement), len(global_bound)) != (48, 30, 500):
        raise ValueError(f"unexpected original-only A-prime cardinalities: {len(rare)}, {len(agreement)}, {len(global_bound)}")

    source_rows = []
    for row in disagreement:
        source_rows.append(
            {
                "source_clip_id": row["case_id"],
                "set_bucket": "detector_disagreement_112",
                "analysis_role": "primary",
                "media_class": "original",
                "source_path": row["package_media_path"],
                "expected_demucs_label": row["demucs_label_0p1791"],
                "requested_vocal": "1" if request_index[row["prompt_id"]] == "vocal" else "0",
                "prompt_id": row["prompt_id"],
                "declared_sha256": row["sha256"],
            }
        )
    for bucket, role, rows in (
        ("rare_basin_48", "primary", rare),
        ("agreement_spotcheck_30", "primary", agreement),
        ("stratified_random_500", "global_bound", global_bound),
    ):
        for row in rows:
            requested = row["requested_vocal"]
            if requested not in {"0", "1"}:
                requested = "1" if request_index.get(row["prompt_id"]) == "vocal" else "0"
            if row["expected_present_label"] not in {"0", "1"}:
                raise ValueError(f"missing expected detector label after regenerated exclusion: {row['source_clip_id']}")
            source_rows.append(
                {
                    "source_clip_id": row["source_clip_id"],
                    "set_bucket": bucket,
                    "analysis_role": role,
                    "media_class": "original",
                    "source_path": row["package_media_path"],
                    "expected_demucs_label": row["expected_present_label"],
                    "requested_vocal": requested,
                    "prompt_id": row["prompt_id"],
                    "declared_sha256": row["sha256"],
                }
            )
    source_ids = [row["source_clip_id"] for row in source_rows]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate A-prime source clip IDs")
    rng = random.Random(SHUFFLE_SEED)
    rng.shuffle(source_rows)
    admin = []
    ratings = []
    for index, row in enumerate(source_rows, 1):
        rating_id = blind_id("aprime", row["source_clip_id"], index, nonce)
        source = ROOT / row["source_path"]
        destination = media / f"{rating_id}{source.suffix.lower()}"
        digest = materialize_fail_closed(source, destination, row["declared_sha256"])
        admin.append(
            {
                "rating_id": rating_id,
                **row,
                "package_media_path": str(destination.relative_to(ROOT)),
                "package_sha256": digest,
                "shuffle_seed": SHUFFLE_SEED,
            }
        )
        ratings.append(
            {
                "rating_id": rating_id,
                "media_path": f"media/{destination.name}",
                "request_type": "vocal" if row["requested_vocal"] == "1" else "instrumental",
                "label_a_voice_presence": "",
                "perceived_vocal_type": "",
                "vocal_extent": "",
                "label_b_constraint": "",
                "confidence_1_to_5": "",
                "rating_source": "",
                "notes": "",
            }
        )
    write_csv(KEYS / "t2_aprime/A_PRIME_PRIMARY_ADMIN.csv", admin)
    write_csv(package / "A_PRIME_PRIMARY_RATINGS.csv", ratings)
    instructions = f"""# A-prime Original-Only Rating Instructions

`A_PRIME_PRIMARY_PACKAGE_STATUS = ORIGINAL_ONLY_PI_READY`

Rows are shuffled with recorded seed {SHUFFLE_SEED}. Filenames and rater rows
contain no detector output. The package contains 112 original disagreement,
48 original rare-basin, 30 original agreement, and 500 original global-bound
clips. The 26 regenerated rare-clean clips are excluded from the primary gate.

## Label A (voice presence)

"{LABEL_A}"

## Label B (constraint satisfaction)

Vocal request → *Satisfied* only when clearly audible vocals function as an
intentional musical element; a fleeting isolated chop, ambiguous voice-like
texture, or background artifact is not sufficient. Instrumental request →
*Violated* when perceived vocal content is salient, recurrent, or functions as
a musical element, or when any phrase is clearly sung, spoken, or rapped; a
single isolated non-linguistic one-shot shorter than ~2 s is normally not a
violation unless unusually prominent.

Choir-pad rule: perceived as human choir → A=Yes and instrumental request
normally violated; perceived as synth timbre → A=No; ambiguous → Unsure.
Keep Unsure rather than forcing a label.
"""
    (package / "README.md").write_text(instructions, encoding="utf-8")
    return {"status": "ORIGINAL_ONLY_PI_READY", "rows": len(admin), "package": str(package)}


def choose_b_calibration(rows: list[dict[str, str]]) -> set[str]:
    rng = random.Random(SHUFFLE_SEED)
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["contrast"], row["group"])].append(row)
    selected = []
    for key in sorted(groups):
        values = sorted(groups[key], key=lambda row: row["pair_id"])
        rng.shuffle(values)
        selected.extend(row["pair_id"] for row in values[:4])
    if len(set(selected)) != 24:
        raise ValueError(f"B calibration stratification produced {len(set(selected))}, expected 24")
    return set(selected)


def build_b_prime(nonce: str) -> dict:
    package = B_DIR / "pi_package_20260709"
    media = package / "media"
    pairs = read_csv(B_DIR / "B_PRIME_MANIFEST.csv")
    pair_ids = [row["pair_id"] for row in pairs]
    if len(pairs) != 80 or len(set(pair_ids)) != 80:
        raise ValueError("B-prime source manifest must have 80 unique pairs")
    calibration = choose_b_calibration(pairs)
    rng = random.Random(SHUFFLE_SEED)
    rng.shuffle(pairs)
    pair_admin = []
    ordered_admin = []
    ratings = []

    def add_presentation(row: dict[str, str], role: str, index: int, method_is_a: bool) -> None:
        rating_id = blind_id("bprime", f"{row['pair_id']}:{role}", index, nonce)
        source_method = ROOT / (row["path_a"] if row["A_is"] == "arm6" else row["path_b"])
        source_baseline = ROOT / (row["path_b"] if row["A_is"] == "arm6" else row["path_a"])
        source_a, source_b = (source_method, source_baseline) if method_is_a else (source_baseline, source_method)
        side_a, side_b = ("arm6", row["B_is"] if row["A_is"] == "arm6" else row["A_is"]) if method_is_a else (row["B_is"] if row["A_is"] == "arm6" else row["A_is"], "arm6")
        destination_a = media / f"{rating_id}_A{source_a.suffix.lower()}"
        destination_b = media / f"{rating_id}_B{source_b.suffix.lower()}"
        hash_a = materialize_fail_closed(source_a, destination_a)
        hash_b = materialize_fail_closed(source_b, destination_b)
        ordered_admin.append(
            {
                "rating_id": rating_id,
                "pair_id": row["pair_id"],
                "presentation_role": role,
                "presented_a_is": side_a,
                "presented_b_is": side_b,
                "media_a_path": str(destination_a.relative_to(ROOT)),
                "media_b_path": str(destination_b.relative_to(ROOT)),
                "sha256_a": hash_a,
                "sha256_b": hash_b,
                "shuffle_seed": SHUFFLE_SEED,
            }
        )
        ratings.append(
            {
                "rating_id": rating_id,
                "request_text": row["request_text"],
                "media_a_path": f"media/{destination_a.name}",
                "media_b_path": f"media/{destination_b.name}",
                "quality_preference": "",
                "overall_preference": "",
                "constraint_preference": "",
                "confidence_1_to_5": "",
                "rating_source": "",
                "notes": "",
            }
        )

    primary_order = {}
    for row in pairs:
        method_is_a = bool(rng.getrandbits(1))
        primary_order[row["pair_id"]] = method_is_a
        pair_admin.append(
            {
                "pair_id": row["pair_id"],
                "contrast": row["contrast"],
                "group": row["group"],
                "prompt_id": row["prompt_id"],
                "method_arm": "arm6",
                "baseline_arm": row["B_is"] if row["A_is"] == "arm6" else row["A_is"],
                "in_calibration_24": str(row["pair_id"] in calibration).lower(),
            }
        )
        add_presentation(row, "primary", len(ordered_admin) + 1, method_is_a)
    reverse_rows = [row for row in pairs if row["pair_id"] in calibration]
    rng.shuffle(reverse_rows)
    for row in reverse_rows:
        add_presentation(row, "reliability_reverse", len(ordered_admin) + 1, not primary_order[row["pair_id"]])
    write_csv(KEYS / "t3_t4_bprime/B_PRIME_PAIR_ADMIN.csv", pair_admin)
    write_csv(KEYS / "t3_t4_bprime/B_PRIME_ORDERED_ADMIN.csv", ordered_admin)
    write_csv(package / "B_PRIME_PI_RATINGS.csv", ratings)
    instructions = f"""# B-prime Solo-Rater Instructions

`B_PRIME_PI_PACKAGE_STATUS = READY`

The first 80 rows are the primary presentation of 80 unique pairs. The final
24 rows are delayed reversed repeats for position-bias and intra-rater
reliability only; they are never counted as extra primary votes.

## Primary quality question

"{QUALITY_INSTRUCTION}"

Record A / B / Tie / Unsure for quality, overall preference, and constraint
preference separately. The scorer excludes ties from the primary denominator,
reports ties-as-half and ties-against-method sensitivities, and reports
abstains under the selected policy.
"""
    (package / "README.md").write_text(instructions, encoding="utf-8")
    return {"status": "READY", "pairs": len(pair_admin), "rating_rows": len(ratings), "package": str(package)}


def main() -> int:
    nonce = os.environ.get("ADSR_BLINDING_NONCE")
    if not nonce:
        raise RuntimeError("ADSR_BLINDING_NONCE is required; blinding keys may not be hard-coded")
    result = {"a_prime": build_a_prime(nonce), "b_prime": build_b_prime(nonce)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
