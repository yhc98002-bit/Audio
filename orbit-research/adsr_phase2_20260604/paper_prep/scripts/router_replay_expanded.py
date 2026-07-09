#!/usr/bin/env python3
"""Expanded CPU-only router replay variants from frozen retry ledgers."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


# `paper_prep` is a symlink into `orbit-research/...`; anchor on the workspace cwd.
ROOT = Path.cwd()
PAPER = ROOT / "paper_prep"
ATLAS = ROOT / "batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test"
N2 = PAPER / "population_retry_20260707" / "full128_prompt_clean_rates.csv"
OUTDIR = PAPER / "router_replay"


def read_jsonl(pattern: str):
    for path in sorted((ATLAS / "ledgers").glob(pattern)):
        with path.open() as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def rates(pattern: str) -> dict[str, dict[str, float]]:
    by_key = {}
    for row in read_jsonl(pattern):
        key = (row.get("prompt_id"), row.get("condition"), row.get("seed_idx"))
        by_key.setdefault(key, row)
    by_prompt: dict[str, list[int]] = defaultdict(list)
    meta: dict[str, dict[str, int]] = {}
    for row in by_key.values():
        pid = row["prompt_id"]
        by_prompt[pid].append(int(row["type_correct"]))
        meta[pid] = {"requested_vocal": int(row.get("requested_vocal", 0))}
    return {
        pid: {
            "n": len(vals),
            "clean": sum(vals),
            "p": sum(vals) / len(vals),
            **meta[pid],
        }
        for pid, vals in by_prompt.items()
    }


def success_prob(p: float, budget: int) -> float:
    return 1.0 - (1.0 - p) ** budget


def read_n2_regimes() -> dict[str, str]:
    if not N2.exists():
        return {}
    with N2.open(newline="") as f:
        return {r["prompt_id"]: r.get("regime", "") for r in csv.DictReader(f)}


def policy_p(row: dict[str, object], policy: str) -> float:
    base = float(row["baseline_p"])
    recond = float(row["recondition_p"])
    rv = int(row["requested_vocal"])
    regime = str(row.get("n2_regime", ""))
    if policy == "always_reseed" or policy == "bon_independent_reseed":
        return base
    if policy == "always_recondition":
        return recond
    if policy == "oracle_best_of_reseed_or_recondition":
        return max(base, recond)
    if policy.startswith("threshold_le_"):
        threshold = float(policy.rsplit("_", 1)[-1])
        return recond if base <= threshold else base
    if policy == "direction_aware_vocal_rare":
        return recond if rv == 1 and base <= 1 / 16 else base
    if policy == "direction_aware_gain_prior":
        # Exploratory upper-bound-like rule using observed sign of re-conditioning gain.
        return recond if recond >= base else base
    if policy == "n2_low_or_rare_prior":
        return recond if regime in {"rare_le_1_in_16", "low_1_in_16_to_1_in_4"} else base
    if policy == "n2_rare_prior":
        return recond if regime == "rare_le_1_in_16" else base
    raise ValueError(policy)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    baseline = rates("bon256_w*.jsonl")
    v3 = rates("v3_vocal_w*.jsonl")
    istrong = rates("istrong_instr_w*.jsonl")
    regimes = read_n2_regimes()
    prompts = sorted(baseline)
    prompt_rows: list[dict[str, object]] = []
    for pid in prompts:
        b = baseline[pid]
        p_recond = v3[pid]["p"] if int(b["requested_vocal"]) == 1 else istrong[pid]["p"]
        prompt_rows.append(
            {
                "prompt_id": pid,
                "requested_vocal": int(b["requested_vocal"]),
                "baseline_n": int(b["n"]),
                "baseline_clean": int(b["clean"]),
                "baseline_p": float(b["p"]),
                "recondition_p": float(p_recond),
                "recondition_delta": float(p_recond) - float(b["p"]),
                "n2_regime": regimes.get(pid, ""),
            }
        )

    prompt_path = OUTDIR / "ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv"
    with prompt_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(prompt_rows[0]))
        writer.writeheader()
        writer.writerows(prompt_rows)

    thresholds = [0.0, 1 / 256, 1 / 128, 1 / 64, 1 / 32, 1 / 16, 1 / 8, 1 / 4, 1 / 2]
    policies = [
        "always_reseed",
        "bon_independent_reseed",
        "always_recondition",
        "direction_aware_vocal_rare",
        "n2_rare_prior",
        "n2_low_or_rare_prior",
        "direction_aware_gain_prior",
        "oracle_best_of_reseed_or_recondition",
    ] + [f"threshold_le_{t:.8f}" for t in thresholds]

    rows = []
    for budget in [1, 2, 4, 8, 16]:
        for policy in policies:
            probs = [success_prob(policy_p(r, policy), budget) for r in prompt_rows]
            clean = sum(probs) / len(probs)
            policy_class = "fixed"
            if policy.startswith("threshold"):
                policy_class = "threshold_sweep"
            if policy in {"direction_aware_gain_prior", "oracle_best_of_reseed_or_recondition"}:
                policy_class = "oracle_or_outcome_informed"
            if policy.startswith("n2_") or policy == "direction_aware_vocal_rare":
                policy_class = "exploratory_rule"
            rows.append(
                {
                    "budget_draws": budget,
                    "policy": policy,
                    "policy_class": policy_class,
                    "prompts": len(probs),
                    "expected_clean_outputs_per_prompt": clean,
                    "final_violation_rate": 1.0 - clean,
                    "clean_yield_per_compute_draw": clean / budget,
                }
            )

    result_path = OUTDIR / "ROUTER_REPLAY_EXPANDED_RESULTS.csv"
    with result_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def row_for(policy: str, budget: int = 8):
        return next(r for r in rows if r["policy"] == policy and r["budget_draws"] == budget)

    b8 = [r for r in rows if r["budget_draws"] == 8]
    best_non_oracle = max(
        [r for r in b8 if r["policy_class"] != "oracle_or_outcome_informed"],
        key=lambda r: r["expected_clean_outputs_per_prompt"],
    )
    always_recond = row_for("always_recondition")
    always_reseed = row_for("always_reseed")
    oracle = row_for("oracle_best_of_reseed_or_recondition")
    # A replay threshold sweep can be useful scientifically, but it is not a
    # deployable live-router claim unless it beats the strongest fixed policy by
    # a meaningful margin without hindsight/oracle information.
    improvement = (
        best_non_oracle["expected_clean_outputs_per_prompt"]
        - always_recond["expected_clean_outputs_per_prompt"]
    )
    supported = (
        best_non_oracle["policy"] not in {"always_recondition", "always_reseed", "bon_independent_reseed"}
        and best_non_oracle["policy_class"] == "exploratory_rule"
        and improvement >= 0.01
    )
    final_claim = "supported" if supported else "reduced to negative/offline replay result"

    top_lines = "\n".join(
        "| {policy} | {policy_class} | {expected_clean_outputs_per_prompt:.6f} | {final_violation_rate:.6f} | {clean_yield_per_compute_draw:.6f} |".format(
            **r
        )
        for r in sorted(b8, key=lambda r: r["expected_clean_outputs_per_prompt"], reverse=True)[:10]
    )
    report = f"""# Router Replay Expanded Report

