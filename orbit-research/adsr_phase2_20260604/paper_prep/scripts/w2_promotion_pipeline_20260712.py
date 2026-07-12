#!/usr/bin/env python3
"""Mechanical W2 reliability, training selection, and held-out promotion scoring."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD
from rating_provenance import parse_rating_source


OLD_THRESHOLD = VOCAL_PRESENCE_THRESHOLD
FIXED_AND_DEMUCS = 0.038639528676867485
FIXED_AND_PANNS = 0.03181814216077328
FAMILIES = ("current_demucs", "demucs", "panns", "and", "or", "fixed_20260711_and")
METRIC_MINIMUMS = {"balanced_accuracy": 0.80, "sensitivity": 0.75, "specificity": 0.75}
MIN_POSITIVES = 30
MIN_NEGATIVES = 50
MIN_RELIABILITY = 0.85
MAX_REVERSALS = 2


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_human_source(value: str) -> str:
    source = parse_rating_source(value)
    if source.kind not in {"pi", "human"}:
        raise ValueError(f"W2 calibration requires pi/human provenance, got {value!r}")
    return source.raw


def join_rows(admin: list[dict[str, str]], ratings: list[dict[str, str]]) -> list[dict]:
    if not admin or not ratings:
        raise ValueError("admin and ratings must be non-empty")
    admin_ids = [row["rating_id"] for row in admin]
    rating_ids = [row["rating_id"] for row in ratings]
    if len(set(admin_ids)) != len(admin_ids) or len(set(rating_ids)) != len(rating_ids):
        raise ValueError("duplicate rating IDs")
    rating_index = {row["rating_id"]: row for row in ratings}
    if set(rating_index) != set(admin_ids):
        missing = sorted(set(admin_ids) - set(rating_index))
        extra = sorted(set(rating_index) - set(admin_ids))
        raise ValueError(f"rating/admin ID mismatch: missing={missing[:5]}, extra={extra[:5]}")
    joined = []
    for row in admin:
        rating = rating_index[row["rating_id"]]
        source = require_human_source(rating.get("rating_source", ""))
        label = rating.get("label_b_constraint", "").strip().lower()
        if label not in {"satisfied", "violated", "unsure"}:
            raise ValueError(f"invalid Label-B response for {row['rating_id']}: {label!r}")
        requested = int(row["requested_vocal"])
        if requested not in {0, 1}:
            raise ValueError(f"invalid requested_vocal for {row['rating_id']}")
        probability = float(row["inclusion_probability"])
        if not 0 < probability <= 1:
            raise ValueError(f"invalid inclusion probability for {row['rating_id']}")
        demucs_value = row.get("demucs_score", "")
        panns_value = row.get("panns_score", "")
        if row.get("role") != "appendix" and (demucs_value == "" or panns_value == ""):
            raise ValueError(f"missing instrument score for {row['rating_id']}")
        joined.append(
            {
                **row,
                "requested_vocal": requested,
                "demucs_score": float(demucs_value) if demucs_value != "" else math.nan,
                "panns_score": float(panns_value) if panns_value != "" else math.nan,
                "inclusion_probability": probability,
                "design_weight": 1.0 / probability,
                "label_b_constraint": label,
                "truth_violation": None if label == "unsure" else int(label == "violated"),
                "rating_source": source,
            }
        )
    return joined


def reliability(rows: list[dict]) -> dict:
    by_id = {row["rating_id"]: row for row in rows}
    repeats = [row for row in rows if row["role"] == "repeat"]
    if len(repeats) != 20:
        raise ValueError(f"expected 20 hidden repeats, found {len(repeats)}")
    exact = 0
    reversals = 0
    unsure_pairs = 0
    details = []
    for repeat in repeats:
        parent_id = repeat.get("repeat_parent_rating_id", "")
        parent = by_id.get(parent_id)
        if parent is None:
            raise ValueError(f"repeat {repeat['rating_id']} has missing parent {parent_id!r}")
        left = parent["label_b_constraint"]
        right = repeat["label_b_constraint"]
        is_exact = left == right
        is_reversal = {left, right} == {"satisfied", "violated"}
        exact += int(is_exact)
        reversals += int(is_reversal)
        unsure_pairs += int("unsure" in {left, right})
        details.append(
            {
                "repeat_rating_id": repeat["rating_id"],
                "parent_rating_id": parent_id,
                "parent_label_b": left,
                "repeat_label_b": right,
                "exact": is_exact,
                "satisfied_violated_reversal": is_reversal,
            }
        )
    rate = exact / len(repeats)
    passed = rate >= MIN_RELIABILITY and reversals <= MAX_REVERSALS
    return {
        "status": "PASS" if passed else "FAIL_CLARIFY_AND_RERATE",
        "repeat_pairs": len(repeats),
        "exact_agreement_count": exact,
        "exact_agreement": rate,
        "satisfied_violated_reversals": reversals,
        "unsure_in_pair_count": unsure_pairs,
        "minimum_exact_agreement": MIN_RELIABILITY,
        "maximum_reversals": MAX_REVERSALS,
        "details": details,
    }


def threshold_grid(values: Iterable[float]) -> list[float]:
    unique = sorted(set(float(value) for value in values))
    if not unique:
        raise ValueError("cannot build threshold grid from no values")
    grid = [math.nextafter(unique[0], -math.inf)]
    grid.extend((left + right) / 2 for left, right in zip(unique, unique[1:]))
    grid.append(math.nextafter(unique[-1], math.inf))
    return grid


def predictions(rows: list[dict], family: str, demucs_threshold: float, panns_threshold: float) -> np.ndarray:
    demucs = np.asarray([row["demucs_score"] >= demucs_threshold for row in rows], dtype=bool)
    panns = np.asarray([row["panns_score"] >= panns_threshold for row in rows], dtype=bool)
    if family in {"current_demucs", "demucs"}:
        present = demucs
    elif family == "panns":
        present = panns
    elif family in {"and", "fixed_20260711_and"}:
        present = demucs & panns
    elif family == "or":
        present = demucs | panns
    else:
        raise ValueError(f"unknown family {family!r}")
    requested = np.asarray([row["requested_vocal"] for row in rows], dtype=bool)
    return (present != requested).astype(int)


def weighted_metrics(rows: list[dict], predicted: np.ndarray) -> dict:
    decided = [(index, row) for index, row in enumerate(rows) if row["truth_violation"] is not None]
    if not decided:
        raise ValueError("no decided Label-B rows")
    y = np.asarray([row["truth_violation"] for _, row in decided], dtype=int)
    p = np.asarray([predicted[index] for index, _ in decided], dtype=int)
    w = np.asarray([row["design_weight"] for _, row in decided], dtype=float)
    tp = float(w[(y == 1) & (p == 1)].sum())
    fn = float(w[(y == 1) & (p == 0)].sum())
    tn = float(w[(y == 0) & (p == 0)].sum())
    fp = float(w[(y == 0) & (p == 1)].sum())
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    balanced = (sensitivity + specificity) / 2
    denominator = math.sqrt(max((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn), 0))
    mcc = (tp * tn - fp * fn) / denominator if denominator else math.nan
    return {
        "decided_rows": len(decided),
        "positive_rows": int(y.sum()),
        "negative_rows": int((y == 0).sum()),
        "abstention_rows": len(rows) - len(decided),
        "abstention_rate": (len(rows) - len(decided)) / len(rows),
        "weighted_tp": tp,
        "weighted_fn": fn,
        "weighted_tn": tn,
        "weighted_fp": fp,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": balanced,
        "mcc": mcc,
    }


def _candidate_key(candidate: dict) -> tuple:
    metrics = candidate["train_metrics"]
    complexity = {"current_demucs": 0, "demucs": 0, "panns": 0, "and": 1, "or": 1, "fixed_20260711_and": 1}
    return (
        metrics["balanced_accuracy"],
        min(metrics["sensitivity"], metrics["specificity"]),
        -math.inf if math.isnan(metrics["mcc"]) else metrics["mcc"],
        -complexity[candidate["family"]],
        -FAMILIES.index(candidate["family"]),
        -candidate["demucs_threshold"],
        -candidate["panns_threshold"],
    )


def select_candidate(train_rows: list[dict]) -> dict:
    if len(train_rows) != 60 or {row["role"] for row in train_rows} != {"train"}:
        raise ValueError("candidate selection requires exactly the frozen 60 training rows")
    if any(row["truth_violation"] is None for row in train_rows):
        raise ValueError("training selection requires decided labels")
    demucs_grid = threshold_grid(row["demucs_score"] for row in train_rows)
    panns_grid = threshold_grid(row["panns_score"] for row in train_rows)
    candidates = []

    def add(family: str, demucs_threshold: float, panns_threshold: float) -> None:
        pred = predictions(train_rows, family, demucs_threshold, panns_threshold)
        candidates.append(
            {
                "family": family,
                "demucs_threshold": demucs_threshold,
                "panns_threshold": panns_threshold,
                "train_metrics": weighted_metrics(train_rows, pred),
            }
        )

    add("current_demucs", OLD_THRESHOLD, math.inf)
    add("fixed_20260711_and", FIXED_AND_DEMUCS, FIXED_AND_PANNS)
    for threshold in demucs_grid:
        add("demucs", threshold, math.inf)
    for threshold in panns_grid:
        add("panns", math.inf, threshold)
    for demucs_threshold in demucs_grid:
        for panns_threshold in panns_grid:
            add("and", demucs_threshold, panns_threshold)
            add("or", demucs_threshold, panns_threshold)
    selected = max(candidates, key=_candidate_key)
    return {
        "status": "TRAIN_SELECTED_HELDOUT_UNSEEN",
        "training_rows": len(train_rows),
        "candidate_count": len(candidates),
        "selection_rule": "weighted_BA_then_min_sens_spec_then_MCC_then_simplicity_then_deterministic_threshold",
        "selected_candidate": selected,
        "family_best": {
            family: max((row for row in candidates if row["family"] == family), key=_candidate_key)
            for family in FAMILIES
        },
    }


def stratified_bootstrap_lcbs(
    rows: list[dict],
    family: str,
    demucs_threshold: float,
    panns_threshold: float,
    *,
    replicates: int = 10_000,
    seed: int = 20260712,
) -> dict:
    decided = [row for row in rows if row["truth_violation"] is not None]
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in decided:
        strata[row["calibration_stratum"]].append(row)
    if not strata:
        raise ValueError("bootstrap has no decided strata")
    rng = np.random.default_rng(seed)
    values = {metric: [] for metric in METRIC_MINIMUMS}
    for _ in range(replicates):
        sample = []
        for stratum in sorted(strata):
            source = strata[stratum]
            indices = rng.integers(0, len(source), size=len(source))
            sample.extend(source[int(index)] for index in indices)
        metrics = weighted_metrics(
            sample,
            predictions(sample, family, demucs_threshold, panns_threshold),
        )
        for metric in values:
            if math.isfinite(metrics[metric]):
                values[metric].append(metrics[metric])
    output = {}
    for metric, samples in values.items():
        if not samples:
            raise ValueError(f"no finite bootstrap values for {metric}")
        output[metric] = {
            "one_sided_95_lcb": float(np.quantile(samples, 0.05)),
            "two_sided_95_ci": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
            "valid_replicates": len(samples),
        }
    return {"seed": seed, "requested_replicates": replicates, "strata": len(strata), "metrics": output}


def evaluate_heldout(
    heldout: list[dict],
    selection: dict,
    reliability_result: dict,
    *,
    bootstrap_replicates: int = 10_000,
    bootstrap_seed: int = 20260712,
) -> dict:
    if reliability_result["status"] != "PASS":
        raise ValueError("held-out evaluation is blocked until reliability passes")
    if len(heldout) < 100 or {row["role"] for row in heldout} != {"heldout"}:
        raise ValueError("held-out evaluation requires the frozen held-out rows only")
    decided_truth = [row["truth_violation"] for row in heldout if row["truth_violation"] is not None]
    positive_rows = sum(int(value) for value in decided_truth)
    negative_rows = len(decided_truth) - positive_rows
    if positive_rows < MIN_POSITIVES or negative_rows < MIN_NEGATIVES:
        return {
            "mechanical_promotion_gate": "NOT_RUN_TOPUP_REQUIRED",
            "corrected_instrument_status": "AWAITING_CLASS_COUNT_TOPUP",
            "plan_or_claim_status_changed": False,
            "heldout_decided_positive_rows": positive_rows,
            "heldout_decided_negative_rows": negative_rows,
            "topup_needed_positive": max(0, MIN_POSITIVES - positive_rows),
            "topup_needed_negative": max(0, MIN_NEGATIVES - negative_rows),
            "topup_rule": "rate frozen reserve in committed order until each deficient class minimum is reached",
            "heldout_metrics_exposed": False,
        }
    selected = selection["selected_candidate"]
    predicted = predictions(
        heldout,
        selected["family"],
        selected["demucs_threshold"],
        selected["panns_threshold"],
    )
    metrics = weighted_metrics(heldout, predicted)
    bootstrap = stratified_bootstrap_lcbs(
        heldout,
        selected["family"],
        selected["demucs_threshold"],
        selected["panns_threshold"],
        replicates=bootstrap_replicates,
        seed=bootstrap_seed,
    )
    checks = {
        "decided_positives_at_least_30": metrics["positive_rows"] >= MIN_POSITIVES,
        "decided_negatives_at_least_50": metrics["negative_rows"] >= MIN_NEGATIVES,
        "reliability": reliability_result["status"] == "PASS",
    }
    for metric, minimum in METRIC_MINIMUMS.items():
        checks[f"{metric}_point_at_least_{minimum}"] = metrics[metric] >= minimum
        checks[f"{metric}_lcb_at_least_{minimum}"] = (
            bootstrap["metrics"][metric]["one_sided_95_lcb"] >= minimum
        )
    mechanical = "PASS" if all(checks.values()) else "FAIL"
    return {
        "mechanical_promotion_gate": mechanical,
        "corrected_instrument_status": (
            "AWAITING_DUAL_PI_PROMOTION_RECORD"
            if mechanical == "PASS"
            else "SENSITIVITY_ONLY"
        ),
        "plan_or_claim_status_changed": False,
        "selected_candidate": selected,
        "heldout_metrics": metrics,
        "bootstrap": bootstrap,
        "checks": checks,
        "failure_rule": "any failed check sets SENSITIVITY_ONLY; mechanical PASS cannot update PLAN",
    }


def _amendment_has_two_signatures(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS" not in text:
        return False
    return text.count("Commit SHA:") >= 2 and "______________________" not in text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin", type=Path, required=True)
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    args = parser.parse_args()
    if not _amendment_has_two_signatures(args.amendment):
        raise SystemExit("W2 amendment lacks two recorded PI signatures; refusing to expose labels")
    admin = read_csv(args.admin)
    ratings = read_csv(args.ratings)
    rows = join_rows(admin, ratings)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rel = reliability(rows)
    write_json(args.output_dir / "W2_RELIABILITY.json", rel)
    if rel["status"] != "PASS":
        raise SystemExit("intra-rater reliability failed; clarify and rerate before training exposure")
    selected = select_candidate([row for row in rows if row["role"] == "train"])
    write_json(args.output_dir / "W2_TRAIN_SELECTION.json", selected)
    heldout = evaluate_heldout(
        [row for row in rows if row["role"] == "heldout"],
        selected,
        rel,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    output = {
        "status": "COMPLETE_NO_AUTOMATIC_PLAN_CHANGE",
        "admin_sha256": sha256_file(args.admin),
        "ratings_sha256": sha256_file(args.ratings),
        "amendment_sha256": sha256_file(args.amendment),
        "rating_source_counts": dict(Counter(row["rating_source"] for row in rows)),
        "reliability": rel,
        "selection": selected,
        "heldout": heldout,
    }
    write_json(args.output_dir / "W2_PROMOTION_RESULT.json", output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
