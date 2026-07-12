from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper_prep"
EXPECTED_GATE = "FAIL_NONINFERIORITY_NOT_ESTABLISHED"
EXPECTED_WORDING = (
    "no statistically significant quality preference in either direction "
    "(method preferred in 42% of decided pairs; one-sided p = 0.156); the "
    "pre-registered non-inferiority bound (LCB > 0.40) was NOT met, so "
    "no-quality-degradation is reported as unconfirmed, not established."
)


def _table_row(path: Path, row_number: int) -> list[str]:
    prefix = f"| {row_number} |"
    line = next(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(prefix))
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def test_gate_report_result_and_study_log_record_pi_decision() -> None:
    report = (PAPER / "validation_B_prime/B_PRIME_GATE_REPORT_20260712.md").read_text(
        encoding="utf-8"
    )
    result = json.loads(
        (PAPER / "validation_B_prime/B_PRIME_GATE_RESULT_20260712.json").read_text(
            encoding="utf-8"
        )
    )
    events = [
        json.loads(line)
        for line in (PAPER / "pi_ratings_20260712/DROP2_STUDY_LOG.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    decisions = [row for row in events if row.get("event") == "B_PRIME_PI_GATE_DECISION"]

    assert f"B_PRIME_GATE = {EXPECTED_GATE}" in report
    assert result["b_prime_gate"] == EXPECTED_GATE
    assert len(decisions) == 1
    assert decisions[0]["b_prime_gate"] == EXPECTED_GATE
    assert decisions[0]["provenance"] == "pi:Richard"
    assert decisions[0]["decision_date"] == "2026-07-12"
    assert decisions[0]["dual_pi_notified"] is True
    assert decisions[0]["no_rerating"] is True
    assert decisions[0]["no_study_enlargement"] is True
    assert decisions[0]["labeled_secondary"]["quality_preference"]["condition_met"] is True
    assert decisions[0]["labeled_secondary"]["overall_preference"]["condition_met"] is True


def test_plan_bprime_row_has_exact_reduced_wording_and_limitations() -> None:
    plan = PAPER / "PLAN.md"
    b_row = _table_row(plan, 11)
    limitations_row = _table_row(plan, 15)
    assert b_row[3] == "REDUCED"
    assert EXPECTED_WORDING in b_row[8]
    assert "20/48 = 0.416667" in b_row[4]
    assert "score LCB 0.307145" in b_row[4]
    assert "exact LCB 0.295877" in b_row[4]
    for phrase in (
        "single expert rater",
        "40% tie rate",
        "pre-W2 detector",
        "t4 same-session deviation",
    ):
        assert phrase in limitations_row[8]


def test_paper_backbone_uses_reduced_wording_and_discloses_limitations() -> None:
    claims = (PAPER / "CLAIMS.md").read_text(encoding="utf-8")
    claim_four = _table_row(PAPER / "CLAIMS.md", 4)
    assert "no quality cost" not in claim_four[1].lower()
    assert "non-inferiority bound was not met" in claim_four[1]
    assert EXPECTED_WORDING in " ".join(line.strip("> ") for line in claims.splitlines())
    for phrase in (
        "single expert rater",
        "40% tie rate",
        "pre-W2 detector",
        "same session as t3",
    ):
        assert phrase in claims
