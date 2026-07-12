from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).parents[1]
    / "paper_prep/rater_admin_keys_20260711/t2_aprime/merge_a_prime_instruments.py"
)
SPEC = importlib.util.spec_from_file_location("merge_a_prime_instruments", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fixtures(global_source: str = "human:CXY"):
    admin = []
    core = []
    global_rows = []
    for index in range(690):
        rating_id = f"r{index:04d}"
        role = "primary" if index < 190 else "global_bound"
        admin.append({"rating_id": rating_id, "analysis_role": role})
        rating = {
            "rating_id": rating_id,
            "label_a_voice_presence": "yes",
            "label_b_constraint": "satisfied",
            "rating_source": "human:CXY" if role == "primary" else global_source,
        }
        (core if role == "primary" else global_rows).append(rating)
    return admin, core, global_rows


def judge_metadata(tmp_path: Path):
    ledger = tmp_path / "raw.jsonl"
    ledger.write_text('{"response": "yes"}\n', encoding="utf-8")
    gold_hash = "d" * 64
    source = f"judge:qwen3-omni:validated:{gold_hash}"
    records = MODULE.normalize_judge_metadata([{
        "validation_status": "PASS",
        "model_id": "qwen3-omni",
        "gold_set_hash": gold_hash,
        "calibration_metrics": {
            "sensitivity": 0.9,
            "specificity": 0.8,
            "balanced_accuracy": 0.85,
            "mcc": 0.7,
            "abstention_rate": 0.0,
        },
        "raw_response_ledger": str(ledger),
    }])
    return source, records, ledger


def test_merge_accepts_human_core_and_human_global():
    admin, core, global_rows = fixtures()
    merged, report = MODULE.merge_instruments(admin, core, global_rows, {})
    assert len(merged) == 690
    assert report["provenance_counts"] == {"pi": 0, "human": 690, "judge": 0}


def test_core_can_be_registered_without_scoring_pending_global_track():
    admin, core, _global_rows = fixtures()
    assert MODULE.register_core_instrument(admin, core) == {"pi": 0, "human": 190}


def test_merge_accepts_only_fully_validated_judge_on_global_rows(tmp_path):
    source, metadata, ledger = judge_metadata(tmp_path)
    admin, core, global_rows = fixtures(source)
    merged, report = MODULE.merge_instruments(admin, core, global_rows, metadata)
    judge_rows = merged[190:]
    assert len(judge_rows) == 500
    assert {row["judge_model_id"] for row in judge_rows} == {"qwen3-omni"}
    assert {row["judge_raw_response_ledger_sha256"] for row in judge_rows} == {
        hashlib.sha256(ledger.read_bytes()).hexdigest()
    }
    assert report["provenance_counts"]["judge"] == 500


def test_merge_rejects_judge_on_core_rows(tmp_path):
    source, metadata, _ledger = judge_metadata(tmp_path)
    admin, core, global_rows = fixtures()
    for row in core:
        row["rating_source"] = source
    with pytest.raises(ValueError, match="requires pi"):
        MODULE.merge_instruments(admin, core, global_rows, metadata)


@pytest.mark.parametrize("source", ["", "qwen_unvalidated", "automatic_model", "unknown"])
def test_merge_rejects_unvalidated_or_unknown_global_source(source):
    admin, core, global_rows = fixtures(source)
    with pytest.raises(ValueError, match="rating_source"):
        MODULE.merge_instruments(admin, core, global_rows, {})


def test_merge_rejects_missing_judge_metadata(tmp_path):
    source, _metadata, _ledger = judge_metadata(tmp_path)
    admin, core, global_rows = fixtures(source)
    with pytest.raises(ValueError, match="metadata is missing"):
        MODULE.merge_instruments(admin, core, global_rows, {})


def test_merge_rejects_wrong_core_cardinality():
    admin, core, global_rows = fixtures()
    core.pop()
    with pytest.raises(ValueError, match="190 primary rows"):
        MODULE.merge_instruments(admin, core, global_rows, {})
