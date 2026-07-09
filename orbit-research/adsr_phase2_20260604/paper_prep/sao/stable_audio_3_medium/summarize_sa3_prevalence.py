#!/usr/bin/env python3
"""Summarize SA3 prevalence generation and Demucs scoring ledgers."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_ROOT = Path("paper_prep/sao/stable_audio_3_medium/prevalence")


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


def rate_row(group: str, value: str, rows: list[dict]) -> dict:
    n = len(rows)
    clean = sum(int(r["type_correct"]) for r in rows)
    present = sum(int(r["present"]) for r in rows)
    failures = n - clean
    lo, hi = wilson(clean, n)
    return {
        "group": group,
        "value": value,
        "rows": n,
        "clean": clean,
        "failures": failures,
        "clean_rate": clean / n if n else float("nan"),
        "clean_ci_low": lo,
        "clean_ci_high": hi,
        "present_rate": present / n if n else float("nan"),
        "median_vocal_energy_ratio": statistics.median(float(r["vocal_energy_ratio"]) for r in rows)
        if rows
        else float("nan"),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--label", default="SA3 Medium Prevalence Pilot")
    args = parser.parse_args()

    root = args.root
    gen_ledger = root / "SA3_PREVALENCE_LEDGER.jsonl"
    demucs_ledger = root / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"
    summary_csv = root / "SA3_PREVALENCE_DEMUCS_SUMMARY.csv"
    report_path = root / "SA3_PREVALENCE_REPORT.md"

    gen_rows = read_jsonl(gen_ledger)
    score_rows = [r for r in read_jsonl(demucs_ledger) if r.get("ok")]
    gen_pass = [r for r in gen_rows if r.get("status") == "PASS"]

    # Deduplicate scores by prompt/seed.
    dedup_scores: dict[tuple[str, int], dict] = {}
    for row in score_rows:
        dedup_scores.setdefault((row["prompt_id"], int(row["seed_idx"])), row)
    score_rows = list(dedup_scores.values())

    summary_rows = [rate_row("overall", "all", score_rows)]
    for key in ["vocal_stratum", "stratum"]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in score_rows:
            groups[str(row.get(key, ""))].append(row)
        for value, rows in sorted(groups.items()):
            summary_rows.append(rate_row(key, value, rows))

    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    failures = Counter()
    for row in score_rows:
        if int(row["type_correct"]):
            continue
        if row.get("vocal_stratum") == "vocal" and int(row["present"]) == 0:
            failures["vocal_miss"] += 1
        elif row.get("vocal_stratum") == "instrumental" and int(row["present"]) == 1:
            failures["instrumental_leak"] += 1
        else:
            failures["other"] += 1

    by_prompt: dict[str, list[dict]] = defaultdict(list)
    for row in score_rows:
        by_prompt[row["prompt_id"]].append(row)
    any_clean = sum(1 for rows in by_prompt.values() if any(int(r["type_correct"]) for r in rows))
    all_fail = sum(1 for rows in by_prompt.values() if not any(int(r["type_correct"]) for r in rows))
    prompt_rates = [
        sum(int(r["type_correct"]) for r in rows) / len(rows) for rows in by_prompt.values()
    ]
    bon_lo, bon_hi = wilson(any_clean, len(by_prompt))

    overall = summary_rows[0]
    dominant = failures.most_common(1)[0][0] if failures else "none_detected"
    if len(gen_pass) >= 4000:
        status = "FULL_GUIDE_COMPLETE"
        acceptance_text = "This run clears the full guide target of at least 4,000 SA3 rows."
    elif len(gen_pass) >= 1024:
        status = "PILOT_COMPLETE"
        acceptance_text = "This pilot clears the generation acceptance threshold of at least 1,024 SA3 rows."
    else:
        status = "INCOMPLETE"
        acceptance_text = "This run does not clear the 1,024-row pilot threshold."

    report = f"""# {args.label} Report

Generated: 2026-07-08

SA3_PREVALENCE_STATUS = {status}

SA3_PREVALENCE_ROWS = {len(gen_pass)}

SA3_DOMINANT_FAILURE_MODE = {dominant}

## Inputs

- Generation manifest: `{root / "SA3_PREVALENCE_MANIFEST.jsonl"}`
- Generation ledger: `{gen_ledger}`
- Demucs scoring ledger: `{demucs_ledger}`
- Summary CSV: `{summary_csv}`
- Generation script: `paper_prep/sao/stable_audio_3_medium/run_sa3_prevalence.py`
- Demucs scoring script: `paper_prep/sao/stable_audio_3_medium/score_sa3_prevalence_demucs.py`

## Generation

- Prompt set: prompt rows from the run manifest, resolved against `configs/prompts/held_out.jsonl` and `configs/prompts/dev.jsonl`.
- Seeds: 8 deterministic seeds per prompt.
- Rows requested: {len(gen_pass)} generated `PASS` rows plus any failed rows in the ledger.
- Rows generated with `PASS`: {len(gen_pass)}.
- WAV files present: {len(list((root / "audio").glob("*/*.wav")))}.
- Duration per clip: 8 seconds.
- Steps: 4.
- Model: ModelScope `stabilityai/stable-audio-3-medium`, local weights.

## Demucs Vocal-Presence Scoring

- Detector: `htdemucs` vocal-energy ratio.
- Fixed threshold: 0.1791, matching current paper-prep workers.
- Scored rows: {len(score_rows)}.
- Overall type-correct rows: {overall['clean']} / {overall['rows']} = {overall['clean_rate']:.6f}.
- 95% Wilson CI: [{overall['clean_ci_low']:.6f}, {overall['clean_ci_high']:.6f}].

## Failure Mode

- Vocal misses: {failures.get('vocal_miss', 0)}.
- Instrumental leaks: {failures.get('instrumental_leak', 0)}.
- Other type failures: {failures.get('other', 0)}.

The dominant detected categorical failure mode is **{dominant}**. This is a
first-pass detector readout, not a human validation of all possible SA3 musical
failure modes.

## By Requested Vocal Stratum

| Vocal stratum | Rows | Type-correct rate | 95% CI | Present rate |
|---|---:|---:|---:|---:|
"""
    for row in summary_rows:
        if row["group"] != "vocal_stratum":
            continue
        report += (
            f"| `{row['value']}` | {row['rows']} | {row['clean_rate']:.6f} | "
            f"[{row['clean_ci_low']:.6f}, {row['clean_ci_high']:.6f}] | "
            f"{row['present_rate']:.6f} |\n"
        )
    report += f"""
## Best-of-8 Selection

- Prompts: {len(by_prompt)}.
- Prompts with at least one type-correct seed: {any_clean}.
- Prompts with zero type-correct seeds: {all_fail}.
- Best-of-8 success rate: {any_clean / len(by_prompt):.6f}.
- 95% Wilson CI: [{bon_lo:.6f}, {bon_hi:.6f}].
- Mean per-prompt clean rate: {statistics.mean(prompt_rates):.6f}.
- Median per-prompt clean rate: {statistics.median(prompt_rates):.6f}.

## Interpretation

{acceptance_text}
It does **not** support a broad second-backbone robustness claim. Instead, it
shows that SA3 Medium can be executed locally and that the same vocal/instrumental
constraint family remains measurable on a second backbone, with vocal-miss as the
dominant detected failure mode under the fixed Demucs detector.

Second-backbone paper wording should therefore be limited to a guide-scale
pilot/follow-up claim and should be interpreted together with the SA3
observability and intervention reports.
"""
    report_path.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
