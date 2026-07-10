#!/usr/bin/env python3
"""Fail-closed analysis and next-stage manifests for ACE-Step 1.5 replication."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


RETRY_SEED_BASE = 2033010000
INTERVENTION_SEED_BASE = 2033020000
NBOOT = 10_000
FOLLOWUP_INPUT_FIELDS = (
    "prompt_id",
    "source_prompt_index",
    "vocal_stratum",
    "text",
    "lyrics",
    "structure_hint",
    "duration_target",
    "requested_vocal",
)


def read_jsonl_strict(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line at {path}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"non-object JSON at {path}:{line_number}")
            rows.append(row)
    return rows


def key(row: dict) -> tuple[str, str, int]:
    return str(row["prompt_id"]), str(row["condition"]), int(row["seed"])


def unique_map(rows: list[dict], label: str) -> dict[tuple[str, str, int], dict]:
    output = {}
    for row in rows:
        row_key = key(row)
        if row_key in output:
            raise ValueError(f"duplicate {label} key {row_key}")
        output[row_key] = row
    return output


def successful_generation_map(rows: list[dict]) -> dict[tuple[str, str, int], dict]:
    output = {}
    for row in rows:
        if row.get("status") != "PASS":
            continue
        row_key = key(row)
        if row_key in output:
            raise ValueError(f"duplicate successful generation key {row_key}")
        output[row_key] = row
    return output


def load_complete(manifest_path: Path, generation_dir: Path, score_dir: Path) -> list[dict]:
    manifest = unique_map(read_jsonl_strict(manifest_path), "manifest")
    generated_rows = []
    for path in sorted((generation_dir / "ledgers").glob("generation_w*.jsonl")):
        generated_rows.extend(read_jsonl_strict(path))
    scored_rows = []
    for path in sorted((score_dir / "ledgers").glob("score_w*.jsonl")):
        scored_rows.extend(read_jsonl_strict(path))
    generated = successful_generation_map(generated_rows)
    scored = unique_map(scored_rows, "score")
    if set(manifest) != set(generated) or set(manifest) != set(scored):
        raise ValueError(
            f"key mismatch manifest={len(manifest)} generation={len(generated)} score={len(scored)}"
        )
    rows = []
    for row_key in sorted(manifest):
        row = {**manifest[row_key], **scored[row_key]}
        if row.get("near_silent") is True:
            raise ValueError(f"near-silent row in completed replication: {row_key}")
        rows.append(row)
    return rows


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return math.nan, math.nan
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return center - half, center + half


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def prompt_rates(rows: list[dict]) -> list[dict]:
    by_prompt = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(row)
    output = []
    for prompt_id, values in sorted(by_prompt.items()):
        clean = sum(int(row["type_correct"]) for row in values)
        low, high = wilson(clean, len(values))
        output.append(
            {
                "prompt_id": prompt_id,
                "vocal_stratum": values[0]["vocal_stratum"],
                "rows": len(values),
                "clean": clean,
                "clean_rate": clean / len(values),
                "ci95_low": low,
                "ci95_high": high,
            }
        )
    return output


def hardest_balanced(rates: list[dict], per_stratum: int = 8) -> list[dict]:
    selected = []
    for stratum in ("vocal", "instrumental"):
        values = sorted(
            (row for row in rates if row["vocal_stratum"] == stratum),
            key=lambda row: (row["clean_rate"], row["prompt_id"]),
        )
        if len(values) < per_stratum:
            raise ValueError(f"not enough {stratum} prompts for focused map")
        selected.extend(values[:per_stratum])
    return sorted(selected, key=lambda row: (row["vocal_stratum"], row["clean_rate"], row["prompt_id"]))


def followup_manifests(rows: list[dict], rates: list[dict]) -> tuple[list[dict], list[dict]]:
    selected = hardest_balanced(rates)
    selected_ids = [row["prompt_id"] for row in selected]
    source_by_prompt = {}
    for row in rows:
        source_by_prompt.setdefault(row["prompt_id"], row)
    retry = []
    intervention = []
    for prompt_rank, prompt_id in enumerate(selected_ids):
        source = source_by_prompt[prompt_id]
        prompt_inputs = {field: source[field] for field in FOLLOWUP_INPUT_FIELDS}
        for seed_idx in range(32):
            retry.append(
                {
                    **prompt_inputs,
                    "condition": "baseline",
                    "seed_idx": seed_idx,
                    "seed": RETRY_SEED_BASE + prompt_rank * 32 + seed_idx,
                    "source": "v15_prevalence_hardest_balanced_16",
                }
            )
        for seed_idx in range(8):
            seed = INTERVENTION_SEED_BASE + prompt_rank * 8 + seed_idx
            for condition in ("baseline", "recondition"):
                intervention.append(
                    {
                        **prompt_inputs,
                        "condition": condition,
                        "seed_idx": seed_idx,
                        "seed": seed,
                        "source": "v15_prevalence_hardest_balanced_16",
                    }
                )
    return retry, intervention


def analyze_prevalence(rows: list[dict], out_dir: Path) -> None:
    if len(rows) != 1024 or len({row["prompt_id"] for row in rows}) != 128:
        raise ValueError("prevalence requires 128 prompts x 8 rows")
    rates = prompt_rates(rows)
    write_csv(out_dir / "V15_PREVALENCE_PROMPT_RATES.csv", rates)
    retry, intervention = followup_manifests(rows, rates)
    write_jsonl(out_dir / "V15_RETRY_MANIFEST.jsonl", retry)
    write_jsonl(out_dir / "V15_INTERVENTION_MANIFEST.jsonl", intervention)
    overall = sum(int(row["type_correct"]) for row in rows) / len(rows)
    strata = {
        stratum: float(np.mean([row["clean_rate"] for row in rates if row["vocal_stratum"] == stratum]))
        for stratum in ("vocal", "instrumental")
    }
    hard = hardest_balanced(rates)
    report = f"""# ACE-Step 1.5 Difficult-Set Prevalence

