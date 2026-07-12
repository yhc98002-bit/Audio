#!/usr/bin/env python3
"""Select a corrected W2 detector on calibration data, then audit held-out PI gold."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from w2_instruments import THRESHOLD


def read_jsonl(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        rows.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    ids = [row["clip_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate PI-gold calibration result")
    if any(row.get("status") != "PASS" for row in rows):
        raise ValueError("PI-gold calibration contains failed rows")
    return rows


def metrics(truth: list[int], predicted: list[int]) -> dict[str, float | int]:
    tp = sum(t == 1 and p == 1 for t, p in zip(truth, predicted, strict=True))
    tn = sum(t == 0 and p == 0 for t, p in zip(truth, predicted, strict=True))
    fp = sum(t == 0 and p == 1 for t, p in zip(truth, predicted, strict=True))
    fn = sum(t == 1 and p == 0 for t, p in zip(truth, predicted, strict=True))
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "n": len(truth),
        "positives": tp + fn,
        "negatives": tn + fp,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "mcc": (tp * tn - fp * fn) / denominator if denominator else 0.0,
        "abstention_rate": 0.0,
    }


def thresholds(values: list[float]) -> list[float]:
    unique = sorted(set(values))
    if not unique:
        raise ValueError("cannot tune an empty score vector")
    output = [max(0.0, unique[0] - 1e-9)]
    output.extend((left + right) / 2 for left, right in zip(unique, unique[1:]))
    output.append(min(1.0 + 1e-9, unique[-1] + 1e-9))
    return output


def predict(rows: list[dict], family: str, demucs_threshold: float, panns_threshold: float) -> list[int]:
    output = []
    for row in rows:
        demucs = float(row["demucs_vocal_energy_ratio"]) >= demucs_threshold and not row["demucs_near_silent"]
        panns = float(row["panns_score"]) >= panns_threshold
        if family in {"current_demucs", "demucs"}:
            value = demucs
        elif family == "panns":
            value = panns
        elif family == "or":
            value = demucs or panns
        elif family == "and":
            value = demucs and panns
        else:
            raise ValueError(family)
        output.append(int(value))
    return output


def objective(value: dict) -> tuple[float, float, float, float]:
    return (
        float(value["balanced_accuracy"]),
        float(value["mcc"]),
        float(value["specificity"]),
        float(value["sensitivity"]),
    )


def tune(rows: list[dict], family: str) -> dict:
    truth = [int(row["true_label"] == "yes") for row in rows]
    demucs_values = thresholds([float(row["demucs_vocal_energy_ratio"]) for row in rows])
    panns_values = thresholds([float(row["panns_score"]) for row in rows])
    if family == "current_demucs":
        candidates = [(THRESHOLD, 0.5)]
    elif family == "demucs":
        candidates = [(value, 0.5) for value in demucs_values]
    elif family == "panns":
        candidates = [(THRESHOLD, value) for value in panns_values]
    else:
        candidates = [(d, p) for d in demucs_values for p in panns_values]
    best = None
    for demucs_threshold, panns_threshold in candidates:
        result = metrics(
            truth, predict(rows, family, demucs_threshold, panns_threshold)
        )
        record = {
            "family": family,
            "demucs_threshold": demucs_threshold,
            "panns_threshold": panns_threshold,
            "train_metrics": result,
        }
        if best is None or objective(result) > objective(best["train_metrics"]):
            best = record
    assert best is not None
    return best


def calibrate(rows: list[dict]) -> dict:
    calibration = [row for row in rows if row["split"] == "calibration"]
    heldout = [row for row in rows if row["split"] == "heldout"]
    if not calibration or not heldout:
        raise ValueError("both calibration and heldout PI-gold splits are required")
    candidates = [tune(calibration, family) for family in ("current_demucs", "demucs", "panns", "or", "and")]
    family_preference = {"demucs": 4, "panns": 3, "or": 2, "and": 1, "current_demucs": 0}
    selected = max(
        candidates,
        key=lambda row: (objective(row["train_metrics"]), family_preference[row["family"]]),
    )
    truth = [int(row["true_label"] == "yes") for row in heldout]
    for candidate in candidates:
        candidate["heldout_metrics"] = metrics(
            truth,
            predict(
                heldout,
                candidate["family"],
                candidate["demucs_threshold"],
                candidate["panns_threshold"],
            ),
        )
    selected = next(row for row in candidates if row["family"] == selected["family"])
    return {
        "status": "CALIBRATED_TRAIN_SELECTED_HELDOUT_AUDITED",
        "selection_rule": "maximize calibration balanced_accuracy, MCC, specificity, sensitivity; family tie-break demucs,panns,or,and,current",
        "calibration_rows": len(calibration),
        "heldout_rows": len(heldout),
        "candidates": candidates,
        "selected_candidate": selected,
        "plan_status_changed": False,
        "dual_pi_adoption_required": True,
    }


def write_report(result: dict, path: Path) -> None:
    lines = [
        "# W2 PI-Calibrated Instrument Report",
        "",
        "`W2_CALIBRATION_STATUS = COMPLETE_DUAL_PI_ADOPTION_REQUIRED`",
        "",
        f"The instrument family and threshold(s) were selected on {result['calibration_rows']} PI-gold clips before the held-out {result['heldout_rows']} clips were evaluated. This calibration does not modify frozen evidence, `PLAN.md`, or any gate status.",
        "",
        "| Candidate | Demucs threshold | PANNs threshold | Train balanced accuracy | Held-out sensitivity | Held-out specificity | Held-out balanced accuracy | Held-out MCC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for candidate in result["candidates"]:
        train = candidate["train_metrics"]
        test = candidate["heldout_metrics"]
        lines.append(
            f"| {candidate['family']} | {candidate['demucs_threshold']:.8f} | {candidate['panns_threshold']:.8f} | {train['balanced_accuracy']:.6f} | {test['sensitivity']:.6f} | {test['specificity']:.6f} | {test['balanced_accuracy']:.6f} | {test['mcc']:.6f} |"
        )
    selected = result["selected_candidate"]
    lines.extend(
        [
            "",
            "## Frozen Selection",
            "",
            f"- Family: `{selected['family']}`.",
            f"- Demucs threshold: `{selected['demucs_threshold']:.10f}`.",
            f"- PANNs threshold: `{selected['panns_threshold']:.10f}`.",
            "- Selection used calibration metrics only; the held-out result did not alter the chosen family or thresholds.",
            "- Adoption into headline claims requires dual-PI review of the downstream old-versus-corrected diff.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = calibrate(read_jsonl(args.scores))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result, args.report)
    print(json.dumps(result["selected_candidate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
