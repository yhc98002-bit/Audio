"""CPU-only Phase C1 step250 decision-checkpoint analyzer."""
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


def read_rows(path: Path) -> tuple[list[dict[str, Any]], int, bool]:
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


def extract_reward_values(row: dict[str, Any]) -> list[float]:
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


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def pstdev(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def summarize_window(rows: list[dict[str, Any]], label: str, method: str, start: int, stop: int) -> dict[str, Any]:
    win = [r for r in rows if start <= int(r.get("step", -1)) <= stop]
    rewards: list[float] = []
    reward_std: list[float] = []
    loss: list[float] = []
    kl_ref: list[float] = []
    ratio_mean: list[float] = []
    ratio_std: list[float] = []
    grad: list[float] = []
    elapsed: list[float] = []
    zero_variance = 0
    for row in win:
        rewards.extend(extract_reward_values(row))
        v = safe_float(row.get("reward_std"))
        if v is not None:
            reward_std.append(v)
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
        "window": label,
        "n_steps": len(win),
        "reward_mean": mean(rewards),
        "reward_std": pstdev(rewards),
        "mean_step_reward_std": mean(reward_std),
        "mean_loss": mean(loss),
        "max_abs_kl_ref": max((abs(x) for x in kl_ref), default=None),
        "mean_ratio_mean": mean(ratio_mean),
        "max_ratio_std": max(ratio_std, default=None),
        "min_grad_norm": min(grad) if grad else None,
        "max_grad_norm": max(grad) if grad else None,
        "mean_sec_per_step": mean(elapsed),
        "zero_variance_groups": zero_variance,
    }


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


