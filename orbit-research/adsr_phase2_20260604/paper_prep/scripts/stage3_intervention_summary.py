#!/usr/bin/env python3
"""Summarize Stage 3 intervention-decomposition ledgers.

The summary is intentionally ledger-first: it reports aggregate correctness,
condition/prompt breakdowns, and whether every successful row points at an
existing kept FLAC under the run root.
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def rate(num: int, den: int) -> float | None:
    return num / den if den else None


def compact_stats(values: list[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values),
        "mean": mean(values),
        "median": median(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--glob", action="append", required=True, dest="patterns")
    ap.add_argument("--root", required=True, help="Run root used to resolve relative FLAC paths")
    ap.add_argument("--expected-rows", type=int, default=0)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    paths: list[Path] = []
    for pattern in args.patterns:
        paths.extend(Path(p) for p in glob.glob(pattern))
    paths = sorted(set(paths))
    root = Path(args.root)

    rows = []
    for path in paths:
        rows.extend(load_jsonl(path))

    condition_counts = Counter(r.get("condition") for r in rows)
    prompt_counts = Counter(r.get("prompt_id") for r in rows)
    source_counts = Counter(r.get("source") for r in rows)
    requested_counts = Counter(r.get("requested_vocal") for r in rows)
    ok_rows = [r for r in rows if r.get("ok") is True]
    error_rows = [r for r in rows if r.get("ok") is not True]
    near_silent_rows = [r for r in ok_rows if r.get("near_silent")]
    missing_flac = []
    for r in ok_rows:
        rel = r.get("flac")
        if not rel or not (root / rel).exists():
            missing_flac.append({
                "prompt_id": r.get("prompt_id"),
                "condition": r.get("condition"),
                "seed_idx": r.get("seed_idx"),
                "flac": rel,
            })

    condition_summary = {}
    prompt_summary = {}
    for condition in sorted(k for k in condition_counts if k is not None):
        subset = [r for r in rows if r.get("condition") == condition]
        ok_subset = [r for r in subset if r.get("ok") is True]
        ratios = [float(r["vocal_energy_ratio"]) for r in ok_subset if "vocal_energy_ratio" in r]
        correct = sum(int(r.get("type_correct", 0)) for r in ok_subset)
        present = sum(int(r.get("present", 0)) for r in ok_subset)
        condition_summary[condition] = {
            "rows": len(subset),
            "ok": len(ok_subset),
            "errors": len(subset) - len(ok_subset),
            "requested_vocal": int(ok_subset[0].get("requested_vocal", 0)) if ok_subset else None,
            "present_rate": rate(present, len(ok_subset)),
            "type_correct_rate": rate(correct, len(ok_subset)),
            "near_silent": sum(1 for r in ok_subset if r.get("near_silent")),
            "vocal_energy_ratio": compact_stats(ratios),
        }

    for prompt_id in sorted(k for k in prompt_counts if k is not None):
        subset = [r for r in rows if r.get("prompt_id") == prompt_id]
        ok_subset = [r for r in subset if r.get("ok") is True]
        correct = sum(int(r.get("type_correct", 0)) for r in ok_subset)
        prompt_summary[prompt_id] = {
            "rows": len(subset),
            "ok": len(ok_subset),
            "errors": len(subset) - len(ok_subset),
            "requested_vocal": int(ok_subset[0].get("requested_vocal", 0)) if ok_subset else None,
            "type_correct_rate": rate(correct, len(ok_subset)),
            "conditions": dict(sorted(Counter(r.get("condition") for r in subset).items())),
        }

    report = {
        "patterns": args.patterns,
        "files": [str(p) for p in paths],
        "rows": len(rows),
        "expected_rows": args.expected_rows,
        "expected_rows_match": (len(rows) == args.expected_rows) if args.expected_rows else None,
        "ok": len(ok_rows),
        "errors": len(error_rows),
        "near_silent": len(near_silent_rows),
        "missing_flac": len(missing_flac),
        "missing_flac_examples": missing_flac[:20],
        "conditions": dict(sorted(condition_counts.items())),
        "prompts": len(prompt_counts),
        "sources": dict(sorted(source_counts.items())),
        "requested_vocal_counts": dict(sorted(requested_counts.items())),
        "type_correct_rate": rate(sum(int(r.get("type_correct", 0)) for r in ok_rows), len(ok_rows)),
        "condition_summary": condition_summary,
        "prompt_summary": prompt_summary,
        "verdict": "PASS" if not error_rows and not near_silent_rows and not missing_flac and (not args.expected_rows or len(rows) == args.expected_rows) else "FAIL",
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Generation Output Summary",
        "",
        f"Verdict: **{report['verdict']}**",
        f"Rows: {report['rows']}",
        f"Expected rows: {report['expected_rows'] or 'not set'}",
        f"OK rows: {report['ok']}",
        f"Errors: {report['errors']}",
        f"Near-silent rows: {report['near_silent']}",
        f"Missing FLACs: {report['missing_flac']}",
        f"Prompt count: {report['prompts']}",
        f"Overall type-correct rate: {report['type_correct_rate']:.6f}" if report["type_correct_rate"] is not None else "Overall type-correct rate: n/a",
        "",
        "## Condition Summary",
        "",
        "| Condition | Rows | OK | Type-correct | Present rate | Median ratio | Mean ratio |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, s in condition_summary.items():
        ratio_stats = s["vocal_energy_ratio"]
        lines.append(
            f"| {condition} | {s['rows']} | {s['ok']} | "
            f"{s['type_correct_rate']:.6f} | {s['present_rate']:.6f} | "
            f"{ratio_stats['median']:.6f} | {ratio_stats['mean']:.6f} |"
        )
    lines += ["", "## Source Counts", ""]
    for source, count in report["sources"].items():
        lines.append(f"- `{source}`: {count}")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n")

    print(json.dumps({"verdict": report["verdict"], "rows": len(rows)}, sort_keys=True))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