Generated: 2026-07-07

Inputs:

- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/bon256_w*.jsonl`
- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/v3_vocal_w*.jsonl`
- `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/istrong_instr_w*.jsonl`
- `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`

Outputs:

- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_RESULTS.csv`
- `paper_prep/router_replay/ROUTER_REPLAY_EXPANDED_PROMPT_POLICIES.csv`

## Expanded Variants

The replay tested fixed policies, rare-threshold sweeps, direction-aware rules,
N2-regime-prior rules, and an outcome-informed oracle upper bound. Outcome-informed
rows are diagnostic only and are not a deployable router claim.

## Budget 8 Top Policies

| Policy | Class | Expected clean / prompt | Final violation rate | Clean yield / draw |
|---|---|---:|---:|---:|
{top_lines}

## Fixed Baselines at Budget 8

- Always reseed: {always_reseed['expected_clean_outputs_per_prompt']:.6f}
- Always recondition: {always_recond['expected_clean_outputs_per_prompt']:.6f}
- Oracle best of reseed/recondition: {oracle['expected_clean_outputs_per_prompt']:.6f}
- Best non-oracle policy: `{best_non_oracle['policy']}` = {best_non_oracle['expected_clean_outputs_per_prompt']:.6f}
- Best non-oracle improvement over always-recondition: {improvement:.6f}

## Conclusion

Router claim: **{final_claim}**.

The simple and expanded non-oracle routers do not establish a deployable router
advantage over the strongest fixed policy in this replay. The paper-safe use is
as a negative/reduced result: existing ledgers show that a naive rare-regime
router is insufficient, and live router confirmation is not justified without a
stronger policy or new evidence.
"""
    (OUTDIR / "ROUTER_REPLAY_EXPANDED_REPORT.md").write_text(report)
    print(result_path)
    print(OUTDIR / "ROUTER_REPLAY_EXPANDED_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
