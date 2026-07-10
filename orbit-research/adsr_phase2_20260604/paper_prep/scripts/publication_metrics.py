#!/usr/bin/env python3
"""Reproduce publication-facing metrics from existing PH2 and ATLAS ledgers."""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import median


REPO = Path(os.environ.get("MPRM_REPO_ROOT", Path(__file__).resolve().parents[4])).resolve()
ATLAS = REPO / "batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test"
PH2 = REPO / "orbit-research/adsr_phase2_20260604"


def read_jsonl_paths(pattern: str):
    for path in sorted(glob.glob(str(pattern))):
        with open(path) as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                rec = json.loads(line)
                rec["_ledger_path"] = path
                rec["_lineno"] = lineno
                yield rec


def dedup(records, key_cols):
    out = {}
    dups = 0
    for rec in records:
        key = tuple(rec.get(c) for c in key_cols)
        if key in out:
            dups += 1
            continue
        out[key] = rec
    return list(out.values()), dups


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - half, center + half


def prompt_rates(rows):
    by_prompt = defaultdict(list)
    for rec in rows:
        if "type_correct" in rec:
            by_prompt[rec["prompt_id"]].append(int(rec["type_correct"]))
    return {pid: mean(vals) for pid, vals in by_prompt.items()}


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    baseline_raw = list(read_jsonl_paths(ATLAS / "ledgers/bon256_w*.jsonl"))
    baseline, baseline_dups = dedup(baseline_raw, ["prompt_id", "condition", "seed_idx"])
    v3_raw = list(read_jsonl_paths(ATLAS / "ledgers/v3_vocal_w*.jsonl"))
    v3, v3_dups = dedup(v3_raw, ["prompt_id", "condition", "seed_idx"])
    istrong_raw = list(read_jsonl_paths(ATLAS / "ledgers/istrong_instr_w*.jsonl"))
    istrong, istrong_dups = dedup(istrong_raw, ["prompt_id", "condition", "seed_idx"])

    baseline_rates = prompt_rates(baseline)
    v3_rates = prompt_rates(v3)
    istrong_rates = prompt_rates(istrong)

    prompt_rows = []
    for pid, rate in sorted(baseline_rates.items()):
        subset = [r for r in baseline if r["prompt_id"] == pid]
        requested_vocal = subset[0].get("requested_vocal")
        n = len(subset)
        k = sum(int(r["type_correct"]) for r in subset)
        lo, hi = wilson_ci(k, n)
        prompt_rows.append({
            "prompt_id": pid,
            "requested_vocal": requested_vocal,
            "baseline_n": n,
            "baseline_clean": k,
            "baseline_p_clean": round(rate, 6),
            "baseline_ci95_lo": round(lo, 6),
            "baseline_ci95_hi": round(hi, 6),
            "v3_p_clean": round(v3_rates[pid], 6) if pid in v3_rates else "",
            "v3_delta": round(v3_rates[pid] - rate, 6) if pid in v3_rates else "",
            "istrong_p_clean": round(istrong_rates[pid], 6) if pid in istrong_rates else "",
            "istrong_delta": round(istrong_rates[pid] - rate, 6) if pid in istrong_rates else "",
        })

    write_csv(
        out_dir / "T21_efficiency_metrics.csv",
        prompt_rows,
        [
            "prompt_id", "requested_vocal", "baseline_n", "baseline_clean",
            "baseline_p_clean", "baseline_ci95_lo", "baseline_ci95_hi",
            "v3_p_clean", "v3_delta", "istrong_p_clean", "istrong_delta",
        ],
    )

    vocal_rates = [r["baseline_p_clean"] for r in prompt_rows if str(r["requested_vocal"]) == "1"]
    instr_rates = [r["baseline_p_clean"] for r in prompt_rows if str(r["requested_vocal"]) == "0"]
    v3_deltas = [float(r["v3_delta"]) for r in prompt_rows if r["v3_delta"] != ""]
    istrong_deltas = [float(r["istrong_delta"]) for r in prompt_rows if r["istrong_delta"] != ""]

    summary = {
        "baseline_rows_raw": len(baseline_raw),
        "baseline_rows_dedup": len(baseline),
        "baseline_duplicate_rows_dropped": baseline_dups,
        "v3_rows_raw": len(v3_raw),
        "v3_rows_dedup": len(v3),
        "v3_duplicate_rows_dropped": v3_dups,
        "istrong_rows_raw": len(istrong_raw),
        "istrong_rows_dedup": len(istrong),
        "istrong_duplicate_rows_dropped": istrong_dups,
        "n_prompts": len(prompt_rows),
        "n_vocal_prompts": len(vocal_rates),
        "n_instrumental_prompts": len(instr_rates),
        "baseline_vocal_mean": round(mean(vocal_rates), 6),
        "baseline_vocal_median": round(median(vocal_rates), 6),
        "baseline_instrumental_mean": round(mean(instr_rates), 6),
        "baseline_instrumental_median": round(median(instr_rates), 6),
        "zero_clean_prompts": sum(1 for r in prompt_rows if int(r["baseline_clean"]) == 0),
        "v3_delta_mean": round(mean(v3_deltas), 6),
        "v3_delta_median": round(median(v3_deltas), 6),
        "v3_prompts_improved": sum(1 for d in v3_deltas if d > 0),
        "v3_prompts_total": len(v3_deltas),
        "istrong_delta_mean": round(mean(istrong_deltas), 6),
        "istrong_delta_median": round(median(istrong_deltas), 6),
        "istrong_prompts_improved": sum(1 for d in istrong_deltas if d > 0),
        "istrong_prompts_total": len(istrong_deltas),
    }
    (out_dir / "T21_efficiency_metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    md = [
        "# T2.1 Efficiency Metrics",
        "",
        "Source ledgers:",
        f"- Baseline: `{ATLAS.relative_to(REPO)}/ledgers/bon256_w*.jsonl`",
        f"- Vocal intervention: `{ATLAS.relative_to(REPO)}/ledgers/v3_vocal_w*.jsonl`",
        f"- Instrumental intervention: `{ATLAS.relative_to(REPO)}/ledgers/istrong_instr_w*.jsonl`",
        "",
        "## Summary",
        "",
        f"- Baseline dedup rows: {summary['baseline_rows_dedup']} "
        f"(raw {summary['baseline_rows_raw']}, dropped {summary['baseline_duplicate_rows_dropped']}).",
        f"- Prompts: {summary['n_prompts']} "
        f"({summary['n_vocal_prompts']} vocal, {summary['n_instrumental_prompts']} instrumental).",
        f"- Zero-clean prompts at frozen baseline: {summary['zero_clean_prompts']}.",
        f"- Vocal clean-rate median: {summary['baseline_vocal_median']:.4f}; "
        f"mean: {summary['baseline_vocal_mean']:.4f}.",
        f"- Instrumental clean-rate median: {summary['baseline_instrumental_median']:.4f}; "
        f"mean: {summary['baseline_instrumental_mean']:.4f}.",
        f"- V3 vocal intervention mean delta: {summary['v3_delta_mean']:+.4f}; "
        f"improved {summary['v3_prompts_improved']}/{summary['v3_prompts_total']} prompts.",
        f"- I_strong instrumental intervention mean delta: {summary['istrong_delta_mean']:+.4f}; "
        f"improved {summary['istrong_prompts_improved']}/{summary['istrong_prompts_total']} prompts.",
        "",
        "CSV: `T21_efficiency_metrics.csv`",
        "JSON: `T21_efficiency_metrics.json`",
    ]
    (out_dir / "T21_efficiency_metrics.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
