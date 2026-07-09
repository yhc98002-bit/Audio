#!/usr/bin/env python3
"""Audit append-only JSONL ledgers for schema, duplicates, and row counts.

The script is intentionally generic: pass one or more glob patterns, a duplicate
key, and optional required columns. It writes a JSON report and can emit a compact
Markdown summary for paper-prep checkpoints.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path):
    with path.open() as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                yield lineno, json.loads(line)
            except json.JSONDecodeError as exc:
                yield lineno, {"__parse_error__": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--glob", action="append", required=True, dest="patterns")
    ap.add_argument("--key", default="", help="Comma-separated duplicate-key columns")
    ap.add_argument("--required", default="", help="Comma-separated required columns")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", default="")
    args = ap.parse_args()

    paths: list[Path] = []
    for pattern in args.patterns:
        paths.extend(Path(p) for p in glob.glob(pattern))
    paths = sorted(set(paths))

    key_cols = [c for c in (s.strip() for s in args.key.split(",")) if c]
    required = [c for c in (s.strip() for s in args.required.split(",")) if c]

    rows = 0
    parse_errors = []
    missing_required = []
    file_rows = Counter()
    key_counts = Counter()
    key_examples = defaultdict(list)
    column_counts = Counter()
    file_hashes = {}

    for path in paths:
        file_hashes[str(path)] = sha256(path)
        for lineno, rec in load_jsonl(path):
            rows += 1
            file_rows[str(path)] += 1
            if "__parse_error__" in rec:
                parse_errors.append({"path": str(path), "line": lineno, "error": rec["__parse_error__"]})
                continue
            column_counts.update(rec.keys())
            miss = [c for c in required if c not in rec]
            if miss:
                missing_required.append({"path": str(path), "line": lineno, "missing": miss})
            if key_cols:
                key = tuple(rec.get(c) for c in key_cols)
                key_counts[key] += 1
                if len(key_examples[key]) < 3:
                    key_examples[key].append({"path": str(path), "line": lineno})

    duplicate_keys = []
    if key_cols:
        for key, count in key_counts.items():
            if count > 1:
                duplicate_keys.append({
                    "key": dict(zip(key_cols, key)),
                    "count": count,
                    "examples": key_examples[key],
                })

    report = {
        "patterns": args.patterns,
        "files": [str(p) for p in paths],
        "n_files": len(paths),
        "n_rows": rows,
        "file_rows": dict(file_rows),
        "file_sha256": file_hashes,
        "key_columns": key_cols,
        "required_columns": required,
        "parse_errors": parse_errors,
        "missing_required": missing_required,
        "duplicate_keys": duplicate_keys,
        "n_parse_errors": len(parse_errors),
        "n_missing_required": len(missing_required),
        "n_duplicate_keys": len(duplicate_keys),
        "columns": sorted(column_counts),
        "verdict": "PASS" if not parse_errors and not missing_required and not duplicate_keys else "FAIL",
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Ledger Audit",
            "",
            f"Verdict: **{report['verdict']}**",
            f"Files: {len(paths)}",
            f"Rows: {rows}",
            f"Parse errors: {len(parse_errors)}",
            f"Missing-required rows: {len(missing_required)}",
            f"Duplicate keys: {len(duplicate_keys)}",
            "",
            "## File Rows",
            "",
        ]
        for p, n in sorted(file_rows.items()):
            lines.append(f"- `{p}`: {n}")
        if duplicate_keys[:10]:
            lines += ["", "## First Duplicate Keys", ""]
            for dup in duplicate_keys[:10]:
                lines.append(f"- `{dup['key']}` count={dup['count']}")
        out_md.write_text("\n".join(lines) + "\n")

    print(json.dumps({"verdict": report["verdict"], "rows": rows, "files": len(paths)}, sort_keys=True))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
