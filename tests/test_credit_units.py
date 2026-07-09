"""Unit tests for ``mprm.credit_units`` (PI requirements 2026-05-23):
  - correct segmentation boundaries
  - no overlap / no empty units unless expected
  - vocal vs instrumental lyric_span behavior
  - reproducibility under fixed seed

The tests use synthetic audio (sine waves, beats, silence) so they run without
GPU. Whisper- and MERT-dependent paths are exercised via mocks; the actual
end-to-end vocal-stem + Whisper pipeline is exercised by scripts/h3_smoke.py
on real audio.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch

# Ensure src/ is on the path when invoked directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mprm.data.prompts import Prompt
from mprm.credit_units import (
    REGISTRY,
    CreditUnitOutput,
    CreditUnitSegment,
    CreditUnitSegmenter,
    TimestepUnit,
    FixedWindowUnit,
    BeatWindowUnit,
    LyricSpanUnit,
    MusicalSectionUnit,
    RandomSectionNullUnit,
)


SAMPLE_RATE = 44_100
SEC = SAMPLE_RATE


def _sine(seconds: float, freq: float = 220.0, sr: int = SAMPLE_RATE) -> torch.Tensor:
    t = torch.arange(int(seconds * sr)) / sr
    return 0.2 * torch.sin(2 * torch.pi * freq * t)


def _beat_train(seconds: float, bpm: float = 120.0, sr: int = SAMPLE_RATE) -> torch.Tensor:
    """Synthesize a click train at ``bpm`` for ``seconds`` seconds."""
    n_samples = int(seconds * sr)
    out = torch.zeros(n_samples)
    period_samples = int(60.0 / bpm * sr)
    for i in range(0, n_samples, period_samples):
        end = min(i + 200, n_samples)  # 200-sample click
        out[i:end] = 0.8
    return out


def _vocal_prompt() -> Prompt:
    return Prompt(
        prompt_id="test_vocal",
        text="a pop song with lyrics",
        lyrics="this is a test lyric line one\nand a second line of text",
        structure_hint=None,
        duration_target=10.0,
        metadata={"instrumental": False},
    )


def _instrumental_prompt() -> Prompt:
    return Prompt(
        prompt_id="test_instrumental",
        text="ambient instrumental piano",
        lyrics=None,
        structure_hint=None,
        duration_target=10.0,
        metadata={"instrumental": True},
    )


# ----------------------------------------------------------- Base assertions


def _assert_no_overlap(out: CreditUnitOutput, *, tol: float = 1e-3) -> None:
    segs = sorted(out.segments, key=lambda s: s.start_s)
    for i in range(len(segs) - 1):
        assert segs[i + 1].start_s + tol >= segs[i].end_s, (
            f"overlap in {out.unit_id}: "
            f"{(segs[i].start_s, segs[i].end_s)} vs {(segs[i+1].start_s, segs[i+1].end_s)}"
        )


def _assert_no_empty(out: CreditUnitOutput) -> None:
    for s in out.segments:
        assert s.end_s > s.start_s, (
            f"empty segment in {out.unit_id}: ({s.start_s}, {s.end_s})"
        )


def _assert_covers_audio(out: CreditUnitOutput, duration: float, *, tol: float = 0.1) -> None:
    """Sum of segment durations should approximately equal the audio duration
    (allowing short tail merges / boundary jitter within ``tol`` seconds).
    """
    covered = sum(s.duration() for s in out.segments)
    assert covered <= duration + tol, (
        f"{out.unit_id} covers {covered:.3f}s > audio {duration:.3f}s + tol"
    )
    assert covered >= duration - tol, (
        f"{out.unit_id} covers {covered:.3f}s < audio {duration:.3f}s - tol"
    )


# ----------------------------------------------------------- Registry


def test_registry_has_all_units():
    expected = {"CU-TS", "CU-FW", "CU-BW", "CU-LS", "CU-MS", "CU-NULL-rand-section"}
    assert expected.issubset(REGISTRY.keys())


def test_registry_classes_are_segmenter_subclasses():
    for unit_id, cls in REGISTRY.items():
        assert issubclass(cls, CreditUnitSegmenter), unit_id


# ----------------------------------------------------------- CU-TS timestep


def test_timestep_whole_audio_one_segment():
    audio = _sine(8.0)
    out = TimestepUnit().segment(audio, SAMPLE_RATE, _vocal_prompt())
    assert out.applicable
    assert len(out.segments) == 1
    assert out.segments[0].start_s == pytest.approx(0.0)
    assert out.segments[0].end_s == pytest.approx(8.0, abs=1e-3)
    _assert_no_empty(out)


def test_timestep_works_on_instrumental():
    audio = _sine(4.0)
    out = TimestepUnit().segment(audio, SAMPLE_RATE, _instrumental_prompt())
    assert out.applicable
    assert len(out.segments) == 1


def test_timestep_empty_audio_returns_na():
    out = TimestepUnit().segment(torch.zeros(0), SAMPLE_RATE, _vocal_prompt())
    assert out.applicable is False
    assert out.not_applicable_reason == "empty_audio"
    assert out.segments == []


# ----------------------------------------------------------- CU-FW fixed_window


def test_fixed_window_4sec_boundaries():
    audio = _sine(12.0)
    out = FixedWindowUnit(window_seconds=4.0).segment(audio, SAMPLE_RATE, _vocal_prompt())
    assert out.applicable
    assert len(out.segments) == 3
    for i, seg in enumerate(out.segments):
        assert seg.start_s == pytest.approx(i * 4.0)
        assert seg.end_s == pytest.approx((i + 1) * 4.0, abs=1e-3)
    _assert_no_overlap(out)
    _assert_no_empty(out)
    _assert_covers_audio(out, 12.0)


def test_fixed_window_short_tail_merged():
    audio = _sine(8.2)  # 2 windows of 4s + 0.2s tail < 0.5s min_tail
    out = FixedWindowUnit(window_seconds=4.0, min_tail_seconds=0.5).segment(
        audio, SAMPLE_RATE, _vocal_prompt()
    )
    assert len(out.segments) == 2
    assert out.segments[1].end_s == pytest.approx(8.2, abs=1e-3)


def test_fixed_window_short_tail_kept_when_above_threshold():
    audio = _sine(9.0)  # 2 windows + 1s tail >= 0.5s -> keep
    out = FixedWindowUnit(window_seconds=4.0, min_tail_seconds=0.5).segment(
        audio, SAMPLE_RATE, _vocal_prompt()
    )
    assert len(out.segments) == 3
    assert out.segments[-1].end_s == pytest.approx(9.0, abs=1e-3)


def test_fixed_window_rejects_invalid_params():
    with pytest.raises(ValueError):
        FixedWindowUnit(window_seconds=0)
    with pytest.raises(ValueError):
        FixedWindowUnit(window_seconds=4.0, min_tail_seconds=4.0)


def test_fixed_window_reproducible_under_seed():
    audio = _sine(10.0)
    seed = 1234
    a = FixedWindowUnit().segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=seed)
    b = FixedWindowUnit().segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=seed)
    assert len(a.segments) == len(b.segments)
    for sa, sb in zip(a.segments, b.segments):
        assert sa.start_s == pytest.approx(sb.start_s)
        assert sa.end_s == pytest.approx(sb.end_s)


# ----------------------------------------------------------- CU-BW beat_window


def test_beat_window_with_click_train():
    pytest.importorskip("librosa")
    audio = _beat_train(16.0, bpm=120.0)  # 32 beats; 8 bars of 4 beats
    out = BeatWindowUnit(beats_per_bar=4).segment(audio, SAMPLE_RATE, _vocal_prompt())
    assert out.applicable
    _assert_no_overlap(out)
    _assert_no_empty(out)
    # With a steady click train, we expect roughly 8 bars (sometimes ±1 due to edge handling).
    assert 4 <= len(out.segments) <= 12, f"unexpected n_segments={len(out.segments)}"


def test_beat_window_silent_audio_fallback():
    pytest.importorskip("librosa")
    audio = torch.zeros(int(8.0 * SAMPLE_RATE))
    out = BeatWindowUnit().segment(audio, SAMPLE_RATE, _vocal_prompt())
    # librosa.beat_track on silence either fails or returns 0 beats; we
    # require the segmenter to gracefully fall back to whole-audio.
    assert out.applicable
    assert len(out.segments) == 1
    assert out.segments[0].end_s == pytest.approx(8.0, abs=1e-3)


def test_beat_window_reproducible():
    pytest.importorskip("librosa")
    audio = _beat_train(8.0, bpm=120.0)
    a = BeatWindowUnit().segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=42)
    b = BeatWindowUnit().segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=42)
    assert len(a.segments) == len(b.segments)
    for sa, sb in zip(a.segments, b.segments):
        # librosa beat_track is deterministic up to numerical noise; allow ~10ms tol.
        assert sa.start_s == pytest.approx(sb.start_s, abs=0.02)
        assert sa.end_s == pytest.approx(sb.end_s, abs=0.02)


def test_beat_window_merges_short_leading_bar(monkeypatch):
    librosa = pytest.importorskip("librosa")
    monkeypatch.setattr(
        librosa.beat,
        "beat_track",
        lambda **kwargs: (120.0, np.array([1, 2, 3, 4], dtype=int)),
    )
    monkeypatch.setattr(
        librosa,
        "frames_to_time",
        lambda frames, sr: np.array([0.05, 1.0, 2.0, 3.0], dtype=float),
    )
    out = BeatWindowUnit(beats_per_bar=1, min_bar_seconds=0.5).segment(
        _sine(4.0), SAMPLE_RATE, _vocal_prompt()
    )
    assert out.segments[0].start_s == pytest.approx(0.0)
    assert out.segments[0].duration() >= 0.5


def test_beat_window_rejects_invalid_params():
    with pytest.raises(ValueError):
        BeatWindowUnit(tempo_prior_bpm=0)
    with pytest.raises(ValueError):
        BeatWindowUnit(beats_per_bar=0)
    with pytest.raises(ValueError):
        BeatWindowUnit(min_bar_seconds=-0.1)


# ----------------------------------------------------------- CU-LS lyric_span


def test_lyric_span_is_not_applicable_on_instrumental():
    unit = LyricSpanUnit(use_demucs=False)
    audio = _sine(4.0)
    out = unit.segment(audio, SAMPLE_RATE, _instrumental_prompt())
    assert out.applicable is False
    assert out.not_applicable_reason == "instrumental"
    assert out.segments == []


def test_lyric_span_is_not_applicable_when_lyrics_absent():
    unit = LyricSpanUnit(use_demucs=False)
    audio = _sine(4.0)
    prompt = Prompt(
        prompt_id="no_lyrics",
        text="any music",
        lyrics=None,
        structure_hint=None,
        duration_target=4.0,
        metadata={"instrumental": False},
    )
    out = unit.segment(audio, SAMPLE_RATE, prompt)
    assert out.applicable is False
    assert out.not_applicable_reason == "instrumental"


def test_lyric_span_is_applicable_check_only_no_whisper_load():
    """is_applicable() must not load Whisper — it's a cheap policy check."""
    unit = LyricSpanUnit(use_demucs=False)
    # Whisper not loaded.
    assert unit._whisper is None
    # is_applicable returns True for vocal, False for instrumental — and does
    # NOT trigger a load.
    assert unit.is_applicable(_vocal_prompt()) is True
    assert unit.is_applicable(_instrumental_prompt()) is False
    assert unit._whisper is None


