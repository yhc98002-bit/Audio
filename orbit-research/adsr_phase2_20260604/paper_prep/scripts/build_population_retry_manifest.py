#!/usr/bin/env python3
"""Build the N2 population retry-map prompt manifest.

Selection is deterministic and stratified over the held-out 8-candidate
violation-count histogram derived from `vocal_presence_raw.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD


THR = VOCAL_PRESENCE_THRESHOLD


def load_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def prompt_index(prompt_id: str) -> int:
    return int(prompt_id.rsplit("_", 1)[1])


def evenly_spaced(rows: list[dict], n: int) -> list[dict]:
    if n >= len(rows):
        return rows
    if n <= 0:
        return []
    rows = sorted(rows, key=lambda r: r["prompt_id"])
    idxs = [math.floor((i + 0.5) * len(rows) / n) for i in range(n)]
    return [rows[i] for i in idxs]


def allocate_targets(counts: Counter, total: int) -> dict[int, int]:
    raw = {k: counts[k] * total / sum(counts.values()) for k in counts}
    target = {k: math.floor(v) for k, v in raw.items()}
    remaining = total - sum(target.values())
    residual_order = sorted(counts, key=lambda k: (raw[k] - target[k], k), reverse=True)
    for k in residual_order[:remaining]:
        target[k] += 1
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--held-out", required=True)
    ap.add_argument("--vocal-presence-raw", required=True)
    ap.add_argument("--n-prompts", type=int, default=128)
    ap.add_argument("--threshold", type=float, default=THR)
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--out-summary-json", required=True)
    ap.add_argument("--out-summary-md", required=True)
    args = ap.parse_args()

    prompts = {r["prompt_id"]: r for r in load_jsonl(Path(args.held_out))}
    raw_by_prompt = defaultdict(list)
    for row in load_jsonl(Path(args.vocal_presence_raw)):
        pid = row["prompt_id"]
        if pid in prompts:
            raw_by_prompt[pid].append(row)

    candidates = []
    for pid, prompt in sorted(prompts.items(), key=lambda kv: prompt_index(kv[0])):
        rows = sorted(raw_by_prompt.get(pid, []), key=lambda r: r["candidate_index"])
        if len(rows) != 8:
            raise RuntimeError(f"{pid} has {len(rows)} raw rows, expected 8")
        stratum = prompt["strata"]["vocal_vs_instrumental"]
        requested_vocal = int(stratum == "vocal")
        present_count = 0
        violation_count = 0
        for row in rows:
            present = int(row["vocal_energy_ratio"] >= args.threshold and not row.get("near_silent", False))
            present_count += present
            violation_count += int(present != requested_vocal)
        candidates.append({
            "prompt_id": pid,
            "prompt_index": prompt_index(pid),
            "text": prompt["text"],
            "lyrics": prompt.get("lyrics"),
            "structure_hint": prompt.get("structure_hint"),
            "duration_target": prompt.get("duration_target"),
            "vocal_stratum": stratum,
            "source": "population_retry_map_heldout",
            "baseline_violation_count_8": violation_count,
            "baseline_clean_count_8": 8 - violation_count,
            "baseline_present_count_8": present_count,
            "selection_threshold": args.threshold,
        })

    hist = Counter(r["baseline_violation_count_8"] for r in candidates)
    targets = allocate_targets(hist, args.n_prompts)
    selected = []
    for violation_count in sorted(targets):
        bucket = [r for r in candidates if r["baseline_violation_count_8"] == violation_count]
        by_stratum = defaultdict(list)
        for row in bucket:
            by_stratum[row["vocal_stratum"]].append(row)
        stratum_counts = Counter({k: len(v) for k, v in by_stratum.items()})
        stratum_targets = allocate_targets(stratum_counts, targets[violation_count])
        for stratum in sorted(stratum_targets):
            for row in evenly_spaced(by_stratum[stratum], stratum_targets[stratum]):
                row = dict(row)
                row["selection_bin"] = violation_count
                selected.append(row)

    selected = sorted(selected, key=lambda r: (r["baseline_violation_count_8"], r["vocal_stratum"], r["prompt_id"]))
    if len(selected) != args.n_prompts:
        raise RuntimeError(f"selected {len(selected)} prompts, expected {args.n_prompts}")
    if len({r["prompt_id"] for r in selected}) != len(selected):
        raise RuntimeError("duplicate prompt_id in selected manifest")

    out_jsonl = Path(args.out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("w") as f:
        for rank, row in enumerate(selected):
            row = dict(row)
            row["selection_rank"] = rank
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    selected_hist = Counter(r["baseline_violation_count_8"] for r in selected)
    selected_by_stratum = defaultdict(Counter)
    for row in selected:
        selected_by_stratum[row["vocal_stratum"]][row["baseline_violation_count_8"]] += 1

    summary = {
        "threshold": args.threshold,
        "source_prompt_count": len(candidates),
        "selected_prompt_count": len(selected),
        "source_histogram": dict(sorted(hist.items())),
        "target_histogram": dict(sorted(targets.items())),
        "selected_histogram": dict(sorted(selected_hist.items())),
        "selected_by_stratum": {k: dict(sorted(v.items())) for k, v in sorted(selected_by_stratum.items())},
        "selected_prompt_ids": [r["prompt_id"] for r in selected],
    }
    Path(args.out_summary_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Population Retry Manifest",
        "",
        f"Threshold: {args.threshold}",
        f"Source held-out prompts: {len(candidates)}",
        f"Selected prompts: {len(selected)}",
        "",
        "## Histogram",
        "",
        "| Violations in 8 | Source | Target | Selected |",
        "|---:|---:|---:|---:|",
    ]
    for k in sorted(hist):
        lines.append(f"| {k} | {hist[k]} | {targets.get(k, 0)} | {selected_hist.get(k, 0)} |")
    lines += ["", "## Selected By Stratum", ""]
    for stratum, counter in summary["selected_by_stratum"].items():
        lines.append(f"- `{stratum}`: {sum(counter.values())} prompts; bins {counter}")
    Path(args.out_summary_md).write_text("\n".join(lines) + "\n")
    print(json.dumps({"selected": len(selected), "histogram": summary["selected_histogram"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
