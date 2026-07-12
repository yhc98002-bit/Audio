#!/usr/bin/env python3
"""Prepare corrected-EVPD retraining and the gated W2 live-confirm manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "src"))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD
PAPER = ROOT / "paper_prep"
OUT = PAPER / "w2_execution_20260712/evpd_liveconfirm"
SPINE_MANIFEST = PAPER / "w2_execution_20260712/spine_reconstruction/SPINE_RECONSTRUCTION_MANIFEST.csv"
SPINE_SCORE_DIR = PAPER / "w2_execution_20260712/spine_reconstruction/scoring_ledgers"
EVPD_CACHE = ROOT / "orbit-research/adsr_phase2_20260604/batch2/evpd_feature_cache.npz"
EVPD_MANIFEST = OUT / "CORRECTED_EVPD_TRAINING_MANIFEST.csv"
EVPD_MODEL = OUT / "corrected_evpd_sigma08.joblib"
EVPD_REPORT = OUT / "CORRECTED_EVPD_REPORT.md"
LIVE_PROMPTS = OUT / "LIVE_CONFIRM_PROMPTS.jsonl"
LIVE_MANIFEST = OUT / "LIVE_CONFIRM_MANIFEST.csv"
POLICY_SPEC = OUT / "LIVE_CONFIRM_POLICY_FREEZE.json"
PREP_REPORT = OUT / "EVPD_LIVECONFIRM_PREP_REPORT.md"
SEED_BASE = 2_035_000_000
POLICIES = (
    "no_probe_reseed",
    "corrected_probe_abort_reseed",
    "always_direction_condition",
    "corrected_probe_direction_action",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_scores() -> dict[str, dict]:
    rows = {}
    for path in sorted(SPINE_SCORE_DIR.glob("scoring_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[row["task_id"]] = row
    return rows


def build_evpd_manifest(allow_pending_scores: bool = False) -> dict:
    cache = np.load(EVPD_CACHE, allow_pickle=True)
    cache_keys = {(str(pid), int(ci)): index for index, (pid, ci) in enumerate(zip(cache["pid"], cache["ci"]))}
    spine = read_csv(SPINE_MANIFEST)
    scores = latest_scores()
    if not allow_pending_scores and len(scores) != 4096:
        raise ValueError(f"spine scoring incomplete: {len(scores)}/4096")
    rows = []
    for task in spine:
        key = (task["prompt_id"], int(task["candidate_index"]))
        cache_index = cache_keys.get(key)
        if cache_index is None:
            raise ValueError(f"EVPD cache missing spine key {key}")
        score = scores.get(task["task_id"])
        rows.append(
            {
                "task_id": task["task_id"],
                "prompt_id": task["prompt_id"],
                "candidate_index": task["candidate_index"],
                "requested_vocal": task["requested_vocal"],
                "prompt_split": str(cache["split"][cache_index]),
                "evpd_cache_index": cache_index,
                "sigma": "0.8",
                "demucs_score": score["recomputed_demucs_score"] if score else "",
                "panns_score": score["panns_score"] if score else "",
                "candidate_present": score["candidate_and_present"] if score else "",
                "target_status": (
                    "PENDING_PROMOTED_INSTRUMENT"
                    if score
                    else "PENDING_SPINE_SCORING_AND_PROMOTED_INSTRUMENT"
                ),
            }
        )
    split_prompt_sets = {
        split: {row["prompt_id"] for row in rows if row["prompt_split"] == split}
        for split in {row["prompt_split"] for row in rows}
    }
    for left in split_prompt_sets:
        for right in split_prompt_sets:
            if left < right and split_prompt_sets[left] & split_prompt_sets[right]:
                raise ValueError(f"prompt leakage between {left} and {right}")
    write_csv(EVPD_MANIFEST, rows)
    return {
        "rows": len(rows),
        "scored_rows": len(scores),
        "split_candidate_counts": dict(Counter(row["prompt_split"] for row in rows)),
        "split_prompt_counts": {key: len(value) for key, value in split_prompt_sets.items()},
        "prompt_overlap": 0,
    }


def _promotion_candidate(record: dict) -> dict:
    if record.get("CORRECTED_INSTRUMENT_STATUS") != "PASS_DUAL_PI_ADOPTED":
        raise ValueError("corrected instrument lacks dual-PI promotion")
    candidate = record.get("selected_candidate") or record.get("heldout", {}).get("selected_candidate")
    if not candidate:
        raise ValueError("promotion record has no selected candidate")
    return candidate


def _present(score: dict, candidate: dict) -> int:
    family = candidate["family"]
    demucs = float(score["recomputed_demucs_score"]) >= float(
        candidate.get("demucs_threshold", VOCAL_PRESENCE_THRESHOLD)
    )
    panns = float(score["panns_score"]) >= float(candidate.get("panns_threshold", 0.5))
    if family in {"current_demucs", "demucs"}:
        return int(demucs)
    if family == "panns":
        return int(panns)
    if family in {"and", "fixed_20260711_and"}:
        return int(demucs and panns)
    if family == "or":
        return int(demucs or panns)
    raise ValueError(f"unknown promoted family {family!r}")


def train_evpd(promotion_path: Path) -> dict:
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    from sklearn.preprocessing import StandardScaler

    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    candidate = _promotion_candidate(promotion)
    cache = np.load(EVPD_CACHE, allow_pickle=True)
    manifest = read_csv(EVPD_MANIFEST)
    scores = latest_scores()
    if len(manifest) != 4096 or len(scores) != 4096:
        raise ValueError("corrected EVPD training requires all 4,096 scored spine rows")
    ordered = sorted(manifest, key=lambda row: int(row["evpd_cache_index"]))
    if [int(row["evpd_cache_index"]) for row in ordered] != list(range(4096)):
        raise ValueError("EVPD manifest/cache identity is not one-to-one")
    y = np.asarray([_present(scores[row["task_id"]], candidate) for row in ordered], dtype=int)
    x = cache["summ"][:, 1, :]
    split = cache["split"].astype(str)
    train, val, test = split == "train", split == "val", split == "test"
    scaler = StandardScaler().fit(x[train])
    model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=20260712)
    model.fit(scaler.transform(x[train]), y[train])
    val_probability = model.predict_proba(scaler.transform(x[val]))[:, 1]
    thresholds = np.unique(np.round(val_probability, 6))
    threshold = max(
        thresholds,
        key=lambda value: (
            balanced_accuracy_score(y[val], val_probability >= value),
            -abs(float(value) - 0.5),
        ),
    )
    test_probability = model.predict_proba(scaler.transform(x[test]))[:, 1]
    metrics = {
        "train_rows": int(train.sum()),
        "val_rows": int(val.sum()),
        "test_rows": int(test.sum()),
        "val_balanced_accuracy": float(balanced_accuracy_score(y[val], val_probability >= threshold)),
        "test_balanced_accuracy": float(balanced_accuracy_score(y[test], test_probability >= threshold)),
        "test_auc": float(roc_auc_score(y[test], test_probability)),
        "threshold": float(threshold),
        "prompt_split_overlap": 0,
    }
    bundle = {
        "model": model,
        "scaler": scaler,
        "threshold": float(threshold),
        "sigma": "0.8",
        "feature": "per-band mean/std/max/p25/p75 of 64-bin early log-mel",
        "target": "promoted corrected voice-presence instrument",
        "selected_candidate": candidate,
        "promotion_record": str(promotion_path),
        "promotion_sha256": sha256_file(promotion_path),
        "manifest_sha256": sha256_file(EVPD_MANIFEST),
        "metrics": metrics,
    }
    EVPD_MODEL.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, EVPD_MODEL)
    EVPD_REPORT.write_text(
        "# Corrected EVPD Retraining\n\n"
        "`CORRECTED_EVPD_STATUS = COMPLETE`\n\n"
        f"- Train/validation/test candidates: {metrics['train_rows']}/{metrics['val_rows']}/{metrics['test_rows']}\n"
        f"- Validation balanced accuracy: {metrics['val_balanced_accuracy']:.6f}\n"
        f"- Test balanced accuracy: {metrics['test_balanced_accuracy']:.6f}\n"
        f"- Test AUC: {metrics['test_auc']:.6f}\n"
        f"- Threshold selected on validation only: {metrics['threshold']:.6f}\n"
        "- Prompt overlap across train/validation/test: 0\n",
        encoding="utf-8",
    )
    return metrics


def build_live_manifest() -> dict:
    prompts = {
        row["prompt_id"]: row
        for row in read_jsonl(PAPER / "population_retry_20260707/population_retry_manifest_128.jsonl")
    }
    for prompt_path in (ROOT / "configs/prompts/dev.jsonl", ROOT / "configs/prompts/held_out.jsonl"):
        for row in read_jsonl(prompt_path):
            prompts.setdefault(row["prompt_id"], row)
    rates = read_csv(PAPER / "population_retry_20260707/full128_prompt_clean_rates.csv")
    instrumental = sorted(
        (row for row in rates if row["vocal_stratum"] == "instrumental"),
        key=lambda row: (float(row["clean_rate"]), row["prompt_id"]),
    )[:48]
    if len(instrumental) < 48:
        already = {row["prompt_id"] for row in instrumental}
        historical: dict[str, list[int]] = {}
        for row in read_csv(SPINE_MANIFEST):
            if row["requested_vocal"] == "0" and row["prompt_id"] not in already:
                historical.setdefault(row["prompt_id"], []).append(
                    int(row["historical_old_present_0p1791"])
                )
        supplements = sorted(
            historical,
            key=lambda prompt_id: (
                -sum(historical[prompt_id]) / len(historical[prompt_id]),
                prompt_id,
            ),
        )
        for prompt_id in supplements[: 48 - len(instrumental)]:
            instrumental.append(
                {
                    "prompt_id": prompt_id,
                    "vocal_stratum": "instrumental",
                    "clean_rate": str(
                        1 - sum(historical[prompt_id]) / len(historical[prompt_id])
                    ),
                    "selection_source": "spine_historical_risk_supplement",
                }
            )
    vocal = sorted(
        (row for row in rates if row["vocal_stratum"] == "vocal"),
        key=lambda row: (-float(row["clean_rate"]), row["prompt_id"]),
    )[:16]
    selected = []
    for rank, row in enumerate(instrumental + vocal):
        prompt = prompts[row["prompt_id"]]
        selected.append(
            {
                **prompt,
                "vocal_stratum": row["vocal_stratum"],
                "live_prompt_rank": rank,
                "live_stratum": "instrumental_risk" if rank < 48 else "vocal_sanity",
                "n2_clean_rate": float(row["clean_rate"]),
                "selection_rule": (
                    str(row.get("selection_source") or "instrumental_ascending_n2_clean_rate")
                    if rank < 48
                    else "vocal_descending_clean_rate"
                ),
            }
        )
    if len(selected) != 64 or len({row["prompt_id"] for row in selected}) != 64:
        raise ValueError("live-confirm prompt cardinality mismatch")
    write_jsonl(LIVE_PROMPTS, selected)
    tasks = []
    for prompt in selected:
        rank = int(prompt["live_prompt_rank"])
        for policy_index, policy in enumerate(POLICIES):
            for rep in range(2):
                seed = SEED_BASE + rank * 100 + rep
                tasks.append(
                    {
                        "unit_id": f"w2live_{rank:02d}_{policy_index}_{rep}",
                        "prompt_rank": rank,
                        "prompt_id": prompt["prompt_id"],
                        "live_stratum": prompt["live_stratum"],
                        "requested_vocal": int(prompt["vocal_stratum"] == "vocal"),
                        "policy_index": policy_index,
                        "policy": policy,
                        "rep": rep,
                        "seed": seed,
                        "nominal_step_budget": 60,
                        "output_ledger": f"live_ledgers/live_w{{worker}}.jsonl",
                    }
                )
    if len(tasks) != 512 or len({(row["prompt_id"], row["policy"], row["rep"]) for row in tasks}) != 512:
        raise ValueError("live-confirm unit cardinality mismatch")
    if len({(row["prompt_id"], row["rep"], row["seed"]) for row in tasks}) != 128:
        raise ValueError("live-confirm CRN cardinality mismatch")
    write_csv(LIVE_MANIFEST, tasks)
    policy = {
        "status": "FROZEN_PRELAUNCH",
        "policies": list(POLICIES),
        "attempt_slots": 2,
        "nominal_steps_per_slot": 30,
        "probe_decision_sigma": 0.8,
        "probe_abort_actual_steps": 12,
        "accounting": "each slot is charged 30 nominal steps; an early abort leaves the unspent 18 steps unused",
        "selection": "among completed slots, prefer promoted-instrument Label-B satisfaction then frozen final-common score",
        "direction_actions": {
            "instrumental": "positive-only instrumental wording plus frozen best sampler setting",
            "vocal": "vocal guidance scales plus structure hint when absent",
        },
        "pass_criteria": {
            "policy4_vs_policy1_violation_reduction_one_sided_95_lcb": ">0",
            "policy4_vs_policy3_excess_violation_one_sided_95_ucb": "<=0.05",
            "nominal_compute_difference": "<=1%",
            "vocal_sanity_excess_violation_vs_policy1": "<=0.05",
            "runtime_hard_stop_hours": 48,
        },
        "cap_miss_rule": "remove online headline",
    }
    POLICY_SPEC.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PREP_REPORT.write_text(
        "# Corrected EVPD And Live-Confirm Preparation\n\n"
        "`EVPD_LIVECONFIRM_PREP = READY_BLOCKED_ON_PROMOTION`\n\n"
        "- Corrected EVPD manifest: `CORRECTED_EVPD_TRAINING_MANIFEST.csv`\n"
        "- Live prompts: 48 instrumental-risk plus 16 vocal-sanity.\n"
        "- Live units: 64 prompts x 4 policies x 2 repetitions = 512.\n"
        "- Common-random-number seed range is registered in `paper_prep/SEED_REGISTRY.md`.\n"
        "- Launch guard requires dual W2 signatures, dual-PI instrument adoption, and unchanged policy hash.\n"
        "- The two-day cap and headline-removal rule are frozen in `LIVE_CONFIRM_POLICY_FREEZE.json`.\n",
        encoding="utf-8",
    )
    return {
        "prompts": len(selected),
        "units": len(tasks),
        "unique_crn_seeds": len({row["seed"] for row in tasks}),
        "min_seed": min(row["seed"] for row in tasks),
        "max_seed": max(row["seed"] for row in tasks),
        "policy_sha256": sha256_file(POLICY_SPEC),
    }


def launch_guard(amendment: Path, promotion: Path, expected_policy_sha256: str) -> dict:
    amendment_text = amendment.read_text(encoding="utf-8")
    if "W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS" not in amendment_text:
        raise ValueError("W2 amendment is not signed by both PIs")
    promotion_record = json.loads(promotion.read_text(encoding="utf-8"))
    _promotion_candidate(promotion_record)
    actual = sha256_file(POLICY_SPEC)
    if actual != expected_policy_sha256:
        raise ValueError(f"live policy hash changed: expected {expected_policy_sha256}, got {actual}")
    if len(read_csv(LIVE_MANIFEST)) != 512:
        raise ValueError("live-confirm manifest cardinality changed")
    if not EVPD_MODEL.is_file():
        raise FileNotFoundError("corrected EVPD model is absent")
    return {
        "status": "PASS_LAUNCH_AUTHORIZED",
        "amendment_sha256": sha256_file(amendment),
        "promotion_sha256": sha256_file(promotion),
        "policy_sha256": actual,
        "evpd_model_sha256": sha256_file(EVPD_MODEL),
        "manifest_sha256": sha256_file(LIVE_MANIFEST),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    evpd = sub.add_parser("build-evpd-manifest")
    evpd.add_argument("--allow-pending-scores", action="store_true")
    train = sub.add_parser("train-evpd")
    train.add_argument("--promotion-record", type=Path, required=True)
    sub.add_parser("build-live-manifest")
    guard = sub.add_parser("launch-guard")
    guard.add_argument("--amendment", type=Path, required=True)
    guard.add_argument("--promotion-record", type=Path, required=True)
    guard.add_argument("--policy-sha256", required=True)
    args = parser.parse_args()
    if args.command == "build-evpd-manifest":
        print(json.dumps(build_evpd_manifest(args.allow_pending_scores), indent=2, sort_keys=True))
    elif args.command == "train-evpd":
        print(json.dumps(train_evpd(args.promotion_record), indent=2, sort_keys=True))
    elif args.command == "build-live-manifest":
        print(json.dumps(build_live_manifest(), indent=2, sort_keys=True))
    elif args.command == "launch-guard":
        print(json.dumps(launch_guard(args.amendment, args.promotion_record, args.policy_sha256), indent=2, sort_keys=True))
    else:
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