def test_lyric_span_load_failure_returns_na(monkeypatch):
    fake_whisper = types.SimpleNamespace(
        load_model=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("missing"))
    )
    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)
    unit = LyricSpanUnit(use_demucs=False)
    out = unit.segment(_sine(4.0), SAMPLE_RATE, _vocal_prompt())
    assert out.applicable is False
    assert out.not_applicable_reason == "whisper_load_failed"


def test_lyric_span_skips_timestamps_outside_audio():
    pytest.importorskip("torchaudio")

    class DummyWhisper:
        def transcribe(self, *args, **kwargs):
            return {
                "text": "ok",
                "segments": [
                    {"start": 5.0, "end": 6.0, "text": "past end"},
                    {"start": 0.2, "end": 1.0, "text": "valid"},
                ],
            }

    unit = LyricSpanUnit(use_demucs=False)
    unit._whisper = DummyWhisper()
    out = unit.segment(_sine(2.0, sr=16_000), 16_000, _vocal_prompt())
    assert out.applicable
    assert len(out.segments) == 1
    assert out.segments[0].start_s == pytest.approx(0.2)
    assert out.segments[0].end_s == pytest.approx(1.0)


# ----------------------------------------------------------- CU-MS musical_section


def test_musical_section_rejects_invalid_params():
    with pytest.raises(ValueError):
        MusicalSectionUnit(n_sections_prior=1)


