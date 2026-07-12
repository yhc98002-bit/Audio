from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_torch251_fidelity_probe_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_torch251_probe", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_gate_requires_every_one_of_51_exact_rows():
    module = load_module()
    exact = [{"exact": True} for _ in range(51)]
    assert module.probe_passes(51, exact)
    assert not module.probe_passes(50, exact)
    assert not module.probe_passes(51, exact[:-1])
    exact[-1]["exact"] = False
    assert not module.probe_passes(51, exact)


def test_runtime_and_full_replay_are_fail_closed_in_source():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'torch.__version__ != "2.5.1+cu121"' in source
    assert 'torchaudio.__version__ != "2.5.1+cu121"' in source
    assert "FAIL_STOP_FULL_REPLAY" in source
    assert '"full_replay_authorized_by_probe": passed' in source
