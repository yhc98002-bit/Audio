#!/usr/bin/env python3
"""Build a checksum manifest for the post-gate ADSR Hugging Face upload."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[6]
HERE = Path(__file__).resolve().parent
INCLUDE = [
    ROOT / "orbit-research/trajectory_candidate_dataset.jsonl",
    ROOT / "paper_prep/figures/fig2_regime_data.csv",
    ROOT / "paper_prep/stage3_intervention_20260707/stage3_condition_rates_figure_data.csv",
    ROOT / "paper_prep/population_retry_20260707/n2_regime_figure_data.csv",
    ROOT / "paper_prep/storage_triage/RELEASE_KEEP_MANIFEST.csv",
    HERE / "DATASET_CARD.md",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    missing = [str(path) for path in INCLUDE if not path.is_file()]
    if missing:
        raise SystemExit(f"release inputs missing: {missing}")
    rows = [
        {
            "source_path": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
            "upload_status": "DEFERRED_POST_GATE_HUMAN_ACTION",
        }
        for path in INCLUDE
    ]
    output = HERE / "UPLOAD_MANIFEST.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
