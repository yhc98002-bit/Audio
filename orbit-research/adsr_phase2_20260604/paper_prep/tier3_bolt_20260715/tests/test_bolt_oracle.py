from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for name in ("bolt_core", "bolt_oracle_headroom"):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
oracle = sys.modules["bolt_oracle_headroom"]


def leaf(name, checkpoint, action, prefix, edge, cqs=0):
    return oracle.Leaf(name, 0, checkpoint, action, prefix, edge, cqs, 0.5, {})


def test_nested_tree_prefix_is_paid_once():
    leaves = [
        leaf("switch6", 6, "SWITCH_CONDITION", 6, 39),
        leaf("fork12", 12, "FORK_LATENT", 17, 28),
    ]
    assert oracle.subset_cost(leaves, 45) == 17 + 39 + 28
    assert oracle.subset_cost(leaves, 45) != (6 + 39) + (17 + 28)


def test_terminal_continue_is_one_physical_leaf():
    base = leaf("base", 30, "CONTINUE", 45, 0, 1)
    options = oracle.root_options([base], 45, 90)
    assert options[45]["selected"] == ["base"]
    assert options[45]["any_success"] == 1


def test_oracle_can_separate_from_static_failure():
    failed_base = leaf("base", 30, "CONTINUE", 45, 0, 0)
    successful_switch = leaf("switch12", 12, "SWITCH_CONDITION", 17, 28, 1)
    options = oracle.root_options([failed_base, successful_switch], 45, 90)
    assert any(row["any_success"] for row in options.values())
    assert min(cost for cost, row in options.items() if row["any_success"]) == 45


def test_nonstatic_program_compares_physical_leaf_sets():
    assert not oracle.oracle_program_differs(["root0_base", "root1_base"], ["root1_base", "root0_base"])
    assert oracle.oracle_program_differs(["root0_base", "root1_base"], ["root0_base", "root0_step12_FORK_LATENT"])


def test_matched_cqs_compute_saving_is_conservative_on_static_failures():
    assert oracle.matched_cqs_compute_saving(1, 90, 45) == 0.5
    assert oracle.matched_cqs_compute_saving(0, 90, 45) == 0.0


def test_full_tree_oracle_never_selects_empty_program(monkeypatch):
    failed = leaf("base", 30, "CONTINUE", 45, 0, 0)
    monkeypatch.setattr(oracle, "root_leaves", lambda *args, **kwargs: [failed])
    result = oracle.full_tree_oracle("p", {("p", 0): {}, ("p", 1): {}}, {}, 45)
    assert result["selected"]
    assert 45 <= result["cost"] <= 90
