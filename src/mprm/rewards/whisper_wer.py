import torch
import torchaudio

from mprm.data.prompts import Prompt
from mprm.rewards.demucs import DemucsVocalStem
from mprm.rewards.feature_cache import AudioFeatureCache, maybe_cache_call
from mprm.rewards.interface import RewardModel, RewardScore


def _wer(ref: list[str], hyp: list[str]) -> float:
    n_ref = len(ref)
    if n_ref == 0:
        return 0.0 if not hyp else 1.0
    d = [[0] * (len(hyp) + 1) for _ in range(n_ref + 1)]
    for i in range(n_ref + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, n_ref + 1):
        for j in range(1, len(hyp) + 1):
            if ref[i - 1] == hyp[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(d[i - 1][j], d[i][j - 1], d[i - 1][j - 1])
    return d[n_ref][len(hyp)] / n_ref


def normalize(text: str) -> list[str]:
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)
    return [t for t in text.split() if t]


class WhisperWerReward(RewardModel):
    axis = "lyric_intelligibility"
    version = "openai-whisper-large-v3"

    def __init__(self, model_size: str = "large-v3", device: str = "cuda",
                 separate_vocals: bool = True, language: str | None = "en"):
        self.model_size = model_size
        self.device = device
        self.separate_vocals = separate_vocals
        self.language = language
        self._whisper = None
        self._demucs: DemucsVocalStem | None = None

    def _ensure_loaded(self) -> None:
        if self._whisper is None:
            import whisper
            self._whisper = whisper.load_model(self.model_size, device=self.device)
        if self.separate_vocals and self._demucs is None:
            self._demucs = DemucsVocalStem(device=self.device)

    def score(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt,
              cache: AudioFeatureCache | None = None) -> RewardScore:
        """Compute Whisper-WER score. Optional AudioFeatureCache for cross-axis reuse.

        The Demucs vocal-stem extraction is the dominant cost; it is cached
        under the key "demucs_vocal_stem" so other reward axes that need
        vocal stems can reuse it within the same scoring session
        (FINAL_REVISION_CRITIC.md #16).
        """
        self._ensure_loaded()
        if prompt.lyrics is None or prompt.lyrics.strip() == "":
            return RewardScore(axis=self.axis, value=1.0, raw={"reason": "instrumental_skip"})
        if self.separate_vocals and self._demucs is not None:
            # Use cached vocal stem if available; compute + cache otherwise.
            waveform = maybe_cache_call(
                cache,
                feature_name="demucs_vocal_stem",
                version=self._demucs.version,  # "htdemucs"
                compute_fn=lambda: self._demucs.extract_vocal(waveform, sample_rate),
                source_sr=sample_rate,
            )
            sample_rate_eff = int(self._demucs._model.samplerate) if self._demucs._model else sample_rate
        else:
            sample_rate_eff = sample_rate
        if sample_rate_eff != 16_000:
            waveform = torchaudio.functional.resample(waveform, sample_rate_eff, 16_000)
        if waveform.dim() == 2:
            waveform = waveform.mean(dim=0)
        result = self._whisper.transcribe(waveform.numpy(), language=self.language)
        hyp = normalize(result["text"])
        ref = normalize(prompt.lyrics)
        wer = _wer(ref, hyp)
        # P0.4 (2026-06-10, experiment_plan_current.md): optionally PERSIST transcripts so future
        # scoring runs keep them. Additive logging only — the reward value is unchanged. Enabled
        # by setting ADSR_TRANSCRIPT_DUMP to a target .jsonl path.
        import os
        dump = os.environ.get("ADSR_TRANSCRIPT_DUMP")
        if dump:
            try:
                import json as _json
                with open(dump, "a", encoding="utf-8") as _fh:
                    _fh.write(_json.dumps({"prompt_id": prompt.prompt_id, "wer": wer,
                                           "transcript": result["text"], "n_ref": len(ref),
                                           "n_hyp": len(hyp)}) + "\n")
            except Exception:
                pass  # logging must never affect scoring
        return RewardScore(
            axis=self.axis,
            value=max(0.0, 1.0 - wer),
            raw={"wer": wer, "transcript": result["text"], "n_ref": len(ref), "n_hyp": len(hyp)},
        )
