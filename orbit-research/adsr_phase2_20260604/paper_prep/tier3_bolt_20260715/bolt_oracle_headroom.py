#!/usr/bin/env python3
"""Frozen static-program and tree-oracle analysis for the BOLT Gate-1 pilot."""

from __future__ import annotations

import csv
import itertools
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))

from bolt_core import CHECKPOINT_STEPS, read_jsonl, sha256_file  # noqa: E402


MANIFEST = OUT / "BOLT_PILOT_PROMPT_MANIFEST.jsonl"
ROOT_LEDGER = OUT / "BOLT_ROOT_TRAJECTORY_LEDGER.jsonl"
ACTION_LEDGER = OUT / "BOLT_ACTION_ATLAS_PILOT_LEDGER.jsonl"
GATE0 = OUT / "BOLT_GATE0_REPORT.md"
AUDIT = OUT / "BOLT_ACTION_ATLAS_PILOT_AUDIT.md"
STATIC_CSV = OUT / "BOLT_STATIC_PROGRAM_TABLE.csv"
ACTION_CSV = OUT / "BOLT_ORACLE_ACTION_TABLE.csv"
STRATUM_CSV = OUT / "BOLT_ORACLE_STRATUM_RESULTS.csv"
BOOTSTRAP_CSV = OUT / "BOLT_ORACLE_BOOTSTRAP.csv"
REPORT = OUT / "BOLT_ORACLE_HEADROOM_REPORT.md"
GATE1 = OUT / "BOLT_GATE1_REPORT.md"
BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 2026071503


@dataclass(frozen=True)
class Leaf:
    leaf_id: str
    root_index: int
    checkpoint: int
    action: str
    prefix_nfe: int
    edge_nfe: int
    cqs: int
    probability: float
    row: dict


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    value = np.asarray(list(values), dtype=np.float64)
    weight = np.asarray(list(weights), dtype=np.float64)
    if len(value) == 0 or weight.sum() <= 0:
        return math.nan
    return float(np.average(value, weights=weight))


def oracle_program_differs(static_leaf_ids: Iterable[str], oracle_leaf_ids: Iterable[str]) -> bool:
    """Apply the frozen prompt-level nonstatic-program definition exactly."""
    return frozenset(static_leaf_ids) != frozenset(oracle_leaf_ids)


def matched_cqs_compute_saving(static_cqs: int, static_cost: int, oracle_success_cost: int) -> float:
    """Conservative paired saving while preserving each static program success."""
    matched_cost = oracle_success_cost if static_cqs else static_cost
    return (static_cost - matched_cost) / static_cost


def option_probability(row: dict) -> float:
    if row.get("quality_floor_status") != "PASS" or not row.get("valid", True):
        return 0.0
    violation = float(row["calibrated_label_b_violation_probability"])
    return min(max(1.0 - violation, 0.0), 1.0 - 1e-12)


def build_indices() -> tuple[list[dict], dict, dict]:
    prompts = read_jsonl(MANIFEST)
    roots = {
        (str(row["prompt_id"]), int(row["root_index"])): row
        for row in read_jsonl(ROOT_LEDGER)
    }
    actions = {
        (str(row["prompt_id"]), int(row["root_index"]), int(row["checkpoint_step"]), str(row["action"])): row
        for row in read_jsonl(ACTION_LEDGER)
    }
    if len(prompts) != 48 or len(roots) != 96 or len(actions) != 1440:
        raise RuntimeError("oracle input cardinality mismatch")
    return prompts, roots, actions


def action_row(actions: dict, prompt_id: str, root: int, checkpoint: int, action: str) -> dict:
    return actions[(prompt_id, root, checkpoint, action)]


