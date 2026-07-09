#!/usr/bin/env python3
"""CPU-only readiness preflight for a future Track C C1-lite smoke.

This script does not launch training. It checks whether the already materialized
C1-lite smoke bundle is safe to hand to a future GPU smoke command. It is
intentionally conservative and reports NOT_READY while Track A is still active
or when PI/researcher GO has not been provided.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import yaml


DEFAULT_STATUS_JSON = Path("orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json")
DEFAULT_AUDIT_JSON = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json")
DEFAULT_ARTIFACTS_DIR = Path("orbit-research/codex-imports")
DEFAULT_OUTPUT_JSON = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.json")
DEFAULT_OUTPUT_MD = Path("orbit-research/C1_LITE_RL_RESCUE_SMOKE_PREFLIGHT_CURRENT.md")
FORBIDDEN_SECTION_KEYS = {
    "terminal_reward",
    "process_reward",
    "sigma_policy",
    "methods",
    "sampler",
}


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML root is not an object: {path}")
    return data


def _latest_smoke_summary(artifacts_dir: Path) -> Path:
    candidates = sorted(
        artifacts_dir.glob("phase_c1_lite_rl_rescue_materialize-smoke_summary_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"no materialize-smoke summary found under {artifacts_dir}")
    return candidates[0]


def _check(name: str, ok: bool, detail: str, *, severity: str = "blocker") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "severity": severity}


def _bundle_checks(bundle_path: Path, future_run_root: Path) -> list[dict[str, Any]]:
    bundle = _load_yaml(bundle_path)
    checks: list[dict[str, Any]] = []
    checks.append(_check("bundle_exists", bundle_path.exists(), str(bundle_path)))
    checks.append(_check("future_run_root_absent", not future_run_root.exists(), str(future_run_root)))
    checks.append(_check("schema_firstwave_compatible", bundle.get("schema_version") == "phase_c1_firstwave_bundle_v1", str(bundle.get("schema_version"))))
    scope = bundle.get("scope") or {}
    checks.append(_check("scope_dev", scope.get("split") == "dev", str(scope.get("split"))))
    checks.append(_check("prompt_source_dev", scope.get("prompt_source") == "configs/prompts/dev.jsonl", str(scope.get("prompt_source"))))
    checks.append(_check("n_prompts_32", int(scope.get("n_prompts", -1)) == 32, str(scope.get("n_prompts"))))
    for key in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
        checks.append(_check(f"{key}_false", scope.get(key) is False, str(scope.get(key))))
    safety = bundle.get("safety") or {}
    checks.append(_check("hard_cap_lte_40", float(safety.get("hard_cap_gpu_h", 999.0)) <= 40.0, str(safety.get("hard_cap_gpu_h"))))
    forbidden_launches = safety.get("forbidden_launches") or {}
    for key in ("held_out", "phase_d", "human_eval", "pruning_rl"):
        checks.append(_check(f"forbidden_launch_{key}_false", forbidden_launches.get(key) is False, str(forbidden_launches.get(key))))
    forbidden_changes = safety.get("forbidden_changes") or {}
    for key in ("reward_definitions", "sigma_policy", "prompt_splits", "credit_unit_definitions", "gate_v1", "gate_v2_activation"):
        checks.append(_check(f"forbidden_change_{key}_false", forbidden_changes.get(key) is False, str(forbidden_changes.get(key))))
    smoke = bundle.get("smoke") or {}
    checks.append(_check("smoke_prompt_count_lte_cap", len(smoke.get("prompt_ids") or []) <= int(smoke.get("max_prompts_allowed", 0)), str(smoke.get("prompt_ids"))))
    checks.append(_check("smoke_output_root_matches_future_root", smoke.get("output_root") == str(future_run_root), f"{smoke.get('output_root')} vs {future_run_root}"))
    backend = bundle.get("backend") or {}
    checks.append(_check("post_update_logging_enabled", backend.get("log_post_update_diagnostics") is True, str(backend.get("log_post_update_diagnostics"))))
    checks.append(_check("adapter_delta_logging_enabled", backend.get("track_adapter_norm_delta") is True, str(backend.get("track_adapter_norm_delta"))))
    return checks


def _diff_checks(diff_path: Path, setting_id: str) -> list[dict[str, Any]]:
    if not diff_path.exists():
        return [_check("diff_report_exists", False, str(diff_path))]
    data = _load_json(diff_path)
    checks = [_check("diff_allowed_only_flag", data.get("allowed_only") is True, str(data.get("allowed_only")))]
    bad = []
    for row in data.get("diffs", []):
        if row.get("setting_id") != setting_id:
            continue
        root = str(row.get("path", "")).split(".", 1)[0]
        if root in FORBIDDEN_SECTION_KEYS:
            bad.append(row)
    checks.append(_check("no_scientific_section_diffs", not bad, f"bad_diff_count={len(bad)}"))
    return checks


def build_preflight(
    *,
    status_json: Path,
    audit_json: Path,
    smoke_summary: Path,
    setting: str,
    pi_go: bool,
) -> dict[str, Any]:
    status = _load_json(status_json)
    audit = _load_json(audit_json)
    summary = _load_json(smoke_summary)
    materialized = [row for row in summary.get("materialized", []) if row.get("setting_id") == setting]
    checks: list[dict[str, Any]] = []

    track_a = status.get("track_a") or {}
    checks.append(_check("track_a_completed", track_a.get("completed") is True, f"records={track_a.get('records')}/{track_a.get('expected_records')} completed={track_a.get('completed')}"))
    checks.append(_check("track_a_not_stalled", track_a.get("track_a_stall_suspected") is False, str(track_a.get("track_a_stall_suspected"))))
    checks.append(_check("track_a_collectors_released", int(track_a.get("python_collector_processes") or 0) == 0, str(track_a.get("python_collector_processes"))))
    checks.append(_check("no_prior_track_c_gpu_smoke", (status.get("boundary") or {}).get("current_stage_forbidden_launch_status", {}).get("track_c_gpu_smoke_launched") is False, "status boundary flag"))
    checks.append(_check("completion_audit_no_fail", audit.get("overall_status") != "FAIL", str(audit.get("overall_status"))))
    checks.append(_check("pi_researcher_go_present", pi_go, "requires --pi-go"))
    checks.append(_check("smoke_summary_pass", summary.get("status") == "PASS", str(summary.get("status"))))
    checks.append(_check("smoke_summary_cpu_only", summary.get("cpu_only") is True and summary.get("gpu_jobs_launched") == 0, f"cpu_only={summary.get('cpu_only')} gpu_jobs={summary.get('gpu_jobs_launched')}"))
    checks.append(_check("setting_materialized_once", len(materialized) == 1, f"setting={setting} n={len(materialized)}"))

    bundle_path: Path | None = None
    future_run_root: Path | None = None
    future_command: list[str] | None = None
    diff_path: Path | None = None
    if materialized:
        row = materialized[0]
        bundle_path = Path(row["bundle_path"])
        future_run_root = Path(row["future_run_root"])
        future_command = list(row.get("future_runner_command") or [])
        diff_path = Path(summary.get("diff_path", ""))
        checks.append(_check("future_command_is_smoke", "--mode" in future_command and "smoke" in future_command, " ".join(future_command)))
        checks.append(_check("future_command_has_pi_launch_flag", "--pi-approved-launch" in future_command, " ".join(future_command)))
        checks.extend(_bundle_checks(bundle_path, future_run_root))
        checks.extend(_diff_checks(diff_path, setting))

    blockers = [row for row in checks if row["severity"] == "blocker" and not row["ok"]]
    return {
        "schema_version": "c1_lite_rl_rescue_smoke_preflight_v1",
        "generated_at_utc": _now_utc(),
        "status": "READY" if not blockers else "NOT_READY",
        "setting": setting,
        "status_json": str(status_json),
        "audit_json": str(audit_json),
        "smoke_summary": str(smoke_summary),
        "bundle_path": str(bundle_path) if bundle_path else None,
        "future_run_root": str(future_run_root) if future_run_root else None,
        "future_runner_command": future_command,
        "diff_path": str(diff_path) if diff_path else None,
        "pi_go": pi_go,
        "checks": checks,
        "blockers": blockers,
        "gpu_jobs_launched": 0,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# C1-Lite RL Rescue Smoke Preflight",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Status: `{report['status']}`",
        f"Setting: `{report['setting']}`",
        f"GPU jobs launched by this preflight: `{report['gpu_jobs_launched']}`",
        "",
        "## Candidate Command",
        "",
    ]
    command = report.get("future_runner_command")
    if command:
        lines.append("```bash")
        lines.append(" ".join(command))
        lines.append("```")
    else:
        lines.append("No future command resolved.")
    lines.extend([
        "",
        "## Checks",
        "",
        "| check | ok | severity | detail |",
        "|---|---|---|---|",
    ])
    for row in report["checks"]:
        detail = str(row["detail"]).replace("|", "\\|")
        lines.append(f"| {row['name']} | {row['ok']} | {row['severity']} | {detail} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
    ])
    if report["status"] == "READY":
        lines.append("The materialized smoke bundle is structurally ready for a future PI/researcher-approved GPU smoke.")
    else:
        lines.append("Do not launch Track C smoke. Resolve blockers first.")
    lines.append("This preflight is CPU-only and does not authorize held-out, Phase D, human eval, pruning+RL, or full 1000-step RL.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-json", type=Path, default=DEFAULT_STATUS_JSON)
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--smoke-summary", type=Path, default=None)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--setting", default="r8b_baseline_instrumented")
    parser.add_argument("--pi-go", action="store_true", help="Record explicit PI/researcher GO for preflight readiness only; does not launch.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--require-ready", action="store_true", help="Exit nonzero unless every blocker is clear.")
    args = parser.parse_args()

    smoke_summary = args.smoke_summary or _latest_smoke_summary(args.artifacts_dir)
    report = build_preflight(
        status_json=args.status_json,
        audit_json=args.audit_json,
        smoke_summary=smoke_summary,
        setting=args.setting,
        pi_go=bool(args.pi_go),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(report), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    if args.require_ready and report["status"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
