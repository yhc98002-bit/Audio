"""Credit-unit segmenter base classes for Phase B.3 H3 (Where to Reward)."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Optional

import torch

from mprm.data.prompts import Prompt


@dataclass
class CreditUnitSegment:
    """One spatial segment of a generated audio.

    Fields:
      start_s, end_s: segment boundaries in seconds.
      label: optional string identifier (e.g. lyric text, section label).
      metadata: optional dict (e.g. beat indices, MERT cluster id, BPM).
    """
    start_s: float
    end_s: float
    label: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def duration(self) -> float:
        return self.end_s - self.start_s

    def __post_init__(self):
        if not math.isfinite(self.start_s) or not math.isfinite(self.end_s):
            raise ValueError(f"non-finite segment boundary: ({self.start_s}, {self.end_s})")
        if self.start_s < 0 or self.end_s < 0:
            raise ValueError(f"negative segment boundary: ({self.start_s}, {self.end_s})")
        if self.end_s <= self.start_s:
            raise ValueError(f"empty or inverted segment: start={self.start_s} end={self.end_s}")


@dataclass
class CreditUnitOutput:
    """Output of a credit-unit segmenter on one (waveform, prompt) pair."""
    unit_id: str
    applicable: bool
    not_applicable_reason: Optional[str] = None
    segments: list[CreditUnitSegment] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def n_segments(self) -> int:
        return len(self.segments)

    def total_covered_seconds(self) -> float:
        return sum(s.duration() for s in self.segments)


def _audio_duration_seconds(waveform: torch.Tensor, sample_rate: int) -> float:
    """Return waveform duration in seconds. Supports (T,) or (C, T)."""
    if sample_rate <= 0:
        raise ValueError(f"sample_rate must be positive, got {sample_rate}")
    if waveform.dim() == 1:
        n_samples = waveform.shape[0]
    elif waveform.dim() == 2:
        n_samples = waveform.shape[1]
    else:
        raise ValueError(f"unsupported waveform shape: {tuple(waveform.shape)}")
    return float(n_samples) / float(sample_rate)


class CreditUnitSegmenter:
    """Base class for credit-unit segmenters.

    Subclasses must override ``unit_id`` and ``segment()``. They may override
    ``is_applicable()`` to declare per-prompt non-applicability (e.g. lyric_span
    on instrumental prompts).
    """
    unit_id: str = "BASE"

    def is_applicable(self, prompt: Prompt) -> bool:
        return True

    def segment(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Prompt,
        seed: int = 0,
    ) -> CreditUnitOutput:
        """Return spatial segments for the given (waveform, prompt).

        ``seed`` is provided to support deterministic randomized segmenters
        (e.g. RandomSectionNullUnit). Deterministic segmenters ignore it.
        """
        raise NotImplementedError

    @staticmethod
    def _audio_duration_seconds(waveform: torch.Tensor, sample_rate: int) -> float:
        return _audio_duration_seconds(waveform, sample_rate)

    @staticmethod
    def _assert_segments_non_overlapping(
        segments: list[CreditUnitSegment], tol: float = 1e-3
    ) -> None:
        """Verify segments are sorted and non-overlapping within tolerance.

        Raises ValueError if any segment overlaps the next one beyond ``tol`` seconds.
        Used by segmenters that produce contiguous segments and by unit tests.
        """
        sorted_segs = sorted(segments, key=lambda s: s.start_s)
        for i in range(len(sorted_segs) - 1):
            a, b = sorted_segs[i], sorted_segs[i + 1]
            if b.start_s + tol < a.end_s:
                raise ValueError(
                    f"overlapping segments: ({a.start_s:.3f}, {a.end_s:.3f}) and "
                    f"({b.start_s:.3f}, {b.end_s:.3f})"
                )