def write_plots(out_dir: Path, rows: list[dict[str, Any]]) -> list[str]:
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
    ]
    for key, title in metrics:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        has = False
        for method in METHODS:
            xs = [int(r["step"]) for r in rows if r["method"] == method and safe_float(r.get(key)) is not None]
            ys = [safe_float(r.get(key)) for r in rows if r["method"] == method and safe_float(r.get(key)) is not None]
            if xs and ys:
                has = True
                ax.plot(xs, ys, linewidth=1.2, label=DISPLAY[method])
        if not has:
            plt.close(fig)
            continue
        ax.set_title(title)
        ax.set_xlabel("optimizer step, truncated to 0-249")
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
    ap.add_argument("--truncate-steps", type=int, default=250)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    curve_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    current_rows: list[dict[str, Any]] = []

    for method in METHODS:
        method_dir = args.root / method
        rows, parse_errors, finite = read_rows(method_dir / "train_log.jsonl")
        opt = [r for r in rows if r.get("event") == "optimizer_step"]
        truncated = opt[: args.truncate_steps]
        if len(truncated) < args.truncate_steps:
            raise RuntimeError(f"{method}: only {len(truncated)} optimizer rows, need {args.truncate_steps}")
        for ckpt in sorted(method_dir.glob("checkpoint_step_*.pt")):
            checkpoint_rows.append({"method": method, "checkpoint": str(ckpt), "exists": ckpt.exists()})
        for row in truncated:
            metrics = row.get("update_metrics") or {}
            ratio = metrics.get("ratio") or {}
            rewards = extract_reward_values(row)
            curve_rows.append({
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
            })
        for label, start, stop in (("0-99", 0, 99), ("100-249", 100, 249), ("0-249", 0, 249)):
            window_rows.append(summarize_window(truncated, label, method, start, stop))
        last = curve_rows[-1]
        current_last = opt[-1]
        current_recent = [safe_float(r.get("elapsed_seconds")) for r in opt[-20:]]
        current_recent = [x for x in current_recent if x is not None]
        summary_rows.append({
            "method": method,
            "display": DISPLAY[method],
            "optimizer_rows_current": len(opt),
            "last_step_current": current_last.get("step"),
            "step250_log_step": truncated[-1].get("step"),
            "parse_errors": parse_errors,
            "all_numeric_finite": finite,
            "step250_reward_mean": last.get("reward_mean"),
            "step250_reward_std": last.get("reward_std"),
            "step250_loss": last.get("loss"),
            "step250_kl_ref": last.get("kl_ref"),
            "step250_ratio_mean": last.get("ratio_mean"),
            "step250_ratio_std": last.get("ratio_std"),
            "step250_grad_norm": last.get("grad_norm"),
            "adapter_updated_all_250": all(r.get("adapter_updated") is True for r in curve_rows if r["method"] == method),
            "base_unchanged_all_250": all(r.get("base_unchanged") is True for r in curve_rows if r["method"] == method),
            "zero_variance_groups_250": sum(int(r.get("zero_variance_groups") or 0) for r in curve_rows if r["method"] == method),
            "gpu_h_step250": sum((r.get("gpu_hours_consumed") or 0.0) for r in curve_rows if r["method"] == method),
            "gpu_h_current": sum((safe_float(r.get("gpu_hours_consumed")) or 0.0) for r in opt),
            "recent20_mean_sec": mean(current_recent),
            "checkpoints": ";".join(p.name for p in sorted(method_dir.glob("checkpoint_step_*.pt"))),
        })
        current_rows.append({
            "method": method,
            "optimizer_rows_current": len(opt),
            "last_step_current": current_last.get("step"),
            "recent20_mean_sec": mean(current_recent),
            "gpu_h_current": summary_rows[-1]["gpu_h_current"],
        })

    write_csv(args.out_dir / "step250_curves.csv", curve_rows)
    write_csv(args.out_dir / "step250_summary.csv", summary_rows)
    write_csv(args.out_dir / "step250_windows.csv", window_rows)
    write_csv(args.out_dir / "checkpoint_status.csv", checkpoint_rows)
    plot_paths = write_plots(args.out_dir, curve_rows)

    by_method = {row["method"]: row for row in summary_rows}
    now_by_method = {row["method"]: row for row in current_rows}
    eta_rows: list[dict[str, Any]] = []
    for target in (500, 1000):
        wall_remaining = 0.0
        active_gpu_h = 0.0
        for method, row in now_by_method.items():
            done = int(row["optimizer_rows_current"])
            remain = max(0, target - done)
            mean_sec = row.get("recent20_mean_sec") or by_method[method].get("recent20_mean_sec") or 0.0
            seconds = remain * mean_sec
            wall_remaining = max(wall_remaining, seconds)
            active_gpu_h += seconds / 3600.0
        eta_rows.append({
            "target_step": target,
            "remaining_wall_h": wall_remaining / 3600.0,
            "remaining_active_gpu_h": active_gpu_h,
        })
    write_csv(args.out_dir / "eta.csv", eta_rows)

    payload = {
        "generated_at_utc": now_utc(),
        "run_root": str(args.root),
        "truncate_steps": args.truncate_steps,
        "summary": summary_rows,
        "windows": window_rows,
        "eta": eta_rows,
        "plots": plot_paths,
        "interpretation_boundary": "training checkpoint only; not held-out, Phase D, or human eval",
    }
    (args.out_dir / "step250_analysis.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Phase C1 Step250 Analysis",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        f"Run root: `{args.root}`",
        "",
        "All method metrics below are truncated to the first 250 optimizer rows for comparability.",
        "",
        "## Summary",
        "",
        "| method | current rows | step250 step | reward_mean | reward_std | loss | KL ref | ratio_mean | grad_norm | step250 GPU-h | current GPU-h | adapter all | base all | zero-var groups |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['display']} | {row['optimizer_rows_current']} | {row['step250_log_step']} | "
            f"{fmt(row['step250_reward_mean'])} | {fmt(row['step250_reward_std'])} | "
            f"{fmt(row['step250_loss'])} | {fmt(row['step250_kl_ref'])} | "
            f"{fmt(row['step250_ratio_mean'])} | {fmt(row['step250_grad_norm'])} | "
            f"{fmt(row['gpu_h_step250'])} | {fmt(row['gpu_h_current'])} | "
            f"{row['adapter_updated_all_250']} | {row['base_unchanged_all_250']} | {row['zero_variance_groups_250']} |"
        )
    lines.extend([
        "",
        "## Windows",
        "",
        "| method | window | n | reward_mean | reward_std | mean_loss | max_abs_KL_ref | mean_ratio | max_ratio_std | grad_min | grad_max | sec/step |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in window_rows:
        if row["window"] == "0-249":
            continue
        lines.append(
            f"| {DISPLAY[row['method']]} | {row['window']} | {row['n_steps']} | "
            f"{fmt(row['reward_mean'])} | {fmt(row['reward_std'])} | {fmt(row['mean_loss'])} | "
            f"{fmt(row['max_abs_kl_ref'])} | {fmt(row['mean_ratio_mean'])} | {fmt(row['max_ratio_std'])} | "
            f"{fmt(row['min_grad_norm'])} | {fmt(row['max_grad_norm'])} | {fmt(row['mean_sec_per_step'])} |"
        )
    lines.extend([
        "",
        "## ETA",
        "",
        "| target | remaining wall h | remaining active GPU-h |",
        "|---:|---:|---:|",
    ])
    for row in eta_rows:
        lines.append(f"| {row['target_step']} | {fmt(row['remaining_wall_h'])} | {fmt(row['remaining_active_gpu_h'])} |")
    lines.extend([
        "",
        "## Plots",
        "",
    ])
    lines.extend(f"- `{path}`" for path in plot_paths)
    lines.extend([
        "",
        "## Interpretation Notes",
        "",
        "- Direct scalar rewards are not on one shared scale across terminal and process-reward methods.",
        "- M-FixedWin and M-Section are more directly comparable than process methods versus R8a/R8b.",
        "- This report is a training checkpoint only; no held-out, Phase D, or human evaluation was run.",
    ])
    (args.out_dir / "step250_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out_dir": str(args.out_dir), "plots": plot_paths}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
