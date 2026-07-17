#!/usr/bin/env python3
"""Complete Dispatch A items 2, 5, and 7 from frozen existing evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_exit1_v2"
V1 = ROOT / "analysis_exit1"
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"

UNCONDITIONAL_SCORES = V1 / "UNCONDITIONAL_SCORES.csv"
UNCONDITIONAL_MANIFEST = V1 / "UNCONDITIONAL_GENERATION_MANIFEST.csv"
UNCONDITIONAL_CHECKSUMS = V1 / "UNCONDITIONAL_AUDIO_SHA256SUMS"
UNCONDITIONAL_V2_CSV = OUT / "UNCONDITIONAL_BASE_RATE_V2.csv"
UNCONDITIONAL_V2_REPORT = OUT / "UNCONDITIONAL_BASE_RATE_V2.md"
UNCONDITIONAL_V2_AUDIT = OUT / "UNCONDITIONAL_BASE_RATE_V2_AUDIT.json"

FACTORIAL_SCORES = PAPER / "autochain_20260712/factorial/FACTORIAL_CORRECTED_SCORE_ROWS.csv"
FACTORIAL_SECONDARY = PAPER / "autochain_20260712/factorial/secondary_ledgers"
LIVE_LEDGERS = PAPER / "w2_execution_20260712/live_confirmation_20260713/live_ledgers"
RECIPE_V2_CSV = OUT / "RECIPE_CURVES_V2.csv"
RECIPE_V2_REPORT = OUT / "RECIPE_CURVES_V2.md"
RECIPE_V2_AUDIT = OUT / "RECIPE_CURVES_V2_AUDIT.json"

FINAL_REPORT = OUT / "EXIT1_V2_FINAL_REPORT.md"
TEST_RESULTS = OUT / "DISPATCH_A_TEST_RESULTS.txt"
COMPLETION_SCRIPT = OUT / "dispatch_a_completion.py"
EVALUATOR_SCRIPT = OUT / "exit1_evaluator_v2.py"
EVALUATOR_TEST = ROOT / "tests/test_exit1_evaluator_v2.py"
COMPLETION_TEST = ROOT / "tests/test_exit1_dispatch_a_completion.py"

T6_PROMOTION_REPORT = PAPER / "autochain_20260712/T6_PROMOTION_REPORT.md"
T6_PROMOTION_RESULT = PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json"
EVALUATOR_REPORT = OUT / "EVALUATOR_COMPARISON_TABLE.md"
EVALUATOR_AUDIT = OUT / "EVALUATOR_COMPARISON_AUDIT.json"
EVALUATOR_AUDIOSET_SCORES = OUT / "EVALUATOR_AUDIOSET_HUMAN_VOICE_SCORES.csv"
EVALUATOR_AUDIOSET_AUDIT = OUT / "EVALUATOR_AUDIOSET_HUMAN_VOICE_AUDIT.json"
NEUTRAL_REPORT = OUT / "neutral_control/NEUTRAL_CONTROL_REPORT.md"
NEUTRAL_RESULTS = OUT / "neutral_control/FOUR_CELL_RESULTS.csv"

HISTORICAL_AND_DEMUCS_THRESHOLD = 0.038639528676867485
HISTORICAL_AND_PANNS_THRESHOLD = 0.03181814216077328
BOOTSTRAP_REPLICATES = 10_000
RECIPE_BOOTSTRAP_SEED = 2026071603

_SPEC = importlib.util.spec_from_file_location(
    "dispatch_a_exit1_evaluator_v2", OUT / "exit1_evaluator_v2.py"
)
assert _SPEC is not None and _SPEC.loader is not None
EVALUATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(EVALUATOR)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite differing output: {path}")
        return
    path.write_text(content, encoding="utf-8")


def csv_text(rows: Sequence[dict]) -> str:
    if not rows:
        raise ValueError("refusing to serialize an empty CSV")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_csv_once(path: Path, rows: Sequence[dict]) -> None:
    _write_once(path, csv_text(rows))


def write_json_once(path: Path, value: object) -> None:
    _write_once(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid Wilson interval counts")
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
    radius /= denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def _rate_row(
    instrument_role: str,
    decision_rule: str,
    group: str,
    value: str,
    values: Sequence[int],
) -> dict:
    present = sum(values)
    low, high = wilson_interval(present, len(values))
    return {
        "instrument_role": instrument_role,
        "decision_rule": decision_rule,
        "group": group,
        "value": value,
        "n": len(values),
        "voice_present": present,
        "voice_absent": len(values) - present,
        "rate": present / len(values),
        "wilson_ci95_low": low,
        "wilson_ci95_high": high,
    }


def build_unconditional_v2() -> dict:
    canonical = EVALUATOR.parse_canonical_instrument(
        T6_PROMOTION_REPORT, T6_PROMOTION_RESULT
    )
    if canonical["family"] != "or":
        raise ValueError("unconditional v2 primary is frozen to promoted OR")
    scores = read_csv(UNCONDITIONAL_SCORES)
    if len(scores) != 256 or len({row["clip_id"] for row in scores}) != 256:
        raise ValueError("unconditional source must contain 256 unique clip IDs")
    manifest = read_csv(UNCONDITIONAL_MANIFEST)
    if len(manifest) != 256 or len({row["clip_id"] for row in manifest}) != 256:
        raise ValueError("unconditional manifest must contain 256 unique clip IDs")
    if {row["clip_id"] for row in scores} != {row["clip_id"] for row in manifest}:
        raise ValueError("unconditional score and manifest clip-ID sets differ")
    checksum_map = {}
    for line in UNCONDITIONAL_CHECKSUMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative_path = line.split(maxsplit=1)
        if relative_path in checksum_map:
            raise ValueError(f"duplicate unconditional checksum path: {relative_path}")
        checksum_map[relative_path] = digest
    if len(checksum_map) != 256:
        raise ValueError("unconditional checksum index must contain 256 paths")
    for row in scores:
        if checksum_map.get(row["output_path"]) != row["audio_sha256"]:
            raise ValueError(f"unconditional checksum mismatch: {row['clip_id']}")
    near_silent_rows = [
        row for row in scores if str(row["near_silent"]).lower() not in {"false", "0"}
    ]
    primary = {
        row["clip_id"]: int(
            (
                float(row["demucs_score"]) >= canonical["demucs_threshold"]
                and str(row["near_silent"]).lower() in {"false", "0"}
            )
            or float(row["panns_score"]) >= canonical["panns_threshold"]
        )
        for row in scores
    }
    sensitivity = {
        row["clip_id"]: int(
            float(row["demucs_score"]) >= HISTORICAL_AND_DEMUCS_THRESHOLD
            and str(row["near_silent"]).lower() in {"false", "0"}
            and float(row["panns_score"]) >= HISTORICAL_AND_PANNS_THRESHOLD
        )
        for row in scores
    }
    summary_rows = []
    for role, rule, decisions in (
        ("PRIMARY", "promoted_or", primary),
        ("SENSITIVITY_ONLY", "historical_and", sensitivity),
    ):
        groups = [("overall", "all", scores)] + [
            ("stratum", stratum, [row for row in scores if row["stratum"] == stratum])
            for stratum in ("empty", "neutral_text")
        ]
        for group, value, rows in groups:
            summary_rows.append(
                _rate_row(
                    role,
                    rule,
                    group,
                    value,
                    [decisions[row["clip_id"]] for row in rows],
                )
            )
    write_csv_once(UNCONDITIONAL_V2_CSV, summary_rows)
    primary_rows = [row for row in summary_rows if row["instrument_role"] == "PRIMARY"]
    sensitivity_rows = [
        row for row in summary_rows if row["instrument_role"] == "SENSITIVITY_ONLY"
    ]
    overall = primary_rows[0]
    lines = [
        "# Exit-1 Unconditional Base Rate v2",
        "",
        "**Evidence role: PRIOR EVIDENCE, NOT CAUSAL PROOF.**",
        "",
        "This analysis re-scores the retained preregistered empty/neutral outputs. It "
        "estimates vocal presence under those prompt cells; it does not establish a causal "
        "vocal-generation bias.",
        "",
        "## Primary - promoted OR",
        "",
        f"Overall: **{overall['voice_present']}/{overall['n']} voice-present** and "
        f"**{overall['voice_absent']}/{overall['n']} voice-absent**; rate "
        f"{overall['rate']:.4f}, Wilson 95% CI "
        f"[{overall['wilson_ci95_low']:.4f}, {overall['wilson_ci95_high']:.4f}].",
        "",
        "| Natural stratum | n | Voice-present | Voice-absent | Rate | Wilson 95% CI |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in primary_rows[1:]:
        lines.append(
            f"| `{row['value']}` | {row['n']} | {row['voice_present']} | "
            f"{row['voice_absent']} | {row['rate']:.4f} | "
            f"[{row['wilson_ci95_low']:.4f}, {row['wilson_ci95_high']:.4f}] |"
        )
    lines.extend(
        [
            "",
            "Canonical parse:",
            "",
            f"> {canonical['report_exact_line']}",
            "",
            f"- Demucs threshold: `{canonical['demucs_threshold']}`.",
            f"- PANNs threshold: `{canonical['panns_threshold']}`.",
            f"- T6 result SHA-256: `{canonical['result_sha256']}`.",
            "",
            "## Sensitivity only - historical AND",
            "",
            "These rows reproduce the earlier operationalization and are not the primary v2 "
            "estimate.",
            "",
            "| Natural stratum | n | Voice-present | Voice-absent | Rate | Wilson 95% CI |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sensitivity_rows:
        label = "overall" if row["group"] == "overall" else row["value"]
        lines.append(
            f"| `{label}` | {row['n']} | {row['voice_present']} | "
            f"{row['voice_absent']} | {row['rate']:.4f} | "
            f"[{row['wilson_ci95_low']:.4f}, {row['wilson_ci95_high']:.4f}] |"
        )
    lines.extend(
        [
            "",
            "Historical rule: Demucs >= "
            f"`{HISTORICAL_AND_DEMUCS_THRESHOLD}` AND PANNs >= "
            f"`{HISTORICAL_AND_PANNS_THRESHOLD}`.",
            "",
            "## Frozen source",
            "",
            "No music was generated for this v2 analysis. It uses the 256 retained clips and "
            "their frozen Demucs/PANNs scores from `analysis_exit1/`.",
            "The frozen 256-row universe includes one source row flagged near-silent "
            "(`exit1_uncond_111`). It remains in the denominator to preserve the "
            "preregistered source universe; this is an explicit validity limitation, not "
            "an unreported exclusion.",
        ]
    )
    _write_once(UNCONDITIONAL_V2_REPORT, "\n".join(lines) + "\n")
    audit = {
        "status": "COMPLETE",
        "evidence_role": "PRIOR EVIDENCE, NOT CAUSAL PROOF",
        "rows": len(scores),
        "unique_clip_ids": len({row["clip_id"] for row in scores}),
        "manifest_rows": len(manifest),
        "checksum_index_rows": len(checksum_map),
        "manifest_score_id_set_match": True,
        "score_checksum_index_match": True,
        "near_silent_rows": len(near_silent_rows),
        "near_silent_clip_ids": [row["clip_id"] for row in near_silent_rows],
        "near_silent_handling": "included_to_preserve_frozen_256_row_universe",
        "near_silent_scoring": (
            "Demucs component forced absent per frozen instrument; PANNs component "
            "remains eligible under the primary OR rule"
        ),
        "primary_instrument": canonical,
        "historical_sensitivity_instrument": {
            "family": "and",
            "demucs_threshold": HISTORICAL_AND_DEMUCS_THRESHOLD,
            "panns_threshold": HISTORICAL_AND_PANNS_THRESHOLD,
        },
        "summary_rows": summary_rows,
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in (
                UNCONDITIONAL_SCORES,
                UNCONDITIONAL_MANIFEST,
                UNCONDITIONAL_CHECKSUMS,
                T6_PROMOTION_REPORT,
                T6_PROMOTION_RESULT,
            )
        },
        "output_sha256": {
            str(UNCONDITIONAL_V2_CSV.relative_to(ROOT)): sha256_file(
                UNCONDITIONAL_V2_CSV
            ),
            str(UNCONDITIONAL_V2_REPORT.relative_to(ROOT)): sha256_file(
                UNCONDITIONAL_V2_REPORT
            ),
        },
        "generator_source_sha256": sha256_file(COMPLETION_SCRIPT),
        "new_music_generation": 0,
    }
    write_json_once(UNCONDITIONAL_V2_AUDIT, audit)
    return audit


def _cluster_rate_ci(rows: list[dict], field: str, seed: int) -> tuple[float, float, float]:
    import numpy as np

    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(float(row[field]))
    prompts = sorted(by_prompt)
    point = float(np.mean([value for values in by_prompt.values() for value in values]))
    rng = np.random.default_rng(seed)
    draws = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for index in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(prompts, size=len(prompts), replace=True)
        values = [value for prompt in sampled for value in by_prompt[str(prompt)]]
        draws[index] = float(np.mean(values))
    return point, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def _paired_delta_ci(
    treatment: list[dict], baseline: list[dict], field: str, seed: int
) -> tuple[float, float, float]:
    import numpy as np

    left = {row["prompt_id"]: float(row[field]) for row in treatment}
    right = {row["prompt_id"]: float(row[field]) for row in baseline}
    if set(left) != set(right):
        raise ValueError("paired recipe comparison prompt sets differ")
    prompts = sorted(left)
    differences = {prompt: left[prompt] - right[prompt] for prompt in prompts}
    point = float(np.mean(list(differences.values())))
    rng = np.random.default_rng(seed)
    draws = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for index in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(prompts, size=len(prompts), replace=True)
        draws[index] = float(np.mean([differences[str(prompt)] for prompt in sampled]))
    return point, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def _load_factorial_evidence() -> tuple[list[dict], dict[str, dict], list[dict], list[Path]]:
    factorial = read_csv(FACTORIAL_SCORES)
    secondary: dict[str, dict] = {}
    source_paths = [FACTORIAL_SCORES]
    for path in sorted(FACTORIAL_SECONDARY.glob("secondary_w*.jsonl")):
        source_paths.append(path)
        for row in read_jsonl(path):
            if row.get("status") != "PASS":
                continue
            prior = secondary.get(row["task_id"])
            if prior is not None and prior != row:
                raise ValueError(f"conflicting factorial secondary row {row['task_id']}")
            secondary[row["task_id"]] = row
    live_raw = []
    for path in sorted(LIVE_LEDGERS.glob("live_w*.jsonl")):
        source_paths.append(path)
        live_raw.extend(read_jsonl(path))
    if len(factorial) != 3072 or len(secondary) != 3072:
        raise ValueError(
            f"factorial/secondary cardinality changed: {len(factorial)}/{len(secondary)}"
        )
    if len({row["task_id"] for row in factorial}) != 3072:
        raise ValueError("factorial source contains duplicate task IDs")
    return factorial, secondary, live_raw, source_paths


def _quality_basis(secondary: dict[str, dict], live_raw: list[dict]) -> dict:
    import numpy as np

    genuine_fields = ("common_robust_lcb", "final_common_robust_lcb")
    complete_field = next(
        (
            field
            for field in genuine_fields
            if all(row.get(field) is not None for row in secondary.values())
        ),
        None,
    )
    if complete_field is not None:
        values = [float(row[complete_field]) for row in secondary.values()]
        return {
            "status": "GENUINE_QUALIFIED_SUCCESS",
            "field": complete_field,
            "scores": {task_id: float(row[complete_field]) for task_id, row in secondary.items()},
            "floor": float(np.quantile(values, 0.25)),
            "primary": False,
        }
    deduplicated = {}
    for row in live_raw:
        key = (row["unit_id"], row["record_type"], str(row.get("slot", "")))
        if key in deduplicated and deduplicated[key] != row:
            raise ValueError(f"conflicting live-confirmation duplicate {key}")
        deduplicated[key] = row
    live_slots = [
        row
        for row in deduplicated.values()
        if row["record_type"] == "slot"
        and row.get("status") == "COMPLETE"
        and row.get("final_common_robust_lcb") is not None
    ]
    x = np.asarray(
        [
            [
                1.0,
                float(row["final_scores"]["semantic_fit"]),
                float(row["final_scores"]["aesthetic_pq"]),
            ]
            for row in live_slots
        ],
        dtype=np.float64,
    )
    y = np.asarray([float(row["final_common_robust_lcb"]) for row in live_slots])
    coefficients, *_ = np.linalg.lstsq(x, y, rcond=None)
    predicted = x @ coefficients
    r_squared = 1.0 - float(np.sum((y - predicted) ** 2) / np.sum((y - y.mean()) ** 2))
    floor_source = [
        float(row["final_common_robust_lcb"])
        for row in live_slots
        if row["policy"] == "no_probe_reseed" and int(row["label_b_satisfied"]) == 1
    ]
    if not floor_source:
        raise ValueError("live baseline has no satisfied quality-floor rows")
    scores = {
        task_id: float(
            coefficients[0]
            + coefficients[1] * float(row["clap_prompt_similarity"])
            + coefficients[2] * float(row["aesthetic_pq"])
        )
        for task_id, row in secondary.items()
    }
    return {
        "status": "PROXY_QUALIFIED_SUCCESS",
        "field": "linear_proxy_from_clap_and_audiobox_pq",
        "scores": scores,
        "floor": float(np.quantile(floor_source, 0.25)),
        "coefficients": {
            "intercept": float(coefficients[0]),
            "clap": float(coefficients[1]),
            "audiobox_pq": float(coefficients[2]),
        },
        "r_squared": r_squared,
        "primary": False,
        "reason": "factorial rows lack complete common robust-LCB scores",
    }


def select_gate_then_quality(candidates: Sequence[dict]) -> dict:
    if not candidates:
        raise ValueError("selection requires at least one candidate")
    return max(
        candidates,
        key=lambda row: (
            1 - int(row["corrected_violation"]),
            float(row["quality_score"]),
            -int(row["seed_idx"]),
        ),
    )


def _frontier(rows: list[dict]) -> list[dict]:
    frontier = []
    for row in rows:
        dominated = any(
            other is not row
            and int(other["attempts_N"]) <= int(row["attempts_N"])
            and float(other["violation_rate"]) <= float(row["violation_rate"])
            and (
                int(other["attempts_N"]) < int(row["attempts_N"])
                or float(other["violation_rate"]) < float(row["violation_rate"])
            )
            for other in rows
        )
        if not dominated:
            frontier.append(row)
    return sorted(frontier, key=lambda row: (int(row["attempts_N"]), row["recipe"]))


def build_recipe_curves_v2() -> dict:
    factorial, secondary, live_raw, source_paths = _load_factorial_evidence()
    quality = _quality_basis(secondary, live_raw)
    prepared = []
    for row in factorial:
        prepared.append(
            {
                **row,
                "seed_idx": int(row["seed_idx"]),
                "corrected_violation": int(row["corrected_violation"]),
                "quality_score": quality["scores"][row["task_id"]],
            }
        )
    by_condition_prompt: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in prepared:
        by_condition_prompt[(row["condition"], row["prompt_id"])].append(row)
    for values in by_condition_prompt.values():
        values.sort(key=lambda row: row["seed_idx"])
    recipes = {
        "plain": "plain_baseline",
        "positive_text": "positive_text",
        "positive_sampler": "positive_sampler",
    }
    outcomes: dict[tuple[str, int], list[dict]] = {}
    output_rows = []
    for n in (1, 2, 4, 8):
        for recipe, condition in recipes.items():
            prompts = sorted(
                prompt for cond, prompt in by_condition_prompt if cond == condition
            )
            if len(prompts) != 32:
                raise ValueError(f"{condition} has {len(prompts)} prompts, expected 32")
            selected_rows = []
            for prompt in prompts:
                candidates = by_condition_prompt[(condition, prompt)][:n]
                if len(candidates) != n:
                    raise ValueError(f"{condition}/{prompt} lacks N={n} attempts")
                selected = select_gate_then_quality(candidates)
                selected_rows.append(
                    {
                        "prompt_id": prompt,
                        "violation": int(selected["corrected_violation"]),
                        "qualified_success": int(
                            not int(selected["corrected_violation"])
                            and float(selected["quality_score"]) >= float(quality["floor"])
                        ),
                    }
                )
            outcomes[(recipe, n)] = selected_rows
            violation = _cluster_rate_ci(
                selected_rows, "violation", RECIPE_BOOTSTRAP_SEED + n
            )
            qualified = _cluster_rate_ci(
                selected_rows, "qualified_success", RECIPE_BOOTSTRAP_SEED + 100 + n
            )
            violations = sum(row["violation"] for row in selected_rows)
            qualified_count = sum(row["qualified_success"] for row in selected_rows)
            output_rows.append(
                {
                    "recipe": recipe,
                    "condition": condition,
                    "attempts_N": n,
                    "prompt_clusters": len(selected_rows),
                    "candidate_rows_considered": len(selected_rows) * n,
                    "selected_rows": len(selected_rows),
                    "corrected_label_b_violations": violations,
                    "corrected_label_b_satisfied": len(selected_rows) - violations,
                    "violation_rate": violation[0],
                    "violation_ci95_low": violation[1],
                    "violation_ci95_high": violation[2],
                    "violation_delta_vs_equal_compute_plain": 0.0 if recipe == "plain" else "",
                    "violation_delta_ci95_low": 0.0 if recipe == "plain" else "",
                    "violation_delta_ci95_high": 0.0 if recipe == "plain" else "",
                    "quality_status": quality["status"],
                    "quality_primary": 0,
                    "qualified_success_count": qualified_count,
                    "qualified_success_rate": qualified[0],
                    "qualified_success_ci95_low": qualified[1],
                    "qualified_success_ci95_high": qualified[2],
                    "qualified_success_delta_vs_equal_compute_plain": (
                        0.0 if recipe == "plain" else ""
                    ),
                    "qualified_success_delta_ci95_low": 0.0 if recipe == "plain" else "",
                    "qualified_success_delta_ci95_high": 0.0 if recipe == "plain" else "",
                }
            )
        baseline = outcomes[("plain", n)]
        for recipe in ("positive_text", "positive_sampler"):
            violation_delta = _paired_delta_ci(
                outcomes[(recipe, n)],
                baseline,
                "violation",
                RECIPE_BOOTSTRAP_SEED + 200 + n,
            )
            qualified_delta = _paired_delta_ci(
                outcomes[(recipe, n)],
                baseline,
                "qualified_success",
                RECIPE_BOOTSTRAP_SEED + 300 + n,
            )
            row = next(
                item
                for item in output_rows
                if item["recipe"] == recipe and item["attempts_N"] == n
            )
            row.update(
                {
                    "violation_delta_vs_equal_compute_plain": violation_delta[0],
                    "violation_delta_ci95_low": violation_delta[1],
                    "violation_delta_ci95_high": violation_delta[2],
                    "qualified_success_delta_vs_equal_compute_plain": qualified_delta[0],
                    "qualified_success_delta_ci95_low": qualified_delta[1],
                    "qualified_success_delta_ci95_high": qualified_delta[2],
                }
            )
    write_csv_once(RECIPE_V2_CSV, output_rows)
    frontier = _frontier(output_rows)
    min_violation = min(float(row["violation_rate"]) for row in output_rows)
    min_n_at_best = min(
        int(row["attempts_N"])
        for row in output_rows
        if float(row["violation_rate"]) == min_violation
    )
    best_observed = [
        row
        for row in output_rows
        if float(row["violation_rate"]) == min_violation
        and int(row["attempts_N"]) == min_n_at_best
    ]
    lines = [
        "# Exit-1 Recipe Curves v2",
        "",
        "## Primary endpoint",
        "",
        "The primary endpoint is corrected Label-B violation after gate-first selection. "
        "Each condition contains 32 prompt clusters and 16 common-random-number attempts. "
        "At each N, selection first prefers a corrected Label-B-satisfied candidate and "
        "then uses the available quality score only as a tie-breaker.",
        "",
        "| Recipe | N | Violations / 32 | Violation rate (95% prompt-cluster CI) | Paired delta vs equal-compute plain (95% CI) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in output_rows:
        delta = float(row["violation_delta_vs_equal_compute_plain"])
        lines.append(
            f"| `{row['recipe']}` | {row['attempts_N']} | "
            f"{row['corrected_label_b_violations']} / 32 | "
            f"{float(row['violation_rate']):.3f} "
            f"[{float(row['violation_ci95_low']):.3f}, "
            f"{float(row['violation_ci95_high']):.3f}] | "
            f"{delta:+.3f} [{float(row['violation_delta_ci95_low']):+.3f}, "
            f"{float(row['violation_delta_ci95_high']):+.3f}] |"
        )
    lines.extend(
        [
            "",
            "## Quality qualification - non-primary",
            "",
            f"`QUALITY_STATUS = {quality['status']}`",
            "",
        ]
    )
    if quality["status"] == "PROXY_QUALIFIED_SUCCESS":
        lines.extend(
            [
                "The 3,072 factorial rows do not contain complete common robust-LCB quality "
                "scores. Qualified-success values therefore use the frozen CLAP + Audiobox "
                "mapping as `PROXY_QUALIFIED_SUCCESS`. They are excluded from the primary "
                "endpoint and must not be presented as genuine qualified success.",
                "",
            ]
        )
    lines.extend(
        [
            "| Recipe | N | Qualified successes / 32 | Diagnostic rate (95% CI) | Diagnostic paired delta vs plain (95% CI) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in output_rows:
        delta = float(row["qualified_success_delta_vs_equal_compute_plain"])
        lines.append(
            f"| `{row['recipe']}` | {row['attempts_N']} | "
            f"{row['qualified_success_count']} / 32 | "
            f"{float(row['qualified_success_rate']):.3f} "
            f"[{float(row['qualified_success_ci95_low']):.3f}, "
            f"{float(row['qualified_success_ci95_high']):.3f}] | "
            f"{delta:+.3f} [{float(row['qualified_success_delta_ci95_low']):+.3f}, "
            f"{float(row['qualified_success_delta_ci95_high']):+.3f}] |"
        )
    lines.extend(
        [
            "",
            "## Observed frontier",
            "",
            "This is a descriptive compute/violation frontier, not a deployable-point claim.",
            "",
        ]
    )
    for row in frontier:
        lines.append(
            f"- `{row['recipe']}`, N={row['attempts_N']}: violation "
            f"{float(row['violation_rate']):.3f}."
        )
    best_text = ", ".join(
        f"`{row['recipe']}` at N={row['attempts_N']}" for row in best_observed
    )
    lines.extend(
        [
            "",
            f"Best observed (exploratory only): {best_text}, each with violation rate "
            f"{min_violation:.3f}. No deployment recommendation is made.",
            "",
            "Intervals use 10,000 prompt-cluster bootstrap replicates. Treatment deltas "
            "are paired by prompt against `plain` at identical N and therefore equal "
            "generation compute.",
            "",
            "No music was generated for this v2 analysis.",
        ]
    )
    _write_once(RECIPE_V2_REPORT, "\n".join(lines) + "\n")
    quality_audit = {key: value for key, value in quality.items() if key != "scores"}
    audit = {
        "status": "COMPLETE",
        "primary_endpoint": "corrected_label_b_violation",
        "factorial_rows": len(factorial),
        "factorial_secondary_rows": len(secondary),
        "prompt_clusters": 32,
        "attempts_per_condition_prompt": 16,
        "conditions": list(recipes.values()),
        "attempts_N": [1, 2, 4, 8],
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": RECIPE_BOOTSTRAP_SEED,
        "selection_rule": "corrected_label_b_gate_first_then_quality_tiebreak",
        "quality": quality_audit,
        "quality_excluded_from_primary": True,
        "rows": output_rows,
        "frontier": frontier,
        "best_observed_exploratory": best_observed,
        "best_deployable_claim_made": False,
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in source_paths
        },
        "output_sha256": {
            str(RECIPE_V2_CSV.relative_to(ROOT)): sha256_file(RECIPE_V2_CSV),
            str(RECIPE_V2_REPORT.relative_to(ROOT)): sha256_file(RECIPE_V2_REPORT),
        },
        "generator_source_sha256": sha256_file(COMPLETION_SCRIPT),
        "new_music_generation": 0,
    }
    write_json_once(RECIPE_V2_AUDIT, audit)
    return audit


def _artifact_line(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return f"`{path.relative_to(ROOT)}` (SHA-256 `{sha256_file(path)}`)"


def build_final_report(branch: str, implementation_commit: str) -> dict:
    required = (
        EVALUATOR_REPORT,
        EVALUATOR_AUDIT,
        EVALUATOR_AUDIOSET_SCORES,
        EVALUATOR_AUDIOSET_AUDIT,
        UNCONDITIONAL_V2_REPORT,
        UNCONDITIONAL_V2_CSV,
        UNCONDITIONAL_V2_AUDIT,
        RECIPE_V2_REPORT,
        RECIPE_V2_CSV,
        RECIPE_V2_AUDIT,
        NEUTRAL_REPORT,
        NEUTRAL_RESULTS,
        TEST_RESULTS,
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    evaluator = json.loads(EVALUATOR_AUDIT.read_text(encoding="utf-8"))
    audioset = json.loads(EVALUATOR_AUDIOSET_AUDIT.read_text(encoding="utf-8"))
    unconditional = json.loads(UNCONDITIONAL_V2_AUDIT.read_text(encoding="utf-8"))
    recipes = json.loads(RECIPE_V2_AUDIT.read_text(encoding="utf-8"))
    if evaluator.get("status") != "COMPLETE":
        raise ValueError("evaluator v2 audit is not COMPLETE")
    if audioset.get("status") != "COMPLETE" or audioset.get("new_music_generation") != 0:
        raise ValueError("AudioSet whitelist audit is not complete and generation-free")
    if unconditional.get("status") != "COMPLETE" or unconditional.get("rows") != 256:
        raise ValueError("unconditional v2 audit is incomplete or changed cardinality")
    if recipes.get("status") != "COMPLETE" or recipes.get("factorial_rows") != 3072:
        raise ValueError("recipe v2 audit is incomplete or changed cardinality")
    if any(
        audit.get("new_music_generation") != 0
        for audit in (evaluator, audioset, unconditional, recipes)
    ):
        raise ValueError("completion evidence unexpectedly reports new music generation")
    panel_a = evaluator["panel_a_pi_only"]
    panel_b = evaluator["panel_b_merged_gold_supplement"]
    tests = TEST_RESULTS.read_text(encoding="utf-8")
    if "Result: PASS" not in tests:
        raise ValueError("Dispatch A test record is not PASS")
    lines = [
        "# Exit-1 v2 Final Report",
        "",
        "ITEM_1_EVALUATOR_COMPARISON_V2_STATUS = COMPLETE",
        "evidence: " + _artifact_line(EVALUATOR_REPORT) + "; " + _artifact_line(EVALUATOR_AUDIT),
        "",
        "ITEM_2_UNCONDITIONAL_BASE_RATE_V2_STATUS = COMPLETE",
        "evidence: " + _artifact_line(UNCONDITIONAL_V2_REPORT) + "; "
        + _artifact_line(UNCONDITIONAL_V2_CSV) + "; " + _artifact_line(UNCONDITIONAL_V2_AUDIT),
        "",
        "ITEM_3_EVALUATOR_PANEL_UNIVERSE_STATUS = COMPLETE",
        "evidence: " + _artifact_line(EVALUATOR_REPORT) + "; " + _artifact_line(EVALUATOR_AUDIT),
        "",
        "ITEM_4_AUDIOSET_HUMAN_VOICE_WHITELIST_STATUS = PASS",
        "evidence: " + _artifact_line(EVALUATOR_AUDIOSET_SCORES) + "; "
        + _artifact_line(EVALUATOR_AUDIOSET_AUDIT) + "; "
        + _artifact_line(EVALUATOR_SCRIPT) + "; " + _artifact_line(EVALUATOR_TEST),
        "",
        "ITEM_5_RECIPE_CURVES_V2_STATUS = COMPLETE",
        "evidence: " + _artifact_line(RECIPE_V2_REPORT) + "; "
        + _artifact_line(RECIPE_V2_CSV) + "; " + _artifact_line(RECIPE_V2_AUDIT),
        "",
        "ITEM_6_MATCHED_NEUTRAL_CONTROL_STATUS = COMPLETE",
        "evidence: " + _artifact_line(NEUTRAL_REPORT) + "; " + _artifact_line(NEUTRAL_RESULTS),
        "",
        "ITEM_7_EXIT1_V2_FINAL_REPORT_STATUS = COMPLETE",
        "evidence: `analysis_exit1_v2/EXIT1_V2_FINAL_REPORT.md`",
        "",
        "NEW_MUSIC_GENERATION = 0",
        "evidence: `analysis_exit1_v2/UNCONDITIONAL_BASE_RATE_V2_AUDIT.json`; "
        "`analysis_exit1_v2/RECIPE_CURVES_V2_AUDIT.json`; "
        "`analysis_exit1_v2/EVALUATOR_AUDIOSET_HUMAN_VOICE_AUDIT.json`",
        "",
        "TEST_SUITE_STATUS = PASS",
        "evidence: " + _artifact_line(TEST_RESULTS) + "; "
        + _artifact_line(COMPLETION_TEST),
        "",
        "## Evaluator panel universes",
        "",
        f"- Panel A (primary): PI-only held-out Label-A gold; exact n={panel_a['rows']} "
        f"({panel_a['decided_positives']} decided positive, "
        f"{panel_a['decided_negatives']} decided negative, 0 unsure in metric rows). "
        f"Power status: {'POWER_LIMITED' if panel_a['power_limited'] else 'ADEQUATELY_POWERED'}.",
        f"- Panel B (supplemental): merged PI plus validated-judge held-out Label-A gold; "
        f"exact n={panel_b['rows']} ({panel_b['decided_positives']} decided positive, "
        f"{panel_b['decided_negatives']} decided negative, 0 unsure in metric rows).",
        "",
        "Panel B remains instrument-qualified and does not replace Panel A. Every Panel-A "
        "metric carries `POWER_LIMITED` because PI-only decided negatives are below 30.",
        "",
        "## Item 4 clarification",
        "",
        "The corrected AudioSet comparator is embodied in "
        "`analysis_exit1_v2/exit1_evaluator_v2.py` as the exact "
        "`HUMAN_VOICE_AUDIOSET_LABELS` whitelist and "
        "`audioset_human_voice_indices`. The regression tests are "
        "`test_audioset_human_voice_whitelist_uses_exact_labels` and the parametrized "
        "`test_audioset_nonhuman_or_synthetic_labels_are_excluded`, which explicitly "
        "cover speech synthesizer, synthetic singing, bird vocalization, whale "
        "vocalization, and singing bowl.",
        "",
        "## Scope and provenance",
        "",
        f"- Branch: `{branch}`.",
        f"- Implementation/evidence commit: `{implementation_commit}`.",
        "- The commit containing this report is the report-delivery commit and is stated "
        "in the delivery response; a Git commit cannot self-embed its own hash.",
        "- This completion generated zero new music. Item 6's previously completed 192-clip "
        "neutral-control run remains separate, preserved evidence and was not rerun here.",
        "- `analysis_exit1/` and `analysis_exit1_v2/superseded_1af4a8a/` are preserved.",
        "- No PLAN, CLAIMS, W2, BOLT, checkpoint, or frozen ledger was modified.",
    ]
    _write_once(FINAL_REPORT, "\n".join(lines) + "\n")
    return {
        "status": "COMPLETE",
        "report": str(FINAL_REPORT.relative_to(ROOT)),
        "report_sha256": sha256_file(FINAL_REPORT),
        "branch": branch,
        "implementation_commit": implementation_commit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("unconditional")
    sub.add_parser("recipes")
    final = sub.add_parser("final-report")
    final.add_argument("--branch", required=True)
    final.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    if args.command == "unconditional":
        result = build_unconditional_v2()
    elif args.command == "recipes":
        result = build_recipe_curves_v2()
    elif args.command == "final-report":
        result = build_final_report(args.branch, args.implementation_commit)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
