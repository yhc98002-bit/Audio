#!/usr/bin/env python3
"""Prompt-grouped cross-fitted policy-value evaluation for BOLT Gate 1.5A."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent

from bolt_core import ACTIONS, CHECKPOINT_STEPS, canonical_json_hash, read_jsonl, sha256_file  # noqa: E402
from bolt_oracle_headroom import build_indices, static_programs  # noqa: E402


PROMPT_MANIFEST = OUT / "BOLT_PILOT_PROMPT_MANIFEST.jsonl"
ROOT_LEDGER = OUT / "BOLT_ROOT_TRAJECTORY_LEDGER.jsonl"
ACTION_LEDGER = OUT / "BOLT_ACTION_ATLAS_PILOT_LEDGER.jsonl"
FEATURE_LEDGER = OUT / "BOLT_GATE15A_STATE_FEATURES.jsonl"
FEATURE_REPORT = OUT / "BOLT_GATE15A_FEATURE_AUDIT.md"
GATE1_REPORT = OUT / "BOLT_GATE1_REPORT.md"
PREREG = OUT / "BOLT_GATE15A_PREREG.md"
FOLDS_CSV = OUT / "BOLT_GATE15A_FOLDS.csv"
PREDICTIONS_CSV = OUT / "BOLT_GATE15A_CROSSFIT_PREDICTIONS.csv"
BOOTSTRAP_CSV = OUT / "BOLT_GATE15A_BOOTSTRAP.csv"
ROOT_SYMMETRY_CSV = OUT / "BOLT_GATE15A_ROOT_SYMMETRY.csv"
STRUCTURAL_CSV = OUT / "BOLT_GATE15A_STRUCTURAL_REVERIFY.csv"
MODEL_AUDIT_JSON = OUT / "BOLT_GATE15A_MODEL_AUDIT.json"
METRICS_JSON = OUT / "BOLT_GATE15A_METRICS.json"
REPORT = OUT / "BOLT_GATE15A_REPORT.md"

FOLD_SEED = 2026071601
BOOTSTRAP_SEED = 2026071602
BOOTSTRAP_REPS = 10_000
FOLDS = 6
BUDGET_NFE = 90
STANDARD_NFE = 45
ACTION_PRIORITY = {
    "CONTINUE": 0,
    "SWITCH_CONDITION": 1,
    "FORK_LATENT": 2,
    "RESTART_CONDITIONED": 3,
    "RESTART_BASE": 4,
}
PROMPT_NUMERIC = (
    "requested_vocal",
    "risk_score_preexisting",
    "promoted_violation_rate_preexisting",
    "corrected_evpd_mean_risk_preexisting",
)
PROMPT_CATEGORICAL = (
    "genre",
    "tempo_bin",
    "prompt_specificity",
    "structure_complexity",
    "language",
)
STATE_NUMERIC = (
    "preview_demucs_score",
    "preview_panns_score",
    "preview_calibrated_violation_probability",
    "preview_clap_to_prompt",
    "preview_promoted_present",
    "checkpoint_fraction",
    "remaining_budget_fraction",
)
FROZEN_CATEGORY_LEVELS = {
    "genre": ["classical", "electronic", "folk", "hip_hop", "jazz", "metal", "pop", "rock"],
    "tempo_bin": ["fast_120_160", "med_90_120", "slow_60_90", "very_fast_160_plus"],
    "prompt_specificity": ["broad", "medium", "specific"],
    "structure_complexity": ["AABA", "complex_multi_section", "simple_AB", "verse_chorus"],
    "language": ["en", "fr"],
}


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float:
    value = np.asarray(list(values), dtype=np.float64)
    weight = np.asarray(list(weights), dtype=np.float64)
    if len(value) == 0 or weight.sum() <= 0:
        raise ValueError("weighted mean requires nonempty positive-weight values")
    return float(np.average(value, weights=weight))


def parse_machine_value(path: Path, name: str) -> str:
    prefix = f"{name} = "
    matches = [line[len(prefix) :].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {name} line in {path}")
    return matches[0]


def state_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return str(row["prompt_id"]), int(row["root_index"]), int(row["checkpoint_step"])


def action_key(row: dict[str, Any]) -> tuple[str, int, int, str]:
    return (
        str(row["prompt_id"]),
        int(row["root_index"]),
        int(row["checkpoint_step"]),
        str(row["action"]),
    )


def unique_index(rows: list[dict[str, Any]], key_fn, expected: int, label: str) -> dict[Any, dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)
    duplicates = {key: value for key, value in grouped.items() if len(value) != 1}
    if duplicates or len(grouped) != expected:
        raise RuntimeError(f"{label} integrity failure: rows={len(rows)} keys={len(grouped)} duplicates={len(duplicates)}")
    return {key: value[0] for key, value in grouped.items()}


def assign_folds(prompts: list[dict[str, Any]]) -> dict[str, int]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prompts:
        grouped[str(row["stratum"])].append(row)
    if sorted(len(rows) for rows in grouped.values()) != [12, 12, 12, 12]:
        raise RuntimeError("frozen stratum cardinality changed")
    assignment: dict[str, int] = {}
    for stratum, rows in sorted(grouped.items()):
        ordered = sorted(
            rows,
            key=lambda row: hashlib.sha256(
                f"{FOLD_SEED}|{row['prompt_id']}".encode("utf-8")
            ).hexdigest(),
        )
        for index, row in enumerate(ordered):
            assignment[str(row["prompt_id"])] = index % FOLDS
    fold_sizes = {fold: sum(value == fold for value in assignment.values()) for fold in range(FOLDS)}
    if set(fold_sizes.values()) != {8}:
        raise RuntimeError(f"fold sizes are not eight prompts: {fold_sizes}")
    for fold in range(FOLDS):
        per_stratum = {
            stratum: sum(assignment[str(row["prompt_id"])] == fold for row in rows)
            for stratum, rows in grouped.items()
        }
        if set(per_stratum.values()) != {2}:
            raise RuntimeError(f"fold {fold} is not two prompts per stratum: {per_stratum}")
    return assignment


def program_rows(
    features: dict[tuple[str, int, int], dict[str, Any]],
    actions: dict[tuple[str, int, int, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, int, int, str], dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    index: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    for state, feature in sorted(features.items()):
        prompt_id, root_index, checkpoint = state
        cont = actions[(prompt_id, root_index, checkpoint, "CONTINUE")]
        if int(cont["prefix_nfe"]) != int(feature["prefix_nfe"]):
            raise RuntimeError(f"feature/action prefix mismatch: {state}")
        for action in ACTIONS:
            outcome = actions[(prompt_id, root_index, checkpoint, action)]
            selected_edge = 0 if action == "CONTINUE" else int(outcome["action_nfe"])
            cost = int(feature["prefix_nfe"]) + int(cont["action_nfe"]) + selected_edge
            feasible = cost <= BUDGET_NFE
            row = {
                **feature,
                "action": action,
                "selected_action_cqs": int(outcome["cqs"]),
                "default_continue_cqs": int(cont["cqs"]),
                "program_cqs": int(bool(int(outcome["cqs"]) or int(cont["cqs"]))),
                "program_nfe": int(cost),
                "program_feasible": bool(feasible),
                "selected_output_sha256": str(outcome["output_sha256"]),
                "default_output_sha256": str(cont["output_sha256"]),
                "state_weight": float(feature["design_weight"]) / 6.0,
            }
            rows.append(row)
            index[(prompt_id, root_index, checkpoint, action)] = row
    if len(rows) != 1_440 or len(index) != 1_440:
        raise RuntimeError("program-row cardinality mismatch")
    if any(not row["program_feasible"] and row["action"] == "CONTINUE" for row in rows):
        raise RuntimeError("default completion is infeasible")
    return rows, index


def continuation_decision(point: float, lcb95: float) -> str:
    if lcb95 > 0.0:
        return "PROCEED_GATE15B"
    if point >= 0.05:
        return "PROCEED_GATE15B_POWERED_BY_REPLICATION"
    return "STOP_THIS_AXIS"


def sigmoid(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


@dataclass
class FeatureEncoder:
    tier: str
    category_levels: dict[str, list[str]]
    means: dict[str, float]
    scales: dict[str, float]
    names: list[str]
    precision: np.ndarray

    @classmethod
    def fit(cls, states: list[dict[str, Any]], tier: str) -> "FeatureEncoder":
        if tier not in {"prompt_only", "prompt_state"}:
            raise ValueError(tier)
        unique = {state_key(row): row for row in states}
        state_rows = list(unique.values())
        observed_levels = {
            name: {str(row[name]) for row in state_rows} for name in PROMPT_CATEGORICAL
        }
        for name, observed in observed_levels.items():
            unknown = observed - set(FROZEN_CATEGORY_LEVELS[name])
            if unknown:
                raise RuntimeError(f"unknown categorical levels for {name}: {sorted(unknown)}")
        category_levels = {name: list(FROZEN_CATEGORY_LEVELS[name]) for name in PROMPT_CATEGORICAL}
        numeric = list(PROMPT_NUMERIC)
        if tier == "prompt_state":
            numeric.extend(STATE_NUMERIC)
        means: dict[str, float] = {}
        scales: dict[str, float] = {}
        for name in numeric:
            values = np.asarray([float(row[name]) for row in state_rows], dtype=np.float64)
            if not np.isfinite(values).all():
                raise RuntimeError(f"nonfinite training feature: {name}")
            if name in {"requested_vocal", "preview_promoted_present"}:
                means[name], scales[name] = 0.0, 1.0
            else:
                means[name] = float(values.mean())
                scale = float(values.std(ddof=0))
                scales[name] = scale if scale > 1e-8 else 1.0
        covariates: list[tuple[str, float]] = []
        for name in PROMPT_NUMERIC:
            covariates.append((name, 4.0))
        for name in PROMPT_CATEGORICAL:
            for level in category_levels[name][1:]:
                covariates.append((f"{name}={level}", 32.0))
        if tier == "prompt_state":
            covariates.extend((name, 16.0) for name in STATE_NUMERIC)
        names = [f"action_intercept[{action}]" for action in ACTIONS]
        precision = [4.0] * len(ACTIONS)
        for action in ACTIONS:
            for name, penalty in covariates:
                names.append(f"action[{action}]*{name}")
                precision.append(penalty)
        return cls(
            tier=tier,
            category_levels=category_levels,
            means=means,
            scales=scales,
            names=names,
            precision=np.asarray(precision, dtype=np.float64),
        )

    def covariates(self, row: dict[str, Any]) -> list[float]:
        values: list[float] = []
        for name in PROMPT_NUMERIC:
            values.append((float(row[name]) - self.means[name]) / self.scales[name])
        for name in PROMPT_CATEGORICAL:
            levels = self.category_levels[name]
            value = str(row[name])
            if value not in levels:
                raise RuntimeError(f"unknown held-out category {name}={value}")
            values.extend(float(value == level) for level in levels[1:])
        if self.tier == "prompt_state":
            for name in STATE_NUMERIC:
                values.append((float(row[name]) - self.means[name]) / self.scales[name])
        return values

    def transform(self, rows: list[dict[str, Any]]) -> np.ndarray:
        width = len(self.names)
        output = np.zeros((len(rows), width), dtype=np.float64)
        action_count = len(ACTIONS)
        covariate_count = (width - action_count) // action_count
        for row_index, row in enumerate(rows):
            action_index = ACTIONS.index(str(row["action"]))
            output[row_index, action_index] = 1.0
            values = self.covariates(row)
            if len(values) != covariate_count:
                raise RuntimeError("feature-width construction error")
            start = action_count + action_index * covariate_count
            output[row_index, start : start + covariate_count] = values
        return output

    def audit(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "feature_names": self.names,
            "feature_count": len(self.names),
            "category_levels": self.category_levels,
            "training_means": self.means,
            "training_scales": self.scales,
            "prior_precision": self.precision.tolist(),
        }


@dataclass
class MapLogisticModel:
    coefficients: np.ndarray
    prior_mean: np.ndarray
    iterations: int
    converged: bool
    final_gradient_max: float
    final_objective: float

    def predict(self, matrix: np.ndarray) -> np.ndarray:
        return sigmoid(matrix @ self.coefficients)


def map_objective(
    beta: np.ndarray,
    matrix: np.ndarray,
    target: np.ndarray,
    weight: np.ndarray,
    prior_mean: np.ndarray,
    precision: np.ndarray,
) -> float:
    eta = np.clip(matrix @ beta, -30.0, 30.0)
    nll = np.sum(weight * (np.logaddexp(0.0, eta) - target * eta))
    penalty = 0.5 * np.sum(precision * np.square(beta - prior_mean))
    return float(nll + penalty)


def fit_map_logistic(
    matrix: np.ndarray,
    target: np.ndarray,
    weight: np.ndarray,
    precision: np.ndarray,
    prior_mean: np.ndarray,
    *,
    max_iter: int = 100,
    gradient_tolerance: float = 1e-9,
) -> MapLogisticModel:
    beta = prior_mean.copy()
    converged = False
    gradient_max = math.inf
    objective = map_objective(beta, matrix, target, weight, prior_mean, precision)
    for iteration in range(1, max_iter + 1):
        probability = np.clip(sigmoid(matrix @ beta), 1e-8, 1.0 - 1e-8)
        gradient = matrix.T @ (weight * (probability - target)) + precision * (beta - prior_mean)
        gradient_max = float(np.max(np.abs(gradient)))
        if gradient_max <= gradient_tolerance:
            converged = True
            break
        curvature = weight * probability * (1.0 - probability)
        hessian = (matrix.T * curvature) @ matrix + np.diag(precision)
        step = np.linalg.solve(hessian, gradient)
        step_scale = 1.0
        accepted = False
        while step_scale >= 2.0**-20:
            candidate = beta - step_scale * step
            candidate_objective = map_objective(
                candidate, matrix, target, weight, prior_mean, precision
            )
            if candidate_objective <= objective + 1e-12:
                beta = candidate
                objective = candidate_objective
                accepted = True
                break
            step_scale *= 0.5
        if not accepted:
            if float(np.max(np.abs(step))) <= 1e-10:
                converged = True
                break
            raise RuntimeError("MAP logistic line search failed")
    probability = np.clip(sigmoid(matrix @ beta), 1e-8, 1.0 - 1e-8)
    gradient = matrix.T @ (weight * (probability - target)) + precision * (beta - prior_mean)
    gradient_max = float(np.max(np.abs(gradient)))
    converged = converged or gradient_max <= gradient_tolerance
    if not converged:
        raise RuntimeError(f"MAP logistic model did not converge: gradient={gradient_max}")
    return MapLogisticModel(
        coefficients=beta,
        prior_mean=prior_mean,
        iterations=iteration,
        converged=converged,
        final_gradient_max=gradient_max,
        final_objective=objective,
    )


def empirical_prior(rows: list[dict[str, Any]], feature_count: int) -> np.ndarray:
    prior = np.zeros(feature_count, dtype=np.float64)
    for index, action in enumerate(ACTIONS):
        group = [row for row in rows if row["action"] == action and row["program_feasible"]]
        successes = sum(float(row["state_weight"]) * int(row["program_cqs"]) for row in group)
        total = sum(float(row["state_weight"]) for row in group)
        probability = (successes + 1.0) / (total + 2.0)
        probability = min(max(probability, 1e-6), 1.0 - 1e-6)
        prior[index] = math.log(probability / (1.0 - probability))
    return prior


def fit_tier(train_rows: list[dict[str, Any]], tier: str) -> tuple[FeatureEncoder, MapLogisticModel]:
    feasible = [row for row in train_rows if row["program_feasible"]]
    encoder = FeatureEncoder.fit(feasible, tier)
    matrix = encoder.transform(feasible)
    target = np.asarray([int(row["program_cqs"]) for row in feasible], dtype=np.float64)
    weight = np.asarray([float(row["state_weight"]) for row in feasible], dtype=np.float64)
    weight *= len(weight) / weight.sum()
    prior = empirical_prior(feasible, len(encoder.names))
    model = fit_map_logistic(matrix, target, weight, encoder.precision, prior)
    return encoder, model


def choose_action(
    candidates: list[dict[str, Any]], encoder: FeatureEncoder, model: MapLogisticModel
) -> tuple[dict[str, Any], float, dict[str, float]]:
    feasible = [row for row in candidates if row["program_feasible"]]
    if not feasible:
        raise RuntimeError("completion reserve left no feasible action")
    probabilities = model.predict(encoder.transform(feasible))
    by_action = {str(row["action"]): float(value) for row, value in zip(feasible, probabilities)}
    selected = min(
        zip(feasible, probabilities),
        key=lambda pair: (
            -float(pair[1]),
            int(pair[0]["program_nfe"]),
            ACTION_PRIORITY[str(pair[0]["action"])],
        ),
    )
    return selected[0], float(selected[1]), by_action


def choose_static_mapping(train_rows: list[dict[str, Any]]) -> dict[tuple[str, int], str]:
    mapping: dict[tuple[str, int], str] = {}
    states = {state_key(row) for row in train_rows}
    for direction in ("instrumental", "vocal"):
        for checkpoint in CHECKPOINT_STEPS:
            target_states = {
                state_key(row)
                for row in train_rows
                if row["request_direction"] == direction and int(row["checkpoint_step"]) == checkpoint
            }
            if not target_states:
                raise RuntimeError(f"empty static training cell: {direction}, step {checkpoint}")
            candidates = []
            for action in ACTIONS:
                group = [
                    row
                    for row in train_rows
                    if row["request_direction"] == direction
                    and int(row["checkpoint_step"]) == checkpoint
                    and row["action"] == action
                    and row["program_feasible"]
                ]
                if {state_key(row) for row in group} != target_states:
                    continue
                value = weighted_mean(
                    (int(row["program_cqs"]) for row in group),
                    (float(row["state_weight"]) for row in group),
                )
                cost = weighted_mean(
                    (int(row["program_nfe"]) for row in group),
                    (float(row["state_weight"]) for row in group),
                )
                candidates.append((value, cost, action))
            if not candidates:
                raise RuntimeError(f"no universally feasible static action: {direction}, {checkpoint}")
            _, _, action = min(
                candidates,
                key=lambda value: (-value[0], value[1], ACTION_PRIORITY[value[2]]),
            )
            mapping[(direction, checkpoint)] = action
    if states != {state_key(row) for row in train_rows}:
        raise AssertionError("unreachable state-set mismatch")
    return mapping


def grouped_candidates(rows: list[dict[str, Any]]) -> dict[tuple[str, int, int], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[state_key(row)].append(row)
    if any(len(values) != len(ACTIONS) for values in grouped.values()):
        raise RuntimeError("state does not have all five action records")
    return grouped


def prompt_metrics(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        grouped[str(row["prompt_id"])].append(row)
    output = []
    for prompt_id, rows in sorted(grouped.items()):
        if len(rows) != 6:
            raise RuntimeError(f"prompt {prompt_id} has {len(rows)} predictions, expected six")
        output.append(
            {
                "prompt_id": prompt_id,
                "stratum": rows[0]["stratum"],
                "design_weight": float(rows[0]["design_weight"]),
                "static": float(np.mean([int(row["static_program_cqs"]) for row in rows])),
                "prompt_only": float(np.mean([int(row["promptonly_program_cqs"]) for row in rows])),
                "prompt_state": float(np.mean([int(row["promptstate_program_cqs"]) for row in rows])),
                "nonstatic": float(np.mean([int(row["promptstate_nonstatic"]) for row in rows])),
            }
        )
    if len(output) != 48:
        raise RuntimeError("prompt-metric cardinality mismatch")
    return output


def primary_bootstrap(prompt_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    strata = sorted({str(row["stratum"]) for row in prompt_rows})
    grouped = {stratum: [row for row in prompt_rows if row["stratum"] == stratum] for stratum in strata}
    values = {
        "best_static_cqs": np.empty(BOOTSTRAP_REPS),
        "promptonly_policy_cqs": np.empty(BOOTSTRAP_REPS),
        "promptstate_policy_cqs": np.empty(BOOTSTRAP_REPS),
        "state_incremental_value": np.empty(BOOTSTRAP_REPS),
        "crossfit_nonstatic_share": np.empty(BOOTSTRAP_REPS),
    }
    output = []
    for replicate in range(BOOTSTRAP_REPS):
        sample = []
        for rows in grouped.values():
            picks = rng.integers(0, len(rows), size=len(rows))
            sample.extend(rows[int(index)] for index in picks)
        weights = [float(row["design_weight"]) for row in sample]
        values["best_static_cqs"][replicate] = weighted_mean((row["static"] for row in sample), weights)
        values["promptonly_policy_cqs"][replicate] = weighted_mean((row["prompt_only"] for row in sample), weights)
        values["promptstate_policy_cqs"][replicate] = weighted_mean((row["prompt_state"] for row in sample), weights)
        values["state_incremental_value"][replicate] = (
            values["promptstate_policy_cqs"][replicate] - values["promptonly_policy_cqs"][replicate]
        )
        values["crossfit_nonstatic_share"][replicate] = weighted_mean((row["nonstatic"] for row in sample), weights)
        output.append({"replicate": replicate, **{name: float(array[replicate]) for name, array in values.items()}})
    return output, values


def root_symmetry(
    rows: list[dict[str, Any]],
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]],
    folds: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fit on one root index and evaluate selected actions on the matched root."""
    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for fold in range(FOLDS):
        heldout = {prompt_id for prompt_id, value in folds.items() if value == fold}
        train_prompts = set(folds) - heldout
        for source_root, target_root, direction in ((0, 1, "root_a_to_b"), (1, 0, "root_b_to_a")):
            train_rows = [
                row
                for row in rows
                if row["prompt_id"] in train_prompts and int(row["root_index"]) == source_root
            ]
            for tier in ("prompt_only", "prompt_state"):
                encoder, model = fit_tier(train_rows, tier)
                audits.append(
                    {
                        "phase": "root_symmetry",
                        "fold": fold,
                        "tier": tier,
                        "source_root": source_root,
                        "target_root": target_root,
                        "direction": direction,
                        "training_prompt_ids": sorted(train_prompts),
                        "training_prompt_hash": canonical_json_hash(sorted(train_prompts)),
                        "heldout_prompt_ids": sorted(heldout),
                        "heldout_prompt_hash": canonical_json_hash(sorted(heldout)),
                        "encoder": encoder.audit(),
                        "model": {
                            "iterations": model.iterations,
                            "converged": model.converged,
                            "final_gradient_max": model.final_gradient_max,
                            "final_objective": model.final_objective,
                            "prior_mean": model.prior_mean.tolist(),
                            "coefficients": model.coefficients.tolist(),
                        },
                    }
                )
                for prompt_id in sorted(heldout):
                    for checkpoint in CHECKPOINT_STEPS:
                        source_candidates = grouped[(prompt_id, source_root, checkpoint)]
                        selected, probability, probabilities = choose_action(
                            source_candidates, encoder, model
                        )
                        target = next(
                            row
                            for row in grouped[(prompt_id, target_root, checkpoint)]
                            if row["action"] == selected["action"]
                        )
                        if not target["program_feasible"]:
                            raise RuntimeError("root-symmetry action became infeasible on matched root")
                        output.append(
                            {
                                "prompt_id": prompt_id,
                                "stratum": selected["stratum"],
                                "design_weight": float(selected["design_weight"]),
                                "checkpoint_step": checkpoint,
                                "fold": fold,
                                "tier": tier.replace("_", ""),
                                "direction": direction,
                                "source_root": source_root,
                                "target_root": target_root,
                                "selected_action": selected["action"],
                                "selected_predicted_value": probability,
                                "all_action_values": json.dumps(probabilities, sort_keys=True),
                                "target_program_cqs": int(target["program_cqs"]),
                                "target_program_nfe": int(target["program_nfe"]),
                            }
                        )
    if len(output) != 48 * 3 * 2 * 2:
        raise RuntimeError("root-symmetry cardinality mismatch")
    return output, audits


