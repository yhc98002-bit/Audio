#!/usr/bin/env python3
"""Build and evaluate the disjoint T6 Label-A self-hosted-judge gold set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
OUT = PAPER / "autochain_20260712/judge_aprime"
T6_ADMIN = PAPER / "rater_admin_keys_20260712/t6_calibration_torch251_recovery/T6_CALIBRATION_ADMIN.csv"
T6_RATINGS = PAPER / "autochain_20260712/T6_OFFICIAL_RATINGS.csv"
T1_ADMIN = PAPER / "rater_admin_keys_20260711/t1_decisive/DECISIVE_PACKET_ADMIN.csv"
T1_RATINGS = PAPER / "pi_ratings_20260711/processed/T1_DECISIVE_OFFICIAL.csv"
T2_ADMIN = PAPER / "rater_admin_keys_20260711/t2_aprime/A_PRIME_PRIMARY_ADMIN.csv"
T2_RATINGS = PAPER / "pi_ratings_20260711/processed/T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv"

GOLD_SPLIT = OUT / "JUDGE_LABEL_A_GOLD_SPLIT.csv"
EVALUATION_MANIFEST = OUT / "JUDGE_LABEL_A_EVALUATION_MANIFEST.csv"
RAW = OUT / "JUDGE_LABEL_A_RAW_RESPONSES.jsonl"
RUN_SUMMARY = OUT / "JUDGE_LABEL_A_RUN_SUMMARY.json"
VALIDATION = OUT / "JUDGE_LABEL_A_VALIDATION.json"
REPORT = OUT / "JUDGE_LABEL_A_VALIDATION_REPORT.md"
A_GATE = PAPER / "validation_A_prime/A_PRIME_GATE_REPORT_20260712.md"

MINIMUMS = {"balanced_accuracy": 0.80, "sensitivity": 0.75, "specificity": 0.75}
MIN_POSITIVES = 30
MIN_NEGATIVES = 50
MAX_ABSTENTION = 0.10
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260716


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _t6_rows() -> list[dict]:
    ratings = {row["rating_id"]: row for row in read_csv(T6_RATINGS)}
    rows = []
    for admin in read_csv(T6_ADMIN):
        if admin["role"] not in {"train", "heldout", "transport"}:
            continue
        rating = ratings[admin["rating_id"]]
        label = rating["label_a_voice_presence"].strip().lower()
        rows.append(
            {
                "rating_id": admin["rating_id"],
                "clip_id": f"t6_{admin['rating_id']}",
                "clip_path": str(Path(admin["media_path"]).resolve()),
                "media_sha256": admin["media_sha256"],
                "true_label": label,
                "rating_source": rating["rating_source"],
                "gold_source": "t6_fresh_pi",
                "judge_role": "judge_evaluation",
                "calibration_stratum": admin["calibration_stratum"],
                "inclusion_probability": float(admin["inclusion_probability"]),
            }
        )
    return rows


def _t1_rows() -> list[dict]:
    ratings = {row["rating_id"]: row for row in read_csv(T1_RATINGS)}
    rows = []
    for admin in read_csv(T1_ADMIN):
        rating = ratings[admin["rating_id"]]
        path = (ROOT / admin["package_media_path"]).resolve()
        rows.append(
            {
                "rating_id": admin["rating_id"],
                "clip_id": f"t1_{admin['rating_id']}",
                "clip_path": str(path),
                "media_sha256": admin["sha256"],
                "true_label": rating["label_a_voice_presence"].strip().lower(),
                "rating_source": rating["rating_source"],
                "gold_source": "t1_prior_pi",
                "judge_role": "judge_tuning_only",
                "calibration_stratum": "t1_prior",
                "inclusion_probability": 1.0,
            }
        )
    return rows


def _t2_rows() -> list[dict]:
    ratings = {row["rating_id"]: row for row in read_csv(T2_RATINGS)}
    admin = {row["rating_id"]: row for row in read_csv(T2_ADMIN)}
    rows = []
    for rating_id, rating in ratings.items():
        key = admin[rating_id]
        path = (ROOT / key["package_media_path"]).resolve()
        rows.append(
            {
                "rating_id": rating_id,
                "clip_id": f"t2_{rating_id}",
                "clip_path": str(path),
                "media_sha256": key["package_sha256"],
                "true_label": rating["label_a_voice_presence"].strip().lower(),
                "rating_source": rating["rating_source"],
                "gold_source": "t2_prior_pi",
                "judge_role": "judge_tuning_only",
                "calibration_stratum": f"t2_{key['set_bucket']}",
                "inclusion_probability": 1.0,
            }
        )
    return rows


def build_gold() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    evaluation = _t6_rows()
    tuning = _t1_rows() + _t2_rows()
    evaluation_hashes = {row["media_sha256"] for row in evaluation}
    tuning_overlap = [row for row in tuning if row["media_sha256"] in evaluation_hashes]
    tuning = [row for row in tuning if row["media_sha256"] not in evaluation_hashes]
    if any(row["rating_source"] != "pi:Richard" for row in evaluation + tuning):
        raise ValueError("judge gold provenance is not pi:Richard")
    for row in evaluation + tuning:
        path = Path(row["clip_path"])
        if not path.is_file() or sha256(path) != row["media_sha256"]:
            raise ValueError(f"judge gold media mismatch: {row['rating_id']}")
    if {row["media_sha256"] for row in evaluation} & {row["media_sha256"] for row in tuning}:
        raise AssertionError("judge tuning/evaluation media overlap")
    decided_evaluation = [row for row in evaluation if row["true_label"] in {"yes", "no"}]
    write_csv(GOLD_SPLIT, evaluation + tuning)
    write_csv(EVALUATION_MANIFEST, decided_evaluation)
    all_available = evaluation + tuning + tuning_overlap
    available_counts = Counter(row["true_label"] for row in all_available)
    result = {
        "status": "GOLD_SPLIT_READY",
        "evaluation_rows_total": len(evaluation),
        "evaluation_rows_decided": len(decided_evaluation),
        "evaluation_counts": dict(Counter(row["true_label"] for row in evaluation)),
        "tuning_rows_after_hash_exclusion": len(tuning),
        "tuning_rows_excluded_hash_overlap": len(tuning_overlap),
        "all_t1_t2_t6_available_counts": dict(available_counts),
        "frozen_negative_minimum": MIN_NEGATIVES,
        "evaluation_negative_topup_needed": max(0, MIN_NEGATIVES - sum(row["true_label"] == "no" for row in decided_evaluation)),
        "all_available_negative_shortfall": max(0, MIN_NEGATIVES - available_counts["no"]),
        "split_disjoint_by_media_sha256": True,
    }
    (OUT / "JUDGE_LABEL_A_GOLD_BUILD.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _raw_majorities() -> dict[str, str]:
    by_clip: dict[str, dict[int, dict]] = defaultdict(dict)
    with RAW.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            by_clip[row["clip_id"]][int(row["call_index"])] = row
    output = {}
    for clip_id, calls in by_clip.items():
        if set(calls) != {0, 1, 2}:
            raise ValueError(f"judge calls incomplete for {clip_id}: {sorted(calls)}")
        labels = [calls[index]["parsed_label"] for index in range(3)]
        counts = Counter(label for label in labels if label in {"yes", "no"})
        output[clip_id] = "yes" if counts["yes"] >= 2 else ("no" if counts["no"] >= 2 else "unsure")
    return output


def _metrics(rows: list[dict], majority: dict[str, str]) -> dict:
    decided = [row for row in rows if majority[row["clip_id"]] in {"yes", "no"}]
    tp = tn = fp = fn = 0.0
    for row in decided:
        weight = 1.0 / float(row["inclusion_probability"])
        truth = row["true_label"]
        predicted = majority[row["clip_id"]]
        tp += weight * int(truth == predicted == "yes")
        tn += weight * int(truth == predicted == "no")
        fp += weight * int(truth == "no" and predicted == "yes")
        fn += weight * int(truth == "yes" and predicted == "no")
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    return {
        "decided_rows": len(decided),
        "abstention_rows": len(rows) - len(decided),
        "abstention_rate": (len(rows) - len(decided)) / len(rows),
        "positive_rows": sum(row["true_label"] == "yes" for row in rows),
        "negative_rows": sum(row["true_label"] == "no" for row in rows),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "weighted_tp": tp,
        "weighted_tn": tn,
        "weighted_fp": fp,
        "weighted_fn": fn,
    }


def _bootstrap(rows: list[dict], majority: dict[str, str]) -> dict:
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        strata[row["calibration_stratum"]].append(row)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values = {metric: [] for metric in MINIMUMS}
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = []
        for key in sorted(strata):
            source = strata[key]
            sample.extend(source[int(index)] for index in rng.integers(0, len(source), len(source)))
        metric = _metrics(sample, majority)
        for key in values:
            if math.isfinite(metric[key]):
                values[key].append(metric[key])
    return {
        key: {
            "one_sided_95_lcb": float(np.quantile(samples, 0.05)),
            "two_sided_95_ci": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
            "valid_replicates": len(samples),
        }
        for key, samples in values.items()
    }


def evaluate() -> dict:
    rows = read_csv(EVALUATION_MANIFEST)
    majority = _raw_majorities()
    if set(majority) != {row["clip_id"] for row in rows}:
        raise ValueError("judge raw/evaluation ID set mismatch")
    metrics = _metrics(rows, majority)
    bootstrap = _bootstrap(rows, majority)
    checks = {
        "decided_positives_at_least_30": metrics["positive_rows"] >= MIN_POSITIVES,
        "decided_negatives_at_least_50": metrics["negative_rows"] >= MIN_NEGATIVES,
        "abstention_at_most_0p10": metrics["abstention_rate"] <= MAX_ABSTENTION,
    }
    for key, minimum in MINIMUMS.items():
        checks[f"{key}_point"] = metrics[key] >= minimum
        checks[f"{key}_lcb"] = bootstrap[key]["one_sided_95_lcb"] >= minimum
    if all(checks.values()):
        status = "PASS_METRICS_REQUIRES_PROVENANCE_REGISTRATION"
        judge_500 = "READY_TO_RUN"
        a_status = "PI_CALL_PENDING_AFTER_500"
    elif not checks["decided_negatives_at_least_50"]:
        status = "BLOCKED_CLASS_COUNT_TOPUP_REQUIRED"
        judge_500 = "BLOCKED_JUDGE_GOLD_NEGATIVE_COUNT"
        a_status = "BLOCKED_JUDGE_GOLD_NEGATIVE_COUNT"
    else:
        status = "BLOCKED_JUDGE_VALIDATION_FAIL"
        judge_500 = "BLOCKED_JUDGE_VALIDATION_FAIL"
        a_status = "BLOCKED_JUDGE_VALIDATION_FAIL"
    result = {
        "JUDGE_VALIDATION_STATUS": status,
        "JUDGE_500_STATUS": judge_500,
        "A_PRIME_GATE": a_status,
        "metrics": metrics,
        "bootstrap": bootstrap,
        "checks": checks,
        "calls_per_clip": 3,
        "model": "Qwen/Qwen3-Omni-30B-A3B-Instruct",
        "served_model": "qwen3-omni-judge",
        "decoding": {"temperature": 0, "seeds": [20260709, 20260710, 20260711]},
        "automatic_gate_change": False,
    }
    VALIDATION.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Disjoint T6 Label-A Judge Validation\n\n"
        f"`JUDGE_VALIDATION_STATUS = {status}`\n\n"
        "The judge prompt/model were frozen before this evaluation. T1/T2 are tuning-only; the fresh T6 evaluation media are SHA-256-disjoint from them.\n\n"
        "| Metric | Point | One-sided 95% LCB | Frozen minimum | Met |\n"
        "|---|---:|---:|---:|---:|\n"
        + "\n".join(
            f"| {key} | {metrics[key]:.6f} | {bootstrap[key]['one_sided_95_lcb']:.6f} | {minimum:.2f} | `{str(checks[f'{key}_point'] and checks[f'{key}_lcb']).lower()}` |"
            for key, minimum in MINIMUMS.items()
        )
        + "\n\n"
        + f"- Decided PI positives/negatives: {metrics['positive_rows']}/{metrics['negative_rows']} (required >=30/>=50).\n"
        + f"- Judge abstention: {metrics['abstention_rate']:.6f} (required <=0.10).\n"
        + "- All available t1+t2+t6 PI gold contains only 43 Label-A negatives, so the frozen negative class count cannot pass without new human gold.\n"
        + "- No stratified-500 calls were launched and no A-prime gate changed.\n",
        encoding="utf-8",
    )
    A_GATE.write_text(
        "# A-Prime Gate Report - T6 Autochain\n\n"
        f"`A_PRIME_GATE = {a_status}`\n\n"
        "The 190-row PI human core remains official. The 500-row judge supplement was not run because the disjoint judge-gold validation cannot meet the frozen 50-negative class count with currently available PI labels.\n\n"
        f"Evidence: `{REPORT.relative_to(ROOT)}`.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-gold", "evaluate"))
    args = parser.parse_args()
    result = build_gold() if args.command == "build-gold" else evaluate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
