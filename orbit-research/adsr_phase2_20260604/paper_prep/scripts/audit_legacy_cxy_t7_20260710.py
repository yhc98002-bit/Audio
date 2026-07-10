#!/usr/bin/env python3
"""Audit the held-out self-hosted judge run against legacy single-rater gold."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def majority(labels: list[str | None]) -> str:
    counts = Counter(label for label in labels if label in {"yes", "no"})
    required = len(labels) // 2 + 1
    if counts["yes"] >= required:
        return "yes"
    if counts["no"] >= required:
        return "no"
    return "unsure"


def metrics(rows: list[dict[str, str]]) -> dict[str, float | int]:
    decided = [row for row in rows if row["predicted"] in {"yes", "no"}]
    tp = sum(row["truth"] == "yes" and row["predicted"] == "yes" for row in decided)
    tn = sum(row["truth"] == "no" and row["predicted"] == "no" for row in decided)
    fp = sum(row["truth"] == "no" and row["predicted"] == "yes" for row in decided)
    fn = sum(row["truth"] == "yes" and row["predicted"] == "no" for row in decided)
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "rows": len(rows),
        "positives": tp + fn,
        "negatives": tn + fp,
        "decided": len(decided),
        "abstained": len(rows) - len(decided),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "mcc": (tp * tn - fp * fn) / denominator if denominator else math.nan,
        "abstention_rate": (len(rows) - len(decided)) / len(rows) if rows else math.nan,
    }


def audit(manifest_path: Path, raw_path: Path, summary_path: Path, calls_per_clip: int) -> dict:
    manifest = read_csv(manifest_path)
    manifest_index = {row["clip_id"]: row for row in manifest}
    if len(manifest_index) != len(manifest) or not manifest:
        raise ValueError("held-out manifest clip IDs must be nonempty and unique")
    raw = read_jsonl(raw_path)
    if len(raw) != len(manifest) * calls_per_clip:
        raise ValueError("raw call cardinality mismatch")
    grouped: dict[str, dict[int, dict]] = defaultdict(dict)
    hash_cache: dict[Path, str] = {}
    for row in raw:
        clip_id = row.get("clip_id", "")
        call_index = int(row.get("call_index", -1))
        if clip_id not in manifest_index or call_index in grouped[clip_id]:
            raise ValueError("raw ledger has unknown or duplicate clip/call key")
        if call_index not in range(calls_per_clip):
            raise ValueError("raw ledger call index is out of range")
        if row.get("error") is not None:
            raise ValueError(f"judge call error for {clip_id}:{call_index}")
        if row.get("parsed_label") not in {"yes", "no", "unsure"}:
            raise ValueError(f"unparsed judge response for {clip_id}:{call_index}")
        if "base64," in json.dumps(row.get("request_without_embedded_audio", {})):
            raise ValueError("raw ledger retained embedded audio")
        media = Path(manifest_index[clip_id]["clip_path"])
        hash_cache.setdefault(media, sha256_file(media))
        if row.get("audio_sha256") != hash_cache[media]:
            raise ValueError(f"raw audio hash mismatch for {clip_id}")
        grouped[clip_id][call_index] = row
    if any(set(calls) != set(range(calls_per_clip)) for calls in grouped.values()):
        raise ValueError("raw ledger has an incomplete call set")

    recomputed = []
    for clip_id, manifest_row in manifest_index.items():
        labels = [grouped[clip_id][index]["parsed_label"] for index in range(calls_per_clip)]
        truth = manifest_row["true_label"].strip().lower()
        if truth not in {"yes", "no"}:
            raise ValueError(f"invalid gold truth for {clip_id}")
        recomputed.append({"clip_id": clip_id, "truth": truth, "predicted": majority(labels), "calls": labels})

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary_results = {row["clip_id"]: row for row in summary.get("results", [])}
    if set(summary_results) != set(manifest_index):
        raise ValueError("summary and manifest ID sets differ")
    for row in recomputed:
        saved = summary_results[row["clip_id"]]
        if saved.get("true_label") != row["truth"] or saved.get("majority_label") != row["predicted"] or saved.get("calls") != row["calls"]:
            raise ValueError(f"summary result mismatch for {row['clip_id']}")
    result = metrics(recomputed)
    for key in ("rows", "decided", "abstained", "sensitivity", "specificity", "balanced_accuracy", "mcc", "abstention_rate"):
        expected = summary[key]
        actual = result[key]
        if isinstance(actual, float):
            if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-12):
                raise ValueError(f"summary metric mismatch: {key}")
        elif actual != expected:
            raise ValueError(f"summary metric mismatch: {key}")
    return {**result, "calls": len(raw), "raw_unique_keys": len(raw), "embedded_audio_rows": 0}


def write_report(result: dict, output: Path, manifest: Path, raw: Path, summary: Path) -> None:
    report = f"""# Legacy CXY Held-Out T7 Judge Audit

`JUDGE_VALIDATION_STATUS = PI_BLOCKED`

## Scope

The self-hosted `qwen3-omni-judge` was evaluated with deterministic decoding and
three calls per clip against the held-out portion of the original-media CXY
legacy gold. The audit independently reconciled the manifest, every raw
clip/call key, audio SHA-256 values, parser outputs, majority votes, and summary
metrics. Embedded audio payloads were not retained in the raw ledger.

| Metric | Result |
|---|---:|
| Held-out clips | {result['rows']} |
| Positive clips | {result['positives']} |
| Negative clips | {result['negatives']} |
| Raw calls | {result['calls']} |
| Decided clips | {result['decided']} |
| Abstentions | {result['abstained']} |
| Sensitivity | {result['sensitivity']:.6f} |
| Specificity | {result['specificity']:.6f} |
| Balanced accuracy | {result['balanced_accuracy']:.6f} |
| MCC | {result['mcc']:.6f} |
| Abstention rate | {result['abstention_rate']:.6f} |

## Status Decision

This is a strong provisional diagnostic, not a validated scaling-instrument
gate. The gold is from one rater, predates the signed amendment, and its held-out
negative class is small. No frozen numeric T7 promotion threshold was specified,
and inter-rater agreement has not been measured. Therefore gates never
auto-pass and `JUDGE_VALIDATION_STATUS` remains `PI_BLOCKED` pending PI or a
second-rater overlap sufficient to report kappa and repeat the held-out audit.

No A-prime or B-prime status changed, and no scale calls were launched.

## Evidence

- Manifest: `{manifest}`
- Append-only raw ledger: `{raw}`
- Runner summary: `{summary}`
- Audit script: `paper_prep/scripts/audit_legacy_cxy_t7_20260710.py`
"""
    output.write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    base = Path("paper_prep/legacy_human_results_20260710")
    parser.add_argument("--manifest", type=Path, default=base / "JUDGE_GOLD_CXY_HELDOUT_MANIFEST.csv")
    parser.add_argument("--raw", type=Path, default=Path("paper_prep/judge_raw/selfhost_qwen3_omni_legacy_cxy_heldout_20260710.jsonl"))
    parser.add_argument("--summary", type=Path, default=base / "JUDGE_GOLD_CXY_T7_SUMMARY.json")
    parser.add_argument("--output", type=Path, default=base / "JUDGE_GOLD_CXY_T7_REPORT.md")
    parser.add_argument("--calls-per-clip", type=int, default=3)
    args = parser.parse_args()
    result = audit(args.manifest, args.raw, args.summary, args.calls_per_clip)
    write_report(result, args.output, args.manifest, args.raw, args.summary)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
