#!/usr/bin/env python3
"""Produce the N2 population retry-map regime read-out."""

from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def regime(clean_rate: float) -> str:
    if clean_rate <= 1 / 16:
        return "rare_le_1_in_16"
    if clean_rate < 0.25:
        return "low_1_in_16_to_1_in_4"
    if clean_rate < 0.5:
        return "seed_recoverable_1_in_4_to_1_in_2"
    return "easy_ge_1_in_2"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--glob", action="append", required=True, dest="patterns")
    ap.add_argument("--expected-seeds", type=int, default=128)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-csv", required=True)
    args = ap.parse_args()

    manifest = {r["prompt_id"]: r for r in load_jsonl(Path(args.manifest))}
    paths = []
    for pattern in args.patterns:
        paths.extend(Path(p) for p in glob.glob(pattern))
    rows = []
    for path in sorted(set(paths)):
        rows.extend(load_jsonl(path))

    by_prompt = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(row)

    prompt_rows = []
    for prompt_id in sorted(manifest, key=lambda p: manifest[p]["prompt_index"]):
        rs = by_prompt.get(prompt_id, [])
        clean = sum(int(r.get("type_correct", 0)) for r in rs if r.get("ok") is True)
        present = sum(int(r.get("present", 0)) for r in rs if r.get("ok") is True)
        ok = sum(1 for r in rs if r.get("ok") is True)
        clean_rate = clean / ok if ok else None
        m = manifest[prompt_id]
        prompt_rows.append({
            "prompt_id": prompt_id,
            "prompt_index": m["prompt_index"],
            "vocal_stratum": m["vocal_stratum"],
            "selection_bin": m["selection_bin"],
            "baseline_violation_count_8": m["baseline_violation_count_8"],
            "baseline_clean_rate_8": m["baseline_clean_count_8"] / 8,
            "rows": len(rs),
            "ok": ok,
            "errors": len(rs) - ok,
            "clean_count": clean,
            "clean_rate": clean_rate,
            "present_rate": present / ok if ok else None,
            "regime": regime(clean_rate) if clean_rate is not None else "missing",
        })

    regime_counts = Counter(r["regime"] for r in prompt_rows)
    bin_summary = {}
    for bin_id in sorted({r["selection_bin"] for r in prompt_rows}):
        subset = [r for r in prompt_rows if r["selection_bin"] == bin_id]
        bin_summary[str(bin_id)] = {
            "prompts": len(subset),
            "mean_clean_rate": sum(r["clean_rate"] for r in subset) / len(subset),
            "regime_counts": dict(sorted(Counter(r["regime"] for r in subset).items())),
        }
    stratum_summary = {}
    for stratum in sorted({r["vocal_stratum"] for r in prompt_rows}):
        subset = [r for r in prompt_rows if r["vocal_stratum"] == stratum]
        stratum_summary[stratum] = {
            "prompts": len(subset),
            "mean_clean_rate": sum(r["clean_rate"] for r in subset) / len(subset),
            "regime_counts": dict(sorted(Counter(r["regime"] for r in subset).items())),
        }

    bad_prompt_counts = [r for r in prompt_rows if r["rows"] != args.expected_seeds]
    report = {
        "rows": len(rows),
        "prompts": len(prompt_rows),
        "expected_rows": len(prompt_rows) * args.expected_seeds,
        "expected_seeds_per_prompt": args.expected_seeds,
        "bad_prompt_counts": bad_prompt_counts,
        "regime_thresholds": {
            "rare_le_1_in_16": "<= 0.0625",
            "low_1_in_16_to_1_in_4": "(0.0625, 0.25)",
            "seed_recoverable_1_in_4_to_1_in_2": "[0.25, 0.5)",
            "easy_ge_1_in_2": ">= 0.5",
        },
        "regime_counts": dict(sorted(regime_counts.items())),
        "regime_fractions": {k: v / len(prompt_rows) for k, v in sorted(regime_counts.items())},
        "bin_summary": bin_summary,
        "stratum_summary": stratum_summary,
        "prompt_rows": prompt_rows,
        "verdict": "PASS" if not bad_prompt_counts and len(rows) == len(prompt_rows) * args.expected_seeds else "FAIL",
    }

    Path(args.out_json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    with Path(args.out_csv).open("w", newline="") as f:
        fieldnames = list(prompt_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prompt_rows)

    lines = [
        "# Population Retry Read-Out",
        "",
        f"Verdict: **{report['verdict']}**",
        f"Rows: {report['rows']}",
        f"Prompts: {report['prompts']}",
        f"Expected rows: {report['expected_rows']}",
        "",
        "## Regime Counts",
        "",
        "| Regime | Prompts | Fraction |",
        "|---|---:|---:|",
    ]
    for name, count in report["regime_counts"].items():
        lines.append(f"| {name} | {count} | {count / len(prompt_rows):.6f} |")
    lines += [
        "",
        "## Baseline-Violation Bin Summary",
        "",
        "| Baseline violations in 8 | Prompts | Mean clean rate | Regime counts |",
        "|---:|---:|---:|---|",
    ]
    for bin_id, s in bin_summary.items():
        lines.append(
            f"| {bin_id} | {s['prompts']} | {s['mean_clean_rate']:.6f} | "
            f"`{s['regime_counts']}` |"
        )
    lines += ["", "## Stratum Summary", ""]
    for stratum, s in stratum_summary.items():
        lines.append(
            f"- `{stratum}`: {s['prompts']} prompts, mean clean rate "
            f"{s['mean_clean_rate']:.6f}, regimes `{s['regime_counts']}`"
        )
    Path(args.out_md).write_text("\n".join(lines) + "\n")

    print(json.dumps({"verdict": report["verdict"], "rows": len(rows), "prompts": len(prompt_rows)}, sort_keys=True))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
