#!/usr/bin/env python3
"""Prepare and mechanically evaluate the disjoint-gold W2 judge track."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rating_provenance import parse_rating_source


MINIMUMS = {"balanced_accuracy": 0.80, "sensitivity": 0.75, "specificity": 0.75}
MIN_POSITIVES = 30
MIN_NEGATIVES = 50
MAX_ABSTENTION = 0.10


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
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


def build_disjoint_gold(admin_rows: list[dict], rating_rows: list[dict]) -> list[dict]:
    ratings = {row["rating_id"]: row for row in rating_rows}
    if set(ratings) != {row["rating_id"] for row in admin_rows}:
        raise ValueError("gold admin/rating ID sets differ")
    output = []
    seen_hash_role: dict[str, str] = {}
    for admin in admin_rows:
        if admin["role"] not in {"train", "heldout"}:
            continue
        rating = ratings[admin["rating_id"]]
        source = parse_rating_source(rating.get("rating_source", ""))
        if source.kind not in {"pi", "human"}:
            raise ValueError("judge gold must originate from pi/human ratings")
        label = rating.get("label_b_constraint", "").strip().lower()
        if label not in {"satisfied", "violated", "unsure"}:
            raise ValueError(f"invalid gold label {label!r}")
        media_hash = admin["media_sha256"]
        role = "judge_tuning" if admin["role"] == "train" else "judge_evaluation"
        previous = seen_hash_role.get(media_hash)
        if previous and previous != role:
            raise ValueError(f"media hash crosses judge tuning/evaluation: {media_hash}")
        seen_hash_role[media_hash] = role
        output.append(
            {
                "rating_id": admin["rating_id"],
                "clip_id": admin["canonical_clip_id"],
                "media_path": admin["media_path"],
                "media_sha256": media_hash,
                "request_mode": admin["request_mode"],
                "calibration_stratum": admin["calibration_stratum"],
                "inclusion_probability": admin["inclusion_probability"],
                "gold_label_b": label,
                "gold_violation": "" if label == "unsure" else int(label == "violated"),
                "gold_rating_source": source.raw,
                "judge_role": role,
            }
        )
    roles = defaultdict(set)
    for row in output:
        roles[row["judge_role"]].add(row["media_sha256"])
    if roles["judge_tuning"] & roles["judge_evaluation"]:
        raise AssertionError("judge gold split is not disjoint")
    return output


def majority_responses(raw_rows: list[dict[str, str]]) -> dict[str, str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in raw_rows:
        label = row["parsed_label_b"].strip().lower()
        if label not in {"satisfied", "violated", "unsure"}:
            raise ValueError(f"invalid judge label {label!r}")
        grouped[row["rating_id"]].append(label)
    output = {}
    for rating_id, labels in grouped.items():
        if len(labels) != 3:
            raise ValueError(f"judge clip {rating_id} has {len(labels)} calls, expected 3")
        counts = Counter(labels)
        decided = [(count, label) for label, count in counts.items() if label != "unsure"]
        if not decided or max(count for count, _ in decided) < 2:
            output[rating_id] = "unsure"
        else:
            output[rating_id] = max(decided)[1]
    return output


def _metrics(rows: list[dict], labels: dict[str, str]) -> dict:
    decided = []
    for row in rows:
        if row["gold_violation"] == "":
            continue
        predicted_label = labels.get(row["rating_id"], "unsure")
        if predicted_label == "unsure":
            continue
        decided.append(
            (
                int(row["gold_violation"]),
                int(predicted_label == "violated"),
                1.0 / float(row["inclusion_probability"]),
            )
        )
    if not decided:
        raise ValueError("no decided judge evaluation rows")
    y = np.asarray([row[0] for row in decided])
    p = np.asarray([row[1] for row in decided])
    w = np.asarray([row[2] for row in decided])
    tp = w[(y == 1) & (p == 1)].sum()
    fn = w[(y == 1) & (p == 0)].sum()
    tn = w[(y == 0) & (p == 0)].sum()
    fp = w[(y == 0) & (p == 1)].sum()
    sensitivity = float(tp / (tp + fn)) if tp + fn else math.nan
    specificity = float(tn / (tn + fp)) if tn + fp else math.nan
    return {
        "decided_rows": len(decided),
        "positive_rows": int(y.sum()),
        "negative_rows": int((y == 0).sum()),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
    }


def bootstrap_lcbs(rows: list[dict], labels: dict[str, str], replicates: int, seed: int) -> dict:
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        strata[row["calibration_stratum"]].append(row)
    rng = np.random.default_rng(seed)
    values = {metric: [] for metric in MINIMUMS}
    for _ in range(replicates):
        sample = []
        for stratum in sorted(strata):
            source = strata[stratum]
            sample.extend(source[int(index)] for index in rng.integers(0, len(source), len(source)))
        try:
            metrics = _metrics(sample, labels)
        except ValueError:
            continue
        for metric in values:
            if math.isfinite(metrics[metric]):
                values[metric].append(metrics[metric])
    return {
        metric: {
            "one_sided_95_lcb": float(np.quantile(samples, 0.05)),
            "valid_replicates": len(samples),
        }
        for metric, samples in values.items()
        if samples
    }


def evaluate_judge(gold_rows: list[dict], raw_rows: list[dict[str, str]], replicates: int = 10_000) -> dict:
    evaluation = [row for row in gold_rows if row["judge_role"] == "judge_evaluation"]
    labels = majority_responses(raw_rows)
    expected_ids = {row["rating_id"] for row in evaluation}
    if set(labels) != expected_ids:
        raise ValueError("judge responses do not exactly cover held-out evaluation IDs")
    metrics = _metrics(evaluation, labels)
    abstentions = sum(labels[row["rating_id"]] == "unsure" for row in evaluation)
    abstention_rate = abstentions / len(evaluation)
    bootstrap = bootstrap_lcbs(evaluation, labels, replicates, 20260712)
    checks = {
        "positive_rows": metrics["positive_rows"] >= MIN_POSITIVES,
        "negative_rows": metrics["negative_rows"] >= MIN_NEGATIVES,
        "abstention": abstention_rate <= MAX_ABSTENTION,
    }
    for metric, minimum in MINIMUMS.items():
        checks[f"{metric}_point"] = metrics[metric] >= minimum
        checks[f"{metric}_lcb"] = (
            metric in bootstrap and bootstrap[metric]["one_sided_95_lcb"] >= minimum
        )
    return {
        "JUDGE_PROMOTION_METRIC_GATE": "PASS" if all(checks.values()) else "FAIL",
        "JUDGE_VALIDATION_STATUS": (
            "METRIC_PASS_AWAITING_PROVENANCE_REGISTRATION"
            if all(checks.values())
            else "BLOCKED"
        ),
        "metrics": metrics,
        "abstention_rate": abstention_rate,
        "bootstrap": bootstrap,
        "checks": checks,
        "disjoint_gold_evaluation_rows": len(evaluation),
        "automatic_paper_gate_change": False,
    }


def stratified_500_result(
    manifest: list[dict[str, str]], raw_rows: list[dict[str, str]], validation: dict
) -> dict:
    if validation.get("JUDGE_PROMOTION_METRIC_GATE") != "PASS":
        raise ValueError("stratified-500 scoring requires a passed disjoint-gold metric gate")
    labels = majority_responses(raw_rows)
    if set(labels) != {row["rating_id"] for row in manifest}:
        raise ValueError("stratified-500 response ID mismatch")
    decided = [row for row in manifest if labels[row["rating_id"]] != "unsure"]
    weights = np.asarray([1.0 / float(row["inclusion_probability"]) for row in decided])
    violation = np.asarray([int(labels[row["rating_id"]] == "violated") for row in decided])
    rate = float(np.average(violation, weights=weights))
    rng = np.random.default_rng(20260712)
    boot = []
    for _ in range(10_000):
        index = rng.integers(0, len(decided), len(decided))
        boot.append(float(np.average(violation[index], weights=weights[index])))
    return {
        "judge_specific_calibrated_violation_rate": rate,
        "judge_specific_95_ci": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
        "decided_rows": len(decided),
        "abstention_rate": 1 - len(decided) / len(manifest),
        "merge_with_detector_forbidden": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-gold")
    build.add_argument("--admin", type=Path, required=True)
    build.add_argument("--ratings", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--gold", type=Path, required=True)
    evaluate.add_argument("--raw", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build-gold":
        rows = build_disjoint_gold(read_csv(args.admin), read_csv(args.ratings))
        write_csv(args.output, rows)
        print(json.dumps({"rows": len(rows), "roles": dict(Counter(row["judge_role"] for row in rows))}, indent=2))
    elif args.command == "evaluate":
        result = evaluate_judge(read_csv(args.gold), read_csv(args.raw))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
