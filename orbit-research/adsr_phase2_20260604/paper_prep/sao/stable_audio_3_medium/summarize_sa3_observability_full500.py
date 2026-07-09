#!/usr/bin/env python3
"""Summarize the 500-prompt SA3 low-step observability proxy."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path


FULL = Path("paper_prep/sao/stable_audio_3_medium/prevalence_full500")
LOW = Path("paper_prep/sao/stable_audio_3_medium/observability/lowstep_full500")
REPORT = Path("paper_prep/sao/stable_audio_3_medium/observability/SA3_OBSERVABILITY_REPORT.md")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return center - half, center + half


def main() -> int:
    full_rows = [r for r in read_jsonl(FULL / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl") if r.get("ok")]
    low_rows = [r for r in read_jsonl(LOW / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl") if r.get("ok")]
    full_by_key = {(r["prompt_id"], int(r["seed_idx"])): r for r in full_rows}
    low_by_key = {(r["prompt_id"], int(r["seed_idx"])): r for r in low_rows}
    keys = sorted(set(full_by_key).intersection(low_by_key))
    matched = [(low_by_key[k], full_by_key[k]) for k in keys]

    present_agree = sum(int(lo["present"]) == int(hi["present"]) for lo, hi in matched)
    type_agree = sum(int(lo["type_correct"]) == int(hi["type_correct"]) for lo, hi in matched)
    low_clean = sum(int(lo["type_correct"]) for lo, _ in matched)
    full_clean = sum(int(hi["type_correct"]) for _, hi in matched)
    low_present = sum(int(lo["present"]) for lo, _ in matched)
    full_present = sum(int(hi["present"]) for _, hi in matched)
    flips = Counter()
    for lo, hi in matched:
        if int(lo["present"]) == int(hi["present"]):
            flips["same_present"] += 1
        elif int(lo["present"]) == 0 and int(hi["present"]) == 1:
            flips["low_absent_full_present"] += 1
        else:
            flips["low_present_full_absent"] += 1

    n = len(matched)
    present_lo, present_hi = wilson(present_agree, n)
    type_lo, type_hi = wilson(type_agree, n)

    conclusion = "EARLY_OBSERVABILITY_WEAK"
    status = "COMPLETE"
    REPORT.write_text(
        f"""# SA3 Medium Observability Report

Generated: 2026-07-08

SA3_OBSERVABILITY_STATUS = {status}

SA3_OBSERVABILITY_CONCLUSION = {conclusion}

## Inputs

- Full 4-step scored ledger: `{FULL / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"}`
- Low-step scored ledger: `{LOW / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"}`
- Low-step generation ledger: `{LOW / "SA3_PREVALENCE_LEDGER.jsonl"}`
- Generation/scoring scripts: `paper_prep/sao/stable_audio_3_medium/run_sa3_prevalence.py`; `paper_prep/sao/stable_audio_3_medium/score_sa3_prevalence_demucs.py`

## Coverage

- Low-step proxy rows generated: {sum(1 for r in read_jsonl(LOW / "SA3_PREVALENCE_LEDGER.jsonl") if r.get("status") == "PASS")}.
- Low-step proxy rows scored: {len(low_rows)}.
- Full-step rows scored: {len(full_rows)}.
- Matched `(prompt_id, seed_idx)` rows: {n}.

## Matched Proxy Results

- Low-step type-correct rows: {low_clean} / {n} = {low_clean / n:.6f}.
- Full 4-step type-correct rows on the same keys: {full_clean} / {n} = {full_clean / n:.6f}.
- Low-step present rows: {low_present} / {n} = {low_present / n:.6f}.
- Full 4-step present rows on the same keys: {full_present} / {n} = {full_present / n:.6f}.
- Present-label agreement: {present_agree} / {n} = {present_agree / n:.6f}; Wilson CI [{present_lo:.6f}, {present_hi:.6f}].
- Type-correct agreement: {type_agree} / {n} = {type_agree / n:.6f}; Wilson CI [{type_lo:.6f}, {type_hi:.6f}].
- Low absent -> full present flips: {flips.get("low_absent_full_present", 0)}.
- Low present -> full absent flips: {flips.get("low_present_full_absent", 0)}.

## Interpretation

SA3's current local inference path did not expose true intermediate-latent
decoding during this recovery run, so this is a low-step proxy rather than a
direct early-denoising probe. The proxy has measurable agreement with the
4-step output on matched keys, but it is not enough to claim the same EVPD-style
early observability established for ACE-Step.

Paper wording should be limited to: SA3 early observability is plausible but
weak under the current API/proxy, and needs a true intermediate callback or a
dedicated early probe before it can support a full cross-backbone observability
claim.
""",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
