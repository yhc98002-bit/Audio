import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
PHASE = ROOT / "orbit-research/adsr_phase2_20260604"
REPORT = PHASE / "paper_prep/rater_bundles_20260711/BUNDLE_JOB_REPORT_20260711.md"
EXPECTED = [
    "BUNDLES_STATUS = READY",
    "ADMIN_LEAK_TEST = PASS",
    "LIGHT_PLAN_ADDENDUM = DRAFTED_AWAITING_SIGNATURE",
    "CORRECTIVE_FLIP_SENTENCE = FIXED",
    "RATING_PROVENANCE_ENFORCED = PASS",
    "MERGE_SCRIPT_STATUS = IMPLEMENTED_TESTED",
    "W2_SCAFFOLD_STATUS = DRY_RUN_PASS",
    "TEST_SUITE_STATUS = PASS",
]
STATUS = re.compile(r"^[A-Z][A-Z0-9_]* = \S+$")


def resolve(reference: str) -> tuple[Path, str]:
    if reference.startswith("paper_prep/"):
        return PHASE / reference, f"orbit-research/adsr_phase2_20260604/{reference}"
    if reference.startswith("tests/"):
        return ROOT / reference, reference
    raise AssertionError(f"unsupported evidence path: {reference}")


def test_bundle_job_report_has_exact_eight_artifact_backed_statuses():
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    statuses = [line for line in lines if STATUS.fullmatch(line)]
    assert statuses == EXPECTED
    for status in statuses:
        index = lines.index(status)
        assert lines[index + 1].startswith("evidence: ")
        references = lines[index + 1].removeprefix("evidence: ").split("; ")
        assert references
        for reference in references:
            path, git_path = resolve(reference)
            assert path.is_file(), reference
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", git_path],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            assert tracked.returncode == 0, reference