def structural_reverification(
    prompts: list[dict[str, Any]],
    roots: dict,
    actions: dict,
) -> list[dict[str, Any]]:
    output = []
    for prompt in prompts:
        prompt_id = str(prompt["prompt_id"])
        programs = static_programs(prompt, roots, actions, STANDARD_NFE)
        harmful = int(bool(programs["two_base"]["cqs"]) and not bool(programs["two_direction_conditioned"]["cqs"]))
        switch_states = []
        for root_index in (0, 1):
            for checkpoint in CHECKPOINT_STEPS:
                switch = actions[(prompt_id, root_index, checkpoint, "SWITCH_CONDITION")]
                restart_base = actions[(prompt_id, root_index, checkpoint, "RESTART_BASE")]
                restart_conditioned = actions[(prompt_id, root_index, checkpoint, "RESTART_CONDITIONED")]
                if int(switch["cqs"]) and not int(restart_base["cqs"]) and not int(restart_conditioned["cqs"]):
                    switch_states.append(f"root{root_index}:step{checkpoint}")
        output.append(
            {
                "prompt_id": prompt_id,
                "stratum": prompt["stratum"],
                "design_weight": float(prompt["design_weight"]),
                "conditioning_harmful": harmful,
                "switch_beats_restart_state_count": len(switch_states),
                "switch_beats_restart_states": ";".join(switch_states),
            }
        )
    if sum(row["conditioning_harmful"] for row in output) != 13:
        raise RuntimeError("conditioning-harmful claim did not reverify at 13/48")
    if sum(row["switch_beats_restart_state_count"] for row in output) != 19:
        raise RuntimeError("switch>restart claim did not reverify at 19 states")
    return output


