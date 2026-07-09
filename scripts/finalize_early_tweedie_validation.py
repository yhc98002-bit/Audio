#!/usr/bin/env python3
"""Finalize Track A Early-Tweedie validation after shard completion.

This wrapper is CPU-only. It refuses to run until the shard launcher has written
completion markers, then runs any missing finalization stages. The shard
launcher already runs the merge step, so existing complete merge outputs are
reused by default and only the independent verifier / PI decision summary are
added. The final tail refreshes the completion audit and the current PI report.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_RUN_ROOT = Path("runs/early_tweedie_validation_512_bon8_20260527_full01")
DEFAULT_MANIFEST = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
DEFAULT_OUTPUT_MD = Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md")
DEFAULT_OUTPUT_JSON = Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json")
DEFAULT_PLOT_CSV = Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv")
DEFAULT_RETENTION_CSV = Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv")
DEFAULT_VERIFY_JSON = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_VERIFICATION_REPORT.json")
DEFAULT_DECISION_MD = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_PI_DECISION.md")
DEFAULT_COMPLETION_AUDIT_JSON = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.json")
DEFAULT_COMPLETION_AUDIT_MD = Path("orbit-research/TRAJECTORY_AWARE_COMPLETION_AUDIT_CURRENT.md")
DEFAULT_PI_REPORT_JSON = Path("orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.json")
DEFAULT_PI_REPORT_MD = Path("orbit-research/TRAJECTORY_AWARE_PI_REPORT_CURRENT.md")


def _run(cmd: list[str], *, dry_run: bool) -> None:
    print("+ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _count_records(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            total += sum(1 for line in f if line.strip())
    return total


def _preflight(run_root: Path, *, expected_shards: int, expected_records: int) -> dict[str, object]:
    record_paths = sorted(run_root.glob("shard*/candidate_records.jsonl"))
    launcher_exit = run_root / "launcher.exit"
    launch_finished = run_root / "launch_finished_utc.txt"
    status: dict[str, object] = {
        "run_root": str(run_root),
        "record_paths": [str(path) for path in record_paths],
        "n_record_paths": len(record_paths),
        "n_records": _count_records(record_paths) if record_paths else 0,
        "launcher_exit_exists": launcher_exit.exists(),
        "launcher_exit": launcher_exit.read_text(encoding="utf-8").strip() if launcher_exit.exists() else None,
        "launch_finished_exists": launch_finished.exists(),
    }
    errors: list[str] = []
    if not run_root.exists():
        errors.append(f"missing run root: {run_root}")
    if len(record_paths) != expected_shards:
        errors.append(f"expected {expected_shards} record files, found {len(record_paths)}")
    if int(status["n_records"]) != expected_records:
        errors.append(f"expected {expected_records} records, found {status['n_records']}")
    if not launcher_exit.exists():
        errors.append(f"missing {launcher_exit}")
    elif status["launcher_exit"] != "0":
        errors.append(f"{launcher_exit} is {status['launcher_exit']!r}, expected '0'")
    if not launch_finished.exists():
        errors.append(f"missing {launch_finished}")
    missing_summaries = [
        str(path.parent / "run_summary.json")
        for path in record_paths
        if not (path.parent / "run_summary.json").exists()
    ]
    if missing_summaries:
        errors.append(f"missing shard summaries: {missing_summaries[:4]} (n={len(missing_summaries)})")
    status["errors"] = errors
    status["ready"] = not errors
    return status


def _existing(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--plot-csv", type=Path, default=DEFAULT_PLOT_CSV)
    parser.add_argument("--retention-csv", type=Path, default=DEFAULT_RETENTION_CSV)
    parser.add_argument("--verification-json", type=Path, default=DEFAULT_VERIFY_JSON)
    parser.add_argument("--decision-md", type=Path, default=DEFAULT_DECISION_MD)
    parser.add_argument("--completion-audit-json", type=Path, default=DEFAULT_COMPLETION_AUDIT_JSON)
    parser.add_argument("--completion-audit-md", type=Path, default=DEFAULT_COMPLETION_AUDIT_MD)
    parser.add_argument("--pi-report-json", type=Path, default=DEFAULT_PI_REPORT_JSON)
    parser.add_argument("--pi-report-md", type=Path, default=DEFAULT_PI_REPORT_MD)
    parser.add_argument("--expected-shards", type=int, default=8)
    parser.add_argument("--expected-prompts", type=int, default=512)
    parser.add_argument("--expected-bon-n", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-existing-outputs",
        action="store_true",
        help="Allow overwriting final report outputs. Default refuses if outputs already exist.",
    )
    args = parser.parse_args()

    expected_records = int(args.expected_prompts) * int(args.expected_bon_n)
    status = _preflight(
        args.run_root,
        expected_shards=int(args.expected_shards),
        expected_records=expected_records,
    )
    print(json.dumps({"preflight": status}, indent=2, sort_keys=True))
    if not status["ready"]:
        return 2

    merge_outputs = [
        args.output_md,
        args.output_json,
        args.plot_csv,
        args.retention_csv,
    ]
    downstream_outputs = [
        args.verification_json,
        args.decision_md,
    ]
    final_outputs = [*merge_outputs, *downstream_outputs]

    existing_merge = _existing(merge_outputs)
    existing_downstream = _existing(downstream_outputs)
    all_merge_outputs_exist = len(existing_merge) == len(merge_outputs)
    no_merge_outputs_exist = not existing_merge

    if existing_downstream and not args.allow_existing_outputs:
        print(
            json.dumps(
                {
                    "status": "REFUSE_EXISTING_DOWNSTREAM_OUTPUTS",
                    "existing_outputs": existing_downstream,
                    "hint": "rerun with --allow-existing-outputs if this is intentional",
                    "note": (
                        "Verification or decision-summary outputs already exist. Refusing by default "
                        "to avoid overwriting reviewed reports."
                    ),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 3
    if existing_merge and not all_merge_outputs_exist and not args.allow_existing_outputs:
        print(
            json.dumps(
                {
                    "status": "REFUSE_PARTIAL_MERGE_OUTPUTS",
                    "existing_outputs": existing_merge,
                    "missing_outputs": [str(path) for path in merge_outputs if not path.exists()],
                    "hint": "rerun with --allow-existing-outputs if this partial merge state is intentional",
                    "note": (
                        "This can happen after partial completion, for example if merge outputs "
                        "were written but verification or decision summarization failed."
                    ),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 3

    record_paths = [Path(path) for path in status["record_paths"]]  # type: ignore[index]
    if all_merge_outputs_exist and not args.allow_existing_outputs:
        print(
            json.dumps(
                {
                    "status": "SKIP_MERGE_REUSE_EXISTING_OUTPUTS",
                    "existing_outputs": existing_merge,
                },
                indent=2,
            )
        )
    else:
        if existing_merge and args.allow_existing_outputs:
            print(json.dumps({"status": "OVERWRITE_MERGE_OUTPUTS", "existing_outputs": existing_merge}, indent=2))
        elif no_merge_outputs_exist:
            print(json.dumps({"status": "RUN_MERGE_NO_EXISTING_OUTPUTS"}, indent=2))
        _run(
            [
                sys.executable,
                "scripts/merge_early_tweedie_validation.py",
                "--records",
                *[str(path) for path in record_paths],
                "--run-root",
                str(args.run_root),
                "--manifest",
                str(args.manifest),
                "--output-md",
                str(args.output_md),
                "--output-json",
                str(args.output_json),
                "--plot-csv",
                str(args.plot_csv),
                "--retention-csv",
                str(args.retention_csv),
                "--expected-bon-n",
                str(args.expected_bon_n),
            ],
            dry_run=args.dry_run,
        )
    _run(
        [
            sys.executable,
            "scripts/verify_early_tweedie_validation.py",
            "--run-root",
            str(args.run_root),
            "--validation-json",
            str(args.output_json),
            "--plot-csv",
            str(args.plot_csv),
            "--retention-csv",
            str(args.retention_csv),
            "--manifest",
            str(args.manifest),
            "--expected-bon-n",
            str(args.expected_bon_n),
            "--expected-prompts",
            str(args.expected_prompts),
            "--expected-shards",
            str(args.expected_shards),
            "--output-json",
            str(args.verification_json),
        ],
        dry_run=args.dry_run,
    )
    _run(
        [
            sys.executable,
            "scripts/summarize_early_tweedie_decision.py",
            "--verification-report",
            str(args.verification_json),
            "--output-md",
            str(args.decision_md),
        ],
        dry_run=args.dry_run,
    )
    _run(
        [
            sys.executable,
            "scripts/audit_trajectory_aware_goal_completion.py",
            "--refresh-status",
            "--output-json",
            str(args.completion_audit_json),
            "--output-md",
            str(args.completion_audit_md),
        ],
        dry_run=args.dry_run,
    )
    _run(
        [
            sys.executable,
            "scripts/generate_trajectory_aware_pi_report.py",
            "--status-json",
            "orbit-research/TRAJECTORY_AWARE_GOAL_STATUS_CURRENT.json",
            "--audit-json",
            str(args.completion_audit_json),
            "--track-a-verification-json",
            str(args.verification_json),
            "--track-a-decision-md",
            str(args.decision_md),
            "--output-json",
            str(args.pi_report_json),
            "--output-md",
            str(args.pi_report_md),
        ],
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "status": "PASS_DRY_RUN" if args.dry_run else "PASS",
                "outputs": [
                    *[str(path) for path in final_outputs],
                    str(args.completion_audit_json),
                    str(args.completion_audit_md),
                    str(args.pi_report_json),
                    str(args.pi_report_md),
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
