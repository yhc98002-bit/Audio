"""CU-FW — fixed window credit unit.

Splits the audio into non-overlapping ``window_seconds``-second windows.
The last window may be shorter than ``window_seconds`` if the audio duration
is not a multiple of the window; it is kept rather than dropped, unless it
is shorter than ``min_tail_seconds`` (default 0.5 s) in which case it is
merged into the previous window.
"""
from __future__ import annotations

import torch

from mprm.credit_units.base import (
    CreditUnitOutput,
    CreditUnitSegment,
    CreditUnitSegmenter,
)
from mprm.data.prompts import Prompt


class FixedWindowUnit(CreditUnitSegmenter):
    unit_id = "CU-FW"

    def __init__(self, window_seconds: float = 4.0, min_tail_seconds: float = 0.5):
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds}")
        if min_tail_seconds < 0 or min_tail_seconds >= window_seconds:
            raise ValueError(
                f"min_tail_seconds={min_tail_seconds} must be in [0, window_seconds)"
            )
        self.window_seconds = window_seconds
        self.min_tail_seconds = min_tail_seconds

    def segment(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Prompt,
        seed: int = 0,
    ) -> CreditUnitOutput:
        duration = self._audio_duration_seconds(waveform, sample_rate)
        if duration <= 0:
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason="empty_audio",
                segments=[],
            )
        boundaries = []
        t = 0.0
        while t < duration:
            boundaries.append((t, min(t + self.window_seconds, duration)))
            t += self.window_seconds
        # Merge short tail into previous window if necessary.
        if len(boundaries) >= 2:
            last_start, last_end = boundaries[-1]
            if last_end - last_start < self.min_tail_seconds:
                prev_start, _ = boundaries[-2]
                boundaries[-2] = (prev_start, last_end)
                boundaries.pop()
        segments = [
            CreditUnitSegment(
                start_s=s,
                end_s=e,
                label=f"fw_{i:02d}",
                metadata={"index": i, "window_seconds": self.window_seconds},
            )
            for i, (s, e) in enumerate(boundaries)
        ]
        self._assert_segments_non_overlapping(segments)
        return CreditUnitOutput(
            unit_id=self.unit_id,
            applicable=True,
            segments=segments,
            metadata={
                "window_seconds": self.window_seconds,
                "min_tail_seconds": self.min_tail_seconds,
                "total_duration_seconds": duration,
            },
        )
