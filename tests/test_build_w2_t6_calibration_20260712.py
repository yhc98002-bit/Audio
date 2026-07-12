from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/build_w2_t6_calibration_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_w2_t6", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_pool():
    rows = []
    for index in range(240):
        violation = index % 2
        rows.append(
            {
                "canonical_clip_id": f"clip{index:03d}",
                "candidate_violation": violation,
                "calibration_stratum": f"s{index % 12}",
            }
        )
    return rows


def test_stratified_pick_has_exact_class_counts_and_is_deterministic():
    module = load_module()
    first = module.stratified_pick(synthetic_pool(), 30, 30, "test")
    second = module.stratified_pick(synthetic_pool(), 30, 30, "test")
    assert [row["canonical_clip_id"] for row in first] == [row["canonical_clip_id"] for row in second]
    assert len(first) == 60
    assert sum(row["candidate_violation"] for row in first) == 30


def test_t6_cardinality_constants_and_source_lock():
    module = load_module()
    assert module.CORE_TRAIN == 60
    assert module.CORE_HELDOUT == 100
    assert module.TRANSPORT == 20
    assert module.REPEATS == 20
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'return v==="pi:Richard"' in source
    assert "sf.info" in source
    assert "media_sha256" in source
    assert "SPINE_REGEN_STATUS = COMPLETE_AUDIT_PASS" in source
    assert "READY_BLOCKED_ON_SIGNATURE" not in source  # status belongs to report, not executable gate logic


def test_csv_writer_preserves_fields_introduced_after_first_row(tmp_path):
    module = load_module()
    path = tmp_path / "heterogeneous.csv"
    module.write_csv(path, [{"a": 1}, {"a": 2, "later_field": 3}])
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    assert rows[0]["later_field"] == ""
    assert rows[1]["later_field"] == "3"


def test_sampling_frame_retains_all_cross_product_cells(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "SAMPLING_FRAME", tmp_path / "frame.csv")
    frame = [
        {
            "calibration_stratum": "vocal|low|old0|corrected0|disagree0|spine",
        }
    ]
    selection = [{**frame[0], "role": "train"}]
    result = module._write_sampling_frame(frame, selection)
    rows = list(csv.DictReader(module.SAMPLING_FRAME.open(newline="", encoding="utf-8")))
    assert result["cross_product_cells"] == 192
    assert result["empty_cross_product_cells"] == 191
    assert len(rows) == 192
    assert sum(int(row["frame_eligible_count"]) for row in rows) == 1


def test_appendix_resolver_uses_actual_admin_schema_and_checksum(tmp_path):
    module = load_module()
    media = tmp_path / "source.flac"
    media.write_bytes(b"frozen-media")
    row = {
        "source_path": media.name,
        "package_media_path": "missing.flac",
        "sha256": module.sha256_file(media),
    }
    assert module.resolve_appendix_media(row, tmp_path) == media


def test_versioned_paths_and_checksum_updates_preserve_other_bundles(tmp_path):
    module = load_module()
    assert module.resolve_repo_path("paper_prep/recovery", "unused") == module.ROOT / "paper_prep/recovery"
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    checksums = tmp_path / "SHA256SUMS"
    module.update_checksum_manifest(checksums, first)
    module.update_checksum_manifest(checksums, second)
    module.update_checksum_manifest(checksums, first)
    lines = checksums.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert any(str(first.resolve()) in line for line in lines)
    assert any(str(second.resolve()) in line for line in lines)
