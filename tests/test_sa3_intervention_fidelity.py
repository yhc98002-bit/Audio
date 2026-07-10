import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/sao/stable_audio_3_medium/audit_sa3_intervention_fidelity.py"
SPEC = importlib.util.spec_from_file_location("audit_sa3_intervention_fidelity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_audio_proxies_detect_silence_and_duration():
    import numpy as np

    values = MODULE.audio_proxies(np.zeros((8000, 2), dtype=np.float32), 8000)
    assert values["duration_s"] == pytest.approx(1.0)
    assert values["near_silent"] is True


def test_prompt_bootstrap_uses_prompt_means():
    rows = [
        {"prompt_id": "a", "delta": 0.0},
        {"prompt_id": "a", "delta": 2.0},
        {"prompt_id": "b", "delta": 3.0},
        {"prompt_id": "b", "delta": 3.0},
    ]
    mean, low, high = MODULE.paired_prompt_bootstrap(rows, "delta", reps=1000)
    assert mean == pytest.approx(2.0)
    assert low <= mean <= high


def test_clap_audit_source_forces_evaluation_mode():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "reward._model.model.eval()" in source
