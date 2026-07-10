from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE_ROOT = ROOT / "orbit-research/adsr_phase2_20260604"
REPORT = PHASE_ROOT / "paper_prep/CODE_REVIEW_RECOVERY_REPORT_20260709.md"

ALLOWED_STATUS_VALUES = {
    "MODEL_IDENTITY_STATUS": {
        "RESOLVED_ACE_STEP_V1",
        "RESOLVED_ACE_STEP_V15",
        "MIXED_BACKBONES",
    },
    "A_PRIME_CARDINALITY_STATUS": {"RECONCILED", "ESCALATED"},
    "REGENERATION_FIDELITY_STATUS": {
        "EXACT",
        "LABEL_STABLE_ONLY",
        "NOT_REPRODUCIBLE",
    },
    "AMENDMENT_STATUS": {"DRAFTED_AWAITING_SIGNATURE", "SIGNED"},
    "BATCH3_REANALYSIS_STATUS": {"PASS", "DIFF_ESCALATED"},
    "PUBLICATION_STATS_V2_STATUS": {"PASS", "DIFF_ESCALATED"},
    "A_PRIME_PRIMARY_PACKAGE_STATUS": {
        "ORIGINAL_ONLY_PI_READY",
        "PI_AMENDMENT_REQUIRED",
    },
    "B_PRIME_PI_PACKAGE_STATUS": {"READY"},
    "JUDGE_VALIDATION_STATUS": {"PASS", "FAIL", "PI_BLOCKED"},
    "SA3_INTERMEDIATE_STATUS": {
        "TRUE_INTERMEDIATE_COMPLETE",
        "API_LIMITATION_PROVEN",
        "TIMEBOX_EXPIRED",
    },
    "SA3_LABEL_CALIBRATION_STATUS": {
        "PACKAGE_READY",
        "SCORED_PASS",
        "SCORED_FAIL",
    },
    "V15_REPLICATION_STATUS": {"COMPLETE", "TIMEBOX_EXPIRED", "NOT_TRIGGERED"},
    "TEST_SUITE_STATUS": {"PASS"},
    "P0_OPEN_COUNT": {"0"},
    "FULL_DRAFT_STATUS": {"NOT_READY", "READY"},
    "REDUCED_DRAFT_STATUS": {"READY_WITH_REDUCED_CLAIMS"},
}
STATUS_RE = re.compile(r"([A-Z][A-Z0-9_]+) = (\S+)")


def resolve_evidence_path(reference: str) -> tuple[Path, str]:
    if reference.startswith("paper_prep/"):
        return PHASE_ROOT / reference, f"orbit-research/adsr_phase2_20260604/{reference}"
    if reference.startswith(("src/", "scripts/", "tests/")):
        return ROOT / reference, reference
    raise AssertionError(f"evidence entry is not a supported file path: {reference!r}")


def test_code_review_recovery_report_satisfies_section_7_contract() -> None:
    assert REPORT.is_file()
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    status_rows = []

    for index, line in enumerate(lines):
        match = STATUS_RE.fullmatch(line)
        if match is None:
            continue
        key, value = match.groups()
        status_rows.append((key, value))
        assert index + 1 < len(lines), f"{key} has no following evidence line"
        evidence_line = lines[index + 1]
        assert evidence_line.startswith("evidence: "), (
            f"{key} is not immediately followed by an evidence line"
        )
        references = [item.strip() for item in evidence_line[10:].split(";")]
        assert references and all(references), f"{key} has empty evidence"
        for reference in references:
            path, git_path = resolve_evidence_path(reference)
            assert path.is_file(), f"missing evidence file for {key}: {reference}"
            if (ROOT / ".git").exists():
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", git_path],
                    cwd=ROOT,
                    capture_output=True,
                    check=False,
                )
                assert tracked.returncode == 0, (
                    f"evidence file for {key} is not tracked: {reference}"
                )

    expected_keys = list(ALLOWED_STATUS_VALUES)
    actual_keys = [key for key, _value in status_rows]
    assert actual_keys == expected_keys
    assert len(actual_keys) == 16
    for key, value in status_rows:
        assert value in ALLOWED_STATUS_VALUES[key]
    assert dict(status_rows)["TEST_SUITE_STATUS"] == "PASS"
    assert dict(status_rows)["P0_OPEN_COUNT"] == "0"
