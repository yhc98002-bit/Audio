import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


BASE = Path(__file__).parents[1] / "paper_prep/w2_contingency_20260711"


def load(name):
    path = BASE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(BASE))
    spec.loader.exec_module(module)
    return module


MANIFEST = load("build_w2_relabel_manifest")
INSTRUMENTS = load("w2_instruments")
RUNNER = load("run_w2_relabel")
RECOMPUTE = load("recompute_w2_headlines")
CALIBRATE = load("calibrate_w2_instrument")
MERGE = load("merge_w2_shards")


def test_frozen_ledger_inventory_is_deduplicated_and_preserves_old_label(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    ledgers = root / "ledgers"
    ledgers.mkdir()
    audio = root / "clip.flac"
    audio.touch()
    row = {
        "ok": True,
        "flac": str(audio),
        "prompt_id": "p1",
        "condition": "baseline",
        "seed_idx": 0,
        "requested_vocal": 1,
        "vocal_energy_ratio": 0.2,
        "near_silent": False,
        "present": 1,
    }
    (ledgers / "full_w0.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    old_root = MANIFEST.ROOT
    MANIFEST.ROOT = root
    try:
        records = MANIFEST.ledger_records("test", ledgers, "full_w*.jsonl")
    finally:
        MANIFEST.ROOT = old_root
    assert len(records) == 1
    assert records[0]["old_present"] == 1
    assert records[0]["media_available"] is True
    (ledgers / "full_w1.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    MANIFEST.ROOT = root
    try:
        with pytest.raises(ValueError, match="duplicate frozen-ledger key"):
            MANIFEST.ledger_records("test", ledgers, "full_w*.jsonl")
    finally:
        MANIFEST.ROOT = old_root


def test_stale_absolute_workspace_prefix_is_relocated(tmp_path):
    old_root = MANIFEST.ROOT
    root = tmp_path / "AudioDiffusion"
    audio = root / "paper_prep/clip.flac"
    audio.parent.mkdir(parents=True)
    audio.touch()
    MANIFEST.ROOT = root
    try:
        relocated = MANIFEST.canonical_audio_path(
            "/stale/home/AudioDiffusion/paper_prep/clip.flac"
        )
    finally:
        MANIFEST.ROOT = old_root
    assert relocated == audio.resolve()


def test_candidate_index_ignores_dangling_symlinks(tmp_path):
    root = tmp_path / "repo"
    runs = root / "runs/job/audio/dev_0000"
    runs.mkdir(parents=True)
    (runs / "candidate_00_seed1.wav").symlink_to(tmp_path / "missing.wav")
    old_root = MANIFEST.ROOT
    old_prep = MANIFEST.PAPER_PREP
    MANIFEST.ROOT = root
    MANIFEST.PAPER_PREP = root / "paper_prep"
    try:
        assert MANIFEST.candidate_audio_index() == {}
    finally:
        MANIFEST.ROOT = old_root
        MANIFEST.PAPER_PREP = old_prep


def test_runner_selects_only_available_requested_cohort():
    rows = [
        {"record_id": "a", "cohort": "stage3", "media_available": True, "audio_path": "/a"},
        {"record_id": "b", "cohort": "n2", "media_available": True, "audio_path": "/b"},
        {"record_id": "c", "cohort": "stage3", "media_available": False, "audio_path": ""},
    ]
    assert [row["record_id"] for row in RUNNER.select_rows(rows, 0, {"stage3"})] == ["a"]


def test_runner_sharding_is_disjoint_and_complete():
    rows = [
        {"record_id": str(index), "cohort": "stage3", "media_available": True, "audio_path": f"/{index}"}
        for index in range(17)
    ]
    shards = [RUNNER.select_rows(rows, 0, set(), 4, index) for index in range(4)]
    ids = [row["record_id"] for shard in shards for row in shard]
    assert len(ids) == len(set(ids)) == 17


def test_human_threshold_requires_calibration_artifact(tmp_path):
    with pytest.raises(FileNotFoundError):
        INSTRUMENTS.HumanCalibratedThresholdInstrument(
            "cpu", 0.2, tmp_path / "missing.json"
        )


def test_demucs_panns_ensemble_is_pluggable(monkeypatch, tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"audio")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    scores = tmp_path / "panns.csv"
    with scores.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["audio_sha256", "panns_score"])
        writer.writeheader()
        writer.writerow({"audio_sha256": digest, "panns_score": "0.9"})
    monkeypatch.setattr(
        INSTRUMENTS.CurrentDemucsInstrument,
        "score",
        lambda self, path: {"present": 0, "vocal_energy_ratio": 0.01},
    )
    instrument = INSTRUMENTS.DemucsPannsEnsembleInstrument(
        "cpu", scores, 0.5, "or"
    )
    assert instrument.score(audio)["present"] == 1


def test_unvalidated_judge_instrument_fails_closed(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text("audio_sha256,label\nabc,yes\n", encoding="utf-8")
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "rating_source": "qwen_unvalidated",
                "validation_status": "FAIL",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="rating_source"):
        INSTRUMENTS.ValidatedJudgeInstrument(labels, metadata)


def test_fully_validated_judge_instrument_scores_hash_join(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"audio")
    audio_hash = hashlib.sha256(audio.read_bytes()).hexdigest()
    labels = tmp_path / "labels.csv"
    labels.write_text(f"audio_sha256,label\n{audio_hash},yes\n", encoding="utf-8")
    raw = tmp_path / "raw.jsonl"
    raw.write_text('{"response":"yes"}\n', encoding="utf-8")
    raw_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
    gold_hash = "d" * 64
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "rating_source": f"judge:model:validated:{gold_hash}",
                "validation_status": "PASS",
                "model_id": "model",
                "gold_set_hash": gold_hash,
                "calibration_metrics": {
                    "sensitivity": 0.9,
                    "specificity": 0.8,
                    "balanced_accuracy": 0.85,
                    "mcc": 0.7,
                    "abstention_rate": 0.0,
                },
                "raw_response_ledger": str(raw),
                "raw_response_ledger_sha256": raw_hash,
            }
        ),
        encoding="utf-8",
    )
    instrument = INSTRUMENTS.ValidatedJudgeInstrument(labels, metadata)
    assert instrument.score(audio)["present"] == 1


