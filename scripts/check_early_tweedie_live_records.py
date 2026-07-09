#!/usr/bin/env python3
"""CPU-only live consistency check for in-progress Early-Tweedie shards.

This checks partial ``candidate_records.jsonl`` files while Track A is still
running. It does not compute pruning results or require final merge artifacts.
The check is conservative about completed records but allows each prompt to be
partially written with contiguous candidate indices during collection.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_RUN_ROOT = Path("runs/early_tweedie_validation_512_bon8_20260527_full01")
DEFAULT_MANIFEST = Path("orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
DEFAULT_OUTPUT_JSON = Path("orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.json")
DEFAULT_OUTPUT_MD = Path("orbit-research/EARLY_TWEEDIE_LIVE_RECORD_CHECK_CURRENT.md")
EXPECTED_STEP_INDEX = {"0.9": 7, "0.8": 12, "0.7": 16}
DEFAULT_METRICS = ("common_robust_lcb", "aesthetic_pq", "semantic_fit", "lyric_intelligibility")
SAFETY_FALSE_FLAGS = (
    "training_launched",
    "held_out_workflow_launched",
    "phase_d_launched",
    "human_eval_launched",
    "pruning_rl_launched",
    "gate_v1_modified",
    "gate_v2_activated",
    "reward_sigma_prompt_credit_definitions_changed",
)


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _manifest_by_id(path: Path) -> dict[str, dict[str, Any]]:
    data = _load_json(path)
    prompts = data.get("prompts")
    if not isinstance(prompts, list):
        raise RuntimeError(f"manifest has no prompts list: {path}")
    by_id: dict[str, dict[str, Any]] = {}
    for row in prompts:
        pid = str(row["prompt_id"])
        if pid in by_id:
            raise RuntimeError(f"duplicate prompt_id in manifest: {pid}")
        by_id[pid] = row
    return by_id


def _read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_no}: invalid JSONL: {exc}")
                continue
            row["_source_record_path"] = str(path)
            row["_source_record_line"] = line_no
            row["_source_shard"] = path.parent.name
            rows.append(row)
    return rows


def _discover_records(run_root: Path) -> list[Path]:
    return sorted(run_root.glob("shard*/candidate_records.jsonl"))


def _summary_for(record_path: Path) -> dict[str, Any] | None:
    path = record_path.parent / "run_summary.json"
    if not path.exists():
        return None
    summary = _load_json(path)
    if isinstance(summary, dict):
        summary["_summary_path"] = str(path)
        return summary
    return None


def _check_row(
    row: dict[str, Any],
    *,
    manifest_by_id: dict[str, dict[str, Any]],
    metrics: tuple[str, ...],
    expected_bon_n: int,
    seed_base: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    loc = f"{row.get('_source_record_path')}:{row.get('_source_record_line')}"
    for key in ("prompt_id", "prompt_source", "candidate_index", "manifest_index", "candidate_seed", "split", "vocal_stratum"):
        if key not in row:
            errors.append(f"{loc}: missing required key {key}")
            return
    pid = str(row["prompt_id"])
    try:
        cand = int(row["candidate_index"])
        manifest_index = int(row["manifest_index"])
        seed = int(row["candidate_seed"])
    except (TypeError, ValueError) as exc:
        errors.append(f"{loc}: candidate_index/manifest_index/candidate_seed parse error: {exc}")
        return
    if cand < 0 or cand >= expected_bon_n:
        errors.append(f"{loc}: candidate_index {cand} outside [0, {expected_bon_n - 1}]")
    expected_seed = seed_base + manifest_index * 1000 + cand
    if seed != expected_seed:
        errors.append(f"{loc}: candidate_seed {seed} != expected {expected_seed}")
    manifest_row = manifest_by_id.get(pid)
    if manifest_row is None:
        errors.append(f"{loc}: prompt_id {pid} absent from manifest")
    else:
        if str(row.get("split")) != str(manifest_row.get("split")):
            errors.append(f"{loc}: split {row.get('split')!r} != manifest {manifest_row.get('split')!r}")
        manifest_vocal = manifest_row.get("vocal_stratum") or (manifest_row.get("strata") or {}).get("vocal_vs_instrumental")
        if str(row.get("vocal_stratum")) != str(manifest_vocal):
            errors.append(f"{loc}: vocal_stratum {row.get('vocal_stratum')!r} != manifest {manifest_vocal!r}")
        manifest_source = manifest_row.get("prompt_source")
        if str(row.get("prompt_source")) != str(manifest_source):
            errors.append(f"{loc}: prompt_source {row.get('prompt_source')!r} != manifest {manifest_source!r}")
    for metric in metrics:
        for key in [f"final_{metric}", *[f"early_{sigma}_{metric}" for sigma in EXPECTED_STEP_INDEX]]:
            if _finite(row.get(key)) is None:
                errors.append(f"{loc}: missing/non-finite metric {key}")
    for sigma, expected_step in EXPECTED_STEP_INDEX.items():
        step_key = f"early_{sigma}_step_index"
        actual_sigma_key = f"early_{sigma}_actual_sigma"
        try:
            step = int(row.get(step_key))
        except (TypeError, ValueError):
            errors.append(f"{loc}: {step_key} missing/non-integer")
            continue
        if step != expected_step:
            errors.append(f"{loc}: {step_key}={step}, expected {expected_step}")
        actual_sigma = _finite(row.get(actual_sigma_key))
        if actual_sigma is None or abs(actual_sigma - float(sigma)) > 0.025:
            errors.append(f"{loc}: {actual_sigma_key}={row.get(actual_sigma_key)!r} outside tolerance")
    if _finite(row.get("duration_actual_s")) is None:
        warnings.append(f"{loc}: duration_actual_s is missing/non-finite")


def build_report(
    *,
    run_root: Path,
    manifest: Path,
    expected_shards: int,
    expected_prompts: int,
    expected_bon_n: int,
    metrics: tuple[str, ...],
    seed_base: int,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_map = _manifest_by_id(manifest)
    record_paths = _discover_records(run_root)
    if len(record_paths) != expected_shards:
        errors.append(f"expected {expected_shards} shard record files, found {len(record_paths)}")
    records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for path in record_paths:
        records.extend(_read_jsonl(path, errors))
        summary = _summary_for(path)
        if summary is None:
            errors.append(f"missing run_summary.json beside {path}")
        else:
            summaries.append(summary)
    seen_keys: set[tuple[str, str, int]] = set()
    seen_seeds: dict[int, tuple[str, int]] = {}
    duplicate_keys: list[tuple[str, str, int]] = []
    duplicate_seeds: list[tuple[int, tuple[str, int], tuple[str, int]]] = []
    by_prompt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    shard_counts: Counter = Counter()
    split_counts: Counter = Counter()
    vocal_counts: Counter = Counter()
    for row in records:
        _check_row(
            row,
            manifest_by_id=manifest_map,
            metrics=metrics,
            expected_bon_n=expected_bon_n,
            seed_base=seed_base,
            errors=errors,
            warnings=warnings,
        )
        if "prompt_id" not in row or "candidate_index" not in row or "prompt_source" not in row:
            continue
        pid = str(row["prompt_id"])
        cand = int(row["candidate_index"])
        key = (str(row["prompt_source"]), pid, cand)
        if key in seen_keys:
            duplicate_keys.append(key)
        seen_keys.add(key)
        seed = int(row.get("candidate_seed", -1))
        if seed in seen_seeds:
            duplicate_seeds.append((seed, seen_seeds[seed], (pid, cand)))
        seen_seeds[seed] = (pid, cand)
        by_prompt[pid].append(row)
        shard_counts[str(row.get("_source_shard"))] += 1
        split_counts[str(row.get("split"))] += 1
        vocal_counts[str(row.get("vocal_stratum"))] += 1
    if duplicate_keys:
        errors.append(f"duplicate candidate keys: {duplicate_keys[:8]} (n={len(duplicate_keys)})")
    if duplicate_seeds:
        errors.append(f"duplicate candidate seeds: {duplicate_seeds[:8]} (n={len(duplicate_seeds)})")

    complete_prompts = 0
    partial_prompts: dict[str, list[int]] = {}
    bad_candidate_sequences: dict[str, list[int]] = {}
    for pid, rows in by_prompt.items():
        indices = sorted(int(row["candidate_index"]) for row in rows)
        if len(indices) > expected_bon_n:
            bad_candidate_sequences[pid] = indices
            continue
        if indices == list(range(expected_bon_n)):
            complete_prompts += 1
        else:
            partial_prompts[pid] = indices
            if indices != list(range(len(indices))):
                bad_candidate_sequences[pid] = indices
    if bad_candidate_sequences:
        errors.append(
            "non-contiguous or overfull candidate sequences: "
            f"{dict(list(bad_candidate_sequences.items())[:8])} (n={len(bad_candidate_sequences)})"
        )
    observed_prompt_ids = set(by_prompt)
    extra_prompt_ids = sorted(observed_prompt_ids - set(manifest_map))
    if extra_prompt_ids:
        errors.append(f"observed prompt IDs outside manifest: {extra_prompt_ids[:8]}")
    if len(observed_prompt_ids) > expected_prompts:
        errors.append(f"observed {len(observed_prompt_ids)} prompts, exceeds expected {expected_prompts}")

    summary_errors = []
    summary_warnings = []
    for summary in summaries:
        label = summary.get("_summary_path")
        if int(summary.get("bon_n", -1)) != expected_bon_n:
            summary_errors.append(f"{label}: bon_n {summary.get('bon_n')!r} != {expected_bon_n}")
        if [float(x) for x in summary.get("target_sigmas", [])] != [0.9, 0.8, 0.7]:
            summary_errors.append(f"{label}: target_sigmas {summary.get('target_sigmas')!r} != [0.9, 0.8, 0.7]")
        if summary.get("gate_policy") != "configs/eval/gate_v2.yaml.draft":
            summary_errors.append(f"{label}: gate_policy {summary.get('gate_policy')!r} unexpected")
        for flag in SAFETY_FALSE_FLAGS:
            value = (summary.get("safety") or {}).get(flag)
            if value is not False:
                summary_errors.append(f"{label}: safety flag {flag} is not false: {value!r}")
        if summary.get("status") not in {"running", "PASS"}:
            summary_warnings.append(f"{label}: status {summary.get('status')!r}")
    errors.extend(summary_errors)
    warnings.extend(summary_warnings)

    status = "FAIL" if errors else ("PASS_PARTIAL_WITH_WARNINGS" if warnings else "PASS_PARTIAL")
    return {
        "schema_version": "early_tweedie_live_record_check_v1",
        "generated_at_utc": _now_utc(),
        "status": status,
        "run_root": str(run_root),
        "manifest": str(manifest),
        "expected_shards": expected_shards,
        "expected_prompts": expected_prompts,
        "expected_bon_n": expected_bon_n,
        "expected_final_records": expected_prompts * expected_bon_n,
        "n_record_paths": len(record_paths),
        "n_records": len(records),
        "n_prompts_observed": len(observed_prompt_ids),
        "n_complete_prompts": complete_prompts,
        "n_partial_prompts": len(partial_prompts),
        "partial_prompt_examples": dict(list(partial_prompts.items())[:12]),
        "shard_record_counts": {str(k): int(v) for k, v in sorted(shard_counts.items())},
        "split_record_counts": {str(k): int(v) for k, v in sorted(split_counts.items())},
        "vocal_record_counts": {str(k): int(v) for k, v in sorted(vocal_counts.items())},
        "record_paths": [str(path) for path in record_paths],
        "summary_count": len(summaries),
        "errors": errors,
        "warnings": warnings,
        "gpu_jobs_launched": 0,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Early-Tweedie Live Record Check",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        f"Status: `{report['status']}`",
        f"Run root: `{report['run_root']}`",
        f"GPU jobs launched by this check: `{report['gpu_jobs_launched']}`",
        "",
        "## Counts",
        "",
        f"- records: `{report['n_records']} / {report['expected_final_records']}`",
        f"- observed prompts: `{report['n_prompts_observed']} / {report['expected_prompts']}`",
        f"- complete prompts: `{report['n_complete_prompts']}`",
        f"- partial prompts: `{report['n_partial_prompts']}`",
        f"- shard record counts: `{report['shard_record_counts']}`",
        f"- split record counts: `{report['split_record_counts']}`",
        f"- vocal record counts: `{report['vocal_record_counts']}`",
        "",
        "## Partial Prompt Examples",
        "",
    ]
    if report["partial_prompt_examples"]:
        for pid, indices in report["partial_prompt_examples"].items():
            lines.append(f"- `{pid}`: `{indices}`")
    else:
        lines.append("No partial prompts observed.")
    lines.extend(["", "## Errors", ""])
    if report["errors"]:
        for error in report["errors"][:30]:
            lines.append(f"- {error}")
        if len(report["errors"]) > 30:
            lines.append(f"- ... {len(report['errors']) - 30} more")
    else:
        lines.append("None.")
    lines.extend(["", "## Warnings", ""])
    if report["warnings"]:
        for warning in report["warnings"][:30]:
            lines.append(f"- {warning}")
        if len(report["warnings"]) > 30:
            lines.append(f"- ... {len(report['warnings']) - 30} more")
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a partial live check. It validates written records only and does not replace the final merge and independent verifier.",
            "A `PASS_PARTIAL*` status means no structural issue has been found in records written so far.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--expected-shards", type=int, default=8)
    parser.add_argument("--expected-prompts", type=int, default=512)
    parser.add_argument("--expected-bon-n", type=int, default=8)
    parser.add_argument("--metrics", nargs="*", default=list(DEFAULT_METRICS))
    parser.add_argument("--seed-base", type=int, default=2026052700)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    report = build_report(
        run_root=args.run_root,
        manifest=args.manifest,
        expected_shards=int(args.expected_shards),
        expected_prompts=int(args.expected_prompts),
        expected_bon_n=int(args.expected_bon_n),
        metrics=tuple(str(x) for x in args.metrics),
        seed_base=int(args.seed_base),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(_markdown(report), encoding="utf-8")
    print(args.output_json)
    print(args.output_md)
    if report["status"] == "FAIL":
        return 1
    if args.fail_on_warning and report["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
