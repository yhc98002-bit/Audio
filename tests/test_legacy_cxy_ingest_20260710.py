from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "paper_prep/scripts/ingest_legacy_cxy_20260710.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ingest_legacy_cxy_20260710", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_arm_mapping_uses_pi_key_and_handles_ties():
    module = load_module()
    key = {"A_is": "arm1", "B_is": "arm6"}
    assert module.map_arm_preference("A", key) == "baseline"
    assert module.map_arm_preference("B", key) == "method"
    assert module.map_arm_preference("tie", key) == "tie"


def test_preference_summary_reports_both_tie_policies():
    module = load_module()
    rows = [
        {"contrast": "arm6_vs_arm1", "overall": "method"},
        {"contrast": "arm6_vs_arm1", "overall": "baseline"},
        {"contrast": "arm6_vs_arm1", "overall": "tie"},
    ]
    summary = module.preference_summary(rows, "overall")
    assert summary["tie_excluded"] == 0.5
    assert summary["ties_as_half"] == 0.5
    assert math.isclose(summary["ties_against_method"], 1 / 3)


def test_heldout_split_is_deterministic_and_stratified():
    module = load_module()
    first = [
        {"clip_id": f"clip-{index}", "source_bucket": "bucket", "true_label": label, "split": ""}
        for label in ("yes", "no")
        for index in range(10)
    ]
    second = [dict(row) for row in first]
    module.heldout_split(first)
    module.heldout_split(second)
    assert [(row["clip_id"], row["split"]) for row in first] == [
        (row["clip_id"], row["split"]) for row in second
    ]
    for label in ("yes", "no"):
        assert sum(row["split"] == "heldout" and row["true_label"] == label for row in first) == 2


def test_wilson_interval_contains_observed_rate():
    module = load_module()
    low, high = module.wilson_interval(7, 10)
    assert low < 0.7 < high


def test_input_record_accepts_repo_relative_path(monkeypatch, tmp_path):
    module = load_module()
    source = tmp_path / "input.csv"
    source.write_text("id\nvalue\n", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    record = module.input_record(Path("input.csv"))
    assert record["path"] == "input.csv"
    assert record["bytes"] == source.stat().st_size


def test_report_generator_names_every_historical_gui_join():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "phase3/human_ab/human_adsr_pairs.jsonl" in source
    assert "2_label_adjudication/response_sheet.csv" in source
    assert "HUMAN_PACKAGE_SOURCE_REFERENCES.csv" in source
    assert "2c_detector_agreement_spotcheck/response_sheet.csv" in source
