from pathlib import Path

import pytest

from v15_gate0_runtime import GlobalComputePool, REQUIRED_STATE_FIELDS, RUN_ROOT, load_state


def test_global_rollover_returns_unused_compute_and_has_dynamic_attempts():
    pool = GlobalComputePool(full_generation_cost=50, total_budget=100)
    pool.charge_shared_prefix("shared", 10)
    first = pool.begin_exploratory("first", 40)
    first_event = pool.finish(first, 5, False)
    second = pool.begin_exploratory("second", 40)
    second_event = pool.finish(second, 10, False)
    completion = pool.begin_completion("completion", 40)
    pool.finish(completion, 40, True)
    assert first_event["returned_unused_calls"] == 35
    assert second_event["returned_unused_calls"] == 25
    assert len(pool.attempts) == 3
    assert pool.remaining == 35
    assert pool.completed_candidates == 1


def test_completion_reserve_rejects_unfunded_exploration():
    pool = GlobalComputePool(full_generation_cost=50, total_budget=100)
    pool.charge_shared_prefix("shared", 50)
    with pytest.raises(ValueError, match="completion reserve"):
        pool.begin_exploratory("forbidden", 1)
    completion = pool.begin_completion("completion", 50)
    pool.finish(completion, 50, True)
    assert pool.completed_candidates == 1


def test_budget_must_be_exactly_two_measured_full_generations():
    with pytest.raises(ValueError, match="exactly two"):
        GlobalComputePool(full_generation_cost=50, total_budget=99)


def test_real_checkpoint_contract_and_separate_process_integration():
    state_paths = sorted((RUN_ROOT / "states").glob("v15g0_*/step_*.pt"))
    assert len(state_paths) == 64
    state, checks = load_state(state_paths[0])
    assert not (REQUIRED_STATE_FIELDS - set(state))
    assert all(checks.values())
    resume_records = sorted((RUN_ROOT / "records" / "resume").glob("*.json"))
    assert len(resume_records) == 64

