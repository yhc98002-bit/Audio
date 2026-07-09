"""Post-run analyzer for Phase C1 first-wave train logs.

This script is intentionally read-only with respect to C1 run directories. It
loads completed ``train_log.jsonl`` or ``*_log.jsonl`` files and optional
``*_results.json`` files, then writes derived tables and plots to a separate
analysis directory.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_METHOD_DIRS = ("r8a", "r8b", "m_fixedwin", "m_section")


@dataclass
class RunSpec:
    label: str
    run_dir: Path
    log_path: Path
    result_path: Path | None


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
    return rows


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _pstdev(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _min(values: list[float]) -> float | None:
    return min(values) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "NA"
        return f"{value:.{digits}g}"
    return str(value)


def _extract_rewards(row: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for report in row.get("reward_reports") or []:
        if not isinstance(report, dict):
            continue
        for key in ("terminal_reward", "process_reward", "reward", "r_music_robust_lcb"):
            value = _safe_float(report.get(key))
            if value is not None:
                values.append(value)
                break
    if values:
        return values
    reward_stats = (
        row.get("update_metrics", {})
        .get("advantage_info", {})
        .get("reward", {})
    )
    value = _safe_float(reward_stats.get("mean"))
    return [value] if value is not None else []


def _discover_specs(root: Path) -> list[RunSpec]:
    specs: list[RunSpec] = []
    for label in DEFAULT_METHOD_DIRS:
        run_dir = root / label
        if not run_dir.is_dir():
            continue
        train_log = run_dir / "train_log.jsonl"
        logs = sorted(run_dir.glob("*_log.jsonl"))
        if not train_log.exists() and not logs:
            continue
        log_path = train_log if train_log.exists() else logs[-1]
        result_candidates = sorted(run_dir.glob("*_results.json"))
        result_path = result_candidates[-1] if result_candidates else None
        specs.append(RunSpec(label=label, run_dir=run_dir, log_path=log_path, result_path=result_path))
    return specs


def _parse_run_arg(value: str) -> RunSpec:
    if "=" in value:
        label, raw_path = value.split("=", 1)
    else:
        p = Path(value)
        label, raw_path = p.name, value
    run_dir = Path(raw_path)
    train_log = run_dir / "train_log.jsonl"
    logs = sorted(run_dir.glob("*_log.jsonl"))
    if not train_log.exists() and not logs:
        raise FileNotFoundError(f"no train_log.jsonl or *_log.jsonl found in {run_dir}")
    log_path = train_log if train_log.exists() else logs[-1]
    result_candidates = sorted(run_dir.glob("*_results.json"))
    result_path = result_candidates[-1] if result_candidates else None
    return RunSpec(label=label, run_dir=run_dir, log_path=log_path, result_path=result_path)


def _summarize_run(spec: RunSpec, *, require_complete: bool) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    result = _read_json(spec.result_path) if spec.result_path and spec.result_path.exists() else {}
    if require_complete:
        if not result:
            raise RuntimeError(f"{spec.label}: result JSON missing; use --allow-incomplete only for diagnostics")
        if result.get("status") != "PASS":
            raise RuntimeError(f"{spec.label}: result status is {result.get('status')!r}, expected PASS")

    rows = _read_jsonl(spec.log_path)
    opt_rows = [r for r in rows if r.get("event") == "optimizer_step"]
    ckpt_rows = [r for r in rows if r.get("event") == "checkpoint_saved_and_resumed"]
    if require_complete and not opt_rows:
        raise RuntimeError(f"{spec.label}: no optimizer_step rows in {spec.log_path}")

    step_rows: list[dict[str, Any]] = []
    reward_values_all: list[float] = []
    reward_std_values: list[float] = []
    loss_values: list[float] = []
    policy_loss_values: list[float] = []
    kl_old_values: list[float] = []
    kl_ref_values: list[float] = []
    ratio_mean_values: list[float] = []
    ratio_std_values: list[float] = []
    grad_norm_values: list[float] = []
    clip_fraction_values: list[float] = []
    adapter_updated_count = 0
    frozen_unchanged_count = 0

    for row in opt_rows:
        metrics = row.get("update_metrics") or {}
        ratio = metrics.get("ratio") or {}
        rewards = _extract_rewards(row)
        reward_values_all.extend(rewards)
        reward_mean = _mean(rewards)
        reward_pstd = _pstdev(rewards)

        values = {
            "reward_std": _safe_float(row.get("reward_std")),
            "loss": _safe_float(metrics.get("loss")),
            "policy_loss": _safe_float(metrics.get("policy_loss")),
            "approx_kl_old": _safe_float(metrics.get("approx_kl_old")),
            "approx_kl_ref": _safe_float(metrics.get("approx_kl_ref")),
            "ratio_mean": _safe_float(ratio.get("mean")),
            "ratio_std": _safe_float(ratio.get("std")),
            "ratio_min": _safe_float(ratio.get("min")),
            "ratio_max": _safe_float(ratio.get("max")),
            "clip_fraction": _safe_float(metrics.get("clip_fraction")),
            "grad_norm": _safe_float(metrics.get("grad_norm")),
        }
        for target, source in (
            (reward_std_values, values["reward_std"]),
            (loss_values, values["loss"]),
            (policy_loss_values, values["policy_loss"]),
            (kl_old_values, values["approx_kl_old"]),
            (kl_ref_values, values["approx_kl_ref"]),
            (ratio_mean_values, values["ratio_mean"]),
            (ratio_std_values, values["ratio_std"]),
            (clip_fraction_values, values["clip_fraction"]),
            (grad_norm_values, values["grad_norm"]),
        ):
            if source is not None:
                target.append(source)
        if metrics.get("adapter_updated") is True:
            adapter_updated_count += 1
        if (metrics.get("frozen_parameters") or {}).get("unchanged") is True:
            frozen_unchanged_count += 1

        step_rows.append({
            "label": spec.label,
            "step": row.get("step"),
            "mode": row.get("mode"),
            "method": row.get("method"),
            "method_id": row.get("method_id"),
            "prompt_ids": ";".join(row.get("prompt_ids") or []),
            "group_size": row.get("group_size"),
            "infer_steps": row.get("infer_steps"),
            "elapsed_seconds": _safe_float(row.get("elapsed_seconds")),
            "gpu_hours_consumed": _safe_float(row.get("gpu_hours_consumed")),
            "reward_mean": reward_mean,
            "reward_pstd": reward_pstd,
            **values,
            "adapter_updated": metrics.get("adapter_updated"),
            "base_parameters_unchanged": (metrics.get("frozen_parameters") or {}).get("unchanged"),
            "nonzero_grad_tensors": metrics.get("nonzero_grad_tensors"),
            "n_zero_variance_groups": (
                metrics.get("advantage_info", {}).get("n_zero_variance_groups")
                if isinstance(metrics.get("advantage_info"), dict) else None
            ),
        })

    checkpoints = [
        {
            "label": spec.label,
            "step": r.get("step"),
            "checkpoint_path": r.get("checkpoint_path"),
            "checkpoint_resume_ok": r.get("checkpoint_resume_ok"),
        }
        for r in ckpt_rows
    ]

    summary = {
        "label": spec.label,
        "run_dir": str(spec.run_dir),
        "log_path": str(spec.log_path),
        "result_path": str(spec.result_path) if spec.result_path else None,
        "status": result.get("status"),
        "mode": result.get("mode") or (opt_rows[-1].get("mode") if opt_rows else None),
        "method": result.get("method") or (opt_rows[-1].get("method") if opt_rows else None),
        "method_id": result.get("method_id") or (opt_rows[-1].get("method_id") if opt_rows else None),
        "reward_mode": result.get("reward_mode"),
        "steps_completed": result.get("steps_completed") or len(opt_rows),
        "optimizer_step_rows": len(opt_rows),
        "gpu_hours_consumed": result.get("gpu_hours_consumed") or sum(
            x for x in (_safe_float(r.get("gpu_hours_consumed")) for r in opt_rows) if x is not None
        ),
        "reward_mean_over_rollouts": _mean(reward_values_all),
        "reward_std_over_rollouts": _pstdev(reward_values_all),
        "min_step_reward_std": _min(reward_std_values),
        "mean_loss": _mean(loss_values),
        "mean_policy_loss": _mean(policy_loss_values),
        "max_abs_kl_old": _max([abs(x) for x in kl_old_values]),
        "max_abs_kl_ref": _max([abs(x) for x in kl_ref_values]),
        "mean_ratio_mean": _mean(ratio_mean_values),
        "max_ratio_std": _max(ratio_std_values),
        "max_clip_fraction": _max(clip_fraction_values),
        "min_grad_norm": _min(grad_norm_values),
        "max_grad_norm": _max(grad_norm_values),
        "adapter_updated_all_steps": bool(opt_rows) and adapter_updated_count == len(opt_rows),
        "base_parameters_unchanged_all_steps": bool(opt_rows) and frozen_unchanged_count == len(opt_rows),
        "checkpoint_count": len(ckpt_rows),
        "checkpoint_resume_all_ok": bool(ckpt_rows) and all(r.get("checkpoint_resume_ok") is True for r in ckpt_rows),
        "result_checkpoint_path": result.get("checkpoint_path"),
        "result_checkpoint_resume_ok": result.get("checkpoint_resume_ok"),
        "base_parameters_frozen": result.get("base_parameters_frozen"),
        "final_adapter_digest_changed": (
            result.get("initial_adapter_digest") != result.get("final_adapter_digest")
            if result.get("initial_adapter_digest") and result.get("final_adapter_digest")
            else None
        ),
    }
    return summary, step_rows, checkpoints


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        if not fieldnames:
            f.write("\n")
            return
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path: Path, summary_rows: list[dict[str, Any]], step_rows: list[dict[str, Any]], ckpt_rows: list[dict[str, Any]], plot_paths: list[str], commands: list[str]) -> None:
    lines = [
        "# Phase C1 Post-Run Analysis",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        "## Commands",
        "",
    ]
    lines.extend([f"- `{cmd}`" for cmd in commands] or ["- NA"])
    lines.extend([
        "",
        "## Run Summary",
        "",
        "| method | status | steps | gpu_h | reward_mean | reward_std | min_step_reward_std | mean_loss | max_abs_kl_ref | min_grad_norm | max_grad_norm | adapter_updated_all | base_unchanged_all | ckpt_ok |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ])
    for row in summary_rows:
        lines.append(
            "| {label} | {status} | {steps} | {gpu_h} | {reward_mean} | {reward_std} | "
            "{min_reward_std} | {loss} | {kl_ref} | {min_grad} | {max_grad} | "
            "{adapter} | {base} | {ckpt} |".format(
                label=row.get("label"),
                status=_fmt(row.get("status")),
                steps=_fmt(row.get("steps_completed")),
                gpu_h=_fmt(row.get("gpu_hours_consumed")),
                reward_mean=_fmt(row.get("reward_mean_over_rollouts")),
                reward_std=_fmt(row.get("reward_std_over_rollouts")),
                min_reward_std=_fmt(row.get("min_step_reward_std")),
                loss=_fmt(row.get("mean_loss")),
                kl_ref=_fmt(row.get("max_abs_kl_ref")),
                min_grad=_fmt(row.get("min_grad_norm")),
                max_grad=_fmt(row.get("max_grad_norm")),
                adapter=_fmt(row.get("adapter_updated_all_steps")),
                base=_fmt(row.get("base_parameters_unchanged_all_steps")),
                ckpt=_fmt(row.get("checkpoint_resume_all_ok") or row.get("result_checkpoint_resume_ok")),
            )
        )

    lines.extend([
        "",
        "## Output Tables",
        "",
        "- `summary.csv`: one row per method.",
        "- `steps.csv`: one row per optimizer step.",
        "- `checkpoints.csv`: checkpoint/resume events.",
        "",
        "## Plots",
        "",
    ])
    lines.extend([f"- `{p}`" for p in plot_paths] if plot_paths else ["- No plots written."])
    lines.extend([
        "",
        "## Audit Notes",
        "",
        "- Source C1 run directories were read only; all derived artifacts were written under this analysis directory.",
        "- Analyzer refuses incomplete runs unless `--allow-incomplete` is supplied.",
        "- `base_unchanged_all` is taken from backend frozen-parameter digest checks in each optimizer step.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plots(out_dir: Path, step_rows: list[dict[str, Any]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        note = out_dir / "plots_unavailable.txt"
        note.write_text(f"matplotlib import failed: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return [str(note)]

    metrics = [
        ("reward_mean", "Reward Mean"),
        ("reward_std", "Reward Std"),
        ("loss", "Loss"),
        ("approx_kl_ref", "KL vs Ref"),
        ("ratio_mean", "Ratio Mean"),
        ("grad_norm", "Grad Norm"),
    ]
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    labels = sorted({str(r.get("label")) for r in step_rows})
    for key, title in metrics:
        has_any = any(_safe_float(r.get(key)) is not None for r in step_rows)
        if not has_any:
            continue
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for label in labels:
            rows = [r for r in step_rows if str(r.get("label")) == label]
            xs = [int(r.get("step") or 0) for r in rows if _safe_float(r.get(key)) is not None]
            ys = [_safe_float(r.get(key)) for r in rows if _safe_float(r.get(key)) is not None]
            if xs and ys:
                ax.plot(xs, ys, marker="o", linewidth=1.4, markersize=3, label=label)
        ax.set_title(title)
        ax.set_xlabel("optimizer step")
        ax.set_ylabel(key)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()
        path = plot_dir / f"{key}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        written.append(str(path))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Phase C1 first-wave root containing r8a/r8b/m_fixedwin/m_section subdirectories.")
    parser.add_argument("--run-dir", action="append", default=[], help="Run directory, optionally label=path. May be repeated.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Separate directory for derived analysis outputs.")
    parser.add_argument("--allow-incomplete", action="store_true", help="Allow missing/non-PASS result JSON. Intended only for smoke/debug.")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    specs: list[RunSpec] = []
    if args.root:
        specs.extend(_discover_specs(args.root))
    for value in args.run_dir:
        specs.append(_parse_run_arg(value))
    if not specs:
        raise SystemExit("no run specs found; pass --root or --run-dir")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    ckpt_rows: list[dict[str, Any]] = []
    for spec in specs:
        summary, steps, checkpoints = _summarize_run(spec, require_complete=not args.allow_incomplete)
        summary_rows.append(summary)
        step_rows.extend(steps)
        ckpt_rows.extend(checkpoints)

    _write_csv(args.out_dir / "summary.csv", summary_rows)
    _write_csv(args.out_dir / "steps.csv", step_rows)
    _write_csv(args.out_dir / "checkpoints.csv", ckpt_rows)
    (args.out_dir / "summary.json").write_text(
        json.dumps(
            {
                "generated_at_utc": _now_utc(),
                "inputs": [spec.__dict__ | {"run_dir": str(spec.run_dir), "log_path": str(spec.log_path), "result_path": str(spec.result_path) if spec.result_path else None} for spec in specs],
                "summary": summary_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    plot_paths = [] if args.no_plots else _write_plots(args.out_dir, step_rows)
    command = "python scripts/analyze_phase_c1_firstwave.py " + " ".join(
        [
            *(["--root", str(args.root)] if args.root else []),
            *sum((["--run-dir", x] for x in args.run_dir), []),
            "--out-dir",
            str(args.out_dir),
            *(["--allow-incomplete"] if args.allow_incomplete else []),
            *(["--no-plots"] if args.no_plots else []),
        ]
    )
    _write_md(args.out_dir / "analysis_summary.md", summary_rows, step_rows, ckpt_rows, plot_paths, [command])
    print(json.dumps({"status": "ok", "out_dir": str(args.out_dir), "n_runs": len(specs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
