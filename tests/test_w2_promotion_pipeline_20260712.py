from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_promotion_pipeline_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_promotion", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_rows(role: str, n: int, start: int = 0):
    rows = []
    for index in range(start, start + n):
        truth = index % 2
        requested = index % 2
        present = bool(truth != requested)
        score = 0.9 if present else 0.01
        rows.append(
            {
                "rating_id": f"r{index}",
                "role": role,
                "repeat_parent_rating_id": "",
                "label_b_constraint": "violated" if truth else "satisfied",
                "truth_violation": truth,
                "requested_vocal": requested,
                "demucs_score": score,
                "panns_score": score,
                "design_weight": 1.0,
                "calibration_stratum": f"s{index % 4}",
            }
        )
    return rows


def test_unvalidated_judge_cannot_enter_calibration():
    module = load_module()
    for source in ["qwen_unvalidated", "automatic_model", "", "judge:qwen:validated:abc"]:
        try:
            module.require_human_source(source)
        except ValueError:
            pass
        else:
            raise AssertionError(f"source should have been rejected: {source}")
    assert module.require_human_source("pi:Richard") == "pi:Richard"
    assert module.require_human_source("human:CXY") == "human:CXY"


def test_reliability_failure_blocks_heldout():
    module = load_module()
    parents = make_rows("heldout", 20)
    repeats = []
    for index, parent in enumerate(parents):
        repeats.append(
            {
                **parent,
                "rating_id": f"repeat{index}",
                "role": "repeat",
                "repeat_parent_rating_id": parent["rating_id"],
                "label_b_constraint": "satisfied" if parent["label_b_constraint"] == "violated" else "violated",
            }
        )
    result = module.reliability(parents + repeats)
    assert result["status"] == "FAIL_CLARIFY_AND_RERATE"
    selection = {"selected_candidate": {"family": "current_demucs", "demucs_threshold": 0.1791, "panns_threshold": float("inf")}}
    try:
        module.evaluate_heldout(make_rows("heldout", 100), selection, result, bootstrap_replicates=10)
    except ValueError as exc:
        assert "reliability" in str(exc)
    else:
        raise AssertionError("reliability failure reached held-out evaluation")


def test_train_selection_keeps_frozen_60_and_excludes_unsure_from_metrics():
    module = load_module()
    rows = make_rows("train", 60)
    rows[0]["truth_violation"] = None
    rows[0]["label_b_constraint"] = "unsure"
    result = module.select_candidate(rows)
    assert result["training_rows"] == 60
    assert result["training_decided_rows"] == 59
    assert result["training_abstention_rows"] == 1
    assert result["selected_candidate"]["train_metrics"]["decided_rows"] == 59


def test_train_selection_and_mechanical_gate_have_no_plan_side_effect():
    module = load_module()
    train = make_rows("train", 60)
    selection = module.select_candidate(train)
    assert selection["status"] == "TRAIN_SELECTED_HELDOUT_UNSEEN"
    assert selection["selected_candidate"]["train_metrics"]["balanced_accuracy"] == 1.0
    heldout = make_rows("heldout", 100, start=100)
    reliability = {
        "status": "PASS",
        "exact_agreement": 1.0,
        "satisfied_violated_reversals": 0,
    }
    result = module.evaluate_heldout(
        heldout,
        selection,
        reliability,
        bootstrap_replicates=100,
        bootstrap_seed=7,
    )
    assert result["mechanical_promotion_gate"] == "PASS"
    assert result["corrected_instrument_status"] == "AWAITING_DUAL_PI_PROMOTION_RECORD"
    assert result["plan_or_claim_status_changed"] is False


def test_class_count_topup_happens_before_heldout_metrics_are_exposed():
    module = load_module()
    train = make_rows("train", 60)
    selection = module.select_candidate(train)
    heldout = make_rows("heldout", 100, start=200)
    for index, row in enumerate(heldout):
        row["truth_violation"] = 1 if index < 80 else 0
        row["label_b_constraint"] = "violated" if index < 80 else "satisfied"
    result = module.evaluate_heldout(
        heldout,
        selection,
        {"status": "PASS"},
        bootstrap_replicates=10,
    )
    assert result["mechanical_promotion_gate"] == "NOT_RUN_TOPUP_REQUIRED"
    assert result["topup_needed_negative"] == 30
    assert result["heldout_metrics_exposed"] is False
