from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_spine_reconstruct_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_spine_reconstruct_20260712", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decoded_audio_hash_is_shape_and_rate_sensitive():
    module = load_module()
    samples = np.zeros((16, 2), dtype=np.float32)
    first = module.decoded_audio_hash(samples, 48_000)
    assert first == module.decoded_audio_hash(samples.copy(), 48_000)
    assert first != module.decoded_audio_hash(samples, 44_100)
    assert first != module.decoded_audio_hash(samples[:, :1], 48_000)


def test_spine_replay_and_candidate_thresholds_are_frozen():
    module = load_module()
    assert module.EXPECTED_ROWS == 4096
    assert module.EXPECTED_MISSING == 4095
    assert module.EXPECTED_SURVIVORS == 1
    assert module.OLD_THRESHOLD == 0.1791
    assert module.CANDIDATE_DEMUCS_THRESHOLD == 0.038639528676867485
    assert module.CANDIDATE_PANNS_THRESHOLD == 0.03181814216077328
    registry = (ROOT / "paper_prep/SEED_REGISTRY.md").read_text(encoding="utf-8")
    assert "W2 spine reconstruction" in registry
    assert "ACTIVE_REPLAY" in registry


def test_recovery_output_root_is_explicit_and_does_not_replace_default():
    module = load_module()
    default = module.PAPER / "w2_execution_20260712/spine_reconstruction"
    recovery = module.resolve_output_root(
        "paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery"
    )
    assert module.resolve_output_root() == default
    assert recovery == module.ROOT / "paper_prep/w2_execution_20260712/spine_reconstruction_torch251_recovery"
    assert recovery != module.OUT
