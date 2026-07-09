"""MERT recurrence-consistency reward.

STOP-B-8 Phase-2 (2026-05-18): `transformers.AutoModel.from_pretrained
("m-a-p/MERT-v1-95M", trust_remote_code=True)` reaches for hf-mirror.com /
huggingface.co at load time, then fails on the 308 redirect chain on this
box (the same pathology the laion_clap shim mitigates). The fix mirrors
`AudioboxReward`: prefer a pre-staged LOCAL checkpoint directory, fall back
to the network hub name only if the local dir is absent.

Default local path: `$MERT_LOCAL_PATH` (env), else
`/home/yehaocun23s/source/mert/MERT-v1-95M/`. Place the following files
there (curl-able via `https://hf-mirror.com/m-a-p/MERT-v1-95M/resolve/main/<file>`):
  - config.json
  - configuration_MERT.py        (custom auto_map module)
  - modeling_MERT.py             (custom auto_map module)
  - preprocessor_config.json
  - pytorch_model.bin            (~377 MB HF-compatible weights)
"""
import os

import torch
import torchaudio

from mprm.data.prompts import Prompt
from mprm.rewards.interface import RewardModel, RewardScore


_DEFAULT_LOCAL_DIR = "/home/yehaocun23s/source/mert/MERT-v1-95M"


class MertReward(RewardModel):
    """MERT-based recurrence-consistency proxy for section coherence (A27).

    Computes a self-similarity matrix on MERT embeddings and reports a smoothness /
    recurrence score in [0, 1]. Phase B uses the same backbone for section segmentation.
    """
    axis = "section_coherence"
    version = "m-a-p/MERT-v1-95M"

    def __init__(self, model_name: str = "m-a-p/MERT-v1-95M", device: str = "cuda",
                 window_seconds: float = 4.0, hop_seconds: float = 2.0):
        self.model_name = model_name
        self.device = device
        self.window_seconds = window_seconds
        self.hop_seconds = hop_seconds
        self._processor = None
        self._model = None

    def _resolve_load_target(self) -> str:
        """Prefer pre-staged local checkpoint dir; fall back to the hub name.

        STOP-B-8 Phase-2: on boxes where hf-mirror.com redirect handling is
        broken, transformers' `from_pretrained` fails before any model code
        runs. The local-dir path lets the production pipeline work entirely
        offline once `pytorch_model.bin` + custom-modeling files are staged."""
        candidate = os.environ.get("MERT_LOCAL_PATH", _DEFAULT_LOCAL_DIR)
        if candidate and os.path.isdir(candidate) and os.path.isfile(
                os.path.join(candidate, "config.json")):
            return candidate
        return self.model_name

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from transformers import AutoModel, Wav2Vec2FeatureExtractor
            target = self._resolve_load_target()
            self._processor = Wav2Vec2FeatureExtractor.from_pretrained(
                target, trust_remote_code=True
            )
            self._model = AutoModel.from_pretrained(
                target, trust_remote_code=True
            ).to(self.device).eval()

    def embed(self, waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
        self._ensure_loaded()
        target_sr = int(self._processor.sampling_rate)
        if sample_rate != target_sr:
            waveform = torchaudio.functional.resample(waveform, sample_rate, target_sr)
        if waveform.dim() == 2:
            waveform = waveform.mean(dim=0)
        win = int(self.window_seconds * target_sr)
        hop = int(self.hop_seconds * target_sr)
        embs: list[torch.Tensor] = []
        for start in range(0, max(1, waveform.shape[-1] - win + 1), hop):
            seg = waveform[start: start + win]
            inputs = self._processor(seg.numpy(), sampling_rate=target_sr, return_tensors="pt")
            with torch.no_grad():
                hidden = self._model(**{k: v.to(self.device) for k, v in inputs.items()}).last_hidden_state
            embs.append(hidden.mean(dim=1).squeeze(0).cpu())
        return torch.stack(embs, dim=0) if embs else torch.zeros((0, 768))

    def score(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt) -> RewardScore:
        emb = self.embed(waveform, sample_rate)
        if emb.shape[0] < 2:
            return RewardScore(axis=self.axis, value=0.0, raw={"reason": "too_short"})
        e = emb / (emb.norm(dim=-1, keepdim=True) + 1e-8)
        sim = (e @ e.T).numpy()
        n = sim.shape[0]
        diag1 = sim[range(n - 1), range(1, n)]
        recurrence = float(diag1.mean())
        return RewardScore(axis=self.axis, value=recurrence, raw={"n_windows": n})
