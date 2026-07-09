#!/usr/bin/env python3
"""Expanded CLAP prompt-fidelity analysis from existing scored outputs."""

from __future__ import annotations

import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path


# `paper_prep` is a symlink into `orbit-research/...`; anchor on the workspace cwd.
ROOT = Path.cwd()
PAPER = ROOT / "paper_prep"
CLAP = PAPER / "clap_fidelity"
N2 = PAPER / "population_retry_20260707" / "full128_prompt_clean_rates.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def pctile(vals: list[float], q: float) -> float:
    if not vals:
        return float("nan")
    vals = sorted(vals)
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def bootstrap_ci(vals: list[float], n_boot: int = 10000) -> tuple[float, float]:
    if not vals:
        return float("nan"), float("nan")
    if len(vals) == 1:
        return vals[0], vals[0]
    rng = random.Random(20260707)
    means = []
    n = len(vals)
    for _ in range(n_boot):
        means.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    return pctile(means, 0.025), pctile(means, 0.975)


def summarize(rows: list[dict[str, object]], group_name: str, group_value: str) -> dict[str, object]:
    vals = [float(r["delta_arm6_minus_arm1"]) for r in rows]
    arm1 = [float(r["arm1_mean"]) for r in rows]
    arm6 = [float(r["arm6_mean"]) for r in rows]
    ci_lo, ci_hi = bootstrap_ci(vals)
    if ci_lo >= 0:
        status = "non_negative_ci"
    elif ci_hi < 0:
        status = "negative_ci"
    else:
        status = "ambiguous_ci_crosses_zero"
    return {
        "group_name": group_name,
        "group_value": group_value,
        "n_prompts": len(rows),
        "arm1_mean": sum(arm1) / len(arm1) if arm1 else "",
        "arm6_mean": sum(arm6) / len(arm6) if arm6 else "",
        "delta_mean": sum(vals) / len(vals) if vals else "",
        "delta_median": statistics.median(vals) if vals else "",
        "bootstrap_ci_low": ci_lo,
        "bootstrap_ci_high": ci_hi,
        "status": status,
    }


def main() -> int:
    CLAP.mkdir(parents=True, exist_ok=True)
    paired = read_csv(CLAP / "CLAP_FIDELITY_PROMPT_PAIRED.csv")
    manifest = read_csv(CLAP / "CLAP_FIDELITY_MANIFEST.csv")
    n2_rows = read_csv(N2) if N2.exists() else []

    meta_by_prompt: dict[str, dict[str, str]] = {}
    for row in manifest:
        pid = row["prompt_id"]
        meta_by_prompt.setdefault(
            pid,
            {
                "prompt_vocal_stratum": row.get("prompt_vocal_stratum", ""),
                "requested_vocal": row.get("requested_vocal", ""),
            },
        )
    regimes = {r["prompt_id"]: r.get("regime", "") for r in n2_rows}

    enriched: list[dict[str, object]] = []
    for row in paired:
        pid = row["prompt_id"]
        meta = meta_by_prompt.get(pid, {})
        requested = meta.get("requested_vocal", "")
        stratum = meta.get("prompt_vocal_stratum", "")
        if stratum == "vocal" or requested == "1":
            direction = "vocal_miss"
        elif stratum == "instrumental" or requested == "0":
            direction = "instrumental_leak"
        else:
            direction = "unknown_direction"
        regime = regimes.get(pid, "no_n2_regime")
        erow: dict[str, object] = dict(row)
        erow["prompt_vocal_stratum"] = stratum
        erow["requested_vocal"] = requested
        erow["direction"] = direction
        erow["n2_regime"] = regime
        erow["rare_basin"] = "true" if regime == "rare_le_1_in_16" else "false"
        enriched.append(erow)

    groups: list[tuple[str, str, list[dict[str, object]]]] = [("overall", "all", enriched)]
    by_direction: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_regime: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_rare: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in enriched:
        by_direction[str(row["direction"])].append(row)
        by_regime[str(row["n2_regime"])].append(row)
        by_rare[str(row["rare_basin"])].append(row)
    groups += [("direction", k, v) for k, v in sorted(by_direction.items())]
    groups += [("n2_regime", k, v) for k, v in sorted(by_regime.items())]
    groups += [("rare_basin", k, v) for k, v in sorted(by_rare.items())]

    summaries = [summarize(rows, name, value) for name, value, rows in groups if rows]
    out_csv = CLAP / "CLAP_FIDELITY_EXPANDED_RESULTS.csv"
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)

    prompt_csv = CLAP / "CLAP_FIDELITY_EXPANDED_PROMPT_ROWS.csv"
    with prompt_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(enriched[0]))
        writer.writeheader()
        writer.writerows(enriched)

    overall = summaries[0]
    if overall["bootstrap_ci_low"] >= 0:
        final = "PASS"
        wording = "CLAP prompt-fidelity was non-negative in the expanded bootstrap analysis."
    elif overall["bootstrap_ci_high"] < 0:
        final = "FAIL"
        wording = "CLAP prompt-fidelity decreased under this automatic metric; semantic-preservation claims must be removed."
    else:
        final = "REDUCED"
        wording = (
            "CLAP prompt-fidelity is non-negative on average, but the bootstrap confidence interval crosses zero; "
            "claim only that no clear CLAP drop was detected."
        )

    table = "\n".join(
        "| {group_name} | {group_value} | {n_prompts} | {delta_mean:.6f} | [{bootstrap_ci_low:.6f}, {bootstrap_ci_high:.6f}] | {status} |".format(
            **r
        )
        for r in summaries
    )
    report = f"""# CLAP Fidelity Expanded Report

Generated: 2026-07-07

Inputs:

- `paper_prep/clap_fidelity/CLAP_FIDELITY_RESULTS.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_PROMPT_PAIRED.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_MANIFEST.csv`
- `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`

Outputs:

- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_RESULTS.csv`
- `paper_prep/clap_fidelity/CLAP_FIDELITY_EXPANDED_PROMPT_ROWS.csv`

## Result

CLAP_STATUS = {final}

Overall paired prompt delta, arm6 minus arm1:

- Prompts: {overall['n_prompts']}
- Mean delta: {overall['delta_mean']:.6f}
- Median delta: {overall['delta_median']:.6f}
- Bootstrap 95% CI: [{overall['bootstrap_ci_low']:.6f}, {overall['bootstrap_ci_high']:.6f}]

## Direction / Regime Breakout

| Group | Value | Prompts | Mean delta | Bootstrap 95% CI | Status |
|---|---|---:|---:|---:|---|
{table}

## Paper-Safe Wording

{wording}

Do not claim semantic preservation is proven. Do not claim quality preservation from CLAP alone.
"""
    (CLAP / "CLAP_FIDELITY_EXPANDED_REPORT.md").write_text(report)
    print(out_csv)
    print(CLAP / "CLAP_FIDELITY_EXPANDED_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
