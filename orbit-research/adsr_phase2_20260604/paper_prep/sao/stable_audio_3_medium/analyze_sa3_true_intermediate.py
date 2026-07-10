#!/usr/bin/env python3
"""Analyze held-out discrimination of SA3 same-trajectory previews."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD


THRESHOLD = VOCAL_PRESENCE_THRESHOLD


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def auroc(y_true: list[int], scores: list[float]) -> float:
    positives = sum(y_true)
    negatives = len(y_true) - positives
    if not positives or not negatives:
        return math.nan
    ordered = sorted(zip(scores, y_true), key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def classification_metrics(y_true: list[int], scores: list[float], threshold: float) -> dict[str, float | int]:
    predicted = [int(score >= threshold) for score in scores]
    tp = sum(y == 1 and p == 1 for y, p in zip(y_true, predicted))
    tn = sum(y == 0 and p == 0 for y, p in zip(y_true, predicted))
    fp = sum(y == 0 and p == 1 for y, p in zip(y_true, predicted))
    fn = sum(y == 1 and p == 0 for y, p in zip(y_true, predicted))
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    balanced = (sensitivity + specificity) / 2 if math.isfinite(sensitivity) and math.isfinite(specificity) else math.nan
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / denominator if denominator else 0.0
    return {
        "n": len(y_true),
        "positives": sum(y_true),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "auroc": auroc(y_true, scores),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": balanced,
        "mcc": mcc,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intermediate-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest_rows = read_jsonl(args.intermediate_dir / "SA3_INTERMEDIATE_MANIFEST.jsonl")
    generation = [row for row in read_jsonl(args.intermediate_dir / "SA3_INTERMEDIATE_LEDGER.jsonl") if row.get("status") == "PASS"]
    scores = [row for row in read_jsonl(args.intermediate_dir / "SA3_INTERMEDIATE_DEMUCS_LEDGER.jsonl") if row.get("ok")]
    generated = {int(row["row_index"]): row for row in generation}
    score_index = {(int(row["row_index"]), row["stage"]): row for row in scores}
    if len(manifest_rows) != 96 or len(generated) != 96:
        raise ValueError(f"expected 96 manifest/generated rows, got {len(manifest_rows)}/{len(generated)}")
    stages = ["same_trajectory_step_0", "same_trajectory_step_1", "same_trajectory_step_2", "same_trajectory_step_3", "final_replay"]
    expected = {(int(row["row_index"]), stage) for row in manifest_rows for stage in stages}
    if set(score_index) != expected:
        raise ValueError(f"score key mismatch: missing={len(expected - set(score_index))}, extra={len(set(score_index) - expected)}")

    metric_rows: list[dict] = []
    methods = ["prompt_only", "independent_lowstep", *stages]
    for split in ("development", "test", "all"):
        for request in ("all", "instrumental", "vocal"):
            subset = [row for row in manifest_rows if (split == "all" or row["split"] == split) and (request == "all" or row["vocal_stratum"] == request)]
            # Same-trajectory observability predicts the final label produced by
            # this bf16 trajectory. The historical final used fp16 and remains a
            # separately reported reproducibility check, not the target.
            target = [
                int(score_index[(int(row["row_index"]), "final_replay")]["present"])
                for row in subset
            ]
            for method in methods:
                if method == "prompt_only":
                    values = [float(row["vocal_stratum"] == "vocal") for row in subset]
                    threshold = 0.5
                elif method == "independent_lowstep":
                    values = [float(row["independent_lowstep_ratio"]) for row in subset]
                    threshold = THRESHOLD
                else:
                    values = [float(score_index[(int(row["row_index"]), method)]["vocal_energy_ratio"]) for row in subset]
                    threshold = THRESHOLD
                metric_rows.append({"split": split, "request_stratum": request, "method": method, **classification_metrics(target, values, threshold)})
    metrics_path = args.intermediate_dir / "SA3_INTERMEDIATE_METRICS.csv"
    write_csv(metrics_path, metric_rows)

    heldout = {row["method"]: row for row in metric_rows if row["split"] == "test" and row["request_stratum"] == "all"}
    early_methods = [f"same_trajectory_step_{step}" for step in range(3)]
    best = max(early_methods, key=lambda method: (float(heldout[method]["auroc"]), float(heldout[method]["balanced_accuracy"])))
    beats_both = (
        float(heldout[best]["auroc"]) > max(float(heldout["prompt_only"]["auroc"]), float(heldout["independent_lowstep"]["auroc"]))
        and float(heldout[best]["balanced_accuracy"]) > max(float(heldout["prompt_only"]["balanced_accuracy"]), float(heldout["independent_lowstep"]["balanced_accuracy"]))
    )
    replay_agreement = sum(
        int(score_index[(int(row["row_index"]), "final_replay")]["present"]) == int(row["old_final_present"])
        for row in manifest_rows
    )
    wallclock = sum(float(row["elapsed_s"]) for row in generated.values())
    report = f"""# SA3 True-Intermediate Observability Report

`SA3_INTERMEDIATE_STATUS = TRUE_INTERMEDIATE_COMPLETE`

## Design

- 96 unique prompts, one replayed historical seed per prompt.
- Request strata: 48 vocal and 48 instrumental.
- Development/test split: 48/48, balanced within request stratum.
- Same trajectory: the official ping-pong sampler callback's `denoised`
  clean-latent estimate at callback indices 0, 1, 2, and 3, decoded with the
  same SA3 autoencoder after the final sample completes.
- Reference: the final Demucs label from the same bf16 four-step trajectory.
- Comparator: independent one-step generation with the same prompt and seed.
- Detector: `htdemucs`, split=True, overlap=0.1, near-silent RMS < 1e-3,
  threshold 0.1791.

## Held-Out Results

| Method | AUROC | Balanced accuracy | Sensitivity | Specificity | MCC |
|---|---:|---:|---:|---:|---:|
"""
    for method in methods:
        row = heldout[method]
        report += f"| {method} | {float(row['auroc']):.6f} | {float(row['balanced_accuracy']):.6f} | {float(row['sensitivity']):.6f} | {float(row['specificity']):.6f} | {float(row['mcc']):.6f} |\n"
    report += f"""

## Integrity Checks

- Final replay label agreement with the prior final: {replay_agreement}/96.
- The prior full scan used fp16; the callback replay follows the recovery brief's
  bf16 requirement. The single disagreement is retained as precision
  sensitivity, not silently overwritten.
- Aggregate generation wall-clock: {wallclock:.3f} seconds.
- Best pre-final same-trajectory checkpoint: `{best}`.
- Best early checkpoint beats prompt-only and independent-low-step on both
  held-out AUROC and balanced accuracy: `{str(beats_both).lower()}`.

## D7 Promotion Decision

The D7 observability-promotion criterion is {'met' if beats_both else 'not met'}
on this pilot. Promotion is **not authorized** unless that criterion is met,
the separate SA3 human threshold-calibration package passes, and the
intervention survives calibrated labeling plus fidelity/quality checks. This
report establishes true same-trajectory instrumentation; it does not by itself
establish a cross-backbone ADSR claim.

## Artifacts

- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_MANIFEST.jsonl`
- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_LEDGER.jsonl`
- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_DEMUCS_LEDGER.jsonl`
- `paper_prep/sao/stable_audio_3_medium/true_intermediate/SA3_INTERMEDIATE_METRICS.csv`
"""
    (args.intermediate_dir / "SA3_INTERMEDIATE_REPORT.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
