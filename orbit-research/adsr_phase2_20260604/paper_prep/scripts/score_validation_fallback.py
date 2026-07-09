#!/usr/bin/env python3
"""Score A-prime and B-prime fallback judge outputs without declaring validation pass."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


# `paper_prep` is a symlink into `orbit-research/...`; anchor on the workspace cwd.
ROOT = Path.cwd()
PAPER = ROOT / "paper_prep"
APRIME = PAPER / "validation_A_prime"
BPRIME = PAPER / "validation_B_prime"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def exact_binom_p_less_equal(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return float("nan")
    return sum(math.comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k + 1))


def score_aprime() -> dict[str, object]:
    manifest = read_csv(APRIME / "A_PRIME_MANIFEST.csv")
    judgeable = read_csv(APRIME / "A_PRIME_JUDGEABLE_MANIFEST.csv")
    raw = read_jsonl(APRIME / "A_PRIME_RAW_RESPONSES.jsonl")
    by_path = {r["clip_path"]: r for r in raw}
    full_by_path = {r["clip_path"]: r for r in manifest}
    matrix_rows = []
    counts = Counter()
    set_counts: dict[str, Counter] = defaultdict(Counter)
    disagreements = []

    for row in manifest:
        clip_path = row["clip_path"]
        res = by_path.get(clip_path)
        majority = res.get("majority", "") if res else ""
        demucs = row.get("expected_demucs_label", "")
        demucs_label = "yes" if demucs == "1" else "no" if demucs == "0" else ""
        exists = row.get("exists", "")
        status = "missing_audio" if exists != "true" else "not_scored"
        if res:
            status = "scored"
            if majority in {"yes", "no"} and demucs_label:
                status = "match" if majority == demucs_label else "disagree"
                if status == "disagree":
                    disagreements.append(row["clip_id"])
        mrow = {
            "clip_id": row["clip_id"],
            "clip_path": clip_path,
            "set_name": row.get("set_name", ""),
            "expected_demucs_label": demucs_label,
            "judge_majority": majority,
            "vote_counts": json.dumps(res.get("vote_counts", {}), sort_keys=True) if res else "",
            "status": status,
        }
        matrix_rows.append(mrow)
        counts[status] += 1
        set_counts[row.get("set_name", "")][status] += 1

    out_matrix = APRIME / "A_PRIME_AGREEMENT_MATRIX.csv"
    with out_matrix.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(matrix_rows[0]))
        writer.writeheader()
        writer.writerows(matrix_rows)

    def subset(predicate):
        return [r for r in matrix_rows if predicate(full_by_path.get(r["clip_path"], {}), r)]

    rare = subset(lambda src, r: src.get("set_name", "").startswith("rare"))
    rare_scored = [r for r in rare if r["judge_majority"] in {"yes", "no"}]
    rare_confirm = [
        r for r in rare_scored if r["judge_majority"] == ("yes" if full_by_path[r["clip_path"]].get("requested_vocal") == "1" else "no")
    ]
    det_dis = subset(lambda src, r: "disagreement" in src.get("set_name", ""))
    det_dis_scored = [r for r in det_dis if r["status"] in {"match", "disagree"}]
    det_dis_match = [r for r in det_dis_scored if r["status"] == "match"]
    agreement = subset(
        lambda src, r: (
            "agreement" in src.get("set_name", "")
            and "disagreement" not in src.get("set_name", "")
        )
    )
    agreement_scored = [r for r in agreement if r["status"] in {"match", "disagree"}]
    agreement_fail = [r for r in agreement_scored if r["status"] == "disagree"]
    strat = subset(lambda src, r: src.get("set_name") == "stratified_random_500")
    strat_scored = [r for r in strat if r["status"] in {"match", "disagree"}]
    strat_dis = [r for r in strat_scored if r["status"] == "disagree"]

    rare_rate = len(rare_confirm) / len(rare_scored) if rare_scored else float("nan")
    det_rate = len(det_dis_match) / len(det_dis_scored) if det_dis_scored else float("nan")
    agreement_fail_count = len(agreement_fail)
    strat_error = len(strat_dis) / len(strat_scored) if strat_scored else float("nan")
    global_bound = 1.96 * math.sqrt(strat_error * (1 - strat_error) / len(strat_scored)) if strat_scored else float("nan")

    complete = len(raw) >= len(judgeable)
    criteria_pass = (
        complete
        and len(rare_scored) > 0
        and rare_rate >= 0.90
        and len(det_dis_scored) >= 112
        and det_rate >= 0.70
        and len(agreement_scored) >= 30
        and agreement_fail_count <= 2
        and len(strat_scored) >= 500
    )
    status = "PASS" if criteria_pass else ("FALLBACK_READY" if complete else "BLOCKED_WITH_EXACT_CAUSE")
    missing = [r for r in manifest if r.get("exists") != "true"]

    set_lines = "\n".join(
        f"- `{name}`: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items()))
        for name, c in sorted(set_counts.items())
    )
    report = f"""# A-prime Gate Report

