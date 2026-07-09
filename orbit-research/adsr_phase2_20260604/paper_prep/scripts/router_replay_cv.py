#!/usr/bin/env python3
"""Cross-validated router replay from existing prompt-level policy rows."""

from __future__ import annotations

import csv
import random
from pathlib import Path


ROOT = Path.cwd()
PAPER = ROOT / "paper_prep"
IN = PAPER / "router_replay" / "ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv"
OUTDIR = PAPER / "router_replay"


def read_rows() -> list[dict[str, object]]:
    with IN.open(newline="") as handle:
        rows = []
        for r in csv.DictReader(handle):
            row = dict(r)
            row["requested_vocal"] = int(row["requested_vocal"])
            row["baseline_p"] = float(row["baseline_p"])
            row["recondition_p"] = float(row["recondition_p"])
            rows.append(row)
        return rows


def success_prob(p: float, budget: int) -> float:
    return 1 - (1 - p) ** budget


def eval_policy(rows: list[dict[str, object]], policy: str, budget: int = 8, threshold: float | None = None,
                vocal_threshold: float | None = None, instr_threshold: float | None = None) -> list[float]:
    out = []
    for row in rows:
        base = float(row["baseline_p"])
        recon = float(row["recondition_p"])
        regime = str(row.get("n2_regime", ""))
        if policy == "always_reseed":
            p = base
        elif policy == "always_recondition":
            p = recon
        elif policy == "oracle_upper_bound":
            p = max(base, recon)
        elif policy == "threshold":
            p = recon if base <= float(threshold) else base
        elif policy == "direction_threshold":
            t = vocal_threshold if int(row["requested_vocal"]) == 1 else instr_threshold
            p = recon if base <= float(t) else base
        elif policy == "n2_low_or_rare_prior":
            p = recon if regime in {"rare_le_1_in_16", "low_1_in_16_to_1_in_4"} else base
        elif policy == "n2_rare_prior":
            p = recon if regime == "rare_le_1_in_16" else base
        elif policy == "direction_aware_vocal_rare":
            p = recon if int(row["requested_vocal"]) == 1 and base <= 1 / 16 else base
        else:
            raise ValueError(policy)
        out.append(success_prob(p, budget))
    return out


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def best_threshold(rows: list[dict[str, object]], grid: list[float]) -> float:
    return max(grid, key=lambda t: mean(eval_policy(rows, "threshold", threshold=t)))


def best_direction_threshold(rows: list[dict[str, object]], grid: list[float]) -> tuple[float, float]:
    best = None
    for vt in grid:
        for it in grid:
            score = mean(eval_policy(rows, "direction_threshold", vocal_threshold=vt, instr_threshold=it))
            if best is None or score > best[0]:
                best = (score, vt, it)
    assert best is not None
    return best[1], best[2]


