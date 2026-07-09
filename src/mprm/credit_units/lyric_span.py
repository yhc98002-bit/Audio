"""CU-LS — lyric span credit unit (D3: vocal/instrumental policy).

On **vocal prompts** (lyrics present + not flagged instrumental), transcribes
the audio with Whisper and uses Whisper's segment-level timestamps as lyric
phrase boundaries. (Word-level would also work but is more brittle on
synthetic / Tweedie-clean audio; phrase-level is sufficient for credit-unit
comparison.)

On **instrumental prompts**, returns ``applicable=False`` with reason
``"instrumental"`` — the H3 driver excludes CU-LS from the comparison on
that prompt and stratifies the report (D3).

The audio is optionally pre-processed by Demucs to isolate the vocal stem,
matching the lyric_intelligibility reward pipeline. Pass ``use_demucs=True``
(default) to enable.
"""
from __future__ import annotations

from typing import Any, Optional

import torch

from mprm.credit_units.base import (
    CreditUnitOutput,
    CreditUnitSegment,
    CreditUnitSegmenter,
)
from mprm.data.prompts import Prompt


def _is_instrumental(prompt: Prompt) -> bool:
    meta_flag = bool((prompt.metadata or {}).get("instrumental", False))
    no_lyrics = prompt.lyrics is None or len((prompt.lyrics or "").strip()) == 0
    return meta_flag or no_lyrics


class LyricSpanUnit(CreditUnitSegmenter):
    unit_id = "CU-LS"

    def __init__(
        self,
        whisper_model_size: str = "large-v3",
        language: str = "en",
        device: str = "cuda",
        use_demucs: bool = True,
        min_span_seconds: float = 0.3,
    ):
        self.whisper_model_size = whisper_model_size
        self.language = language
        self.device = device
        self.use_demucs = use_demucs
        self.min_span_seconds = min_span_seconds
        self._whisper: Any = None
        self._demucs: Any = None

    def is_applicable(self, prompt: Prompt) -> bool:
        return not _is_instrumental(prompt)

    def _ensure_loaded(self) -> None:
        if self._whisper is None:
            try:
                import whisper as openai_whisper  # type: ignore
                self._whisper = openai_whisper.load_model(
                    self.whisper_model_size, device=self.device
                )
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"whisper_load_failed: {type(e).__name__}") from e
        if self.use_demucs and self._demucs is None:
            try:
                from mprm.rewards.demucs import DemucsVocalStem
                self._demucs = DemucsVocalStem(device=self.device)
                self._demucs._ensure_loaded()  # noqa: SLF001
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"demucs_load_failed: {type(e).__name__}") from e

    def segment(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Prompt,
        seed: int = 0,
    ) -> CreditUnitOutput:
        # D3 instrumental policy: NA on instrumental.
        if not self.is_applicable(prompt):
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason="instrumental",
                segments=[],
                metadata={"d3_policy": "lyric_span_excluded_on_instrumental"},
            )

        try:
            self._ensure_loaded()
        except RuntimeError as e:
            reason = str(e).split(":", 1)[0]
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason=reason,
                segments=[],
                metadata={"load_error": str(e)},
            )

        duration = self._audio_duration_seconds(waveform, sample_rate)
        if duration <= 0:
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason="empty_audio",
                segments=[],
            )

        import torchaudio

        wav = waveform
        sr_eff = sample_rate

        # Optional vocal-stem isolation (Demucs).
        if self.use_demucs and self._demucs is not None:
            try:
                stem = self._demucs.extract_vocal(wav, sample_rate)
                wav = stem
                sr_eff = int(self._demucs._model.samplerate) if self._demucs._model else sample_rate
            except Exception as e:  # noqa: BLE001
                # Fall back to raw waveform — log in metadata.
                return CreditUnitOutput(
                    unit_id=self.unit_id,
                    applicable=False,
                    not_applicable_reason=f"demucs_failed: {type(e).__name__}",
                    segments=[],
                )

        # Resample to 16 kHz mono (Whisper standard).
        if sr_eff != 16_000:
            wav = torchaudio.functional.resample(wav, sr_eff, 16_000)
        if wav.dim() == 2:
            wav = wav.mean(dim=0)

        try:
            result = self._whisper.transcribe(
                wav.detach().cpu().numpy().astype("float32"),
                language=self.language,
                verbose=False,
            )
        except Exception as e:  # noqa: BLE001
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason=f"whisper_failed: {type(e).__name__}",
                segments=[],
            )

        whisper_segments = result.get("segments", []) or []
        segments: list[CreditUnitSegment] = []
        for i, s in enumerate(whisper_segments):
            start = max(0.0, min(float(s.get("start", 0.0)), duration))
            end = max(0.0, min(float(s.get("end", 0.0)), duration))
            if end <= start:
                continue
            if end - start < self.min_span_seconds:
                # Merge into previous if possible.
                if segments:
                    prev = segments[-1]
                    segments[-1] = CreditUnitSegment(
                        start_s=prev.start_s, end_s=end,
                        label=(prev.label or "") + " " + (s.get("text", "") or "").strip(),
                        metadata=prev.metadata,
                    )
                    continue
            text = (s.get("text") or "").strip()
            segments.append(CreditUnitSegment(
                start_s=start,
                end_s=end,
                label=text or f"ls_{i:02d}",
                metadata={"index": i, "whisper_text": text},
            ))

        if not segments:
            # Whisper produced no usable segments (e.g., silence on Tweedie-clean
            # very noisy σ). Mark NA with reason for transparency.
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason="no_lyric_spans_detected",
                segments=[],
                metadata={"whisper_transcript": result.get("text", "")},
            )

        self._assert_segments_non_overlapping(segments, tol=1e-2)
        return CreditUnitOutput(
            unit_id=self.unit_id,
            applicable=True,
            segments=segments,
            metadata={
                "whisper_model_size": self.whisper_model_size,
                "language": self.language,
                "use_demucs": self.use_demucs,
                "min_span_seconds": self.min_span_seconds,
                "total_duration_seconds": duration,
                "n_whisper_segments_raw": len(whisper_segments),
                "transcript": result.get("text", ""),
            },
        )
