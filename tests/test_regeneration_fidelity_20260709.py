from __future__ import annotations

import importlib.util
from importlib.machinery import PathFinder
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "orbit-research/adsr_phase2_20260604/paper_prep/scripts/regeneration_fidelity_20260709.py"
)
SPEC = importlib.util.spec_from_file_location("regeneration_fidelity_20260709", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_candidate_path_accepts_packet_path_union() -> None:
    assert MODULE.parse_candidate_path(
        "first/missing.wav|runs/x/audio/dev_0001/candidate_07_seed2026053707.wav"
    ) == (7, 2026053707)


def test_control_selection_preserves_minority_label_stratum() -> None:
    rows = [
        {
            "case_id": f"p{i:03d}",
            "analysis_role": "primary",
            "media_class": "original",
            "demucs_label_0p1791": "1",
        }
        for i in range(3)
    ] + [
        {
            "case_id": f"n{i:03d}",
            "analysis_role": "primary",
            "media_class": "original",
            "demucs_label_0p1791": "0",
        }
        for i in range(10)
    ]
    selected = MODULE.select_controls(rows, n=8)
    assert len(selected) == 8
    assert sum(row["demucs_label_0p1791"] == "1" for row in selected) == 3


def test_aligned_waveform_error_recovers_positive_lag() -> None:
    rng = np.random.default_rng(7)
    original = rng.normal(size=8000).astype(np.float32)
    replay = np.concatenate([np.zeros(80, dtype=np.float32), original])
    lag, nrmse = MODULE.aligned_waveform_error(original, replay, sample_rate=8000)
    assert abs(lag - 80) <= 4
    assert nrmse < 1e-8


def test_decoded_waveform_hash_is_content_not_container_hash() -> None:
    waveform = np.arange(24, dtype=np.float32).reshape(2, 12)
    assert MODULE.decoded_waveform_sha256(waveform, 48_000) == MODULE.decoded_waveform_sha256(
        waveform.copy(), 48_000
    )
    changed = waveform.copy()
    changed[0, 0] += 1
    assert MODULE.decoded_waveform_sha256(waveform, 48_000) != MODULE.decoded_waveform_sha256(
        changed, 48_000
    )
    assert MODULE.decoded_waveform_sha256(waveform, 48_000) != MODULE.decoded_waveform_sha256(
        waveform, 44_100
    )


def test_stable_scoring_seed_is_repeatable_and_identity_specific() -> None:
    assert MODULE.stable_scoring_seed("control:x") == MODULE.stable_scoring_seed("control:x")
    assert MODULE.stable_scoring_seed("control:x") != MODULE.stable_scoring_seed("control:y")


def test_shard_rows_are_disjoint_and_complete() -> None:
    rows = [{"id": index} for index in range(17)]
    shards = [MODULE.shard_rows(rows, index, 3) for index in range(3)]
    flattened = [row["id"] for shard in shards for row in shard]
    assert sorted(flattened) == list(range(17))
    assert len(flattened) == len(set(flattened))


def test_repository_scripts_package_wins_name_collision() -> None:
    root = Path(__file__).resolve().parents[1]
    package = PathFinder.find_spec("scripts", [str(root)])
    assert package is not None and package.submodule_search_locations is not None
    spec = PathFinder.find_spec(
        "scripts.collect_early_tweedie_validation",
        package.submodule_search_locations,
    )
    assert spec is not None and spec.origin is not None
    assert Path(spec.origin).resolve().parents[1] == root
