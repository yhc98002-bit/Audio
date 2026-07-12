from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_recompute_suite_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_recompute", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wilson_interval_contains_point():
    module = load_module()
    low, high = module._wilson(40, 100)
    assert low < 0.4 < high
    assert module._wilson(0, 0)[0] != module._wilson(0, 0)[0]


def test_recompute_contract_names_all_three_rate_columns():
    module = load_module()
    source = SCRIPT.read_text(encoding="utf-8")
    assert "apparent_rate" in source
    assert "candidate_sensitivity_rate" in source
    assert "calibrated_rate" in source
    assert module.OLD_THRESHOLD == 0.1791
    assert module.CANDIDATE_DEMUCS_THRESHOLD == 0.038639528676867485
    assert module.CANDIDATE_PANNS_THRESHOLD == 0.03181814216077328


def test_directionless_and_superseded_cohorts_are_explicitly_excluded():
    module = load_module()
    assert module.existing_exclusion_reason("n2_population_retry") == ""
    assert module.existing_exclusion_reason("stage3_intervention") == ""
    assert module.existing_exclusion_reason("atlas_keep") == "outside_direction_specific_recompute_scope"
    assert module.existing_exclusion_reason("candidate_spine_4096") == "superseded_by_reconstructed_spine"
