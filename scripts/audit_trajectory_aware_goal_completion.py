#!/usr/bin/env python3
"""Audit whether the trajectory-aware pivot goal is actually complete.

This script is CPU-only and read-only except for its own report outputs. It
checks concrete artifacts for the current objective:

- robust Track A Early-Tweedie validation and independent verification;
- completed Track B global-quality analysis;
- bounded Track C rescue opportunity, either summarized from a future run or
  explicitly stopped by PI/researcher decision;
- hard-boundary evidence from the current status report.

It deliberately treats missing or indirect evidence as not complete.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EXPECTED_GATE_V1_SHA256 = "43a306753583f03563c792ac9399bb1e30b0525c98c902a1e18756d54e25b3c6"

DEFAULT_STATUS_JSON = Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json")
DEFAULT_OUTPUT_JSON = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json")
DEFAULT_OUTPUT_MD = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md")

TRACK_A_OUTPUTS = [
    Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md"),
    Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json"),
    Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv"),
    Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv"),
]
TRACK_A_VERIFICATION = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json")
TRACK_A_PI_DECISION = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md")

TRACK_B_OUTPUTS = [
    Path("orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md"),
    Path("orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.json"),
]

TRACK_C_SUMMARY_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.json")
TRACK_C_SUMMARY_MD = Path("orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.md")
TRACK_C_STOP_DECISIONS = [
    Path("orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md"),
    Path("orbit-research/TRAJECTORY_AWARE_RL_RESCUE_STOP_DECISION.md"),
]


def _exists_all(paths: list[Path]) -> bool:
    return all(path.exists() and path.stat().st_size > 0 for path in paths)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _row(
    requirement: str,
    status: str,
    evidence: str,
    details: str,
) -> dict[str, str]:
    return {
        "requirement": requirement,
        "status": status,
        "evidence": evidence,
        "details": details,
    }


def _audit_track_a_completion(status: dict[str, Any]) -> dict[str, str]:
    track_a = status.get("track_a") or {}
    run_complete = track_a.get("completed") is True
    outputs_exist = _exists_all(TRACK_A_OUTPUTS)
    records = track_a.get("records")
    expected = track_a.get("expected_records")
    if run_complete and outputs_exist:
        state = "COMPLETE"
    elif track_a.get("launcher_exit") not in (None, "0"):
        state = "FAIL"
    else:
        state = "PENDING"
    return _row(
        "Track A robust Early-Tweedie validation completed",
        state,
        ", ".join(str(path) for path in TRACK_A_OUTPUTS),
        (
            f"run_completed={run_complete}; records={records}/{expected}; "
            f"launcher_exit={track_a.get('launcher_exit')}; outputs_exist={outputs_exist}"
        ),
    )


def _audit_track_a_verification() -> dict[str, str]:
    report = _load_json(TRACK_A_VERIFICATION)
    if report is None:
        return _row(
            "Track A independent verification passed",
            "PENDING",
            str(TRACK_A_VERIFICATION),
            "verification report is missing or not valid JSON",
        )
    status = str(report.get("status", "UNKNOWN"))
    errors = report.get("errors") or []
    passed = status in {"PASS", "PASS_WITH_WARNINGS"} and not errors
    return _row(
        "Track A independent verification passed",
        "COMPLETE" if passed else "FAIL",
        str(TRACK_A_VERIFICATION),
        f"verifier_status={status}; error_count={len(errors)}",
    )


def _audit_track_a_decision() -> dict[str, str]:
    if not TRACK_A_PI_DECISION.exists() or TRACK_A_PI_DECISION.stat().st_size == 0:
        return _row(
            "Track A PI decision memo produced",
            "PENDING",
            str(TRACK_A_PI_DECISION),
            "PI decision memo is missing",
        )
    text = TRACK_A_PI_DECISION.read_text(encoding="utf-8", errors="ignore")
    has_decision = "Decision status:" in text and "Verifier status:" in text
    return _row(
        "Track A PI decision memo produced",
        "COMPLETE" if has_decision else "FAIL",
        str(TRACK_A_PI_DECISION),
        f"decision_fields_present={has_decision}",
    )


def _audit_track_b() -> dict[str, str]:
    data = _load_json(TRACK_B_OUTPUTS[1])
    complete = _exists_all(TRACK_B_OUTPUTS) and data is not None and data.get("status") == "COMPLETE_CPU_ONLY"
    return _row(
        "Track B global-quality structure analysis completed",
        "COMPLETE" if complete else "PENDING",
        ", ".join(str(path) for path in TRACK_B_OUTPUTS),
        f"json_status={data.get('status') if data else None}",
    )


def _audit_track_c() -> dict[str, str]:
    summary = _load_json(TRACK_C_SUMMARY_JSON)
    if summary is not None and TRACK_C_SUMMARY_MD.exists():
        status = str(summary.get("status", "UNKNOWN"))
        ok = status in {"PASS", "PASS_WITH_WARNINGS", "COMPLETE", "STOPPED_AFTER_SMOKE", "NO_MEANINGFUL_SIGNAL"}
        return _row(
            "Track C bounded rescue opportunity resolved",
            "COMPLETE" if ok else "FAIL",
            f"{TRACK_C_SUMMARY_JSON}, {TRACK_C_SUMMARY_MD}",
            f"track_c_summary_status={status}",
        )
    for path in TRACK_C_STOP_DECISIONS:
        if path.exists() and path.stat().st_size > 0:
            text = path.read_text(encoding="utf-8", errors="ignore")
            explicit = "STOP_TRACK_C" in text or "do not run Track C" in text or "stop after CPU prep" in text
            return _row(
                "Track C bounded rescue opportunity resolved",
                "COMPLETE" if explicit else "FAIL",
                str(path),
                f"explicit_stop_marker_present={explicit}",
            )
    return _row(
        "Track C bounded rescue opportunity resolved",
        "PENDING",
        f"{TRACK_C_SUMMARY_JSON} or {TRACK_C_STOP_DECISIONS[0]}",
        "no Track C output summary and no explicit stop-decision artifact",
    )


def _audit_boundaries(status: dict[str, Any]) -> dict[str, str]:
    boundary = status.get("boundary") or {}
    flags = boundary.get("current_stage_forbidden_launch_status") or {}
    flags_ok = all(value is False for value in flags.values())
    gate_ok = boundary.get("gate_v1_sha256") == EXPECTED_GATE_V1_SHA256
    gate_v2_ok = boundary.get("gate_v2_draft_exists") is True
    ok = flags_ok and gate_ok and gate_v2_ok
    return _row(
        "Hard scientific boundaries preserved",
        "COMPLETE" if ok else "FAIL",
        str(DEFAULT_STATUS_JSON),
        (
            f"flags_ok={flags_ok}; gate_v1_sha256={boundary.get('gate_v1_sha256')}; "
            f"gate_v2_draft_exists={boundary.get('gate_v2_draft_exists')}"
        ),
    )


def _build_markdown(audit: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Trajectory-Aware Completion Audit")
    lines.append("")
    lines.append(f"Overall status: `{audit['overall_status']}`")
    lines.append(f"Goal complete: `{audit['goal_complete']}`")
    lines.append("")
    lines.append("| requirement | status | evidence | details |")
    lines.append("|---|---|---|---|")
    for row in audit["requirements"]:
        lines.append(
            "| {requirement} | {status} | `{evidence}` | {details} |".format(
                requirement=row["requirement"],
                status=row["status"],
                evidence=row["evidence"],
                details=row["details"].replace("|", "\\|"),
            )
        )
    lines.append("")
    lines.append("## Rule")
    lines.append("")
    lines.append("The goal is complete only when every requirement is `COMPLETE`.")
    lines.append("`PENDING` means evidence is missing or the relevant work is still running.")
    lines.append("`FAIL` means current evidence contradicts completion and needs diagnosis.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-json", type=Path, default=DEFAULT_STATUS_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument(
        "--refresh-status",
        action="store_true",
        help="Refresh TRAJECTORY_AWARE_GOAL_STATUS_CURRENT before auditing.",
    )
    args = parser.parse_args()

    if args.refresh_status:
        subprocess.run(
            [
                sys.executable,
                "scripts/report_trajectory_goal_status.py",
                "--output-json",
                str(args.status_json),
            ],
            check=True,
        )

    status = _load_json(args.status_json)
    if status is None:
        raise SystemExit(f"missing or invalid status JSON: {args.status_json}")

    requirements = [
        _audit_track_a_completion(status),
        _audit_track_a_verification(),
        _audit_track_a_decision(),
        _audit_track_b(),
        _audit_track_c(),
        _audit_boundaries(status),
    ]
    any_fail = any(row["status"] == "FAIL" for row in requirements)
    all_complete = all(row["status"] == "COMPLETE" for row in requirements)
    overall = "COMPLETE" if all_complete else ("FAIL" if any_fail else "INCOMPLETE")
    audit = {
        "schema_version": "trajectory_aware_completion_audit_v1",
        "status_json": str(args.status_json),
        "overall_status": overall,
        "goal_complete": all_complete,
        "requirements": requirements,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_build_markdown(audit), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    return 0 if overall != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
