from pathlib import Path

import torch
import torchaudio


def load_audio(path: str | Path, target_sr: int | None = None) -> tuple[torch.Tensor, int]:
    waveform, sr = torchaudio.load(str(path))
    if target_sr is not None and sr != target_sr:
        waveform = torchaudio.functional.resample(waveform, sr, target_sr)
        sr = target_sr
    return waveform, sr


def save_audio(path: str | Path, waveform: torch.Tensor, sample_rate: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    torchaudio.save(str(path), waveform, sample_rate)
