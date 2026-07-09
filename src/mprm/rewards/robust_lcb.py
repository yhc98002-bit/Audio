"""Robust lower-bound aggregate reward (METHOD_SPEC §2.2).

The robust aggregate is computed over the **axis × perturbation cross-product cells**:

    R_lcb(x, c) = mean(cells) - β · std(cells) - λ · probe_pen

where each cell is `r_axis(π(x), c)` for an axis and a perturbation π ∈ Π. This matches
the cross-product formulation in METHOD_SPEC.md §2.2; the prior implementation collapsed
per-axis-over-Π first and then std-axes, which underestimates std (it discards within-axis
perturbation variance).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

import torch

from mprm.data.prompts import Prompt
from mprm.rewards.interface import RewardModel


@dataclass
class RobustLcbResult:
    value: float
    mean_cells: float
    std_cells: float
    probe_penalty: float
    per_axis: dict[str, float]
    per_perturbation: dict[str, dict[str, float]]


def robust_lcb(waveform: torch.Tensor, sample_rate: int, prompt: Prompt,
               reward_models: list[RewardModel],
               perturbations: dict[str, callable],
               probe_scores: dict[str, float],
               lambda_probe: dict[str, float],
               beta_robust: float = 0.5,
               probe_floors: dict[str, float] | None = None) -> RobustLcbResult:
    per_perturbation: dict[str, dict[str, float]] = {}
    cell_values: list[float] = []
    for name, transform in perturbations.items():
        w_p = transform(waveform, sample_rate)
        per_perturbation[name] = {}
        for rm in reward_models:
            score = rm.score(w_p, sample_rate, prompt)
            per_perturbation[name][rm.axis] = score.value
            cell_values.append(score.value)

    per_axis: dict[str, float] = {}
    for rm in reward_models:
        vals = [per_perturbation[p][rm.axis] for p in per_perturbation]
        per_axis[rm.axis] = float(sum(vals) / len(vals)) if vals else 0.0

    mean_cells = float(sum(cell_values) / len(cell_values)) if cell_values else 0.0
    std_cells = float(statistics.pstdev(cell_values)) if len(cell_values) > 1 else 0.0

    probe_floors = probe_floors or {}
    probe_penalty = 0.0
    for probe_name, score in probe_scores.items():
        coef = float(lambda_probe.get(probe_name, 0.0))
        floor = float(probe_floors.get(probe_name, 0.0))
        # Hinge above the activation floor (METHOD_SPEC §2.3).
        probe_penalty += coef * max(0.0, score - floor)

    value = mean_cells - beta_robust * std_cells - probe_penalty

    return RobustLcbResult(
        value=value,
        mean_cells=mean_cells,
        std_cells=std_cells,
        probe_penalty=probe_penalty,
        per_axis=per_axis,
        per_perturbation=per_perturbation,
    )
