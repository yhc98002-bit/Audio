#!/usr/bin/env python3
"""Score the amended B-prime solo-rater package."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def find_root(path: Path) -> Path:
    for candidate in path.parents:
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from validation_gate_v2 import score_b_prime  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    package = ROOT / "paper_prep/validation_B_prime/pi_package_20260709"
    parser.add_argument("--pair-admin", type=Path, default=package / "B_PRIME_PAIR_ADMIN.csv")
    parser.add_argument("--ordered-admin", type=Path, default=package / "B_PRIME_ORDERED_ADMIN.csv")
    parser.add_argument("--ratings", type=Path, default=package / "B_PRIME_PI_RATINGS.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "paper_prep/validation_B_prime/B_PRIME_HUMAN_GATE_REPORT_20260709.md")
    parser.add_argument("--abstain-policy", choices=["report", "count-as-disagree"], default="report")
    args = parser.parse_args()
    result = score_b_prime(read_csv(args.pair_admin), read_csv(args.ordered_admin), read_csv(args.ratings), args.abstain_policy)
    report = f"""# B-prime Amended Human Gate Report

`B_PRIME_STATUS = {result['status']}`

- Primary endpoint: `quality_preference` from the first presentation of each pair.
- Reversed 24-pair presentations: reliability only, never extra votes.
- Primary criterion: one-sided 95% score lower bound > 0.40.
- Abstain policy: `{result['abstain_policy']}`.

| Endpoint | Method/decided | Rate | One-sided lower | Primary NI pass | Ties-half | Ties-against |
|---|---:|---:|---:|---:|---:|---:|
"""
    for endpoint, values in result["endpoints"].items():
        method = values["counts"].get("method", 0)
        report += f"| {endpoint} | {method}/{values['decided']} | {values['method_rate']:.6f} | {values['one_sided_95_lower']:.6f} | {str(values['primary_noninferiority_pass']).lower()} | {values['ties_as_half_rate']:.6f} | {values['ties_against_method_rate']:.6f} |\n"
    report += f"""

A PASS is forbidden until every row carries non-synthetic human/PI rating
provenance. Quality, overall, and constraint questions are reported separately.

```json
{json.dumps(result, indent=2, sort_keys=True)}
```
"""
    args.out.write_text(report, encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
