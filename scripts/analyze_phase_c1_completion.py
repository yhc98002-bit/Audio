"""CPU-only Phase C1 completion analyzer.

Reads existing C1 train logs, checkpoints, and train_results files. It never
modifies run directories.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any


METHODS = ("r8a", "r8b", "m_fixedwin", "m_section")
DISPLAY = {
    "r8a": "R8a",
    "r8b": "R8b",
    "m_fixedwin": "M-FixedWin",
    "m_section": "M-Section",
}
PROCESS_METHODS = ("m_fixedwin", "m_section")
TERMINAL_METHODS = ("r8a", "r8b")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def finite_json(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite_json(v) for v in value.values())
    if isinstance(value, list):
        return all(finite_json(v) for v in value)
    return True


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int, bool]:
    rows: list[dict[str, Any]] = []
    parse_errors = 0
    finite = True
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        rows.append(row)
        finite = finite and finite_json(row)
    return rows, parse_errors, finite


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(errors="replace")), None
    except json.JSONDecodeError as exc:
        return None, f"json_parse_error:{exc}"


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def pstdev(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def fmt(value: Any, digits: int = 6) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return "NA" if not math.isfinite(value) else f"{value:.{digits}g}"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def reward_values(row: dict[str, Any]) -> list[float]:
    values: list[float] = []
    for report in row.get("reward_reports") or []:
        if not isinstance(report, dict):
            continue
        for key in ("terminal_reward", "process_reward", "r_music_robust_lcb"):
            value = safe_float(report.get(key))
            if value is not None:
                values.append(value)
                break
    if values:
        return values
    reward = (((row.get("update_metrics") or {}).get("advantage_info") or {}).get("reward") or {})
    value = safe_float(reward.get("mean"))
    return [value] if value is not None else []


def curve_row(method: str, row: dict[str, Any]) -> dict[str, Any]:
    metrics = row.get("update_metrics") or {}
    ratio = metrics.get("ratio") or {}
    rewards = reward_values(row)
    return {
        "method": method,
        "display": DISPLAY[method],
        "step": row.get("step"),
        "prompt_ids": ";".join(row.get("prompt_ids") or []),
        "elapsed_seconds": safe_float(row.get("elapsed_seconds")),
        "gpu_hours_consumed": safe_float(row.get("gpu_hours_consumed")),
        "reward_mean": mean(rewards),
        "reward_std": pstdev(rewards),
        "loss": safe_float(metrics.get("loss")),
        "kl_old": safe_float(metrics.get("approx_kl_old")),
        "kl_ref": safe_float(metrics.get("approx_kl_ref")),
        "ratio_mean": safe_float(ratio.get("mean")),
        "ratio_std": safe_float(ratio.get("std")),
        "ratio_min": safe_float(ratio.get("min")),
        "ratio_max": safe_float(ratio.get("max")),
        "clip_fraction": safe_float(metrics.get("clip_fraction")),
        "grad_norm": safe_float(metrics.get("grad_norm")),
        "adapter_updated": metrics.get("adapter_updated"),
        "base_unchanged": (metrics.get("frozen_parameters") or {}).get("unchanged"),
        "zero_variance_groups": ((metrics.get("advantage_info") or {}).get("n_zero_variance_groups") or 0),
        "safety_held_out_launched": (row.get("safety") or {}).get("held_out_launched"),
        "safety_phase_d_launched": (row.get("safety") or {}).get("phase_d_launched"),
        "safety_human_eval_launched": (row.get("safety") or {}).get("human_eval_launched"),
    }


def summarize_window(rows: list[dict[str, Any]], method: str, label: str, start: int, stop: int) -> dict[str, Any]:
    win = [r for r in rows if isinstance(r.get("step"), int) and start <= r["step"] <= stop]
    return summarize_named_rows(win, method, label)


def summarize_named_rows(rows: list[dict[str, Any]], method: str, label: str) -> dict[str, Any]:
    rewards = [x for r in rows for x in reward_values(r)]
    step_reward_std = [safe_float(r.get("reward_std")) for r in rows]
    step_reward_std = [x for x in step_reward_std if x is not None]
    loss: list[float] = []
    kl_ref: list[float] = []
    ratio_mean: list[float] = []
    ratio_std: list[float] = []
    grad: list[float] = []
    elapsed: list[float] = []
    zero_variance = 0
    for row in rows:
        metrics = row.get("update_metrics") or {}
        ratio = metrics.get("ratio") or {}
        for arr, value in (
            (loss, safe_float(metrics.get("loss"))),
            (kl_ref, safe_float(metrics.get("approx_kl_ref"))),
            (ratio_mean, safe_float(ratio.get("mean"))),
            (ratio_std, safe_float(ratio.get("std"))),
            (grad, safe_float(metrics.get("grad_norm"))),
            (elapsed, safe_float(row.get("elapsed_seconds"))),
        ):
            if value is not None:
                arr.append(value)
        zero_variance += int((((metrics.get("advantage_info") or {}).get("n_zero_variance_groups") or 0)))
    return {
        "method": method,
        "display": DISPLAY[method],
        "window": label,
        "n_steps": len(rows),
        "reward_mean": mean(rewards),
        "reward_std": pstdev(rewards),
        "mean_step_reward_std": mean(step_reward_std),
        "mean_loss": mean(loss),
        "max_abs_kl_ref": max((abs(x) for x in kl_ref), default=None),
        "mean_ratio_mean": mean(ratio_mean),
        "max_ratio_std": max(ratio_std, default=None),
        "min_grad_norm": min(grad) if grad else None,
        "max_grad_norm": max(grad) if grad else None,
        "mean_sec_per_step": mean(elapsed),
        "zero_variance_groups": zero_variance,
    }


def status_from_checks(checks: dict[str, bool]) -> str:
    return "PASS" if all(checks.values()) else "FAIL"


def write_plots(out_dir: Path, curve_rows: list[dict[str, Any]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001
        note = out_dir / "plots_unavailable.txt"
        note.write_text(f"matplotlib unavailable: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        return [str(note)]
    plot_dir = out_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    metrics = [
        ("reward_mean", "Reward mean"),
        ("reward_std", "Reward std"),
        ("loss", "Loss"),
        ("kl_ref", "KL vs ref"),
        ("ratio_mean", "Ratio mean"),
        ("grad_norm", "Grad norm"),
        ("gpu_hours_cumulative", "Cumulative GPU-h"),
    ]
    rows_by_method: dict[str, list[dict[str, Any]]] = {m: [] for m in METHODS}
    cumulative = {m: 0.0 for m in METHODS}
    enriched: list[dict[str, Any]] = []
    for row in curve_rows:
        method = row["method"]
        cumulative[method] += row.get("gpu_hours_consumed") or 0.0
        copy = dict(row)
        copy["gpu_hours_cumulative"] = cumulative[method]
        enriched.append(copy)
        rows_by_method[method].append(copy)
    for key, title in metrics:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        has = False
        for method in METHODS:
            xs = [int(r["step"]) for r in rows_by_method[method] if safe_float(r.get(key)) is not None]
            ys = [safe_float(r.get(key)) for r in rows_by_method[method] if safe_float(r.get(key)) is not None]
            if xs and ys:
                has = True
                ax.plot(xs, ys, linewidth=1.2, label=DISPLAY[method])
        if not has:
            plt.close(fig)
            continue
        ax.set_title(title)
        ax.set_xlabel("optimizer step")
        ax.set_ylabel(key)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()
        path = plot_dir / f"{key}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(str(path))
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--expected-steps", type=int, default=1000)
    ap.add_argument("--allow-incomplete", action="store_true")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    curve_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    train_result_rows: list[dict[str, Any]] = []
    anomaly_rows: list[dict[str, Any]] = []
    opt_by_method: dict[str, list[dict[str, Any]]] = {}

    for method in METHODS:
        method_dir = args.root / method
        log_path = method_dir / "train_log.jsonl"
        if not log_path.exists():
            raise FileNotFoundError(log_path)
        rows, parse_errors, finite = read_jsonl(log_path)
        opt = [r for r in rows if r.get("event") == "optimizer_step"]
        opt_by_method[method] = opt
        if len(opt) < args.expected_steps and not args.allow_incomplete:
            raise RuntimeError(f"{method}: only {len(opt)} optimizer rows, need {args.expected_steps}")

        result, result_error = read_json(method_dir / "train_results.json")
        checkpoints = sorted(method_dir.glob("checkpoint_step_*.pt"))
        for ckpt in checkpoints:
            checkpoint_rows.append({
                "method": method,
                "display": DISPLAY[method],
                "checkpoint": str(ckpt),
                "exists": ckpt.exists(),
                "bytes": ckpt.stat().st_size if ckpt.exists() else None,
            })

        for row in opt:
            curve_rows.append(curve_row(method, row))

        last = curve_row(method, opt[-1]) if opt else {}
        gpu_h_log = sum((safe_float(r.get("gpu_hours_consumed")) or 0.0) for r in opt)
        result_gpu_h = safe_float((result or {}).get("gpu_hours_consumed"))
        result_status = (result or {}).get("status")
        result_checkpoint = (result or {}).get("checkpoint_path")
        checks = {
            "has_train_log": log_path.exists(),
            "parse_errors_zero": parse_errors == 0,
            "json_numeric_finite": finite,
            "reached_expected_steps": len(opt) >= args.expected_steps,
            "train_results_exists": result is not None,
            "train_results_pass": result_status == "PASS",
            "adapter_updated_all_logs": all(r.get("adapter_updated") is True for r in curve_rows if r["method"] == method),
            "base_unchanged_all_logs": all(r.get("base_unchanged") is True for r in curve_rows if r["method"] == method),
            "zero_variance_groups_zero": sum(int(r.get("zero_variance_groups") or 0) for r in curve_rows if r["method"] == method) == 0,
            "checkpoint_exists": bool(checkpoints),
            "held_out_not_launched": not bool((result or {}).get("held_out_launched")),
            "phase_d_not_launched": not bool((result or {}).get("phase_d_launched")),
            "human_eval_not_launched": not bool((result or {}).get("human_eval_launched")),
            "gate_v1_not_touched": not bool((result or {}).get("gate_v1_touched_by_runner")),
            "reward_defs_unchanged": not bool((result or {}).get("reward_definitions_changed")),
            "sigma_policy_unchanged": not bool((result or {}).get("sigma_policy_changed")),
            "prompt_splits_unchanged": not bool((result or {}).get("prompt_splits_changed")),
            "credit_units_unchanged": not bool((result or {}).get("credit_unit_definitions_changed")),
        }
        summary = {
            "method": method,
            "display": DISPLAY[method],
            "optimizer_rows": len(opt),
            "last_step": opt[-1].get("step") if opt else None,
            "expected_steps": args.expected_steps,
            "completed_expected_steps": len(opt) >= args.expected_steps,
            "parse_errors": parse_errors,
            "all_numeric_finite": finite,
            "last_step_reward_mean": last.get("reward_mean"),
            "last_step_reward_std": last.get("reward_std"),
            "final_loss": last.get("loss"),
            "final_kl_ref": last.get("kl_ref"),
            "final_ratio_mean": last.get("ratio_mean"),
            "final_ratio_std": last.get("ratio_std"),
            "final_grad_norm": last.get("grad_norm"),
            "adapter_updated_all_logs": checks["adapter_updated_all_logs"],
            "base_unchanged_all_logs": checks["base_unchanged_all_logs"],
            "zero_variance_groups": sum(int(r.get("zero_variance_groups") or 0) for r in curve_rows if r["method"] == method),
            "gpu_h_log_sum": gpu_h_log,
            "gpu_h_train_results": result_gpu_h,
            "elapsed_seconds_train_results": safe_float((result or {}).get("elapsed_seconds")),
            "checkpoint_count": len(checkpoints),
            "latest_checkpoint": checkpoints[-1].name if checkpoints else None,
            "train_results_exists": result is not None,
            "train_results_status": result_status,
            "train_results_error": result_error,
            "train_results_checkpoint_path": result_checkpoint,
            "anomaly_status": status_from_checks(checks),
        }
        summary_rows.append(summary)
        train_result_rows.append({
            "method": method,
            "display": DISPLAY[method],
            "exists": result is not None,
            "parse_error": result_error,
            "status": result_status,
            "method_id": (result or {}).get("method_id"),
            "reward_mode": (result or {}).get("reward_mode"),
            "steps_completed": (result or {}).get("steps_completed"),
            "gpu_hours_consumed": result_gpu_h,
            "elapsed_seconds": safe_float((result or {}).get("elapsed_seconds")),
            "checkpoint_path": result_checkpoint,
            "checkpoint_resume_ok": (result or {}).get("checkpoint_resume_ok"),
            "adapter_updated": (result or {}).get("adapter_updated"),
            "base_parameters_frozen": (result or {}).get("base_parameters_frozen"),
            "held_out_launched": (result or {}).get("held_out_launched"),
            "phase_d_launched": (result or {}).get("phase_d_launched"),
            "human_eval_launched": (result or {}).get("human_eval_launched"),
            "gate_v1_touched_by_runner": (result or {}).get("gate_v1_touched_by_runner"),
            "reward_definitions_changed": (result or {}).get("reward_definitions_changed"),
            "sigma_policy_changed": (result or {}).get("sigma_policy_changed"),
            "prompt_splits_changed": (result or {}).get("prompt_splits_changed"),
            "credit_unit_definitions_changed": (result or {}).get("credit_unit_definitions_changed"),
        })
        anomaly_rows.append({
            "method": method,
            "display": DISPLAY[method],
            "overall": status_from_checks(checks),
            **checks,
        })

        windows = [
            ("0-249", 0, 249),
            ("250-499", 250, 499),
            ("500-749", 500, 749),
            ("750-999", 750, 999),
            ("0-final", 0, args.expected_steps - 1),
        ]
        for label, start, stop in windows:
            window_rows.append(summarize_window(opt, method, label, start, stop))
        window_rows.append(summarize_named_rows(opt[-100:] if len(opt) >= 100 else opt, method, "last100_observed"))

    fixed_section_rows: list[dict[str, Any]] = []
    fixed = {r["step"]: r for r in curve_rows if r["method"] == "m_fixedwin"}
    section = {r["step"]: r for r in curve_rows if r["method"] == "m_section"}
    for step in sorted(set(fixed) & set(section)):
        f = fixed[step]
        s = section[step]
        fixed_section_rows.append({
            "step": step,
            "fixedwin_reward_mean": f.get("reward_mean"),
            "section_reward_mean": s.get("reward_mean"),
            "fixedwin_minus_section_reward_mean": (
                (f.get("reward_mean") - s.get("reward_mean"))
                if f.get("reward_mean") is not None and s.get("reward_mean") is not None else None
            ),
            "fixedwin_loss": f.get("loss"),
            "section_loss": s.get("loss"),
            "fixedwin_kl_ref": f.get("kl_ref"),
            "section_kl_ref": s.get("kl_ref"),
            "fixedwin_grad_norm": f.get("grad_norm"),
            "section_grad_norm": s.get("grad_norm"),
        })

    write_csv(args.out_dir / "completion_curves.csv", curve_rows)
    write_csv(args.out_dir / "completion_summary.csv", summary_rows)
    write_csv(args.out_dir / "completion_windows.csv", window_rows)
    write_csv(args.out_dir / "train_results_summary.csv", train_result_rows)
    write_csv(args.out_dir / "checkpoint_status.csv", checkpoint_rows)
    write_csv(args.out_dir / "anomaly_checks.csv", anomaly_rows)
    write_csv(args.out_dir / "fixedwin_section_stepwise.csv", fixed_section_rows)
    plot_paths = write_plots(args.out_dir, curve_rows)

    payload = {
        "generated_at_utc": now_utc(),
        "run_root": str(args.root),
        "expected_steps": args.expected_steps,
        "allow_incomplete": args.allow_incomplete,
        "summary": summary_rows,
        "train_results": train_result_rows,
        "windows": window_rows,
        "anomaly_checks": anomaly_rows,
        "plots": plot_paths,
        "interpretation_boundary": (
            "Completion training analysis only. Do not compare terminal and process scalar "
            "reward levels directly. No held-out, Phase D, or human eval is launched here."
        ),
    }
    (args.out_dir / "completion_analysis.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phase C1 Completion Analysis",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        f"Run root: `{args.root}`",
        "",
        f"Expected steps per method: `{args.expected_steps}`",
        "",
        "## Completion Summary",
        "",
        "| method | rows | last step | train_results | last-step reward | last-step loss | KL ref | ratio | grad | GPU-h log | GPU-h result | checkpoint | anomaly |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['display']} | {row['optimizer_rows']} | {row['last_step']} | "
            f"{row['train_results_status']} | {fmt(row['last_step_reward_mean'])} | {fmt(row['final_loss'])} | "
            f"{fmt(row['final_kl_ref'])} | {fmt(row['final_ratio_mean'])} | {fmt(row['final_grad_norm'])} | "
            f"{fmt(row['gpu_h_log_sum'])} | {fmt(row['gpu_h_train_results'])} | "
            f"`{row['latest_checkpoint']}` | {row['anomaly_status']} |"
        )
    lines.extend([
        "",
        "## Window Summary",
        "",
        "| method | window | n | reward mean | reward std | mean loss | max abs KL ref | mean ratio | max ratio std | grad min | grad max | sec/step | zero-var groups |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in window_rows:
        lines.append(
            f"| {row['display']} | {row['window']} | {row['n_steps']} | {fmt(row['reward_mean'])} | "
            f"{fmt(row['reward_std'])} | {fmt(row['mean_loss'])} | {fmt(row['max_abs_kl_ref'])} | "
            f"{fmt(row['mean_ratio_mean'])} | {fmt(row['max_ratio_std'])} | {fmt(row['min_grad_norm'])} | "
            f"{fmt(row['max_grad_norm'])} | {fmt(row['mean_sec_per_step'])} | {row['zero_variance_groups']} |"
        )
    lines.extend([
        "",
        "## Anomaly Checks",
        "",
        "| method | overall | reached expected steps | train_results PASS | finite JSON | adapter updated logs | base unchanged logs | zero-var groups zero | safety/definition flags ok |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for row in anomaly_rows:
        safety_ok = all(
            row[k] for k in (
                "held_out_not_launched",
                "phase_d_not_launched",
                "human_eval_not_launched",
                "gate_v1_not_touched",
                "reward_defs_unchanged",
                "sigma_policy_unchanged",
                "prompt_splits_unchanged",
                "credit_units_unchanged",
            )
        )
        lines.append(
            f"| {row['display']} | {row['overall']} | {row['reached_expected_steps']} | "
            f"{row['train_results_pass']} | {row['json_numeric_finite']} | {row['adapter_updated_all_logs']} | "
            f"{row['base_unchanged_all_logs']} | {row['zero_variance_groups_zero']} | {safety_ok} |"
        )
    lines.extend([
        "",
        "## Output Tables",
        "",
        f"- `{args.out_dir / 'completion_curves.csv'}`",
        f"- `{args.out_dir / 'completion_summary.csv'}`",
        f"- `{args.out_dir / 'completion_windows.csv'}`",
        f"- `{args.out_dir / 'train_results_summary.csv'}`",
        f"- `{args.out_dir / 'checkpoint_status.csv'}`",
        f"- `{args.out_dir / 'anomaly_checks.csv'}`",
        f"- `{args.out_dir / 'fixedwin_section_stepwise.csv'}`",
        "",
        "## Plots",
        "",
    ])
    lines.extend(f"- `{path}`" for path in plot_paths)
    lines.extend([
        "",
        "## Interpretation Boundary",
        "",
        "- This is a training completion analysis, not held-out evaluation.",
        "- Direct scalar rewards are not comparable between terminal and process objectives.",
        "- M-FixedWin and M-Section are the most direct scalar comparison pair, but shared downstream evaluation is still needed for final quality claims.",
    ])
    (args.out_dir / "completion_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out_dir": str(args.out_dir), "plots": plot_paths}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
