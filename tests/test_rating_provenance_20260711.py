from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/rating_provenance.py"
SPEC = importlib.util.spec_from_file_location("rating_provenance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("value,kind", [
    ("pi:Richard Ye", "pi"),
    ("human:CXY", "human"),
    (f"judge:qwen3-omni:validated:{'a' * 64}", "judge"),
])
def test_explicit_rating_source_enum_accepts_only_frozen_shapes(value, kind):
    assert MODULE.parse_rating_source(value).kind == kind


@pytest.mark.parametrize("value", [
    "",
    "pi",
    "pi_rater",
    "qwen_unvalidated",
    "automatic_model",
    "synthetic",
    "judge:qwen3-omni:unvalidated:" + "a" * 64,
    "judge:qwen3-omni:validated:short",
])
def test_explicit_rating_source_enum_rejects_aliases_and_unvalidated_sources(value):
    with pytest.raises(ValueError, match="invalid rating_source"):
        MODULE.parse_rating_source(value)


def test_validated_judge_requires_matching_metadata_and_raw_ledger(tmp_path):
    ledger = tmp_path / "raw.jsonl"
    ledger.write_text('{"ok": true}\n', encoding="utf-8")
    digest = hashlib.sha256(ledger.read_bytes()).hexdigest()
    gold_hash = "b" * 64
    source = MODULE.parse_rating_source(f"judge:qwen3-omni:validated:{gold_hash}")
    row = {
        "judge_validation_status": "PASS",
        "judge_model_id": "qwen3-omni",
        "judge_gold_set_hash": gold_hash,
        "judge_calibration_metrics": json.dumps({
            "sensitivity": 0.9,
            "specificity": 0.8,
            "balanced_accuracy": 0.85,
            "mcc": 0.7,
            "abstention_rate": 0.0,
        }),
        "judge_raw_response_ledger": str(ledger),
        "judge_raw_response_ledger_sha256": digest,
    }
    metrics = MODULE.require_validated_judge_metadata(row, source)
    assert metrics["balanced_accuracy"] == 0.85
    row["judge_validation_status"] = "PI_BLOCKED"
    with pytest.raises(ValueError, match="must be PASS"):
        MODULE.require_validated_judge_metadata(row, source)
