#!/usr/bin/env python3
"""Build a balanced self-hosted judge smoke only from real PI ratings."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


VALID_LABELS = {"yes", "no", "unsure"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def select_pi_gold(admin_rows: list[dict], rating_rows: list[dict]) -> list[dict]:
    admin = {row["rating_id"]: row for row in admin_rows}
    if len(admin) != len(admin_rows):
        raise ValueError("duplicate decisive admin rating_id")
    rating_ids = [row["rating_id"] for row in rating_rows]
    if len(set(rating_ids)) != len(rating_ids):
        raise ValueError("duplicate decisive rating rating_id")
    candidates = []
    for rating in rating_rows:
        rating_id = rating["rating_id"]
        if rating_id not in admin:
            raise ValueError(f"rating outside admin manifest: {rating_id}")
        label = rating.get("label_a_voice_presence", "").strip().lower()
        source = rating.get("rating_source", "").strip()
        confidence_text = rating.get("confidence_1_to_5", "").strip()
        if not label and not source and not confidence_text:
            continue
        if label not in VALID_LABELS:
            raise ValueError(f"invalid Label A for {rating_id}: {label!r}")
        if not source.lower().startswith("pi"):
            raise ValueError(f"non-PI provenance for {rating_id}: {source!r}")
        try:
            confidence = int(confidence_text)
        except ValueError as exc:
            raise ValueError(f"invalid confidence for {rating_id}") from exc
        if label in {"yes", "no"} and confidence >= 4:
            candidates.append(
                {
                    "clip_id": rating_id,
                    "clip_path": admin[rating_id]["package_media_path"],
                    "true_label": label,
                    "rating_source": source,
                    "confidence": confidence,
                    "source_category": admin[rating_id]["category"],
                    "sha256": admin[rating_id]["sha256"],
                }
            )
    selected = []
    for label in ("yes", "no"):
        values = sorted(
            (row for row in candidates if row["true_label"] == label),
            key=lambda row: (row["source_category"], row["clip_id"]),
        )
        if len(values) < 5:
            raise ValueError(
                f"need five confidence>=4 PI-gold {label} clips; found {len(values)}"
            )
        selected.extend(values[:5])
    return sorted(selected, key=lambda row: (row["true_label"], row["clip_id"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    base = Path("paper_prep/pi_decisive_packet_20260709")
    parser.add_argument("--admin", type=Path, default=base / "DECISIVE_PACKET_ADMIN.csv")
    parser.add_argument("--ratings", type=Path, default=base / "DECISIVE_PACKET_RATINGS.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("paper_prep/judge_selfhost_20260709/SELFHOST_SMOKE_PI_GOLD.csv"),
    )
    args = parser.parse_args()
    selected = select_pi_gold(read_csv(args.admin), read_csv(args.ratings))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    print(f"PI_GOLD_SMOKE_ROWS={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
