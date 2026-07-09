#!/usr/bin/env python3
"""Summarize verified Early-Tweedie validation results for PI decision.

This script is CPU-only. It reads the independent verifier report produced by
``scripts/verify_early_tweedie_validation.py`` and writes a short Markdown memo
focused on the pre-specified Track A decision threshold.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _safe_float(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_nontrivial_prune_schedule(row: dict[str, Any]) -> bool:
    schedule = str(row.get("schedule", ""))
    return schedule != "full_bon8" and not schedule.startswith("random_")


def _select_primary_rows(report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    key_metrics = report.get("key_metrics") or {}
    schedules = [
        row for row in key_metrics.get("robust_common_all_schedules", [])
        if row.get("metric") == "common_robust_lcb" and row.get("stratum") == "all"
    ]
    retention = [
        row for row in key_metrics.get("robust_common_all_retention", [])
        if row.get("metric") == "common_robust_lcb" and row.get("stratum") == "all"
    ]
    return schedules, retention


def _thresholds(report: dict[str, Any]) -> dict[str, float]:
    defaults = {
        "reward_fraction_min": 0.98,
        "compute_fraction_max": 0.5,
        "bottom_prune_false_negative_max": 0.05,
    }
    raw = (report.get("key_metrics") or {}).get("strong_candidate_threshold") or {}
    for key, default in defaults.items():
        try:
            defaults[key] = float(raw.get(key, default))
        except (TypeError, ValueError):
            defaults[key] = default
    return defaults


def _decision(report: dict[str, Any]) -> dict[str, Any]:
    thresholds = _thresholds(report)
    schedules, retention = _select_primary_rows(report)
    efficient = []
    for row in schedules:
        compute = _safe_float(row, "compute_fraction")
        reward = _safe_float(row, "reward_fraction")
        if (
            _is_nontrivial_prune_schedule(row)
            and compute is not None
            and reward is not None
            and compute <= thresholds["compute_fraction_max"]
            and reward >= thresholds["reward_fraction_min"]
        ):
            efficient.append(row)

    bottom25_values = [
        _safe_float(row, "bottom25_false_negative")
        for row in retention
        if str(row.get("sigma")) in {"0.8", "0.7"}
    ]
    bottom25_values = [v for v in bottom25_values if v is not None]
    min_bottom25 = min(bottom25_values) if bottom25_values else None
    bottom_pass = (
        min_bottom25 is not None
        and min_bottom25 <= thresholds["bottom_prune_false_negative_max"]
    )

    verifier_status = str(report.get("status", "UNKNOWN"))
    verifier_ok = verifier_status in {"PASS", "PASS_WITH_WARNINGS"}
    strong_candidate = bool(verifier_ok and efficient and bottom_pass)
    return {
        "strong_candidate": strong_candidate,
        "verifier_status": verifier_status,
        "verifier_ok": verifier_ok,
        "thresholds": thresholds,
        "efficient_schedules": efficient,
        "min_bottom25_false_negative_sigma0.8_or_0.7": min_bottom25,
        "bottom_prune_threshold_pass": bottom_pass,
        "primary_schedules": schedules,
        "primary_retention": retention,
    }


def _schedule_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| schedule | compute_fraction | reward_fraction | winner_match | false_negative | median_regret | n_prompts |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {schedule} | {compute} | {reward} | {winner} | {false_neg} | {regret} | {n} |".format(
                schedule=row.get("schedule"),
                compute=_fmt(_safe_float(row, "compute_fraction")),
                reward=_fmt(_safe_float(row, "reward_fraction")),
                winner=_fmt(_safe_float(row, "winner_match")),
                false_neg=_fmt(_safe_float(row, "false_negative")),
                regret=_fmt(_safe_float(row, "median_regret")),
                n=row.get("n_prompts", "NA"),
            )
        )
    return lines


def _retention_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| sigma | top1 | top2 | top4 | bottom25_false_negative | n_prompts |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {sigma} | {top1} | {top2} | {top4} | {fn} | {n} |".format(
                sigma=row.get("sigma"),
                top1=_fmt(_safe_float(row, "winner_retention_top1")),
                top2=_fmt(_safe_float(row, "winner_retention_top2")),
                top4=_fmt(_safe_float(row, "winner_retention_top4")),
                fn=_fmt(_safe_float(row, "bottom25_false_negative")),
                n=row.get("n_prompts", "NA"),
            )
        )
    return lines


def build_markdown(report: dict[str, Any], report_path: Path) -> str:
    decision = _decision(report)
    thresholds = decision["thresholds"]
    warnings = report.get("warnings") or []
    errors = report.get("errors") or []
    counts = report.get("counts") or {}

    verdict = (
        "STRONG_CANDIDATE_MAIN_APPLICATION"
        if decision["strong_candidate"]
        else "NOT_YET_STRONG_CANDIDATE"
    )
    if errors:
        verdict = "VERIFIER_FAILED_NO_SCIENTIFIC_DECISION"

    lines: list[str] = []
    lines.append("# Early-Tweedie Validation PI Decision Summary")
    lines.append("")
    lines.append(f"Verifier report: `{report_path}`")
    lines.append("")
    lines.append(f"Decision status: `{verdict}`")
    lines.append(f"Verifier status: `{decision['verifier_status']}`")
    lines.append(f"Warnings: `{len(warnings)}`")
    lines.append(f"Errors: `{len(errors)}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- prompts observed: `{counts.get('n_prompts', 'NA')}`")
    lines.append(f"- candidate records observed: `{counts.get('n_records', 'NA')}`")
    lines.append(f"- manifest prompts: `{counts.get('manifest_n_prompts', 'NA')}`")
    lines.append(f"- prompt split counts: `{counts.get('prompt_split_counts', 'NA')}`")
    lines.append("")
    lines.append("## Pre-Specified Threshold")
    lines.append("")
    lines.append(f"- reward_fraction >= `{thresholds['reward_fraction_min']}`")
    lines.append(f"- compute_fraction <= `{thresholds['compute_fraction_max']}`")
    lines.append(f"- bottom-prune false-negative <= `{thresholds['bottom_prune_false_negative_max']}`")
    lines.append("")
    lines.append("## Robust/Common Primary Schedule Rows")
    lines.append("")
    lines.extend(_schedule_table(decision["primary_schedules"]))
    lines.append("")
    lines.append("## Robust/Common Primary Retention Rows")
    lines.append("")
    lines.extend(_retention_table(decision["primary_retention"]))
    lines.append("")
    lines.append("## Threshold Readout")
    lines.append("")
    if decision["efficient_schedules"]:
        lines.append("Efficient non-random pruning schedules meeting reward/compute threshold:")
        for row in decision["efficient_schedules"]:
            lines.append(
                f"- `{row.get('schedule')}`: reward_fraction={_fmt(_safe_float(row, 'reward_fraction'))}, "
                f"compute_fraction={_fmt(_safe_float(row, 'compute_fraction'))}, "
                f"winner_match={_fmt(_safe_float(row, 'winner_match'))}"
            )
    else:
        lines.append("No non-random pruning schedule met the reward/compute threshold.")
    lines.append("")
    lines.append(
        "Best bottom25 false-negative at sigma 0.8/0.7: "
        f"`{_fmt(decision['min_bottom25_false_negative_sigma0.8_or_0.7'])}`"
    )
    lines.append(f"Bottom-prune threshold pass: `{decision['bottom_prune_threshold_pass']}`")
    lines.append("")
    lines.append("## Interpretation Guardrails")
    lines.append("")
    lines.append("- Use `common_robust_lcb / all` as the primary readout.")
    lines.append("- Treat constant-metric rows, especially lyric-intelligibility rows on instrumental prompts, as diagnostic only.")
    lines.append("- Do not claim final main-method status without PI sign-off.")
    lines.append("- Do not launch pruning+RL from this result.")
    lines.append("")
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings[:20]:
            lines.append(f"- {warning}")
        if len(warnings) > 20:
            lines.append(f"- ... {len(warnings) - 20} more warnings")
        lines.append("")
    if errors:
        lines.append("## Errors")
        lines.append("")
        for error in errors[:20]:
            lines.append(f"- {error}")
        if len(errors) > 20:
            lines.append(f"- ... {len(errors) - 20} more errors")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verification-report",
        type=Path,
        default=Path("orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md"),
    )
    args = parser.parse_args()

    report = json.loads(args.verification_report.read_text(encoding="utf-8"))
    md = build_markdown(report, args.verification_report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(md, encoding="utf-8")
    print(args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
