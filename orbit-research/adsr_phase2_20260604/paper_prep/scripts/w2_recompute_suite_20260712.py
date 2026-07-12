#!/usr/bin/env python3
"""Score retained Batch-3 media and assemble direction/arm W2 recomputations."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import socket
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
sys.path.insert(0, str(ROOT / "paper_prep/w2_contingency_20260711"))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

PAPER = ROOT / "paper_prep"
OUT = PAPER / "w2_execution_20260712/analysis"
BATCH3_MANIFEST = OUT / "BATCH3_1342_RESCORING_MANIFEST.csv"
BATCH3_LEDGER_DIR = OUT / "batch3_scoring_ledgers"
TARGET_TABLE = OUT / "W2_TARGET_SCORE_TABLE.csv"
PUBLICATION_TABLE = OUT / "W2_PUBLICATION_RATES.csv"
PROMPT_ECDF = OUT / "W2_PROMPT_LEVEL_ECDF.csv"
RECOMPUTE_REPORT = OUT / "W2_RECOMPUTE_REPORT.md"
RELEASE_KEEP = PAPER / "storage_triage/RELEASE_KEEP_MANIFEST.csv"
RETAINED = PAPER / "w2_contingency_20260711/W2_RETAINED_AUDIO_MANIFEST.jsonl"
EXISTING_SCORES = PAPER / "w2_contingency_20260711/activated_20260711/full_corrected/W2_CORRECTED_MERGED.jsonl"
SPINE_MANIFEST = PAPER / "w2_execution_20260712/spine_reconstruction/SPINE_RECONSTRUCTION_MANIFEST.csv"
SPINE_SCORING_DIR = PAPER / "w2_execution_20260712/spine_reconstruction/scoring_ledgers"
OLD_THRESHOLD = VOCAL_PRESENCE_THRESHOLD
CANDIDATE_DEMUCS_THRESHOLD = 0.038639528676867485
CANDIDATE_PANNS_THRESHOLD = 0.03181814216077328


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


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_batch3_manifest() -> dict:
    source = read_csv(RELEASE_KEEP)
    if len(source) != 1342:
        raise ValueError(f"release keep cardinality changed: {len(source)}")
    rows = []
    for index, row in enumerate(source):
        path = ROOT / row["copied_path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        if sha256_file(path) != row["sha256"]:
            raise ValueError(f"release keep checksum mismatch: {row['sample_id']}")
        rows.append(
            {
                "record_id": f"batch3keep_{index:04d}_{row['sample_id']}",
                "sample_id": row["sample_id"],
                "audio_path": row["copied_path"],
                "audio_sha256": row["sha256"],
                "source_path": row["source_path"],
                "source_family": row["source_family"],
                "corpus": row["corpus"],
                "prompt_id": row["prompt_id"],
                "condition": row["condition"],
                "arm": row["arm"],
                "rep": row["rep"],
                "attempt": row["attempt"],
                "seed": row["seed"],
                "requested_vocal": row["requested_vocal"],
                "historical_present": row["present"],
                "historical_type_correct": row["type_correct"],
                "ledger_path": row["ledger_path"],
                "release_reason": row["release_reason"],
                "target_sampling_weight": 1.0,
            }
        )
    write_csv(BATCH3_MANIFEST, rows)
    return {
        "rows": len(rows),
        "unique_copied_paths": len({row["audio_path"] for row in rows}),
        "unique_audio_hashes": len({row["audio_sha256"] for row in rows}),
        "corpus_counts": dict(Counter(row["corpus"] for row in rows)),
    }


def _latest(directory: Path, pattern: str, key: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in sorted(directory.glob(pattern)):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[str(row[key])] = row
    return rows


def _seed_rng(identity: str) -> None:
    import torch

    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:4], "big")
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def score_batch3(worker_index: int, num_workers: int, limit: int) -> int:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("exactly one CUDA_VISIBLE_DEVICES entry is required")
    from w2_instruments import CurrentDemucsInstrument, LivePannsInstrument

    rows = read_csv(BATCH3_MANIFEST)
    mine = rows[worker_index::num_workers]
    if limit:
        mine = mine[:limit]
    done = _latest(BATCH3_LEDGER_DIR, "batch3_w*.jsonl", "record_id")
    demucs = CurrentDemucsInstrument(device="cuda", threshold=OLD_THRESHOLD)
    panns = LivePannsInstrument(device="cuda", threshold=CANDIDATE_PANNS_THRESHOLD)
    ledger = BATCH3_LEDGER_DIR / f"batch3_w{worker_index}.jsonl"
    written = 0
    for row in mine:
        if row["record_id"] in done:
            continue
        started = time.time()
        path = ROOT / row["audio_path"]
        record = {
            **row,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "status": "FAIL",
            "error": "",
        }
        try:
            _seed_rng(row["audio_sha256"] + "|demucs")
            demucs_result = demucs.score(path)
            _seed_rng(row["audio_sha256"] + "|panns")
            panns_result = panns.score(path)
            demucs_candidate = int(
                demucs_result["vocal_energy_ratio"] >= CANDIDATE_DEMUCS_THRESHOLD
                and not demucs_result["near_silent"]
            )
            panns_candidate = int(panns_result["panns_score"] >= CANDIDATE_PANNS_THRESHOLD)
            candidate = int(demucs_candidate and panns_candidate)
            requested = int(row["requested_vocal"])
            record.update(
                {
                    "status": "PASS",
                    "demucs_score": float(demucs_result["vocal_energy_ratio"]),
                    "near_silent": bool(demucs_result["near_silent"]),
                    "old_present": int(demucs_result["present"]),
                    "panns_score": float(panns_result["panns_score"]),
                    "panns_top_vocal_class": panns_result["panns_top_vocal_class"],
                    "candidate_demucs_present": demucs_candidate,
                    "candidate_panns_present": panns_candidate,
                    "candidate_present": candidate,
                    "old_violation": int(int(demucs_result["present"]) != requested),
                    "candidate_violation": int(candidate != requested),
                    "instrument_status": "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED",
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_s"] = round(time.time() - started, 6)
        append_jsonl(ledger, record)
        print(json.dumps(record, sort_keys=True), flush=True)
        written += 1
        if record["status"] != "PASS":
            return 1
    return 0 if written or all(row["record_id"] in done for row in mine) else 1


def assemble_targets(require_complete: bool = True) -> dict:
    rows: list[dict] = []
    retained = {row["record_id"]: row for row in read_jsonl(RETAINED)}
    existing = [row for row in read_jsonl(EXISTING_SCORES) if row.get("status") == "PASS"]
    for score in existing:
        admin = retained.get(score["record_id"])
        if admin is None:
            raise ValueError(f"missing retained metadata for {score['record_id']}")
        if admin["cohort"] == "candidate_spine_4096":
            # The reconstructed/scored spine below supersedes this lone inventory
            # survivor for W2 analysis; retain its old score only in the audit trail.
            continue
        rows.append(
            {
                "record_id": score["record_id"],
                "cohort": admin["cohort"],
                "source_family": admin["cohort"],
                "prompt_id": admin["prompt_id"],
                "condition": admin["condition"],
                "arm": "",
                "requested_vocal": int(admin["requested_vocal"]),
                "demucs_score": float(score["vocal_energy_ratio"]),
                "panns_score": float(score["panns_score"]),
                "apparent_present": int(score["old_present"]),
                "candidate_present": int(score["present"]),
                "apparent_violation": int(int(score["old_present"]) != int(admin["requested_vocal"])),
                "candidate_violation": int(int(score["present"]) != int(admin["requested_vocal"])),
                "target_sampling_weight": 1.0,
                "instrument_status": "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED",
            }
        )

    spine_admin = {row["task_id"]: row for row in read_csv(SPINE_MANIFEST)}
    spine_scores = _latest(SPINE_SCORING_DIR, "scoring_w*.jsonl", "task_id")
    if require_complete and len(spine_scores) != 4096:
        raise ValueError(f"spine scoring incomplete: {len(spine_scores)}/4096")
    for task_id, score in spine_scores.items():
        admin = spine_admin[task_id]
        rows.append(
            {
                "record_id": admin["record_id"],
                "cohort": "candidate_spine_4096",
                "source_family": "spine",
                "prompt_id": admin["prompt_id"],
                "condition": "candidate_final",
                "arm": "",
                "requested_vocal": int(admin["requested_vocal"]),
                "demucs_score": float(score["recomputed_demucs_score"]),
                "panns_score": float(score["panns_score"]),
                "apparent_present": int(score["recomputed_old_present_0p1791"]),
                "candidate_present": int(score["candidate_and_present"]),
                "apparent_violation": int(score["old_label_b_violation"]),
                "candidate_violation": int(score["candidate_label_b_violation"]),
                "target_sampling_weight": 1.0,
                "instrument_status": "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED",
            }
        )

    batch3_scores = _latest(BATCH3_LEDGER_DIR, "batch3_w*.jsonl", "record_id")
    if require_complete and len(batch3_scores) != 1342:
        raise ValueError(f"Batch-3 keep scoring incomplete: {len(batch3_scores)}/1342")
    for score in batch3_scores.values():
        rows.append(
            {
                "record_id": score["record_id"],
                "cohort": "batch3_release_keep_1342",
                "source_family": score["source_family"],
                "prompt_id": score["prompt_id"],
                "condition": score["condition"],
                "arm": score["arm"],
                "requested_vocal": int(score["requested_vocal"]),
                "demucs_score": float(score["demucs_score"]),
                "panns_score": float(score["panns_score"]),
                "apparent_present": int(score["old_present"]),
                "candidate_present": int(score["candidate_present"]),
                "apparent_violation": int(score["old_violation"]),
                "candidate_violation": int(score["candidate_violation"]),
                "target_sampling_weight": float(score["target_sampling_weight"]),
                "instrument_status": "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED",
            }
        )
    identities = [(row["cohort"], row["record_id"]) for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("assembled target identities are not unique")
    if rows:
        write_csv(TARGET_TABLE, rows)
    return {
        "rows": len(rows),
        "cohort_counts": dict(Counter(row["cohort"] for row in rows)),
        "spine_scores": len(spine_scores),
        "batch3_scores": len(batch3_scores),
        "existing_scores": len(existing),
    }


def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return float(center - half), float(center + half)


def summarize() -> dict:
    rows = read_csv(TARGET_TABLE)
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        direction = "vocal_request" if row["requested_vocal"] == "1" else "instrumental_request"
        groups[(row["cohort"], direction, row["condition"], row["arm"])].append(row)
    table = []
    for key in sorted(groups):
        group = groups[key]
        old = sum(int(row["apparent_violation"]) for row in group)
        candidate = sum(int(row["candidate_violation"]) for row in group)
        old_ci = _wilson(old, len(group))
        candidate_ci = _wilson(candidate, len(group))
        table.append(
            {
                "cohort": key[0],
                "request_direction": key[1],
                "condition": key[2],
                "arm": key[3],
                "rows": len(group),
                "apparent_rate": old / len(group),
                "apparent_95_ci_low": old_ci[0],
                "apparent_95_ci_high": old_ci[1],
                "candidate_sensitivity_rate": candidate / len(group),
                "candidate_95_ci_low": candidate_ci[0],
                "candidate_95_ci_high": candidate_ci[1],
                "calibrated_rate": "",
                "joint_95_interval_low": "",
                "joint_95_interval_high": "",
                "publication_status": "BLOCKED_ON_PROMOTION_AND_RATINGS",
            }
        )
    write_csv(PUBLICATION_TABLE, table)

    prompt_groups: dict[tuple, list[int]] = defaultdict(list)
    for row in rows:
        direction = "vocal_request" if row["requested_vocal"] == "1" else "instrumental_request"
        prompt_groups[(row["cohort"], direction, row["prompt_id"])].append(int(row["candidate_violation"]))
    ecdf = []
    rates_by_group: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (cohort, direction, _prompt), values in prompt_groups.items():
        rates_by_group[(cohort, direction)].append(sum(values) / len(values))
    for (cohort, direction), values in sorted(rates_by_group.items()):
        ordered = sorted(values)
        for rank, value in enumerate(ordered, start=1):
            ecdf.append(
                {
                    "cohort": cohort,
                    "request_direction": direction,
                    "prompt_violation_rate": value,
                    "ecdf": rank / len(ordered),
                    "prompt_count": len(ordered),
                    "instrument_status": "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED",
                }
            )
    write_csv(PROMPT_ECDF, ecdf)
    RECOMPUTE_REPORT.write_text(
        "# W2 Recompute Suite\n\n"
        "`RECOMPUTE_PIPELINE_STATUS = READY`\n\n"
        f"- Assembled target rows: {len(rows)}\n"
        f"- Publication table rows: {len(table)}\n"
        f"- Prompt ECDF rows: {len(ecdf)}\n"
        "- Apparent rates use the frozen current detector.\n"
        "- Candidate rates are sensitivity-only until the signed W2 gate promotes an instrument.\n"
        "- Calibrated columns remain blank until ratings and dual-PI promotion exist.\n\n"
        "## Batch-3 Required Disclosures\n\n"
        "1. The 1,342 files are retained/release-selected outputs, not an unselected population sample.\n"
        "2. Their retention was partly conditioned on current-detector outputs, so corrected rates are selection-conditioned.\n"
        "3. Duplicate decoded media may occupy distinct release roles; row and unique-hash counts must both be reported.\n"
        "4. Candidate and calibrated estimates must identify the instrument and its promotion/calibration artifact.\n",
        encoding="utf-8",
    )
    return {"target_rows": len(rows), "publication_rows": len(table), "ecdf_rows": len(ecdf)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-batch3-manifest")
    score = sub.add_parser("score-batch3")
    score.add_argument("--worker-index", type=int, required=True)
    score.add_argument("--num-workers", type=int, required=True)
    score.add_argument("--limit", type=int, default=0)
    assemble = sub.add_parser("assemble")
    assemble.add_argument("--allow-incomplete", action="store_true")
    sub.add_parser("summarize")
    args = parser.parse_args()
    if args.command == "build-batch3-manifest":
        print(json.dumps(build_batch3_manifest(), indent=2, sort_keys=True))
        return 0
    if args.command == "score-batch3":
        return score_batch3(args.worker_index, args.num_workers, args.limit)
    if args.command == "assemble":
        print(json.dumps(assemble_targets(not args.allow_incomplete), indent=2, sort_keys=True))
        return 0
    if args.command == "summarize":
        print(json.dumps(summarize(), indent=2, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
