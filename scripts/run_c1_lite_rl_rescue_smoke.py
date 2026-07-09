#!/usr/bin/env python3
"""Guarded wrapper for the future Track C C1-lite smoke.

Default behavior is dry-run only: refresh the smoke preflight, write a launch
plan, and exit without starting GPU work. Actual execution requires both
``--execute`` and ``--pi-go``, and the preflight must report READY.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_PREFLIGHT_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json")
DEFAULT_PREFLIGHT_MD = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.md")
DEFAULT_OUTPUT_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.json")
DEFAULT_OUTPUT_MD = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.md")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _refresh_preflight(args: argparse.Namespace) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "scripts/preflight_c1_lite_rl_rescue_smoke.py",
        "--setting",
        args.setting,
        "--output-json",
        str(args.preflight_json),
        "--output-md",
        str(args.preflight_md),
    ]
    if args.pi_go:
        cmd.append("--pi-go")
    subprocess.run(cmd, check=True)
    return _load_json(args.preflight_json)


def _normalize_command(command: list[str]) -> list[str]:
    if not command:
        raise RuntimeError("preflight did not provide future_runner_command")
    normalized = list(command)
    if normalized[0] in {"python", "python3"}:
        normalized[0] = sys.executable
    return normalized


def _build_plan(args: argparse.Namespace, preflight: dict[str, Any]) -> dict[str, Any]:
    command = _normalize_command(preflight.get("future_runner_command") or [])
    ready = preflight.get("status") == "READY"
    blockers = [row.get("name") for row in preflight.get("blockers", [])]
    execute_allowed = bool(args.execute and args.pi_go and ready)
    status = "READY_TO_EXECUTE" if execute_allowed else "DRY_RUN_OR_NOT_READY"
    if args.execute and not execute_allowed:
        status = "REFUSE_EXECUTE"
    return {
        "schema_version": "c1_lite_rl_rescue_smoke_launch_plan_v1",
        "generated_at_utc": _now_utc(),
        "status": status,
        "setting": args.setting,
        "execute_requested": bool(args.execute),
        "pi_go": bool(args.pi_go),
        "preflight_status": preflight.get("status"),
        "preflight_blockers": blockers,
        "preflight_json": str(args.preflight_json),
        "preflight_md": str(args.preflight_md),
        "future_run_root": preflight.get("future_run_root"),
        "bundle_path": preflight.get("bundle_path"),
        "command": command,
        "gpu_jobs_launched": 0,
        "hard_boundaries": {
            "held_out": False,
            "phase_d": False,
            "human_eval": False,
            "pruning_rl": False,
            "full_1000_step_rl": False,
        },
    }


def _markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# C1-Lite RL Rescue Smoke Launch Plan",
        "",
        f"Generated UTC: `{plan['generated_at_utc']}`",
        f"Status: `{plan['status']}`",
        f"Setting: `{plan['setting']}`",
        f"Execute requested: `{plan['execute_requested']}`",
        f"PI/researcher GO: `{plan['pi_go']}`",
        f"Preflight status: `{plan['preflight_status']}`",
        f"Preflight blockers: `{plan['preflight_blockers']}`",
        f"GPU jobs launched: `{plan['gpu_jobs_launched']}`",
        "",
        "## Command",
        "",
        "```bash",
        " ".join(str(x) for x in plan["command"]),
        "```",
        "",
        "## Interpretation",
        "",
    ]
    if plan["status"] == "READY_TO_EXECUTE":
        lines.append("The wrapper may execute this command because explicit GO is present and the preflight is READY.")
    elif plan["status"] == "REFUSE_EXECUTE":
        lines.append("Execution was requested but refused because GO and/or preflight readiness is missing.")
    else:
        lines.append("Dry-run only. No GPU job was launched.")
    lines.append("This wrapper does not authorize held-out, Phase D, human eval, pruning+RL, or full 1000-step RL.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setting", default="r8b_baseline_instrumented")
    parser.add_argument("--preflight-json", type=Path, default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--preflight-md", type=Path, default=DEFAULT_PREFLIGHT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--pi-go", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Actually run the smoke command if preflight is READY.")
    parser.add_argument("--require-ready", action="store_true", help="Exit nonzero unless the plan is ready to execute.")
    args = parser.parse_args()

    preflight = _refresh_preflight(args)
    plan = _build_plan(args, preflight)
    _write_json(args.output_json, plan)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(plan), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)

    if args.require_ready and plan["status"] != "READY_TO_EXECUTE":
        return 2
    if args.execute:
        if plan["status"] != "READY_TO_EXECUTE":
            return 2
        command = [str(x) for x in plan["command"]]
        subprocess.run(command, check=True)
        plan["status"] = "EXECUTED"
        plan["gpu_jobs_launched"] = 1
        plan["executed_at_utc"] = _now_utc()
        _write_json(args.output_json, plan)
        args.output_md.write_text(_markdown(plan), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
