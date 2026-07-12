from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_calibrated_prevalence_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_calibrated", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calibration_rows():
    rows = []
    for index in range(60):
        truth = index % 2
        request = (index // 2) % 2
        rows.append(
            {
                "prompt_id": f"p{index // 2:02d}",
                "calibration_stratum": f"s{index % 4}",
                "truth_violation": truth,
                "requested_vocal": request,
                "demucs_score": 0.85 if truth else 0.02,
                "panns_score": 0.80 if truth else 0.01,
                "design_weight": 1.0,
            }
        )
    return rows


def target_rows():
    rows = []
    for index in range(40):
        truth = index % 2
        rows.append(
            {
                "prompt_id": f"target{index // 4:02d}",
                "requested_vocal": 0,
                "demucs_score": 0.85 if truth else 0.02,
                "panns_score": 0.80 if truth else 0.01,
                "apparent_violation": truth,
                "design_weight": 1.0,
            }
        )
    return rows


def test_model_selection_is_train_only_and_low_capacity():
    module = load_module()
    fit = module.select_model(calibration_rows())
    assert fit["status"] == "TRAIN_ONLY_MODEL_SELECTED"
    assert fit["selected"]["form"] in module.FORMS
    assert fit["selected"]["l2"] in module.L2_VALUES
    probabilities = module.predict_probability(target_rows(), fit)
    assert len(probabilities) == 40
    assert all(0 <= value <= 1 for value in probabilities)


def test_nested_bootstrap_resamples_calibration_target_and_refits():
    module = load_module()
    result = module.nested_bootstrap(calibration_rows(), target_rows(), replicates=20, seed=11)
    assert result["requested_replicates"] == 20
    assert result["valid_replicates"] >= 16
    assert 0 <= result["calibrated_rate"] <= 1
    assert len(result["joint_95_interval"]) == 2

