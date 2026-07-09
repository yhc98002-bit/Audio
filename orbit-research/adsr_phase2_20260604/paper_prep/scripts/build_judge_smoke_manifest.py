#!/usr/bin/env python3
"""Build a clearly separated 10-clip A' judge smoke manifest.

The previous smoke used two near-threshold negative clips. This builder follows
the guide's intent: five clearly vocal and five clearly instrumental examples.
PANNs is not used as a hard negative filter because the project logs already
record that it over-fires on instrumental music.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def as_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pick_distinct(rows, n, prompt_col="prompt_id"):
    picked = []
    seen = set()
    for row in rows:
        pid = row.get(prompt_col)
        if pid in seen:
            continue
        picked.append(row)
        seen.add(pid)
        if len(picked) == n:
            return picked
    for row in rows:
        if row in picked:
            continue
        picked.append(row)
        if len(picked) == n:
            return picked
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest-enriched", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.manifest_enriched)))
    for row in rows:
        row["_demucs"] = as_float(row.get("vocal_energy_ratio"))
        row["_panns"] = as_float(row.get("panns_vocal"))

    positives = [
        r for r in rows
        if r.get("present") == "1" and r["_demucs"] is not None and r["_panns"] is not None
        and r["_demucs"] >= 0.25 and r["_panns"] >= 0.15
        and Path(r["copied_path"]).exists()
    ]
    positives.sort(key=lambda r: (min(r["_demucs"], r["_panns"]), r["_demucs"]), reverse=True)

    negatives = [
        r for r in rows
        if r.get("present") == "0" and r.get("requested_vocal") == "0"
        and r["_demucs"] is not None and r["_demucs"] <= 0.01
        and Path(r["copied_path"]).exists()
    ]
    negatives.sort(key=lambda r: (r["_demucs"], r["_panns"]))

    picked_pos = pick_distinct(positives, 5)
    picked_neg = pick_distinct(negatives, 5)
    if len(picked_pos) < 5 or len(picked_neg) < 5:
        raise SystemExit(f"not enough smoke clips: positives={len(picked_pos)} negatives={len(picked_neg)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "clip_path", "expected", "prompt_id", "demucs_ratio", "panns",
        "requested_vocal", "present", "source_path",
    ]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row, expected in [(r, "yes") for r in picked_pos] + [(r, "no") for r in picked_neg]:
            w.writerow({
                "clip_path": row["copied_path"],
                "expected": expected,
                "prompt_id": row["prompt_id"],
                "demucs_ratio": row["vocal_energy_ratio"],
                "panns": row.get("panns_vocal", ""),
                "requested_vocal": row.get("requested_vocal", ""),
                "present": row.get("present", ""),
                "source_path": row.get("source_path", ""),
            })

    print(f"wrote {out} positives={len(picked_pos)} negatives={len(picked_neg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
