"""Credit-unit segmenters for Phase B.3 H3 (Where to Reward).

Each segmenter takes a (waveform, sample_rate, prompt) tuple and returns a
``CreditUnitOutput`` describing spatial segments of the audio. The σ dimension
(across sampler checkpoints) is orthogonal — the H3 driver iterates over σ
and computes per-segment reward inside each spatial segment.

See ``orbit-research/PHASE_B3_H3_PLAN.md`` and
``configs/runs/phase_b3_credit_unit_comparison.yaml`` for the canonical
plan + config. D3 instrumental policy: ``lyric_span`` returns
``applicable=False`` on instrumental prompts; the comparison is 4-unit on
the instrumental subset (D3 strata reporting is the driver's responsibility).
"""
from mprm.credit_units.base import (
    CreditUnitSegment,
    CreditUnitOutput,
    CreditUnitSegmenter,
)
from mprm.credit_units.timestep import TimestepUnit
from mprm.credit_units.fixed_window import FixedWindowUnit
from mprm.credit_units.beat_window import BeatWindowUnit
from mprm.credit_units.lyric_span import LyricSpanUnit
from mprm.credit_units.musical_section import MusicalSectionUnit
from mprm.credit_units.null_random import RandomSectionNullUnit


REGISTRY: dict[str, type[CreditUnitSegmenter]] = {
    "CU-TS": TimestepUnit,
    "CU-FW": FixedWindowUnit,
    "CU-BW": BeatWindowUnit,
    "CU-LS": LyricSpanUnit,
    "CU-MS": MusicalSectionUnit,
    "CU-NULL-rand-section": RandomSectionNullUnit,
}


__all__ = [
    "CreditUnitSegment",
    "CreditUnitOutput",
    "CreditUnitSegmenter",
    "TimestepUnit",
    "FixedWindowUnit",
    "BeatWindowUnit",
    "LyricSpanUnit",
    "MusicalSectionUnit",
    "RandomSectionNullUnit",
    "REGISTRY",
]
