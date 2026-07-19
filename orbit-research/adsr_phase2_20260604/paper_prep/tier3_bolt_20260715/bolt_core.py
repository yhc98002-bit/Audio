#!/usr/bin/env python3
"""Pure BOLT state, budget, key-audit, and tree-accounting primitives."""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ACTIONS = (
    "CONTINUE",
    "SWITCH_CONDITION",
    "FORK_LATENT",
    "RESTART_BASE",
    "RESTART_CONDITIONED",
)
CHECKPOINT_STEPS = (6, 12, 18)


def canonical_json_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def finite_score_or_neg_inf(value: float | None) -> float:
    """Preserve a scientific zero while treating only None/nonfinite as missing."""
    if value is None:
        return -math.inf
    score = float(value)
    return score if math.isfinite(score) else -math.inf


def select_best_scored(rows: Sequence[Mapping[str, object]], key: str) -> Mapping[str, object]:
    if not rows:
        raise ValueError("cannot select from an empty sequence")
    return max(rows, key=lambda row: finite_score_or_neg_inf(row.get(key)))


@dataclasses.dataclass(frozen=True)
class SeedNamespace:
    base: int
    width: int = 10_000_000

    def _check(self, seed: int) -> int:
        if not self.base <= seed < self.base + self.width:
            raise ValueError(f"derived seed {seed} is outside [{self.base}, {self.base + self.width})")
        return seed

    def root_seed(self, prompt_slot: int, root_index: int) -> int:
        if not 0 <= prompt_slot < 48 or root_index not in (0, 1):
            raise ValueError("root seed coordinates outside the frozen pilot design")
        return self._check(self.base + prompt_slot * 100_000 + root_index * 10_000)

    def restart_seed(self, prompt_slot: int, root_index: int, checkpoint_step: int, conditioned: bool) -> int:
        if checkpoint_step not in CHECKPOINT_STEPS:
            raise ValueError("unknown checkpoint")
        action_code = 2 if conditioned else 1
        return self._check(self.root_seed(prompt_slot, root_index) + checkpoint_step * 100 + action_code)

    def fork_seed(self, prompt_slot: int, root_index: int, checkpoint_step: int, branch_index: int = 0) -> int:
        if checkpoint_step not in CHECKPOINT_STEPS or not 0 <= branch_index < 50:
            raise ValueError("fork coordinates outside frozen bounds")
        return self._check(
            self.root_seed(prompt_slot, root_index) + checkpoint_step * 100 + 50 + branch_index
        )


@dataclasses.dataclass
class BudgetEvent:
    name: str
    reserved_nfe: int
    consumed_nfe: int
    completed_candidate: bool


class BudgetManager:
    """Global measured-NFE budget with rollover and a completion reserve."""

    def __init__(self, total_nfe: int, standard_generation_nfe: int):
        if total_nfe <= 0 or standard_generation_nfe <= 0:
            raise ValueError("NFE budgets must be positive")
        if total_nfe < standard_generation_nfe:
            raise ValueError("total budget cannot be smaller than one completion")
        self.total_nfe = int(total_nfe)
        self.standard_generation_nfe = int(standard_generation_nfe)
        self.spent_nfe = 0
        self.valid_completed_candidates = 0
        self.events: list[BudgetEvent] = []

    @property
    def remaining_nfe(self) -> int:
        return self.total_nfe - self.spent_nfe

    def feasible(self, planned_nfe: int, *, guarantees_completion: bool = False) -> bool:
        if planned_nfe < 0 or planned_nfe > self.remaining_nfe:
            return False
        if self.valid_completed_candidates == 0 and not guarantees_completion:
            return self.remaining_nfe - planned_nfe >= self.standard_generation_nfe
        return True

    def consume(
        self,
        name: str,
        *,
        planned_nfe: int,
        actual_nfe: int,
        completed_candidate: bool,
        guarantees_completion: bool = False,
    ) -> None:
        if not self.feasible(planned_nfe, guarantees_completion=guarantees_completion):
            raise RuntimeError(
                f"infeasible action {name}: planned={planned_nfe}, remaining={self.remaining_nfe}, "
                f"reserve={self.standard_generation_nfe}, valid={self.valid_completed_candidates}"
            )
        if actual_nfe < 0 or actual_nfe > planned_nfe:
            raise ValueError("actual NFE must lie between zero and the reserved amount")
        self.spent_nfe += int(actual_nfe)
        if completed_candidate:
            self.valid_completed_candidates += 1
        self.events.append(BudgetEvent(name, int(planned_nfe), int(actual_nfe), completed_candidate))


