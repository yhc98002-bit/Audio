#!/usr/bin/env python3
"""CPU-only counterfactual router replay from existing retry/intervention ledgers."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
ATLAS = ROOT / "batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test"
OUTDIR = PAPER / "router_replay"


def read_jsonl(pattern: str):
    for path in sorted(ATLAS.glob(pattern)):
        with path.open() as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def rates(pattern: str) -> dict[str, dict]:
    by_key = {}
    for r in read_jsonl(pattern):
        key = (r.get("prompt_id"), r.get("condition"), r.get("seed_idx"))
        by_key.setdefault(key, r)
    by_prompt = defaultdict(list)
    meta = {}
    for r in by_key.values():
        pid = r["prompt_id"]
        by_prompt[pid].append(int(r["type_correct"]))
        meta[pid] = {"requested_vocal": int(r.get("requested_vocal", 0))}
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


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    baseline = rates("ledgers/bon256_w*.jsonl")
    v3 = rates("ledgers/v3_vocal_w*.jsonl")
    istrong = rates("ledgers/istrong_instr_w*.jsonl")
    prompts = sorted(baseline)
    prompt_rows = []
    for pid in prompts:
        b = baseline[pid]
        p_base = b["p"]
        p_recond = v3[pid]["p"] if b["requested_vocal"] == 1 else istrong[pid]["p"]
        regime = (
            "rare_le_1_in_16"
            if p_base <= 1 / 16
            else "retry_recoverable_gt_1_in_16"
        )
        p_router = p_recond if regime == "rare_le_1_in_16" else p_base
        prompt_rows.append(
            {
                "prompt_id": pid,
                "requested_vocal": b["requested_vocal"],
                "baseline_n": b["n"],
                "baseline_clean": b["clean"],
                "baseline_p": p_base,
                "recondition_p": p_recond,
                "regime": regime,
                "router_policy": "recondition" if regime == "rare_le_1_in_16" else "reseed",
                "router_p": p_router,
            }
        )

    prompt_path = OUTDIR / "ROUTER_REPLAY_PROMPT_POLICIES.csv"
    with prompt_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(prompt_rows[0]))
        writer.writeheader()
        writer.writerows(prompt_rows)

    rows = []
    for budget in [1, 2, 4, 8]:
        for policy in ["always_reseed", "always_recondition", "rare_router"]:
            probs = []
            for r in prompt_rows:
                if policy == "always_reseed":
                    p = r["baseline_p"]
                elif policy == "always_recondition":
                    p = r["recondition_p"]
                else:
                    p = r["router_p"]
                probs.append(success_prob(float(p), budget))
            clean_yield = sum(probs) / len(probs)
            rows.append(
                {
                    "budget_draws": budget,
                    "policy": policy,
                    "prompts": len(probs),
                    "expected_clean_outputs_per_prompt": clean_yield,
                    "final_violation_rate": 1.0 - clean_yield,
                    "clean_yield_per_compute_draw": clean_yield / budget,
                }
            )

    result_path = OUTDIR / "ROUTER_REPLAY_RESULTS.csv"
    with result_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    rare_count = sum(1 for r in prompt_rows if r["regime"] == "rare_le_1_in_16")
    budget8 = {r["policy"]: r for r in rows if r["budget_draws"] == 8}
    router8 = budget8["rare_router"]
    reseed8 = budget8["always_reseed"]
    recond8 = budget8["always_recondition"]
    go = (
        router8["expected_clean_outputs_per_prompt"] > reseed8["expected_clean_outputs_per_prompt"]
        and router8["expected_clean_outputs_per_prompt"] >= recond8["expected_clean_outputs_per_prompt"] - 0.01
    )
    report = f"""# Router Replay Report

Generated: 2026-07-07

Inputs:

- Baseline ledgers: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/bon256_w*.jsonl`
- Vocal re-conditioning ledgers: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/v3_vocal_w*.jsonl`
- Instrumental re-conditioning ledgers: `batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers/istrong_instr_w*.jsonl`

Outputs:

- Results: `paper_prep/router_replay/ROUTER_REPLAY_RESULTS.csv`
- Prompt policies: `paper_prep/router_replay/ROUTER_REPLAY_PROMPT_POLICIES.csv`

## Replay Rule

Classify a prompt as rare-regime if its baseline clean rate is <= 1/16.
The router re-conditions rare-regime prompts and otherwise re-seeds. Fixed
baselines are always-reseed and always-recondition at the same draw budgets.

## Prompt Mix

- Prompts: {len(prompt_rows)}
- Rare-regime prompts by replay rule: {rare_count}
- Non-rare prompts by replay rule: {len(prompt_rows) - rare_count}

## Equal-Compute Results

| Budget | Policy | Expected clean / prompt | Final violation rate | Clean yield / draw |
|---:|---|---:|---:|---:|
"""
    for r in rows:
        report += (
            f"| {r['budget_draws']} | `{r['policy']}` | "
            f"{r['expected_clean_outputs_per_prompt']:.6f} | "
            f"{r['final_violation_rate']:.6f} | "
            f"{r['clean_yield_per_compute_draw']:.6f} |\n"
        )
    report += f"""
## Recommendation

GO/NO-GO for live router confirmation: **{'GO' if go else 'NO-GO'}**.

At budget 8, rare-router expected clean/prompt is
{router8['expected_clean_outputs_per_prompt']:.6f} versus
{reseed8['expected_clean_outputs_per_prompt']:.6f} for always-reseed and
{recond8['expected_clean_outputs_per_prompt']:.6f} for always-recondition.

Wording constraint: this is a counterfactual replay from existing ledgers, not
a live router confirmation. It can motivate a live confirmation run, but it
does not replace one.
"""
    (OUTDIR / "ROUTER_REPLAY_REPORT.md").write_text(report)
    print(result_path)
    print(OUTDIR / "ROUTER_REPLAY_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