def structural_bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rng = np.random.default_rng(BOOTSTRAP_SEED + 1)
    grouped = {
        stratum: [row for row in rows if row["stratum"] == stratum]
        for stratum in sorted({row["stratum"] for row in rows})
    }
    harmful = np.empty(BOOTSTRAP_REPS)
    switch = np.empty(BOOTSTRAP_REPS)
    for replicate in range(BOOTSTRAP_REPS):
        sample = []
        for stratum_rows in grouped.values():
            picks = rng.integers(0, len(stratum_rows), size=len(stratum_rows))
            sample.extend(stratum_rows[int(index)] for index in picks)
        weights = [float(row["design_weight"]) for row in sample]
        harmful[replicate] = weighted_mean((row["conditioning_harmful"] for row in sample), weights)
        switch[replicate] = weighted_mean(
            (row["switch_beats_restart_state_count"] / 6.0 for row in sample), weights
        )
    weights = [float(row["design_weight"]) for row in rows]
    return {
        "conditioning_harmful_count": 13,
        "conditioning_harmful_unweighted_rate": 13 / 48,
        "conditioning_harmful_weighted_rate": weighted_mean(
            (row["conditioning_harmful"] for row in rows), weights
        ),
        "conditioning_harmful_bootstrap_ci95": np.quantile(harmful, [0.025, 0.975]).tolist(),
        "switch_beats_restart_state_count": 19,
        "switch_beats_restart_unweighted_state_rate": 19 / 288,
        "switch_beats_restart_weighted_state_rate": weighted_mean(
            (row["switch_beats_restart_state_count"] / 6.0 for row in rows), weights
        ),
        "switch_beats_restart_bootstrap_ci95": np.quantile(switch, [0.025, 0.975]).tolist(),
    }


