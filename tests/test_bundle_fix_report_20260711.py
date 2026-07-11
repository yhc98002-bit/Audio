import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
PHASE = ROOT / "orbit-research/adsr_phase2_20260604"
PAPER_PREP = PHASE / "paper_prep"
OUTPUT = PAPER_PREP / "rater_bundles_20260711"
REPORT = OUTPUT / "BUNDLE_FIX_REPORT_20260711.md"
EXPECTED_STATUSES = [
    "BUNDLE_FIX_STATUS = READY",
    "REQUEST_METADATA_STATUS = PASS",
    "STAGED_REVEAL_STATUS = PASS",
    "ID_SEED_PRESERVATION_STATUS = PASS",
    "T2_T5_UNCHANGED_STATUS = PASS",
    "ARCHIVE_CHECKSUM_STATUS = PASS",
    "TEST_SUITE_STATUS = PASS",
]
STATUS = re.compile(r"^[A-Z][A-Z0-9_]* = \S+$")


def resolve_evidence(reference: str) -> Path:
    if reference.startswith("paper_prep/"):
        return PHASE / reference
    if reference.startswith("tests/"):
        return ROOT / reference
    raise AssertionError(f"unsupported evidence path: {reference}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_bundle_fix_report_has_artifact_backed_ready_contract():
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    statuses = [line for line in lines if STATUS.fullmatch(line)]
    assert statuses == EXPECTED_STATUSES
    for status in statuses:
        index = lines.index(status)
        assert lines[index + 1].startswith("evidence: ")
        references = lines[index + 1].removeprefix("evidence: ").split("; ")
        assert references
        for reference in references:
            assert resolve_evidence(reference).is_file(), reference


def test_three_v2_archives_are_listed_present_and_checksum_clean():
    expected_names = {
        "t1_decisive_v2.zip",
        "t3_bprime_primary_v2.zip",
        "t4_bprime_reverse_v2.zip",
    }
    entries = {}
    for line in (OUTPUT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        entries[Path(path).name] = (digest, Path(path))
    assert expected_names.issubset(entries)
    report_text = REPORT.read_text(encoding="utf-8")
    for name in expected_names:
        digest, path = entries[name]
        assert path.is_file(), path
        assert sha256(path) == digest
        assert str(path) in report_text
        assert digest in report_text
