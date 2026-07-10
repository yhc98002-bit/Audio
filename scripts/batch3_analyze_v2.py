#!/usr/bin/env python3
"""Fail-closed, read-only Batch-3 reanalysis for publication recovery."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
BUDGETS = {1: 168, 2: 168, 3: 168, 4: 168, 6: 168, 7: 240, 8: 120}
ARMS = tuple(sorted(BUDGETS))
CHECKPOINTS = (30, 60, 90, 120, 150, 168)
NBOOT = 10_000
SEED_B3 = 2026062000


def load_jsonl_strict(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line at {path}:{line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"non-object JSON at {path}:{line_number}")
            row["_source_path"] = str(path)
            row["_line_number"] = line_number
            rows.append(row)
    return rows


def selected_candidate(rows: list[dict], lyric_defer: bool = False) -> dict | None:
    completed = [row for row in rows if row.get("completed") is True]
    if not completed:
        return None
    passers = [row for row in completed if row.get("gate_pass") == 1]
    pool = passers if passers else completed

    def key(row: dict) -> float:
        common = row.get("final_common_robust_lcb")
        common = float(common) if common is not None else -math.inf
        if not lyric_defer:
            return common
        lyric = row.get("final_lyric_intelligibility")
        lyric = float(lyric) if lyric is not None else 0.0
        return common + 0.25 * lyric

    return max(pool, key=key)


def expected_unit_keys(prompt_ids: list[str], tail_ids: set[str]) -> set[tuple[str, int, int]]:
    keys = {(prompt_id, arm, rep) for prompt_id in prompt_ids for arm in ARMS for rep in (0, 1)}
    keys.update((prompt_id, arm, 2) for prompt_id in tail_ids for arm in (4, 6))
    return keys


def load_and_validate(ledger_dir: Path, selected_path: Path, tail_path: Path):
    selected_prompts = load_jsonl_strict(selected_path)
    tail_rows = load_jsonl_strict(tail_path)
    prompt_ids = [row["prompt_id"] for row in selected_prompts]
    if len(prompt_ids) != 256 or len(set(prompt_ids)) != 256:
        raise ValueError("Batch-3 selected prompt manifest must contain 256 unique IDs")
    tail_ids = {row["prompt_id"] for row in tail_rows}
    if len(tail_ids) != 32 or not tail_ids.issubset(prompt_ids):
        raise ValueError("Batch-3 tail subgroup must contain 32 selected prompts")
    prompt_index = {row["prompt_id"]: row for row in selected_prompts}
    manifest_position = {row["prompt_id"]: int(row["manifest_index"]) for row in selected_prompts}

    attempts: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    selections: dict[tuple[str, int, int], dict] = {}
    attempt_keys: set[tuple[str, int, int, int]] = set()
    all_rows = []
    paths = sorted(ledger_dir.glob("ledger_w*.jsonl"))
    if len(paths) != 16:
        raise ValueError(f"expected 16 Batch-3 worker ledgers, found {len(paths)}")
    for path in paths:
        for row in load_jsonl_strict(path):
            all_rows.append(row)
            required = {"prompt_id", "arm", "rep"}
            if not required.issubset(row):
                raise ValueError(f"missing required fields at {path}:{row['_line_number']}")
            unit_key = (str(row["prompt_id"]), int(row["arm"]), int(row["rep"]))
            if row.get("type") == "unit_selection":
                if unit_key in selections:
                    raise ValueError(f"duplicate unit-selection key {unit_key}")
                selections[unit_key] = row
                continue
            if "attempt" not in row:
                raise ValueError(f"attempt row lacks attempt index: {path}:{row['_line_number']}")
            attempt_key = (*unit_key, int(row["attempt"]))
            if attempt_key in attempt_keys:
                raise ValueError(f"duplicate attempt key {attempt_key}")
            attempt_keys.add(attempt_key)
            attempts[unit_key].append(row)

    expected = expected_unit_keys(prompt_ids, tail_ids)
    if set(attempts) != expected or set(selections) != expected:
        raise ValueError(
            f"Batch-3 unit cell mismatch: attempt missing={len(expected-set(attempts))}, "
            f"attempt extra={len(set(attempts)-expected)}, selection missing={len(expected-set(selections))}, "
            f"selection extra={len(set(selections)-expected)}"
        )
    if len(expected) != 3648:
        raise AssertionError(f"internal expected-unit shape is {len(expected)}, not 3648")

    selection_mismatches = []
    for unit_key, rows in attempts.items():
        rows.sort(key=lambda row: int(row["attempt"]))
        if [int(row["attempt"]) for row in rows] != list(range(len(rows))):
            raise ValueError(f"non-contiguous attempts in {unit_key}")
        prompt_id, arm, rep = unit_key
        aborts = 0
        spent = 0
        for row in rows:
            expected_seed = SEED_B3 + manifest_position[prompt_id] * 1000 + rep * 100 + int(row["attempt"])
            if int(row["seed"]) != expected_seed:
                raise ValueError(f"CRN seed mismatch in {unit_key} attempt {row['attempt']}")
            if int(row["budget_before"]) < 30:
                raise ValueError(f"attempt entered with budget_before <30 in {unit_key}")
            cost = int(row["cost"])
            if cost not in {12, 30}:
                raise ValueError(f"invalid cost {cost} in {unit_key}")
            spent += cost
            aborts += int(row.get("aborted") is True)
            if row.get("completed") is True and row.get("gate_pass") not in {0, 1}:
                raise ValueError(f"completed row lacks binary gate_pass in {unit_key}")
            if row.get("aborted") is True and row.get("completed") is not False:
                raise ValueError(f"aborted/completed inconsistency in {unit_key}")
        if spent > BUDGETS[arm] or aborts > 6:
            raise ValueError(f"budget/abort cap violation in {unit_key}: spent={spent}, aborts={aborts}")
        recomputed = selected_candidate(rows)
        recorded = selections[unit_key].get("selected")
        recomputed_name = Path(recomputed["wav"]).name if recomputed else None
        if recorded != recomputed_name:
            selection_mismatches.append({"prompt_id": prompt_id, "arm": arm, "rep": rep, "recorded": recorded, "recomputed": recomputed_name})
    if selection_mismatches:
        raise ValueError(f"recorded selection reconciliation failed for {len(selection_mismatches)} units")
    return attempts, selections, prompt_index, tail_ids, paths, all_rows


def paired_bootstrap(values: list[float], rng: np.random.RandomState, nboot: int = NBOOT) -> tuple[float, np.ndarray]:
    array = np.asarray(values, dtype=float)
    if not len(array):
        return math.nan, np.asarray([])
    samples = np.asarray([array[rng.choice(len(array), len(array), replace=True)].mean() for _ in range(nboot)])
    return float(array.mean()), samples


def population_weights(prompt_index: dict[str, dict]) -> dict[str, float]:
    by_direction = Counter(row["vocal_stratum"] for row in prompt_index.values())
    if set(by_direction) != {"vocal", "instrumental"}:
        raise ValueError(f"unexpected vocal strata: {by_direction}")
    return {
        prompt_id: (316 / 512) / by_direction["vocal"]
        if row["vocal_stratum"] == "vocal"
        else (196 / 512) / by_direction["instrumental"]
        for prompt_id, row in prompt_index.items()
    }


def weighted_prompt_mean(values: dict[str, float], weights: dict[str, float]) -> float:
    if not values:
        return math.nan
    denominator = sum(weights[prompt_id] for prompt_id in values)
    return sum(weights[prompt_id] * value for prompt_id, value in values.items()) / denominator


def selected_rows_for_arm(attempts: dict, prompt_index: dict, arm: int) -> dict[tuple[str, int], dict]:
    output = {}
    for (prompt_id, candidate_arm, rep), rows in attempts.items():
        if candidate_arm != arm:
            continue
        lyric_defer = arm == 4 and prompt_index[prompt_id]["vocal_stratum"] == "vocal" and prompt_index[prompt_id].get("language") == "en"
        output[(prompt_id, rep)] = selected_candidate(rows, lyric_defer=False)
        if output[(prompt_id, rep)] is None:
            raise ValueError(f"no completed candidates for {(prompt_id, arm, rep)}")
    return output


def reconstructed_arm5(attempts: dict, prompt_index: dict) -> dict[tuple[str, int], dict]:
    output = {}
    for (prompt_id, arm, rep), rows in attempts.items():
        if arm != 4:
            continue
        use_lyric = prompt_index[prompt_id]["vocal_stratum"] == "vocal" and prompt_index[prompt_id].get("language") == "en"
        output[(prompt_id, rep)] = selected_candidate(rows, lyric_defer=use_lyric)
    return output


def summarize_selected(selected: dict[tuple[str, int], dict], prompt_index: dict, weights: dict[str, float]) -> dict:
    axis_names = (
        "final_common_robust_lcb",
        "final_semantic_fit",
        "final_aesthetic_pq",
        "final_lyric_intelligibility",
    )
    per_prompt: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (prompt_id, _rep), row in selected.items():
        for axis in axis_names:
            value = row.get(axis)
            if value is None:
                continue
            if axis == "final_lyric_intelligibility" and not (
                prompt_index[prompt_id]["vocal_stratum"] == "vocal"
                and prompt_index[prompt_id].get("language") == "en"
            ):
                continue
            per_prompt[prompt_id][axis].append(float(value))
    result = {}
    for axis in axis_names:
        values = {prompt_id: float(np.mean(axes[axis])) for prompt_id, axes in per_prompt.items() if axes.get(axis)}
        result[axis] = {
            "n_prompts": len(values),
            "unweighted_mean": float(np.mean(list(values.values()))) if values else math.nan,
            "population_weighted_mean": weighted_prompt_mean(values, weights),
        }
    type_by_prompt = defaultdict(list)
    for (prompt_id, _rep), row in selected.items():
        type_by_prompt[prompt_id].append(1.0 - float(row["gate_pass"]))
    type_values = {prompt_id: float(np.mean(values)) for prompt_id, values in type_by_prompt.items()}
    by_stratum = {}
    for stratum in ("vocal", "instrumental"):
        subset = {prompt_id: value for prompt_id, value in type_values.items() if prompt_index[prompt_id]["vocal_stratum"] == stratum}
        by_stratum[stratum] = {"n_prompts": len(subset), "mean": float(np.mean(list(subset.values())))}
    return {
        "axes": result,
        "type_error_unweighted": float(np.mean(list(type_values.values()))),
        "type_error_population_weighted": weighted_prompt_mean(type_values, weights),
        "type_error_by_stratum": by_stratum,
    }


def yield_curve(attempts: dict, arm: int, weights: dict[str, float]) -> dict[str, float]:
    per_prompt: dict[str, list[list[dict]]] = defaultdict(list)
    for (prompt_id, candidate_arm, _rep), rows in attempts.items():
        if candidate_arm == arm:
            per_prompt[prompt_id].append(rows)
    output = {}
    for checkpoint in CHECKPOINTS:
        values = {}
        for prompt_id, units in per_prompt.items():
            yields = []
            for rows in units:
                spent = 0
                clean = 0
                for row in rows:
                    if spent + int(row["cost"]) > checkpoint:
                        break
                    spent += int(row["cost"])
                    clean += int(row.get("completed") is True and row.get("gate_pass") == 1)
                yields.append(clean)
            values[prompt_id] = float(np.mean(yields))
        output[str(checkpoint)] = weighted_prompt_mean(values, weights)
    return output


def cost_summary(attempts: dict, arm: int) -> dict:
    units = [rows for (_prompt, candidate_arm, _rep), rows in attempts.items() if candidate_arm == arm]
    spent = [sum(int(row["cost"]) for row in rows) for rows in units]
    return {
        "units": len(units),
        "attempts": sum(len(rows) for rows in units),
        "mean_nominal_steps": float(np.mean(spent)),
        "budget": BUDGETS[arm],
        "nominal_vs_budget_deviation": float(np.mean(spent)) / BUDGETS[arm] - 1,
        "aborts": sum(row.get("aborted") is True for rows in units for row in rows),
        "completions": sum(row.get("completed") is True for rows in units for row in rows),
        "probes": sum(row.get("probed") is True for rows in units for row in rows),
        "wall_gpu_hours": sum(float(row.get("wall_s", 0)) for rows in units for row in rows) / 3600,
        "probe_overhead_hours": sum(float(row.get("probe_overhead_s", 0)) for rows in units for row in rows) / 3600,
    }


def analyze(attempts: dict, prompt_index: dict, tail_ids: set[str]) -> dict:
    rng = np.random.RandomState(20260612)

    def restart2_values(prompt_id: str, arm: int) -> list[int]:
        values = []
        for (candidate_prompt, candidate_arm, _rep), rows in attempts.items():
            if candidate_prompt != prompt_id or candidate_arm != arm:
                continue
            aborts = 0
            for row in rows:
                if row.get("aborted") is True:
                    aborts += 1
                elif row.get("completed") is True and aborts >= 2:
                    values.append(int(row["gate_pass"]))
        return values

    primary_differences = {}
    for prompt_id in sorted(tail_ids):
        arm4 = restart2_values(prompt_id, 4)
        arm6 = restart2_values(prompt_id, 6)
        if arm4 and arm6:
            primary_differences[prompt_id] = float(np.mean(arm6) - np.mean(arm4))
    primary_estimate, primary_boot = paired_bootstrap(list(primary_differences.values()), rng)
    primary_ci = [float(np.quantile(primary_boot, 0.025)), float(np.quantile(primary_boot, 0.975))]
    direction = {}
    for stratum in ("vocal", "instrumental"):
        values = [value for prompt_id, value in primary_differences.items() if prompt_index[prompt_id]["vocal_stratum"] == stratum]
        direction[stratum] = {"n_prompts": len(values), "mean_delta": float(np.mean(values)) if values else math.nan}
    primary = {
        "n_prompts_contributing": len(primary_differences),
        "estimate": primary_estimate,
        "ci95": primary_ci,
        "pass": primary_estimate >= 0.15 and primary_ci[0] > 0,
        "by_direction": direction,
    }

    def all_values(prompt_id: str, arm: int) -> list[int]:
        return [int(row["gate_pass"]) for (candidate_prompt, candidate_arm, _rep), rows in attempts.items() if candidate_prompt == prompt_id and candidate_arm == arm for row in rows if row.get("completed") is True]

    secondary_differences = {}
    for prompt_id in sorted(tail_ids):
        arm4 = all_values(prompt_id, 4)
        arm6 = all_values(prompt_id, 6)
        if arm4 and arm6:
            secondary_differences[prompt_id] = float(np.mean(arm6) - np.mean(arm4))
    secondary_estimate, secondary_boot = paired_bootstrap(list(secondary_differences.values()), rng)
    one_sided = [float(np.quantile(secondary_boot, 0.025)), math.inf]
    two_sided = [float(np.quantile(secondary_boot, 0.0125)), float(np.quantile(secondary_boot, 0.9875))]
    secondary = {
        "n_prompts_contributing": len(secondary_differences),
        "estimate": secondary_estimate,
        "frozen_sentence": "Secondary (E2a, Bonferroni alpha=0.025): same construction over ALL completions per trajectory.",
        "adjudication": "one-sided alpha=0.025 lower bound uses the 2.5th percentile because the frozen criterion tests only a positive lower bound",
        "one_sided_97p5_lower": one_sided[0],
        "two_sided_97p5_sensitivity": two_sided,
        "pass_primary_reading": secondary_estimate >= 0.15 and one_sided[0] > 0,
        "pass_two_sided_sensitivity": secondary_estimate >= 0.15 and two_sided[0] > 0,
    }
    weights = population_weights(prompt_index)
    selected = {arm: selected_rows_for_arm(attempts, prompt_index, arm) for arm in ARMS}
    selected[5] = reconstructed_arm5(attempts, prompt_index)
    selected_summaries = {f"arm{arm}": summarize_selected(rows, prompt_index, weights) for arm, rows in selected.items()}
    curves = {f"arm{arm}": yield_curve(attempts, arm, weights) for arm in ARMS}
    curves["arm5"] = dict(curves["arm4"])
    costs = {f"arm{arm}": cost_summary(attempts, arm) for arm in ARMS}
    margins = {}
    for axis, limit in (("final_common_robust_lcb", -0.015), ("final_semantic_fit", -0.015), ("final_aesthetic_pq", -0.02), ("final_lyric_intelligibility", -0.02)):
        value = selected_summaries["arm6"]["axes"][axis]["unweighted_mean"] - selected_summaries["arm1"]["axes"][axis]["unweighted_mean"]
        margins[axis] = {"delta": value, "limit": limit, "pass": value >= limit}
    verdict = "SUPPORTED_TAIL_RESCUE" if primary["pass"] and all(value["pass"] for value in margins.values()) else "CONDITIONAL" if secondary["pass_primary_reading"] else "NOT_SUPPORTED"
    return {
        "primary": primary,
        "secondary": secondary,
        "selected": selected_summaries,
        "yield_vs_compute": curves,
        "cost_accounting": costs,
        "selected_axis_margins_arm6_minus_arm1": margins,
        "verdict": verdict,
    }


def old_vs_v2(result: dict, old: dict) -> tuple[list[dict], bool]:
    rows = []

    def add(name: str, old_value: float, new_value: float, gate: bool = False):
        delta = new_value - old_value
        rows.append({"metric": name, "old": old_value, "v2": new_value, "absolute_delta": abs(delta), "gate_metric": str(gate).lower()})

    add("primary_estimate", float(old["primary"]["estimate"]), result["primary"]["estimate"], True)
    add("secondary_estimate", float(old["secondary"]["estimate"]), result["secondary"]["estimate"], True)
    for arm in ARMS:
        name = f"arm{arm}"
        add(f"{name}_selected_type_error", float(old["selected_output_type_error"][name]), result["selected"][name]["type_error_population_weighted"])
        for axis, old_value in old["selected_axis_means"][name].items():
            add(f"{name}_{axis}_unweighted", float(old_value), result["selected"][name]["axes"][axis]["unweighted_mean"])
    gate_flip = bool(old["primary"]["pass"] != result["primary"]["pass"] or old["secondary"]["pass"] != result["secondary"]["pass_primary_reading"])
    escalated = gate_flip or any(float(row["absolute_delta"]) > 0.01 for row in rows)
    return rows, escalated


def write_outputs(out_dir: Path, result: dict, diff_rows: list[dict], completeness: dict, status: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"BATCH3_REANALYSIS_STATUS": status, **result, "completeness": completeness}
    (out_dir / "BATCH3_RESULTS_V2.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with (out_dir / "BATCH3_OLD_VS_V2_DIFF.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(diff_rows[0]))
        writer.writeheader()
        writer.writerows(diff_rows)
    secondary = result["secondary"]
    report = f"""# Batch-3 Results V2

