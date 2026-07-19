from __future__ import annotations

import importlib.util
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("bolt_gate15a_crossfit", ROOT / "bolt_gate15a_crossfit.py")
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)
import bolt_scoring


def test_folds_are_prompt_grouped_and_balanced():
    prompts = []
    for stratum_index in range(4):
        for prompt_index in range(12):
            prompts.append(
                {
                    "prompt_id": f"s{stratum_index}_p{prompt_index}",
                    "stratum": f"stratum_{stratum_index}",
                }
            )
    folds = gate.assign_folds(prompts)
    assert len(folds) == 48
    assert {sum(value == fold for value in folds.values()) for fold in range(6)} == {8}
    for fold in range(6):
        assert {
            sum(
                folds[row["prompt_id"]] == fold
                for row in prompts
                if row["stratum"] == stratum
            )
            for stratum in {row["stratum"] for row in prompts}
        } == {2}


def _program_inputs():
    features = {}
    actions = {}
    prefix = {6: 9, 12: 18, 18: 27}
    for prompt_index in range(48):
        prompt_id = f"p{prompt_index:02d}"
        for root_index in (0, 1):
            for checkpoint in gate.CHECKPOINT_STEPS:
                state = (prompt_id, root_index, checkpoint)
                features[state] = {
                    "prompt_id": prompt_id,
                    "root_index": root_index,
                    "checkpoint_step": checkpoint,
                    "prefix_nfe": prefix[checkpoint],
                    "design_weight": 1.0,
                }
                for action in gate.ACTIONS:
                    edge = 45 - prefix[checkpoint] if action == "CONTINUE" else 45
                    actions[(*state, action)] = {
                        "prompt_id": prompt_id,
                        "root_index": root_index,
                        "checkpoint_step": checkpoint,
                        "action": action,
                        "prefix_nfe": prefix[checkpoint],
                        "action_nfe": edge,
                        "cqs": int(action == "RESTART_BASE"),
                        "output_sha256": f"{prompt_id}-{root_index}-{checkpoint}-{action}",
                    }
    return features, actions


def test_program_semantics_pay_shared_prefix_once_and_keep_completion_reserve():
    features, actions = _program_inputs()
    rows, index = gate.program_rows(features, actions)
    assert len(rows) == 1_440
    assert index[("p00", 0, 6, "CONTINUE")]["program_nfe"] == 45
    assert index[("p00", 0, 6, "RESTART_BASE")]["program_nfe"] == 90
    assert index[("p00", 0, 6, "RESTART_BASE")]["program_cqs"] == 1
    assert index[("p00", 0, 12, "RESTART_BASE")]["program_nfe"] == 90
    assert all(row["program_feasible"] for row in rows)


@pytest.mark.parametrize(
    ("point", "lcb", "expected"),
    [
        (0.0, 1e-12, "PROCEED_GATE15B"),
        (0.05, 0.0, "PROCEED_GATE15B_POWERED_BY_REPLICATION"),
        (0.049999, 0.0, "STOP_THIS_AXIS"),
        (0.10, -1e-9, "PROCEED_GATE15B_POWERED_BY_REPLICATION"),
    ],
)
def test_frozen_continuation_rule_boundaries(point, lcb, expected):
    assert gate.continuation_decision(point, lcb) == expected


def test_map_logistic_reaches_frozen_stationarity_tolerance():
    matrix = np.asarray([[1.0, -1.0], [1.0, 0.0], [1.0, 1.0], [1.0, 2.0]])
    target = np.asarray([0.0, 0.0, 1.0, 1.0])
    weight = np.ones(4)
    precision = np.asarray([1.0, 1.0])
    prior = np.zeros(2)
    model = gate.fit_map_logistic(matrix, target, weight, precision, prior)
    assert model.converged
    assert model.final_gradient_max <= 1e-9
    assert model.predict(matrix)[0] < model.predict(matrix)[-1]


def _model_row(action: str, value_marker: int):
    return {
        "prompt_id": "heldout",
        "root_index": 0,
        "checkpoint_step": 12,
        "action": action,
        "program_feasible": True,
        "program_nfe": 45 + gate.ACTIONS.index(action),
        "program_cqs": value_marker,
        "requested_vocal": 0,
        "risk_score_preexisting": 0.5,
        "promoted_violation_rate_preexisting": 0.5,
        "corrected_evpd_mean_risk_preexisting": 0.5,
        "genre": "folk",
        "tempo_bin": "med_90_120",
        "prompt_specificity": "medium",
        "structure_complexity": "simple_AB",
        "language": "en",
        "preview_demucs_score": 0.2,
        "preview_panns_score": 0.3,
        "preview_calibrated_violation_probability": 0.4,
        "preview_clap_to_prompt": 0.5,
        "preview_promoted_present": 0,
        "checkpoint_fraction": 0.4,
        "remaining_budget_fraction": 0.8,
    }


