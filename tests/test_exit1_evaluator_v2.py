from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "analysis_exit1_v2/exit1_evaluator_v2.py"
SPEC = importlib.util.spec_from_file_location("exit1_evaluator_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _promotion_result(family: str = "or") -> dict:
    return {
        "CORRECTED_INSTRUMENT_STATUS": "PROMOTED",
        "heldout": {
            "selected_candidate": {
                "family": family,
                "demucs_threshold": 0.2,
                "panns_threshold": 0.3,
            }
        },
    }


def test_canonical_parse_records_exact_line_and_result_hash(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    result = tmp_path / "result.json"
    report.write_text("# Report\n\n- Selected family: `or`.\n", encoding="utf-8")
    result.write_text(json.dumps(_promotion_result()) + "\n", encoding="utf-8")

    parsed = MODULE.parse_canonical_instrument(report, result)

    assert parsed["family"] == "or"
    assert parsed["report_exact_line"] == "- Selected family: `or`."
    assert parsed["result_sha256"] == MODULE.sha256_file(result)


def test_canonical_parse_fails_closed_on_report_result_disagreement(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    result = tmp_path / "result.json"
    report.write_text("- Selected family: `and`.\n", encoding="utf-8")
    result.write_text(json.dumps(_promotion_result("or")) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="family mismatch"):
        MODULE.parse_canonical_instrument(report, result)


def test_canonical_or_is_not_silently_evaluated_as_and() -> None:
    assert MODULE.canonical_prediction("or", 0.25, 0.1, 0.2, 0.3) == 1
    assert MODULE.canonical_prediction("and", 0.25, 0.1, 0.2, 0.3) == 0


def test_power_limited_marker_is_adjacent_to_every_panel_metric() -> None:
    names = {"model": "Model"}
    thresholds = {"model": "rule"}
    metrics = {
        "model": {
            "sensitivity": 0.9,
            "specificity": 0.8,
            "balanced_accuracy": 0.85,
            "mcc": 0.7,
        }
    }
    intervals = {
        "model": {
            "sensitivity": [0.7, 1.0],
            "specificity": [0.6, 1.0],
            "balanced_accuracy": [0.7, 0.95],
            "mcc": [0.4, 0.9],
        }
    }

    rendered = "\n".join(
        MODULE.render_panel_table(names, thresholds, metrics, intervals, True)
    )

    assert rendered.count("POWER_LIMITED") == 4


def test_power_marker_absent_when_panel_has_sufficient_negatives() -> None:
    assert "POWER_LIMITED" not in MODULE.metric_cell(0.5, [0.4, 0.6], False)


def test_v2_output_is_separate_from_preserved_v1_evidence() -> None:
    assert MODULE.OUT.name == "analysis_exit1_v2"
    assert MODULE.V1.name == "analysis_exit1"
    assert MODULE.OUT.resolve() != MODULE.V1.resolve()
