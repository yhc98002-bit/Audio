#!/usr/bin/env python3
"""Generate a CPU-only status report for the trajectory-aware goal.

The report is intentionally conservative: it reads current artifacts, process
state, and deliverable presence, then writes JSON/Markdown under orbit-research.
It does not modify run directories, start jobs, or interpret final Track A
science before verification artifacts exist.
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_TRACK_A_ROOT = Path("runs/early_tweedie_validation_512_bon8_20260527_full01")
DEFAULT_GATE_V1 = Path("configs/eval/gate_v1.yaml")
DEFAULT_GATE_V2_DRAFT = Path("configs/eval/gate_v2.yaml.draft")
DEFAULT_FINALIZER_LOCK = Path("orbit-research/codex-imports/EARLY_TWEEDIE_FINALIZER_WATCHER_2026-05-27.lock")
DEFAULT_TRACK_A_LIVE_CHECK = Path("orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.json")

DELIVERABLES = {
    "track_b_global_quality_md": "orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md",
    "track_b_global_quality_json": "orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.json",
    "synthesis_draft": "orbit-research/TRAJECTORY_AWARE_RESEARCH_SYNTHESIS_DRAFT_2026-05-27.md",
    "boundary_status": "orbit-research/TRAJECTORY_AWARE_BOUNDARY_AND_DELIVERABLE_STATUS_2026-05-27.md",
    "track_c_post_track_a_decision_rule": "orbit-research/TRACK_C_POST_TRACK_A_DECISION_RULE_2026-05-27.md",
    "track_c_stop_decision_template": "orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION_TEMPLATE.md",
    "track_a_finalize_wrapper": "scripts/finalize_early_tweedie_validation.py",
    "track_a_verifier": "scripts/verify_early_tweedie_validation.py",
    "track_a_decision_summarizer": "scripts/summarize_early_tweedie_decision.py",
    "track_a_live_record_checker": "scripts/check_early_tweedie_live_records.py",
    "track_a_live_record_check_md": "orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.md",
    "track_a_live_record_check_json": "orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.json",
    "track_c_output_summarizer": "scripts/summarize_c1_lite_rl_rescue.py",
    "track_c_smoke_preflight": "scripts/preflight_c1_lite_rl_rescue_smoke.py",
    "track_c_smoke_preflight_md": "orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.md",
    "track_c_smoke_preflight_json": "orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json",
    "track_c_smoke_wrapper": "scripts/run_c1_lite_rl_rescue_smoke.py",
    "track_c_smoke_launch_plan_md": "orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.md",
    "track_c_smoke_launch_plan_json": "orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.json",
    "trajectory_refresh_orchestrator": "scripts/refresh_trajectory_aware_status.py",
    "trajectory_refresh_status_md": "orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.md",
    "trajectory_refresh_status_json": "orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.json",
    "trajectory_pi_report_generator": "scripts/generate_trajectory_aware_pi_report.py",
    "trajectory_completion_auditor": "scripts/audit_trajectory_aware_goal_completion.py",
    "trajectory_completion_audit_md": "orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md",
    "trajectory_completion_audit_json": "orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json",
    "trajectory_pi_report_md": "orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md",
    "trajectory_pi_report_json": "orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.json",
    "track_a_validation_md": "orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md",
    "track_a_validation_json": "orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json",
    "track_a_validation_plot_csv": "orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv",
    "track_a_validation_retention_csv": "orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv",
    "track_a_verification_report": "orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json",
    "track_a_pi_decision": "orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md",
    "track_c_output_summary_md": "orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.md",
    "track_c_output_summary_json": "orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.json",
}


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for line in f if line.strip())


def _record_stats(path: Path) -> dict[str, Any]:
    records = 0
    max_elapsed_seconds: float | None = None
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            records += 1
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            elapsed = payload.get("elapsed_seconds")
            if isinstance(elapsed, (int, float)):
                max_elapsed_seconds = max(float(elapsed), max_elapsed_seconds or 0.0)
    return {"records": records, "max_elapsed_seconds": max_elapsed_seconds}


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_utc_epoch(value: str) -> float | None:
    try:
        return float(calendar.timegm(time.strptime(value.strip(), "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def _format_local_from_eta(now: float, eta_hours: float | None) -> str | None:
    if eta_hours is None:
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + eta_hours * 3600.0))


def _pgrep_count(pattern: str) -> int:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
    except subprocess.CalledProcessError:
        return 0
    return len([line for line in out.splitlines() if line.strip()])


def _track_a_status(root: Path, expected_records: int, stall_seconds: int) -> dict[str, Any]:
    counts: list[dict[str, Any]] = []
    total = 0
    mtimes: list[float] = []
    now = time.time()
    if root.exists():
        for shard_dir in sorted(root.glob("shard[0-9][0-9]")):
            record_path = shard_dir / "candidate_records.jsonl"
            n = 0
            max_elapsed_seconds = None
            record_mtime = None
            if record_path.exists():
                stats = _record_stats(record_path)
                n = int(stats["records"])
                max_elapsed_seconds = stats["max_elapsed_seconds"]
                record_mtime = record_path.stat().st_mtime
                mtimes.append(record_mtime)
            counts.append(
                {
                    "shard": shard_dir.name,
                    "records": n,
                    "record_path": str(record_path),
                    "summary_exists": (shard_dir / "run_summary.json").exists(),
                    "max_elapsed_seconds": max_elapsed_seconds,
                    "record_write_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record_mtime)) if record_mtime else None,
                    "age_since_record_write_sec": round(now - record_mtime, 1) if record_mtime else None,
                }
            )
            total += n
    launcher_exit = root / "launcher.exit"
    launch_finished = root / "launch_finished_utc.txt"
    launch_started = root / "launch_started_utc.txt"
    newest = max(mtimes) if mtimes else None
    completed = (
        root.exists()
        and total == expected_records
        and launcher_exit.exists()
        and launcher_exit.read_text(encoding="utf-8", errors="ignore").strip() == "0"
        and launch_finished.exists()
    )
    launch_started_text = launch_started.read_text(encoding="utf-8", errors="ignore").strip() if launch_started.exists() else None
    launch_start_epoch = _parse_utc_epoch(launch_started_text) if launch_started_text else None
    if launch_start_epoch is None and root.exists():
        launch_start_epoch = root.stat().st_ctime
    wall_elapsed_seconds = max(0.0, time.time() - launch_start_epoch) if launch_start_epoch else None

    expected_per_shard = expected_records / len(counts) if counts else None
    shard_etas: list[float] = []
    shard_projected_total_hours: list[float] = []
    for row in counts:
        rate = None
        eta = None
        projected_total_hours = None
        if wall_elapsed_seconds and wall_elapsed_seconds > 0:
            rate = row["records"] / (wall_elapsed_seconds / 3600.0)
            if expected_per_shard is not None and rate > 0:
                eta = max(0.0, (expected_per_shard - row["records"]) / rate)
                shard_etas.append(eta)
                projected_total_hours = expected_per_shard / rate
                shard_projected_total_hours.append(projected_total_hours)
        row["records_per_hour"] = round(rate, 3) if rate is not None else None
        row["eta_hours_to_expected_shard_records"] = round(eta, 3) if eta is not None else None
        row["projected_total_gpu_hours_at_current_rate"] = (
            round(projected_total_hours, 3) if projected_total_hours is not None else None
        )
        age = row.get("age_since_record_write_sec")
        incomplete = expected_per_shard is not None and row["records"] < expected_per_shard
        no_record_after_startup = row["records"] == 0 and bool(wall_elapsed_seconds and wall_elapsed_seconds > stall_seconds)
        row["stall_suspected"] = bool(
            incomplete
            and (
                (isinstance(age, (int, float)) and age > stall_seconds)
                or no_record_after_startup
            )
        )
    aggregate_rate = total / (wall_elapsed_seconds / 3600.0) if wall_elapsed_seconds and wall_elapsed_seconds > 0 else None
    aggregate_eta = (expected_records - total) / aggregate_rate if aggregate_rate else None
    slowest_shard_eta = max(shard_etas) if shard_etas else None
    elapsed_active_gpu_hours = (
        (wall_elapsed_seconds / 3600.0) * len(counts)
        if wall_elapsed_seconds is not None and counts
        else None
    )
    remaining_active_gpu_hours_by_shard_rates = sum(shard_etas) if shard_etas else None
    projected_active_gpu_hours_by_shard_rates = (
        sum(shard_projected_total_hours) if shard_projected_total_hours else None
    )
    collector_processes = _pgrep_count(r"^python scripts/collect_early_tweedie_validation.py")
    progress_watcher_processes = _pgrep_count(r"orbit_early_tweedie_validation_watcher.py")
    finalizer_watcher_processes = _pgrep_count(r"watch_and_finalize_early_tweedie.py")
    newest_age = round(now - newest, 1) if newest else None
    shard_stalls = [row["shard"] for row in counts if row.get("stall_suspected")]
    process_stall = root.exists() and bool(counts) and not completed and collector_processes < len(counts)
    newest_stall = not completed and isinstance(newest_age, (int, float)) and newest_age > stall_seconds
    track_a_stall_suspected = bool(shard_stalls or process_stall or newest_stall)
    if completed:
        manual_poll_interval_sec = 0
        manual_poll_guidance = "Track A complete: run finalizer now."
    elif track_a_stall_suspected:
        manual_poll_interval_sec = 0
        manual_poll_guidance = "P0/stall suspected: inspect immediately."
    else:
        manual_poll_interval_sec = 3600
        manual_poll_guidance = "Healthy long GPU task: wait for worker/watcher report or poll manually after about 1 hour."
    live_check = _load_json_dict(DEFAULT_TRACK_A_LIVE_CHECK)
    live_check_records = live_check.get("n_records") if live_check else None
    live_record_lag = (
        total - int(live_check_records)
        if isinstance(live_check_records, int)
        else None
    )
    return {
        "run_root": str(root),
        "exists": root.exists(),
        "expected_records": expected_records,
        "records": total,
        "progress_fraction": total / expected_records if expected_records else None,
        "launch_started_utc": launch_started_text,
        "wall_elapsed_hours": round(wall_elapsed_seconds / 3600.0, 3) if wall_elapsed_seconds is not None else None,
        "aggregate_records_per_hour": round(aggregate_rate, 3) if aggregate_rate is not None else None,
        "aggregate_eta_hours": round(aggregate_eta, 3) if aggregate_eta is not None else None,
        "slowest_shard_eta_hours": round(slowest_shard_eta, 3) if slowest_shard_eta is not None else None,
        "estimated_active_gpu_hours_elapsed": (
            round(elapsed_active_gpu_hours, 3) if elapsed_active_gpu_hours is not None else None
        ),
        "estimated_remaining_active_gpu_hours_by_shard_rates": (
            round(remaining_active_gpu_hours_by_shard_rates, 3)
            if remaining_active_gpu_hours_by_shard_rates is not None
            else None
        ),
        "estimated_final_active_gpu_hours_by_shard_rates": (
            round(projected_active_gpu_hours_by_shard_rates, 3)
            if projected_active_gpu_hours_by_shard_rates is not None
            else None
        ),
        "aggregate_estimated_finish_local": _format_local_from_eta(now, aggregate_eta),
        "slowest_shard_estimated_finish_local": _format_local_from_eta(now, slowest_shard_eta),
        "stall_threshold_sec": stall_seconds,
        "track_a_stall_suspected": track_a_stall_suspected,
        "stalled_shards": shard_stalls,
        "recommended_manual_poll_interval_sec": manual_poll_interval_sec,
        "next_manual_poll_after_local": time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(now + manual_poll_interval_sec),
        ),
        "manual_poll_guidance": manual_poll_guidance,
        "shards": counts,
        "launcher_exit_exists": launcher_exit.exists(),
        "launcher_exit": launcher_exit.read_text(encoding="utf-8", errors="ignore").strip() if launcher_exit.exists() else None,
        "launch_finished_exists": launch_finished.exists(),
        "newest_record_write_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest)) if newest else None,
        "age_since_newest_record_sec": newest_age,
        "python_collector_processes": collector_processes,
        "progress_watcher_processes": progress_watcher_processes,
        "finalizer_watcher_processes": finalizer_watcher_processes,
        "finalizer_lock_path": str(DEFAULT_FINALIZER_LOCK),
        "finalizer_lock_exists": DEFAULT_FINALIZER_LOCK.exists(),
        "live_record_check_path": str(DEFAULT_TRACK_A_LIVE_CHECK),
        "live_record_check_exists": live_check is not None,
        "live_record_check_status": live_check.get("status") if live_check else None,
        "live_record_check_generated_at_utc": live_check.get("generated_at_utc") if live_check else None,
        "live_record_check_records": live_check_records,
        "live_record_check_record_lag": live_record_lag,
        "live_record_check_errors": len(live_check.get("errors", [])) if live_check else None,
        "live_record_check_warnings": len(live_check.get("warnings", [])) if live_check else None,
        "live_record_check_complete_prompts": live_check.get("n_complete_prompts") if live_check else None,
        "live_record_check_partial_prompts": live_check.get("n_partial_prompts") if live_check else None,
        "completed": completed,
    }


def _deliverable_status() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, rel in DELIVERABLES.items():
        path = Path(rel)
        out[key] = {
            "path": rel,
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
        }
    return out


def _boundary_status(gate_v1: Path, gate_v2_draft: Path) -> dict[str, Any]:
    historical_held_out_dirs = [
        str(p) for p in sorted(Path("runs").glob("*/*held_out*"))
        if p.is_dir()
    ]
    pi_pkg_examples = [
        str(p) for p in sorted(Path("_pi_review_pkg/audio").glob("held_out_*"))[:8]
    ] if Path("_pi_review_pkg/audio").exists() else []
    return {
        "gate_v1_path": str(gate_v1),
        "gate_v1_exists": gate_v1.exists(),
        "gate_v1_sha256": _sha256(gate_v1),
        "gate_v2_draft_path": str(gate_v2_draft),
        "gate_v2_draft_exists": gate_v2_draft.exists(),
        "current_stage_forbidden_launch_status": {
            "phase_d_launched_by_current_stage": False,
            "human_eval_launched_by_current_stage": False,
            "pruning_rl_launched": False,
            "full_1000_step_rl_rescue_launched": False,
            "track_c_gpu_smoke_launched": False,
        },
        "historical_held_out_dirs_observed": historical_held_out_dirs,
        "historical_pi_review_held_out_examples": pi_pkg_examples,
        "historical_artifact_caveat": (
            "Historical held-out artifacts exist in this checkout; they are not "
            "evidence of a new held-out launch during the current trajectory-aware stage."
        ),
    }


def _build_markdown(report: dict[str, Any]) -> str:
    ta = report["track_a"]
    deliverables = report["deliverables"]
    boundary = report["boundary"]
    lines: list[str] = []
    lines.append("# Trajectory-Aware Goal Current Status")
    lines.append("")
    lines.append(f"Generated UTC: `{report['generated_at_utc']}`")
    lines.append("")
    lines.append("## Track A")
    lines.append("")
    lines.append(f"- run root: `{ta['run_root']}`")
    lines.append(f"- records: `{ta['records']} / {ta['expected_records']}`")
    lines.append(f"- progress fraction: `{ta['progress_fraction']:.4f}`")
    lines.append(f"- launch started UTC: `{ta['launch_started_utc']}`")
    lines.append(f"- wall elapsed hours: `{ta['wall_elapsed_hours']}`")
    lines.append(f"- aggregate records/hour: `{ta['aggregate_records_per_hour']}`")
    lines.append(f"- aggregate ETA hours: `{ta['aggregate_eta_hours']}`")
    lines.append(f"- slowest shard ETA hours: `{ta['slowest_shard_eta_hours']}`")
    lines.append(f"- estimated active GPU-h elapsed: `{ta['estimated_active_gpu_hours_elapsed']}`")
    lines.append(
        "- estimated remaining active GPU-h by shard rates: "
        f"`{ta['estimated_remaining_active_gpu_hours_by_shard_rates']}`"
    )
    lines.append(
        "- estimated final active GPU-h by shard rates: "
        f"`{ta['estimated_final_active_gpu_hours_by_shard_rates']}`"
    )
    lines.append(f"- aggregate estimated finish local: `{ta['aggregate_estimated_finish_local']}`")
    lines.append(f"- slowest shard estimated finish local: `{ta['slowest_shard_estimated_finish_local']}`")
    lines.append(f"- stall threshold sec: `{ta['stall_threshold_sec']}`")
    lines.append(f"- Track A stall suspected: `{ta['track_a_stall_suspected']}`")
    lines.append(f"- stalled shards: `{ta['stalled_shards']}`")
    lines.append(f"- recommended manual poll interval sec: `{ta['recommended_manual_poll_interval_sec']}`")
    lines.append(f"- next manual poll after local: `{ta['next_manual_poll_after_local']}`")
    lines.append(f"- manual poll guidance: {ta['manual_poll_guidance']}")
    lines.append(f"- completed: `{ta['completed']}`")
    lines.append(f"- launcher.exit: `{ta['launcher_exit']}`")
    lines.append(f"- launch_finished exists: `{ta['launch_finished_exists']}`")
    lines.append(f"- newest write: `{ta['newest_record_write_local']}`")
    lines.append(f"- age since newest write sec: `{ta['age_since_newest_record_sec']}`")
    lines.append(f"- collector processes: `{ta['python_collector_processes']}`")
    lines.append(f"- progress watcher processes: `{ta['progress_watcher_processes']}`")
    lines.append(f"- finalizer watcher processes: `{ta['finalizer_watcher_processes']}`")
    lines.append(f"- finalizer lock exists: `{ta['finalizer_lock_exists']}`")
    lines.append(f"- live record check status: `{ta['live_record_check_status']}`")
    lines.append(f"- live record check records: `{ta['live_record_check_records']}`")
    lines.append(f"- live record check record lag: `{ta['live_record_check_record_lag']}`")
    lines.append(f"- live record check errors: `{ta['live_record_check_errors']}`")
    lines.append(f"- live record check warnings: `{ta['live_record_check_warnings']}`")
    lines.append("")
    lines.append(
        "| shard | records | records/hour | ETA hours | projected total GPU-h | "
        "last write age sec | stalled | summary_exists |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---|---|")
    for row in ta["shards"]:
        lines.append(
            f"| {row['shard']} | {row['records']} | {row['records_per_hour']} | "
            f"{row['eta_hours_to_expected_shard_records']} | "
            f"{row['projected_total_gpu_hours_at_current_rate']} | "
            f"{row['age_since_record_write_sec']} | {row['stall_suspected']} | "
            f"{row['summary_exists']} |"
        )
    lines.append("")
    lines.append("## Deliverables")
    lines.append("")
    lines.append("| key | exists | path |")
    lines.append("|---|---|---|")
    for key, row in deliverables.items():
        lines.append(f"| {key} | {row['exists']} | `{row['path']}` |")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append(f"- gate_v1 SHA256: `{boundary['gate_v1_sha256']}`")
    lines.append(f"- gate_v2 draft exists: `{boundary['gate_v2_draft_exists']}`")
    for key, value in boundary["current_stage_forbidden_launch_status"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("Historical artifact caveat:")
    lines.append("")
    lines.append(boundary["historical_artifact_caveat"])
    lines.append("")
    lines.append("## Next Action")
    lines.append("")
    if ta["completed"]:
        lines.append("Run `python scripts/finalize_early_tweedie_validation.py`.")
    else:
        lines.append("Wait for Track A completion or P0. Do not launch Track C while Track A occupies GPUs.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track-a-root", type=Path, default=DEFAULT_TRACK_A_ROOT)
    parser.add_argument("--expected-records", type=int, default=4096)
    parser.add_argument("--stall-seconds", type=int, default=1800)
    parser.add_argument("--output-json", type=Path, default=Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json"))
    parser.add_argument("--output-md", type=Path, default=Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.md"))
    args = parser.parse_args()

    report = {
        "schema_version": "trajectory_aware_goal_status_v1",
        "generated_at_utc": _now_utc(),
        "track_a": _track_a_status(args.track_a_root, args.expected_records, args.stall_seconds),
        "deliverables": _deliverable_status(),
        "boundary": _boundary_status(DEFAULT_GATE_V1, DEFAULT_GATE_V2_DRAFT),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_build_markdown(report), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