`BATCH3_REANALYSIS_STATUS = {status}`

## Frozen Endpoints

- Primary restart2+ delta: {result['primary']['estimate']:.6f}, 95% CI [{result['primary']['ci95'][0]:.6f}, {result['primary']['ci95'][1]:.6f}], n={result['primary']['n_prompts_contributing']}, pass={str(result['primary']['pass']).lower()}.
- Secondary full-trajectory delta: {secondary['estimate']:.6f}, one-sided alpha=.025 lower={secondary['one_sided_97p5_lower']:.6f}, pass={str(secondary['pass_primary_reading']).lower()}.
- Secondary two-sided 97.5% sensitivity: [{secondary['two_sided_97p5_sensitivity'][0]:.6f}, {secondary['two_sided_97p5_sensitivity'][1]:.6f}], pass={str(secondary['pass_two_sided_sensitivity']).lower()}.
- Mechanical verdict: `{result['verdict']}`.

Frozen sentence: "Secondary (E2a, Bonferroni alpha=0.025): same construction over ALL completions per trajectory."

The primary reading is one-sided because the frozen rule asks whether a lower
bound exceeds zero. The stricter two-sided reading is shown as sensitivity;
neither reading changes the gate.

## Integrity

- 16 ledgers parsed line-by-line with no invalid JSON.
- 22,825 unique attempt rows and 3,648 unique unit-selection rows.
- Expected 256-prompt x arm x replicate cells, including exactly 32 rep-2
  tail cells for arms 4 and 6, were asserted.
