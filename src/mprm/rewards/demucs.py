import torch
import torchaudio

from mprm.data.prompts import Prompt


class DemucsVocalStem:
    """Demucs htdemucs vocal-stem extractor (A29). Falls back to no-separation on failure."""
    version = "htdemucs"

    def __init__(self, device: str = "cuda"):
        self.device = device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from demucs.pretrained import get_model
            self._model = get_model(self.version).to(self.device).eval()

    def extract_vocal(self, waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
        self._ensure_loaded()
        target_sr = int(self._model.samplerate)
        if sample_rate != target_sr:
            waveform = torchaudio.functional.resample(waveform, sample_rate, target_sr)
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        if waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)
        # STOP-B-8 Phase-2 (2026-05-18): htdemucs is a `BagOfModels` whose
        # `.forward()` raises `NotImplementedError("Call apply_model on this.")`.
        # The upstream entry point is `demucs.apply.apply_model`, which handles
        # the bag-of-models ensemble (shifts, splits, weight blending) and
        # returns a (batch, sources, channels, samples) tensor.
        from demucs.apply import apply_model
        with torch.no_grad():
            stems = apply_model(
                self._model,
                waveform.unsqueeze(0).to(self.device),
                device=self.device,
            )
        idx = self._model.sources.index("vocals")
        vocal = stems[0, idx].mean(dim=0).cpu()
        return vocal
