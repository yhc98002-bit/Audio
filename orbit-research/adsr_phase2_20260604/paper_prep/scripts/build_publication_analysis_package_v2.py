#!/usr/bin/env python3
"""Build the fail-closed ADSR publication statistics v2 package.

The primary efficiency estimand is prompt-averaged deployment success, not
``1 / mean(p)``.  Uncertainty uses a prompt-and-seed cluster bootstrap with
the frozen difficult-set sampling strata preserved.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 20260709
DEPLOYMENT_N = (4, 5, 8, 16)
DRAW_BOUNDS = (16, 128, 1024)
THRESHOLD = 0.1791
REGIMES = (
    "rare_le_1_in_16",
    "low_1_in_16_to_1_in_4",
    "seed_recoverable_1_in_4_to_1_in_2",
    "easy_ge_1_in_2",
)


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "orbit-research").is_dir() and (candidate / "src/mprm").is_dir():
            return candidate
    raise RuntimeError(f"cannot find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
ATLAS = ROOT / "batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test"
PH2 = ROOT / "orbit-research/adsr_phase2_20260604"
STAGE3 = PAPER / "stage3_intervention_20260707"
N2 = PAPER / "population_retry_20260707"
SA3 = PAPER / "sao/stable_audio_3_medium"


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
            row["_source_path"] = str(path.relative_to(ROOT))
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def load_glob(directory: Path, pattern: str) -> list[dict]:
    paths = sorted(directory.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"no files matched {directory / pattern}")
    return [row for path in paths for row in read_jsonl(path)]


def unique_rows(rows: Iterable[dict], keys: Sequence[str], source: str) -> list[dict]:
    """Reject duplicate keys, including identical duplicates.

    There is no legitimate keep-first policy for publication-facing ledgers.
    An identical duplicate is still an ambiguous attempt count.
    """
    output: dict[tuple, dict] = {}
    for row in rows:
        missing = [key for key in keys if key not in row]
        if missing:
            raise ValueError(f"{source} row is missing key fields {missing}: {row}")
        key = tuple(row[field] for field in keys)
        if key in output:
            qualifier = "conflicting" if row != output[key] else "identical"
            raise ValueError(f"{qualifier} duplicate in {source}: {dict(zip(keys, key))}")
        output[key] = row
    return list(output.values())


def require_success(rows: Iterable[dict], source: str) -> list[dict]:
    checked = list(rows)
    failed = [row for row in checked if "ok" in row and row["ok"] is not True]
    if failed:
        first = failed[0]
        raise ValueError(
            f"{source} contains {len(failed)} failed rows; first at "
            f"{first.get('_source_path')}:{first.get('_source_line')}"
        )
    missing_label = [row for row in checked if "type_correct" not in row]
    if missing_label:
        raise ValueError(f"{source} contains {len(missing_label)} rows without type_correct")
    invalid = [row for row in checked if int(row["type_correct"]) not in (0, 1)]
    if invalid:
        raise ValueError(f"{source} contains non-binary type_correct values")
    return checked


def assert_cells(
    rows: Sequence[dict], expected: dict[str, tuple[int, int]], source: str
) -> None:
    """Assert ``condition -> (prompt_count, seeds_per_prompt)`` exactly."""
    by_condition: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_condition[str(row["condition"])][str(row["prompt_id"])].append(int(row["seed_idx"]))
    if set(by_condition) != set(expected):
        raise ValueError(
            f"{source} conditions {sorted(by_condition)} != expected {sorted(expected)}"
        )
    for condition, (prompt_count, seeds_per_prompt) in expected.items():
        cells = by_condition[condition]
        if len(cells) != prompt_count:
            raise ValueError(
                f"{source}/{condition} has {len(cells)} prompts, expected {prompt_count}"
            )
        expected_seeds = set(range(seeds_per_prompt))
        bad = {
            prompt_id: sorted(seed_indices)
            for prompt_id, seed_indices in cells.items()
            if set(seed_indices) != expected_seeds or len(seed_indices) != seeds_per_prompt
        }
        if bad:
            prompt_id, seeds = next(iter(bad.items()))
            raise ValueError(
                f"{source}/{condition}/{prompt_id} has invalid seed cell "
                f"({len(seeds)} rows, min={min(seeds)}, max={max(seeds)})"
            )


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n) / denom
    return center - half, center + half


def deployment_success(p: float | np.ndarray, draws: int) -> float | np.ndarray:
    return 1.0 - np.power(1.0 - np.asarray(p), draws)


def restricted_expected_draws(p: float, bound: int) -> float:
    if p <= 0.0:
        return float(bound)
    return float((1.0 - (1.0 - p) ** bound) / p)


def zero_success_upper_bound(n: int, alpha: float = 0.05) -> float:
    if n <= 0:
        raise ValueError("n must be positive")
    return 1.0 - alpha ** (1.0 / n)


def regime(clean_rate: float, edges: tuple[float, float, float] = (1 / 16, 0.25, 0.5)) -> str:
    rare, recoverable, easy = edges
    if clean_rate <= rare:
        return REGIMES[0]
    if clean_rate < recoverable:
        return REGIMES[1]
    if clean_rate < easy:
        return REGIMES[2]
    return REGIMES[3]


def write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    names = list(fieldnames or rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=names, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def prompt_cells(rows: Sequence[dict], population_weights: dict[str, float] | None = None) -> list[dict]:
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    metadata: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (str(row["condition"]), str(row["prompt_id"]))
        grouped[key].append(int(row["type_correct"]))
        metadata[key] = row
    cells = []
    for (condition, prompt_id), values in sorted(grouped.items()):
        row = metadata[(condition, prompt_id)]
        stratum = "vocal" if int(row["requested_vocal"]) else "instrumental"
        selection_bin = str(row.get("selection_bin", "all"))
        cells.append(
            {
                "condition": condition,
                "prompt_id": prompt_id,
                "stratum": stratum,
                "selection_bin": selection_bin,
                "values": np.asarray(values, dtype=np.int8),
                "weight": float((population_weights or {}).get(prompt_id, 1.0)),
            }
        )
    return cells


def weighted_average(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / np.sum(weights))


def stratified_bootstrap(
    cells: Sequence[dict],
    transform,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
    seed_resampling: bool = True,
) -> np.ndarray:
    """Bootstrap prompts within strata, then binary seeds within prompts."""
    if not cells:
        raise ValueError("cannot bootstrap an empty cell set")
    rng = np.random.default_rng(seed)
    by_stratum: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for cell in cells:
        by_stratum[(cell["stratum"], cell["selection_bin"])].append(cell)
    numerator = np.zeros(reps, dtype=np.float64)
    denominator = np.zeros(reps, dtype=np.float64)
    for group_key in sorted(by_stratum):
        group = by_stratum[group_key]
        count = len(group)
        sampled = rng.integers(0, count, size=(reps, count))
        empirical = np.asarray([cell["values"].mean() for cell in group])
        sample_sizes = np.asarray([len(cell["values"]) for cell in group])
        weights = np.asarray([cell["weight"] for cell in group])
        p = empirical[sampled]
        if seed_resampling:
            sizes = sample_sizes[sampled]
            p = rng.binomial(sizes, p) / sizes
        sampled_weights = weights[sampled]
        numerator += np.sum(transform(p) * sampled_weights, axis=1)
        denominator += np.sum(sampled_weights, axis=1)
    return numerator / denominator


def paired_delta_bootstrap(
    baseline_cells: Sequence[dict],
    intervention_cells: Sequence[dict],
    draws: int,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    """Prompt-paired, seed-independent bootstrap for non-CRN conditions."""
    baseline = {cell["prompt_id"]: cell for cell in baseline_cells}
    intervention = {cell["prompt_id"]: cell for cell in intervention_cells}
    if set(intervention) - set(baseline):
        raise ValueError("intervention contains prompts absent from baseline")
    prompt_ids = sorted(intervention)
    if not prompt_ids:
        raise ValueError("no paired prompts")
    rng = np.random.default_rng(seed + draws)
    sampled = rng.integers(0, len(prompt_ids), size=(reps, len(prompt_ids)))
    base_p = np.asarray([baseline[p]["values"].mean() for p in prompt_ids])[sampled]
    int_p = np.asarray([intervention[p]["values"].mean() for p in prompt_ids])[sampled]
    base_n = np.asarray([len(baseline[p]["values"]) for p in prompt_ids])[sampled]
    int_n = np.asarray([len(intervention[p]["values"]) for p in prompt_ids])[sampled]
    # These frozen ATLAS/Stage-3 conditions use different seed families.
    base_boot = rng.binomial(base_n, base_p) / base_n
    int_boot = rng.binomial(int_n, int_p) / int_n
    return np.mean(deployment_success(int_boot, draws) - deployment_success(base_boot, draws), axis=1)


def quantiles(values: np.ndarray) -> tuple[float, float]:
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def n2_population_weights(manifest_rows: Sequence[dict]) -> tuple[dict[str, float], dict[str, int]]:
    prompts = {row["prompt_id"]: row for row in read_jsonl(ROOT / "configs/prompts/held_out.jsonl")}
    raw_by_prompt: dict[str, list[dict]] = defaultdict(list)
    for row in read_jsonl(PH2 / "vocal_presence_raw.jsonl"):
        if row["prompt_id"] in prompts:
            raw_by_prompt[row["prompt_id"]].append(row)
    source_counts: Counter[tuple[str, int]] = Counter()
    for prompt_id, prompt in prompts.items():
        rows = raw_by_prompt[prompt_id]
        if len(rows) != 8:
            raise ValueError(f"{prompt_id} has {len(rows)} Phase-0 candidates, expected 8")
        stratum = prompt["strata"]["vocal_vs_instrumental"]
        requested = int(stratum == "vocal")
        violation_count = sum(
            int(int(float(row["vocal_energy_ratio"]) >= THRESHOLD and not row.get("near_silent", False)) != requested)
            for row in rows
        )
        source_counts[(stratum, violation_count)] += 1
    selected_counts = Counter(
        (row["vocal_stratum"], int(row["selection_bin"])) for row in manifest_rows
    )
    missing_cells = set(source_counts) - set(selected_counts)
    if missing_cells:
        raise ValueError(f"N2 selection omitted source strata: {sorted(missing_cells)}")
    weights = {
        row["prompt_id"]: source_counts[(row["vocal_stratum"], int(row["selection_bin"]))]
        / selected_counts[(row["vocal_stratum"], int(row["selection_bin"]))]
        for row in manifest_rows
    }
    return weights, {f"{stratum}:{bin_id}": count for (stratum, bin_id), count in sorted(source_counts.items())}


def load_primary_data() -> tuple[dict[str, list[dict]], dict[str, float], dict]:
    baseline = require_success(
        unique_rows(load_glob(ATLAS / "ledgers", "bon256_w*.jsonl"), ("prompt_id", "condition", "seed_idx"), "ATLAS baseline"),
        "ATLAS baseline",
    )
    v3 = require_success(
        unique_rows(load_glob(ATLAS / "ledgers", "v3_vocal_w*.jsonl"), ("prompt_id", "condition", "seed_idx"), "ATLAS V3"),
        "ATLAS V3",
    )
    istrong = require_success(
        unique_rows(load_glob(ATLAS / "ledgers", "istrong_instr_w*.jsonl"), ("prompt_id", "condition", "seed_idx"), "ATLAS I-strong"),
        "ATLAS I-strong",
    )
    assert_cells(baseline, {"none": (32, 512)}, "ATLAS baseline")
    assert_cells(v3, {"V3": (17, 128)}, "ATLAS V3")
    assert_cells(istrong, {"I_strong": (15, 128)}, "ATLAS I-strong")

    stage3 = require_success(
        unique_rows(load_glob(STAGE3 / "ledgers", "full64_w*.jsonl"), ("prompt_id", "condition", "seed_idx"), "Stage 3"),
        "Stage 3",
    )
    stage3_expected = {
        "vocal_guidance": (17, 64),
        "vocal_hints": (17, 64),
        "vocal_both": (17, 64),
        "instr_text": (15, 64),
        "instr_sampler": (15, 64),
        "instr_both": (15, 64),
    }
    assert_cells(stage3, stage3_expected, "Stage 3")

    n2_manifest = unique_rows(read_jsonl(N2 / "population_retry_manifest_128.jsonl"), ("prompt_id",), "N2 manifest")
    if len(n2_manifest) != 128:
        raise ValueError(f"N2 manifest has {len(n2_manifest)} prompts, expected 128")
    n2 = require_success(
        unique_rows(load_glob(N2 / "ledgers", "full128_w*.jsonl"), ("prompt_id", "seed_idx"), "N2"),
        "N2",
    )
    for row in n2:
        row["condition"] = "N2_reseed"
    assert_cells(n2, {"N2_reseed": (128, 128)}, "N2")
    weights, source_counts = n2_population_weights(n2_manifest)
    return {
        "atlas_baseline": baseline,
        "atlas_v3": v3,
        "atlas_istrong": istrong,
        "stage3": stage3,
        "n2": n2,
    }, weights, {"n2_source_cell_counts": source_counts, "n2_manifest": n2_manifest}


def make_deployment_tables(data: dict[str, list[dict]], n2_weights: dict[str, float], out_dir: Path) -> tuple[list[dict], list[dict]]:
    scenarios: list[tuple[str, str, list[dict], dict[str, float] | None]] = []
    for name in ("atlas_baseline", "atlas_v3", "atlas_istrong", "stage3", "n2"):
        rows = data[name]
        conditions = sorted({str(row["condition"]) for row in rows})
        for condition in conditions:
            condition_rows = [row for row in rows if str(row["condition"]) == condition]
            strata = sorted({"vocal" if int(row["requested_vocal"]) else "instrumental" for row in condition_rows})
            for stratum in strata:
                subset = [
                    row for row in condition_rows
                    if ("vocal" if int(row["requested_vocal"]) else "instrumental") == stratum
                ]
                scenarios.append((name, condition, subset, n2_weights if name == "n2" else None))

    deployment_rows: list[dict] = []
    secondary_rows: list[dict] = []
    scenario_cells: dict[tuple[str, str, str], list[dict]] = {}
    for dataset, condition, rows, weights in scenarios:
        cells = prompt_cells(rows, weights)
        stratum = cells[0]["stratum"]
        scenario_cells[(dataset, condition, stratum)] = cells
        p = np.asarray([cell["values"].mean() for cell in cells])
        w = np.asarray([cell["weight"] for cell in cells])
        for draws in DEPLOYMENT_N:
            estimate = weighted_average(deployment_success(p, draws), w)
            boot = stratified_bootstrap(cells, lambda x, n=draws: deployment_success(x, n))
            prompt_only = stratified_bootstrap(
                cells,
                lambda x, n=draws: deployment_success(x, n),
                seed=BOOTSTRAP_SEED + 1000 + draws,
                seed_resampling=False,
            )
            low, high = quantiles(boot)
            po_low, po_high = quantiles(prompt_only)
            deployment_rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "stratum": stratum,
                    "prompts": len(cells),
                    "seeds_per_prompt": min(len(cell["values"]) for cell in cells),
                    "population_weighted": int(weights is not None),
                    "draws_N": draws,
                    "deployment_success": estimate,
                    "cluster_bootstrap_ci95_low": low,
                    "cluster_bootstrap_ci95_high": high,
                    "prompt_only_ci95_low": po_low,
                    "prompt_only_ci95_high": po_high,
                    "estimand": "mean_prompt[1-(1-p_hat_i)^N]",
                    "rate_scope": "selected/difficult held-out; not a generic population rate",
                }
            )
        for cell in cells:
            successes = int(cell["values"].sum())
            attempts = len(cell["values"])
            p_hat = successes / attempts
            lo, hi = wilson(successes, attempts)
            secondary_rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "stratum": stratum,
                    "selection_bin": cell["selection_bin"],
                    "prompt_id": cell["prompt_id"],
                    "successes": successes,
                    "attempts": attempts,
                    "p_hat": p_hat,
                    "wilson_ci95_low": lo,
                    "wilson_ci95_high": hi,
                    "inverse_p_if_observed": 1.0 / p_hat if p_hat > 0 else "",
                    "restricted_draws_B16": restricted_expected_draws(p_hat, 16),
                    "restricted_draws_B128": restricted_expected_draws(p_hat, 128),
                    "restricted_draws_B1024": restricted_expected_draws(p_hat, 1024),
                    "zero_success_notation": f"0/{attempts}" if successes == 0 else "",
                    "zero_success_p_upper95": zero_success_upper_bound(attempts) if successes == 0 else "",
                    "wording_constraint": "never convert a zero-success row to expected draws > attempts",
                }
            )

    paired_rows: list[dict] = []
    baseline_by_stratum = {
        stratum: scenario_cells[("atlas_baseline", "none", stratum)]
        for stratum in ("vocal", "instrumental")
    }
    comparisons = [
        ("atlas_v3", "V3", "vocal"),
        ("atlas_istrong", "I_strong", "instrumental"),
    ]
    comparisons.extend(
        ("stage3", condition, "vocal" if condition.startswith("vocal") else "instrumental")
        for condition in sorted({row["condition"] for row in data["stage3"]})
    )
    for dataset, condition, stratum in comparisons:
        intervention = scenario_cells[(dataset, condition, stratum)]
        baseline = baseline_by_stratum[stratum]
        base_index = {cell["prompt_id"]: cell for cell in baseline}
        int_index = {cell["prompt_id"]: cell for cell in intervention}
        for draws in DEPLOYMENT_N:
            prompt_deltas = [
                float(deployment_success(int_index[p]["values"].mean(), draws))
                - float(deployment_success(base_index[p]["values"].mean(), draws))
                for p in sorted(int_index)
            ]
            boot = paired_delta_bootstrap(baseline, intervention, draws)
            low, high = quantiles(boot)
            paired_rows.append(
                {
                    "dataset": dataset,
                    "condition": condition,
                    "stratum": stratum,
                    "prompts": len(prompt_deltas),
                    "draws_N": draws,
                    "prompt_paired_delta": float(np.mean(prompt_deltas)),
                    "cluster_bootstrap_ci95_low": low,
                    "cluster_bootstrap_ci95_high": high,
                    "seed_pairing": "independent seed resampling; prompts paired",
                }
            )

    write_csv(out_dir / "deployment_success_metrics.csv", deployment_rows)
    write_csv(out_dir / "deployment_success_paired_deltas.csv", paired_rows)
    write_csv(out_dir / "prompt_secondary_draw_metrics.csv", secondary_rows)

    summary_rows = []
    by_scenario: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in secondary_rows:
        by_scenario[(row["dataset"], row["condition"], row["stratum"])].append(row)
    for (dataset, condition, stratum), rows in sorted(by_scenario.items()):
        positive = [float(row["inverse_p_if_observed"]) for row in rows if row["inverse_p_if_observed"] != ""]
        summary_rows.append(
            {
                "dataset": dataset,
                "condition": condition,
                "stratum": stratum,
                "prompts": len(rows),
                "prompts_with_success": len(positive),
                "zero_success_prompts": len(rows) - len(positive),
                "median_inverse_p_among_observed": float(np.median(positive)) if positive else "",
                "median_restricted_draws_B16": float(np.median([row["restricted_draws_B16"] for row in rows])),
                "median_restricted_draws_B128": float(np.median([row["restricted_draws_B128"] for row in rows])),
                "median_restricted_draws_B1024": float(np.median([row["restricted_draws_B1024"] for row in rows])),
            }
        )
    write_csv(out_dir / "secondary_draw_summary.csv", summary_rows)
    return deployment_rows, secondary_rows


def make_n2_regime_outputs(data: dict[str, list[dict]], n2_weights: dict[str, float], out_dir: Path) -> list[dict]:
    cells = prompt_cells(data["n2"], n2_weights)
    rng = np.random.default_rng(BOOTSTRAP_SEED + 6000)
    rows = []
    for cell in cells:
        values = cell["values"]
        attempts = len(values)
        p_hat = float(values.mean())
        draws = rng.binomial(attempts, p_hat, size=BOOTSTRAP_REPS) / attempts
        probabilities = {name: float(np.mean([regime(value) == name for value in draws])) for name in REGIMES}
        assigned = regime(p_hat)
        max_probability = max(probabilities.values())
        rows.append(
            {
                "prompt_id": cell["prompt_id"],
                "stratum": cell["stratum"],
                "selection_bin": cell["selection_bin"],
                "successes": int(values.sum()),
                "attempts": attempts,
                "p_hat": p_hat,
                "assigned_regime": assigned,
                **{f"prob_{name}": probabilities[name] for name in REGIMES},
                "max_membership_probability": max_probability,
                "membership_flag": "stable" if max_probability >= 0.80 else "uncertain",
                "population_weight": cell["weight"],
            }
        )
    write_csv(out_dir / "n2_regime_membership_bootstrap.csv", rows)

    edge_specs = {
        "frozen": (1 / 16, 0.25, 0.5),
        "edges_minus_1_over_128": (1 / 16 - 1 / 128, 0.25 - 1 / 128, 0.5 - 1 / 128),
        "edges_plus_1_over_128": (1 / 16 + 1 / 128, 0.25 + 1 / 128, 0.5 + 1 / 128),
    }
    sensitivity = []
    for spec, edges in edge_specs.items():
        counts = Counter(regime(float(row["p_hat"]), edges) for row in rows)
        for name in REGIMES:
            sensitivity.append(
                {
                    "edge_spec": spec,
                    "rare_edge": edges[0],
                    "recoverable_edge": edges[1],
                    "easy_edge": edges[2],
                    "regime": name,
                    "prompt_count": counts[name],
                    "fraction": counts[name] / len(rows),
                }
            )
    write_csv(out_dir / "n2_regime_bin_edge_sensitivity.csv", sensitivity)
    return rows


def make_replication_scatter(data: dict[str, list[dict]], figures_dir: Path, analysis_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    baseline = {cell["prompt_id"]: cell for cell in prompt_cells(data["atlas_baseline"])}
    n2 = {cell["prompt_id"]: cell for cell in prompt_cells(data["n2"])}
    overlap = sorted(set(baseline) & set(n2))
    if not overlap:
        raise ValueError("ATLAS and N2 have no overlapping prompts")
    rows = []
    for prompt_id in overlap:
        atlas_p = float(baseline[prompt_id]["values"].mean())
        n2_p = float(n2[prompt_id]["values"].mean())
        rows.append(
            {
                "prompt_id": prompt_id,
                "stratum": baseline[prompt_id]["stratum"],
                "overlap_prompts": len(overlap),
                "atlas_prompts": len(baseline),
                "n2_prompts": len(n2),
                "atlas_p_512": atlas_p,
                "n2_p_128": n2_p,
                "delta_n2_minus_atlas": n2_p - atlas_p,
            }
        )
    write_csv(analysis_dir / "atlas_n2_replication_scatter.csv", rows)
    x = np.asarray([row["atlas_p_512"] for row in rows])
    y = np.asarray([row["n2_p_128"] for row in rows])
    correlation = float(np.corrcoef(x, y)[0, 1])
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    colors = ["#26734d" if row["stratum"] == "vocal" else "#a3532a" for row in rows]
    ax.scatter(x, y, c=colors, s=38, alpha=0.85, edgecolor="white", linewidth=0.4)
    ax.plot([0, 1], [0, 1], color="#555555", linestyle="--", linewidth=1)
    ax.set(xlabel="ATLAS clean rate (512 seeds)", ylabel="N2 clean rate (128 seeds)", xlim=(-0.02, 1.02), ylim=(-0.02, 1.02))
    ax.set_title(f"ATLAS to N2 replication ({len(overlap)} overlapping prompts, r={correlation:.3f})")
    ax.grid(alpha=0.18)
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(figures_dir / f"atlas_n2_replication_scatter.{suffix}", dpi=220)
    plt.close(fig)


def make_primary_figure(deployment_rows: Sequence[dict], secondary_rows: Sequence[dict], figures_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    fig, (ax_ecdf, ax_forest) = plt.subplots(1, 2, figsize=(12.2, 6.5), gridspec_kw={"width_ratios": [1, 1.28]})
    forest_rows = [row for row in secondary_rows if row["dataset"] == "n2" and row["condition"] == "N2_reseed"]
    for stratum, color in (("vocal", "#26734d"), ("instrumental", "#a3532a")):
        values = np.sort([float(row["p_hat"]) for row in forest_rows if row["stratum"] == stratum])
        ax_ecdf.step(values, np.arange(1, len(values) + 1) / len(values), where="post", label=stratum, color=color, linewidth=2)
    for edge in (1 / 16, 0.25, 0.5):
        ax_ecdf.axvline(edge, color="#777777", linestyle=":", linewidth=1)
    ax_ecdf.set(xlabel="Per-prompt clean rate", ylabel="Empirical CDF", xlim=(-0.01, 1.01), ylim=(0, 1.01))
    ax_ecdf.set_title("N2 selected difficult-set ECDF")
    ax_ecdf.legend(frameon=False)
    ax_ecdf.grid(alpha=0.18)

    ordered = sorted(forest_rows, key=lambda row: float(row["p_hat"]))
    y = np.arange(len(ordered))
    p = np.asarray([float(row["p_hat"]) for row in ordered])
    lo = np.asarray([float(row["wilson_ci95_low"]) for row in ordered])
    hi = np.asarray([float(row["wilson_ci95_high"]) for row in ordered])
    colors = ["#26734d" if row["stratum"] == "vocal" else "#a3532a" for row in ordered]
    ax_forest.hlines(y, lo, hi, color="#a8a8a8", linewidth=0.6)
    ax_forest.scatter(p, y, c=colors, s=12, zorder=2)
    for edge in (1 / 16, 0.25, 0.5):
        ax_forest.axvline(edge, color="#777777", linestyle=":", linewidth=1)
    ax_forest.set(xlabel="Clean rate with per-prompt Wilson 95% CI", ylabel="Prompts sorted by clean rate", xlim=(-0.01, 1.01), ylim=(-1, len(ordered)))
    ax_forest.set_yticks([])
    ax_forest.set_title("N2 prompt forest")
    ax_forest.grid(axis="x", alpha=0.18)
    fig.suptitle("Figure 2 v2: retry regimes on the selected difficult held-out set", fontsize=13)
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(figures_dir / f"fig2_retry_regime_ecdf_forest.{suffix}", dpi=220)
    plt.close(fig)

    figure_data = [row for row in deployment_rows if int(row["draws_N"]) == 8]
    write_csv(figures_dir / "fig2_deployment_success_N8.csv", figure_data)


def make_sa3_threshold_sensitivity(analysis_dir: Path, figures_dir: Path) -> dict:
    score_path = SA3 / "prevalence_full500/SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"
    rows = require_success(unique_rows(read_jsonl(score_path), ("row_index",), "SA3 full-500 scores"), "SA3 full-500 scores")
    if len(rows) != 4000:
        raise ValueError(f"SA3 full-500 score ledger has {len(rows)} rows, expected 4000")
    ratios = defaultdict(list)
    for row in rows:
        ratios[row["vocal_stratum"]].append(float(row["vocal_energy_ratio"]))
    medians = {stratum: float(np.median(values)) for stratum, values in ratios.items()}
    midpoint = (medians["vocal"] + medians["instrumental"]) / 2.0
    thresholds = sorted({0.10, 0.15, THRESHOLD, 0.20, 0.25, midpoint})
    output = []
    for threshold in thresholds:
        for stratum in ("vocal", "instrumental"):
            subset = [row for row in rows if row["vocal_stratum"] == stratum]
            requested = int(stratum == "vocal")
            clean = [int(int(float(row["vocal_energy_ratio"]) >= threshold and not row.get("near_silent", False)) == requested) for row in subset]
            output.append(
                {
                    "threshold": threshold,
                    "threshold_label": "strata_median_midpoint" if math.isclose(threshold, midpoint) else ("canonical" if math.isclose(threshold, THRESHOLD) else "sensitivity"),
                    "stratum": stratum,
                    "rows": len(subset),
                    "stratum_ratio_median": medians[stratum],
                    "clean_rate": float(np.mean(clean)),
                    "pooled_seed_level_descriptive_only": 1,
                }
            )
    write_csv(analysis_dir / "sa3_threshold_sensitivity.csv", output)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    for stratum, color in (("vocal", "#26734d"), ("instrumental", "#a3532a")):
        subset = [row for row in output if row["stratum"] == stratum]
        ax.plot([row["threshold"] for row in subset], [row["clean_rate"] for row in subset], marker="o", color=color, label=stratum)
    ax.axvline(THRESHOLD, color="#444444", linestyle="--", linewidth=1, label="canonical 0.1791")
    ax.axvline(midpoint, color="#8255a6", linestyle=":", linewidth=1.5, label="SA3 median midpoint")
    ax.set(xlabel="Demucs vocal-energy threshold", ylabel="Pooled clean rate (descriptive only)", ylim=(0, 1.02))
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.18)
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(figures_dir / f"sa3_threshold_sensitivity.{suffix}", dpi=220)
    plt.close(fig)
    return {"instrumental_median": medians["instrumental"], "vocal_median": medians["vocal"], "midpoint": midpoint}


def old_vs_v2(data: dict[str, list[dict]], analysis_dir: Path) -> tuple[str, list[dict]]:
    old = json.loads((PAPER / "execution_20260707/T21_efficiency_metrics.json").read_text())
    stage3_old = json.loads((STAGE3 / "full64_final_summary.json").read_text())
    n2_old = json.loads((N2 / "full128_regime_readout.json").read_text())

    def prompt_mean(rows: Sequence[dict], requested: int | None = None) -> float:
        selected = [row for row in rows if requested is None or int(row["requested_vocal"]) == requested]
        cells = prompt_cells(selected)
        return float(np.mean([cell["values"].mean() for cell in cells]))

    baseline_vocal = prompt_mean(data["atlas_baseline"], 1)
    baseline_instr = prompt_mean(data["atlas_baseline"], 0)
    base_cells = {cell["prompt_id"]: cell for cell in prompt_cells(data["atlas_baseline"])}
    v3_cells = {cell["prompt_id"]: cell for cell in prompt_cells(data["atlas_v3"])}
    i_cells = {cell["prompt_id"]: cell for cell in prompt_cells(data["atlas_istrong"])}
    values: list[tuple[str, float, float]] = [
        ("baseline_vocal_prompt_mean", old["baseline_vocal_mean"], baseline_vocal),
        ("baseline_instrumental_prompt_mean", old["baseline_instrumental_mean"], baseline_instr),
        ("V3_prompt_paired_delta", old["v3_delta_mean"], float(np.mean([v3_cells[p]["values"].mean() - base_cells[p]["values"].mean() for p in v3_cells]))),
        ("I_strong_prompt_paired_delta", old["istrong_delta_mean"], float(np.mean([i_cells[p]["values"].mean() - base_cells[p]["values"].mean() for p in i_cells]))),
    ]
    for condition, summary in stage3_old["condition_summary"].items():
        condition_rows = [row for row in data["stage3"] if row["condition"] == condition]
        values.append((f"stage3_{condition}_pooled_rate", float(summary["type_correct_rate"]), float(np.mean([row["type_correct"] for row in condition_rows]))))
    n2_old_mean = sum(row["clean_count"] for row in n2_old["prompt_rows"]) / n2_old["rows"]
    values.append(("N2_pooled_seed_rate_descriptive_only", n2_old_mean, float(np.mean([row["type_correct"] for row in data["n2"]]))))
    rows = []
    escalated = False
    for metric, old_value, v2_value in values:
        difference = v2_value - old_value
        flag = abs(difference) > 0.01
        escalated |= flag
        rows.append({"metric": metric, "old_value": old_value, "v2_value": v2_value, "difference": difference, "abs_difference_gt_0_01": int(flag)})
    status = "DIFF_ESCALATED" if escalated else "PASS"
    lines = [
        "# Old vs v2 Publication Number Diff",
        "",
        f"PUBLICATION_STATS_V2_STATUS = {status}",
        "",
        "Shared per-try quantities are compared below. The D1 deployment-success",
        "estimand has no old counterpart; retiring `1/mean(p)` is an intentional",
        "estimand correction, not a numerical discrepancy.",
        "",
        "| Metric | Old | v2 | Difference | Escalate |",
        "|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['metric']} | {row['old_value']:.9f} | {row['v2_value']:.9f} | {row['difference']:+.9f} | {'YES' if row['abs_difference_gt_0_01'] else 'no'} |")
    lines += [
        "",
        "No old figure or old metrics file was modified.",
        "Pooled seed-level rates are descriptive only; prompt-level estimands are primary.",
    ]
    (analysis_dir / "OLD_VS_V2_PUBLICATION_NUMBER_DIFF.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_csv(analysis_dir / "old_vs_v2_publication_number_diff.csv", rows)
    return status, rows


def write_report(
    status: str,
    deployment_rows: Sequence[dict],
    secondary_rows: Sequence[dict],
    n2_rows: Sequence[dict],
    sa3_threshold: dict,
    source_meta: dict,
    analysis_dir: Path,
) -> None:
    zero_rows = [row for row in secondary_rows if int(row["successes"]) == 0]
    n2_counts = Counter(row["assigned_regime"] for row in n2_rows)
    uncertain = sum(row["membership_flag"] == "uncertain" for row in n2_rows)
    lines = [
        "# Publication Statistics v2",
        "",
        f"PUBLICATION_STATS_V2_STATUS = {status}",
        "",
        "## Frozen Estimands",
        "",
        "Primary deployment success is `S_N = mean_prompt[1-(1-p_hat_i)^N]`",
        "for N in {4, 5, 8, 16}. The legacy `1/mean(p)` quantity is retired.",
        "Two-stage cluster-bootstrap intervals use 10,000 replicates, resampling",
        "prompts within vocal/instrumental and selection-bin strata and then seeds",
        "within prompts. N2 source-population cell weights are reapplied in every",
        "replicate. Prompt-only intervals are provided as robustness checks.",
        "",
        "## Integrity Checks",
        "",
        "- ATLAS baseline: 32 prompts x 512 seeds.",
        "- ATLAS V3: 17 prompts x 128 seeds; I-strong: 15 x 128.",
        "- Stage 3: 6,144 successful rows across the six frozen conditions.",
        "- N2: 128 prompts x 128 seeds; sampling cells reconstructed from all 256 held-out prompts.",
        "- Duplicate keys and failed rows are fatal; none were accepted.",
        "",
        "## N2 Regimes",
        "",
        f"Frozen plug-in counts: `{dict(n2_counts)}`. Bootstrap membership is",
        f"uncertain (<0.80 maximum membership probability) for {uncertain}/128 prompts.",
        "The primary Figure 2 object is the ECDF plus per-prompt Wilson forest, not",
        "a pooled seed-rate bar chart.",
        "",
        "## Secondary Draw Metrics",
        "",
        f"There are {len(zero_rows)} zero-success prompt-condition cells. Each is",
        "reported as `0/m` with a one-sided 95% upper confidence bound on p. The",
        "package never converts those observations into an 'expected draws > m' claim.",
        "",
        "## SA3 Threshold Sensitivity",
        "",
        f"SA3 instrumental/vocal median Demucs ratios are {sa3_threshold['instrumental_median']:.6f}",
        f"and {sa3_threshold['vocal_median']:.6f}; their midpoint is {sa3_threshold['midpoint']:.6f}.",
        "This is model-specific sensitivity analysis. It is not a calibrated human threshold,",
        "and all pooled SA3 seed rates are labeled descriptive-only.",
        "",
        "## Wording Constraints",
        "",
        "- These are selected/difficult-test-set rates, not generic population rates.",
        "- Use 'rare / impractical to retry', never 'impossible'.",
        "- Do not write `1/mean(p)` as expected draws.",
        "- Do not infer human label validity from the automatic detector.",
        "",
        "## Artifacts",
        "",
        "- `paper_prep/analysis_v2/deployment_success_metrics.csv`",
        "- `paper_prep/analysis_v2/deployment_success_paired_deltas.csv`",
        "- `paper_prep/analysis_v2/prompt_secondary_draw_metrics.csv`",
        "- `paper_prep/analysis_v2/n2_regime_membership_bootstrap.csv`",
        "- `paper_prep/analysis_v2/n2_regime_bin_edge_sensitivity.csv`",
        "- `paper_prep/analysis_v2/atlas_n2_replication_scatter.csv`",
        "- `paper_prep/analysis_v2/sa3_threshold_sensitivity.csv`",
        "- `paper_prep/figures_v2/fig2_retry_regime_ecdf_forest.{png,pdf}`",
        "- `paper_prep/figures_v2/atlas_n2_replication_scatter.{png,pdf}`",
    ]
    (analysis_dir / "PUBLICATION_STATS_V2_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (analysis_dir / "ANALYSIS_PROVENANCE.json").write_text(
        json.dumps(
            {
                "bootstrap_reps": BOOTSTRAP_REPS,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "deployment_N": DEPLOYMENT_N,
                "draw_bounds": DRAW_BOUNDS,
                "threshold": THRESHOLD,
                **source_meta,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, default=PAPER / "analysis_v2")
    parser.add_argument("--figures-dir", type=Path, default=PAPER / "figures_v2")
    args = parser.parse_args()
    args.analysis_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)

    data, n2_weights, source_meta = load_primary_data()
    deployment_rows, secondary_rows = make_deployment_tables(data, n2_weights, args.analysis_dir)
    n2_rows = make_n2_regime_outputs(data, n2_weights, args.analysis_dir)
    make_primary_figure(deployment_rows, secondary_rows, args.figures_dir)
    make_replication_scatter(data, args.figures_dir, args.analysis_dir)
    sa3_threshold = make_sa3_threshold_sensitivity(args.analysis_dir, args.figures_dir)
    status, _ = old_vs_v2(data, args.analysis_dir)
    write_report(status, deployment_rows, secondary_rows, n2_rows, sa3_threshold, source_meta, args.analysis_dir)
    print(json.dumps({"status": status, "deployment_rows": len(deployment_rows), "n2_prompts": len(n2_rows)}, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