def test_headline_diff_uses_old_and_corrected_labels_without_mutation():
    manifest = []
    corrected = []
    for index, (old, new) in enumerate([(1, 1), (0, 1)]):
        manifest.append(
            {
                "record_id": str(index),
                "cohort": "stage3_intervention",
                "condition": "vocal_guidance",
                "prompt_id": "p",
                "requested_vocal": 1,
                "old_present": old,
            }
        )
        corrected.append({"record_id": str(index), "status": "PASS", "present": new})
    rows = RECOMPUTE.compute_diff(manifest, corrected)
    rate = next(row for row in rows if row["metric"] == "clean_rate")
    assert rate["old_value"] == 0.5
    assert rate["corrected_value"] == 1.0
    assert manifest[1]["old_present"] == 0


def test_n2_diff_reports_old_and_corrected_regimes_and_request_strata():
    manifest = []
    corrected = []
    for index in range(16):
        manifest.append(
            {
                "record_id": str(index),
                "cohort": "n2_population_retry",
                "condition": "baseline",
                "prompt_id": "p",
                "requested_vocal": 1,
                "old_present": 0,
            }
        )
        corrected.append(
            {"record_id": str(index), "status": "PASS", "present": int(index < 8)}
        )
    rows = RECOMPUTE.compute_diff(manifest, corrected)
    easy = next(
        row
        for row in rows
        if row["metric"] == "n2_regime_prompt_count"
        and row["condition"] == "easy_ge_1_in_2"
    )
    rare = next(
        row
        for row in rows
        if row["metric"] == "n2_regime_prompt_count"
        and row["condition"] == "rare_le_1_in_16"
    )
    assert (easy["old_value"], easy["corrected_value"], easy["delta"]) == (0, 1, 1)
    assert (rare["old_value"], rare["corrected_value"], rare["delta"]) == (1, 0, -1)


def test_calibration_selection_uses_train_and_reports_heldout():
    rows = []
    for split in ("calibration", "heldout"):
        for index, (truth, demucs, panns) in enumerate(
            [("yes", 0.05, 0.9), ("yes", 0.08, 0.8), ("no", 0.01, 0.1), ("no", 0.02, 0.2)]
        ):
            rows.append(
                {
                    "clip_id": f"{split}-{index}",
                    "split": split,
                    "true_label": truth,
                    "demucs_vocal_energy_ratio": demucs,
                    "demucs_near_silent": False,
                    "panns_score": panns,
                }
            )
    result = CALIBRATE.calibrate(rows)
    assert result["status"] == "CALIBRATED_TRAIN_SELECTED_HELDOUT_AUDITED"
    assert result["selected_candidate"]["heldout_metrics"]["balanced_accuracy"] == 1.0
    assert result["plan_status_changed"] is False


def test_w2_shard_merge_requires_every_retained_row():
    manifest = [
        {"record_id": "a", "cohort": "stage3", "media_available": True, "audio_path": "/a"},
        {"record_id": "b", "cohort": "spine", "media_available": False, "audio_path": ""},
    ]
    rows, report = MERGE.merge(
        manifest,
        [[{"record_id": "a", "cohort": "stage3", "status": "PASS", "instrument_id": "test"}]],
    )
    assert len(rows) == 1
    assert report["status"] == "PASS_COMPLETE_RETAINED_AUDIO"
    assert report["demucs_score_source_counts"] == {
        "live_recomputed_initial_pass_pre_optimization": 1
    }


def test_calibrated_ensemble_reuses_frozen_demucs_ratio(monkeypatch, tmp_path):
    artifact = tmp_path / "calibration.json"
    artifact.write_text(
        json.dumps(
            {
                "status": "CALIBRATED_TRAIN_SELECTED_HELDOUT_AUDITED",
                "selected_candidate": {
                    "family": "and",
                    "demucs_threshold": 0.04,
                    "panns_threshold": 0.03,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        INSTRUMENTS.LivePannsInstrument,
        "__init__",
        lambda self, device, threshold: setattr(self, "threshold", threshold),
    )
    monkeypatch.setattr(
        INSTRUMENTS.LivePannsInstrument,
        "score",
        lambda self, path: {"panns_score": 0.5, "present": 1},
    )
    monkeypatch.setattr(
        INSTRUMENTS.CurrentDemucsInstrument,
        "score",
        lambda self, path: pytest.fail("live Demucs must not run when a frozen score exists"),
    )
    instrument = INSTRUMENTS.CalibratedCompositeInstrument("cuda", artifact)
    result = instrument.score_row(
        tmp_path / "clip.flac",
        {"old_vocal_energy_ratio": 0.2, "old_near_silent": False},
    )
    assert result["present"] == 1
    assert result["demucs_score_source"] == "precomputed_frozen_ledger"
