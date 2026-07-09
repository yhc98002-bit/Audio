#!/usr/bin/env python3
"""Summarize and sanity-check future C1-lite RL rescue smoke/triage outputs.

This script is CPU-only and read-only. It scans a run root for ``train_log.jsonl``
and optional ``train_results.json`` files, then writes a compact JSON and
Markdown report focused on the bounded Track C rescue criteria:

- post-update ratio/log-ratio/KL diagnostics are present;
- adapter norm delta is logged;
- adapter updates and base parameters stay frozen;
- safety flags remain false;
- step count and GPU-hour accounting stay within the configured bounds.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SAFETY_FALSE_FLAGS = (
    "held_out_launched",
    "phase_d_launched",
    "human_eval_launched",
    "reward_definitions_changed",
    "sigma_policy_changed",
    "prompt_splits_changed",
    "credit_unit_definitions_changed",
    "gate_v1_touched_by_runner",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["_line_no"] = line_no
            rows.append(row)
    return rows


def _finite(value: Any) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x)


def _stat_range(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "max": None, "last": None}
    return {"min": min(values), "max": max(values), "last": values[-1]}


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _summarize_log(
    log_path: Path,
    *,
    require_track_c_instrumentation: bool,
    max_steps: int | None,
) -> dict[str, Any]:
    rows = _iter_jsonl(log_path)
    step_rows = [row for row in rows if row.get("event") == "optimizer_step"]
    errors: list[str] = []
    warnings: list[str] = []

    if not step_rows:
        errors.append("no optimizer_step rows found")

    method = step_rows[-1].get("method") if step_rows else None
    method_id = step_rows[-1].get("method_id") if step_rows else None
    steps = [int(row.get("step", -1)) for row in step_rows]
    steps_completed = len(step_rows)
    max_observed_step = max(steps) if steps else None
    if max_steps is not None and steps_completed > max_steps:
        errors.append(f"steps_completed {steps_completed} exceeds max_steps {max_steps}")

    update_rows = [row.get("update_metrics") or {} for row in step_rows]
    missing_update = [row.get("_line_no") for row, metrics in zip(step_rows, update_rows) if not metrics]
    if missing_update:
        errors.append(f"rows missing update_metrics: {missing_update[:8]}")

    grad_norms = []
    reward_stds = []
    advantage_gains = []
    post_ratio_std = []
    adapter_delta = []
    for row, metrics in zip(step_rows, update_rows):
        line_no = row.get("_line_no")
        grad = metrics.get("grad_norm")
        if _finite(grad):
            grad_norms.append(float(grad))
        else:
            errors.append(f"line {line_no}: missing/non-finite grad_norm")

        reward_std = row.get("reward_std")
        if _finite(reward_std):
            reward_stds.append(float(reward_std))

        gain = metrics.get("advantage_gain")
        if _finite(gain):
            advantage_gains.append(float(gain))
        else:
            if require_track_c_instrumentation:
                errors.append(f"line {line_no}: missing advantage_gain")

        if metrics.get("adapter_updated") is not True:
            errors.append(f"line {line_no}: adapter_updated is not true")
        frozen = metrics.get("frozen_parameters") or {}
        if frozen.get("unchanged") is not True:
            errors.append(f"line {line_no}: frozen_parameters.unchanged is not true")

        post_update = metrics.get("post_update")
        if post_update is None:
            if require_track_c_instrumentation:
                errors.append(f"line {line_no}: missing post_update diagnostics")
        else:
            ratio_std = _get_nested(post_update, "ratio.std")
            if _finite(ratio_std):
                post_ratio_std.append(float(ratio_std))
            else:
                errors.append(f"line {line_no}: post_update.ratio.std missing/non-finite")
            for key in ("approx_kl_old", "approx_kl_ref", "clip_fraction"):
                if not _finite(post_update.get(key)):
                    errors.append(f"line {line_no}: post_update.{key} missing/non-finite")
            for key in ("ratio", "log_ratio"):
                stats = post_update.get(key) or {}
                for skey in ("mean", "std", "min", "max"):
                    if not _finite(stats.get(skey)):
                        errors.append(f"line {line_no}: post_update.{key}.{skey} missing/non-finite")

        norm = metrics.get("adapter_norm")
        if norm is None:
            if require_track_c_instrumentation:
                errors.append(f"line {line_no}: missing adapter_norm diagnostics")
        else:
            delta = norm.get("delta_l2")
            if _finite(delta):
                adapter_delta.append(float(delta))
            else:
                errors.append(f"line {line_no}: adapter_norm.delta_l2 missing/non-finite")

        for metric_name in ("loss", "policy_loss", "approx_kl_old", "approx_kl_ref", "clip_fraction"):
            if metric_name in metrics and not _finite(metrics.get(metric_name)):
                errors.append(f"line {line_no}: {metric_name} is non-finite")

        safety = row.get("safety") or {}
        for flag in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
            if safety.get(flag) is not False:
                errors.append(f"line {line_no}: safety flag {flag} is not false")

    result_path = log_path.with_name("train_results.json")
    result: dict[str, Any] | None = None
    if result_path.exists():
        result = _load_json(result_path)
        if result.get("status") != "PASS":
            errors.append(f"{result_path}: status is not PASS: {result.get('status')!r}")
        if result.get("adapter_updated") is not True:
            errors.append(f"{result_path}: adapter_updated is not true")
        if result.get("base_parameters_frozen") is not True:
            errors.append(f"{result_path}: base_parameters_frozen is not true")
        if result.get("checkpoint_resume_ok") is not True:
            warnings.append(f"{result_path}: checkpoint_resume_ok is not true")
        if max_steps is not None and int(result.get("steps_completed", 0)) > max_steps:
            errors.append(f"{result_path}: steps_completed exceeds max_steps")
        # Definition-change and gate flags are run-level invariants in the
        # existing runner, so the full SAFETY_FALSE_FLAGS check is anchored on
        # train_results.json rather than repeated for every train_log row.
        for flag in SAFETY_FALSE_FLAGS:
            if flag in result and result.get(flag) is not False:
                errors.append(f"{result_path}: {flag} is not false")
    else:
        warnings.append(f"missing train_results.json beside {log_path}")

    return {
        "log_path": str(log_path),
        "result_path": str(result_path) if result_path.exists() else None,
        "method": method,
        "method_id": method_id,
        "status": "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "steps_completed": steps_completed,
        "max_observed_step": max_observed_step,
        "gpu_hours_consumed": result.get("gpu_hours_consumed") if result else None,
        "grad_norm": _stat_range(grad_norms),
        "reward_std": _stat_range(reward_stds),
        "advantage_gain_values": sorted(set(round(x, 8) for x in advantage_gains)),
        "post_update_ratio_std": _stat_range(post_ratio_std),
        "adapter_norm_delta_l2": _stat_range(adapter_delta),
        "post_update_rows": len(post_ratio_std),
        "adapter_norm_rows": len(adapter_delta),
        "errors": errors,
        "warnings": warnings,
    }


def _build_markdown(summary: dict[str, Any]) -> str:
    lines = ["# C1-Lite RL Rescue Output Summary", ""]
    lines.append(f"Run root: `{summary['run_root']}`")
    lines.append(f"Overall status: `{summary['status']}`")
    lines.append(f"Require Track C instrumentation: `{summary['require_track_c_instrumentation']}`")
    lines.append(f"Max steps: `{summary['max_steps']}`")
    lines.append("")
    lines.append("## Per-Log Summary")
    lines.append("")
    lines.append("| method | status | steps | gpu_h | advantage_gain | post_rows | adapter_norm_rows | grad_norm_last | post_ratio_std_last |")
    lines.append("|---|---|---:|---:|---|---:|---:|---:|---:|")
    for row in summary["logs"]:
        lines.append(
            "| {method} | {status} | {steps} | {gpu_h} | {gain} | {post_rows} | {norm_rows} | {grad_last} | {post_std} |".format(
                method=row.get("method") or "NA",
                status=row.get("status"),
                steps=row.get("steps_completed"),
                gpu_h="NA" if row.get("gpu_hours_consumed") is None else f"{float(row['gpu_hours_consumed']):.4f}",
                gain=",".join(str(x) for x in row.get("advantage_gain_values", [])) or "NA",
                post_rows=row.get("post_update_rows"),
                norm_rows=row.get("adapter_norm_rows"),
                grad_last="NA" if row["grad_norm"]["last"] is None else f"{row['grad_norm']['last']:.4g}",
                post_std="NA" if row["post_update_ratio_std"]["last"] is None else f"{row['post_update_ratio_std']['last']:.4g}",
            )
        )
    lines.append("")
    lines.append("## Errors And Warnings")
    lines.append("")
    for row in summary["logs"]:
        if not row["errors"] and not row["warnings"]:
            continue
        lines.append(f"### `{row['log_path']}`")
        for error in row["errors"]:
            lines.append(f"- ERROR: {error}")
        for warning in row["warnings"]:
            lines.append(f"- WARNING: {warning}")
        lines.append("")
    if all(not row["errors"] and not row["warnings"] for row in summary["logs"]):
        lines.append("No errors or warnings.")
        lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- PASS means logs are structurally suitable for Track C triage interpretation.")
    lines.append("- This script does not decide scientific success; common downstream eval before/after is still required.")
    lines.append("- Do not use this report to justify held-out, Phase D, human eval, pruning+RL, or full 1000-step RL.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=250)
    parser.add_argument(
        "--no-require-track-c-instrumentation",
        action="store_true",
        help="Allow old C1 logs without post_update/adapter_norm diagnostics. Intended only for script self-checks.",
    )
    args = parser.parse_args()

    logs = sorted(args.run_root.glob("**/train_log.jsonl"))
    if not logs:
        raise SystemExit(f"no train_log.jsonl files found under {args.run_root}")
    require = not args.no_require_track_c_instrumentation
    summaries = [
        _summarize_log(log, require_track_c_instrumentation=require, max_steps=args.max_steps)
        for log in logs
    ]
    any_errors = any(row["errors"] for row in summaries)
    any_warnings = any(row["warnings"] for row in summaries)
    summary = {
        "schema_version": "c1_lite_rl_rescue_output_summary_v1",
        "run_root": str(args.run_root),
        "status": "FAIL" if any_errors else ("PASS_WITH_WARNINGS" if any_warnings else "PASS"),
        "require_track_c_instrumentation": require,
        "max_steps": args.max_steps,
        "n_logs": len(summaries),
        "logs": summaries,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_build_markdown(summary), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
