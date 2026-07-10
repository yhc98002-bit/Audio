#!/usr/bin/env python3
"""Build deterministic ACE-Step 1.5 smoke and prevalence manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SMOKE_SEED_BASE = 2033090000
PREVALENCE_SEED_BASE = 2033000000


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line at {path}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"non-object JSON at {path}:{line_number}")
            rows.append(row)
    return rows


def generation_row(source: dict, manifest_index: int, condition: str, seed_idx: int, seed: int) -> dict:
    requested_vocal = int(source["vocal_stratum"] == "vocal")
    return {
        "prompt_id": source["prompt_id"],
        "source_prompt_index": int(source["prompt_index"]),
        "manifest_index": manifest_index,
        "vocal_stratum": source["vocal_stratum"],
        "requested_vocal": requested_vocal,
        "text": source["text"],
        "lyrics": source.get("lyrics"),
        "structure_hint": source.get("structure_hint"),
        "duration_target": float(source["duration_target"]),
        "condition": condition,
        "seed_idx": seed_idx,
        "seed": seed,
        "source": "n2_difficult_stratified_128",
    }


def build_manifests(source_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    if len(source_rows) != 128 or len({row["prompt_id"] for row in source_rows}) != 128:
        raise ValueError("v1.5 replication source must contain 128 unique prompts")
    if {row["vocal_stratum"] for row in source_rows} != {"vocal", "instrumental"}:
        raise ValueError("source must contain both vocal request strata")
    prevalence = []
    for manifest_index, source in enumerate(source_rows):
        for seed_idx in range(8):
            prevalence.append(
                generation_row(
                    source,
                    manifest_index,
                    "baseline",
                    seed_idx,
                    PREVALENCE_SEED_BASE + manifest_index * 8 + seed_idx,
                )
            )
    smoke_sources = [
        next(row for row in source_rows if row["vocal_stratum"] == "instrumental"),
        next(row for row in source_rows if row["vocal_stratum"] == "vocal"),
    ]
    smoke = [
        generation_row(row, index, "baseline", 0, SMOKE_SEED_BASE + index)
        for index, row in enumerate(smoke_sources)
    ]
    return smoke, prevalence


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    smoke, prevalence = build_manifests(read_jsonl(args.source))
    write_jsonl(args.out_dir / "V15_SMOKE_MANIFEST.jsonl", smoke)
    write_jsonl(args.out_dir / "V15_PREVALENCE_MANIFEST.jsonl", prevalence)
    summary = {
        "smoke_rows": len(smoke),
        "prevalence_rows": len(prevalence),
        "prevalence_prompts": len({row["prompt_id"] for row in prevalence}),
        "prevalence_seeds_per_prompt": 8,
        "seed_policy": "2033000000 + manifest_index*8 + seed_idx",
    }
    (args.out_dir / "V15_INITIAL_MANIFEST_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
