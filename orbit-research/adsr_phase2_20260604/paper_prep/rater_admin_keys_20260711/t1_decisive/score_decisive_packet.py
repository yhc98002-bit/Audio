#!/usr/bin/env python3
"""Score the non-gating PI construct-branch packet."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path


def find_root(path: Path) -> Path:
    for candidate in path.parents:
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from bundle_response_io import remap_bundle_rows  # noqa: E402
from rating_provenance import validate_human_rating_rows  # noqa: E402


def normalize(value: str) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def label_a_presence(value: str) -> int | None:
    value = normalize(value)
    if value in {"yes", "y", "1"}:
        return 1
    if value in {"no", "n", "0"}:
        return 0
    if value in {"unsure", "unknown", "uncertain", "u", ""}:
        return None
    raise ValueError(f"invalid Label A: {value!r}")


def label_b_presence(value: str, requested_vocal: str) -> int | None:
    value = normalize(value)
    if value in {"unsure", "unknown", "uncertain", "u", ""}:
        return None
    if value not in {"satisfied", "violated"}:
        raise ValueError(f"invalid Label B: {value!r}")
    if requested_vocal not in {"0", "1"}:
        raise ValueError(f"invalid requested_vocal: {requested_vocal!r}")
    return int((requested_vocal == "1" and value == "satisfied") or (requested_vocal == "0" and value == "violated"))


def score(admin: list[dict[str, str]], ratings: list[dict[str, str]]) -> dict:
    admin_ids = [row["rating_id"] for row in admin]
    rating_ids = [row["rating_id"] for row in ratings]
    if len(admin_ids) != len(set(admin_ids)) or len(rating_ids) != len(set(rating_ids)):
        raise ValueError("duplicate rating_id")
    if set(admin_ids) != set(rating_ids):
        raise ValueError("admin/rating ID mismatch")
    if len(admin) != 42:
        raise ValueError(f"decisive packet must contain 42 rows, got {len(admin)}")
    provenance_counts = validate_human_rating_rows(ratings, id_field="rating_id")
    rating_index = {row["rating_id"]: row for row in ratings}
    scored = []
    for admin_row in admin:
        rating = rating_index[admin_row["rating_id"]]
        a = label_a_presence(rating.get("label_a_voice_presence", ""))
        b = label_b_presence(rating.get("label_b_constraint", ""), admin_row["requested_vocal"])
        scored.append({**admin_row, "label_a_presence": a, "label_b_presence": b})

    contested = [
        row for row in scored
        if row["category"] in {"failed_smoke_negative_4", "judge_yes_demucs_no_20"}
    ]
    if len(contested) != 24:
        raise ValueError(f"contested branch set has {len(contested)} rows, expected 24")
    controls = [row for row in scored if row["category"] == "obvious_agreement_control_6"]
    decided_b = [row for row in contested if row["label_b_presence"] is not None]
    decided_both = [
        row for row in contested
        if row["label_a_presence"] is not None and row["label_b_presence"] is not None
    ]
    construct_disagreement = (
        sum(row["label_a_presence"] != row["label_b_presence"] for row in decided_both)
        / len(decided_both)
        if decided_both else math.nan
    )
    judge_matches = sum(row["label_b_presence"] == 1 for row in decided_b)
    demucs_matches = sum(row["label_b_presence"] == 0 for row in decided_b)
    control_decided = [row for row in controls if row["label_b_presence"] is not None]
    control_matches = sum(
        row["label_b_presence"] == int(row["demucs_label"] == "yes")
        for row in control_decided
    )

    if len(decided_b) < 20 or len(control_decided) < 5:
        verdict = "construct_mismatch"
    elif control_matches < 5 or (not math.isnan(construct_disagreement) and construct_disagreement >= 0.25):
        verdict = "construct_mismatch"
    elif judge_matches / len(decided_b) >= 2 / 3:
        verdict = "demucs_missing"
    elif demucs_matches / len(decided_b) >= 2 / 3:
        verdict = "judge_over_calling"
    else:
        verdict = "construct_mismatch"
    return {
        "branch_verdict": verdict,
        "real_ratings_complete": True,
        "provenance_counts": provenance_counts,
        "contested_rows": len(contested),
        "contested_label_b_decided": len(decided_b),
        "judge_matches_label_b": judge_matches,
        "demucs_matches_label_b": demucs_matches,
        "label_a_b_decided": len(decided_both),
        "label_a_b_disagreement_rate": construct_disagreement,
        "control_decided": len(control_decided),
        "control_matches": control_matches,
        "category_counts": dict(Counter(row["category"] for row in scored)),
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    keys = Path(__file__).resolve().parent
    package = ROOT / "paper_prep/pi_decisive_packet_20260709"
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin", type=Path, default=keys / "DECISIVE_PACKET_ADMIN.csv")
    parser.add_argument("--ratings", type=Path, default=package / "DECISIVE_PACKET_RATINGS.csv")
    parser.add_argument("--bundle-key", type=Path, default=keys / "T1_BUNDLE_KEY.csv")
    parser.add_argument("--out", type=Path, default=keys / "DECISIVE_BRANCH_REPORT.md")
    args = parser.parse_args()
    ratings = remap_bundle_rows(
        read_csv(args.ratings), args.bundle_key, scorer_id_field="rating_id"
    )
    result = score(
        read_csv(args.admin),
        ratings,
    )
    report = f"""# Decisive Construct Branch Report

`BRANCH_VERDICT = {result['branch_verdict']}`

This packet selects a diagnostic branch; it is not A-prime validation.

- Contested Label-B decisions: {result['contested_label_b_decided']}/24.
- Qwen matches to Label B: {result['judge_matches_label_b']}.
- Demucs matches to Label B: {result['demucs_matches_label_b']}.
- Label-A/Label-B disagreement: {result['label_a_b_disagreement_rate']}.
- Obvious-control matches: {result['control_matches']}/{result['control_decided']}.
- Real ratings complete: {str(result['real_ratings_complete']).lower()}.

```json
{json.dumps(result, indent=2, sort_keys=True)}
```
"""
    args.out.write_text(report, encoding="utf-8")
    print(result["branch_verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
