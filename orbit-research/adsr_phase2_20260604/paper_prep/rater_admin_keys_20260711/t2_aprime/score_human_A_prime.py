#!/usr/bin/env python3
"""Score the amended original-only A-prime PI package."""
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
from validation_gate_v2 import score_a_prime  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    package = ROOT / "paper_prep/validation_A_prime/primary_package_20260709"
    keys = ROOT / "paper_prep/rater_admin_keys_20260711/t2_aprime"
    parser.add_argument("--admin", type=Path, default=keys / "A_PRIME_PRIMARY_ADMIN.csv")
    parser.add_argument("--ratings", type=Path, default=package / "A_PRIME_PRIMARY_RATINGS.csv")
    parser.add_argument("--out", type=Path, default=keys / "A_PRIME_HUMAN_GATE_REPORT_20260709.md")
    parser.add_argument("--abstain-policy", choices=["report", "count-as-disagree"], default="report")
    args = parser.parse_args()
    result = score_a_prime(read_csv(args.admin), read_csv(args.ratings), args.abstain_policy)
    b = result["constructs"]["label_b"]
    a = result["constructs"]["label_a"]
    report = f"""# A-prime Amended Human Gate Report

`A_PRIME_STATUS = {result['status']}`

- Abstain policy: `{result['abstain_policy']}`.
- Regenerated primary rows excluded: {result['excluded_regenerated_primary']}.
- Real ratings complete: {str(result['complete_real_ratings']).lower()}.
- Mechanical criteria status: `{result['criteria_status']}`.

| Gate set | Label B matches/decided | Label B rate | Label A matches/decided | Label A rate |
|---|---:|---:|---:|---:|
"""
    for bucket in ("rare_basin_48", "detector_disagreement_112", "agreement_spotcheck_30", "stratified_random_500"):
        report += f"| {bucket} | {b[bucket]['matches']}/{b[bucket]['decided']} | {b[bucket]['match_rate']:.6f} | {a[bucket]['matches']}/{a[bucket]['decided']} | {a[bucket]['match_rate']:.6f} |\n"
    report += f"""

The stratified 500 supplies a global Wilson bound and is not part of the pass
shape. Label B is the paper endpoint; Label A is a reported detector construct
sensitivity. A mechanical result never signs the gate: the PI makes the gate
call. Criteria evaluation is forbidden unless all 190 core rows carry `pi:<name>` or
`human:<initials>` provenance and every global row carries either the same
human provenance or a fully documented validated-judge source.

```json
{json.dumps(result, indent=2, sort_keys=True)}
```
"""
    args.out.write_text(report, encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
