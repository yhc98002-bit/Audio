from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(
    "build_selfhost_pi_gold_smoke_test",
    "orbit-research/adsr_phase2_20260604/paper_prep/scripts/build_selfhost_pi_gold_smoke.py",
)
runner = load(
    "run_selfhost_audio_judge_test",
    "orbit-research/adsr_phase2_20260604/paper_prep/scripts/run_selfhost_audio_judge.py",
)


def test_parse_label_is_strict() -> None:
    assert runner.parse_label("YES") == "yes"
    assert runner.parse_label("answer: no") == "no"
    assert runner.parse_label("yes or no") is None
    assert runner.parse_label("instrumental") is None


def test_majority_and_metrics() -> None:
    assert runner.majority(["yes", "yes", "no"]) == "yes"
    assert runner.majority(["yes", "unsure", None]) == "unsure"
    assert runner.majority(["yes", "no", None]) == "unsure"
    metrics = runner.binary_metrics(
        [
            {"true_label": "yes", "majority_label": "yes"},
            {"true_label": "no", "majority_label": "no"},
            {"true_label": "yes", "majority_label": "unsure"},
        ]
    )
    assert metrics["balanced_accuracy"] == 1
    assert metrics["abstention_rate"] == pytest.approx(1 / 3)


def test_pi_gold_builder_fails_closed_then_selects_balanced() -> None:
    admin = []
    ratings = []
    for index in range(12):
        rating_id = f"r{index:02d}"
        admin.append(
            {
                "rating_id": rating_id,
                "package_media_path": f"media/{rating_id}.flac",
                "category": "control",
                "sha256": "a" * 64,
            }
        )
        ratings.append(
            {
                "rating_id": rating_id,
                "label_a_voice_presence": "",
                "confidence_1_to_5": "",
                "rating_source": "",
            }
        )
    with pytest.raises(ValueError, match="five"):
        builder.select_pi_gold(admin, ratings)
    for index, rating in enumerate(ratings):
        rating["label_a_voice_presence"] = "yes" if index < 6 else "no"
        rating["confidence_1_to_5"] = "5"
        rating["rating_source"] = "PI_primary"
    selected = builder.select_pi_gold(admin, ratings)
    assert len(selected) == 10
    assert [row["true_label"] for row in selected].count("yes") == 5
    assert [row["true_label"] for row in selected].count("no") == 5


def test_pi_gold_builder_rejects_duplicate_rating_ids() -> None:
    admin = [
        {
            "rating_id": "r00",
            "package_media_path": "media/r00.flac",
            "category": "control",
            "sha256": "a" * 64,
        }
    ]
    rating = {
        "rating_id": "r00",
        "label_a_voice_presence": "yes",
        "confidence_1_to_5": "5",
        "rating_source": "PI_primary",
    }
    with pytest.raises(ValueError, match="duplicate decisive rating"):
        builder.select_pi_gold(admin, [rating, rating.copy()])


def test_judge_manifest_rejects_duplicate_clip_ids() -> None:
    rows = [
        {"clip_id": "duplicate", "clip_path": "a.flac"},
        {"clip_id": "duplicate", "clip_path": "b.flac"},
    ]
    with pytest.raises(ValueError, match="present and unique"):
        runner.validate_manifest_rows(rows)


def test_canonical_request_replaces_embedded_audio() -> None:
    payload = {
        "model": "judge",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "audio_url", "audio_url": {"url": "data:audio/flac;base64,abc"}},
                    {"type": "text", "text": "question"},
                ],
            }
        ],
    }
    canonical = runner.canonical_request(payload, "f" * 64, "audio/flac")
    url = canonical["messages"][0]["content"][0]["audio_url"]["url"]
    assert url == f"sha256:{'f' * 64};media_type=audio/flac"
    assert payload["messages"][0]["content"][0]["audio_url"]["url"].startswith("data:")


def test_launcher_rejects_active_staging_marker(tmp_path: Path) -> None:
    (tmp_path / "model.safetensors.index.json").write_text("{}\n")
    (tmp_path / "STAGING_INCOMPLETE").touch()
    launch = ROOT / (
        "orbit-research/adsr_phase2_20260604/paper_prep/"
        "judge_selfhost_20260709/launch_vllm_an29.sh"
    )
    result = subprocess.run(
        ["bash", str(launch)],
        env={**os.environ, "MODEL_PATH": str(tmp_path), "ENV_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "staging marker remains" in result.stderr