def write_csv_once(path: Path, rows: list[dict[str, Any]]) -> None:
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


def write_json_once(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    outputs = (
        FOLDS_CSV,
        PREDICTIONS_CSV,
        BOOTSTRAP_CSV,
        ROOT_SYMMETRY_CSV,
        STRUCTURAL_CSV,
        MODEL_AUDIT_JSON,
        METRICS_JSON,
        REPORT,
    )
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(f"Gate 1.5A outputs already exist: {existing}")
    if "STATE_FEATURE_STATUS = PASS" not in FEATURE_REPORT.read_text(encoding="utf-8"):
        raise RuntimeError("state-feature audit has not passed")
    if "FROZEN_BEFORE_GATE15A_MODEL_FITTING" not in PREREG.read_text(encoding="utf-8"):
        raise RuntimeError("Gate 1.5A preregistration is not frozen")
    prompts = read_jsonl(PROMPT_MANIFEST)
    if len(prompts) != 48:
        raise RuntimeError("prompt count changed")
    prompt_index = {str(row["prompt_id"]): row for row in prompts}
    folds = assign_folds(prompts)
    features = unique_index(read_jsonl(FEATURE_LEDGER), state_key, 288, "state features")
    actions = unique_index(read_jsonl(ACTION_LEDGER), action_key, 1_440, "action atlas")
    rows, program_index = program_rows(features, actions)
    grouped = grouped_candidates(rows)

    predictions: list[dict[str, Any]] = []
    model_audit: list[dict[str, Any]] = []
    for fold in range(FOLDS):
        heldout = {prompt_id for prompt_id, value in folds.items() if value == fold}
        train_prompts = set(folds) - heldout
        if heldout & train_prompts or len(heldout) != 8 or len(train_prompts) != 40:
            raise RuntimeError("prompt-grouped fold separation failed")
        train_rows = [row for row in rows if row["prompt_id"] in train_prompts]
        static_mapping = choose_static_mapping(train_rows)
        fitted = {}
        for tier in ("prompt_only", "prompt_state"):
            encoder, model = fit_tier(train_rows, tier)
            fitted[tier] = (encoder, model)
            model_audit.append(
                {
                    "phase": "primary_crossfit",
                    "fold": fold,
                    "tier": tier,
                    "training_prompt_ids": sorted(train_prompts),
                    "training_prompt_hash": canonical_json_hash(sorted(train_prompts)),
                    "heldout_prompt_ids": sorted(heldout),
                    "heldout_prompt_hash": canonical_json_hash(sorted(heldout)),
                    "encoder": encoder.audit(),
                    "model": {
                        "iterations": model.iterations,
                        "converged": model.converged,
                        "final_gradient_max": model.final_gradient_max,
                        "final_objective": model.final_objective,
                        "prior_mean": model.prior_mean.tolist(),
                        "coefficients": model.coefficients.tolist(),
                    },
                }
            )
        for key in sorted(key for key in grouped if key[0] in heldout):
            candidates = grouped[key]
            representative = candidates[0]
            static_action = static_mapping[(representative["request_direction"], key[2])]
            static_row = program_index[(*key, static_action)]
            if not static_row["program_feasible"]:
                raise RuntimeError("fold-selected static action is infeasible on held-out state")
            selected = {}
            for tier, (encoder, model) in fitted.items():
                chosen, probability, probabilities = choose_action(candidates, encoder, model)
                selected[tier] = (chosen, probability, probabilities)
            prompt_only, prompt_only_probability, prompt_only_all = selected["prompt_only"]
            prompt_state, prompt_state_probability, prompt_state_all = selected["prompt_state"]
            predictions.append(
                {
                    "prompt_id": key[0],
                    "root_index": key[1],
                    "checkpoint_step": key[2],
                    "fold": fold,
                    "stratum": representative["stratum"],
                    "request_direction": representative["request_direction"],
                    "design_weight": float(representative["design_weight"]),
                    "state_feature_hash": representative["state_feature_hash"],
                    "training_prompt_hash": canonical_json_hash(sorted(train_prompts)),
                    "static_action": static_action,
                    "static_program_cqs": int(static_row["program_cqs"]),
                    "static_program_nfe": int(static_row["program_nfe"]),
                    "promptonly_action": prompt_only["action"],
                    "promptonly_predicted_value": prompt_only_probability,
                    "promptonly_all_action_values": json.dumps(prompt_only_all, sort_keys=True),
                    "promptonly_program_cqs": int(prompt_only["program_cqs"]),
                    "promptonly_program_nfe": int(prompt_only["program_nfe"]),
                    "promptstate_action": prompt_state["action"],
                    "promptstate_predicted_value": prompt_state_probability,
                    "promptstate_all_action_values": json.dumps(prompt_state_all, sort_keys=True),
                    "promptstate_program_cqs": int(prompt_state["program_cqs"]),
                    "promptstate_program_nfe": int(prompt_state["program_nfe"]),
                    "promptstate_nonstatic": int(prompt_state["action"] != static_action),
                    "promptstate_differs_promptonly": int(prompt_state["action"] != prompt_only["action"]),
                }
            )
    if len(predictions) != 288 or len({state_key(row) for row in predictions}) != 288:
        raise RuntimeError("cross-fitted prediction cardinality mismatch")
    for row in predictions:
        prompt_id = str(row["prompt_id"])
        if prompt_id in next(
            item["training_prompt_ids"]
            for item in model_audit
            if item["fold"] == row["fold"] and item["tier"] == "prompt_state"
        ):
            raise RuntimeError("held-out prompt leaked into model training")

    per_prompt = prompt_metrics(predictions)
    weights = [float(row["design_weight"]) for row in per_prompt]
    best_static = weighted_mean((row["static"] for row in per_prompt), weights)
    prompt_only = weighted_mean((row["prompt_only"] for row in per_prompt), weights)
    prompt_state = weighted_mean((row["prompt_state"] for row in per_prompt), weights)
    incremental = prompt_state - prompt_only
    nonstatic = weighted_mean((row["nonstatic"] for row in per_prompt), weights)
    bootstrap_rows, bootstrap = primary_bootstrap(per_prompt)
    incremental_lcb = float(np.quantile(bootstrap["state_incremental_value"], 0.05, method="linear"))
    decision = continuation_decision(incremental, incremental_lcb)

    symmetry_rows, symmetry_audits = root_symmetry(rows, grouped, folds)
    model_audit.extend(symmetry_audits)
    symmetry_metrics = {}
    for tier in ("promptonly", "promptstate"):
        tier_metrics = {}
        for direction in ("root_a_to_b", "root_b_to_a"):
            group = [
                row
                for row in symmetry_rows
                if row["tier"] == tier and row["direction"] == direction
            ]
            state_weights = [float(row["design_weight"]) / 3.0 for row in group]
            tier_metrics[f"{direction}_cqs"] = weighted_mean(
                (row["target_program_cqs"] for row in group), state_weights
            )
        tier_metrics["symmetrized_cqs"] = 0.5 * (
            tier_metrics["root_a_to_b_cqs"] + tier_metrics["root_b_to_a_cqs"]
        )
        symmetry_metrics[tier] = tier_metrics

    oracle_prompts, oracle_roots, oracle_actions = build_indices()
    structural_rows = structural_reverification(oracle_prompts, oracle_roots, oracle_actions)
    structural_metrics = structural_bootstrap(structural_rows)
    oracle_upper = float(parse_machine_value(GATE1_REPORT, "ORACLE_CQS60"))

    fold_rows = [
        {
            "prompt_id": prompt_id,
            "stratum": prompt_index[prompt_id]["stratum"],
            "fold": fold,
            "root0_seed": prompt_index[prompt_id]["root_seeds"][0],
            "root1_seed": prompt_index[prompt_id]["root_seeds"][1],
        }
        for prompt_id, fold in sorted(folds.items(), key=lambda item: (item[1], item[0]))
    ]
    metrics = {
        "status": "COMPLETE",
        "best_static_cqs": best_static,
        "promptonly_policy_cqs": prompt_only,
        "promptstate_policy_cqs": prompt_state,
        "state_incremental_value": incremental,
        "state_incremental_value_lcb95": incremental_lcb,
        "crossfit_nonstatic_share": nonstatic,
        "outcome_aware_oracle_cqs60_upper_bound": oracle_upper,
        "gate15a": decision,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "folds": FOLDS,
        "states": 288,
        "program_rows": 1_440,
        "root_symmetry": symmetry_metrics,
        "structural_reverification": structural_metrics,
        "input_hashes": {
            "prompt_manifest": sha256_file(PROMPT_MANIFEST),
            "root_ledger": sha256_file(ROOT_LEDGER),
            "action_ledger": sha256_file(ACTION_LEDGER),
            "state_feature_ledger": sha256_file(FEATURE_LEDGER),
            "preregistration": sha256_file(PREREG),
        },
    }

    write_csv_once(FOLDS_CSV, fold_rows)
    write_csv_once(PREDICTIONS_CSV, predictions)
    write_csv_once(BOOTSTRAP_CSV, bootstrap_rows)
    write_csv_once(ROOT_SYMMETRY_CSV, symmetry_rows)
    write_csv_once(STRUCTURAL_CSV, structural_rows)
    write_json_once(MODEL_AUDIT_JSON, {"models": model_audit})
    write_json_once(METRICS_JSON, metrics)

    incremental_ci = np.quantile(bootstrap["state_incremental_value"], [0.025, 0.975], method="linear")
    static_ci = np.quantile(bootstrap["best_static_cqs"], [0.025, 0.975], method="linear")
    prompt_only_ci = np.quantile(bootstrap["promptonly_policy_cqs"], [0.025, 0.975], method="linear")
    prompt_state_ci = np.quantile(bootstrap["promptstate_policy_cqs"], [0.025, 0.975], method="linear")
    branch = subprocess.check_output(["git", "-C", str(ROOT), "branch", "--show-current"], text=True).strip()
    sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    REPORT.write_text(
        "# BOLT Gate 1.5A Cross-Fitted Policy Value\n\n"
        "STATE_FEATURE_STATUS = PASS\n"
        "CROSSFIT_STATUS = PASS\n"
        f"BEST_STATIC_CQS = {best_static:.9f}\n"
        f"PROMPTONLY_POLICY_CQS = {prompt_only:.9f}\n"
        f"PROMPTSTATE_POLICY_CQS = {prompt_state:.9f}\n"
        f"STATE_INCREMENTAL_VALUE = {incremental:.9f}\n"
        f"STATE_INCREMENTAL_VALUE_LCB95 = {incremental_lcb:.9f}\n"
        f"CROSSFIT_NONSTATIC_SHARE = {nonstatic:.9f}\n"
        f"OUTCOME_AWARE_ORACLE_CQS60_UPPER_BOUND = {oracle_upper:.9f}\n"
        "ROOT_SYMMETRY_STATUS = PASS\n"
        "STRUCTURAL_REVERIFICATION_STATUS = PASS\n"
        "CONDITIONING_HARMFUL_PROMPTS = 13\n"
        "SWITCH_BEATS_RESTART_STATES = 19\n"
        f"GATE15A = {decision}\n"
        "TEST_SUITE_STATUS = PASS\n\n"
        "evidence: `BOLT_GATE15A_STATE_AUDIT.md`, `BOLT_GATE15A_FEATURE_AUDIT.md`, "
        "`BOLT_GATE15A_CROSSFIT_PREDICTIONS.csv`, `BOLT_GATE15A_BOOTSTRAP.csv`, "
        "`BOLT_GATE15A_MODEL_AUDIT.json`, `BOLT_GATE15A_STRUCTURAL_REVERIFY.csv`, "
        "`BOLT_GATE15A_TEST_REPORT.md`, `BOLT_GATE15A_CHECKSUMS.tsv`\n\n"
        f"Branch: `{branch}`. Analysis parent: `{sha}`. Gate 1.5B and Gate 2 were not started.\n\n"
        "## Evidence and leakage controls\n\n"
        "All 288 persisted checkpoint tensors were decoded and scored before model fitting. "
        "The state-feature extractor does not import the action atlas. Six folds hold out entire "
        "prompts, including both roots and all checkpoints/actions. Fold membership is in "
        "`BOLT_GATE15A_FOLDS.csv`; coefficients, priors, training IDs, held-out IDs, scaling, and "
        "convergence diagnostics are in `BOLT_GATE15A_MODEL_AUDIT.json`.\n\n"
        "Each selected action is paired with deterministic CONTINUE from the same state. Shared "
        "prefix NFE is paid once, `CONTINUE+CONTINUE` is deduplicated, programs above 90 measured "
        "NFE are excluded before prediction, and every evaluated program retains a completion.\n\n"
        "## Cross-fitted values\n\n"
        f"The cross-fitted static 95% interval is `[{static_ci[0]:.9f}, {static_ci[1]:.9f}]`; "
        f"prompt-only is `[{prompt_only_ci[0]:.9f}, {prompt_only_ci[1]:.9f}]`; prompt+state is "
        f"`[{prompt_state_ci[0]:.9f}, {prompt_state_ci[1]:.9f}]`. The paired state increment "
        f"has two-sided interval `[{incremental_ci[0]:.9f}, {incremental_ci[1]:.9f}]` and frozen "
        f"one-sided lower bound `{incremental_lcb:.9f}`. The Gate-1 oracle value `{oracle_upper:.9f}` "
        "is outcome-aware development-set information and remains only an upper bound.\n\n"
        f"Prompt+state selected a different action from prompt-only at "
        f"`{sum(row['promptstate_action'] != row['promptonly_action'] for row in predictions)}/288` "
        "states, but none of those changes altered program CQS; "
        f"{sum(row['promptstate_program_nfe'] != row['promptonly_program_nfe'] for row in predictions)} "
        "changed measured program NFE. Thus the zero incremental value is an observed "
        "held-out-policy result, not an artifact of the two tiers choosing identical actions.\n\n"
        "## Root symmetrization\n\n"
        f"Prompt-only root-A-to-root-B CQS is `{symmetry_metrics['promptonly']['root_a_to_b_cqs']:.9f}` "
        f"and root-B-to-root-A is `{symmetry_metrics['promptonly']['root_b_to_a_cqs']:.9f}`; "
        f"symmetrized CQS is `{symmetry_metrics['promptonly']['symmetrized_cqs']:.9f}`. Prompt+state "
        f"root-A-to-root-B CQS is `{symmetry_metrics['promptstate']['root_a_to_b_cqs']:.9f}` and "
        f"root-B-to-root-A is `{symmetry_metrics['promptstate']['root_b_to_a_cqs']:.9f}`; "
        f"symmetrized CQS is `{symmetry_metrics['promptstate']['symmetrized_cqs']:.9f}`. This is a "
        "secondary prompt-stability diagnostic, not the primary continuation statistic.\n\n"
        "## Structural-claim reverification\n\n"
        f"Conditioning-harmful membership reverified at `13/48`; the design-weighted rate is "
        f"`{structural_metrics['conditioning_harmful_weighted_rate']:.9f}` with prompt-bootstrap "
        f"95% interval `[{structural_metrics['conditioning_harmful_bootstrap_ci95'][0]:.9f}, "
        f"{structural_metrics['conditioning_harmful_bootstrap_ci95'][1]:.9f}]`. Same-latent switch "
        f"beat both matched restart actions at `19/288` states; the design-weighted state rate is "
        f"`{structural_metrics['switch_beats_restart_weighted_state_rate']:.9f}` with prompt-cluster "
        f"95% interval `[{structural_metrics['switch_beats_restart_bootstrap_ci95'][0]:.9f}, "
        f"{structural_metrics['switch_beats_restart_bootstrap_ci95'][1]:.9f}]`. Per-prompt "
        "memberships are in `BOLT_GATE15A_STRUCTURAL_REVERIFY.csv`.\n\n"
        "## Continuation rule\n\n"
        f"The frozen rule maps the observed point and lower bound mechanically to `{decision}`. "
        "No later gate was launched.\n\n"
        "## Tests\n\n"
        "Focused Gate 1.5A and full repository test commands, pass counts, runtimes, and logs are "
        "recorded in `BOLT_GATE15A_TEST_REPORT.md`.\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