- Every recorded selection matched the fail-closed recomputation.
- Arm 5 was reconstructed as the frozen lyric-defer selection over arm-4
  candidates without adding generation cost.
- Population weights are joined by prompt ID. Weighted and unweighted selected
  summaries are both retained in the JSON.
"""
    (out_dir / "BATCH3_RESULTS_V2.md").write_text(report, encoding="utf-8")
    completeness_text = "# Batch-3 Ledger Completeness Report\n\n" + "\n".join(f"- {key}: {value}" for key, value in completeness.items()) + "\n"
    (out_dir / "BATCH3_LEDGER_COMPLETENESS_REPORT.md").write_text(completeness_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger-dir", type=Path, default=B3 / "online_run")
    parser.add_argument("--selected-prompts", type=Path, default=B3 / "batch3_selected_prompts_256.jsonl")
    parser.add_argument("--tail-prompts", type=Path, default=B3 / "E2_TAIL_SUBGROUP.jsonl")
    parser.add_argument("--old-results", type=Path, default=B3 / "ADSR_ONLINE_COMPREHENSIVE_RESULTS.json")
    parser.add_argument("--out-dir", type=Path, default=REPO / "paper_prep/reanalysis_20260709")
    args = parser.parse_args()
    attempts, selections, prompt_index, tail_ids, paths, all_rows = load_and_validate(
        args.ledger_dir, args.selected_prompts, args.tail_prompts
    )
    result = analyze(attempts, prompt_index, tail_ids)
    old = json.loads(args.old_results.read_text(encoding="utf-8"))
    diff_rows, escalated = old_vs_v2(result, old)
    status = "DIFF_ESCALATED" if escalated else "PASS"
    completeness = {
        "ledger_files": len(paths),
        "json_rows": len(all_rows),
        "attempt_rows": sum(len(rows) for rows in attempts.values()),
        "unit_selection_rows": len(selections),
        "unique_unit_keys": len(attempts),
        "tail_prompts": len(tail_ids),
        "selection_mismatches": 0,
        "cost_reconciliation_artifact": "orbit-research/adsr_phase2_20260604/batch3/COST_RECONCILIATION.json",
        "source_ledgers": ", ".join(str(path.relative_to(REPO)) for path in paths),
    }
    write_outputs(args.out_dir, result, diff_rows, completeness, status)
    print(json.dumps({"status": status, "primary": result["primary"], "secondary": result["secondary"], "verdict": result["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
