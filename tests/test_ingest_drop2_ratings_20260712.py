from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/ingest_drop2_ratings_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("drop2", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_lower_bound_and_tie_sensitivities() -> None:
    module = load_module()
    assert module.exact_binomial_lower(0, 10) == 0.0
    assert module.exact_binomial_lower(1, 1) == pytest.approx(0.05)
    assert module.exact_binomial_lower(20, 48) == pytest.approx(0.2958770027182114)
    result = module.endpoint_statistics(
        ["method"] * 20 + ["baseline"] * 28 + ["tie"] * 32
    )
    assert result["method_rate"] == pytest.approx(20 / 48)
    assert result["ties_as_half_rate"] == pytest.approx(0.45)
    assert result["ties_against_method_rate"] == pytest.approx(0.25)
    assert result["score_lower_gt_0p40"] is False
    assert result["exact_lower_gt_0p40"] is False


def test_real_drop_exact_ids_provenance_and_optional_t5_confidence() -> None:
    module = load_module()
    _p3, t3, audit3 = module.validate_and_remap_pair_export(
        module.T3_INPUT, module.T3_KEY, "t3_bprime_primary_v2", 80
    )
    _p4, t4, audit4 = module.validate_and_remap_pair_export(
        module.T4_INPUT, module.T4_KEY, "t4_bprime_reverse_v2", 24
    )
    _p5, t5, audit5 = module.validate_and_remap_t5()
    assert len(t3) == 80 and audit3["exact_id_set_match"]
    assert len(t4) == 24 and audit4["exact_id_set_match"]
    assert len(t5) == 60 and audit5["exact_id_set_match"]
    assert audit5["optional_confidence_missing"] == 59
    assert audit3["required_answer_blanks"] == 0
    assert audit4["required_answer_blanks"] == 0
    assert audit5["required_answer_blanks"] == 0


def test_b_prime_is_pi_pending_even_when_synthetic_numbers_are_strong() -> None:
    module = load_module()
    _payload, t3, _audit = module.validate_and_remap_pair_export(
        module.T3_INPUT, module.T3_KEY, "t3_bprime_primary_v2", 80
    )
    result, _primary, _pairs = module.score_b_prime(t3)
    assert result["b_prime_gate"] == "PI_CALL_PENDING"
    assert result["gate_never_auto_passes"] is True
    assert result["frozen_signed_condition_met"] is False
    quality = result["endpoints"]["quality_preference"]
    assert quality["counts"] == {
        "baseline": 28,
        "tie": 32,
        "method": 20,
        "abstain": 0,
    }
    assert quality["original_rule_pass"] is True


def test_pi_gate_decision_is_idempotent_and_evidence_locked(tmp_path: Path) -> None:
    module = load_module()
    module.STUDY_LOG = tmp_path / "study.jsonl"
    _payload, t3, _audit = module.validate_and_remap_pair_export(
        module.T3_INPUT, module.T3_KEY, "t3_bprime_primary_v2", 80
    )
    mechanical, _primary, _pairs = module.score_b_prime(t3)
    first = module.append_pi_gate_decision(mechanical)
    second = module.append_pi_gate_decision(mechanical)
    assert first == second
    assert len(module.STUDY_LOG.read_text(encoding="utf-8").splitlines()) == 1
    assert first["provenance"] == "pi:Richard"
    assert first["decision_date"] == "2026-07-12"
    assert first["b_prime_gate"] == "FAIL_NONINFERIORITY_NOT_ESTABLISHED"
    assert first["labeled_secondary"]["quality_preference"]["condition_met"] is True
    assert first["labeled_secondary"]["overall_preference"]["condition_met"] is True

    finalized = module.apply_pi_gate_decision(mechanical, first)
    assert finalized["b_prime_gate"] == "FAIL_NONINFERIORITY_NOT_ESTABLISHED"
    assert finalized["gate_never_auto_passes"] is True

    tampered = dict(first)
    tampered["provenance"] = "judge:qwen_unvalidated"
    with pytest.raises(ValueError, match="does not match"):
        module.apply_pi_gate_decision(mechanical, tampered)


def test_final_b_report_records_pi_call_and_limitations(tmp_path: Path) -> None:
    module = load_module()
    module.STUDY_LOG = tmp_path / "study.jsonl"
    module.B_REPORT = tmp_path / "report.md"
    _payload, t3, _audit = module.validate_and_remap_pair_export(
        module.T3_INPUT, module.T3_KEY, "t3_bprime_primary_v2", 80
    )
    mechanical, _primary, _pairs = module.score_b_prime(t3)
    decision = module.append_pi_gate_decision(mechanical)
    module.write_b_report(module.apply_pi_gate_decision(mechanical, decision))
    report = module.B_REPORT.read_text(encoding="utf-8")
    assert "B_PRIME_GATE = FAIL_NONINFERIORITY_NOT_ESTABLISHED" in report
    assert "Quality has one-sided p = 0.156163" in report
    assert "single expert rater" in report
    assert "40% tie rate" in report
    assert "pre-W2 detector" in report
    assert "t4 same-session protocol deviation" in report


def test_t4_same_session_deviation_and_informational_flags() -> None:
    module = load_module()
    p3, t3, _audit3 = module.validate_and_remap_pair_export(
        module.T3_INPUT, module.T3_KEY, "t3_bprime_primary_v2", 80
    )
    p4, t4, audit4 = module.validate_and_remap_pair_export(
        module.T4_INPUT, module.T4_KEY, "t4_bprime_reverse_v2", 24
    )
    _b, primary, pairs = module.score_b_prime(t3)
    result = module.analyze_t4(
        t3,
        t4,
        p3,
        p4,
        primary,
        pairs,
        audit4["sequence_anomalies_constraint_after_overall"],
    )
    assert result["protocol_deviation"] == "PROTOCOL_DEVIATION_T4_SAME_SESSION"
    assert result["later_day_rule_met"] is False
    assert result["agreement_interpretation"] == "UPPER_BOUND_ONLY"
    assert result["t6_supersedes_as_primary_rater_stability_evidence"] is True
    assert len(result["nonuniform_answer_triples"]) == 1
    assert len(result["constraint_overall_sequence_anomalies"]) == 1


def test_sa3_calibration_uses_unsure_as_abstain_and_remains_pilot() -> None:
    module = load_module()
    _payload, t5, _audit = module.validate_and_remap_t5()
    result = module.score_sa3(t5)
    assert result["sa3_label_calibration_status"] == "SCORED_PASS"
    assert result["overall"]["abstains"] == 4
    assert result["overall"]["balanced_accuracy"] == pytest.approx(13 / 18)
    assert result["by_calibration_band"]["near_threshold"]["abstains"] == 4
    assert result["sa3_disposition"] == "PILOT_REGARDLESS_OF_CALIBRATION_STATUS"


def test_pair_ingest_rejects_unknown_ids_and_unvalidated_sources(tmp_path: Path) -> None:
    module = load_module()
    payload = json.loads(module.T3_INPUT.read_text(encoding="utf-8"))
    payload["responses"][0]["rating_id"] = "unknown"
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly match"):
        module.validate_and_remap_pair_export(
            unknown, module.T3_KEY, "t3_bprime_primary_v2", 80
        )

    payload = json.loads(module.T3_INPUT.read_text(encoding="utf-8"))
    payload["rating_source"] = "qwen_unvalidated"
    invalid = tmp_path / "invalid_source.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="top-level rating_source"):
        module.validate_and_remap_pair_export(
            invalid, module.T3_KEY, "t3_bprime_primary_v2", 80
        )


def test_pair_ingest_rejects_blank_required_answer(tmp_path: Path) -> None:
    module = load_module()
    payload = json.loads(module.T3_INPUT.read_text(encoding="utf-8"))
    payload["responses"][0]["quality_preference"] = ""
    invalid = tmp_path / "blank.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="blank required fields"):
        module.validate_and_remap_pair_export(
            invalid, module.T3_KEY, "t3_bprime_primary_v2", 80
        )


def test_deviation_log_is_idempotent(tmp_path: Path) -> None:
    module = load_module()
    module.STUDY_LOG = tmp_path / "study.jsonl"
    result = {
        "protocol_deviation": "PROTOCOL_DEVIATION_T4_SAME_SESSION",
        "t3_exported_at": "2026-07-12T16:36:43.026Z",
        "t4_exported_at": "2026-07-12T17:09:36.829Z",
        "elapsed_seconds": 1973.803,
    }
    first = module.append_deviation_log(result)
    second = module.append_deviation_log(result)
    assert first == second
    assert len(module.STUDY_LOG.read_text(encoding="utf-8").splitlines()) == 1
