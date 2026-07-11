#!/usr/bin/env python3
"""Create old-vs-corrected ADSR headline diffs without mutating PLAN.md."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def clean(present: int, requested: int) -> int:
    return int(int(present) == int(requested))


def regime(rate: float) -> str:
    if rate >= 0.5:
        return "easy_ge_1_in_2"
    if rate >= 0.25:
        return "seed_recoverable_1_in_4_to_1_in_2"
    if rate > 1 / 16:
        return "low_1_in_16_to_1_in_4"
    return "rare_le_1_in_16"


def compute_diff(manifest: list[dict], corrected: list[dict]) -> list[dict]:
    manifest_index = {row["record_id"]: row for row in manifest}
    corrected_index = {}
    for row in corrected:
        if row.get("status") != "PASS":
            continue
        if row["record_id"] in corrected_index:
            raise ValueError(f"duplicate corrected result: {row['record_id']}")
        corrected_index[row["record_id"]] = row
    groups = defaultdict(list)
    for record_id, score in corrected_index.items():
        source = manifest_index.get(record_id)
        if source is None:
            raise ValueError(f"corrected result absent from manifest: {record_id}")
        if source.get("old_present", "") == "" or source.get("requested_vocal", "") == "":
            continue
        groups[(source["cohort"], source.get("condition", ""))].append((source, score))
    output = []
    for (cohort, condition), rows in sorted(groups.items()):
        old = sum(clean(int(source["old_present"]), int(source["requested_vocal"])) for source, _ in rows) / len(rows)
        new = sum(clean(int(score["present"]), int(source["requested_vocal"])) for source, score in rows) / len(rows)
        output.append(
            {
                "metric": "clean_rate",
                "cohort": cohort,
                "condition": condition,
                "n": len(rows),
                "old_value": old,
                "corrected_value": new,
                "delta": new - old,
            }
        )
    n2 = defaultdict(list)
    for record_id, score in corrected_index.items():
        source = manifest_index.get(record_id, {})
        if source.get("cohort") == "n2_population_retry":
            n2[source["prompt_id"]].append(
                clean(int(score["present"]), int(source["requested_vocal"]))
            )
    if n2:
        counts = Counter(regime(sum(values) / len(values)) for values in n2.values())
        for name, count in sorted(counts.items()):
            output.append(
                {
                    "metric": "n2_regime_prompt_count",
                    "cohort": "n2_population_retry",
                    "condition": name,
                    "n": len(n2),
                    "old_value": "",
                    "corrected_value": count,
                    "delta": "",
                }
            )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--corrected-ledger", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()
    rows = compute_diff(read_jsonl(args.manifest), read_jsonl(args.corrected_ledger))
    if not rows:
        raise ValueError("no comparable old/corrected headline rows")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# W2 Old-Versus-Corrected Headline Diff",
        "",
        "`W2_ADOPTION_STATUS = REVIEW_REQUIRED_NO_AUTOMATIC_PLAN_CHANGE`",
        "",
        "This report is generated only after a corrected instrument is selected. It does not relabel frozen evidence or change any gate/status line by itself.",
        "",
        "| Metric | Cohort | Condition | N | Old | Corrected | Delta |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['metric']} | {row['cohort']} | {row['condition']} | {row['n']} | {row['old_value']} | {row['corrected_value']} | {row['delta']} |"
        )
    args.output_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "status": "REVIEW_REQUIRED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
