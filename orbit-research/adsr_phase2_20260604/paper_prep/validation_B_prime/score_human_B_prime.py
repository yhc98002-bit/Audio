#!/usr/bin/env python3
"""Score B-prime PI/human quality ratings with pair-level aggregation."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path.cwd()
B_DIR = ROOT / "paper_prep" / "validation_B_prime"
PKG = B_DIR / "human_package"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def norm_pref(value: str) -> str:
    value = (value or "").strip().lower()
    if value in {"a", "clip_a", "left", "first"}:
        return "a"
    if value in {"b", "clip_b", "right", "second"}:
        return "b"
    if value in {"tie", "same", "equal", "neither"}:
        return "tie"
    if value in {"unsure", "unknown", "u", ""}:
        return "unsure"
    return "unparsed"


def exact_binom_less_equal(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return math.nan
    return sum(math.comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k + 1))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return math.nan, math.nan, math.nan
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def pref_to_arm(admin_row: dict[str, str], pref: str) -> str:
    if pref == "a":
        return admin_row["presented_a_is"]
    if pref == "b":
        return admin_row["presented_b_is"]
    return pref


def arm_to_class(arm: str) -> str:
    if arm == "arm6":
        return "method"
    if arm in {"arm1", "arm4"}:
        return "baseline"
    return arm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, default=PKG / "B_PRIME_HUMAN_RATING_TEMPLATE.csv")
    parser.add_argument("--out", type=Path, default=B_DIR / "B_PRIME_HUMAN_GATE_REPORT.md")
    args = parser.parse_args()

    admin = {r["rating_id"]: r for r in read_csv(PKG / "B_PRIME_HUMAN_ORDERED_ADMIN_MANIFEST.csv")}
    pair_admin = {r["pair_id"]: r for r in read_csv(PKG / "B_PRIME_HUMAN_PAIR_ADMIN.csv")}
    ratings = read_csv(args.ratings)

    joined = []
    order_counts: dict[str, Counter] = defaultdict(Counter)
    pair_votes: dict[str, list[str]] = defaultdict(list)
    unanswered = 0
    for row in ratings:
        rid = row["rating_id"]
        a = admin.get(rid)
        if not a:
            continue
        pref = norm_pref(row.get("quality_preference", ""))
        if pref in {"unsure", "unparsed"}:
            unanswered += 1
        arm = pref_to_arm(a, pref)
        klass = arm_to_class(arm)
        joined.append({**a, "quality_preference": pref, "chosen_arm": arm, "preference_class": klass})
        order_counts[a["order"]][klass] += 1
        if klass in {"method", "baseline", "tie"}:
            pair_votes[a["pair_id"]].append(klass)

    pair_rows = []
    for pair_id, votes in pair_votes.items():
        counts = Counter(votes)
        if counts["method"] > counts["baseline"] and counts["method"] > counts["tie"]:
            result = "method"
        elif counts["baseline"] > counts["method"] and counts["baseline"] > counts["tie"]:
            result = "baseline"
        elif counts["method"] == counts["baseline"] and counts["method"] > 0:
            result = "tie"
        elif counts["tie"] > 0:
            result = "tie"
        else:
            result = "unscored"
        pair_rows.append({"pair_id": pair_id, "result": result, **pair_admin.get(pair_id, {})})

    decided = [r for r in pair_rows if r["result"] in {"method", "baseline"}]
    method = [r for r in decided if r["result"] == "method"]
    method_rate, lo, hi = wilson(len(method), len(decided))
    p_less = exact_binom_less_equal(len(method), len(decided)) if decided else math.nan
    all_answered = len(joined) == len(admin) and unanswered == 0
    pass_shape = all_answered and len(decided) > 0 and method_rate >= 0.40 and p_less >= 0.05
    if pass_shape:
        status = "PASS"
    elif all_answered and joined:
        status = "FAIL"
    else:
        status = "FALLBACK_READY"

    calib = [r for r in pair_rows if r.get("in_calibration_24") == "true"]
    calib_decided = [r for r in calib if r["result"] in {"method", "baseline"}]
    order_lines = "\n".join(
        f"- `{order}`: " + ", ".join(f"{k}={v}" for k, v in sorted(counter.items()))
        for order, counter in sorted(order_counts.items())
    )
    args.out.write_text(
        f"""# B-prime Human Gate Report

B_PRIME_STATUS = {status}

Input ratings: `{args.ratings}`

## Coverage

- Ordered admin rows: {len(admin)}
- Rating rows read: {len(ratings)}
- Joined ordered rows: {len(joined)}
- Unanswered/unsure/unparsed ordered rows: {unanswered}
- Pair rows with any scored vote: {len(pair_rows)}
- Decided pairs: {len(decided)}
- Calibration pairs represented: {len(calib)}
- Decided calibration pairs: {len(calib_decided)}

## Pair-Level Primary Result

- Method-preferred decided pairs: {len(method)}/{len(decided)} = {method_rate:.6f}; Wilson 95% CI [{lo:.6f}, {hi:.6f}].
- One-sided binomial P[X <= observed | p=0.5]: {p_less:.6f}; non-inferiority requires not significantly below 50% at 5%.
- Frozen pass shape: method rate >= 0.40 and p >= 0.05.

## Order Bias

{order_lines}

## Interpretation

Do not claim B-prime passed unless `B_PRIME_STATUS = PASS`. If this report says
`FALLBACK_READY`, the package is ready for PI/human ratings but the ratings are
not complete enough for the gate.
""",
        encoding="utf-8",
    )
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
