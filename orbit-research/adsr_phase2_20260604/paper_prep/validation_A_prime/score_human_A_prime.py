#!/usr/bin/env python3
"""Score A-prime PI/human ratings."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path.cwd()
A_DIR = ROOT / "paper_prep" / "validation_A_prime"
PKG = A_DIR / "human_package"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def norm_label(value: str) -> str:
    value = (value or "").strip().lower()
    if value in {"yes", "y", "1", "voice", "vocal", "present"}:
        return "yes"
    if value in {"no", "n", "0", "none", "absent", "instrumental"}:
        return "no"
    if value in {"unsure", "unknown", "uncertain", "u", "tie", ""}:
        return "unsure"
    return "unparsed"


def wilson_half_width(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return math.nan, math.nan, math.nan
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + (z * z / (4 * n * n))) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, default=PKG / "A_PRIME_HUMAN_RATING_TEMPLATE.csv")
    parser.add_argument("--out", type=Path, default=A_DIR / "A_PRIME_HUMAN_GATE_REPORT.md")
    args = parser.parse_args()

    admin = {r["rating_id"]: r for r in read_csv(PKG / "A_PRIME_HUMAN_ADMIN_MANIFEST.csv")}
    ratings = read_csv(args.ratings)
    scored = []
    missing_rating = 0
    for row in ratings:
        rid = row["rating_id"]
        a = admin.get(rid)
        if not a:
            continue
        label = norm_label(row.get("contains_human_voice", ""))
        if label in {"unsure", "unparsed"}:
            missing_rating += 1
        truth = a.get("expected_present_label", "")
        expected_label = "yes" if truth == "1" else "no" if truth == "0" else ""
        status = ""
        if label in {"yes", "no"} and expected_label:
            status = "match" if label == expected_label else "disagree"
        scored.append({**a, "human_label": label, "expected_label": expected_label, "status": status})

    by_set: dict[str, Counter] = defaultdict(Counter)
    for row in scored:
        by_set[row["set_bucket"]][row["human_label"]] += 1

    rare = [r for r in scored if r["set_bucket"] == "rare_basin" and r["expected_label"]]
    rare_match = [r for r in rare if r["status"] == "match"]
    det = [r for r in scored if r["set_bucket"] == "detector_disagreement_packet" and r["expected_label"]]
    det_match = [r for r in det if r["status"] == "match"]
    agree = [r for r in scored if r["set_bucket"] == "agreement_spotcheck_30" and r["expected_label"]]
    agree_fail = [r for r in agree if r["status"] == "disagree"]
    strat = [r for r in scored if r["set_bucket"] == "stratified_random_500" and r["expected_label"]]
    strat_fail = [r for r in strat if r["status"] == "disagree"]

    rare_rate = len(rare_match) / len(rare) if rare else math.nan
    det_rate = len(det_match) / len(det) if det else math.nan
    strat_rate, strat_lo, strat_hi = wilson_half_width(len(strat_fail), len(strat))

    all_answered = len(scored) > 0 and missing_rating == 0
    pass_shape = (
        all_answered
        and len(rare) >= 50
        and rare_rate >= 0.90
        and len(det) >= 112
        and det_rate >= 0.70
        and len(agree) >= 30
        and len(agree_fail) <= 2
        and len(strat) >= 500
    )
    if pass_shape:
        status = "PASS"
    elif len(scored) and all_answered:
        status = "FAIL"
    else:
        status = "FALLBACK_READY"

    set_lines = "\n".join(
        f"- `{name}`: " + ", ".join(f"{k}={v}" for k, v in sorted(counter.items()))
        for name, counter in sorted(by_set.items())
    )
    args.out.write_text(
        f"""# A-prime Human Gate Report

A_PRIME_STATUS = {status}

Input ratings: `{args.ratings}`

## Coverage

- Admin rows: {len(admin)}
- Rating rows read: {len(ratings)}
- Rows joined to admin: {len(scored)}
- Unanswered/unsure/unparsed rows: {missing_rating}

## Frozen Criteria

- Rare-basin confirmation: {len(rare_match)}/{len(rare)} = {rare_rate:.6f}; required >= 0.90 on about 50 clips.
- Detector-disagreement agreement with reference label: {len(det_match)}/{len(det)} = {det_rate:.6f}; checklist requires >= 0.70 on 112 cases.
- Agreement-spotcheck failures: {len(agree_fail)}/{len(agree)}; required <= 2/30.
- Stratified global disagreement: {len(strat_fail)}/{len(strat)} = {strat_rate:.6f}; Wilson 95% CI [{strat_lo:.6f}, {strat_hi:.6f}].

## Set-Level Human Labels

{set_lines}

## Interpretation

Do not claim A-prime passed unless `A_PRIME_STATUS = PASS`. If this report says
`FALLBACK_READY`, the package still needs completed PI/human ratings or has
insufficient cardinality for the frozen checklist.
""",
        encoding="utf-8",
    )
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
