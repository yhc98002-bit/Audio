"""CU-NULL-rand-section — random-section null control.

Preserves the MERT-detected section count and per-section duration distribution
from CU-MS, but **shuffles** which segment receives which reward delta. If the
random-section null also beats {timestep, fixed_window, beat_window, lyric_span}
by the H3 threshold, H3 is NOT about musical structure — the MERT grid is just
providing a more granular signal regardless of content.

Per FINAL_PROPOSAL §B.3 + EXPERIMENT_PLAN_EXEC Block B.3 audit Fix #11.

Operationally:
  - Run CU-MS on the audio to get the canonical section boundaries.
  - Reuse the same start/end pairs but shuffle the *labels* (so when the H3
    driver computes per-segment reward, the result is the same as CU-MS in
    terms of where the boundaries lie; the null comes from the *driver*
    permuting which segment's reward delta is treated as "the prediction" for
    each ground-truth bucket).
  - Alternatively, the driver can directly permute reward-delta vectors. This
    segmenter just emits the unshuffled MERT segments and marks them with
    metadata signaling that the null permutation is to be applied downstream.

For the smoke test we operationalize option (a): emit the MERT segments and
flag them with ``metadata["null_permutation_seed"]`` so the H3
driver knows to permute downstream.
"""
from __future__ import annotations

import random

import torch

from mprm.credit_units.base import (
    CreditUnitOutput,
    CreditUnitSegment,
    CreditUnitSegmenter,
)
from mprm.credit_units.musical_section import MusicalSectionUnit
from mprm.data.prompts import Prompt


class RandomSectionNullUnit(CreditUnitSegmenter):
    unit_id = "CU-NULL-rand-section"

    def __init__(
        self,
        underlying_ms_unit: MusicalSectionUnit | None = None,
        permutation_seed: int = 20260524,
    ):
        self.underlying = underlying_ms_unit or MusicalSectionUnit()
        self.permutation_seed = permutation_seed

    def segment(
        self,
        waveform: torch.Tensor,
        sample_rate: int,
        prompt: Prompt,
        seed: int = 0,
    ) -> CreditUnitOutput:
        ms_out = self.underlying.segment(waveform, sample_rate, prompt, seed=seed)
        if not ms_out.applicable:
            return CreditUnitOutput(
                unit_id=self.unit_id,
                applicable=False,
                not_applicable_reason=ms_out.not_applicable_reason,
                segments=[],
                metadata={"reason": "underlying_ms_unit_not_applicable"},
            )

        # Build a deterministic permutation of segment indices for downstream
        # use by the H3 driver. The driver applies the permutation when
        # comparing reward deltas; the boundaries themselves are unchanged.
        rng = random.Random(self.permutation_seed + seed)
        n = len(ms_out.segments)
        perm = list(range(n))
        rng.shuffle(perm)

        # Re-label segments to record the permutation; durations/boundaries unchanged.
        new_segs: list[CreditUnitSegment] = []
        for i, src_seg in enumerate(ms_out.segments):
            permuted_target = perm[i]
            new_meta = dict(src_seg.metadata or {})
            new_meta["null_permutation_target_index"] = permuted_target
            new_meta["null_permutation_seed"] = self.permutation_seed + seed
            new_segs.append(CreditUnitSegment(
                start_s=src_seg.start_s,
                end_s=src_seg.end_s,
                label=f"null_{i:02d}_to_{permuted_target:02d}",
                metadata=new_meta,
            ))
        return CreditUnitOutput(
            unit_id=self.unit_id,
            applicable=True,
            segments=new_segs,
            metadata={
                "underlying": "CU-MS",
                "permutation_seed": self.permutation_seed + seed,
                "permutation": perm,
                "n_segments": n,
                "null_type": "random_section_label_shuffle",
                "note": (
                    "Boundaries identical to CU-MS; the null comes from the "
                    "driver permuting which segment's reward delta is treated "
                    "as 'the prediction' for each ground-truth bucket."
                ),
            },
        )
