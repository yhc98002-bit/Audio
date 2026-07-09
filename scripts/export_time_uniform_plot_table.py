"""Export plot-ready tables and a PI memo from cached time-uniform diagnostics."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
from typing import Any


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _fmt(x: Any, digits: int = 3) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", default="orbit-research/TIME_UNIFORM_QUALITY_DIAGNOSTIC.json")
    parser.add_argument("--memo-out", default="orbit-research/TIME_UNIFORM_QUALITY_PI_MEMO.md")
    parser.add_argument("--csv-out", default="orbit-research/TIME_UNIFORM_QUALITY_PLOT_TABLE.csv")
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    uniformity = payload["plot_ready_tables"]["uniformity_by_unit_axis"]
    gaps = payload["plot_ready_tables"]["top_bottom_gap_by_position_bin"]
    usable = [r for r in uniformity if r.get("status") == "usable"]
    between_shares = [float(r["between_prompt_variance_share"]) for r in usable]
    ratios = [
        float(r["between_prompt_variance_share"]) / max(1e-12, 1.0 - float(r["between_prompt_variance_share"]))
        for r in usable
    ]
    crossing_rows = {}
    for row in gaps:
        key = (row["unit"], row["axis"])
        crossing_rows.setdefault(key, []).append(row)
    crossing = {}
    for key, rows in crossing_rows.items():
        finite = [r for r in rows if r.get("top_minus_bottom_gap") is not None]
        crossing[key] = {
            "finite_bins": len(finite),
            "crossing_frequency": (
                sum(1 for r in finite if float(r["top_minus_bottom_gap"]) <= 0.0) / len(finite)
                if finite else None
            ),
        }

    csv_path = Path(args.csv_out)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "table",
            "unit",
            "axis",
            "position_bin",
            "position_range",
            "reward_axis",
            "reward_value",
            "top_mean",
            "bottom_mean",
            "top_minus_bottom_gap",
            "between_prompt_variance_share",
            "between_within_ratio",
            "median_within_prompt_pstd",
            "median_within_prompt_range",
            "crossing_frequency",
            "status",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in uniformity:
            share = row.get("between_prompt_variance_share")
            ratio = None if share is None else float(share) / max(1e-12, 1.0 - float(share))
            cross = crossing.get((row["unit"], row["axis"]), {}).get("crossing_frequency")
            writer.writerow(
                {
                    "table": "uniformity_by_unit_axis",
                    "unit": row["unit"],
                    "axis": row["axis"],
                    "reward_axis": row["axis"],
                    "between_prompt_variance_share": share,
                    "between_within_ratio": ratio,
                    "median_within_prompt_pstd": row.get("median_within_prompt_pstd"),
                    "median_within_prompt_range": row.get("median_within_prompt_range"),
                    "crossing_frequency": cross,
                    "status": row.get("status"),
                }
            )
        for row in gaps:
            writer.writerow(
                {
                    "table": "top_bottom_gap_by_position_bin",
                    "unit": row["unit"],
                    "axis": row["axis"],
                    "position_bin": row["position_bin"],
                    "position_range": row["position_range"],
                    "reward_axis": row["axis"],
                    "reward_value": row.get("top_minus_bottom_gap"),
                    "top_mean": row.get("top_mean"),
                    "bottom_mean": row.get("bottom_mean"),
                    "top_minus_bottom_gap": row.get("top_minus_bottom_gap"),
                    "crossing_frequency": crossing.get((row["unit"], row["axis"]), {}).get("crossing_frequency"),
                }
            )

    lines = [
        "# Time-Uniform Quality Diagnostic PI Memo",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        "## Bottom Line",
        "",
        "Cached H3 local-vector diagnostics support a cautious time-uniform/global-quality reading. FixedWin appears more like a stable local proxy for global trajectory quality than a clean causal local-credit oracle.",
        "",
        "## Variance Summary",
        "",
        f"- usable cells: `{len(usable)}`",
        f"- median between-song variance share: `{_fmt(statistics.median(between_shares) if between_shares else None)}`",
        f"- median between/within ratio: `{_fmt(statistics.median(ratios) if ratios else None)}`",
        f"- cells with between-share >= 0.5: `{sum(1 for x in between_shares if x >= 0.5)}/{len(usable)}`",
        "",
        "| unit | axis | status | between_share | between/within | within_pstd | within_range | crossing_frequency |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in uniformity:
        share = row.get("between_prompt_variance_share")
        ratio = None if share is None else float(share) / max(1e-12, 1.0 - float(share))
        cross = crossing.get((row["unit"], row["axis"]), {}).get("crossing_frequency")
        lines.append(
            f"| {row['unit']} | {row['axis']} | {row.get('status')} | {_fmt(share)} | "
            f"{_fmt(ratio)} | {_fmt(row.get('median_within_prompt_pstd'))} | "
            f"{_fmt(row.get('median_within_prompt_range'))} | {_fmt(cross)} |"
        )
    lines.extend(
        [
            "",
            "## Top-vs-Bottom Time-Window Curves",
            "",
            "| unit | axis | 0.00-0.25 | 0.25-0.50 | 0.50-0.75 | 0.75-1.00 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for key in sorted(crossing_rows):
        rows = sorted(crossing_rows[key], key=lambda r: int(r["position_bin"]))
        values = [_fmt(r.get("top_minus_bottom_gap")) for r in rows]
        while len(values) < 4:
            values.append("NA")
        lines.append(f"| {key[0]} | {key[1]} | {values[0]} | {values[1]} | {values[2]} | {values[3]} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Musicality and prompt_fit provide the strongest evidence for broad time-uniform differences.",
            "- Coherence is degenerate or low dynamic range in this cached diagnostic and should not be used as positive evidence.",
            "- Do not change Phase C methods or paper claims automatically.",
            "",
            f"Plot-ready CSV: `{csv_path}`",
        ]
    )
    Path(args.memo_out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "csv": str(csv_path), "memo": args.memo_out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
