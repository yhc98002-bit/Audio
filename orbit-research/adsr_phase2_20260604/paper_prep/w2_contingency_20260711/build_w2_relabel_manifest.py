#!/usr/bin/env python3
"""Inventory retained ADSR audio for a future corrected-instrument relabel."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PAPER_PREP = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
CANDIDATE_SPINE = ROOT / "orbit-research/trajectory_candidate_dataset.jsonl"


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def record_id(cohort: str, identity: str) -> str:
    return hashlib.sha256(f"{cohort}|{identity}".encode()).hexdigest()[:24]


def canonical_audio_path(path_value: str, base_dir: Path | None = None) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        candidates = [base_dir / path] if base_dir else []
        candidates.extend([ROOT / path, PAPER_PREP / path])
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return candidates[0].resolve()
    if path.is_file():
        return path.resolve()
    parts = path.parts
    if "AudioDiffusion" in parts:
        suffix = Path(*parts[parts.index("AudioDiffusion") + 1 :])
        relocated = (ROOT / suffix).resolve()
        if relocated.is_file():
            return relocated
    return path


def ledger_records(cohort: str, directory: Path, pattern: str) -> list[dict]:
    output = []
    seen_keys = set()
    for ledger in sorted(directory.glob(pattern)):
        for row_index, row in enumerate(read_jsonl(ledger), start=1):
            if not row.get("ok"):
                continue
            path_value = row.get("flac") or row.get("audio_path") or row.get("output_path")
            if not path_value:
                continue
            path = canonical_audio_path(path_value, directory.parent)
            key = (
                row.get("prompt_id", ""),
                row.get("condition", ""),
                int(row.get("seed_idx", -1)),
            )
            if key in seen_keys:
                raise ValueError(f"duplicate frozen-ledger key in {cohort}: {key}")
            seen_keys.add(key)
            requested = row.get("requested_vocal")
            if requested is None:
                requested = int(row.get("vocal_stratum") == "vocal")
            output.append(
                {
                    "record_id": record_id(cohort, "|".join(map(str, key))),
                    "cohort": cohort,
                    "source_artifact": str(ledger.relative_to(ROOT)),
                    "source_row": row_index,
                    "prompt_id": row.get("prompt_id", ""),
                    "condition": row.get("condition", ""),
                    "seed_idx": row.get("seed_idx", ""),
                    "requested_vocal": int(requested),
                    "audio_path": str(path),
                    "media_available": path.is_file(),
                    "media_class": "frozen_retained",
                    "old_vocal_energy_ratio": row.get("vocal_energy_ratio", ""),
                    "old_near_silent": row.get("near_silent", ""),
                    "old_present": row.get("present", ""),
                }
            )
    return output


def retained_keep_records() -> list[dict]:
    output = []
    keep_files = sorted(
        path
        for path in (ROOT / "batch3").glob("**/keep/**/*")
        if path.is_file() and path.suffix.lower() in {".flac", ".wav"}
    )
    for path in keep_files:
        relative = path.relative_to(ROOT)
        cohort = (
            "atlas_keep"
            if "20260620_regime_atlas_autopilot_v3" in str(relative)
            else "batch3_keep"
        )
        prompt_match = re.search(r"(held_out_\d+|dev_\d+)", str(relative))
        output.append(
            {
                "record_id": record_id(cohort, str(relative)),
                "cohort": cohort,
                "source_artifact": "filesystem retained keep",
                "source_row": "",
                "prompt_id": prompt_match.group(1) if prompt_match else "",
                "condition": "",
                "seed_idx": "",
                "requested_vocal": "",
                "audio_path": str(path.resolve()),
                "media_available": True,
                "media_class": "retained_keep",
                "old_vocal_energy_ratio": "",
                "old_near_silent": "",
                "old_present": "",
            }
        )
    return output


def candidate_audio_index() -> dict[tuple[str, int, int], tuple[Path, str]]:
    output: dict[tuple[str, int, int], tuple[Path, str]] = {}
    roots = [
        (ROOT / "runs", "surviving_original"),
        (PAPER_PREP / "validation_A_prime/recovered_media_20260708/audio", "regenerated_sensitivity"),
    ]
    pattern = re.compile(r"candidate_(\d+)_seed(\d+)\.wav$")
    for search_root, media_class in roots:
        if not search_root.exists():
            continue
        for path in sorted(search_root.glob("**/candidate_*_seed*.wav")):
            if not path.is_file():
                continue
            if "_early" in path.name:
                continue
            match = pattern.search(path.name)
            prompt_match = re.search(r"(dev_\d+|held_out_\d+)", str(path.parent))
            if not match or not prompt_match:
                continue
            key = (prompt_match.group(1), int(match.group(1)), int(match.group(2)))
            current = output.get(key)
            if current and current[0].resolve() != path.resolve():
                if current[1] == "surviving_original":
                    continue
                if media_class != "surviving_original":
                    raise ValueError(f"ambiguous candidate audio for {key}")
            output[key] = (path.resolve(), media_class)
    return output


def candidate_spine_records() -> list[dict]:
    audio_index = candidate_audio_index()
    output = []
    for row_index, row in enumerate(read_jsonl(CANDIDATE_SPINE), start=1):
        key = (row["prompt_id"], int(row["candidate_index"]), int(row["candidate_seed"]))
        audio = audio_index.get(key)
        output.append(
            {
                "record_id": record_id("candidate_spine_4096", row["candidate_uid"]),
                "cohort": "candidate_spine_4096",
                "source_artifact": str(CANDIDATE_SPINE.relative_to(ROOT)),
                "source_row": row_index,
                "prompt_id": row["prompt_id"],
                "condition": "candidate_final",
                "seed_idx": row["candidate_index"],
                "requested_vocal": int(row["vocal_stratum"] == "vocal"),
                "audio_path": str(audio[0]) if audio else "",
                "media_available": bool(audio),
                "media_class": audio[1] if audio else "not_retained_on_disk",
                "old_vocal_energy_ratio": "",
                "old_near_silent": "",
                "old_present": "",
            }
        )
    if len(output) != 4096:
        raise ValueError(f"candidate spine cardinality changed: {len(output)}")
    return output


def build_manifest() -> list[dict]:
    rows = []
    rows.extend(
        ledger_records(
            "stage3_intervention",
            PAPER_PREP / "stage3_intervention_20260707/ledgers",
            "full64_w*.jsonl",
        )
    )
    rows.extend(
        ledger_records(
            "n2_population_retry",
            PAPER_PREP / "population_retry_20260707/ledgers",
            "full128_w*.jsonl",
        )
    )
    rows.extend(retained_keep_records())
    rows.extend(candidate_spine_records())
    ids = [row["record_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("W2 manifest record IDs are not unique")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    out_dir = Path(__file__).resolve().parent
    parser.add_argument("--manifest", type=Path, default=out_dir / "W2_RETAINED_AUDIO_MANIFEST.jsonl")
    parser.add_argument("--inventory", type=Path, default=out_dir / "W2_RETAINED_AUDIO_INVENTORY.json")
    args = parser.parse_args()
    rows = build_manifest()
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    counts = Counter(row["cohort"] for row in rows)
    available = Counter(row["cohort"] for row in rows if row["media_available"])
    media_classes = Counter(row["media_class"] for row in rows)
    inventory = {
        "status": "SCAFFOLD_ONLY_NO_EVIDENCE_RELABELED",
        "manifest": str(args.manifest.resolve()),
        "rows_by_cohort": dict(sorted(counts.items())),
        "available_media_by_cohort": dict(sorted(available.items())),
        "media_classes": dict(sorted(media_classes.items())),
        "total_rows": len(rows),
        "available_media": sum(available.values()),
    }
    args.inventory.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
