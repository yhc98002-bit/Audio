#!/usr/bin/env python3
"""Generate the trajectory-aware PI report from current artifacts.

This is a CPU-only reporting script. It does not start jobs, modify run
directories, or infer scientific completion from partial evidence. If the
completion audit is incomplete, the report is explicitly marked interim.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


DEFAULT_STATUS_JSON = Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json")
DEFAULT_AUDIT_JSON = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json")
DEFAULT_TRACK_A_LIVE_CHECK_JSON = Path("orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.json")
DEFAULT_TRACK_A_VERIFICATION_JSON = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json")
DEFAULT_TRACK_A_DECISION_MD = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md")
DEFAULT_TRACK_B_JSON = Path("orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.json")
DEFAULT_TRACK_C_SUMMARY_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.json")
DEFAULT_TRACK_C_STOP_MD = Path("orbit-research/C1_LITE_RL_RESCUE_STOP_DECISION.md")
DEFAULT_TRACK_C_PREFLIGHT_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json")
DEFAULT_TRACK_C_LAUNCH_PLAN_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_LAUNCH_PLAN_CURRENT.json")
DEFAULT_REFRESH_JSON = Path("orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.json")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _decision_field(text: str | None, field: str) -> str | None:
    if not text:
        return None
    match = re.search(rf"^{re.escape(field)}:\s*`([^`]+)`", text, flags=re.MULTILINE)
    return match.group(1) if match else None


def _safe_float(row: dict[str, Any], key: str) -> float | None:
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


def _track_a_summary(
    status: dict[str, Any],
    live_check: dict[str, Any] | None,
    verification: dict[str, Any] | None,
    decision_md: str | None,
) -> dict[str, Any]:
    track_a_status = status.get("track_a", {})
    decision_status = _decision_field(decision_md, "Decision status")
    verifier_status = _decision_field(decision_md, "Verifier status")
    status_records = track_a_status.get("records")
    live_records = live_check.get("n_records") if live_check else None
    if isinstance(status_records, int) and isinstance(live_records, int):
        live_record_lag = status_records - live_records
    else:
        live_record_lag = track_a_status.get("live_record_check_record_lag")
    summary: dict[str, Any] = {
        "run_root": track_a_status.get("run_root"),
        "records": track_a_status.get("records"),
        "expected_records": track_a_status.get("expected_records"),
        "completed": track_a_status.get("completed"),
        "stall_suspected": track_a_status.get("track_a_stall_suspected"),
        "aggregate_estimated_finish_local": track_a_status.get("aggregate_estimated_finish_local"),
        "slowest_shard_estimated_finish_local": track_a_status.get("slowest_shard_estimated_finish_local"),
        "estimated_active_gpu_hours_elapsed": track_a_status.get("estimated_active_gpu_hours_elapsed"),
        "estimated_final_active_gpu_hours_by_shard_rates": track_a_status.get("estimated_final_active_gpu_hours_by_shard_rates"),
        "live_record_check_status": live_check.get("status") if live_check else None,
        "live_record_check_records": live_check.get("n_records") if live_check else None,
        "live_record_check_record_lag": live_record_lag,
        "live_record_check_fresh": live_record_lag == 0 if live_record_lag is not None else None,
        "live_record_check_complete_prompts": live_check.get("n_complete_prompts") if live_check else None,
        "live_record_check_errors": len(live_check.get("errors", [])) if live_check else None,
        "verification_status": verification.get("status") if verification else verifier_status,
        "decision_status": decision_status,
        "primary_schedules": [],
        "primary_retention": [],
        "threshold": None,
    }
    if not verification:
        return summary
    key_metrics = verification.get("key_metrics") or {}
    summary["threshold"] = key_metrics.get("strong_candidate_threshold")
    schedules = [
        row for row in key_metrics.get("robust_common_all_schedules", [])
        if row.get("metric") == "common_robust_lcb" and row.get("stratum") == "all"
    ]
    retention = [
        row for row in key_metrics.get("robust_common_all_retention", [])
        if row.get("metric") == "common_robust_lcb" and row.get("stratum") == "all"
    ]
    summary["primary_schedules"] = schedules
    summary["primary_retention"] = retention
    return summary


def _track_b_summary(track_b: dict[str, Any] | None) -> dict[str, Any]:
    if not track_b:
        return {"status": "MISSING"}
    aggregate = track_b.get("aggregate_summary") or {}
    interpretation = track_b.get("interpretation") or {}
    return {
        "status": track_b.get("status"),
        "gpu_hours_consumed": track_b.get("gpu_hours_consumed"),
        "classification": interpretation.get("classification"),
        "cautious_claim": interpretation.get("cautious_claim"),
        "fixedwin_read": interpretation.get("fixedwin_read"),
        "primary_median_between_share": aggregate.get("primary_median_between_share"),
        "primary_median_between_within_ratio": aggregate.get("primary_median_between_within_ratio"),
        "primary_median_crossing_frequency": aggregate.get("primary_median_crossing_frequency"),
        "primary_median_globalness_index": aggregate.get("primary_median_globalness_index"),
        "output_tables": track_b.get("output_tables") or {},
        "hard_boundary_flags": track_b.get("hard_boundary_flags") or {},
    }


def _track_c_summary(
    track_c: dict[str, Any] | None,
    stop_text: str | None,
    preflight: dict[str, Any] | None,
    launch_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    preflight_status = preflight.get("status") if preflight else None
    preflight_blockers = [row.get("name") for row in (preflight or {}).get("blockers", [])]
    launch_status = launch_plan.get("status") if launch_plan else None
    launch_gpu_jobs = launch_plan.get("gpu_jobs_launched") if launch_plan else None
    if track_c:
        gpu_h = 0.0
        any_gpu_h = False
        for row in track_c.get("logs", []):
            value = row.get("gpu_hours_consumed")
            if value is not None:
                gpu_h += float(value)
                any_gpu_h = True
        return {
            "status": track_c.get("status"),
            "resolution": "OUTPUT_SUMMARY_AVAILABLE",
            "run_root": track_c.get("run_root"),
            "n_logs": track_c.get("n_logs"),
            "gpu_hours_consumed": gpu_h if any_gpu_h else None,
            "smoke_preflight_status": preflight_status,
            "smoke_preflight_blockers": preflight_blockers,
            "smoke_launch_plan_status": launch_status,
            "smoke_launch_plan_gpu_jobs": launch_gpu_jobs,
        }
    if stop_text:
        return {
            "status": "STOPPED_BY_DECISION",
            "resolution": "EXPLICIT_STOP_DECISION",
            "gpu_hours_consumed": 0.0,
            "smoke_preflight_status": preflight_status,
            "smoke_preflight_blockers": preflight_blockers,
            "smoke_launch_plan_status": launch_status,
            "smoke_launch_plan_gpu_jobs": launch_gpu_jobs,
        }
    return {
        "status": "PENDING",
        "resolution": "NO_OUTPUT_SUMMARY_OR_STOP_DECISION",
        "gpu_hours_consumed": None,
        "smoke_preflight_status": preflight_status,
        "smoke_preflight_blockers": preflight_blockers,
        "smoke_launch_plan_status": launch_status,
        "smoke_launch_plan_gpu_jobs": launch_gpu_jobs,
    }


def _refresh_summary(refresh: dict[str, Any] | None) -> dict[str, Any]:
    if not refresh:
        return {"status": "MISSING"}
    return {
        "status": refresh.get("status"),
        "gpu_jobs_launched": refresh.get("gpu_jobs_launched"),
        "commands_run": len(refresh.get("commands") or []),
        "track_a_records": refresh.get("track_a_records"),
        "track_a_expected_records": refresh.get("track_a_expected_records"),
        "completion_audit_status": refresh.get("completion_audit_status"),
        "pi_report_status": refresh.get("pi_report_status"),
        "track_c_preflight_status": refresh.get("track_c_preflight_status"),
        "track_c_launch_plan_status": refresh.get("track_c_launch_plan_status"),
        "seconds_until_next_manual_poll": refresh.get("seconds_until_next_manual_poll"),
        "next_manual_poll_after_local": refresh.get("next_manual_poll_after_local"),
        "manual_poll_guidance": refresh.get("manual_poll_guidance"),
        "previous_status_generated_at_utc": refresh.get("previous_status_generated_at_utc"),
    }


def _requirements(audit: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not audit:
        return [{"name": "completion audit", "status": "MISSING", "details": "audit JSON missing"}]
    return list(audit.get("requirements") or [])


def _recommendation(report: dict[str, Any]) -> str:
    if report["overall_status"] != "FINAL_READY":
        return (
            "Do not make final method-ranking or paper-direction claims yet. "
            "Wait for Track A verification and resolve Track C by bounded output summary or explicit stop decision."
        )
    track_a_decision = str(report["track_a"].get("decision_status") or "")
    track_c_status = str(report["track_c"].get("status") or "")
    if track_a_decision == "STRONG_CANDIDATE_MAIN_APPLICATION" and track_c_status in {
        "FAIL",
        "STOPPED_BY_DECISION",
        "PASS_WITH_WARNINGS",
        "PASS",
    }:
        return (
            "Recommended framing: pivot toward trajectory-aware inference-time selection plus "
            "global-quality emergence analysis; keep RL rescue as bounded exploratory evidence."
        )
    return (
        "Use the verified Track A/Track C readouts to decide between trajectory-aware pivot, "
        "additional bounded triage, or stopping the RL line."
    )


def build_report(
    *,
    status_json: Path,
    audit_json: Path,
    track_a_verification_json: Path,
    track_a_live_check_json: Path,
    track_a_decision_md: Path,
    track_b_json: Path,
    track_c_summary_json: Path,
    track_c_stop_md: Path,
    track_c_preflight_json: Path,
    track_c_launch_plan_json: Path,
    refresh_json: Path,
) -> dict[str, Any]:
    status = _load_json(status_json) or {}
    audit = _load_json(audit_json) or {}
    live_check = _load_json(track_a_live_check_json)
    verification = _load_json(track_a_verification_json)
    decision_text = _read_text(track_a_decision_md)
    track_b = _load_json(track_b_json)
    track_c = _load_json(track_c_summary_json)
    track_c_stop = _read_text(track_c_stop_md)
    track_c_preflight = _load_json(track_c_preflight_json)
    track_c_launch_plan = _load_json(track_c_launch_plan_json)
    refresh = _load_json(refresh_json)
    goal_complete = bool(audit.get("goal_complete"))
    report: dict[str, Any] = {
        "schema_version": "trajectory_aware_pi_report_v1",
        "generated_at_utc": _now_utc(),
        "overall_status": "FINAL_READY" if goal_complete else "INTERIM_INCOMPLETE_DO_NOT_CLAIM_FINAL",
        "goal_complete": goal_complete,
        "status_json": str(status_json),
        "completion_audit_json": str(audit_json),
        "track_a": _track_a_summary(status, live_check, verification, decision_text),
        "track_b": _track_b_summary(track_b),
        "track_c": _track_c_summary(track_c, track_c_stop, track_c_preflight, track_c_launch_plan),
        "refresh": _refresh_summary(refresh),
        "requirements": _requirements(audit),
        "boundary": (status.get("boundary") or {}),
    }
    report["recommendation"] = _recommendation(report)
    return report


def _schedule_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| schedule | compute_fraction | reward_fraction | winner_match | false_negative | median_regret |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if not rows:
        lines.append("| NA | NA | NA | NA | NA | NA |")
        return lines
    for row in rows:
        lines.append(
            "| {schedule} | {compute} | {reward} | {winner} | {false_neg} | {regret} |".format(
                schedule=row.get("schedule"),
                compute=_fmt(_safe_float(row, "compute_fraction")),
                reward=_fmt(_safe_float(row, "reward_fraction")),
                winner=_fmt(_safe_float(row, "winner_match")),
                false_neg=_fmt(_safe_float(row, "false_negative")),
                regret=_fmt(_safe_float(row, "median_regret")),
            )
        )
    return lines


def _retention_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| sigma | top1 | top2 | top4 | bottom25_false_negative |",
        "|---|---:|---:|---:|---:|",
    ]
    if not rows:
        lines.append("| NA | NA | NA | NA | NA |")
        return lines
    for row in rows:
        lines.append(
            "| {sigma} | {top1} | {top2} | {top4} | {fn} |".format(
                sigma=row.get("sigma"),
                top1=_fmt(_safe_float(row, "winner_retention_top1")),
                top2=_fmt(_safe_float(row, "winner_retention_top2")),
                top4=_fmt(_safe_float(row, "winner_retention_top4")),
                fn=_fmt(_safe_float(row, "bottom25_false_negative")),
            )
        )
    return lines


def build_markdown(report: dict[str, Any]) -> str:
    ta = report["track_a"]
    tb = report["track_b"]
    tc = report["track_c"]
    refresh = report["refresh"]
    boundary = report["boundary"]
    lines: list[str] = []
    lines.append("# Trajectory-Aware PI Report")
    lines.append("")
    lines.append(f"Generated UTC: `{report['generated_at_utc']}`")
    lines.append(f"Overall status: `{report['overall_status']}`")
    lines.append(f"Goal complete: `{report['goal_complete']}`")
    lines.append("")
    if not report["goal_complete"]:
        lines.append("This is an interim report. Do not use it to claim final method ranking or final paper direction.")
        lines.append("")
    lines.append("## Refresh Status")
    lines.append("")
    lines.append(f"- status: `{refresh.get('status')}`")
    lines.append(f"- GPU jobs launched by refresh: `{refresh.get('gpu_jobs_launched')}`")
    lines.append(f"- commands run by refresh: `{refresh.get('commands_run')}`")
    lines.append(f"- Track A records in refresh snapshot: `{refresh.get('track_a_records')} / {refresh.get('track_a_expected_records')}`")
    lines.append(f"- completion audit status in refresh snapshot: `{refresh.get('completion_audit_status')}`")
    lines.append(f"- Track C preflight status in refresh snapshot: `{refresh.get('track_c_preflight_status')}`")
    lines.append(f"- next manual poll after local: `{refresh.get('next_manual_poll_after_local')}`")
    if refresh.get("manual_poll_guidance"):
        lines.append(f"- manual poll guidance: {refresh.get('manual_poll_guidance')}")
    lines.append("")
    lines.append("## Completion Evidence")
    lines.append("")
    lines.append("| requirement | status | details |")
    lines.append("|---|---|---|")
    for row in report["requirements"]:
        name = row.get("requirement") or row.get("name") or "unknown"
        status = row.get("status")
        details = row.get("details") or row.get("evidence") or ""
        lines.append(f"| {name} | {status} | {details} |")
    lines.append("")
    lines.append("## Track A: Early-Tweedie Validation")
    lines.append("")
    lines.append(f"- run root: `{ta.get('run_root')}`")
    lines.append(f"- records: `{ta.get('records')} / {ta.get('expected_records')}`")
    lines.append(f"- completed: `{ta.get('completed')}`")
    lines.append(f"- stall suspected: `{ta.get('stall_suspected')}`")
    lines.append(f"- verification status: `{ta.get('verification_status')}`")
    lines.append(f"- PI decision status: `{ta.get('decision_status')}`")
    lines.append(f"- active GPU-h elapsed estimate: `{ta.get('estimated_active_gpu_hours_elapsed')}`")
    lines.append(f"- final active GPU-h estimate: `{ta.get('estimated_final_active_gpu_hours_by_shard_rates')}`")
    lines.append(f"- aggregate finish estimate local: `{ta.get('aggregate_estimated_finish_local')}`")
    lines.append(f"- slowest-shard finish estimate local: `{ta.get('slowest_shard_estimated_finish_local')}`")
    lines.append(f"- live record check status: `{ta.get('live_record_check_status')}`")
    lines.append(f"- live record check records: `{ta.get('live_record_check_records')}`")
    lines.append(f"- live record check record lag: `{ta.get('live_record_check_record_lag')}`")
    lines.append(f"- live record check fresh: `{ta.get('live_record_check_fresh')}`")
    lines.append(f"- live record check complete prompts: `{ta.get('live_record_check_complete_prompts')}`")
    lines.append(f"- live record check errors: `{ta.get('live_record_check_errors')}`")
    lines.append("")
    lines.append("Primary robust/common schedule rows:")
    lines.append("")
    lines.extend(_schedule_table(ta.get("primary_schedules") or []))
    lines.append("")
    lines.append("Primary robust/common winner-retention rows:")
    lines.append("")
    lines.extend(_retention_table(ta.get("primary_retention") or []))
    lines.append("")
    lines.append("## Track B: Global Quality Structure")
    lines.append("")
    lines.append(f"- status: `{tb.get('status')}`")
    lines.append(f"- classification: `{tb.get('classification')}`")
    lines.append(f"- cautious claim: {tb.get('cautious_claim') or 'NA'}")
    lines.append(f"- FixedWin read: `{tb.get('fixedwin_read')}`")
    lines.append(f"- primary median between-share: `{_fmt(tb.get('primary_median_between_share'))}`")
    lines.append(f"- primary median between/within ratio: `{_fmt(tb.get('primary_median_between_within_ratio'))}`")
    lines.append(f"- primary median crossing frequency: `{_fmt(tb.get('primary_median_crossing_frequency'))}`")
    lines.append(f"- primary median globalness index: `{_fmt(tb.get('primary_median_globalness_index'))}`")
    lines.append("")
    lines.append("## Track C: Bounded RL Rescue")
    lines.append("")
    lines.append(f"- status: `{tc.get('status')}`")
    lines.append(f"- resolution: `{tc.get('resolution')}`")
    lines.append(f"- run root: `{tc.get('run_root')}`")
    lines.append(f"- logs: `{tc.get('n_logs')}`")
    lines.append(f"- GPU-h consumed: `{tc.get('gpu_hours_consumed')}`")
    lines.append(f"- smoke preflight status: `{tc.get('smoke_preflight_status')}`")
    lines.append(f"- smoke preflight blockers: `{tc.get('smoke_preflight_blockers')}`")
    lines.append(f"- smoke launch plan status: `{tc.get('smoke_launch_plan_status')}`")
    lines.append(f"- smoke launch plan GPU jobs: `{tc.get('smoke_launch_plan_gpu_jobs')}`")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(report["recommendation"])
    lines.append("")
    lines.append("## Boundary Confirmation")
    lines.append("")
    lines.append(f"- gate_v1 SHA256: `{boundary.get('gate_v1_sha256')}`")
    lines.append(f"- gate_v2 draft exists: `{boundary.get('gate_v2_draft_exists')}`")
    for key, value in (boundary.get("current_stage_forbidden_launch_status") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append("- no canonical proposal rewrite is authorized by this report")
    lines.append("- no pruning+RL is authorized by this report")
    lines.append("")
    lines.append("## Files To Inspect")
    lines.append("")
    for path in [
        report["status_json"],
        report["completion_audit_json"],
        "orbit-research/TRAJECTORY_AWARE_REFRESH_STATUS_CURRENT.md",
        "orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md",
        "orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md",
        "orbit-research/C1_LITE_RL_RESCUE_OUTPUT_SUMMARY.md",
    ]:
        lines.append(f"- `{path}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-json", type=Path, default=DEFAULT_STATUS_JSON)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--track-a-live-check-json", type=Path, default=DEFAULT_TRACK_A_LIVE_CHECK_JSON)
    parser.add_argument("--track-a-verification-json", type=Path, default=DEFAULT_TRACK_A_VERIFICATION_JSON)
    parser.add_argument("--track-a-decision-md", type=Path, default=DEFAULT_TRACK_A_DECISION_MD)
    parser.add_argument("--track-b-json", type=Path, default=DEFAULT_TRACK_B_JSON)
    parser.add_argument("--track-c-summary-json", type=Path, default=DEFAULT_TRACK_C_SUMMARY_JSON)
    parser.add_argument("--track-c-stop-md", type=Path, default=DEFAULT_TRACK_C_STOP_MD)
    parser.add_argument("--track-c-preflight-json", type=Path, default=DEFAULT_TRACK_C_PREFLIGHT_JSON)
    parser.add_argument("--track-c-launch-plan-json", type=Path, default=DEFAULT_TRACK_C_LAUNCH_PLAN_JSON)
    parser.add_argument("--refresh-json", type=Path, default=DEFAULT_REFRESH_JSON)
    parser.add_argument("--output-json", type=Path, default=Path("orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.json"))
    parser.add_argument("--output-md", type=Path, default=Path("orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md"))
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit nonzero if completion audit does not prove the full objective.",
    )
    args = parser.parse_args()

    report = build_report(
        status_json=args.status_json,
        audit_json=args.audit_json,
        track_a_live_check_json=args.track_a_live_check_json,
        track_a_verification_json=args.track_a_verification_json,
        track_a_decision_md=args.track_a_decision_md,
        track_b_json=args.track_b_json,
        track_c_summary_json=args.track_c_summary_json,
        track_c_stop_md=args.track_c_stop_md,
        track_c_preflight_json=args.track_c_preflight_json,
        track_c_launch_plan_json=args.track_c_launch_plan_json,
        refresh_json=args.refresh_json,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(build_markdown(report), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    if args.require_complete and not report["goal_complete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
