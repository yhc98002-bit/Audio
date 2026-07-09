"""Independently verify Early-Tweedie pruning validation outputs.

This verifier is CPU-only and read-only with respect to run artifacts. It does
not import the merge script; it re-computes schedule and retention tables from
candidate_records.jsonl and compares them with the published JSON/CSV outputs.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SIGMA_STEPS = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
EXPECTED_STEP_INDEX = {"0.9": 7, "0.8": 12, "0.7": 16}
FULL_STEPS = 30.0
DEFAULT_METRICS = ("common_robust_lcb", "aesthetic_pq", "semantic_fit", "lyric_intelligibility")
DEFAULT_STRATA = ("all", "vocal", "instrumental")
DEFAULT_DIAGNOSTIC_STRATA = ("split:dev", "split:held_out")
SCHEDULES = (
    "full_bon8",
    "schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1",
    "schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1",
    "schedule_c_sigma0.8_keep_top6_final_top1",
    "bottom_prune_sigma0.8_remove_bottom25_final_top1",
    "bottom_prune_sigma0.7_remove_bottom25_final_top1",
    "random_prune_keep4_keep2_final_top1",
)
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


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_no}: invalid JSONL row: {exc}") from exc
            row["_source_record_path"] = str(path)
            row["_source_record_line"] = line_no
            rows.append(row)
    return rows


def _read_records(paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
        out.extend(_read_jsonl(path))
    return out


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _discover_records(run_root: Path) -> list[Path]:
    return sorted(run_root.glob("shard*/candidate_records.jsonl"))


def _discover_summaries(record_paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record_path in record_paths:
        summary_path = record_path.parent / "run_summary.json"
        if summary_path.exists():
            summary = _read_json(summary_path)
            summary["_summary_path"] = str(summary_path)
            out.append(summary)
    return out


def _finite(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _mean(xs: list[float]) -> float | None:
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.mean(xs) if xs else None


def _median(xs: list[float]) -> float | None:
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(xs) if xs else None


def _rank_desc(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda row: (
            _finite(row.get(key)) if _finite(row.get(key)) is not None else float("-inf"),
            -int(row["candidate_index"]),
        ),
        reverse=True,
    )


def _bottom(items: list[dict[str, Any]], key: str, fraction: float) -> list[dict[str, Any]]:
    ordered = sorted(
        items,
        key=lambda row: (
            _finite(row.get(key)) if _finite(row.get(key)) is not None else float("inf"),
            int(row["candidate_index"]),
        ),
    )
    n = max(1, int(math.ceil(len(ordered) * fraction)))
    return ordered[:n]


def _compute_fraction(schedule: str) -> float:
    if schedule == "full_bon8":
        return 1.0
    if schedule == "schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1":
        return (8 * SIGMA_STEPS["0.9"] + 4 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.9"]) + 2 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if schedule == "schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1":
        return (8 * SIGMA_STEPS["0.8"] + 4 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.8"]) + 2 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if schedule in {
        "schedule_c_sigma0.8_keep_top6_final_top1",
        "bottom_prune_sigma0.8_remove_bottom25_final_top1",
    }:
        return (8 * SIGMA_STEPS["0.8"] + 6 * (FULL_STEPS - SIGMA_STEPS["0.8"])) / (8 * FULL_STEPS)
    if schedule == "bottom_prune_sigma0.7_remove_bottom25_final_top1":
        return (8 * SIGMA_STEPS["0.7"] + 6 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if schedule == "random_prune_keep4_keep2_final_top1":
        return _compute_fraction("schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1")
    raise KeyError(schedule)


def _stratum_rows(records: list[dict[str, Any]], stratum: str) -> list[dict[str, Any]]:
    if stratum == "all":
        return records
    if stratum == "vocal":
        return [r for r in records if r.get("vocal_stratum") == "vocal"]
    if stratum == "instrumental":
        return [r for r in records if r.get("vocal_stratum") == "instrumental"]
    if stratum.startswith("split:"):
        split = stratum.split(":", 1)[1]
        return [r for r in records if r.get("split") == split]
    raise KeyError(stratum)


def _select_survivors(
    rows: list[dict[str, Any]],
    *,
    metric: str,
    schedule: str,
    rng: random.Random,
) -> list[dict[str, Any]] | None:
    if schedule == "full_bon8":
        return rows
    if schedule == "schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1":
        k09 = f"early_0.9_{metric}"
        k07 = f"early_0.7_{metric}"
        if any(_finite(r.get(k09)) is None or _finite(r.get(k07)) is None for r in rows):
            return None
        keep4 = _rank_desc(rows, k09)[:4]
        return _rank_desc(keep4, k07)[:2]
    if schedule == "schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1":
        k08 = f"early_0.8_{metric}"
        k07 = f"early_0.7_{metric}"
        if any(_finite(r.get(k08)) is None or _finite(r.get(k07)) is None for r in rows):
            return None
        keep4 = _rank_desc(rows, k08)[:4]
        return _rank_desc(keep4, k07)[:2]
    if schedule == "schedule_c_sigma0.8_keep_top6_final_top1":
        k08 = f"early_0.8_{metric}"
        if any(_finite(r.get(k08)) is None for r in rows):
            return None
        return _rank_desc(rows, k08)[:6]
    if schedule == "bottom_prune_sigma0.8_remove_bottom25_final_top1":
        k08 = f"early_0.8_{metric}"
        if any(_finite(r.get(k08)) is None for r in rows):
            return None
        pruned = {int(r["candidate_index"]) for r in _bottom(rows, k08, 0.25)}
        return [r for r in rows if int(r["candidate_index"]) not in pruned]
    if schedule == "bottom_prune_sigma0.7_remove_bottom25_final_top1":
        k07 = f"early_0.7_{metric}"
        if any(_finite(r.get(k07)) is None for r in rows):
            return None
        pruned = {int(r["candidate_index"]) for r in _bottom(rows, k07, 0.25)}
        return [r for r in rows if int(r["candidate_index"]) not in pruned]
    if schedule == "random_prune_keep4_keep2_final_top1":
        ordered = sorted(rows, key=lambda r: int(r["candidate_index"]))
        keep4 = rng.sample(ordered, min(4, len(ordered)))
        return rng.sample(keep4, min(2, len(keep4)))
    raise KeyError(schedule)


def _group_by_prompt(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        out.setdefault(str(row["prompt_id"]), []).append(row)
    return out


def _analyze(
    records: list[dict[str, Any]],
    *,
    metrics: tuple[str, ...],
    strata: tuple[str, ...],
    expected_bon_n: int,
    random_seed: int,
    random_repeats: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schedule_rows: list[dict[str, Any]] = []
    retention_rows: list[dict[str, Any]] = []

    for stratum in strata:
        subset = _stratum_rows(records, stratum)
        by_prompt = _group_by_prompt(subset)
        complete_prompts = {
            pid: sorted(rows, key=lambda r: int(r["candidate_index"]))
            for pid, rows in by_prompt.items()
            if len(rows) == expected_bon_n
        }
        for metric in metrics:
            final_key = f"final_{metric}"
            full_scores: list[float] = []
            full_winners: dict[str, dict[str, Any]] = {}
            for pid, rows in complete_prompts.items():
                if any(_finite(r.get(final_key)) is None for r in rows):
                    continue
                ranked = _rank_desc(rows, final_key)
                full_winners[pid] = ranked[0]
                full_scores.append(float(ranked[0][final_key]))
            full_mean = _mean(full_scores)
            for sigma in ("0.9", "0.8", "0.7"):
                early_key = f"early_{sigma}_{metric}"
                n = top1 = top2 = top4 = bottom25_fn = 0
                for pid, rows in complete_prompts.items():
                    if pid not in full_winners or any(_finite(r.get(early_key)) is None for r in rows):
                        continue
                    winner = int(full_winners[pid]["candidate_index"])
                    order = [int(r["candidate_index"]) for r in _rank_desc(rows, early_key)]
                    bottom25 = {int(r["candidate_index"]) for r in _bottom(rows, early_key, 0.25)}
                    n += 1
                    top1 += int(winner in set(order[:1]))
                    top2 += int(winner in set(order[:2]))
                    top4 += int(winner in set(order[:4]))
                    bottom25_fn += int(winner in bottom25)
                retention_rows.append(
                    {
                        "metric": metric,
                        "stratum": stratum,
                        "sigma": sigma,
                        "n_prompts": n,
                        "winner_retention_top1": top1 / n if n else None,
                        "winner_retention_top2": top2 / n if n else None,
                        "winner_retention_top4": top4 / n if n else None,
                        "bottom25_false_negative": bottom25_fn / n if n else None,
                    }
                )
            for schedule in SCHEDULES:
                selected_scores: list[float] = []
                regrets: list[float] = []
                winner_match = 0
                false_negative = 0
                n = 0
                repeats = random_repeats if schedule.startswith("random_") else 1
                for repeat in range(repeats):
                    rng = random.Random(random_seed + repeat)
                    for pid, rows in complete_prompts.items():
                        if pid not in full_winners or any(_finite(r.get(final_key)) is None for r in rows):
                            continue
                        survivors = _select_survivors(rows, metric=metric, schedule=schedule, rng=rng)
                        if survivors is None:
                            continue
                        full_winner = full_winners[pid]
                        survivor_ids = {int(r["candidate_index"]) for r in survivors}
                        selected = _rank_desc(survivors, final_key)[0]
                        full_score = float(full_winner[final_key])
                        selected_score = float(selected[final_key])
                        n += 1
                        winner_match += int(int(selected["candidate_index"]) == int(full_winner["candidate_index"]))
                        false_negative += int(int(full_winner["candidate_index"]) not in survivor_ids)
                        selected_scores.append(selected_score)
                        regrets.append(full_score - selected_score)
                selected_mean = _mean(selected_scores)
                schedule_rows.append(
                    {
                        "schedule": schedule,
                        "compute_fraction": _compute_fraction(schedule),
                        "metric": metric,
                        "reward_fraction": (
                            selected_mean / full_mean
                            if selected_mean is not None and full_mean not in (None, 0.0)
                            else None
                        ),
                        "winner_match": winner_match / n if n else None,
                        "false_negative": false_negative / n if n else None,
                        "stratum": stratum,
                        "n_prompts": n,
                        "mean_selected_reward": selected_mean,
                        "mean_full_bon8_reward": full_mean,
                        "mean_regret": _mean(regrets),
                        "median_regret": _median(regrets),
                    }
                )
    return schedule_rows, retention_rows


def _index_schedule_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (str(r.get("schedule")), str(r.get("metric")), str(r.get("stratum"))): r
        for r in rows
    }


def _index_retention_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (str(r.get("metric")), str(r.get("stratum")), str(r.get("sigma"))): r
        for r in rows
    }


def _normalize_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if value == "":
            out[key] = None
            continue
        numeric = _finite(value)
        out[key] = numeric if numeric is not None else value
    return out


def _close_enough(a: Any, b: Any, tol: float) -> bool:
    fa = _finite(a)
    fb = _finite(b)
    if fa is None or fb is None:
        return a in ("", None) and b in ("", None)
    return abs(fa - fb) <= tol


def _compare_row_sets(
    *,
    label: str,
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    indexer: Any,
    numeric_fields: tuple[str, ...],
    errors: list[str],
    tol: float,
) -> None:
    expected_idx = indexer(expected)
    actual_idx = indexer(actual)
    missing = sorted(set(expected_idx) - set(actual_idx))
    extra = sorted(set(actual_idx) - set(expected_idx))
    if missing:
        errors.append(f"{label}: missing rows for keys {missing[:8]} (n={len(missing)})")
    if extra:
        errors.append(f"{label}: extra rows for keys {extra[:8]} (n={len(extra)})")
    for key in sorted(set(expected_idx) & set(actual_idx)):
        exp = expected_idx[key]
        got = actual_idx[key]
        for field in numeric_fields:
            if not _close_enough(exp.get(field), got.get(field), tol):
                errors.append(
                    f"{label}: {key} field {field} mismatch: "
                    f"expected {exp.get(field)!r}, got {got.get(field)!r}"
                )


def _manifest_maps(manifest: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Counter]]:
    prompts = manifest.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise RuntimeError("manifest missing non-empty prompts list")
    by_id: dict[str, dict[str, Any]] = {}
    counts = {"split": Counter(), "vocal_stratum": Counter()}
    for row in prompts:
        pid = str(row["prompt_id"])
        if pid in by_id:
            raise RuntimeError(f"manifest duplicate prompt_id: {pid}")
        by_id[pid] = row
        counts["split"][str(row.get("split"))] += 1
        vocal = row.get("vocal_stratum") or (row.get("strata") or {}).get("vocal_vs_instrumental")
        counts["vocal_stratum"][str(vocal)] += 1
    return by_id, counts


def _counter_dict(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in sorted(counter.items())}


def _check_records(
    *,
    records: list[dict[str, Any]],
    manifest_by_id: dict[str, dict[str, Any]],
    metrics: tuple[str, ...],
    expected_bon_n: int,
    expected_prompts: int | None,
    allow_subset: bool,
    seed_base: int,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    duplicate_keys = []
    seen_keys: set[tuple[str, str, int]] = set()
    seen_seeds: dict[int, tuple[str, int]] = {}
    duplicate_seeds = []
    missing_metric_examples: list[str] = []
    sigma_step_mismatches: list[str] = []
    seed_mismatches: list[str] = []
    prompt_ids: set[str] = set()
    record_split_counts: Counter = Counter()
    record_vocal_counts: Counter = Counter()
    by_prompt: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in records:
        try:
            pid = str(row["prompt_id"])
            source = str(row["prompt_source"])
            cand = int(row["candidate_index"])
        except KeyError as exc:
            errors.append(f"record missing required key {exc}: {row.get('_source_record_path')}:{row.get('_source_record_line')}")
            continue
        key = (source, pid, cand)
        if key in seen_keys:
            duplicate_keys.append(key)
        seen_keys.add(key)
        prompt_ids.add(pid)
        by_prompt[pid].append(row)
        record_split_counts[str(row.get("split"))] += 1
        record_vocal_counts[str(row.get("vocal_stratum"))] += 1

        seed = row.get("candidate_seed")
        if seed is not None:
            seed_int = int(seed)
            if seed_int in seen_seeds:
                duplicate_seeds.append((seed_int, seen_seeds[seed_int], (pid, cand)))
            seen_seeds[seed_int] = (pid, cand)
            manifest_index = int(row.get("manifest_index", -1))
            expected_seed = seed_base + manifest_index * 1000 + cand
            if seed_int != expected_seed and len(seed_mismatches) < 10:
                seed_mismatches.append(f"{pid}/cand{cand}: seed {seed_int} != expected {expected_seed}")

        manifest_row = manifest_by_id.get(pid)
        if manifest_row is None:
            errors.append(f"record prompt_id {pid} is absent from manifest")
        else:
            if str(row.get("split")) != str(manifest_row.get("split")):
                errors.append(f"{pid}: record split {row.get('split')!r} != manifest split {manifest_row.get('split')!r}")
            manifest_vocal = manifest_row.get("vocal_stratum") or (manifest_row.get("strata") or {}).get("vocal_vs_instrumental")
            if str(row.get("vocal_stratum")) != str(manifest_vocal):
                errors.append(f"{pid}: record vocal_stratum {row.get('vocal_stratum')!r} != manifest {manifest_vocal!r}")

        for metric in metrics:
            required_keys = [f"final_{metric}"] + [f"early_{sigma}_{metric}" for sigma in ("0.9", "0.8", "0.7")]
            for metric_key in required_keys:
                if _finite(row.get(metric_key)) is None and len(missing_metric_examples) < 12:
                    missing_metric_examples.append(f"{pid}/cand{cand}:{metric_key}")
        for sigma, expected_step in EXPECTED_STEP_INDEX.items():
            step_key = f"early_{sigma}_step_index"
            actual_sigma_key = f"early_{sigma}_actual_sigma"
            if int(row.get(step_key, -1)) != expected_step and len(sigma_step_mismatches) < 12:
                sigma_step_mismatches.append(f"{pid}/cand{cand}:{step_key}={row.get(step_key)!r}")
            actual_sigma = _finite(row.get(actual_sigma_key))
            if actual_sigma is None or abs(actual_sigma - float(sigma)) > 0.025:
                if len(sigma_step_mismatches) < 12:
                    sigma_step_mismatches.append(f"{pid}/cand{cand}:{actual_sigma_key}={row.get(actual_sigma_key)!r}")

    if duplicate_keys:
        errors.append(f"duplicate candidate keys found: {duplicate_keys[:8]} (n={len(duplicate_keys)})")
    if duplicate_seeds:
        errors.append(f"duplicate candidate seeds found: {duplicate_seeds[:8]} (n={len(duplicate_seeds)})")
    if seed_mismatches:
        errors.append(f"candidate_seed formula mismatches: {seed_mismatches}")
    if missing_metric_examples:
        errors.append(f"missing/non-finite required metric fields: {missing_metric_examples}")
    if sigma_step_mismatches:
        errors.append(f"early sigma/step mismatches: {sigma_step_mismatches}")

    incomplete: dict[str, list[int]] = {}
    expected_indices = list(range(expected_bon_n))
    for pid, rows in by_prompt.items():
        indices = sorted(int(r["candidate_index"]) for r in rows)
        if indices != expected_indices:
            incomplete[pid] = indices
    if incomplete:
        examples = dict(list(incomplete.items())[:8])
        errors.append(f"prompts without exact candidate indices {expected_indices}: {examples} (n={len(incomplete)})")

    if expected_prompts is not None and len(prompt_ids) != expected_prompts:
        msg = f"observed {len(prompt_ids)} prompts, expected {expected_prompts}"
        if allow_subset and len(prompt_ids) < expected_prompts:
            warnings.append(msg)
        else:
            errors.append(msg)
    expected_records = (expected_prompts or len(prompt_ids)) * expected_bon_n
    if len(records) != expected_records:
        msg = f"observed {len(records)} records, expected {expected_records}"
        if allow_subset and expected_prompts is not None and len(records) < expected_records:
            warnings.append(msg)
        else:
            errors.append(msg)
    if allow_subset and not prompt_ids.issubset(manifest_by_id):
        errors.append("subset records include prompt IDs outside manifest")
    if not allow_subset and prompt_ids != set(manifest_by_id):
        missing = sorted(set(manifest_by_id) - prompt_ids)
        extra = sorted(prompt_ids - set(manifest_by_id))
        errors.append(f"observed prompt IDs do not equal manifest: missing={missing[:8]} extra={extra[:8]}")

    prompt_split_counts = Counter()
    prompt_vocal_counts = Counter()
    for pid in prompt_ids:
        row = manifest_by_id.get(pid)
        if row:
            prompt_split_counts[str(row.get("split"))] += 1
            vocal = row.get("vocal_stratum") or (row.get("strata") or {}).get("vocal_vs_instrumental")
            prompt_vocal_counts[str(vocal)] += 1

    return {
        "n_records": len(records),
        "n_prompts": len(prompt_ids),
        "prompt_split_counts": _counter_dict(prompt_split_counts),
        "prompt_vocal_stratum_counts": _counter_dict(prompt_vocal_counts),
        "record_split_counts": _counter_dict(record_split_counts),
        "record_vocal_stratum_counts": _counter_dict(record_vocal_counts),
        "candidate_indices_expected": expected_indices,
    }


def _check_payload_metadata(
    *,
    payload: dict[str, Any],
    record_paths: list[Path],
    summaries: list[dict[str, Any]],
    run_root: Path | None,
    manifest: Path,
    expected_bon_n: int,
    observed_counts: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    tol: float,
    allow_missing_logs: bool,
    allow_subset: bool,
) -> None:
    if payload.get("schema_version") != "early_tweedie_pruning_validation_merge_v1":
        errors.append(f"unexpected validation schema_version: {payload.get('schema_version')!r}")
    if str(payload.get("manifest")) != str(manifest):
        errors.append(f"payload manifest {payload.get('manifest')!r} != expected {str(manifest)!r}")
    if run_root is not None and str(payload.get("run_root")) != str(run_root):
        errors.append(f"payload run_root {payload.get('run_root')!r} != expected {str(run_root)!r}")
    if int(payload.get("bon_n", -1)) != expected_bon_n:
        errors.append(f"payload bon_n {payload.get('bon_n')!r} != expected {expected_bon_n}")
    if int(payload.get("n_prompts", -1)) != int(observed_counts["n_prompts"]):
        errors.append(f"payload n_prompts {payload.get('n_prompts')!r} != observed {observed_counts['n_prompts']}")
    if int(payload.get("n_candidates", -1)) != int(observed_counts["n_records"]):
        errors.append(f"payload n_candidates {payload.get('n_candidates')!r} != observed {observed_counts['n_records']}")

    payload_record_paths = [str(p) for p in payload.get("record_paths", [])]
    expected_record_paths = [str(p) for p in record_paths]
    if payload_record_paths != expected_record_paths:
        errors.append(f"payload record_paths != provided records: {payload_record_paths!r} vs {expected_record_paths!r}")

    safety = payload.get("safety") or {}
    for flag in SAFETY_FALSE_FLAGS:
        if safety.get(flag) is not False:
            errors.append(f"payload safety flag {flag} is not false: {safety.get(flag)!r}")

    if summaries:
        sum_records = 0
        sum_gpu_hours = 0.0
        for summary in summaries:
            if summary.get("status") != "PASS":
                errors.append(f"{summary.get('_summary_path')}: status is not PASS: {summary.get('status')!r}")
            if int(summary.get("bon_n", -1)) != expected_bon_n:
                errors.append(f"{summary.get('_summary_path')}: bon_n {summary.get('bon_n')!r} != {expected_bon_n}")
            if [float(x) for x in summary.get("target_sigmas", [])] != [0.9, 0.8, 0.7]:
                errors.append(f"{summary.get('_summary_path')}: target_sigmas {summary.get('target_sigmas')!r} != [0.9, 0.8, 0.7]")
            if summary.get("gate_policy") != "configs/eval/gate_v2.yaml.draft":
                errors.append(f"{summary.get('_summary_path')}: gate_policy {summary.get('gate_policy')!r} is unexpected")
            for flag in SAFETY_FALSE_FLAGS:
                if (summary.get("safety") or {}).get(flag) is not False:
                    errors.append(f"{summary.get('_summary_path')}: safety flag {flag} is not false")
            sum_records += int(summary.get("n_candidate_records") or 0)
            sum_gpu_hours += float(summary.get("gpu_hours_consumed") or 0.0)
        if sum_records != int(observed_counts["n_records"]):
            errors.append(f"run summaries n_candidate_records sum {sum_records} != observed {observed_counts['n_records']}")
        if not _close_enough(payload.get("gpu_hours_actual_sum"), sum_gpu_hours, tol):
            errors.append(f"payload gpu_hours_actual_sum {payload.get('gpu_hours_actual_sum')!r} != summary sum {sum_gpu_hours!r}")
    else:
        warnings.append("no shard run_summary.json files found beside record paths")

    for log_path in payload.get("shard_logs", []):
        if not Path(log_path).exists():
            msg = f"payload shard log path is missing: {log_path}"
            if allow_missing_logs:
                warnings.append(msg)
            else:
                errors.append(msg)

    if run_root is not None:
        launcher_exit = run_root / "launcher.exit"
        launch_finished = run_root / "launch_finished_utc.txt"
        if launcher_exit.exists():
            code = launcher_exit.read_text(encoding="utf-8").strip()
            if code != "0":
                errors.append(f"{launcher_exit}: launcher exit code is {code!r}, expected '0'")
        elif allow_subset:
            warnings.append(f"{launcher_exit}: missing launcher exit file in subset/smoke mode")
        else:
            errors.append(f"{launcher_exit}: missing launcher exit file")
        if not launch_finished.exists():
            msg = f"{launch_finished}: missing launch completion timestamp"
            if allow_subset:
                warnings.append(msg)
            else:
                errors.append(msg)


def _check_bottom_prune_consistency(
    schedule_rows: list[dict[str, Any]],
    retention_rows: list[dict[str, Any]],
    errors: list[str],
    tol: float,
) -> None:
    retention_idx = _index_retention_rows(retention_rows)
    for row in schedule_rows:
        schedule = row.get("schedule")
        sigma = None
        if schedule == "bottom_prune_sigma0.8_remove_bottom25_final_top1":
            sigma = "0.8"
        elif schedule == "bottom_prune_sigma0.7_remove_bottom25_final_top1":
            sigma = "0.7"
        if sigma is None:
            continue
        key = (str(row.get("metric")), str(row.get("stratum")), sigma)
        retention = retention_idx.get(key)
        if not retention:
            errors.append(f"missing retention row for bottom-prune consistency key {key}")
            continue
        if not _close_enough(row.get("false_negative"), retention.get("bottom25_false_negative"), tol):
            errors.append(
                f"bottom-prune false_negative mismatch for {key}: "
                f"schedule={row.get('false_negative')!r}, retention={retention.get('bottom25_false_negative')!r}"
            )


def _extract_key_metrics(schedule_rows: list[dict[str, Any]], retention_rows: list[dict[str, Any]]) -> dict[str, Any]:
    robust_all = [
        r for r in schedule_rows
        if r.get("metric") == "common_robust_lcb" and r.get("stratum") == "all"
    ]
    robust_retention = [
        r for r in retention_rows
        if r.get("metric") == "common_robust_lcb" and r.get("stratum") == "all"
    ]
    return {
        "robust_common_all_schedules": robust_all,
        "robust_common_all_retention": robust_retention,
        "strong_candidate_threshold": {
            "reward_fraction_min": 0.98,
            "compute_fraction_max": 0.5,
            "bottom_prune_false_negative_max": 0.05,
        },
    }


def _constant_metric_diagnostics(
    records: list[dict[str, Any]],
    *,
    metrics: tuple[str, ...],
    strata: tuple[str, ...],
    expected_bon_n: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    warned: set[tuple[str, str, str]] = set()
    for stratum in strata:
        by_prompt = _group_by_prompt(_stratum_rows(records, stratum))
        complete_prompts = {
            pid: rows
            for pid, rows in by_prompt.items()
            if len(rows) == expected_bon_n
        }
        for metric in metrics:
            for prefix in ("final", "early_0.9", "early_0.8", "early_0.7"):
                key = f"{prefix}_{metric}"
                n_evaluable = 0
                n_constant = 0
                examples: list[str] = []
                for pid, rows in complete_prompts.items():
                    values = [_finite(r.get(key)) for r in rows]
                    if any(v is None for v in values):
                        continue
                    n_evaluable += 1
                    unique_values = {round(float(v), 12) for v in values if v is not None}
                    if len(unique_values) <= 1:
                        n_constant += 1
                        if len(examples) < 5:
                            examples.append(pid)
                fraction = n_constant / n_evaluable if n_evaluable else None
                diagnostics.append(
                    {
                        "stratum": stratum,
                        "metric": metric,
                        "score_prefix": prefix,
                        "n_evaluable_prompts": n_evaluable,
                        "n_constant_prompts": n_constant,
                        "constant_prompt_fraction": fraction,
                        "examples": examples,
                    }
                )
                if fraction is not None and fraction >= 0.2:
                    warn_key = (stratum, metric, prefix)
                    if warn_key not in warned:
                        warnings.append(
                            f"{stratum}/{metric}/{prefix}: {n_constant}/{n_evaluable} prompts have "
                            "constant candidate scores; tie-driven retention/false-negative rows may be "
                            "diagnostic only, especially for lyric_intelligibility."
                        )
                        warned.add(warn_key)
    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, nargs="*", help="candidate_records.jsonl files. If omitted, --run-root/shard*/candidate_records.jsonl is used.")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--validation-json", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json"))
    parser.add_argument("--plot-csv", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv"))
    parser.add_argument("--retention-csv", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"))
    parser.add_argument("--expected-bon-n", type=int, default=8)
    parser.add_argument("--expected-prompts", type=int, default=None)
    parser.add_argument("--expected-shards", type=int, default=8)
    parser.add_argument("--allow-subset", action="store_true", help="Allow fewer than manifest/expected prompts; intended for smoke verification only.")
    parser.add_argument("--allow-missing-logs", action="store_true", help="Downgrade missing payload shard logs to warnings; intended for ad hoc smoke artifacts only.")
    parser.add_argument("--seed-base", type=int, default=2026052700)
    parser.add_argument("--random-seed", type=int, default=20260527)
    parser.add_argument("--random-repeats", type=int, default=20)
    parser.add_argument("--diagnostic-strata", nargs="*", default=list(DEFAULT_DIAGNOSTIC_STRATA))
    parser.add_argument("--float-tol", type=float, default=1.0e-9)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    if args.records:
        record_paths = sorted(args.records)
    elif args.run_root:
        record_paths = _discover_records(args.run_root)
    else:
        raise SystemExit("either --records or --run-root is required")
    if not record_paths:
        raise SystemExit("no candidate_records.jsonl files found")
    if args.expected_shards is not None and len(record_paths) != args.expected_shards:
        msg = f"observed {len(record_paths)} record shards, expected {args.expected_shards}"
        if args.allow_subset and len(record_paths) < args.expected_shards:
            warnings.append(msg)
        else:
            errors.append(msg)

    for path in [args.validation_json, args.plot_csv, args.retention_csv, args.manifest, *record_paths]:
        if not path.exists():
            errors.append(f"required path does not exist: {path}")
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2), file=sys.stderr)
        return 1

    payload = _read_json(args.validation_json)
    plot_csv_rows = [_normalize_csv_row(row) for row in _read_csv(args.plot_csv)]
    retention_csv_rows = [_normalize_csv_row(row) for row in _read_csv(args.retention_csv)]
    manifest = _read_json(args.manifest)
    manifest_by_id, manifest_counts = _manifest_maps(manifest)
    records = _read_records(record_paths)
    summaries = _discover_summaries(record_paths)

    metrics = tuple(payload.get("metrics") or DEFAULT_METRICS)
    strata = tuple(payload.get("strata") or DEFAULT_STRATA)
    expected_prompts = args.expected_prompts
    if expected_prompts is None:
        expected_prompts = None if args.allow_subset else len(manifest_by_id)

    observed_counts = _check_records(
        records=records,
        manifest_by_id=manifest_by_id,
        metrics=metrics,
        expected_bon_n=args.expected_bon_n,
        expected_prompts=expected_prompts,
        allow_subset=args.allow_subset,
        seed_base=args.seed_base,
        errors=errors,
        warnings=warnings,
    )

    _check_payload_metadata(
        payload=payload,
        record_paths=record_paths,
        summaries=summaries,
        run_root=args.run_root,
        manifest=args.manifest,
        expected_bon_n=args.expected_bon_n,
        observed_counts=observed_counts,
        errors=errors,
        warnings=warnings,
        tol=args.float_tol,
        allow_missing_logs=args.allow_missing_logs,
        allow_subset=args.allow_subset,
    )

    recomputed_schedule, recomputed_retention = _analyze(
        records,
        metrics=metrics,
        strata=strata,
        expected_bon_n=args.expected_bon_n,
        random_seed=args.random_seed,
        random_repeats=args.random_repeats,
    )
    payload_schedule = payload.get("schedule_rows") or []
    payload_retention = payload.get("retention_rows") or []

    schedule_numeric_fields = (
        "compute_fraction",
        "reward_fraction",
        "winner_match",
        "false_negative",
        "n_prompts",
        "mean_selected_reward",
        "mean_full_bon8_reward",
        "mean_regret",
        "median_regret",
    )
    retention_numeric_fields = (
        "n_prompts",
        "winner_retention_top1",
        "winner_retention_top2",
        "winner_retention_top4",
        "bottom25_false_negative",
    )
    _compare_row_sets(
        label="payload schedule_rows vs recomputed",
        expected=recomputed_schedule,
        actual=payload_schedule,
        indexer=_index_schedule_rows,
        numeric_fields=schedule_numeric_fields,
        errors=errors,
        tol=args.float_tol,
    )
    _compare_row_sets(
        label="plot CSV vs recomputed schedule rows",
        expected=recomputed_schedule,
        actual=plot_csv_rows,
        indexer=_index_schedule_rows,
        numeric_fields=schedule_numeric_fields,
        errors=errors,
        tol=args.float_tol,
    )
    _compare_row_sets(
        label="payload retention_rows vs recomputed",
        expected=recomputed_retention,
        actual=payload_retention,
        indexer=_index_retention_rows,
        numeric_fields=retention_numeric_fields,
        errors=errors,
        tol=args.float_tol,
    )
    _compare_row_sets(
        label="retention CSV vs recomputed retention rows",
        expected=recomputed_retention,
        actual=retention_csv_rows,
        indexer=_index_retention_rows,
        numeric_fields=retention_numeric_fields,
        errors=errors,
        tol=args.float_tol,
    )
    _check_bottom_prune_consistency(recomputed_schedule, recomputed_retention, errors, args.float_tol)
    diagnostic_schedule: list[dict[str, Any]] = []
    diagnostic_retention: list[dict[str, Any]] = []
    if args.diagnostic_strata:
        diagnostic_schedule, diagnostic_retention = _analyze(
            records,
            metrics=metrics,
            strata=tuple(args.diagnostic_strata),
            expected_bon_n=args.expected_bon_n,
            random_seed=args.random_seed,
            random_repeats=args.random_repeats,
        )
    constant_metric_diagnostics = _constant_metric_diagnostics(
        records,
        metrics=metrics,
        strata=tuple(dict.fromkeys([*strata, *tuple(args.diagnostic_strata or [])])),
        expected_bon_n=args.expected_bon_n,
        warnings=warnings,
    )

    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    report = {
        "schema_version": "early_tweedie_validation_independent_verification_v1",
        "generated_at_utc": _now_utc(),
        "status": status,
        "command": " ".join(sys.argv),
        "inputs": {
            "records": [str(p) for p in record_paths],
            "run_root": str(args.run_root) if args.run_root else None,
            "validation_json": str(args.validation_json),
            "plot_csv": str(args.plot_csv),
            "retention_csv": str(args.retention_csv),
            "manifest": str(args.manifest),
            "expected_bon_n": args.expected_bon_n,
            "expected_prompts": expected_prompts,
            "expected_shards": args.expected_shards,
            "allow_subset": args.allow_subset,
            "allow_missing_logs": args.allow_missing_logs,
            "random_seed": args.random_seed,
            "random_repeats": args.random_repeats,
            "diagnostic_strata": list(args.diagnostic_strata or []),
            "seed_base": args.seed_base,
        },
        "counts": {
            "manifest_n_prompts": len(manifest_by_id),
            "manifest_split_counts": _counter_dict(manifest_counts["split"]),
            "manifest_vocal_stratum_counts": _counter_dict(manifest_counts["vocal_stratum"]),
            **observed_counts,
        },
        "warnings": warnings,
        "errors": errors,
        "key_metrics": _extract_key_metrics(recomputed_schedule, recomputed_retention),
        "diagnostics": {
            "split_schedule_rows": diagnostic_schedule,
            "split_retention_rows": diagnostic_retention,
            "constant_metric_prompt_counts": constant_metric_diagnostics,
            "tie_breaking_note": (
                "Verifier intentionally mirrors the merge tie-breakers so JSON/CSV equality can be "
                "checked. Rows for metrics that are constant across candidates can have tie-driven "
                "winner retention and false-negative values and should not be interpreted as pruning "
                "quality evidence."
            ),
        },
    }

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
