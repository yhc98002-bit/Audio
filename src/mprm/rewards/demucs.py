import torch
import torchaudio

from mprm.data.prompts import Prompt


class DemucsVocalStem:
    """Extract the mono vocal stem with the upstream ``htdemucs`` ensemble.

    Inputs are resampled to the model rate and promoted to stereo before
    ``demucs.apply.apply_model``. The upstream default shift/split policy is
    retained, so callers that compare ratios across files must seed Python and
    Torch consistently. Load and inference errors propagate to the caller;
    this class does not substitute the mixture or a zero stem on failure.
    """
    version = "htdemucs"

    def __init__(self, device: str = "cuda"):
        self.device = device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from demucs.pretrained import get_model
            self._model = get_model(self.version).to(self.device).eval()

    def _prepare_waveform(self, waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
        self._ensure_loaded()
        target_sr = int(self._model.samplerate)
        if sample_rate != target_sr:
            waveform = torchaudio.functional.resample(waveform, sample_rate, target_sr)
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        if waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)
        return waveform.to(torch.float32)

    def _separate(self, waveform: torch.Tensor, sample_rate: int) -> tuple[torch.Tensor, float]:
        waveform = self._prepare_waveform(waveform, sample_rate)
        rms = float(torch.sqrt((waveform**2).mean()))
        from demucs.apply import apply_model
        with torch.no_grad():
            stems = apply_model(
                self._model,
                waveform.unsqueeze(0).to(self.device),
                device=self.device,
                shifts=1,
                split=True,
                overlap=0.1,
            )
        return stems[0], rms

    def extract_vocal(self, waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
        stems, _rms = self._separate(waveform, sample_rate)
        idx = self._model.sources.index("vocals")
        vocal = stems[idx].mean(dim=0).cpu()
        return vocal

    def vocal_energy_ratio(self, waveform: torch.Tensor, sample_rate: int) -> tuple[float, bool]:
        """Return ADSR's vocal-stem energy share and near-silent mixture flag."""
        stems, rms = self._separate(waveform, sample_rate)
        energies = (stems.to(torch.float32) ** 2).mean(dim=(1, 2))
        vocal_index = self._model.sources.index("vocals")
        ratio = float(energies[vocal_index] / energies.sum().clamp_min(1e-12))
        from mprm.common.thresholds import NEAR_SILENT_RMS_THRESHOLD

        return ratio, rms < NEAR_SILENT_RMS_THRESHOLD
