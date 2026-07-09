"""CU-TS — timestep credit unit.

Reward delta is computed *across σ checkpoints* by the H3 driver, not across
spatial segments of the audio. From a spatial-segmentation perspective, the
timestep unit returns one segment covering the entire audio. The σ dimension
is orthogonal.
"""
from __future__ import annotations

import torch

from mprm.credit_units.base import (
    CreditUnitOutput,
    CreditUnitSegment,
    CreditUnitSegmenter,
)
from mprm.data.prompts import Prompt


class TimestepUnit(CreditUnitSegmenter):
    unit_id = "CU-TS"

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
        seg = CreditUnitSegment(
            start_s=0.0,
            end_s=duration,
            label="whole_audio",
            metadata={"note": "timestep credit unit: reward delta is per-σ, not spatial"},
        )
        return CreditUnitOutput(
            unit_id=self.unit_id,
            applicable=True,
            segments=[seg],
            metadata={"spatial_segmentation": "none; per-σ delta is the credit signal"},
        )
