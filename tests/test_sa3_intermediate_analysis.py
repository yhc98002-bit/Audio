import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/sao/stable_audio_3_medium/analyze_sa3_true_intermediate.py"
SPEC = importlib.util.spec_from_file_location("analyze_sa3_true_intermediate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_auroc_handles_ties_and_perfect_ordering():
    assert MODULE.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == pytest.approx(1.0)
    assert MODULE.auroc([0, 1], [0.5, 0.5]) == pytest.approx(0.5)


def test_classification_metrics_confusion_and_mcc():
    metrics = MODULE.classification_metrics([0, 0, 1, 1], [0.1, 0.8, 0.9, 0.2], 0.5)
    assert (metrics["tp"], metrics["tn"], metrics["fp"], metrics["fn"]) == (1, 1, 1, 1)
    assert metrics["balanced_accuracy"] == pytest.approx(0.5)
    assert metrics["mcc"] == pytest.approx(0.0)