def static_programs(prompt: dict, roots: dict, actions: dict, standard_nfe: int) -> dict[str, dict]:
    prompt_id = str(prompt["prompt_id"])
    r0, r1 = roots[(prompt_id, 0)], roots[(prompt_id, 1)]

    def result(name: str, rows: list[dict], cost: int, leaf_ids: list[str]) -> dict:
        feasible = cost <= 2 * standard_nfe and bool(rows)
        return {
            "program": name,
            "cost": int(cost),
            "feasible": feasible,
            "completion": int(feasible),
            "cqs": int(feasible and any(int(row["cqs"]) for row in rows)),
            "quality_failures": sum(row.get("quality_floor_status") != "PASS" for row in rows),
            "leaf_ids": leaf_ids,
        }

    programs: dict[str, dict] = {}
    programs["two_base"] = result(
        "two_base", [r0, r1], 2 * standard_nfe, ["root0_base", "root1_base"]
    )
    conditioned = [action_row(actions, prompt_id, root, 6, "RESTART_CONDITIONED") for root in (0, 1)]
    programs["two_direction_conditioned"] = result(
        "two_direction_conditioned", conditioned,
        sum(int(row["action_nfe"]) for row in conditioned),
        ["root0_step6_RESTART_CONDITIONED", "root1_step6_RESTART_CONDITIONED"],
    )
    mixed = [r0, conditioned[1]]
    programs["one_base_plus_one_conditioned"] = result(
        "one_base_plus_one_conditioned", mixed,
        standard_nfe + int(conditioned[1]["action_nfe"]),
        ["root0_base", "root1_step6_RESTART_CONDITIONED"],
    )
    for checkpoint in CHECKPOINT_STEPS:
        for root_index in (0, 1):
            cont = action_row(actions, prompt_id, root_index, checkpoint, "CONTINUE")
            for branch_action, label in (("SWITCH_CONDITION", "continue_switch"), ("FORK_LATENT", "deterministic_fork")):
                branch = action_row(actions, prompt_id, root_index, checkpoint, branch_action)
                name = f"fixed_step{checkpoint}_{label}_root{root_index}"
                cost = int(cont["prefix_nfe"]) + int(cont["action_nfe"]) + int(branch["action_nfe"])
                programs[name] = result(
                    name, [cont, branch], cost,
                    [f"root{root_index}_base", f"root{root_index}_step{checkpoint}_{branch_action}"],
                )

    probe_high = bool(int(r0["corrected_evpd_decision"]))
    probe_nfe = int(r0["corrected_evpd_probe_nfe"])
    if probe_high:
        conditioned_after_abort = action_row(actions, prompt_id, 0, 12, "RESTART_CONDITIONED")
        programs["frozen_w2_two_slot"] = result(
            "frozen_w2_two_slot", [conditioned_after_abort],
            probe_nfe + int(conditioned_after_abort["action_nfe"]),
            ["root0_step12_RESTART_CONDITIONED"],
        )
        root1_cont = action_row(actions, prompt_id, 1, 18, "CONTINUE")
        root1_switch = action_row(actions, prompt_id, 1, 18, "SWITCH_CONDITION")
        rollover_cost = probe_nfe + standard_nfe + int(root1_switch["action_nfe"])
        programs["true_rollover_corrected_evpd"] = result(
            "true_rollover_corrected_evpd", [root1_cont, root1_switch], rollover_cost,
            ["root1_base", "root1_step18_SWITCH_CONDITION"],
        )
    else:
        programs["frozen_w2_two_slot"] = result(
            "frozen_w2_two_slot", [r0, r1], 2 * standard_nfe, ["root0_base", "root1_base"]
        )
        programs["true_rollover_corrected_evpd"] = result(
            "true_rollover_corrected_evpd", [r0, r1], 2 * standard_nfe, ["root0_base", "root1_base"]
        )
    return programs


def root_leaves(prompt_id: str, root_index: int, root: dict, actions: dict) -> list[Leaf]:
    leaves = [
        Leaf(
            f"root{root_index}_base", root_index, 30, "CONTINUE", int(root["transformer_forward_calls"]), 0,
            int(root["cqs"]), option_probability(root), root,
        )
    ]
    for checkpoint in CHECKPOINT_STEPS:
        for action in ("SWITCH_CONDITION", "FORK_LATENT", "RESTART_BASE", "RESTART_CONDITIONED"):
            row = action_row(actions, prompt_id, root_index, checkpoint, action)
            leaves.append(
                Leaf(
                    f"root{root_index}_step{checkpoint}_{action}", root_index, checkpoint, action,
                    int(row["prefix_nfe"]), int(row["action_nfe"]), int(row["cqs"]),
                    option_probability(row), row,
                )
            )
    return leaves


