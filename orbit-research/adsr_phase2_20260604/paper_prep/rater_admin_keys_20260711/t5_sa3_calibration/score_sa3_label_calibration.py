#!/usr/bin/env python3
"""Fail-closed scorer for the SA3 human label-calibration package."""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path


def find_root(path: Path) -> Path:
    for candidate in path.parents:
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from rating_provenance import validate_human_rating_rows  # noqa: E402
from bundle_response_io import remap_bundle_rows  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_ids(admin: list[dict[str, str]], ratings: list[dict[str, str]]) -> None:
    expected = [row["blind_id"] for row in admin]
    actual = [row["blind_id"] for row in ratings]
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate admin blind_id")
    if len(actual) != len(set(actual)):
        raise ValueError("duplicate rating blind_id")
    if set(actual) != set(expected):
        raise ValueError(f"rating/admin ID mismatch: missing={set(expected)-set(actual)}, unknown={set(actual)-set(expected)}")


def validate_real_provenance(ratings: list[dict[str, str]]) -> None:
    validate_human_rating_rows(ratings, id_field="blind_id")


def confusion(truth: list[int], predicted: list[int]) -> dict[str, float | int]:
    tp = sum(t == 1 and p == 1 for t, p in zip(truth, predicted))
    tn = sum(t == 0 and p == 0 for t, p in zip(truth, predicted))
    fp = sum(t == 0 and p == 1 for t, p in zip(truth, predicted))
    fn = sum(t == 1 and p == 0 for t, p in zip(truth, predicted))
    sens = tp / (tp + fn) if tp + fn else math.nan
    spec = tn / (tn + fp) if tn + fp else math.nan
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "sensitivity": sens, "specificity": spec, "balanced_accuracy": (sens + spec) / 2}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin", type=Path, required=True)
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--bundle-key",
        type=Path,
        default=ROOT / "paper_prep/rater_admin_keys_20260711/t5_sa3_calibration/T5_BUNDLE_KEY.csv",
    )
    args = parser.parse_args()
    admin = read_csv(args.admin)
    ratings = remap_bundle_rows(
        read_csv(args.ratings), args.bundle_key, scorer_id_field="blind_id"
    )
    validate_ids(admin, ratings)
    validate_real_provenance(ratings)
    rated = {row["blind_id"]: row for row in ratings}
    results = {}
    for construct in ("label_a",):
        truth = []
        predicted = []
        abstains = 0
        for row in admin:
            rating = rated[row["blind_id"]]
            if construct == "label_a":
                value = rating["label_a_voice_presence"].strip().lower()
                if value == "unsure":
                    abstains += 1
                    continue
                if value not in {"yes", "no"}:
                    raise ValueError(f"invalid or missing Label A for {row['blind_id']}")
                target = int(value == "yes")
            truth.append(target)
            predicted.append(int(row["demucs_present_0p1791"]))
        results[construct] = {**confusion(truth, predicted), "decided": len(truth), "abstains": abstains}
    passed = float(results["label_a"]["balanced_accuracy"]) >= 0.70
    status = "SCORED_PASS" if passed else "SCORED_FAIL"
    report = f"""# SA3 Label Calibration Result

`SA3_LABEL_CALIBRATION_STATUS = {status}`

| Construct | Decided | Abstains | Sensitivity | Specificity | Balanced accuracy |
|---|---:|---:|---:|---:|---:|
| Label A | {results['label_a']['decided']} | {results['label_a']['abstains']} | {results['label_a']['sensitivity']:.6f} | {results['label_a']['specificity']:.6f} | {results['label_a']['balanced_accuracy']:.6f} |
The mechanical package criterion requires Label-A balanced accuracy at least
0.70. Human labels remain the reference; this score does
not convert Demucs into ground truth.
"""
    args.report.write_text(report, encoding="utf-8")
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