Generated: 2026-07-07

A_PRIME_STATUS = {status}

Important: Qwen smoke v2 did not pass. These rows are fallback evidence only
unless a scientifically acceptable replacement validation is approved.

## Inputs / Outputs

- Manifest: `paper_prep/validation_A_prime/A_PRIME_MANIFEST.csv`
- Judgeable manifest: `paper_prep/validation_A_prime/A_PRIME_JUDGEABLE_MANIFEST.csv`
- Raw responses: `paper_prep/validation_A_prime/A_PRIME_RAW_RESPONSES.jsonl`
- Agreement matrix: `paper_prep/validation_A_prime/A_PRIME_AGREEMENT_MATRIX.csv`

## Coverage

- Full manifest rows: {len(manifest)}
- Judgeable rows: {len(judgeable)}
- Scored rows: {len(raw)}
- Missing/unjudgeable manifest rows: {len(missing)}

## Gate Criteria

- Rare-basin confirmation: {len(rare_confirm)}/{len(rare_scored)} = {rare_rate:.6f}; required >= 0.90.
- Demucs match on detector-disagreement cases: {len(det_dis_match)}/{len(det_dis_scored)} = {det_rate:.6f}; required >= 70% on 112 cases.
- Agreement spotcheck failures: {agreement_fail_count}/{len(agreement_scored)}; required <= 2/30.
- Stratified 500 disagreement rate versus Demucs: {len(strat_dis)}/{len(strat_scored)} = {strat_error:.6f}; approximate 95% half-width {global_bound:.6f}.

## Set-Level Counts

{set_lines}

## Interpretation

Do not cite A-prime as passed unless `A_PRIME_STATUS = PASS`. If status is
`FALLBACK_READY`, the scored package can support a PI/human adjudication or a
reduced automatic-label caveat, but it is not a validated A-prime pass because
the model smoke did not clear and/or required sample coverage is incomplete.
"""
    (APRIME / "A_PRIME_GATE_REPORT.md").write_text(report)
    return {"status": status, "scored": len(raw), "manifest": len(manifest), "missing": len(missing)}


def chosen_arm(manifest_row: dict[str, str], order: str, answer: str) -> str:
    if answer not in {"a", "b"}:
        return answer
    if order == "ab":
        return manifest_row["A_is"] if answer == "a" else manifest_row["B_is"]
    if order == "ba":
        return manifest_row["B_is"] if answer == "a" else manifest_row["A_is"]
    return ""


def score_bprime() -> dict[str, object]:
    manifest = read_csv(BPRIME / "B_PRIME_MANIFEST.csv")
    raw = read_jsonl(BPRIME / "B_PRIME_RAW_RESPONSES.jsonl")
    by_pair = {r["pair_id"]: r for r in manifest}
    question_rows = []
    pair_votes: dict[str, list[str]] = defaultdict(list)
    order_counts: dict[str, Counter] = defaultdict(Counter)

    for row in raw:
        pair_id = row["pair_id"]
        m = by_pair.get(pair_id)
        if not m:
            continue
        order = row.get("order", "")
        for q, answer in row.get("parsed", {}).items():
            arm = chosen_arm(m, order, answer)
            pref = "method" if arm == "arm6" else "baseline" if arm in {"arm1", "arm4"} else arm
            question_rows.append(
                {
                    "pair_id": pair_id,
                    "contrast": m.get("contrast", ""),
                    "group": m.get("group", ""),
                    "order": order,
                    "question": q,
                    "answer": answer,
                    "chosen_arm": arm,
                    "preference": pref,
                }
            )
            if q == "q1":
                pair_votes[pair_id].append(pref)
                order_counts[order][pref] += 1

    decided = [r for r in question_rows if r["question"] == "q1" and r["preference"] in {"method", "baseline"}]
    method = [r for r in decided if r["preference"] == "method"]
    ties = [r for r in question_rows if r["question"] == "q1" and r["preference"] == "tie"]
    refusals = [r for r in question_rows if r["question"] == "q1" and r["preference"] not in {"method", "baseline", "tie"}]
    method_rate = len(method) / len(decided) if decided else float("nan")
    p_less = exact_binom_p_less_equal(len(method), len(decided)) if decided else float("nan")

    by_contrast: dict[str, Counter] = defaultdict(Counter)
    for r in decided:
        by_contrast[r["contrast"]][r["preference"]] += 1

    order_report = BPRIME / "B_PRIME_ORDER_BIAS_REPORT.md"
    order_lines = "\n".join(
        f"- `{order}`: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items()))
        for order, c in sorted(order_counts.items())
    )
    order_report.write_text(
        f"""# B-prime Order Bias Report

