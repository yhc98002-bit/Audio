#!/usr/bin/env python3
"""Complete pooled T7 judge validation and the A-prime judge supplement."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
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
OUT = PAPER / "t7_judge_gold_20260713/judge_completion"
BASE_GOLD = PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_EVALUATION_MANIFEST.csv"
T7_GOLD = PAPER / "t7_judge_gold_20260713/ratings_ingest/T7_ALL_DISJOINT_GOLD_MANIFEST.csv"
BASE_RAW = PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_RAW_RESPONSES.jsonl"
T7_RAW = OUT / "T7_JUDGE_RAW_RESPONSES.jsonl"
T7_RUN_SUMMARY = OUT / "T7_JUDGE_RUN_SUMMARY.json"
POOLED_GOLD = OUT / "POOLED_DISJOINT_GOLD_MANIFEST.csv"
POOLED_RAW = OUT / "POOLED_DISJOINT_GOLD_RAW_RESPONSES.jsonl"
VALIDATION_JSON = OUT / "POOLED_JUDGE_VALIDATION.json"
VALIDATION_REPORT = OUT / "POOLED_JUDGE_VALIDATION_REPORT.md"
GLOBAL_ADMIN = PAPER / "rater_admin_keys_20260711/t2_aprime/A_PRIME_PRIMARY_ADMIN.csv"
GLOBAL_SOURCE = PAPER / "storage_triage/A_PRIME_500_JUDGE_SAMPLE/manifest_enriched.csv"
GLOBAL_MANIFEST = OUT / "A_PRIME_STRATIFIED_500_JUDGE_MANIFEST.csv"
GLOBAL_MAPPING = OUT / "A_PRIME_STRATIFIED_500_RATING_TO_JUDGE_MAP.csv"
GLOBAL_RAW = OUT / "A_PRIME_STRATIFIED_500_RAW_RESPONSES.jsonl"
GLOBAL_RUN_SUMMARY = OUT / "A_PRIME_STRATIFIED_500_RUN_SUMMARY.json"
GLOBAL_RATINGS = OUT / "A_PRIME_STRATIFIED_500_JUDGE_RATINGS.csv"
GLOBAL_RESULTS = OUT / "A_PRIME_STRATIFIED_500_RESULTS.csv"
GLOBAL_REPORT = OUT / "A_PRIME_STRATIFIED_500_REPORT.md"
ALL_RAW = OUT / "A_PRIME_ALL_JUDGE_RAW_RESPONSES.jsonl"
JUDGE_METADATA = OUT / "A_PRIME_JUDGE_VALIDATION_METADATA.json"
CORE_RATINGS = PAPER / "pi_ratings_20260711/processed/T2_A_PRIME_HUMAN_CORE_OFFICIAL.csv"
MERGED = OUT / "A_PRIME_INSTRUMENT_MERGED_690.csv"
MERGE_REPORT = OUT / "A_PRIME_INSTRUMENT_MERGE_REPORT.json"
A_GATE = PAPER / "validation_A_prime/A_PRIME_GATE_REPORT_20260713.md"
A_GATE_JSON = PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json"
MODEL_ID = "Qwen3-Omni-30B-A3B-Instruct"
SERVED_MODEL = "qwen3-omni-judge"
MINIMUMS = {"balanced_accuracy": 0.80, "sensitivity": 0.75, "specificity": 0.75}
MIN_POSITIVES = 30
MIN_NEGATIVES = 50
MAX_ABSTENTION = 0.10
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260713


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def deduplicated_raw(paths: list[Path]) -> list[dict]:
    latest: dict[tuple[str, int], dict] = {}
    for path in paths:
        for row in read_jsonl(path):
            key = (str(row["clip_id"]), int(row["call_index"]))
            latest[key] = row
    return [latest[key] for key in sorted(latest)]


def majorities(raw_rows: list[dict]) -> dict[str, str]:
    calls: dict[str, dict[int, str | None]] = defaultdict(dict)
    for row in raw_rows:
        calls[str(row["clip_id"])][int(row["call_index"])] = row.get("parsed_label")
    output = {}
    for clip_id, by_call in calls.items():
        if set(by_call) != {0, 1, 2}:
            raise ValueError(f"incomplete judge calls for {clip_id}: {sorted(by_call)}")
        counts = Counter(label for label in by_call.values() if label in {"yes", "no"})
        output[clip_id] = "yes" if counts["yes"] >= 2 else ("no" if counts["no"] >= 2 else "unsure")
    return output


def prepare() -> dict:
    base = read_csv(BASE_GOLD)
    t7 = read_csv(T7_GOLD)
    if len(base) != 176 or len(t7) != 40:
        raise ValueError(f"pooled gold cardinality changed: {len(base)} + {len(t7)}")
    if {row["media_sha256"] for row in base} & {row["media_sha256"] for row in t7}:
        raise ValueError("T7 and prior disjoint-gold media hashes overlap")
    pooled = base + t7
    if len({row["clip_id"] for row in pooled}) != len(pooled):
        raise ValueError("pooled judge-gold clip IDs are not unique")
    for row in pooled:
        if row["true_label"] not in {"yes", "no"}:
            raise ValueError("pooled judge gold contains an undecided human label")
        path = Path(row["clip_path"])
        if not path.is_file() or sha256_file(path) != row["media_sha256"]:
            raise ValueError(f"pooled judge-gold media mismatch: {row['clip_id']}")
    write_csv(POOLED_GOLD, pooled)

    admin = [row for row in read_csv(GLOBAL_ADMIN) if row["analysis_role"] == "global_bound"]
    source_by_hash = {row["sha256"]: row for row in read_csv(GLOBAL_SOURCE)}
    if len(admin) != 500:
        raise ValueError(f"A-prime global admin changed: {len(admin)}")
    candidates = []
    for row in admin:
        path = ROOT / row["package_media_path"]
        if not path.is_file() or sha256_file(path) != row["package_sha256"]:
            raise ValueError(f"stratified-500 media mismatch: {row['rating_id']}")
        source = source_by_hash.get(row["package_sha256"])
        if source is None:
            raise ValueError(f"stratified-500 source metadata missing: {row['rating_id']}")
        candidates.append(
            {
                "rating_id": row["rating_id"],
                "clip_id": row["rating_id"],
                "clip_path": str(path.resolve()),
                "media_sha256": row["package_sha256"],
                "requested_vocal": row["requested_vocal"],
                "prompt_id": row["prompt_id"],
                "source_family": source["source_family"],
                "corpus": source["corpus"],
                "calibration_stratum": f"{source['corpus']}|{source['source_family']}|request_{row['requested_vocal']}",
                "inclusion_probability": "1.0",
            }
        )
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for row in candidates:
        by_hash[row["media_sha256"]].append(row)
    manifest = []
    mapping = []
    for digest, rows in sorted(by_hash.items()):
        metadata = {
            (row["requested_vocal"], row["prompt_id"], row["source_family"], row["corpus"])
            for row in rows
        }
        if len(metadata) != 1:
            raise ValueError(f"duplicate global audio has conflicting metadata: {digest}")
        representative = min(rows, key=lambda row: row["rating_id"])
        judge_clip_id = f"aprime_global_{digest[:20]}"
        manifest.append(
            {
                **representative,
                "clip_id": judge_clip_id,
                "represented_rating_rows": len(rows),
            }
        )
        mapping.extend(
            {
                "rating_id": row["rating_id"],
                "judge_clip_id": judge_clip_id,
                "media_sha256": digest,
                "duplicate_group_size": len(rows),
            }
            for row in rows
        )
    write_csv(GLOBAL_MANIFEST, manifest)
    write_csv(GLOBAL_MAPPING, sorted(mapping, key=lambda row: row["rating_id"]))
    result = {
        "status": "PREPARED",
        "pooled_gold_rows": len(pooled),
        "pooled_gold_counts": dict(Counter(row["true_label"] for row in pooled)),
        "t7_rows": len(t7),
        "t7_counts": dict(Counter(row["true_label"] for row in t7)),
        "pooled_unique_hashes": len({row["media_sha256"] for row in pooled}),
        "stratified_500_nominal_rows": len(candidates),
        "stratified_500_unique_inference_rows": len(manifest),
        "stratified_500_unique_hashes": len({row["media_sha256"] for row in manifest}),
        "stratified_500_duplicate_rows": len(candidates) - len(manifest),
        "pooled_gold_sha256": sha256_file(POOLED_GOLD),
    }
    (OUT / "JUDGE_COMPLETION_PREP_AUDIT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _confusion(rows: list[dict], labels: dict[str, str]) -> dict:
    tp = tn = fp = fn = 0.0
    unweighted = Counter()
    abstained = 0
    for row in rows:
        predicted = labels[row["clip_id"]]
        if predicted == "unsure":
            abstained += 1
            continue
        truth = row["true_label"]
        weight = 1.0 / float(row["inclusion_probability"])
        key = "tp" if truth == predicted == "yes" else "tn" if truth == predicted == "no" else "fp" if truth == "no" else "fn"
        if key == "tp":
            tp += weight
        elif key == "tn":
            tn += weight
        elif key == "fp":
            fp += weight
        else:
            fn += weight
        unweighted[key] += 1
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    denominator = math.sqrt((unweighted["tp"] + unweighted["fp"]) * (unweighted["tp"] + unweighted["fn"]) * (unweighted["tn"] + unweighted["fp"]) * (unweighted["tn"] + unweighted["fn"]))
    return {
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "mcc": ((unweighted["tp"] * unweighted["tn"] - unweighted["fp"] * unweighted["fn"]) / denominator if denominator else math.nan),
        "abstention_rate": abstained / len(rows),
        "abstentions": abstained,
        "weighted_tp": tp,
        "weighted_tn": tn,
        "weighted_fp": fp,
        "weighted_fn": fn,
        "unweighted_confusion": dict(unweighted),
    }


def _validation_bootstrap(rows: list[dict], labels: dict[str, str]) -> dict:
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        strata[f"{row['gold_source']}|{row['calibration_stratum']}|{row['true_label']}"].append(row)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    values = {key: [] for key in MINIMUMS}
    for _ in range(BOOTSTRAP_REPLICATES):
        sample = []
        for key in sorted(strata):
            source = strata[key]
            sample.extend(source[int(index)] for index in rng.integers(0, len(source), len(source)))
        metrics = _confusion(sample, labels)
        for key in values:
            if math.isfinite(metrics[key]):
                values[key].append(metrics[key])
    return {
        key: {
            "one_sided_95_lcb": float(np.quantile(samples, 0.05)),
            "two_sided_95_ci": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
            "valid_replicates": len(samples),
        }
        for key, samples in values.items()
    }


def evaluate_validation() -> dict:
    rows = read_csv(POOLED_GOLD)
    raw = deduplicated_raw([BASE_RAW, T7_RAW])
    labels = majorities(raw)
    expected = {row["clip_id"] for row in rows}
    if set(labels) != expected:
        raise ValueError(f"pooled judge response mismatch: missing={len(expected-set(labels))}, extra={len(set(labels)-expected)}")
    write_jsonl(POOLED_RAW, raw)
    metrics = _confusion(rows, labels)
    bootstrap = _validation_bootstrap(rows, labels)
    counts = Counter(row["true_label"] for row in rows)
    checks = {
        "positive_rows_at_least_30": counts["yes"] >= MIN_POSITIVES,
        "negative_rows_at_least_50": counts["no"] >= MIN_NEGATIVES,
        "abstention_at_most_0p10": metrics["abstention_rate"] <= MAX_ABSTENTION,
    }
    for key, minimum in MINIMUMS.items():
        checks[f"{key}_point"] = metrics[key] >= minimum
        checks[f"{key}_lcb"] = bootstrap[key]["one_sided_95_lcb"] >= minimum
    status = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "JUDGE_VALIDATION_STATUS": status,
        "model_id": MODEL_ID,
        "served_model": SERVED_MODEL,
        "gold_set_hash": sha256_file(POOLED_GOLD),
        "class_composition": {"positive_yes": counts["yes"], "negative_no": counts["no"]},
        "source_composition": dict(Counter(row["gold_source"] for row in rows)),
        "metrics": metrics,
        "bootstrap": bootstrap,
        "checks": checks,
        "calls_per_clip": 3,
        "decoding": {"temperature": 0, "seeds": [20260709, 20260710, 20260711]},
        "tuning_and_evaluation_overlap": 0,
    }
    VALIDATION_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    VALIDATION_REPORT.write_text(
        "# Pooled Disjoint-Gold Label-A Judge Validation\n\n"
        f"`JUDGE_VALIDATION_STATUS = {status}`\n\n"
        f"The held-out pool contains {counts['yes']} human `yes` positives from the existing disjoint T6 set and {counts['no']} human `no` negatives: 27 existing plus all 40 T7 rows. T7 is intentionally all-negative; sensitivity therefore comes from pooled existing positives and specificity from all pooled negatives. No evaluation row was used to tune the judge.\n\n"
        "| Metric | Point | One-sided 95% LCB | Frozen minimum | Met |\n"
        "|---|---:|---:|---:|---:|\n"
        + "\n".join(
            f"| {key} | {metrics[key]:.6f} | {bootstrap[key]['one_sided_95_lcb']:.6f} | {minimum:.2f} | `{str(checks[f'{key}_point'] and checks[f'{key}_lcb']).lower()}` |"
            for key, minimum in MINIMUMS.items()
        )
        + "\n\n"
        f"- MCC: {metrics['mcc']:.6f}.\n"
        f"- Abstention: {metrics['abstentions']}/{len(rows)} = {metrics['abstention_rate']:.6f}; maximum 0.10.\n"
        f"- Class-count checks: positives {counts['yes']}/30; negatives {counts['no']}/50.\n"
        f"- Pooled gold SHA-256: `{result['gold_set_hash']}`.\n",
        encoding="utf-8",
    )
    return result


def pending_manifest(manifest_path: Path, raw_path: Path, output: Path) -> dict:
    manifest = read_csv(manifest_path)
    complete: set[str] = set()
    if raw_path.is_file():
        calls: dict[str, set[int]] = defaultdict(set)
        for row in read_jsonl(raw_path):
            calls[str(row["clip_id"])].add(int(row["call_index"]))
        complete = {clip_id for clip_id, indices in calls.items() if indices == {0, 1, 2}}
    pending = [row for row in manifest if row["clip_id"] not in complete]
    if pending:
        write_csv(output, pending)
    return {"manifest_rows": len(manifest), "complete_rows": len(complete), "pending_rows": len(pending), "output": str(output)}


def _rate(values: list[int], weights: list[float]) -> float:
    return float(np.average(np.asarray(values), weights=np.asarray(weights)))


def _calibrated_rate(apparent: float, sensitivity: float, specificity: float) -> float:
    denominator = sensitivity + specificity - 1
    if denominator <= 0:
        return math.nan
    return min(1.0, max(0.0, (apparent + specificity - 1) / denominator))


def _global_estimates(manifest: list[dict], labels: dict[str, str], validation: dict) -> list[dict]:
    groups = [("all", "all", manifest)]
    for requested in ("0", "1"):
        groups.append(("requested_vocal", requested, [row for row in manifest if row["requested_vocal"] == requested]))
    sensitivity = float(validation["metrics"]["sensitivity"])
    specificity = float(validation["metrics"]["specificity"])
    output = []
    for group, value, rows in groups:
        decided = [row for row in rows if labels[row["clip_id"]] in {"yes", "no"}]
        weights = [1.0 / float(row["inclusion_probability"]) for row in decided]
        presence = [int(labels[row["clip_id"]] == "yes") for row in decided]
        apparent_presence = _rate(presence, weights)
        calibrated_presence = _calibrated_rate(apparent_presence, sensitivity, specificity)
        requested = None if value == "all" else int(value)
        apparent_violation = (
            _rate([int(p != requested) for p in presence], weights) if requested is not None else math.nan
        )
        calibrated_violation = (
            calibrated_presence if requested == 0 else 1 - calibrated_presence if requested == 1 else math.nan
        )
        output.append(
            {
                "group": group,
                "group_value": value,
                "rows": len(rows),
                "decided": len(decided),
                "abstentions": len(rows) - len(decided),
                "apparent_voice_presence_rate": apparent_presence,
                "judge_calibrated_voice_presence_rate": calibrated_presence,
                "apparent_label_a_violation_rate": apparent_violation,
                "judge_calibrated_label_a_violation_rate": calibrated_violation,
            }
        )
    return output


def _global_bootstrap(manifest: list[dict], labels: dict[str, str], gold: list[dict], gold_labels: dict[str, str], estimates: list[dict]) -> None:
    rng = np.random.default_rng(BOOTSTRAP_SEED + 1)
    target_strata: dict[str, list[dict]] = defaultdict(list)
    for row in manifest:
        target_strata[row["calibration_stratum"]].append(row)
    gold_strata: dict[str, list[dict]] = defaultdict(list)
    for row in gold:
        gold_strata[f"{row['gold_source']}|{row['calibration_stratum']}|{row['true_label']}"].append(row)
    draws: dict[tuple[str, str], dict[str, list[float]]] = {}
    for estimate in estimates:
        draws[(estimate["group"], estimate["group_value"])] = defaultdict(list)
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled_target = []
        for key in sorted(target_strata):
            source = target_strata[key]
            sampled_target.extend(source[int(index)] for index in rng.integers(0, len(source), len(source)))
        sampled_gold = []
        for key in sorted(gold_strata):
            source = gold_strata[key]
            sampled_gold.extend(source[int(index)] for index in rng.integers(0, len(source), len(source)))
        calibration = _confusion(sampled_gold, gold_labels)
        for estimate in estimates:
            value = estimate["group_value"]
            rows = sampled_target if value == "all" else [row for row in sampled_target if row["requested_vocal"] == value]
            decided = [row for row in rows if labels[row["clip_id"]] in {"yes", "no"}]
            weights = [1.0 / float(row["inclusion_probability"]) for row in decided]
            presence = [int(labels[row["clip_id"]] == "yes") for row in decided]
            apparent = _rate(presence, weights)
            corrected = _calibrated_rate(apparent, calibration["sensitivity"], calibration["specificity"])
            if not math.isfinite(corrected):
                continue
            bucket = draws[(estimate["group"], value)]
            bucket["apparent"].append(apparent)
            bucket["calibrated"].append(corrected)
            if value != "all":
                requested = int(value)
                bucket["apparent_violation"].append(_rate([int(p != requested) for p in presence], weights))
                bucket["calibrated_violation"].append(corrected if requested == 0 else 1 - corrected)
    for estimate in estimates:
        bucket = draws[(estimate["group"], estimate["group_value"])]
        for key, values in bucket.items():
            estimate[f"{key}_95_ci_low"] = float(np.quantile(values, 0.025))
            estimate[f"{key}_95_ci_high"] = float(np.quantile(values, 0.975))
            estimate[f"{key}_bootstrap_replicates"] = len(values)


def _load_merge_module():
    merge_path = PAPER / "rater_admin_keys_20260711/t2_aprime/merge_a_prime_instruments.py"
    spec = importlib.util.spec_from_file_location("merge_a_prime_instruments_t7", merge_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import A-prime merge script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _human_core_buckets() -> tuple[dict, dict]:
    admin = read_csv(GLOBAL_ADMIN)
    core = read_csv(CORE_RATINGS)
    module = _load_merge_module()
    provenance = module.register_core_instrument(admin, core)
    labels = {row["rating_id"]: row["label_a_voice_presence"].strip().lower() for row in core}
    buckets = {}
    for bucket in ("detector_disagreement_112", "rare_basin_48", "agreement_spotcheck_30"):
        rows = [row for row in admin if row["set_bucket"] == bucket]
        decided = matches = abstains = 0
        for row in rows:
            label = labels[row["rating_id"]]
            if label == "unsure":
                abstains += 1
                continue
            decided += 1
            matches += int(int(label == "yes") == int(row["expected_demucs_label"]))
        buckets[bucket] = {
            "rows": len(rows),
            "decided": decided,
            "abstains": abstains,
            "matches": matches,
            "match_rate": matches / decided if decided else math.nan,
        }
    return buckets, provenance


def _refuse_finalized_gate_overwrite() -> None:
    """Keep a committed PI call terminal under later scorer reruns."""
    if not A_GATE_JSON.is_file():
        return
    current = json.loads(A_GATE_JSON.read_text(encoding="utf-8"))
    if current.get("pi_gate_decision"):
        raise RuntimeError(
            "A-prime PI gate call is already recorded; refusing to overwrite it "
            "with a mechanical PI_CALL_PENDING result"
        )


def finalize_core_only() -> dict:
    _refuse_finalized_gate_overwrite()
    validation = json.loads(VALIDATION_JSON.read_text(encoding="utf-8"))
    if validation["JUDGE_VALIDATION_STATUS"] != "FAIL":
        raise ValueError("human-core-only finalization is reserved for failed judge validation")
    buckets, provenance = _human_core_buckets()
    criteria = {
        "rare_basin_confirmation_at_least_0p90": buckets["rare_basin_48"]["match_rate"] >= 0.90,
        "demucs_disagreement_match_at_least_0p70": buckets["detector_disagreement_112"]["match_rate"] >= 0.70,
        "agreement_failures_at_most_2_of_30": buckets["agreement_spotcheck_30"]["decided"] - buckets["agreement_spotcheck_30"]["matches"] <= 2,
    }
    gate = {
        "A_PRIME_GATE": "PI_CALL_PENDING",
        "judge_validation_status": "FAIL",
        "judge_role": "EXPLORATORY_ONLY_NOT_USED_FOR_GLOBAL_BOUND",
        "human_core_rows": 190,
        "human_core_provenance": provenance,
        "label_a_bucket_results": buckets,
        "frozen_label_a_criteria": criteria,
        "all_frozen_label_a_criteria_met": all(criteria.values()),
        "global_bound_status": "NOT_RUN_JUDGE_VALIDATION_FAIL",
        "automatic_gate_pass_forbidden": True,
        "label_b_scope_note": "The human core measures Label A; it does not establish the signed amendment's paper-primary Label-B endpoint.",
    }
    A_GATE_JSON.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    A_GATE.write_text(
        "# A-Prime Gate Report - Human Core After Judge Validation Failure\n\n"
        "`A_PRIME_GATE = PI_CALL_PENDING`\n\n"
        "The pooled disjoint-gold judge failed the frozen validation rule, so it is exploratory and was not used on the stratified-500. The official A-prime evidence in this branch is the provenance-enforced 190-row `pi:Richard` human core. This report does not auto-pass the gate. The human core measures Label A and does not establish the signed amendment's paper-primary Label-B endpoint.\n\n"
        "| Set | Matches/decided | Match rate | Frozen condition met |\n"
        "|---|---:|---:|---:|\n"
        f"| Detector disagreement | {buckets['detector_disagreement_112']['matches']}/{buckets['detector_disagreement_112']['decided']} | {buckets['detector_disagreement_112']['match_rate']:.6f} | `{str(criteria['demucs_disagreement_match_at_least_0p70']).lower()}` |\n"
        f"| Rare basin | {buckets['rare_basin_48']['matches']}/{buckets['rare_basin_48']['decided']} | {buckets['rare_basin_48']['match_rate']:.6f} | `{str(criteria['rare_basin_confirmation_at_least_0p90']).lower()}` |\n"
        f"| Agreement controls | {buckets['agreement_spotcheck_30']['matches']}/{buckets['agreement_spotcheck_30']['decided']} | {buckets['agreement_spotcheck_30']['match_rate']:.6f} | `{str(criteria['agreement_failures_at_most_2_of_30']).lower()}` |\n\n"
        f"Judge failure evidence: `{VALIDATION_REPORT.relative_to(ROOT)}`.\n",
        encoding="utf-8",
    )
    return {
        "A_PRIME_GATE": "PI_CALL_PENDING",
        "JUDGE_500_STATUS": "NOT_RUN_JUDGE_VALIDATION_FAIL",
        "human_core_rows": 190,
        "all_frozen_label_a_criteria_met": all(criteria.values()),
    }


def finalize_500() -> dict:
    _refuse_finalized_gate_overwrite()
    validation = json.loads(VALIDATION_JSON.read_text(encoding="utf-8"))
    if validation["JUDGE_VALIDATION_STATUS"] != "PASS":
        raise ValueError("stratified-500 requires JUDGE_VALIDATION_STATUS = PASS")
    manifest = read_csv(GLOBAL_MANIFEST)
    raw = deduplicated_raw([GLOBAL_RAW])
    labels = majorities(raw)
    if set(labels) != {row["clip_id"] for row in manifest}:
        raise ValueError("stratified-500 judge response ID mismatch")
    pooled_gold = read_csv(POOLED_GOLD)
    pooled_labels = majorities(deduplicated_raw([POOLED_RAW]))
    estimates = _global_estimates(manifest, labels, validation)
    _global_bootstrap(manifest, labels, pooled_gold, pooled_labels, estimates)
    write_csv(GLOBAL_RESULTS, estimates)

    gold_hash = validation["gold_set_hash"]
    rating_source = f"judge:{MODEL_ID}:validated:{gold_hash}"
    mapping = read_csv(GLOBAL_MAPPING)
    rating_rows = [
        {
            "rating_id": row["rating_id"],
            "label_a_voice_presence": labels[row["judge_clip_id"]],
            "label_b_constraint": "unsure",
            "rating_source": rating_source,
        }
        for row in mapping
    ]
    write_csv(GLOBAL_RATINGS, rating_rows)
    write_jsonl(ALL_RAW, deduplicated_raw([POOLED_RAW, GLOBAL_RAW]))
    metadata_record = {
        "validation_status": "PASS",
        "model_id": MODEL_ID,
        "gold_set_hash": gold_hash,
        "calibration_metrics": {
            "sensitivity": validation["metrics"]["sensitivity"],
            "specificity": validation["metrics"]["specificity"],
            "balanced_accuracy": validation["metrics"]["balanced_accuracy"],
            "mcc": validation["metrics"]["mcc"],
            "abstention_rate": validation["metrics"]["abstention_rate"],
        },
        "raw_response_ledger": str(ALL_RAW.resolve()),
        "validation_report": str(VALIDATION_REPORT.resolve()),
        "validation_raw_ledger_sha256": sha256_file(POOLED_RAW),
        "global_raw_ledger_sha256": sha256_file(GLOBAL_RAW),
    }
    JUDGE_METADATA.write_text(json.dumps(metadata_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    module = _load_merge_module()
    metadata = module.normalize_judge_metadata([metadata_record])
    admin = read_csv(GLOBAL_ADMIN)
    core = read_csv(CORE_RATINGS)
    merged, merge_report = module.merge_instruments(admin, core, rating_rows, metadata)
    write_csv(MERGED, merged)
    MERGE_REPORT.write_text(json.dumps(merge_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    merged_index = {row["rating_id"]: row for row in merged}
    buckets = {}
    for bucket in ("detector_disagreement_112", "rare_basin_48", "agreement_spotcheck_30", "stratified_random_500"):
        rows = [row for row in admin if row["set_bucket"] == bucket]
        if bucket == "stratified_random_500":
            representative_ids = {
                min(group, key=lambda row: row["rating_id"])["rating_id"]
                for group in (
                    [row for row in rows if row["package_sha256"] == digest]
                    for digest in {row["package_sha256"] for row in rows}
                )
            }
            rows = [row for row in rows if row["rating_id"] in representative_ids]
        decided = matches = abstains = 0
        for row in rows:
            label = merged_index[row["rating_id"]]["label_a_voice_presence"].strip().lower()
            if label == "unsure":
                abstains += 1
                continue
            decided += 1
            matches += int(int(label == "yes") == int(row["expected_demucs_label"]))
        buckets[bucket] = {
            "rows": len(rows),
            "decided": decided,
            "abstains": abstains,
            "matches": matches,
            "match_rate": matches / decided if decided else math.nan,
        }
    criteria = {
        "rare_basin_confirmation_at_least_0p90": buckets["rare_basin_48"]["match_rate"] >= 0.90,
        "demucs_disagreement_match_at_least_0p70": buckets["detector_disagreement_112"]["match_rate"] >= 0.70,
        "agreement_failures_at_most_2_of_30": buckets["agreement_spotcheck_30"]["decided"] - buckets["agreement_spotcheck_30"]["matches"] <= 2,
    }
    gate = {
        "A_PRIME_GATE": "PI_CALL_PENDING",
        "judge_validation_status": "PASS",
        "instrument_merge_rows": len(merged),
        "instrument_merge_provenance": merge_report["provenance_counts"],
        "label_a_bucket_results": buckets,
        "frozen_label_a_criteria": criteria,
        "all_frozen_label_a_criteria_met": all(criteria.values()),
        "automatic_gate_pass_forbidden": True,
        "label_b_scope_note": "T2 human core and the judge supplement are Label-A instruments; they do not establish the signed amendment's paper-primary Label-B endpoint.",
    }
    A_GATE_JSON.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    A_GATE.write_text(
        "# A-Prime Gate Report - Pooled Judge Completion\n\n"
        "`A_PRIME_GATE = PI_CALL_PENDING`\n\n"
        "The 190-row human core and nominal 500-row validated-judge supplement are complete and provenance-enforced. The supplement contains 493 unique audio hashes; inference and estimates are deduplicated to 493 clips, while labels map back to all 500 frozen rating IDs for the instrument contract. This report does not auto-pass the gate. The core and supplement measure Label A (perceived voice presence); they do not establish the signed amendment's paper-primary Label-B constraint endpoint.\n\n"
        "| Set | Instrument | Matches/decided | Match rate | Frozen condition met |\n"
        "|---|---|---:|---:|---:|\n"
        f"| Detector disagreement | `pi:Richard` | {buckets['detector_disagreement_112']['matches']}/{buckets['detector_disagreement_112']['decided']} | {buckets['detector_disagreement_112']['match_rate']:.6f} | `{str(criteria['demucs_disagreement_match_at_least_0p70']).lower()}` |\n"
        f"| Rare basin | `pi:Richard` | {buckets['rare_basin_48']['matches']}/{buckets['rare_basin_48']['decided']} | {buckets['rare_basin_48']['match_rate']:.6f} | `{str(criteria['rare_basin_confirmation_at_least_0p90']).lower()}` |\n"
        f"| Agreement controls | `pi:Richard` | {buckets['agreement_spotcheck_30']['matches']}/{buckets['agreement_spotcheck_30']['decided']} | {buckets['agreement_spotcheck_30']['match_rate']:.6f} | `{str(criteria['agreement_failures_at_most_2_of_30']).lower()}` |\n"
        f"| Stratified global bound | validated judge | {buckets['stratified_random_500']['matches']}/{buckets['stratified_random_500']['decided']} | {buckets['stratified_random_500']['match_rate']:.6f} | outside pass shape |\n\n"
        f"Judge evidence: `{VALIDATION_REPORT.relative_to(ROOT)}`.\n\n"
        f"Instrument merge: `{MERGED.relative_to(ROOT)}`.\n",
        encoding="utf-8",
    )
    GLOBAL_REPORT.write_text(
        "# A-Prime Stratified-500 Judge Result\n\n"
        "`JUDGE_500_STATUS = COMPLETE`\n\n"
        "Apparent and judge-calibrated Label-A estimates are reported separately from detector estimates. The nominal 500 rows deduplicate to 493 unique audio hashes before inference and estimation. Equal manifest weights are used because the frozen manifest does not record unequal inclusion probabilities; bootstrap strata preserve corpus, source family, and request direction.\n\n"
        "| Group | Rows | Apparent voice | Calibrated voice | Apparent Label-A violation | Calibrated Label-A violation |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        + "\n".join(
            f"| {row['group']}={row['group_value']} | {row['rows']} | {row['apparent_voice_presence_rate']:.6f} | {row['judge_calibrated_voice_presence_rate']:.6f} | {row['apparent_label_a_violation_rate'] if math.isfinite(row['apparent_label_a_violation_rate']) else 'NA'} | {row['judge_calibrated_label_a_violation_rate'] if math.isfinite(row['judge_calibrated_label_a_violation_rate']) else 'NA'} |"
            for row in estimates
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "JUDGE_500_STATUS": "COMPLETE",
        "A_PRIME_GATE": "PI_CALL_PENDING",
        "nominal_rows": len(mapping),
        "unique_inference_rows": len(manifest),
        "merge_rows": len(merged),
        "rating_source": rating_source,
        "all_frozen_label_a_criteria_met": all(criteria.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("evaluate-validation")
    sub.add_parser("finalize-core-only")
    pending = sub.add_parser("pending")
    pending.add_argument("--manifest", type=Path, required=True)
    pending.add_argument("--raw", type=Path, required=True)
    pending.add_argument("--output", type=Path, required=True)
    sub.add_parser("finalize-500")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "evaluate-validation":
        result = evaluate_validation()
    elif args.command == "pending":
        result = pending_manifest(args.manifest, args.raw, args.output)
    elif args.command == "finalize-core-only":
        result = finalize_core_only()
    elif args.command == "finalize-500":
        result = finalize_500()
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
