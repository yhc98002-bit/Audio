from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_judge_track_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_judge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gold_media_cannot_cross_tuning_and_evaluation():
    module = load_module()
    admin = [
        {"rating_id": "a", "role": "train", "media_sha256": "same", "canonical_clip_id": "a", "media_path": "a.wav", "request_mode": "vocal", "calibration_stratum": "s", "inclusion_probability": "1"},
        {"rating_id": "b", "role": "heldout", "media_sha256": "same", "canonical_clip_id": "b", "media_path": "b.wav", "request_mode": "vocal", "calibration_stratum": "s", "inclusion_probability": "1"},
    ]
    ratings = [
        {"rating_id": "a", "rating_source": "pi:Richard", "label_b_constraint": "satisfied"},
        {"rating_id": "b", "rating_source": "pi:Richard", "label_b_constraint": "violated"},
    ]
    try:
        module.build_disjoint_gold(admin, ratings)
    except ValueError as exc:
        assert "crosses" in str(exc)
    else:
        raise AssertionError("overlapping media entered judge train/evaluation")


def test_three_call_majority_and_abstention():
    module = load_module()
    raw = [
        {"rating_id": "a", "parsed_label_b": value}
        for value in ("violated", "violated", "unsure")
    ] + [
        {"rating_id": "b", "parsed_label_b": value}
        for value in ("satisfied", "violated", "unsure")
    ]
    assert module.majority_responses(raw) == {"a": "violated", "b": "unsure"}