def bootstrap_ci(values: list[float], rng: random.Random, reps: int = 5000) -> tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    draws = []
    n = len(values)
    for _ in range(reps):
        draws.append(mean([values[rng.randrange(n)] for _ in range(n)]))
    draws.sort()
    return draws[int(0.025 * reps)], draws[int(0.975 * reps)]


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    grid = [0.0, 1 / 256, 1 / 128, 1 / 64, 1 / 32, 1 / 16, 1 / 8, 1 / 4, 1 / 2]
    folds = 5
    sorted_rows = sorted(rows, key=lambda r: str(r["prompt_id"]))
    fold_rows = []
    prompt_policy_values: dict[str, dict[str, float]] = {}

    for fold in range(folds):
        test = [r for i, r in enumerate(sorted_rows) if i % folds == fold]
        train = [r for i, r in enumerate(sorted_rows) if i % folds != fold]
        t = best_threshold(train, grid)
        vt, it = best_direction_threshold(train, grid)
        fold_rows.append(
            {
                "fold": fold,
                "train_prompts": len(train),
                "test_prompts": len(test),
                "selected_threshold": t,
                "selected_vocal_threshold": vt,
                "selected_instr_threshold": it,
                "cv_threshold_clean": mean(eval_policy(test, "threshold", threshold=t)),
                "cv_direction_threshold_clean": mean(
                    eval_policy(test, "direction_threshold", vocal_threshold=vt, instr_threshold=it)
                ),
                "always_reseed_clean": mean(eval_policy(test, "always_reseed")),
                "always_recondition_clean": mean(eval_policy(test, "always_recondition")),
                "n2_low_or_rare_prior_clean": mean(eval_policy(test, "n2_low_or_rare_prior")),
                "direction_aware_vocal_rare_clean": mean(eval_policy(test, "direction_aware_vocal_rare")),
                "oracle_upper_bound_clean": mean(eval_policy(test, "oracle_upper_bound")),
            }
        )
        cv_threshold_vals = eval_policy(test, "threshold", threshold=t)
        cv_direction_vals = eval_policy(test, "direction_threshold", vocal_threshold=vt, instr_threshold=it)
        for row, cv_t, cv_d in zip(test, cv_threshold_vals, cv_direction_vals):
            pid = str(row["prompt_id"])
            prompt_policy_values[pid] = {
                "cv_threshold": cv_t,
                "cv_direction_threshold": cv_d,
                "always_reseed": eval_policy([row], "always_reseed")[0],
                "always_recondition": eval_policy([row], "always_recondition")[0],
                "n2_low_or_rare_prior": eval_policy([row], "n2_low_or_rare_prior")[0],
                "direction_aware_vocal_rare": eval_policy([row], "direction_aware_vocal_rare")[0],
                "oracle_upper_bound": eval_policy([row], "oracle_upper_bound")[0],
            }

    policy_rows = []
    for policy in [
        "always_reseed",
        "always_recondition",
        "cv_threshold",
        "cv_direction_threshold",
        "n2_low_or_rare_prior",
        "direction_aware_vocal_rare",
        "oracle_upper_bound",
    ]:
        vals = [prompt_policy_values[str(r["prompt_id"])][policy] for r in sorted_rows]
        base = [prompt_policy_values[str(r["prompt_id"])]["always_recondition"] for r in sorted_rows]
        diffs = [v - b for v, b in zip(vals, base)]
        lo, hi = bootstrap_ci(vals, random.Random(20260708))
        dlo, dhi = bootstrap_ci(diffs, random.Random(20260709))
        policy_rows.append(
            {
                "policy": policy,
                "prompts": len(vals),
                "expected_clean_outputs_per_prompt": mean(vals),
                "final_violation_rate": 1 - mean(vals),
                "bootstrap_ci_low": lo,
                "bootstrap_ci_high": hi,
                "delta_vs_always_recondition": mean(diffs),
                "delta_ci_low": dlo,
                "delta_ci_high": dhi,
            }
        )

    fold_path = OUTDIR / "ROUTER_REPLAY_CV_FOLDS.csv"
    with fold_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fold_rows[0]))
        writer.writeheader()
        writer.writerows(fold_rows)

    result_path = OUTDIR / "ROUTER_REPLAY_CV_RESULTS.csv"
    with result_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(policy_rows[0]))
        writer.writeheader()
        writer.writerows(policy_rows)

    best_non_oracle = max([r for r in policy_rows if r["policy"] != "oracle_upper_bound"], key=lambda r: r["expected_clean_outputs_per_prompt"])
    if (
        best_non_oracle["policy"] not in {"always_recondition", "always_reseed"}
        and best_non_oracle["delta_vs_always_recondition"] >= 0.01
        and best_non_oracle["delta_ci_low"] > 0
    ):
        final_claim = "SUPPORTED"
    elif best_non_oracle["policy"] == "always_recondition" or best_non_oracle["delta_vs_always_recondition"] < 0.01:
        final_claim = "REDUCED"
    else:
        final_claim = "REMOVED"

    lines = "\n".join(
        "| {policy} | {expected_clean_outputs_per_prompt:.6f} | [{bootstrap_ci_low:.6f}, {bootstrap_ci_high:.6f}] | {delta_vs_always_recondition:.6f} | [{delta_ci_low:.6f}, {delta_ci_high:.6f}] |".format(**r)
        for r in sorted(policy_rows, key=lambda r: r["expected_clean_outputs_per_prompt"], reverse=True)
    )
    report = f"""# Router Replay Cross-Validation Report

Generated: 2026-07-08

ROUTER_CV_STATUS = COMPLETE

ROUTER_FINAL_CLAIM = {final_claim}

## Inputs

- Prompt policy rows: `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv`
- Script: `paper_prep/scripts/router_replay_cv.py`

## Outputs

- Fold selections: `paper_prep/router_replay/ROUTER_REPLAY_CV_FOLDS.csv`
- Cross-validated results: `paper_prep/router_replay/ROUTER_REPLAY_CV_RESULTS.csv`

## Method

Prompts were split into five deterministic folds. Rare-threshold and
direction-aware thresholds were selected on train folds only and evaluated on
held-out prompts. Fixed policies and the oracle upper bound were evaluated on
the same held-out prompts for comparison. Bootstrap confidence intervals resample
prompts, not ordered calls.

## Results

| Policy | Expected clean / prompt | 95% CI | Delta vs always-recondition | Delta 95% CI |
|---|---:|---:|---:|---:|
{lines}

## Conclusion

The router claim remains **{final_claim}**. A deployable router is not supported
unless a held-out policy beats always-recondition by a nontrivial margin with a
positive prompt-bootstrap interval. This run should be cited as a reduced or
negative replay result if included.
"""
    (OUTDIR / "ROUTER_REPLAY_CV_REPORT.md").write_text(report, encoding="utf-8")
    print(result_path)
    print(OUTDIR / "ROUTER_REPLAY_CV_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
