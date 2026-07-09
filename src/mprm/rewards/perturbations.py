"""Benign perturbations Π used for robust reward (METHOD_SPEC §2.2)."""
from __future__ import annotations

import io

import torch
import torchaudio


def _identity(w: torch.Tensor, sr: int) -> torch.Tensor:
    return w


def _crop(w: torch.Tensor, sr: int, ratio: float = 0.9) -> torch.Tensor:
    n = w.shape[-1]
    new_n = int(n * ratio)
    start = (n - new_n) // 2
    return w[..., start:start + new_n]


def _loudness(w: torch.Tensor, sr: int, gain_db: float = 3.0) -> torch.Tensor:
    g = 10.0 ** (gain_db / 20.0)
    return (w * g).clamp(-1.0, 1.0)


def _codec(w: torch.Tensor, sr: int, format: str = "mp3", bitrate: str = "128k") -> torch.Tensor:
    buf = io.BytesIO()
    try:
        torchaudio.save(buf, w if w.dim() == 2 else w.unsqueeze(0), sr,
                        format=format, encoding="PCM_S", bits_per_sample=16)
        buf.seek(0)
        loaded, _ = torchaudio.load(buf)
        if w.dim() == 1:
            loaded = loaded.squeeze(0)
        return loaded[..., :w.shape[-1]]
    except Exception:
        return w


def _fold_down(w: torch.Tensor, sr: int) -> torch.Tensor:
    if w.dim() == 2 and w.shape[0] == 2:
        return w.mean(dim=0, keepdim=True)
    return w


def _time_shift(w: torch.Tensor, sr: int, shift_ms: float = 100.0) -> torch.Tensor:
    s = int(shift_ms / 1000.0 * sr)
    return torch.roll(w, shifts=s, dims=-1)


PERTURBATIONS = {
    "identity": _identity,
    "crop": _crop,
    "loudness": _loudness,
    "codec": _codec,
    "fold_down": _fold_down,
    "time_shift": _time_shift,
}


def perturbation_set(names: list[str] | None = None):
    if names is None:
        names = list(PERTURBATIONS.keys())
    return {n: PERTURBATIONS[n] for n in names}