def demonstrate_true_rollover(standard_generation_nfe: int, abort_nfe: int) -> dict[str, object]:
    manager = BudgetManager(2 * standard_generation_nfe, standard_generation_nfe)
    manager.consume(
        "abort_1", planned_nfe=abort_nfe, actual_nfe=abort_nfe,
        completed_candidate=False, guarantees_completion=False,
    )
    after_first = manager.remaining_nfe
    manager.consume(
        "abort_2", planned_nfe=abort_nfe, actual_nfe=abort_nfe,
        completed_candidate=False, guarantees_completion=False,
    )
    after_second = manager.remaining_nfe
    manager.consume(
        "complete", planned_nfe=standard_generation_nfe, actual_nfe=standard_generation_nfe,
        completed_candidate=True, guarantees_completion=True,
    )
    return {
        "total_nfe": manager.total_nfe,
        "after_first_abort": after_first,
        "after_second_abort": after_second,
        "final_remaining": manager.remaining_nfe,
        "valid_completed_candidates": manager.valid_completed_candidates,
        "status": "PASS" if manager.valid_completed_candidates == 1 else "FAIL",
    }


def action_key(row: Mapping[str, object]) -> tuple[str, int, int, str]:
    return (
        str(row["prompt_id"]),
        int(row["root_seed"]),
        int(row["checkpoint_step"]),
        str(row["action"]),
    )


def expected_action_keys(prompt_rows: Iterable[Mapping[str, object]]) -> set[tuple[str, int, int, str]]:
    expected: set[tuple[str, int, int, str]] = set()
    for prompt in prompt_rows:
        for root_seed in prompt["root_seeds"]:
            for checkpoint_step in CHECKPOINT_STEPS:
                for action in ACTIONS:
                    expected.add((str(prompt["prompt_id"]), int(root_seed), checkpoint_step, action))
    return expected


def audit_action_rows(
    rows: Sequence[Mapping[str, object]], expected: set[tuple[str, int, int, str]]
) -> dict[str, object]:
    seen: dict[tuple[str, int, int, str], list[Mapping[str, object]]] = {}
    for row in rows:
        seen.setdefault(action_key(row), []).append(row)
    duplicates = sorted(key for key, group in seen.items() if len(group) > 1)
    missing = sorted(expected - set(seen))
    unexpected = sorted(set(seen) - expected)
    conflicts = []
    for key, group in seen.items():
        if len(group) > 1:
            signatures = {
                (str(row.get("output_sha256")), str(row.get("status")), str(row.get("error")))
                for row in group
            }
            if len(signatures) > 1:
                conflicts.append(key)
    errors = [action_key(row) for row in rows if row.get("status") != "PASS"]
    return {
        "expected": len(expected),
        "observed_rows": len(rows),
        "unique_keys": len(seen),
        "missing": missing,
        "duplicates": duplicates,
        "conflicts": sorted(conflicts),
        "errors": errors,
        "status": "PASS" if not (missing or duplicates or conflicts or errors or unexpected) else "FAIL",
    }


def deduplicate_terminal_leaves(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Keep one record per physical terminal output within a root tree."""
    kept: list[Mapping[str, object]] = []
    seen: set[tuple[str, int, str]] = set()
    for row in rows:
        terminal_hash = str(row.get("output_sha256") or row.get("output_path") or "")
        key = (str(row["prompt_id"]), int(row["root_seed"]), terminal_hash)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def shared_prefix_program_cost(prefix_nfe: int, edge_nfes: Iterable[int]) -> int:
    if prefix_nfe < 0:
        raise ValueError("prefix NFE cannot be negative")
    edges = [int(value) for value in edge_nfes]
    if any(value < 0 for value in edges):
        raise ValueError("edge NFE cannot be negative")
    return int(prefix_nfe) + sum(edges)


@dataclasses.dataclass(frozen=True)
class KnapsackLeaf:
    leaf_id: str
    incremental_cost: int
    success: int
    probability: float | None = None


def knapsack_oracle(leaves: Sequence[KnapsackLeaf], budget: int) -> dict[str, object]:
    """Exact 0/1 knapsack for a fixed shared-prefix state.

    Objective is empirical any-success first, then number of successes, then
    option-value approximation, and finally lower cost. The shared prefix is
    charged by the caller before this function.
    """
    if budget < 0:
        raise ValueError("budget cannot be negative")
    states: dict[int, tuple[tuple[int, int, float, int], tuple[str, ...]]] = {
        0: ((0, 0, 0.0, 0), ())
    }
    for leaf in leaves:
        if leaf.incremental_cost < 0:
            raise ValueError("leaf cost cannot be negative")
        option = 0.0
        if leaf.probability is not None:
            p = min(max(float(leaf.probability), 0.0), 1.0 - 1e-12)
            option = -math.log1p(-p)
        updates = dict(states)
        for used, (objective, selected) in states.items():
            new_used = used + leaf.incremental_cost
            if new_used > budget:
                continue
            success_count = objective[1] + int(bool(leaf.success))
            candidate_objective = (
                int(success_count > 0),
                success_count,
                objective[2] + option,
                -new_used,
            )
            incumbent = updates.get(new_used)
            if incumbent is None or candidate_objective > incumbent[0]:
                updates[new_used] = (candidate_objective, selected + (leaf.leaf_id,))
        states = updates
    used, (objective, selected) = max(
        states.items(), key=lambda item: (item[1][0], -item[0], item[1][1])
    )
    return {
        "selected_leaf_ids": list(selected),
        "used_nfe": used,
        "any_success": bool(objective[0]),
        "success_count": int(objective[1]),
        "option_value": float(objective[2]),
    }
