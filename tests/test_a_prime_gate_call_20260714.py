from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper_prep"


def load_script(name: str):
    path = PAPER / f"scripts/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_prime_pi_gate_call_is_exact_and_provenance_enforced():
    result = json.loads(
        (PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json").read_text()
    )
    assert result["A_PRIME_GATE"] == "FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED"
    assert result["legacy_instrument_validated"] is False
    assert result["demucs_missing_finding_quantified"] is True
    assert result["instrument_merge_rows"] == 690
    assert result["instrument_merge_provenance"] == {"human": 0, "judge": 500, "pi": 190}
    assert result["judge_validation_status"] == "PASS"
    assert result["pi_gate_decision"]["provenance"] == "pi:Richard"
    assert result["pi_gate_decision"]["decision_date"] == "2026-07-13"


def test_a_prime_failure_numbers_match_completed_evidence():
    result = json.loads(
        (PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json").read_text()
    )["label_a_bucket_results"]
    assert (result["detector_disagreement_112"]["matches"], result["detector_disagreement_112"]["decided"]) == (7, 112)
    assert (result["rare_basin_48"]["matches"], result["rare_basin_48"]["decided"]) == (16, 47)
    assert (result["agreement_spotcheck_30"]["matches"], result["agreement_spotcheck_30"]["decided"]) == (28, 30)
    assert (result["stratified_random_500"]["matches"], result["stratified_random_500"]["decided"]) == (124, 493)


def test_t6_carries_corrected_instrument_validity_without_relabeling_a_prime():
    result = json.loads(
        (PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json").read_text()
    )
    t6 = result["t6_corrected_instrument_evidence"]
    assert t6["status"] == "PROMOTED"
    assert abs(t6["balanced_accuracy"] - 0.9873081908896325) < 1e-12
    assert t6["sensitivity"] == 1.0
    assert abs(t6["specificity"] - 0.974616381779265) < 1e-12
    assert t6["label_a_repeat_agreement"] == [20, 20]
    assert t6["label_b_repeat_agreement"] == [20, 20]
    assert result["A_PRIME_GATE"].startswith("FAIL_")


def test_gate_call_recorder_is_idempotent():
    module = load_script("record_a_prime_gate_call_20260714")
    before_study = module.STUDY_LOG.read_bytes()
    before_gate = module.GATE_RESULT.read_bytes()
    audit = module.run()
    assert audit["status"] == "PASS"
    assert module.STUDY_LOG.read_bytes() == before_study
    assert module.GATE_RESULT.read_bytes() == before_gate
    study_rows = [json.loads(line) for line in before_study.decode().splitlines() if line]
    assert sum(row["event"] == "A_PRIME_PI_GATE_DECISION" for row in study_rows) == 1
    execution_rows = [
        json.loads(line)
        for line in module.EXECUTION_LEDGER.read_text().splitlines()
        if line
    ]
    assert sum(row.get("event_id") == "a-prime-gate-call-20260713-pi-richard" for row in execution_rows) == 1


def test_plan_and_claims_separate_legacy_failure_from_t6_validity():
    plan = (PAPER / "PLAN.md").read_text()
    claims = (PAPER / "CLAIMS.md").read_text()
    required = [
        "FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED",
        "balanced accuracy 0.987308",
        "sensitivity 1.000000",
        "specificity 0.974616",
    ]
    for marker in required:
        assert marker in plan
        assert marker in claims
    assert "legacy detector was validated" in plan
    assert "legacy 0.1791 Demucs-energy detector was validated" in claims
    assert "READY rows: 10" in plan
    assert "REDUCED rows: 6" in plan
    assert "0 amendment-compliant primary ratings" not in plan


def test_amendment_unlocks_live_while_adoption_supersession_remains_closed():
    builder = load_script("build_t7_evidence_bundle_20260713")
    statuses = builder.current_statuses()
    assert statuses["A_PRIME_GATE"] == "FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED"
    assert statuses["W2_AMENDMENT_STATUS"] == "SIGNED_BY_BOTH_PIS"
    assert statuses["W2_ADOPTION"] == "PI1_SIGNED_PI2_INCOMPLETE"
    assert statuses["PLAN_CLAIMS_SUPERSESSION"] == "NOT_APPLIED"
    assert statuses["LIVE_CONFIRM_STATUS"] == "COMPLETE_CRITERIA_NOT_ALL_MET"


def test_mechanical_scorer_cannot_overwrite_terminal_pi_gate_call():
    module = load_script("complete_t7_judge_aprime_20260713")
    before_result = module.A_GATE_JSON.read_bytes()
    before_report = module.A_GATE.read_bytes()
    with pytest.raises(RuntimeError, match="PI gate call is already recorded"):
        module.finalize_500()
    assert module.A_GATE_JSON.read_bytes() == before_result
    assert module.A_GATE.read_bytes() == before_report


def test_unblock_report_has_terminal_statuses_and_existing_evidence():
    report = PAPER / "validation_A_prime/A_PRIME_GATE_CALL_UNBLOCK_REPORT_20260714.md"
    lines = report.read_text().splitlines()
    expected = {
        "A_PRIME_GATE": "FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED",
        "T6_LABEL_VALIDITY_STATUS": "PROMOTED",
        "PLAN_CLAIMS_LABEL_VALIDITY": "UPDATED",
        "W2_AMENDMENT_STATUS": "SIGNED_BY_BOTH_PIS",
        "W2_ADOPTION": "PI1_SIGNED_PI2_INCOMPLETE",
        "PLAN_CLAIMS_SUPERSESSION": "NOT_APPLIED",
        "LIVE_CONFIRM_STATUS": "COMPLETE_CRITERIA_NOT_ALL_MET",
        "EVIDENCE_BUNDLE_CURRENT": "BUILT_PRE_ADOPTION",
        "EVIDENCE_BUNDLE_POST_ADOPTION": "BLOCKED_W2_ADOPTION",
        "TEST_SUITE_STATUS": "PASS",
    }
    for key, value in expected.items():
        index = lines.index(f"`{key} = {value}`")
        assert lines[index + 1].startswith("evidence:")
        paths = lines[index + 1].split("`")[1::2]
        assert paths and all((ROOT / path).exists() for path in paths)
