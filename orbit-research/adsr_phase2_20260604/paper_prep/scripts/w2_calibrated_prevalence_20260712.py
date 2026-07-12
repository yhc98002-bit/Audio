#!/usr/bin/env python3
"""Design-weighted W2 calibration model and nested prevalence bootstrap."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold


FORMS = ("M0", "M1", "M2")
L2_VALUES = (0.1, 1.0, 10.0)
BOOTSTRAP_SEED = 20260712


class Transform:
    FIELDS = (
        "demucs_low",
        "demucs_high",
        "panns_low",
        "panns_high",
        "demucs_mean",
        "demucs_scale",
        "panns_mean",
        "panns_scale",
    )

    def __init__(self, **values: float):
        missing = set(self.FIELDS) - set(values)
        extra = set(values) - set(self.FIELDS)
        if missing or extra:
            raise ValueError(f"invalid transform fields: missing={sorted(missing)}, extra={sorted(extra)}")
        for field in self.FIELDS:
            setattr(self, field, float(values[field]))

    def as_dict(self) -> dict:
        return {field: getattr(self, field) for field in self.FIELDS}


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


def _logit(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))


def fit_transform(rows: list[dict]) -> Transform:
    demucs = np.asarray([float(row["demucs_score"]) for row in rows])
    panns = np.asarray([float(row["panns_score"]) for row in rows])
    d_low, d_high = np.quantile(demucs, [0.01, 0.99])
    p_low, p_high = np.quantile(panns, [0.01, 0.99])
    d = _logit(np.clip(demucs, d_low, d_high))
    p = _logit(np.clip(panns, p_low, p_high))
    return Transform(
        demucs_low=float(d_low),
        demucs_high=float(d_high),
        panns_low=float(p_low),
        panns_high=float(p_high),
        demucs_mean=float(d.mean()),
        demucs_scale=float(max(d.std(), 1e-6)),
        panns_mean=float(p.mean()),
        panns_scale=float(max(p.std(), 1e-6)),
    )


def design_matrix(rows: list[dict], form: str, transform: Transform) -> np.ndarray:
    if form not in FORMS:
        raise ValueError(f"unknown form {form!r}")
    request = np.asarray([float(row["requested_vocal"]) for row in rows])
    demucs_raw = np.asarray([float(row["demucs_score"]) for row in rows])
    panns_raw = np.asarray([float(row["panns_score"]) for row in rows])
    demucs = (
        _logit(np.clip(demucs_raw, transform.demucs_low, transform.demucs_high))
        - transform.demucs_mean
    ) / transform.demucs_scale
    panns = (
        _logit(np.clip(panns_raw, transform.panns_low, transform.panns_high))
        - transform.panns_mean
    ) / transform.panns_scale
    columns = [request]
    if form in {"M1", "M2"}:
        columns.extend([demucs, panns])
    if form == "M2":
        columns.extend([request * demucs, request * panns])
    return np.column_stack(columns)


def _labels(rows: list[dict]) -> np.ndarray:
    values = np.asarray([int(row["truth_violation"]) for row in rows], dtype=int)
    if set(values) != {0, 1}:
        raise ValueError("calibration fitting requires both Label-B classes")
    return values


def _weights(rows: list[dict]) -> np.ndarray:
    values = np.asarray([float(row.get("design_weight", 1.0)) for row in rows])
    if np.any(values <= 0) or not np.all(np.isfinite(values)):
        raise ValueError("design weights must be finite and positive")
    return values


def fit_model(rows: list[dict], form: str, l2: float, transform: Transform) -> LogisticRegression:
    model = LogisticRegression(
        C=1.0 / l2,
        penalty="l2",
        solver="lbfgs",
        max_iter=1000,
        random_state=BOOTSTRAP_SEED,
    )
    model.fit(design_matrix(rows, form, transform), _labels(rows), sample_weight=_weights(rows))
    return model


def select_model(rows: list[dict]) -> dict:
    if len({row["prompt_id"] for row in rows}) < 5:
        raise ValueError("five-fold prompt-grouped selection requires at least five prompts")
    transform = fit_transform(rows)
    groups = np.asarray([row["prompt_id"] for row in rows])
    labels = _labels(rows)
    weights = _weights(rows)
    splitter = GroupKFold(n_splits=5)
    candidates = []
    for form in FORMS:
        matrix = design_matrix(rows, form, transform)
        for l2 in L2_VALUES:
            losses = []
            for train_index, test_index in splitter.split(matrix, labels, groups):
                train_rows = [rows[int(index)] for index in train_index]
                if len(set(_labels(train_rows))) < 2:
                    losses.append(math.inf)
                    continue
                model = fit_model(train_rows, form, l2, transform)
                probability = model.predict_proba(matrix[test_index])[:, 1]
                losses.append(
                    float(
                        log_loss(
                            labels[test_index],
                            probability,
                            sample_weight=weights[test_index],
                            labels=[0, 1],
                        )
                    )
                )
            finite = [value for value in losses if math.isfinite(value)]
            mean = float(np.mean(finite)) if len(finite) == 5 else math.inf
            se = float(np.std(finite, ddof=1) / math.sqrt(5)) if len(finite) == 5 else math.inf
            candidates.append({"form": form, "l2": l2, "fold_losses": losses, "mean_log_loss": mean, "se_log_loss": se})
    best = min(candidates, key=lambda row: (row["mean_log_loss"], FORMS.index(row["form"]), row["l2"]))
    cutoff = best["mean_log_loss"] + best["se_log_loss"]
    eligible = [row for row in candidates if row["mean_log_loss"] <= cutoff]
    selected = min(eligible, key=lambda row: (FORMS.index(row["form"]), row["l2"], row["mean_log_loss"]))
    model = fit_model(rows, selected["form"], selected["l2"], transform)
    return {
        "status": "TRAIN_ONLY_MODEL_SELECTED",
        "selection_rule": "prompt_grouped_5fold_weighted_logloss_one_SE_then_simpler_form_then_lower_L2",
        "selected": selected,
        "best_raw": best,
        "candidates": candidates,
        "transform": transform.as_dict(),
        "model": model,
    }


def predict_probability(rows: list[dict], fit: dict) -> np.ndarray:
    transform = Transform(**fit["transform"])
    return fit["model"].predict_proba(
        design_matrix(rows, fit["selected"]["form"], transform)
    )[:, 1]


def _resample_calibration(rows: list[dict], rng: np.random.Generator) -> list[dict]:
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        strata[row["calibration_stratum"]].append(row)
    sampled = []
    for stratum in sorted(strata):
        source = strata[stratum]
        sampled.extend(source[int(index)] for index in rng.integers(0, len(source), len(source)))
    return sampled


def _resample_target(rows: list[dict], rng: np.random.Generator) -> list[dict]:
    prompts: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        prompts[row["prompt_id"]].append(row)
    prompt_ids = sorted(prompts)
    sampled_ids = rng.choice(prompt_ids, size=len(prompt_ids), replace=True)
    return [row for prompt_id in sampled_ids for row in prompts[str(prompt_id)]]


def nested_bootstrap(
    calibration_rows: list[dict],
    target_rows: list[dict],
    *,
    replicates: int = 10_000,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    if not calibration_rows or not target_rows:
        raise ValueError("calibration and target rows must be non-empty")
    fit = select_model(calibration_rows)
    target_probability = predict_probability(target_rows, fit)
    target_weights = _weights(target_rows)
    point = float(np.average(target_probability, weights=target_weights))
    apparent = float(
        np.average(
            np.asarray([float(row["apparent_violation"]) for row in target_rows]),
            weights=target_weights,
        )
    )
    rng = np.random.default_rng(seed)
    estimates = []
    failures = Counter()
    for _ in range(replicates):
        sampled_calibration = _resample_calibration(calibration_rows, rng)
        sampled_target = _resample_target(target_rows, rng)
        try:
            sampled_fit = select_model(sampled_calibration)
            probability = predict_probability(sampled_target, sampled_fit)
            estimates.append(float(np.average(probability, weights=_weights(sampled_target))))
        except (ValueError, np.linalg.LinAlgError) as exc:
            failures[type(exc).__name__] += 1
    if len(estimates) < max(10, int(replicates * 0.8)):
        raise RuntimeError(f"too few valid nested-bootstrap replicates: {len(estimates)}/{replicates}")
    return {
        "apparent_rate": apparent,
        "calibrated_rate": point,
        "joint_95_interval": [float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))],
        "bootstrap_seed": seed,
        "requested_replicates": replicates,
        "valid_replicates": len(estimates),
        "failure_counts": dict(failures),
        "selected_form": fit["selected"]["form"],
        "selected_l2": fit["selected"]["l2"],
        "selection_audit": {key: value for key, value in fit.items() if key != "model"},
    }


def _prepared_rows(rows: list[dict[str, str]], calibration: bool) -> list[dict]:
    output = []
    for row in rows:
        prepared = {
            **row,
            "requested_vocal": int(row["requested_vocal"]),
            "demucs_score": float(row["demucs_score"]),
            "panns_score": float(row["panns_score"]),
            "design_weight": float(row.get("design_weight", 1.0)),
        }
        if calibration:
            prepared["truth_violation"] = int(row["truth_violation"])
        else:
            prepared["apparent_violation"] = int(row["apparent_violation"])
        output.append(prepared)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--promotion-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=10_000)
    args = parser.parse_args()
    promotion = json.loads(args.promotion_record.read_text(encoding="utf-8"))
    if promotion.get("CORRECTED_INSTRUMENT_STATUS") != "PASS_DUAL_PI_ADOPTED":
        raise SystemExit("corrected instrument is not dual-PI promoted; calibrated headline is blocked")
    result = nested_bootstrap(
        _prepared_rows(read_csv(args.calibration), calibration=True),
        _prepared_rows(read_csv(args.target), calibration=False),
        replicates=args.replicates,
    )
    serializable = {**result, "promotion_record": str(args.promotion_record)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(serializable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
