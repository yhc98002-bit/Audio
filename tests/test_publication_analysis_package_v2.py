import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/build_publication_analysis_package_v2.py"
SPEC = importlib.util.spec_from_file_location("publication_analysis_v2", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_deployment_success_matches_frozen_formula():
    p = np.array([0.0, 0.25, 1.0])
    assert np.allclose(MODULE.deployment_success(p, 4), [0.0, 1 - 0.75**4, 1.0])


def test_restricted_expected_draws_is_bounded_and_handles_zero():
    assert MODULE.restricted_expected_draws(0.0, 128) == 128
    assert MODULE.restricted_expected_draws(0.5, 16) == pytest.approx(2 * (1 - 0.5**16))


def test_zero_success_upper_bound_is_one_sided_binomial_bound():
    upper = MODULE.zero_success_upper_bound(128)
    assert (1 - upper) ** 128 == pytest.approx(0.05)


def test_duplicate_key_fails_even_when_rows_are_identical():
    row = {"prompt_id": "p", "seed_idx": 0}
    with pytest.raises(ValueError, match="identical duplicate"):
        MODULE.unique_rows([row, dict(row)], ("prompt_id", "seed_idx"), "fixture")


def test_duplicate_key_fails_when_rows_conflict():
    with pytest.raises(ValueError, match="conflicting duplicate"):
        MODULE.unique_rows(
            [
                {"prompt_id": "p", "seed_idx": 0, "type_correct": 0},
                {"prompt_id": "p", "seed_idx": 0, "type_correct": 1},
            ],
            ("prompt_id", "seed_idx"),
            "fixture",
        )


def test_failed_rows_are_fatal():
    with pytest.raises(ValueError, match="failed rows"):
        MODULE.require_success([{"ok": False, "type_correct": 0}], "fixture")


def test_expected_cell_shape_is_exact():
    rows = [
        {"condition": "x", "prompt_id": prompt, "seed_idx": seed}
        for prompt in ("a", "b")
        for seed in range(3)
    ]
    MODULE.assert_cells(rows, {"x": (2, 3)}, "fixture")
    with pytest.raises(ValueError, match="invalid seed cell"):
        MODULE.assert_cells(rows[:-1], {"x": (2, 3)}, "fixture")


def test_regime_boundaries_match_frozen_definition():
    assert MODULE.regime(1 / 16) == "rare_le_1_in_16"
    assert MODULE.regime(1 / 16 + 1e-6) == "low_1_in_16_to_1_in_4"
    assert MODULE.regime(0.25) == "seed_recoverable_1_in_4_to_1_in_2"
    assert MODULE.regime(0.5) == "easy_ge_1_in_2"


def test_two_stage_bootstrap_respects_binary_extremes():
    cells = [
        {"stratum": "vocal", "selection_bin": "0", "values": np.ones(8), "weight": 1.0},
        {"stratum": "instrumental", "selection_bin": "0", "values": np.ones(8), "weight": 2.0},
    ]
    result = MODULE.stratified_bootstrap(cells, lambda p: MODULE.deployment_success(p, 4), reps=100)
    assert np.all(result == 1.0)


def test_paired_delta_bootstrap_zero_for_identical_cells():
    cells = [
        {
            "prompt_id": "p1",
            "stratum": "vocal",
            "selection_bin": "all",
            "values": np.array([0, 1] * 8),
            "weight": 1.0,
        }
    ]
    # Independent seed resampling can vary per replicate, but remains centered at zero.
    result = MODULE.paired_delta_bootstrap(cells, cells, 4, reps=20_000)
    assert abs(float(result.mean())) < 0.01
