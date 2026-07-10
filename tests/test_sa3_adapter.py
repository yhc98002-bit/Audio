import pytest
import torch

from mprm.inference.sa3 import SameTrajectoryCapture, normalize_capture_steps


def test_normalize_capture_steps_deduplicates_and_sorts():
    assert normalize_capture_steps([3, 1, 1, 0], 4) == (0, 1, 3)
    assert normalize_capture_steps(None, 3) == (0, 1, 2)


def test_normalize_capture_steps_rejects_out_of_range():
    with pytest.raises(ValueError, match="outside"):
        normalize_capture_steps([0, 4], 4)


def test_same_trajectory_capture_copies_only_requested_steps():
    capture = SameTrajectoryCapture([0, 2], total_steps=3)
    source = torch.tensor([[[1.0, 2.0]]])
    capture({"i": 0, "t": torch.tensor(1.0), "sigma": 1.0, "denoised": source})
    source.zero_()
    capture({"i": 1, "t": 0.5, "sigma": 0.5, "denoised": source})
    capture({"i": 2, "t": 0.1, "sigma": torch.tensor([0.1]), "denoised": source})
    capture.assert_complete()

    assert capture.latents[0].tolist() == [[[1.0, 2.0]]]
    assert sorted(capture.latents) == [0, 2]
    assert capture.metadata[2]["sigma"] == pytest.approx(0.1)


def test_same_trajectory_capture_fails_closed_on_missing_callback():
    capture = SameTrajectoryCapture([0, 2], total_steps=3)
    capture({"i": 0, "t": 1.0, "sigma": 1.0, "denoised": torch.zeros(1, 1, 1)})
    with pytest.raises(RuntimeError, match="omitted"):
        capture.assert_complete()
