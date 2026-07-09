"""CU-MS — musical-section credit unit (MERT/CBM-style).

Uses MERT embeddings as the musical feature representation, then runs
librosa.segment.agglomerative to detect section boundaries. The minimum
section duration is enforced by merging adjacent shorter segments into
neighbors.

Approach:
  1. Compute MERT embeddings over the audio (uses ``mprm.rewards.mert``).
  2. Resample/pool embeddings to a feature matrix of shape (n_features, T_frames).
  3. Call librosa.segment.agglomerative with ``k`` boundaries (default 4
     sections — CBM-style intro/verse/chorus/outro prior; the actual labels are
     unknown — just numbered sections).
  4. Convert frame indices to seconds, enforce min_section_seconds.

If MERT loading fails, falls back to a librosa-only segmentation using
melspectrogram features — recorded in metadata for the audit trail.
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


class MusicalSectionUnit(CreditUnitSegmenter):
    unit_id = "CU-MS"

    def __init__(
        self,
        n_sections_prior: int = 4,
        min_section_seconds: float = 2.0,
        use_mert: bool = True,
        device: str = "cuda",
    ):
        if n_sections_prior < 2:
            raise ValueError(f"n_sections_prior must be >= 2, got {n_sections_prior}")
        self.n_sections_prior = n_sections_prior
        self.min_section_seconds = min_section_seconds
        self.use_mert = use_mert
        self.device = device
        self._mert: Any = None

    def _ensure_mert(self) -> None:
        if self.use_mert and self._mert is None:
            from mprm.rewards.mert import MertReward
            self._mert = MertReward(device=self.device)
            self._mert._ensure_loaded()  # noqa: SLF001

    def _mert_features(self, waveform: torch.Tensor, sample_rate: int) -> Any:
        """Return MERT-derived features as ``(n_features, T_frames)``."""
        try:
            self._ensure_mert()
            emb = self._mert.embed(waveform, sample_rate)  # shape varies
            # Normalize to 2-D feature matrix (n_features, T_frames). The
            # project MertReward.embed() returns (T_windows, D). Some MERT
            # variants return (layers, T, D), where we use the last layer.
            t = emb.detach().cpu()
            if t.dim() == 1:
                # Single-vector embed — degenerate; can't segment over time.
                return None
            if t.dim() == 3:
                # (layers, T, D) → take last layer.
                t = t[-1]
            # t is now (T, D) or (D, T). Convert to (D, T). For all H3 audio
            # durations, T_windows is far smaller than the MERT embedding
            # dimension; smoke previously exposed this by reporting
            # n_feature_frames=768 for every prompt.
            arr = t.numpy()
            if arr.shape[0] <= arr.shape[1]:
                return arr.T
            return arr
        except Exception:
            return None

    def _melspec_features(self, waveform: torch.Tensor, sample_rate: int) -> Any:
        """Fallback: log-mel spectrogram features."""
        import librosa  # type: ignore
        import numpy as np
        if waveform.dim() == 2:
            mono = waveform.mean(dim=0)
        else:
            mono = waveform
        y = mono.detach().cpu().numpy().astype("float32")
        ms = librosa.feature.melspectrogram(y=y, sr=sample_rate, n_mels=64)
        log_ms = librosa.power_to_db(ms, ref=np.max)
        return log_ms  # (n_mels, T)

    def segment(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Prompt,
        seed: int = 0,
    ) -> CreditUnitOutput:
        try:
            import librosa  # type: ignore
            import numpy as np
        except ImportError as e:
            raise ImportError(
                "librosa + numpy required for MusicalSectionUnit"
            ) from e

        duration = self._audio_duration_seconds(waveform, sample_rate)
        if duration <= 0:
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason="empty_audio",
                segments=[],
            )

        used_mert = False
        feat: Any = None
        if self.use_mert:
            feat = self._mert_features(waveform, sample_rate)
            used_mert = feat is not None
        if feat is None:
            feat = self._melspec_features(waveform, sample_rate)

        # Enforce minimum frames for agglomerative segmentation.
        if feat.shape[1] < self.n_sections_prior + 1:
            # Audio too short / feature degenerate. Fall back to whole audio.
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=True,
                segments=[CreditUnitSegment(
                    start_s=0.0, end_s=duration, label="ms_whole",
                    metadata={"reason": "insufficient_frames_for_segmentation"}
                )],
                metadata={
                    "used_mert": used_mert,
                    "n_feature_frames": int(feat.shape[1]),
                    "fallback": "whole_audio",
                },
            )

        # Effective n_sections: cap at min(prior, n_frames - 1).
        k = min(self.n_sections_prior, feat.shape[1] - 1)
        try:
            boundary_frames = librosa.segment.agglomerative(feat, k=k)
        except Exception as e:  # noqa: BLE001
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason=f"agglomerative_failed: {type(e).__name__}",
                segments=[],
            )

        # Convert frame indices to seconds.
        n_frames = feat.shape[1]
        frame_to_seconds = duration / float(n_frames)

        # Boundary frames are sorted; ensure they cover 0 → duration.
        bounds_s = sorted({float(b * frame_to_seconds) for b in boundary_frames})
        if not bounds_s or bounds_s[0] > 0.01:
            bounds_s = [0.0] + bounds_s
        if bounds_s[-1] < duration - 0.01:
            bounds_s = bounds_s + [duration]

        # Build sections.
        raw_sections: list[CreditUnitSegment] = []
        for i in range(len(bounds_s) - 1):
            s = bounds_s[i]
            e = bounds_s[i + 1]
            if e - s <= 0:
                continue
            raw_sections.append(CreditUnitSegment(
                start_s=s, end_s=e, label=f"ms_{i:02d}",
                metadata={"index": i, "used_mert": used_mert},
            ))

        # Enforce min_section_seconds by merging short sections into adjacent
        # sections while keeping contiguous coverage.
        merged: list[CreditUnitSegment] = []
        for seg in raw_sections:
            if seg.duration() < self.min_section_seconds and merged:
                prev = merged[-1]
                merged[-1] = CreditUnitSegment(
                    start_s=prev.start_s, end_s=seg.end_s,
                    label=prev.label, metadata=prev.metadata,
                )
            else:
                merged.append(seg)
        # Handle case where the first segment itself is too short by merging
        # into the second.
        if len(merged) >= 2 and merged[0].duration() < self.min_section_seconds:
            second = merged[1]
            merged[1] = CreditUnitSegment(
                start_s=merged[0].start_s, end_s=second.end_s,
                label=second.label, metadata=second.metadata,
            )
            merged.pop(0)

        if not merged:
            merged = [CreditUnitSegment(
                start_s=0.0, end_s=duration, label="ms_whole",
                metadata={"reason": "merge_collapsed_to_single"}
            )]

        self._assert_segments_non_overlapping(merged)
        return CreditUnitOutput(
            unit_id=self.unit_id,
            applicable=True,
            segments=merged,
            metadata={
                "used_mert": used_mert,
                "n_sections_prior": self.n_sections_prior,
                "min_section_seconds": self.min_section_seconds,
                "n_feature_frames": int(n_frames),
                "total_duration_seconds": duration,
            },
        )
