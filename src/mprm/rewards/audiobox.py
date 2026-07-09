"""Audiobox-Aesthetics-4 reward (PQ axis by default).

STOP-B-8 Phase-1 (2026-05-17): audiobox_aesthetics 0.0.4 does NOT export a
top-level `AudioboxAestheticsModel` class. The actual public entry point is
`audiobox_aesthetics.infer.AesPredictor`, which:
  - takes `checkpoint_pth: str` (local path); if None, uses HF
    `hf_hub_download("facebook/audiobox-aesthetics", "checkpoint.pt")`
  - has a `.forward([{"path": waveform_tensor, "sample_rate": sr}])` API
    returning `[{"PQ": float, "PC": float, "CE": float, "CU": float}]`

The HF Python lib was unreliable on this box for the bert/roberta cases
(STOP-B-8 Phase-1 tokenizer shim issue), so we pre-download the checkpoint via
the public S3 URL `https://dl.fbaipublicfiles.com/audiobox-aesthetics/checkpoint.pt`
to `$AUDIOBOX_AES_CKPT` (default `/home/yehaocun23s/source/audiobox_aesthetics/checkpoint.pt`)
and pass the local path to `AesPredictor`. If the env var path doesn't exist,
we fall back to `initialize_predictor(ckpt=None)` which will re-attempt the
HF download.
"""
import os

import torch
import torchaudio

from mprm.data.prompts import Prompt
from mprm.rewards.interface import RewardModel, RewardScore


_DEFAULT_LOCAL_CKPT = "/home/yehaocun23s/source/audiobox_aesthetics/checkpoint.pt"


class AudioboxReward(RewardModel):
    axis = "aesthetic"
    version = "facebook/audiobox-aesthetics-v1"
    AXES = ("PQ", "PC", "CE", "CU")

    def __init__(self, target_axis: str = "PQ", device: str = "cuda"):
        if target_axis not in self.AXES:
            raise ValueError(f"axis must be in {self.AXES}; got {target_axis}")
        self.target_axis = target_axis
        self.axis = f"aesthetic_{target_axis.lower()}"
        self.device = device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from audiobox_aesthetics.infer import AesPredictor, initialize_predictor
        except ImportError as e:
            raise ImportError(
                "audiobox_aesthetics not installed. See "
                "github.com/facebookresearch/audiobox-aesthetics"
            ) from e
        ckpt_path = os.environ.get("AUDIOBOX_AES_CKPT", _DEFAULT_LOCAL_CKPT)
        if ckpt_path and os.path.isfile(ckpt_path):
            self._model = AesPredictor(checkpoint_pth=ckpt_path, data_col="path")
        else:
            # Fallback: let audiobox download via huggingface_hub. May fail on
            # this box if HF redirects misbehave, but kept for portability.
            self._model = initialize_predictor(ckpt=None)
        # AesPredictor.setup_model picks `cuda` if available — already aligned
        # with our CVD-pinned subprocess, so no per-device override is needed.

    def score(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt) -> RewardScore:
        self._ensure_loaded()
        # AesPredictor.audio_resample_mono handles resample + mono internally,
        # but it expects (channels, time). Ensure 2-D.
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        batch = [{"path": waveform, "sample_rate": sample_rate}]
        with torch.no_grad():
            results = self._model.forward(batch)
        # results: List[{"CE": float, "CU": float, "PC": float, "PQ": float}]
        row = results[0]
        score = float(row[self.target_axis])
        return RewardScore(
            axis=self.axis,
            value=score,
            raw={k: float(row[k]) for k in self.AXES},
        )