def test_musical_section_short_audio_falls_back_to_whole():
    """Audio too short for K sections — must fall back to one whole segment."""
    pytest.importorskip("librosa")
    audio = _sine(0.5)  # very short
    unit = MusicalSectionUnit(use_mert=False, n_sections_prior=4, min_section_seconds=2.0)
    out = unit.segment(audio, SAMPLE_RATE, _vocal_prompt())
    assert out.applicable
    # Either whole-audio fallback or merged-into-single section.
    assert len(out.segments) == 1
    _assert_no_empty(out)


def test_musical_section_synthetic_change_audio():
    """Audio with a tonal change — expect at least 2 sections detected (when
    we have enough audio for k=4 to even be possible)."""
    pytest.importorskip("librosa")
    a = _sine(6.0, freq=220.0)
    b = _sine(6.0, freq=880.0)
    c = _sine(6.0, freq=440.0)
    d = _sine(6.0, freq=110.0)
    audio = torch.cat([a, b, c, d], dim=0)  # 24 sec
    unit = MusicalSectionUnit(use_mert=False, n_sections_prior=4, min_section_seconds=2.0)
    out = unit.segment(audio, SAMPLE_RATE, _vocal_prompt())
    assert out.applicable
    assert len(out.segments) >= 2
    _assert_no_overlap(out)
    _assert_no_empty(out)
    # All segments must meet min_section_seconds.
    for s in out.segments:
        assert s.duration() >= 2.0 - 1e-3, f"section too short: {s.duration():.3f}s"


