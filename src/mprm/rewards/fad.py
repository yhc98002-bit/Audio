"""Fréchet Audio Distance — side-instrument, not an RL reward (per BASELINE_CEILING §2).

Operates over a *batch* of generated audio against a reference set. Single-sample FAD is
undefined; this class returns a placeholder until a batch is supplied.
"""
from __future__ import annotations

import numpy as np
import torch

from mprm.data.prompts import Prompt
from mprm.rewards.interface import RewardModel, RewardScore


class FadReward(RewardModel):
    axis = "fad_distance"
    version = "vggish-fad-v1"

    def __init__(self, reference_features: np.ndarray | None = None, device: str = "cuda"):
        self.device = device
        self.reference_features = reference_features
        self._embedder = None

    def _ensure_loaded(self) -> None:
        if self._embedder is None:
            try:
                import torchvggish
            except ImportError as e:
                raise ImportError(
                    "torchvggish not installed; install via pip (used for FAD VGGish embeddings)"
                ) from e
            self._embedder = torchvggish.vggish().to(self.device).eval()

    def embed_batch(self, waveforms: list[torch.Tensor], sample_rate: int) -> np.ndarray:
        self._ensure_loaded()
        feats: list[np.ndarray] = []
        for w in waveforms:
            if w.dim() == 2:
                w = w.mean(dim=0)
            f = self._embedder(w.numpy(), sample_rate)
            feats.append(f.detach().cpu().numpy())
        return np.stack(feats, axis=0)

    @staticmethod
    def _frechet(mu1: np.ndarray, sigma1: np.ndarray, mu2: np.ndarray, sigma2: np.ndarray) -> float:
        from scipy.linalg import sqrtm
        diff = mu1 - mu2
        covmean = sqrtm(sigma1 @ sigma2)
        if np.iscomplexobj(covmean):
            covmean = covmean.real
        return float(diff @ diff + np.trace(sigma1 + sigma2 - 2 * covmean))

    def score(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt) -> RewardScore:
        return RewardScore(axis=self.axis, value=float("nan"),
                           raw={"reason": "single_sample_fad_undefined; use score_set"})

    def score_set(self, waveforms: list[torch.Tensor], sample_rate: int) -> RewardScore:
        if self.reference_features is None:
            return RewardScore(axis=self.axis, value=float("nan"),
                               raw={"reason": "no_reference_features"})
        gen = self.embed_batch(waveforms, sample_rate)
        mu_g, sig_g = gen.mean(axis=0), np.cov(gen, rowvar=False)
        mu_r, sig_r = self.reference_features.mean(axis=0), np.cov(self.reference_features, rowvar=False)
        fad = self._frechet(mu_g, sig_g, mu_r, sig_r)
        return RewardScore(axis=self.axis, value=fad, raw={"n_gen": gen.shape[0]})