`V15_PREVALENCE_STATUS = COMPLETE`

- Rows: 1,024 (128 difficult/stratified prompts x 8 seeds).
- Overall per-draw type-correct rate: {overall:.6f}.
- Vocal-request prompt mean: {strata['vocal']:.6f}.
- Instrumental-request prompt mean: {strata['instrumental']:.6f}.
- Focused follow-up: 16 hardest prompts, balanced 8/8 by request direction.

These are difficult/stratified-set rates, not generic population prevalence.
The retry and matched intervention manifests were generated only after this
readout and use fresh registered seed ranges.

Hardest selected prompts: {', '.join(row['prompt_id'] for row in hard)}.
"""
    (out_dir / "V15_PREVALENCE_REPORT.md").write_text(report, encoding="utf-8")


def analyze_smoke(rows: list[dict], out_dir: Path) -> None:
    if len(rows) != 2 or {row["requested_vocal"] for row in rows} != {0, 1}:
        raise ValueError("smoke requires one vocal and one instrumental row")
    report = f"""# ACE-Step 1.5 Smoke Report

`V15_SMOKE_STATUS = PASS`

- Generated and decoded rows: 2/2.
- Request strata: one vocal, one instrumental.
- Non-silent rows: 2/2.
- Canonically scored rows: 2/2.
- Type-correct rows: {sum(int(row['type_correct']) for row in rows)}/2.

Smoke PASS is an engineering gate: model load, CUDA generation, audio decode,
and detector scoring completed. Type-correct outcomes are reported but are not
required to be 2/2 for an unconditional generative model.
"""
    (out_dir / "V15_SMOKE_REPORT.md").write_text(report, encoding="utf-8")


def analyze_retry(rows: list[dict], out_dir: Path) -> None:
    if len(rows) != 512 or len({row["prompt_id"] for row in rows}) != 16:
        raise ValueError("retry map requires 16 prompts x 32 rows")
    rates = prompt_rates(rows)
    write_csv(out_dir / "V15_RETRY_PROMPT_RATES.csv", rates)
    mean = float(np.mean([row["clean_rate"] for row in rates]))
    report = f"""# ACE-Step 1.5 Focused Retry Map

