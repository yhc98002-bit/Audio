from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "analysis_exit1/exit1_analysis.py"
SPEC = importlib.util.spec_from_file_location("exit1_analysis", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_binary_metrics_exact() -> None:
    result = MODULE.binary_metrics([1, 1, 0, 0], [1, 0, 0, 1])
    assert result["sensitivity"] == 0.5
    assert result["specificity"] == 0.5
    assert result["balanced_accuracy"] == 0.5
    assert result["mcc"] == 0.0


def test_threshold_selection_uses_scores_deterministically() -> None:
    result = MODULE.select_threshold(
        [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]
    )
    assert result["threshold"] == 0.8
    assert result["train_metrics"]["balanced_accuracy"] == 1.0


def test_threshold_selection_respects_transcript_eligibility() -> None:
    result = MODULE.select_threshold(
        [0, 0, 1, 1], [0.9, 0.3, 0.8, 0.7], [False, True, True, True]
    )
    assert result["threshold"] == 0.7
    assert result["train_metrics"]["balanced_accuracy"] == 1.0


def test_component_split_keeps_prompts_and_duplicate_media_together() -> None:
    rows = [
        {"prompt_id": "p1", "media_sha256": "a"},
        {"prompt_id": "p2", "media_sha256": "a"},
        {"prompt_id": "p2", "media_sha256": "b"},
        {"prompt_id": "p3", "media_sha256": "c"},
    ]
    MODULE._assign_component_split(rows, 0.4)
    split = {row["prompt_id"]: row["split"] for row in rows}
    assert split["p1"] == split["p2"]
    assert len({row["split"] for row in rows if row["media_sha256"] == "a"}) == 1


def test_attempt_selection_is_constraint_first_then_quality() -> None:
    selected = MODULE.select_attempt(
        [
            {"violation": 1, "quality_score": 10.0, "attempt_index": 0},
            {"violation": 0, "quality_score": 1.0, "attempt_index": 1},
            {"violation": 0, "quality_score": 2.0, "attempt_index": 2},
        ]
    )
    assert selected["attempt_index"] == 2


def test_unconditional_manifest_cardinality_and_seed_range() -> None:
    prompts = [
        {"prompt_id": f"p{index}", "stratum": "empty", "prompt_text": "", "replicates": "16"}
        for index in range(16)
    ]
    tasks = MODULE.build_unconditional_tasks(prompts, 2_036_000_000)
    assert len(tasks) == 256
    assert tasks[0]["seed"] == 2_036_000_000
    assert tasks[-1]["seed"] == 2_036_000_255
    assert len({row["seed"] for row in tasks}) == 256


def test_wilson_interval_contains_observed_rate() -> None:
    low, high = MODULE.wilson_interval(32, 100)
    assert low < 0.32 < high
    assert 0.0 <= low < high <= 1.0