def subset_cost(leaves: list[Leaf], standard_nfe: int) -> int:
    if not leaves:
        return 0
    trunk = 0
    edges = 0
    for leaf in leaves:
        if leaf.action == "CONTINUE" and leaf.checkpoint == 30:
            trunk = max(trunk, standard_nfe)
        else:
            trunk = max(trunk, leaf.prefix_nfe)
            edges += leaf.edge_nfe
    return trunk + edges


def root_options(leaves: list[Leaf], standard_nfe: int, budget: int) -> dict[int, dict]:
    """Enumerate one root tree exactly, then retain its best option at each cost."""
    best: dict[int, dict] = {0: {"selected": [], "any_success": 0, "success_count": 0, "option": 0.0}}
    for mask in range(1, 1 << len(leaves)):
        selected = [leaf for index, leaf in enumerate(leaves) if mask & (1 << index)]
        cost = subset_cost(selected, standard_nfe)
        if cost > budget:
            continue
        successes = sum(leaf.cqs for leaf in selected)
        option = sum(-math.log1p(-leaf.probability) for leaf in selected)
        value = {
            "selected": [leaf.leaf_id for leaf in selected],
            "any_success": int(successes > 0),
            "success_count": successes,
            "option": option,
        }
        incumbent = best.get(cost)
        objective = (value["any_success"], value["success_count"], value["option"], -cost)
        incumbent_objective = (
            incumbent["any_success"], incumbent["success_count"], incumbent["option"], -cost
        ) if incumbent else None
        if incumbent is None or objective > incumbent_objective:
            best[cost] = value
    return best


def full_tree_oracle(prompt_id: str, roots: dict, actions: dict, standard_nfe: int) -> dict:
    budget = 2 * standard_nfe
    leaves_by_root = {
        root: root_leaves(prompt_id, root, roots[(prompt_id, root)], actions) for root in (0, 1)
    }
    options = {root: root_options(leaves, standard_nfe, budget) for root, leaves in leaves_by_root.items()}
    candidates = []
    for cost0, left in options[0].items():
        for cost1, right in options[1].items():
            cost = cost0 + cost1
            if cost > budget:
                continue
            selected = left["selected"] + right["selected"]
            if not selected:
                # A feasible BOLT program must honor the completion reserve by
                # producing at least one completed candidate.
                continue
            candidates.append(
                {
                    "cost": cost,
                    "selected": selected,
                    "any_success": int(left["any_success"] or right["any_success"]),
                    "success_count": left["success_count"] + right["success_count"],
                    "option": left["option"] + right["option"],
                }
            )
    best = max(
        candidates,
        key=lambda row: (row["any_success"], row["success_count"], row["option"], -row["cost"]),
    )
    successful = [row for row in candidates if row["any_success"]]
    minimum_success = min((row["cost"] for row in successful), default=budget)
    cheapest = min(
        (row for row in successful if row["cost"] == minimum_success),
        key=lambda row: (-row["success_count"], -row["option"]),
        default=best,
    )
    per_root = {}
    for root_index, root_options_by_cost in options.items():
        nonempty = [
            {"cost": cost, **value}
            for cost, value in root_options_by_cost.items()
            if value["selected"]
        ]
        root_best = max(
            nonempty,
            key=lambda row: (
                row["any_success"], row["success_count"], row["option"], -row["cost"]
            ),
        )
        per_root[root_index] = root_best
    leaf_index = {
        leaf.leaf_id: leaf
        for root_index in (0, 1)
        for leaf in leaves_by_root[root_index]
    }
    return {
        **best,
        "minimum_success_cost": minimum_success,
        "cheapest_successful": cheapest["selected"],
        "per_root": per_root,
        "quality_floor_failures": sum(
            leaf_index[leaf_id].row.get("quality_floor_status") != "PASS"
            for leaf_id in best["selected"]
        ),
    }