`V15_RETRY_STATUS = COMPLETE`

- Rows: 512 (16 prevalence-selected hard prompts x 32 fresh seeds).
- Prompt-mean clean rate: {mean:.6f}.
- Zero-clean prompts: {sum(row['clean'] == 0 for row in rates)}/16.

Selection used only the preceding 8-seed prevalence stage. This map estimates
retry recoverability on selected hard prompts and is not a population rate.
"""
    (out_dir / "V15_RETRY_REPORT.md").write_text(report, encoding="utf-8")


def analyze_intervention(rows: list[dict], out_dir: Path) -> None:
    if len(rows) != 256 or len({row["prompt_id"] for row in rows}) != 16:
        raise ValueError("intervention requires 16 prompts x 8 seeds x 2 conditions")
    paired = defaultdict(dict)
    metadata = {}
    for row in rows:
        pair_key = (row["prompt_id"], int(row["seed_idx"]))
        paired[pair_key][row["condition"]] = int(row["type_correct"])
        metadata[row["prompt_id"]] = row["vocal_stratum"]
    if any(set(values) != {"baseline", "recondition"} for values in paired.values()):
        raise ValueError("incomplete matched intervention pair")
    per_prompt = defaultdict(list)
    pair_rows = []
    for (prompt_id, seed_idx), values in sorted(paired.items()):
        delta = values["recondition"] - values["baseline"]
        per_prompt[prompt_id].append(delta)
        pair_rows.append(
            {
                "prompt_id": prompt_id,
                "vocal_stratum": metadata[prompt_id],
                "seed_idx": seed_idx,
                "baseline_clean": values["baseline"],
                "recondition_clean": values["recondition"],
                "delta": delta,
            }
        )
    write_csv(out_dir / "V15_INTERVENTION_PAIRS.csv", pair_rows)
    prompt_delta = {prompt_id: float(np.mean(values)) for prompt_id, values in per_prompt.items()}
    rng = np.random.default_rng(20260709)
    values = np.asarray(list(prompt_delta.values()))
    boot = np.asarray([rng.choice(values, len(values), replace=True).mean() for _ in range(NBOOT)])
    estimate = float(values.mean())
    ci = [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]
    strata = {
        stratum: float(np.mean([value for prompt_id, value in prompt_delta.items() if metadata[prompt_id] == stratum]))
        for stratum in ("vocal", "instrumental")
    }
    conclusion = "SUPPORTED" if ci[0] > 0 else "WEAK_OR_NOT_SUPPORTED"
    report = f"""# ACE-Step 1.5 Matched Reconditioning Intervention

`V15_INTERVENTION_STATUS = COMPLETE`

- Matched pairs: {len(pair_rows)} across 16 prevalence-selected hard prompts.
- Prompt-mean clean-rate delta: {estimate:+.6f}, 95% prompt-bootstrap CI
  [{ci[0]:+.6f}, {ci[1]:+.6f}].
- Vocal-request delta: {strata['vocal']:+.6f}.
- Instrumental-request delta: {strata['instrumental']:+.6f}.
- Directional conclusion: `{conclusion}`.

This is a focused difficult-prompt intervention, not a generic v1.5 effect.
"""
    (out_dir / "V15_INTERVENTION_REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("smoke", "prevalence", "retry", "intervention"),
        required=True,
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--generation-dir", type=Path, required=True)
    parser.add_argument("--score-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = load_complete(args.manifest, args.generation_dir, args.score_dir)
    {
        "smoke": analyze_smoke,
        "prevalence": analyze_prevalence,
        "retry": analyze_retry,
        "intervention": analyze_intervention,
    }[args.mode](rows, args.out_dir)
    print(json.dumps({"mode": args.mode, "rows": len(rows), "status": "COMPLETE"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