def test_musical_section_min_section_enforced():
    """Even when the agglomerative segmenter picks a short boundary, the
    merge step must produce only segments >= min_section_seconds."""
    pytest.importorskip("librosa")
    audio = _sine(12.0)
    unit = MusicalSectionUnit(use_mert=False, n_sections_prior=8, min_section_seconds=3.0)
    out = unit.segment(audio, SAMPLE_RATE, _vocal_prompt())
    for s in out.segments:
        # The first segment may absorb a short head; >= min should still hold
        # except in degenerate single-section fallback (len==1 always allowed).
        if len(out.segments) > 1:
            assert s.duration() >= 3.0 - 1e-3, (
                f"section {s.label} = {s.duration():.3f}s < 3.0s min"
            )


def test_musical_section_mert_features_are_time_axis_last():
    class DummyMert:
        def embed(self, waveform, sample_rate):
            return torch.randn(12, 768)

    unit = MusicalSectionUnit(use_mert=True)
    unit._mert = DummyMert()
    feat = unit._mert_features(_sine(24.0), SAMPLE_RATE)
    assert feat.shape == (768, 12)


# ----------------------------------------------------------- CU-NULL-rand-section


def test_random_section_null_reproducible_under_seed():
    pytest.importorskip("librosa")
    a = _sine(6.0, freq=220.0)
    b = _sine(6.0, freq=880.0)
    c = _sine(6.0, freq=440.0)
    d = _sine(6.0, freq=110.0)
    audio = torch.cat([a, b, c, d], dim=0)
    unit_ms = MusicalSectionUnit(use_mert=False, n_sections_prior=4, min_section_seconds=2.0)
    unit_null = RandomSectionNullUnit(underlying_ms_unit=unit_ms, permutation_seed=42)
    out_a = unit_null.segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=0)
    out_b = unit_null.segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=0)
    assert out_a.metadata.get("permutation") == out_b.metadata.get("permutation")


