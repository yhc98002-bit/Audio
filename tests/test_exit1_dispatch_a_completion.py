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