def state_action_oracle(prompt_id: str, actions: dict, budget: int) -> list[dict]:
    output = []
    for root in (0, 1):
        for checkpoint in CHECKPOINT_STEPS:
            rows = [action_row(actions, prompt_id, root, checkpoint, action) for action in (
                "CONTINUE", "SWITCH_CONDITION", "FORK_LATENT", "RESTART_BASE", "RESTART_CONDITIONED"
            )]
            feasible = [row for row in rows if int(row["total_tree_edge_nfe"]) <= budget]
            chosen = max(
                feasible,
                key=lambda row: (
                    int(row["cqs"]), option_probability(row),
                    float(row.get("common_robust_lcb") or -math.inf), -int(row["total_tree_edge_nfe"]),
                ),
            )
            output.append(
                {
                    "prompt_id": prompt_id, "root_index": root, "checkpoint_step": checkpoint,
                    "oracle_action": chosen["action"], "oracle_cqs": int(chosen["cqs"]),
                    "oracle_cost_nfe": int(chosen["total_tree_edge_nfe"]),
                    "oracle_output_sha256": chosen["output_sha256"],
                }
            )
    return output


def stratified_bootstrap(prompt_rows: list[dict], reps: int = BOOTSTRAP_REPS) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    strata = sorted({row["stratum"] for row in prompt_rows})
    grouped = {stratum: [row for row in prompt_rows if row["stratum"] == stratum] for stratum in strata}
    headrooms = np.empty(reps, dtype=np.float64)
    savings = np.empty(reps, dtype=np.float64)
    static_rates = np.empty(reps, dtype=np.float64)
    oracle_rates = np.empty(reps, dtype=np.float64)
    nonstatic_rates = np.empty(reps, dtype=np.float64)
    for index in range(reps):
        sample = []
        for rows in grouped.values():
            picks = rng.integers(0, len(rows), size=len(rows))
            sample.extend(rows[pick] for pick in picks)
        weights = [row["design_weight"] for row in sample]
        static_rates[index] = weighted_mean((row["best_static_cqs"] for row in sample), weights)
        oracle_rates[index] = weighted_mean((row["oracle_cqs"] for row in sample), weights)
        headrooms[index] = oracle_rates[index] - static_rates[index]
        savings[index] = weighted_mean((row["compute_saving"] for row in sample), weights)
        nonstatic_rates[index] = weighted_mean((row["nonstatic_program"] for row in sample), weights)
    return {
        "best_static_cqs": static_rates,
        "oracle_cqs": oracle_rates,
        "oracle_headroom": headrooms,
        "compute_saving": savings,
        "nonstatic_prompt_share": nonstatic_rates,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(path)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    for prerequisite, text in ((GATE0, "GATE0_STATUS = PASS"), (AUDIT, "PILOT_AUDIT_STATUS = PASS")):
        if not prerequisite.is_file() or text not in prerequisite.read_text(encoding="utf-8"):
            raise RuntimeError(f"oracle analysis blocked by {prerequisite.name}")
    for output in (STATIC_CSV, ACTION_CSV, STRATUM_CSV, BOOTSTRAP_CSV, REPORT, GATE1):
        if output.exists():
            raise FileExistsError(output)
    prompts, roots, actions = build_indices()
    nfes = {int(row["transformer_forward_calls"]) for row in roots.values()}
    if len(nfes) != 1:
        raise RuntimeError(f"standard generation NFE is not invariant: {nfes}")
    standard_nfe = next(iter(nfes))
    budget = 2 * standard_nfe

    by_prompt_programs = {
        row["prompt_id"]: static_programs(row, roots, actions, standard_nfe) for row in prompts
    }
    program_names = sorted(next(iter(by_prompt_programs.values())))
    static_rows = []
    for name in program_names:
        values = [by_prompt_programs[row["prompt_id"]][name] for row in prompts]
        weights = [float(row["design_weight"]) for row in prompts]
        static_rows.append(
            {
                "program": name,
                "population_weighted_cqs60": weighted_mean((value["cqs"] for value in values), weights),
                "equal_prompt_cqs60": float(np.mean([value["cqs"] for value in values])),
                "completion_probability": weighted_mean((value["completion"] for value in values), weights),
                "mean_actual_nfe": weighted_mean((value["cost"] for value in values), weights),
                "max_actual_nfe": max(value["cost"] for value in values),
                "infeasible_prompts": sum(not value["feasible"] for value in values),
                "quality_floor_failures": sum(value["quality_failures"] for value in values),
            }
        )
    feasible_static = [row for row in static_rows if row["infeasible_prompts"] == 0]
    best_static = max(
        feasible_static,
        key=lambda row: (row["population_weighted_cqs60"], -row["mean_actual_nfe"], row["program"]),
    )
    best_name = best_static["program"]

    prompt_results = []
    action_rows = []
    for prompt in prompts:
        prompt_id = prompt["prompt_id"]
        action_rows.extend(state_action_oracle(prompt_id, actions, budget))
        oracle = full_tree_oracle(prompt_id, roots, actions, standard_nfe)
        for root_index, root_oracle in oracle["per_root"].items():
            action_rows.append(
                {
                    "prompt_id": prompt_id,
                    "oracle_level": "per_root_feasible_subset",
                    "root_index": root_index,
                    "oracle_cqs": root_oracle["any_success"],
                    "oracle_cost_nfe": root_oracle["cost"],
                    "oracle_selected": ";".join(root_oracle["selected"]),
                    "oracle_success_count": root_oracle["success_count"],
                    "oracle_option_value": root_oracle["option"],
                }
            )
        static = by_prompt_programs[prompt_id][best_name]
        oracle_cqs = int(oracle["any_success"])
        static_cqs = int(static["cqs"])
        saving = matched_cqs_compute_saving(
            static_cqs, int(static["cost"]), int(oracle["minimum_success_cost"])
        )
        prompt_results.append(
            {
                "prompt_id": prompt_id,
                "stratum": prompt["stratum"],
                "design_weight": float(prompt["design_weight"]),
                "best_static_program": best_name,
                "best_static_cqs": static_cqs,
                "best_static_nfe": int(static["cost"]),
                "oracle_cqs": oracle_cqs,
                "oracle_tree_nfe": int(oracle["cost"]),
                "oracle_minimum_success_nfe": int(oracle["minimum_success_cost"]),
                "oracle_selected": ";".join(oracle["selected"]),
                "oracle_cheapest_successful": ";".join(oracle["cheapest_successful"]),
                "oracle_option_value": float(oracle["option"]),
                "oracle_quality_floor_failures": int(oracle["quality_floor_failures"]),
                "oracle_completion": int(bool(oracle["selected"])),
                "compute_saving": float(saving),
                "matched_oracle_nfe": (
                    int(oracle["minimum_success_cost"]) if static_cqs else int(static["cost"])
                ),
                "nonstatic_program": int(
                    oracle_program_differs(static["leaf_ids"], oracle["selected"])
                ),
            }
        )

    weights = [row["design_weight"] for row in prompt_results]
    static_cqs = weighted_mean((row["best_static_cqs"] for row in prompt_results), weights)
    oracle_cqs = weighted_mean((row["oracle_cqs"] for row in prompt_results), weights)
    headroom = oracle_cqs - static_cqs
    nonstatic = weighted_mean((row["nonstatic_program"] for row in prompt_results), weights)
    compute_saving = weighted_mean((row["compute_saving"] for row in prompt_results), weights)
    bootstraps = stratified_bootstrap(prompt_results)
    headroom_boot = bootstraps["oracle_headroom"]
    saving_boot = bootstraps["compute_saving"]
    headroom_lcb = float(np.quantile(headroom_boot, 0.05, method="linear"))
    saving_lcb = float(np.quantile(saving_boot, 0.05, method="linear"))
    static_ci = np.quantile(bootstraps["best_static_cqs"], [0.025, 0.975], method="linear")
    oracle_ci = np.quantile(bootstraps["oracle_cqs"], [0.025, 0.975], method="linear")
    bootstrap_rows = [
        {"replicate": index, **{name: values[index] for name, values in bootstraps.items()}}
        for index in range(BOOTSTRAP_REPS)
    ]

    stratum_rows = []
    for stratum in sorted({row["stratum"] for row in prompt_results}):
        group = [row for row in prompt_results if row["stratum"] == stratum]
        group_weights = [row["design_weight"] for row in group]
        static_rate = weighted_mean((row["best_static_cqs"] for row in group), group_weights)
        oracle_rate = weighted_mean((row["oracle_cqs"] for row in group), group_weights)
        stratum_rows.append(
            {
                "stratum": stratum, "prompts": len(group),
                "best_static_cqs60": static_rate, "oracle_cqs60": oracle_rate,
                "oracle_headroom": oracle_rate - static_rate,
                "nonstatic_prompt_share": weighted_mean((row["nonstatic_program"] for row in group), group_weights),
                "oracle_mean_minimum_success_nfe": weighted_mean((row["oracle_minimum_success_nfe"] for row in group), group_weights),
            }
        )

    equal_stratum_static = float(np.mean([row["best_static_cqs60"] for row in stratum_rows]))
    equal_stratum_oracle = float(np.mean([row["oracle_cqs60"] for row in stratum_rows]))
    oracle_mean_nfe = weighted_mean((row["oracle_tree_nfe"] for row in prompt_results), weights)
    oracle_completion = weighted_mean((row["oracle_completion"] for row in prompt_results), weights)
    oracle_quality_failures = sum(row["oracle_quality_floor_failures"] for row in prompt_results)

    fixed_condition_unnecessary = []
    fixed_condition_harmful = []
    switch_beats_restart = []
    branching_helps = []
    for prompt in prompts:
        prompt_id = prompt["prompt_id"]
        programs = by_prompt_programs[prompt_id]
        if programs["two_base"]["cqs"]:
            fixed_condition_unnecessary.append(prompt_id)
            if not programs["two_direction_conditioned"]["cqs"]:
                fixed_condition_harmful.append(prompt_id)
        if not programs["two_base"]["cqs"] and any(
            programs[name]["cqs"]
            for name in programs
            if "deterministic_fork" in name
        ):
            branching_helps.append(prompt_id)
        for root_index in (0, 1):
            for checkpoint in CHECKPOINT_STEPS:
                switch = action_row(actions, prompt_id, root_index, checkpoint, "SWITCH_CONDITION")
                restart_base = action_row(actions, prompt_id, root_index, checkpoint, "RESTART_BASE")
                restart_conditioned = action_row(
                    actions, prompt_id, root_index, checkpoint, "RESTART_CONDITIONED"
                )
                if int(switch["cqs"]) and not int(restart_base["cqs"]) and not int(restart_conditioned["cqs"]):
                    switch_beats_restart.append(f"{prompt_id}:root{root_index}:step{checkpoint}")

    action_frequency = Counter()
    checkpoint_frequency = Counter()
    for row in prompt_results:
        for leaf in filter(None, row["oracle_cheapest_successful"].split(";")):
            parts = leaf.split("_")
            if "step" in leaf:
                checkpoint_frequency[int(parts[1].removeprefix("step"))] += 1
                action_frequency["_".join(parts[2:])] += 1
            else:
                checkpoint_frequency[30] += 1
                action_frequency["CONTINUE"] += 1
    total_actions = sum(action_frequency.values())
    entropy = -sum((count / total_actions) * math.log(count / total_actions) for count in action_frequency.values()) if total_actions else 0.0

    headroom_pass = headroom >= 0.05 and headroom_lcb > 0.0
    compute_pass = compute_saving >= 0.20 and saving_lcb > 0.0
    nonstatic_pass = nonstatic >= 0.20
    decision = "GO_ACTION_VALUE_LEARNING" if (headroom_pass or compute_pass) and nonstatic_pass else "STOP_NO_STRUCTURAL_HEADROOM"

    write_csv(STATIC_CSV, static_rows)
    write_csv(ACTION_CSV, action_rows + [{"prompt_id": row["prompt_id"], "oracle_level": "full_tree", **row} for row in prompt_results])
    write_csv(STRATUM_CSV, stratum_rows)
    write_csv(BOOTSTRAP_CSV, bootstrap_rows)
    static_lines = "".join(
        f"| {row['program']} | {row['population_weighted_cqs60']:.6f} | {row['completion_probability']:.6f} | {row['mean_actual_nfe']:.3f} | {row['infeasible_prompts']} |\n"
        for row in sorted(static_rows, key=lambda item: (-item["population_weighted_cqs60"], item["mean_actual_nfe"]))
    )
    stratum_lines = "".join(
        f"| {row['stratum']} | {row['best_static_cqs60']:.6f} | {row['oracle_cqs60']:.6f} | {row['oracle_headroom']:.6f} | {row['nonstatic_prompt_share']:.6f} |\n"
        for row in stratum_rows
    )
    REPORT.write_text(
        "# BOLT Oracle Structural Headroom\n\n"
        f"Best globally fixed feasible program: `{best_name}`. Raw-NFE budget: `{budget}` "
        f"(`2 x {standard_nfe}` measured forward calls).\n\n"
        f"BEST_STATIC_CQS60 = {static_cqs:.9f}\n"
        f"ORACLE_CQS60 = {oracle_cqs:.9f}\n"
        f"ORACLE_HEADROOM_CQS60 = {headroom:.9f}\n"
        f"ORACLE_HEADROOM_LCB95 = {headroom_lcb:.9f}\n"
        f"ORACLE_COMPUTE_SAVING = {compute_saving:.9f}\n"
        f"ORACLE_COMPUTE_SAVING_LCB95 = {saving_lcb:.9f}\n"
        f"ORACLE_NONSTATIC_PROMPT_SHARE = {nonstatic:.9f}\n\n"
        f"Best-static prompt-bootstrap 95% interval: `[{static_ci[0]:.9f}, {static_ci[1]:.9f}]`; "
        f"oracle interval: `[{oracle_ci[0]:.9f}, {oracle_ci[1]:.9f}]`. Equal-stratum "
        f"diagnostic CQS@60 is `{equal_stratum_static:.9f}` static and "
        f"`{equal_stratum_oracle:.9f}` oracle. Oracle completion probability is "
        f"`{oracle_completion:.9f}`, mean selected-program NFE is `{oracle_mean_nfe:.6f}`, and "
        f"selected oracle leaves contain `{oracle_quality_failures}` quality-floor failures.\n\n"
        "The empirical tree oracle is outcome-aware and is only an upper bound. Terminal CONTINUE "
        "leaves are deduplicated by physical root output. Tree costs share each root prefix once; "
        "switch/fork continuations pay their remaining measured NFE and restarts pay their complete "
        "measured generation NFE. The option-value approximation uses `sum[-log(1-p_i)]` and is "
        "reported separately from empirical any-success.\n\n"
        "`ORACLE_NONSTATIC_PROMPT_SHARE` is the frozen weighted share of prompts where the "
        "oracle-optimal feasible leaf program differs from the globally best static program. "
        "Comparison uses canonical physical leaf IDs after CONTINUE deduplication.\n\n"
        "## Static programs\n\n| program | weighted CQS@60 | completion | mean NFE | infeasible prompts |\n| --- | ---: | ---: | ---: | ---: |\n"
        + static_lines
        + "\n## Frozen strata\n\n| stratum | static | oracle | headroom | nonstatic share |\n| --- | ---: | ---: | ---: | ---: |\n"
        + stratum_lines
        + f"\n## Structural choices\n\nAction frequency: `{dict(action_frequency)}`. Checkpoint frequency: "
        f"`{dict(checkpoint_frequency)}`. Action entropy (natural log): `{entropy:.6f}`.\n\n"
        f"Fixed conditioning is unnecessary on `{len(fixed_condition_unnecessary)}` sampled prompts "
        f"(base already attains CQS) and harmful on `{len(fixed_condition_harmful)}` of them: "
        f"`{', '.join(fixed_condition_harmful) or 'none'}`. Same-latent switching beats both "
        f"matched restart actions at `{len(switch_beats_restart)}` states: "
        f"`{', '.join(switch_beats_restart) or 'none'}`. A fixed deterministic-plus-fork program "
        f"rescues `{len(branching_helps)}` prompts missed by two base generations: "
        f"`{', '.join(branching_helps) or 'none'}`.\n\n"
        "The corrected-EVPD baselines use the frozen sigma-0.8 W2 probe without retuning. The W2 "
        "two-slot baseline leaves abort savings unused; the true-rollover baseline returns measured "
        "NFE and uses only an additional branch that fits the global budget.\n",
        encoding="utf-8",
    )
    gate0_text = GATE0.read_text(encoding="utf-8")
    statuses = {}
    for name in (
        "GATE0_STATUS", "ENVIRONMENT_PARITY_STATUS", "RESUME_EQUIVALENCE_STATUS",
        "CONDITION_SWITCH_STATUS", "FORK_STATUS", "ACTUAL_NFE_STATUS",
        "TRUE_ROLLOVER_STATUS", "COMPLETION_RESERVE_STATUS",
    ):
        statuses[name] = next(line.split("=", 1)[1].strip() for line in gate0_text.splitlines() if line.startswith(name + " ="))
    branch = subprocess.check_output(["git", "-C", str(ROOT), "branch", "--show-current"], text=True).strip()
    sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    GATE1.write_text(
        "# BOLT Gate 1 Report\n\n"
        + "".join(f"{name} = {statuses[name]}\n" for name in (
            "GATE0_STATUS", "ENVIRONMENT_PARITY_STATUS", "RESUME_EQUIVALENCE_STATUS",
            "CONDITION_SWITCH_STATUS", "FORK_STATUS", "ACTUAL_NFE_STATUS",
            "TRUE_ROLLOVER_STATUS", "COMPLETION_RESERVE_STATUS",
        ))
        + "ROOT_TRAJECTORIES = 96\nCHECKPOINT_STATES = 288\nPILOT_ACTION_OUTCOMES = 1440\n"
        + f"BEST_STATIC_CQS60 = {static_cqs:.9f}\nORACLE_CQS60 = {oracle_cqs:.9f}\n"
        + f"ORACLE_HEADROOM_CQS60 = {headroom:.9f}\nORACLE_HEADROOM_LCB95 = {headroom_lcb:.9f}\n"
        + f"ORACLE_COMPUTE_SAVING = {compute_saving:.9f}\nORACLE_NONSTATIC_PROMPT_SHARE = {nonstatic:.9f}\n"
        + f"BOLT_GATE1 = {decision}\nTEST_SUITE_STATUS = PENDING\n\n"
        + f"Branch: `{branch}`. Analysis-parent commit: `{sha}`. The containing final Git commit is "
        "reported by the immutable branch ref because a commit cannot embed its own SHA.\n\n"
        + f"Prompt IDs: `{', '.join(row['prompt_id'] for row in prompts)}`. Seed namespace: `2060000000`.\n\n"
        + f"Quality floors: `{FLOORS_PATH}`. Static table: `{STATIC_CSV.relative_to(ROOT)}`. "
        f"Oracle table: `{ACTION_CSV.relative_to(ROOT)}`. Strata: `{STRATUM_CSV.relative_to(ROOT)}`.\n\n"
        + f"Decision checks: headroom={headroom_pass}; compute-saving={compute_pass}; nonstatic={nonstatic_pass}. "
        "No Gate 2 work was launched.\n",
        encoding="utf-8",
    )
    print(json.dumps({"decision": decision, "best_static": static_cqs, "oracle": oracle_cqs, "headroom": headroom, "lcb": headroom_lcb, "nonstatic": nonstatic}))
    return 0


FLOORS_PATH = "paper_prep/tier3_bolt_20260715/BOLT_QUALITY_FLOORS.json"


if __name__ == "__main__":
    raise SystemExit(main())