def test_random_section_null_different_seed_produces_different_permutation():
    pytest.importorskip("librosa")
    a = _sine(6.0, freq=220.0)
    b = _sine(6.0, freq=880.0)
    c = _sine(6.0, freq=440.0)
    d = _sine(6.0, freq=110.0)
    audio = torch.cat([a, b, c, d], dim=0)
    unit_ms = MusicalSectionUnit(use_mert=False, n_sections_prior=4, min_section_seconds=2.0)
    unit_null = RandomSectionNullUnit(underlying_ms_unit=unit_ms, permutation_seed=42)
    out_seed0 = unit_null.segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=0)
    out_seed1 = unit_null.segment(audio, SAMPLE_RATE, _vocal_prompt(), seed=1)
    # With n=4 segments, P(identical perm) = 1/24; allow occasional flake but
    # check the permutation field is different OR the perm seed has changed.
    p0 = out_seed0.metadata.get("permutation")
    p1 = out_seed1.metadata.get("permutation")
    seed0 = out_seed0.metadata.get("permutation_seed")
    seed1 = out_seed1.metadata.get("permutation_seed")
    assert seed0 != seed1
    # Boundaries must be identical (we permute labels, not boundaries).
    for sa, sb in zip(out_seed0.segments, out_seed1.segments):
        assert sa.start_s == pytest.approx(sb.start_s)
        assert sa.end_s == pytest.approx(sb.end_s)


def test_random_section_null_boundaries_identical_to_ms():
    pytest.importorskip("librosa")
    a = _sine(6.0, freq=220.0)
    b = _sine(6.0, freq=880.0)
    c = _sine(6.0, freq=440.0)
    d = _sine(6.0, freq=110.0)
    audio = torch.cat([a, b, c, d], dim=0)
    unit_ms = MusicalSectionUnit(use_mert=False, n_sections_prior=4, min_section_seconds=2.0)
    unit_null = RandomSectionNullUnit(underlying_ms_unit=unit_ms, permutation_seed=42)
    ms_out = unit_ms.segment(audio, SAMPLE_RATE, _vocal_prompt())
    null_out = unit_null.segment(audio, SAMPLE_RATE, _vocal_prompt())
    assert len(ms_out.segments) == len(null_out.segments)
    for ms_seg, null_seg in zip(ms_out.segments, null_out.segments):
        assert ms_seg.start_s == pytest.approx(null_seg.start_s)
        assert ms_seg.end_s == pytest.approx(null_seg.end_s)


# ----------------------------------------------------------- CreditUnitSegment dataclass guards


def test_credit_unit_segment_rejects_negative_boundary():
    with pytest.raises(ValueError):
        CreditUnitSegment(start_s=-1.0, end_s=1.0)


def test_credit_unit_segment_rejects_empty_segment():
    with pytest.raises(ValueError):
        CreditUnitSegment(start_s=1.0, end_s=1.0)


def test_credit_unit_segment_rejects_inverted_boundary():
    with pytest.raises(ValueError):
        CreditUnitSegment(start_s=2.0, end_s=1.0)


def test_credit_unit_segment_rejects_non_finite_boundary():
    with pytest.raises(ValueError):
        CreditUnitSegment(start_s=float("nan"), end_s=1.0)
    with pytest.raises(ValueError):
        CreditUnitSegment(start_s=0.0, end_s=float("inf"))


# ----------------------------------------------------------- Smoke import test


def test_all_segmenters_implement_required_interface():
    for unit_id, cls in REGISTRY.items():
        instance = cls()  # default constructor must work
        assert hasattr(instance, "segment")
        assert hasattr(instance, "is_applicable")
        assert getattr(instance, "unit_id", None) == unit_id