def test_action_selection_does_not_read_heldout_outcome():
    rows_a = [_model_row(action, 0) for action in gate.ACTIONS]
    rows_b = [_model_row(action, int(action == "RESTART_BASE")) for action in gate.ACTIONS]
    encoder = gate.FeatureEncoder.fit(rows_a, "prompt_state")
    coefficients = np.zeros(len(encoder.names))
    coefficients[gate.ACTIONS.index("SWITCH_CONDITION")] = 2.0
    model = gate.MapLogisticModel(coefficients, np.zeros_like(coefficients), 1, True, 0.0, 0.0)
    selected_a = gate.choose_action(rows_a, encoder, model)[0]["action"]
    selected_b = gate.choose_action(rows_b, encoder, model)[0]["action"]
    assert selected_a == selected_b == "SWITCH_CONDITION"


def test_category_schema_is_frozen_not_fold_dependent():
    rows = [_model_row(action, 0) for action in gate.ACTIONS]
    encoder = gate.FeatureEncoder.fit(rows, "prompt_only")
    assert encoder.category_levels == gate.FROZEN_CATEGORY_LEVELS
    bad = dict(rows[0], genre="unknown_genre")
    with pytest.raises(RuntimeError, match="unknown held-out category"):
        encoder.transform([bad])


def test_audio_recovery_compares_encoded_candidate(tmp_path):
    phase = torch.arange(96_000, dtype=torch.float32) * (2.0 * np.pi * 440.0 / 48_000.0)
    waveform = (0.01 * torch.sin(phase)).reshape(1, -1)
    path = tmp_path / "quiet_valid.flac"
    first = bolt_scoring.save_audio_once(path, waveform, 48_000)
    second = bolt_scoring.save_audio_once(path, waveform, 48_000)
    assert first["recovered_existing"] is False
    assert second["recovered_existing"] is True
    assert first["output_sha256"] == second["output_sha256"]
    assert not list(tmp_path.glob("*.recovery.*"))


def test_gate15a_terminal_report_and_crossfit_audit():
    report = (ROOT / "BOLT_GATE15A_REPORT.md").read_text(encoding="utf-8")
    metrics = json.loads((ROOT / "BOLT_GATE15A_METRICS.json").read_text(encoding="utf-8"))
    assert "GATE15A = STOP_THIS_AXIS" in report
    assert "STATE_INCREMENTAL_VALUE = 0.000000000" in report
    assert "STATE_INCREMENTAL_VALUE_LCB95 = 0.000000000" in report
    assert metrics["gate15a"] == "STOP_THIS_AXIS"
    assert metrics["state_incremental_value"] == 0.0
    assert metrics["state_incremental_value_lcb95"] == 0.0
    assert "Gate 1.5B and Gate 2 were not started" in report

    predictions = list(csv.DictReader((ROOT / "BOLT_GATE15A_CROSSFIT_PREDICTIONS.csv").open()))
    assert len(predictions) == 288
    assert len({(row["prompt_id"], row["root_index"], row["checkpoint_step"]) for row in predictions}) == 288
    assert all(int(row["promptonly_program_nfe"]) <= 90 for row in predictions)
    assert all(int(row["promptstate_program_nfe"]) <= 90 for row in predictions)

    audit = json.loads((ROOT / "BOLT_GATE15A_MODEL_AUDIT.json").read_text(encoding="utf-8"))["models"]
    assert len(audit) == 36
    assert max(row["model"]["final_gradient_max"] for row in audit) <= 1e-9
    for row in audit:
        assert set(row["training_prompt_ids"]).isdisjoint(row["heldout_prompt_ids"])
        assert len(row["training_prompt_ids"]) == 40
        assert len(row["heldout_prompt_ids"]) == 8


def test_gate15a_feature_ledger_is_complete_and_proxy_free():
    features = [json.loads(line) for line in (ROOT / "BOLT_GATE15A_STATE_FEATURES.jsonl").read_text().splitlines()]
    assert len(features) == 288
    assert len({(row["prompt_id"], row["root_index"], row["checkpoint_step"]) for row in features}) == 288
    assert all(row["status"] == "PASS" for row in features)
    assert all(str(row["state_path"]).endswith(".pt") for row in features)
    assert all(str(row["preview_output_path"]).endswith(".flac") for row in features)
