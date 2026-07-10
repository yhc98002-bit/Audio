from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(
    "build_v15_manifests_test",
    "orbit-research/adsr_phase2_20260604/paper_prep/scripts/build_v15_replication_manifests.py",
)
runner = load(
    "run_v15_replication_test",
    "orbit-research/adsr_phase2_20260604/paper_prep/scripts/run_v15_replication.py",
)
analysis = load(
    "analyze_v15_replication_test",
    "orbit-research/adsr_phase2_20260604/paper_prep/scripts/analyze_v15_replication.py",
)
audit = load(
    "audit_v15_replication_test",
    "orbit-research/adsr_phase2_20260604/paper_prep/scripts/audit_v15_replication.py",
)


def source_rows():
    return [
        {
            "prompt_id": f"p{index:03d}",
            "prompt_index": index,
            "vocal_stratum": "vocal" if index % 2 else "instrumental",
            "text": f"prompt {index}",
            "lyrics": "sing this" if index % 2 else None,
            "structure_hint": "AABA",
            "duration_target": 30,
        }
        for index in range(128)
    ]


def test_initial_v15_manifests_have_expected_shape_and_disjoint_seeds() -> None:
    smoke, prevalence = builder.build_manifests(source_rows())
    assert len(smoke) == 2
    assert len(prevalence) == 1024
    assert len({row["seed"] for row in prevalence}) == 1024
    assert not ({row["seed"] for row in smoke} & {row["seed"] for row in prevalence})
    assert {row["requested_vocal"] for row in smoke} == {0, 1}


def test_v15_conditioning_is_direction_aware() -> None:
    instrumental = {
        "text": "jazz trio",
        "lyrics": None,
        "requested_vocal": 0,
        "condition": "recondition",
    }
    text, lyrics, flag = runner.conditioned_inputs(instrumental)
    assert "no vocals" in text and lyrics == "[Instrumental]" and flag
    vocal = {
        "text": "pop song",
        "lyrics": "hello",
        "structure_hint": "AABA",
        "requested_vocal": 1,
        "condition": "recondition",
    }
    text, lyrics, flag = runner.conditioned_inputs(vocal)
    assert "human singing" in text and "AABA" in text and lyrics == "hello" and not flag


def test_v15_manifest_duplicate_keys_fail_closed() -> None:
    row = {"prompt_id": "p", "condition": "baseline", "seed": 1}
    with pytest.raises(ValueError, match="duplicate"):
        runner.unique_keys([row, dict(row)])


def test_v15_failed_attempt_can_retry_but_duplicate_pass_fails() -> None:
    row = {"prompt_id": "p", "condition": "baseline", "seed": 1}
    expected = {("p", "baseline", 1)}
    assert runner.completed_keys([{**row, "status": "FAIL"}], expected) == set()
    assert runner.completed_keys(
        [{**row, "status": "FAIL"}, {**row, "status": "PASS"}], expected
    ) == expected
    with pytest.raises(ValueError, match="duplicate successful"):
        runner.completed_keys(
            [{**row, "status": "PASS"}, {**row, "status": "PASS"}], expected
        )


def test_v15_materialization_is_atomic_and_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "scratch" / "clip.flac"
    source.parent.mkdir()
    source.write_bytes(b"completed-audio")
    destination = runner.materialize_generated_audio(source, tmp_path / "shared")
    assert destination.read_bytes() == b"completed-audio"
    assert not list((tmp_path / "shared").glob("*.partial.*"))
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        runner.materialize_generated_audio(source, tmp_path / "shared")


def test_v15_followup_manifests_are_balanced_paired_and_seed_disjoint() -> None:
    _, prevalence = builder.build_manifests(source_rows())
    scored = [{**row, "type_correct": int(row["manifest_index"] % 3 != 0)} for row in prevalence]
    rates = analysis.prompt_rates(scored)
    retry, intervention = analysis.followup_manifests(scored, rates)
    assert len(retry) == 16 * 32
    assert len(intervention) == 16 * 8 * 2
    selected = {row["prompt_id"]: row["vocal_stratum"] for row in retry}
    assert list(selected.values()).count("vocal") == 8
    assert list(selected.values()).count("instrumental") == 8
    pairs = {}
    for row in intervention:
        pairs.setdefault((row["prompt_id"], row["seed_idx"]), set()).add((row["condition"], row["seed"]))
    assert all(len(values) == 2 and len({seed for _condition, seed in values}) == 1 for values in pairs.values())
    assert not ({row["seed"] for row in retry} & {row["seed"] for row in intervention})
    assert all("type_correct" not in row and "audio_path" not in row for row in retry + intervention)


def test_v15_smoke_requires_both_request_strata(tmp_path: Path) -> None:
    rows = [{"requested_vocal": 0, "type_correct": 1}, {"requested_vocal": 1, "type_correct": 0}]
    analysis.analyze_smoke(rows, tmp_path)
    assert "V15_SMOKE_STATUS = PASS" in (tmp_path / "V15_SMOKE_REPORT.md").read_text()
    with pytest.raises(ValueError, match="one vocal"):
        analysis.analyze_smoke([rows[0], dict(rows[0])], tmp_path)


def test_v15_final_audit_accepts_failed_attempt_then_one_pass(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    generation_dir = tmp_path / "generation"
    score_dir = tmp_path / "score"
    generation_dir.mkdir()
    score_dir.mkdir()
    audio = tmp_path / "clip.flac"
    audio.write_bytes(b"audio")
    digest = audit.sha256_file(audio)
    row = {"prompt_id": "p", "condition": "baseline", "seed": 1}
    manifest_path.write_text(__import__("json").dumps(row) + "\n")
    attempts = [
        {**row, "status": "FAIL", "error": "RuntimeError: NaN"},
        {**row, "status": "PASS", "audio_path": str(audio), "audio_sha256": digest, "host": "h"},
    ]
    (generation_dir / "generation_w0.jsonl").write_text(
        "".join(__import__("json").dumps(value) + "\n" for value in attempts)
    )
    (score_dir / "score_w0.jsonl").write_text(
        __import__("json").dumps({**row, "near_silent": False}) + "\n"
    )
    original = audit.EXPECTED["smoke"]
    audit.EXPECTED["smoke"] = 1
    try:
        result, media, _scores = audit.audit_stage(
            "smoke", manifest_path, generation_dir, score_dir, True
        )
    finally:
        audit.EXPECTED["smoke"] = original
    assert result["generation_attempts"] == 2
    assert result["generation_fail"] == 1
    assert len(media) == 1
