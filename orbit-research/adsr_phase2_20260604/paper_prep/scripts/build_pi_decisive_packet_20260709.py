#!/usr/bin/env python3
"""Build the blinded 42-clip PI construct-branch packet."""
from __future__ import annotations

import csv
import hashlib
import hmac
import json
import math
import os
import random
import shutil
from pathlib import Path

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD


SHUFFLE_SEED = 20260709
THRESHOLD = VOCAL_PRESENCE_THRESHOLD


def find_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "orbit-research").is_dir() and (candidate / "src/mprm").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
A_DIR = PAPER / "validation_A_prime"
OUT = PAPER / "pi_decisive_packet_20260709"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evenly_spaced(rows: list[dict], count: int) -> list[dict]:
    if len(rows) < count:
        raise ValueError(f"need {count} rows, have {len(rows)}")
    indices = [math.floor((index + 0.5) * len(rows) / count) for index in range(count)]
    selected = [rows[index] for index in indices]
    if len({row["source_path"] for row in selected}) != count:
        raise ValueError("evenly-spaced selection contains duplicate media")
    return selected


def materialize(source: Path, destination: Path) -> str:
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = sha256(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != digest:
            raise ValueError(f"stale packet media differs from source: {destination}")
        return digest
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    if sha256(destination) != digest:
        raise ValueError(f"packet media hash mismatch: {destination}")
    return digest


def candidate_from_manifest(row: dict[str, str], category: str, qwen: str, demucs: str) -> dict:
    ratio = row.get("vocal_energy_ratio", "")
    return {
        "source_id": row["clip_id"],
        "category": category,
        "source_path": row["clip_path"],
        "prompt_id": row.get("prompt_id", ""),
        "requested_vocal": row.get("requested_vocal", ""),
        "qwen_label": qwen,
        "demucs_label": demucs,
        "vocal_energy_ratio": ratio,
        "selection_note": "",
    }


def select_rows() -> list[dict]:
    manifest = read_csv(A_DIR / "A_PRIME_MANIFEST.csv")
    matrix = read_csv(A_DIR / "A_PRIME_AGREEMENT_MATRIX.csv")
    old_admin = read_csv(A_DIR / "human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv")
    reconciliation = read_csv(A_DIR / "A_PRIME_CARDINALITY_RECONCILIATION.csv")
    failures = read_csv(PAPER / "judge_debug/NEGATIVE_SMOKE_FAILURE_TABLE.csv")
    by_id = {row["clip_id"]: row for row in manifest}
    by_path = {row["clip_path"]: row for row in manifest}
    matrix_by_id = {row["clip_id"]: row for row in matrix}
    prompt_request = {}
    for path in (ROOT / "configs/prompts/dev.jsonl", ROOT / "configs/prompts/held_out.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                prompt = json.loads(line)
                prompt_request[prompt["prompt_id"]] = (
                    "1" if prompt["strata"]["vocal_vs_instrumental"] == "vocal" else "0"
                )
    if len(by_id) != len(manifest):
        raise ValueError("duplicate clip_id in A-prime manifest")

    selected: list[dict] = []
    used_paths: set[str] = set()
    for failure in failures:
        source = by_path.get(failure["path"])
        if source is None:
            raise ValueError(f"failed smoke path absent from A-prime manifest: {failure['path']}")
        row = candidate_from_manifest(source, "failed_smoke_negative_4", "yes", "no")
        row["selection_note"] = failure["failure_hypothesis"]
        selected.append(row)
        used_paths.add(row["source_path"])
    if len(selected) != 4:
        raise ValueError(f"failed-smoke set has {len(selected)} rows, expected 4")

    contested = []
    for agreement in matrix:
        if agreement["expected_demucs_label"] != "no" or agreement["judge_majority"] != "yes":
            continue
        source = by_id[agreement["clip_id"]]
        if source["clip_path"] in used_paths or source["vocal_energy_ratio"] == "":
            continue
        row = candidate_from_manifest(source, "judge_yes_demucs_no_20", "yes", "no")
        contested.append(row)
    contested.sort(key=lambda row: (float(row["vocal_energy_ratio"]), row["source_id"]))
    chosen = evenly_spaced(contested, 20)
    for index, row in enumerate(chosen):
        row["selection_note"] = f"ratio_histogram_quantile_{index + 1:02d}_of_20"
        used_paths.add(row["source_path"])
    selected.extend(chosen)

    def from_old(row: dict[str, str], category: str) -> dict:
        source = by_id[row["source_clip_id"]]
        output = candidate_from_manifest(
            source,
            category,
            "",
            "yes" if row["expected_present_label"] == "1" else "no",
        )
        # Prefer the original-only, already hash-audited human package media.
        output["source_path"] = row["package_media_path"]
        if output["requested_vocal"] not in {"0", "1"}:
            output["requested_vocal"] = prompt_request[row["prompt_id"]]
        return output

    rare_candidates = [
        from_old(row, "rare_basin_6")
        for row in old_admin
        if row["set_bucket"] == "rare_basin"
        and row["original_media_available"] == "true"
        and row["package_media_path"] not in used_paths
    ]
    # The historical rare packet did not preserve every Demucs ratio. Ratio
    # stratification is not part of this six-row diagnostic category.
    rare_candidates.sort(key=lambda row: row["source_id"])
    rare = evenly_spaced(rare_candidates, 6)
    for row in rare:
        row["selection_note"] = "original rare-basin diagnostic"
        used_paths.add(row["source_path"])
    selected.extend(rare)

    near_candidates = []
    for row in reconciliation:
        if row["final_set_bucket"] != "phase0_near_threshold_packet" or row["media_class"] != "original":
            continue
        if row["package_media_path"] in used_paths:
            continue
        near_candidates.append(
            {
                "source_id": row["case_id"],
                "category": "threshold_near_6",
                "source_path": row["package_media_path"],
                "prompt_id": row["prompt_id"],
                "requested_vocal": prompt_request[row["prompt_id"]],
                "qwen_label": matrix_by_id[row["case_id"]]["judge_majority"],
                "demucs_label": "yes" if row["demucs_label_0p1791"] == "1" else "no",
                "vocal_energy_ratio": row["demucs_ratio"],
                "selection_note": "",
            }
        )
    near_candidates.sort(key=lambda row: (abs(float(row["vocal_energy_ratio"]) - THRESHOLD), row["source_id"]))
    near = near_candidates[:6]
    if len(near) != 6:
        raise ValueError("not enough original threshold-near clips")
    for row in near:
        row["selection_note"] = f"abs_ratio_delta={abs(float(row['vocal_energy_ratio']) - THRESHOLD):.8f}"
        used_paths.add(row["source_path"])
    selected.extend(near)

    match_index = {row["clip_id"]: row for row in matrix if row["status"] == "match"}
    controls = []
    for expected in ("no", "yes"):
        candidates = []
        for clip_id, agreement in match_index.items():
            if agreement["expected_demucs_label"] != expected:
                continue
            source = by_id[clip_id]
            if source["clip_path"] in used_paths or source["vocal_energy_ratio"] == "":
                continue
            row = candidate_from_manifest(source, "obvious_agreement_control_6", expected, expected)
            candidates.append(row)
        candidates.sort(
            key=lambda row: float(row["vocal_energy_ratio"]), reverse=(expected == "yes")
        )
        controls.extend(candidates[:3])
    if len(controls) != 6:
        raise ValueError(f"agreement controls have {len(controls)} rows, expected 6")
    for row in controls:
        row["selection_note"] = "detector/judge agreement far from threshold"
        used_paths.add(row["source_path"])
    selected.extend(controls)

    expected_counts = {
        "failed_smoke_negative_4": 4,
        "judge_yes_demucs_no_20": 20,
        "rare_basin_6": 6,
        "threshold_near_6": 6,
        "obvious_agreement_control_6": 6,
    }
    counts = {category: sum(row["category"] == category for row in selected) for category in expected_counts}
    if counts != expected_counts or len(selected) != 42:
        raise ValueError(f"decisive packet shape mismatch: {counts}, total={len(selected)}")
    if len({row["source_path"] for row in selected}) != 42:
        raise ValueError("decisive packet contains duplicate media paths")
    if any(row["requested_vocal"] not in {"0", "1"} for row in selected):
        missing = [row["source_id"] for row in selected if row["requested_vocal"] not in {"0", "1"}]
        raise ValueError(f"missing request labels: {missing}")
    return selected


def main() -> int:
    nonce = os.environ.get("ADSR_BLINDING_NONCE")
    if not nonce:
        raise RuntimeError("ADSR_BLINDING_NONCE is required")
    rows = select_rows()
    random.Random(SHUFFLE_SEED).shuffle(rows)
    media_dir = OUT / "media"
    OUT.mkdir(parents=True, exist_ok=True)
    admin = []
    ratings = []
    for index, row in enumerate(rows, 1):
        opaque = hmac.new(nonce.encode(), row["source_id"].encode(), hashlib.sha256).hexdigest()[:12]
        rating_id = f"decisive_{index:02d}_{opaque}"
        source = ROOT / row["source_path"]
        destination = media_dir / f"{rating_id}{source.suffix.lower()}"
        digest = materialize(source, destination)
        admin.append(
            {
                "rating_id": rating_id,
                **row,
                "package_media_path": str(destination.relative_to(ROOT)),
                "sha256": digest,
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
    write_csv(OUT / "DECISIVE_PACKET_ADMIN.csv", admin)
    write_csv(OUT / "DECISIVE_PACKET_RATINGS.csv", ratings)
    readme = """# PI Decisive Construct Packet

This is a 42-clip branch-selection packet. It is **not A-prime gate
validation** and cannot be used to claim that A-prime passed.

The blinded order contains four failed-smoke negatives, 20 Qwen-yes/Demucs-no
clips spread across the detector-ratio histogram, six original rare-basin
clips, six original threshold-near clips, and six obvious-agreement controls.

Use the D5 Label A and Label B definitions in
`paper_prep/HUMAN_STUDY_CRITERIA_AMENDMENT_20260709.md`. Keep `Unsure` rather
than forcing a label. After all rows are rated with non-synthetic provenance,
run:

```bash
python paper_prep/pi_decisive_packet_20260709/score_decisive_packet.py
```

The scorer returns one branch: `judge_over_calling`, `demucs_missing`, or
`construct_mismatch`. A `demucs_missing` branch is an escalation trigger.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"rows": len(admin), "status": "PI_RATING_READY"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