Generated: 2026-07-07

Inputs:

- `paper_prep/validation_B_prime/B_PRIME_MANIFEST.csv`
- `paper_prep/validation_B_prime/B_PRIME_RAW_RESPONSES.jsonl`

Q1 preference counts by presentation order:

{order_lines}

Interpretation: this is fallback-model evidence only because the model smoke did
not pass. Position-bias diagnostics are recorded for later PI/human calibration.
"""
    )

    contrast_lines = "\n".join(
        f"- `{contrast}`: method={c['method']}, baseline={c['baseline']}"
        for contrast, c in sorted(by_contrast.items())
    )
    status = "FALLBACK_READY" if len(raw) >= len(manifest) * 2 else "BLOCKED_WITH_EXACT_CAUSE"
    pass_shape = method_rate >= 0.40 and p_less >= 0.05 if decided else False
    if status == "FALLBACK_READY" and not pass_shape:
        status = "FAIL"
    report = f"""# B-prime Gate Report

Generated: 2026-07-07

B_PRIME_STATUS = {status}

Important: Qwen smoke v2 did not pass. These rows are fallback evidence only
unless a scientifically acceptable replacement validation is approved.

## Inputs / Outputs

- Manifest: `paper_prep/validation_B_prime/B_PRIME_MANIFEST.csv`
- Raw responses: `paper_prep/validation_B_prime/B_PRIME_RAW_RESPONSES.jsonl`
- Order-bias report: `paper_prep/validation_B_prime/B_PRIME_ORDER_BIAS_REPORT.md`

## Coverage

- Pair rows: {len(manifest)}
- Expected ordered calls: {len(manifest) * 2}
- Completed ordered calls: {len(raw)}
- Q1 decided calls: {len(decided)}
- Q1 ties: {len(ties)}
- Q1 refusals/unparsed: {len(refusals)}

## Gate Shape

- Method preferred among decided Q1 calls: {len(method)}/{len(decided)} = {method_rate:.6f}; frozen criterion >= 0.40.
- Exact one-sided binomial P[X <= observed | n, p=0.5]: {p_less:.6f}; criterion not significantly below 50% at 5%.

By contrast:

{contrast_lines}

## Interpretation

Do not claim B-prime passed unless `B_PRIME_STATUS = PASS`. This report can
support reduced wording only after the failed-smoke judge limitation is stated.
Forbidden wording remains: "proved no loss" and unqualified "no quality degradation".
"""
    (BPRIME / "B_PRIME_GATE_REPORT.md").write_text(report)
    return {"status": status, "calls": len(raw), "pairs": len(manifest), "method_rate": method_rate, "p_less": p_less}


def main() -> int:
    a = score_aprime()
    b = score_bprime()
    print(json.dumps({"a_prime": a, "b_prime": b}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
