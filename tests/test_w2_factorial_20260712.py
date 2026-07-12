from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_factorial_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_factorial_20260712", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_factorial_condition_contract():
    module = load_module()
    module.assert_positive_text_contract()
    assert len(module.CONDITIONS) == 6
    assert module.condition_spec("plain_baseline") == (None, 5.0)
    assert module.condition_spec("sampler_only") == (None, 7.5)
    assert module.condition_spec("negative_text") == (module.NEGATIVE_TEXT, 5.0)
    assert module.condition_spec("positive_sampler") == (module.POSITIVE_TEXT, 7.5)


def test_factorial_seed_formula_is_crn_and_registered():
    module = load_module()
    seeds = {
        module.SEED_BASE + prompt_rank * 1000 + seed_idx
        for prompt_rank in range(module.N_PROMPTS)
        for seed_idx in range(module.N_SEEDS)
    }
    assert len(seeds) == 32 * 16
    assert min(seeds) == 2_034_000_000
    assert max(seeds) == 2_034_031_015
    registry = (ROOT / "paper_prep/SEED_REGISTRY.md").read_text(encoding="utf-8")
    assert "2034000000" in registry
    assert "2034031015" in registry


def test_factorial_instrument_thresholds_are_sensitivity_only():
    module = load_module()
    assert module.OLD_THRESHOLD == 0.1791
    assert module.CANDIDATE_DEMUCS_THRESHOLD == 0.038639528676867485
    assert module.CANDIDATE_PANNS_THRESHOLD == 0.03181814216077328
    assert "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED" in SCRIPT.read_text(encoding="utf-8")
