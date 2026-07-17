from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "analysis_exit1_v2/dispatch_a_completion.py"
SPEC = importlib.util.spec_from_file_location("dispatch_a_completion", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_wilson_interval_contains_observed_rate() -> None:
    low, high = MODULE.wilson_interval(5, 10)
    assert low < 0.5 < high


def test_gate_selection_prefers_satisfaction_before_quality() -> None:
    selected = MODULE.select_gate_then_quality(
        [
            {"corrected_violation": 1, "quality_score": 99.0, "seed_idx": 0},
            {"corrected_violation": 0, "quality_score": 0.0, "seed_idx": 1},
        ]
    )
    assert selected["corrected_violation"] == 0
    assert selected["quality_score"] == 0.0


def test_unconditional_v2_has_primary_and_sensitivity_counts() -> None:
    rows = read_csv(ROOT / "analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2.csv")
    assert len(rows) == 6
    assert {(row["instrument_role"], row["value"]) for row in rows} == {
        (role, value)
        for role in ("PRIMARY", "SENSITIVITY_ONLY")
        for value in ("all", "empty", "neutral_text")
    }
    assert all(int(row["voice_present"]) + int(row["voice_absent"]) == int(row["n"]) for row in rows)
    historical = next(
        row
        for row in rows
        if row["instrument_role"] == "SENSITIVITY_ONLY" and row["value"] == "all"
    )
    primary = {
        row["value"]: row for row in rows if row["instrument_role"] == "PRIMARY"
    }
    assert int(primary["all"]["voice_present"]) == 187
    assert int(primary["empty"]["voice_present"]) == 98
    assert int(primary["neutral_text"]["voice_present"]) == 89
    assert int(historical["voice_present"]) == 171
    audit = json.loads(
        (ROOT / "analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2_AUDIT.json").read_text()
    )
    assert audit["primary_instrument"]["family"] == "or"
    assert audit["manifest_rows"] == 256
    assert audit["checksum_index_rows"] == 256
    assert audit["manifest_score_id_set_match"] is True
    assert audit["score_checksum_index_match"] is True
    assert audit["near_silent_clip_ids"] == ["exit1_uncond_111"]
    assert audit["generator_source_sha256"] == MODULE.sha256_file(SCRIPT)
    assert audit["new_music_generation"] == 0


def test_recipe_v2_primary_is_corrected_label_b_and_quality_is_proxy() -> None:
    rows = read_csv(ROOT / "analysis_exit1_v2/RECIPE_CURVES_V2.csv")
    assert len(rows) == 12
    assert {row["recipe"] for row in rows} == {
        "plain",
        "positive_text",
        "positive_sampler",
    }
    assert {int(row["attempts_N"]) for row in rows} == {1, 2, 4, 8}
    assert all(int(row["prompt_clusters"]) == 32 for row in rows)
    assert all(row["quality_status"] == "PROXY_QUALIFIED_SUCCESS" for row in rows)
    assert all(int(row["quality_primary"]) == 0 for row in rows)
    audit = json.loads(
        (ROOT / "analysis_exit1_v2/RECIPE_CURVES_V2_AUDIT.json").read_text()
    )
    assert audit["primary_endpoint"] == "corrected_label_b_violation"
    assert audit["quality_excluded_from_primary"] is True
    assert audit["best_deployable_claim_made"] is False
    assert audit["generator_source_sha256"] == MODULE.sha256_file(SCRIPT)
    assert audit["new_music_generation"] == 0


def test_recipe_v2_uses_equal_compute_paired_plain_baselines() -> None:
    rows = read_csv(ROOT / "analysis_exit1_v2/RECIPE_CURVES_V2.csv")
    for row in rows:
        if row["recipe"] == "plain":
            assert float(row["violation_delta_vs_equal_compute_plain"]) == 0.0
            assert float(row["qualified_success_delta_vs_equal_compute_plain"]) == 0.0
    report = (ROOT / "analysis_exit1_v2/RECIPE_CURVES_V2.md").read_text()
    assert "Best deployable operating point" not in report
    assert "Best observed (exploratory only)" in report
    assert "No deployment recommendation is made" in report
    assert "PROXY_QUALIFIED_SUCCESS" in report


def test_exit1_v2_final_report_contract() -> None:
    report_path = ROOT / "analysis_exit1_v2/EXIT1_V2_FINAL_REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    status_lines = [
        "ITEM_1_EVALUATOR_COMPARISON_V2_STATUS = COMPLETE",
        "ITEM_2_UNCONDITIONAL_BASE_RATE_V2_STATUS = COMPLETE",
        "ITEM_3_EVALUATOR_PANEL_UNIVERSE_STATUS = COMPLETE",
        "ITEM_4_AUDIOSET_HUMAN_VOICE_WHITELIST_STATUS = PASS",
        "ITEM_5_RECIPE_CURVES_V2_STATUS = COMPLETE",
        "ITEM_6_MATCHED_NEUTRAL_CONTROL_STATUS = COMPLETE",
        "ITEM_7_EXIT1_V2_FINAL_REPORT_STATUS = COMPLETE",
        "NEW_MUSIC_GENERATION = 0",
        "TEST_SUITE_STATUS = PASS",
    ]
    lines = report.splitlines()
    for status in status_lines:
        index = lines.index(status)
        assert lines[index + 1].startswith("evidence: ")
    assert "exact n=126 (117 decided positive, 9 decided negative" in report
    assert "exact n=451 (416 decided positive, 35 decided negative" in report
    assert "Implementation/evidence commit: `0265723`" in report
