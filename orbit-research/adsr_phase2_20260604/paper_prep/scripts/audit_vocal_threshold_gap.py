#!/usr/bin/env python3
"""Audit whether the historical 0.179/0.1791 difference changes any label."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD


HISTORICAL_THRESHOLD = VOCAL_PRESENCE_THRESHOLD - 0.0001
RATIO_KEYS = {
    "ratio",
    "vocal_energy_ratio",
    "gate_ratio",
    "demucs_ratio",
    "recorded_demucs_ratio",
    "original_demucs_ratio_rescored",
    "replay_demucs_ratio",
}


def is_candidate_ratio_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in RATIO_KEYS or (
        "ratio" in normalized
        and any(token in normalized for token in ("vocal", "demucs", "gate", "stem"))
    )


def iter_rows(path: Path):
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                if line.strip():
                    yield line_number, json.loads(line)
    elif path.suffix == ".csv":
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            for line_number, row in enumerate(csv.DictReader(handle), 2):
                yield line_number, row


def discover_inputs(repo_root: Path) -> list[Path]:
    explicit = [
        repo_root / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl",
    ]
    roots = [
        repo_root / "orbit-research/adsr_phase2_20260604/batch3",
        repo_root / "orbit-research/adsr_phase2_20260604/paper_prep",
        repo_root / "batch3/exploratory_auto",
    ]
    paths = {path.resolve() for path in explicit if path.is_file()}
    for root in roots:
        if not root.is_dir():
            continue
        for suffix in ("*.jsonl", "*.csv"):
            for path in root.rglob(suffix):
                if not any(part in {"logs", "audio", "media"} for part in path.parts):
                    paths.add(path.resolve())
    return sorted(paths)


def audit(paths: list[Path]) -> dict:
    gap_hits: list[dict] = []
    parse_errors: list[dict] = []
    field_counts: dict[str, int] = {}
    rows_parsed = 0
    values_checked = 0
    files_with_ratios = 0
    for path in paths:
        file_has_ratio = False
        try:
            for line_number, row in iter_rows(path):
                rows_parsed += 1
                if not isinstance(row, dict):
                    continue
                for key, value in row.items():
                    if not is_candidate_ratio_key(key):
                        continue
                    try:
                        ratio = float(value)
                    except (TypeError, ValueError):
                        continue
                    if not math.isfinite(ratio):
                        continue
                    file_has_ratio = True
                    values_checked += 1
                    field_counts[key] = field_counts.get(key, 0) + 1
                    if HISTORICAL_THRESHOLD <= ratio < VOCAL_PRESENCE_THRESHOLD:
                        gap_hits.append(
                            {
                                "path": str(path),
                                "line": line_number,
                                "field": key,
                                "value": ratio,
                            }
                        )
        except (OSError, csv.Error, json.JSONDecodeError) as exc:
            parse_errors.append({"path": str(path), "error": str(exc)})
        files_with_ratios += int(file_has_ratio)
    return {
        "status": "PASS" if not gap_hits and not parse_errors else "FAIL",
        "historical_threshold": HISTORICAL_THRESHOLD,
        "canonical_threshold": VOCAL_PRESENCE_THRESHOLD,
        "files_discovered": len(paths),
        "files_with_candidate_ratios": files_with_ratios,
        "rows_parsed": rows_parsed,
        "candidate_ratio_values_checked": values_checked,
        "field_counts": dict(sorted(field_counts.items())),
        "gap_hit_count": len(gap_hits),
        "gap_hits": gap_hits,
        "parse_errors": parse_errors,
    }


def write_outputs(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "VOCAL_THRESHOLD_GAP_AUDIT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = f"""# Vocal Threshold Gap Audit

`VOCAL_THRESHOLD_GAP_STATUS = {result['status']}`

The historical value 0.179 and canonical value
{result['canonical_threshold']:.4f} differ only for candidate ratios in
`[0.179, 0.1791)`. This read-only audit scanned completed ADSR candidate
ledgers and analysis tables.

| Measure | Count |
|---|---:|
| Files discovered | {result['files_discovered']} |
| Files containing candidate-ratio fields | {result['files_with_candidate_ratios']} |
| Rows parsed | {result['rows_parsed']} |
| Candidate-ratio values checked | {result['candidate_ratio_values_checked']} |
| Values in `[0.179, 0.1791)` | {result['gap_hit_count']} |
| Parse errors | {len(result['parse_errors'])} |

Conclusion: {'centralizing code at 0.1791 changes no observed candidate label.' if result['status'] == 'PASS' else 'the threshold migration is not label-neutral; inspect the JSON audit before using it.'}
"""
    (out_dir / "VOCAL_THRESHOLD_GAP_AUDIT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    result = audit(discover_inputs(args.repo_root.resolve()))
    write_outputs(result, args.out_dir)
    print(result["status"])
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
