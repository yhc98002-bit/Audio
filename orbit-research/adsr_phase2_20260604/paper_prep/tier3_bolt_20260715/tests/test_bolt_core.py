from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bolt_core", ROOT / "bolt_core.py")
bolt = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = bolt
SPEC.loader.exec_module(bolt)


def test_zero_score_selection_is_not_missing():
    rows = [{"score": None, "id": "missing"}, {"score": 0.0, "id": "zero"}]
    assert bolt.select_best_scored(rows, "score")["id"] == "zero"


def test_two_abort_true_rollover():
    result = bolt.demonstrate_true_rollover(45, 6)
    assert result == {
        "total_nfe": 90,
        "after_first_abort": 84,
        "after_second_abort": 78,
        "final_remaining": 33,
        "valid_completed_candidates": 1,
        "status": "PASS",
    }


def test_completion_reserve_rejects_infeasible_plan():
    manager = bolt.BudgetManager(90, 45)
    assert not manager.feasible(46)
    with pytest.raises(RuntimeError, match="infeasible action"):
        manager.consume(
            "bad", planned_nfe=46, actual_nfe=1,
            completed_candidate=False, guarantees_completion=False,
        )
    assert manager.feasible(45, guarantees_completion=True)


def test_shared_prefix_accounting():
    assert bolt.shared_prefix_program_cost(12, [18, 18]) == 48
    assert bolt.shared_prefix_program_cost(12, [18, 18]) != 60


def test_seed_derivation_is_order_independent_and_unique():
    namespace = bolt.SeedNamespace(2_040_000_000)
    seeds = set()
    for slot in range(48):
        for root_index in (0, 1):
            root = namespace.root_seed(slot, root_index)
            seeds.add(root)
            for checkpoint in bolt.CHECKPOINT_STEPS:
                seeds.add(namespace.fork_seed(slot, root_index, checkpoint))
                seeds.add(namespace.restart_seed(slot, root_index, checkpoint, False))
                seeds.add(namespace.restart_seed(slot, root_index, checkpoint, True))
    assert len(seeds) == 48 * 2 * 10
    assert namespace.restart_seed(4, 1, 12, True) == namespace.restart_seed(4, 1, 12, True)


def _prompt_rows():
    return [{"prompt_id": "p0", "root_seeds": [101, 102]}]


def test_duplicate_action_key_fails_audit():
    expected = bolt.expected_action_keys(_prompt_rows())
    rows = [
        {"prompt_id": p, "root_seed": s, "checkpoint_step": c, "action": a, "status": "PASS"}
        for p, s, c, a in expected
    ]
    rows.append(dict(rows[0]))
    assert bolt.audit_action_rows(rows, expected)["status"] == "FAIL"
    assert len(bolt.audit_action_rows(rows, expected)["duplicates"]) == 1


def test_missing_action_key_fails_audit():
    expected = bolt.expected_action_keys(_prompt_rows())
    rows = [
        {"prompt_id": p, "root_seed": s, "checkpoint_step": c, "action": a, "status": "PASS"}
        for p, s, c, a in list(expected)[1:]
    ]
    result = bolt.audit_action_rows(rows, expected)
    assert result["status"] == "FAIL"
    assert len(result["missing"]) == 1


def test_oracle_terminal_leaf_deduplication():
    rows = [
        {"prompt_id": "p", "root_seed": 1, "checkpoint_step": c, "output_sha256": "same"}
        for c in (6, 12, 18)
    ]
    assert len(bolt.deduplicate_terminal_leaves(rows)) == 1


def test_tree_knapsack_cost_and_oracle_separation():
    leaves = [
        bolt.KnapsackLeaf("static", 45, 0, 0.2),
        bolt.KnapsackLeaf("switch", 30, 1, 0.6),
        bolt.KnapsackLeaf("fork", 30, 0, 0.3),
    ]
    result = bolt.knapsack_oracle(leaves, 60)
    assert result["any_success"] is True
    assert "switch" in result["selected_leaf_ids"]
    assert result["used_nfe"] <= 60


def test_crash_resume_contract_is_key_driven_and_nonoverwriting():
    source = (ROOT / "bolt_pilot_worker.py").read_text(encoding="utf-8")
    assert "existing = action_done.get(key_action)" in source
    assert "verify_media(existing)" in source
    assert "continue" in source
    assert "allow_existing=True" in source
