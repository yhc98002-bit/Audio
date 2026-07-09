"""CU-BW — beat-synchronous window credit unit.

Uses librosa beat tracker to detect beat times, then forms segments between
consecutive beats. Beat tracking is deterministic given a fixed seed
(librosa beat_track ignores numpy RNG state, so this segmenter is naturally
reproducible).

To avoid 100+ ultra-short segments, beats are grouped into "bars" of
``beats_per_bar`` consecutive beats (default 4). The bar boundaries are the
unit segments.

If beat tracking fails or returns no beats (e.g., pure-tone or silent audio),
the segmenter falls back to whole-audio (one segment) and records the
failure in metadata.
"""
from __future__ import annotations

import warnings

import torch

from mprm.credit_units.base import (
    CreditUnitOutput,
    CreditUnitSegment,
    CreditUnitSegmenter,
)
from mprm.data.prompts import Prompt


class BeatWindowUnit(CreditUnitSegmenter):
    unit_id = "CU-BW"

    def __init__(
        self,
        tempo_prior_bpm: float = 120.0,
        beats_per_bar: int = 4,
        min_bar_seconds: float = 0.5,
    ):
        if tempo_prior_bpm <= 0:
            raise ValueError(f"tempo_prior_bpm must be positive, got {tempo_prior_bpm}")
        if beats_per_bar <= 0:
            raise ValueError(f"beats_per_bar must be positive, got {beats_per_bar}")
        if min_bar_seconds < 0:
            raise ValueError(f"min_bar_seconds must be non-negative, got {min_bar_seconds}")
        self.tempo_prior_bpm = tempo_prior_bpm
        self.beats_per_bar = beats_per_bar
        self.min_bar_seconds = min_bar_seconds

    def segment(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Prompt,
        seed: int = 0,
    ) -> CreditUnitOutput:
        try:
            import librosa
            import numpy as np
        except ImportError as e:
            raise ImportError(
                "librosa + numpy required for BeatWindowUnit; install with "
                "`pip install librosa numpy`."
            ) from e

        duration = self._audio_duration_seconds(waveform, sample_rate)
        if duration <= 0:
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason="empty_audio",
                segments=[],
            )

        # Convert to mono numpy for librosa.
        if waveform.dim() == 2:
            mono = waveform.mean(dim=0)
        else:
            mono = waveform
        y = mono.detach().cpu().numpy().astype("float32")

        beats_failed = False
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _, beat_frames = librosa.beat.beat_track(
                    y=y, sr=sample_rate, start_bpm=self.tempo_prior_bpm, units="frames"
                )
            beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)
            beat_times = np.asarray(beat_times, dtype=float)
        except Exception:
            beats_failed = True
            beat_times = np.array([], dtype=float)

        if beats_failed or len(beat_times) < 2:
            # Fallback: whole-audio segment.
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=True,
                segments=[CreditUnitSegment(
                    start_s=0.0, end_s=duration, label="bw_whole",
                    metadata={"beat_tracking": "failed_or_insufficient_beats"}
                )],
                metadata={
                    "beat_tracking_failed": beats_failed,
                    "n_beats_detected": int(len(beat_times)),
                    "tempo_prior_bpm": self.tempo_prior_bpm,
                    "fallback": "whole_audio",
                },
            )

        # Form bar boundaries from every Nth beat.
        bar_boundaries = list(beat_times[:: self.beats_per_bar])
        # Ensure boundaries cover the audio: prepend 0.0 if first bar > 0; append duration.
        if bar_boundaries[0] > 1e-3:
            bar_boundaries = [0.0] + bar_boundaries
        if bar_boundaries[-1] < duration - 1e-3:
            bar_boundaries = bar_boundaries + [duration]

        # Build segments from consecutive boundaries, merging any ultra-short
        # edge segment into its neighbor rather than scoring a few milliseconds.
        raw_boundaries = [
            (float(bar_boundaries[i]), float(bar_boundaries[i + 1]))
            for i in range(len(bar_boundaries) - 1)
        ]
        merged_boundaries: list[tuple[float, float]] = []
        i = 0
        while i < len(raw_boundaries):
            s, e = raw_boundaries[i]
            if e - s < self.min_bar_seconds:
                if merged_boundaries:
                    prev_s, _ = merged_boundaries[-1]
                    merged_boundaries[-1] = (prev_s, e)
                elif i + 1 < len(raw_boundaries):
                    next_s, next_e = raw_boundaries[i + 1]
                    raw_boundaries[i + 1] = (s, next_e)
                else:
                    merged_boundaries.append((s, e))
                i += 1
                continue
            merged_boundaries.append((s, e))
            i += 1

        segments = [
            CreditUnitSegment(
                start_s=s,
                end_s=e,
                label=f"bw_{i:02d}",
                metadata={"index": i, "beats_per_bar": self.beats_per_bar},
            )
            for i, (s, e) in enumerate(merged_boundaries)
        ]
        self._assert_segments_non_overlapping(segments)
        return CreditUnitOutput(
            unit_id=self.unit_id,
            applicable=True,
            segments=segments,
            metadata={
                "n_beats_detected": int(len(beat_times)),
                "tempo_prior_bpm": self.tempo_prior_bpm,
                "beats_per_bar": self.beats_per_bar,
                "min_bar_seconds": self.min_bar_seconds,
                "total_duration_seconds": duration,
            },
        )
