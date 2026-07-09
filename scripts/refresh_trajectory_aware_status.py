#!/usr/bin/env python3
"""Refresh all trajectory-aware status artifacts in a safe CPU-only sequence.

This script is a polling convenience wrapper. It does not launch GPU work and
has no execute mode. It refreshes:

1. Track A live record check.
2. Completion audit plus Track A status.
3. Track C smoke preflight and dry-run launch plan.
4. Current PI report.
"""

from __future__ import annotations

import argparse
import calendar
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_JSON = Path("orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.json")
DEFAULT_OUTPUT_MD = Path("orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.md")
DEFAULT_GOAL_STATUS_JSON = Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json")
DEFAULT_AUDIT_JSON = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json")
DEFAULT_PREFLIGHT_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json")
DEFAULT_LAUNCH_PLAN_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.json")
DEFAULT_PI_REPORT_JSON = Path("orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.json")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_utc(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(calendar.timegm(time.strptime(value.strip(), "%Y-%m-%dT%H:%M:%SZ")))
    except ValueError:
        return None


def _run(cmd: list[str]) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip().splitlines(),
        "stderr": proc.stderr.strip().splitlines(),
        "duration_sec": round(time.time() - started, 3),
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Trajectory-Aware Refresh Status",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Status: `{report['status']}`",
        f"GPU jobs launched: `{report['gpu_jobs_launched']}`",
        "",
        "## Current Snapshot",
        "",
        f"- Track A records: `{report['track_a_records']} / {report['track_a_expected_records']}`",
        f"- Track A completed: `{report['track_a_completed']}`",
        f"- Track A stall suspected: `{report['track_a_stall_suspected']}`",
        f"- live record check: `{report['live_record_check_status']}`",
        f"- live record check lag: `{report['live_record_check_record_lag']}`",
        f"- completion audit: `{report['completion_audit_status']}`",
        f"- PI report: `{report['pi_report_status']}`",
        f"- Track C preflight: `{report['track_c_preflight_status']}`",
        f"- Track C launch plan: `{report['track_c_launch_plan_status']}`",
        "",
        "## Commands",
        "",
        "| command | rc | duration_sec |",
        "|---|---:|---:|",
    ]
    for row in report["commands"]:
        lines.append(f"| `{' '.join(row['cmd'])}` | {row['returncode']} | {row['duration_sec']} |")
    lines.extend(["", "## Notes", ""])
    if report["status"] == "PASS":
        lines.append("All refresh commands completed successfully.")
    elif report["status"] == "SKIPPED_TOO_SOON":
        lines.append("Refresh skipped because Track A is healthy and the recommended manual poll interval has not elapsed.")
        lines.append(f"Next manual poll after local: `{report.get('next_manual_poll_after_local')}`")
    else:
        lines.append("At least one refresh command failed; inspect JSON stderr/stdout entries.")
    lines.append("This script is CPU-only and has no GPU execution mode.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument(
        "--respect-manual-poll-interval",
        action="store_true",
        help="Skip refresh while the existing Track A status is healthy and before its next recommended manual poll time.",
    )
    args = parser.parse_args()

    if args.respect_manual_poll_interval and DEFAULT_GOAL_STATUS_JSON.exists():
        previous = _load_json(DEFAULT_GOAL_STATUS_JSON)
        track_a = previous.get("track_a") or {}
        interval = track_a.get("recommended_manual_poll_interval_sec")
        generated_at = _parse_utc(previous.get("generated_at_utc"))
        completed = track_a.get("completed") is True
        stalled = track_a.get("track_a_stall_suspected") is True
        if (
            isinstance(interval, int)
            and interval > 0
            and generated_at is not None
            and not completed
            and not stalled
            and time.time() < generated_at + interval
        ):
            audit_json = _load_json_optional(DEFAULT_AUDIT_JSON)
            preflight_json = _load_json_optional(DEFAULT_PREFLIGHT_JSON)
            launch_json = _load_json_optional(DEFAULT_LAUNCH_PLAN_JSON)
            pi_json = _load_json_optional(DEFAULT_PI_REPORT_JSON)
            report = {
                "schema_version": "trajectory_aware_refresh_status_v1",
                "generated_at_utc": _now_utc(),
                "status": "SKIPPED_TOO_SOON",
                "gpu_jobs_launched": 0,
                "commands": [],
                "track_a_records": track_a.get("records"),
                "track_a_expected_records": track_a.get("expected_records"),
                "track_a_completed": completed,
                "track_a_stall_suspected": stalled,
                "live_record_check_status": track_a.get("live_record_check_status"),
                "live_record_check_record_lag": track_a.get("live_record_check_record_lag"),
                "completion_audit_status": audit_json.get("overall_status"),
                "pi_report_status": pi_json.get("overall_status"),
                "track_c_preflight_status": preflight_json.get("status"),
                "track_c_launch_plan_status": launch_json.get("status"),
                "track_c_preflight_gpu_jobs_launched": preflight_json.get("gpu_jobs_launched"),
                "track_c_launch_plan_gpu_jobs_launched": launch_json.get("gpu_jobs_launched"),
                "respect_manual_poll_interval": True,
                "seconds_until_next_manual_poll": round(generated_at + interval - time.time(), 1),
                "next_manual_poll_after_local": track_a.get("next_manual_poll_after_local"),
                "manual_poll_guidance": track_a.get("manual_poll_guidance"),
                "previous_status_generated_at_utc": previous.get("generated_at_utc"),
            }
            _write_json(args.output_json, report)
            args.output_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_md.write_text(_markdown(report), encoding="utf-8")
            print(args.output_json)
            print(args.output_md)
            return 0

    commands = [
        [sys.executable, "scripts/check_early_tweedie_live_records.py"],
        [sys.executable, "scripts/audit_trajectory_aware_goal_completion.py", "--refresh-status"],
        [sys.executable, "scripts/run_c1_lite_rl_rescue_smoke.py"],
        [sys.executable, "scripts/generate_trajectory_aware_pi_report.py"],
    ]
    results = [_run(cmd) for cmd in commands]
    status_json = _load_json(Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json"))
    live_json = _load_json(Path("orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.json"))
    audit_json = _load_json(Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json"))
    preflight_json = _load_json(Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json"))
    launch_json = _load_json(Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.json"))
    pi_json = _load_json(Path("orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.json"))
    track_a = status_json.get("track_a") or {}
    report = {
        "schema_version": "trajectory_aware_refresh_status_v1",
        "generated_at_utc": _now_utc(),
        "status": "PASS" if all(row["returncode"] == 0 for row in results) else "FAIL",
        "gpu_jobs_launched": 0,
        "commands": results,
        "track_a_records": track_a.get("records"),
        "track_a_expected_records": track_a.get("expected_records"),
        "track_a_completed": track_a.get("completed"),
        "track_a_stall_suspected": track_a.get("track_a_stall_suspected"),
        "live_record_check_status": live_json.get("status"),
        "live_record_check_record_lag": track_a.get("live_record_check_record_lag"),
        "completion_audit_status": audit_json.get("overall_status"),
        "pi_report_status": pi_json.get("overall_status"),
        "track_c_preflight_status": preflight_json.get("status"),
        "track_c_launch_plan_status": launch_json.get("status"),
    }
    _write_json(args.output_json, report)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(report), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
