from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_survivor_fidelity_diagnosis_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("survivor_fidelity", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_survivor_diagnosis_fixes_first_candidate_identity():
    module = load_module()
    assert module.SEED == 2026052700
    assert module.ORIGINAL.name == "candidate_00_seed2026052700.wav"
    assert module.FINAL_ONLY.name == module.ORIGINAL.name


def test_decoded_hash_changes_with_sample_content(tmp_path):
    import soundfile as sf

    module = load_module()
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    sf.write(first, np.zeros((100, 2), dtype=np.float32), 48_000, subtype="FLOAT")
    sf.write(second, np.ones((100, 2), dtype=np.float32), 48_000, subtype="FLOAT")
    assert module.decoded_hash(first) != module.decoded_hash(second)
