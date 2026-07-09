"""Merge Early-Tweedie validation shards and compute pruning schedule tables."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import time
from pathlib import Path
from typing import Any


SIGMA_STEPS = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
FULL_STEPS = 30.0
DEFAULT_METRICS = ("common_robust_lcb", "aesthetic_pq", "semantic_fit", "lyric_intelligibility")
DEFAULT_STRATA = ("all", "vocal", "instrumental")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_records(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def _read_summaries(paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
        summary = path.parent / "run_summary.json" if path.name == "candidate_records.jsonl" else path
        if summary.exists() and summary.name == "run_summary.json":
            out.append(json.loads(summary.read_text(encoding="utf-8")))
    return out


def _finite(value: Any) -> float | None:
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
    schedules = (
        "full_bon8",
        "schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1",
        "schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1",
        "schedule_c_sigma0.8_keep_top6_final_top1",
        "bottom_prune_sigma0.8_remove_bottom25_final_top1",
        "bottom_prune_sigma0.7_remove_bottom25_final_top1",
        "random_prune_keep4_keep2_final_top1",
    )
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
            for schedule in schedules:
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = [
        "schedule",
        "compute_fraction",
        "metric",
        "reward_fraction",
        "winner_match",
        "false_negative",
        "stratum",
    ]
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any, digits: int = 4) -> str:
    value = _finite(value)
    return "NA" if value is None else f"{value:.{digits}f}"


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = payload["schedule_rows"]
    robust_all = [
        r for r in rows
        if r["metric"] == "common_robust_lcb" and r["stratum"] == "all"
    ]
    lines = [
        "# Early-Tweedie Pruning Validation",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "Early-Tweedie BoN validation from existing prompt splits. This is inference/evaluation only: no RL training, pruning+RL, Phase D, human eval, reward-definition edits, prompt-split edits, or gate activation.",
        "",
        "## Run Metadata",
        "",
        "| field | value |",
        "|---|---|",
        f"| run_root | `{payload['run_root']}` |",
        f"| manifest | `{payload['manifest']}` |",
        f"| n_prompts | {payload['n_prompts']} |",
        f"| bon_n | {payload['bon_n']} |",
        f"| metrics | `{', '.join(payload['metrics'])}` |",
        f"| record_files | `{payload['record_paths']}` |",
        f"| shard_logs | `{payload['shard_logs']}` |",
        f"| gpu_hours_actual_sum | {_fmt(payload['gpu_hours_actual_sum'], 6)} |",
        "",
        "## Robust/Common Metric Schedule Summary",
        "",
        "| schedule | compute | reward_fraction | winner_match | false_negative | n |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in robust_all:
        lines.append(
            f"| {row['schedule']} | {_fmt(row['compute_fraction'], 3)} | "
            f"{_fmt(row['reward_fraction'], 4)} | {_fmt(row['winner_match'], 3)} | "
            f"{_fmt(row['false_negative'], 3)} | {row['n_prompts']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Threshold",
            "",
            "- Strong candidate main application result requires `reward_fraction >= 0.98` at `compute_fraction <= 0.5` under robust/common metric and bottom-prune false-negative `<= 5%`.",
            "- If that threshold is not met, treat the result as a conservative inference-time side diagnostic only.",
            "",
            "## Output Files",
            "",
            f"- JSON: `{payload['json_path']}`",
            f"- Plot CSV: `{payload['plot_csv_path']}`",
            f"- Retention CSV: `{payload['retention_csv_path']}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, nargs="+", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--manifest", default="orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
    parser.add_argument("--output-md", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.md"))
    parser.add_argument("--output-json", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION.json"))
    parser.add_argument("--plot-csv", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_PLOT.csv"))
    parser.add_argument("--retention-csv", type=Path, default=Path("orbit-research/EARLY_TWEEDIE_PRUNING_VALIDATION_RETENTION.csv"))
    parser.add_argument("--metrics", nargs="+", default=list(DEFAULT_METRICS))
    parser.add_argument("--strata", nargs="+", default=list(DEFAULT_STRATA))
    parser.add_argument("--random-seed", type=int, default=20260527)
    parser.add_argument("--random-repeats", type=int, default=20)
    parser.add_argument("--expected-bon-n", type=int, default=8)
    args = parser.parse_args()

    records = _read_records(args.records)
    summaries = _read_summaries(args.records)
    schedule_rows, retention_rows = _analyze(
        records,
        metrics=tuple(args.metrics),
        strata=tuple(args.strata),
        expected_bon_n=int(args.expected_bon_n),
        random_seed=args.random_seed,
        random_repeats=args.random_repeats,
    )
    shard_logs = []
    for summary in summaries:
        out_dir = Path(summary["output_dir"])
        shard_logs.extend([str(out_dir.with_name(out_dir.name + "_stdout.log")), str(out_dir.with_name(out_dir.name + "_stderr.log"))])
    payload = {
        "schema_version": "early_tweedie_pruning_validation_merge_v1",
        "generated_at_utc": _now_utc(),
        "run_root": str(args.run_root),
        "manifest": args.manifest,
        "record_paths": [str(p) for p in args.records],
        "shard_summaries": summaries,
        "shard_logs": shard_logs,
        "n_prompts": len({r["prompt_id"] for r in records}),
        "n_candidates": len(records),
        "bon_n": int(args.expected_bon_n),
        "metrics": list(args.metrics),
        "strata": list(args.strata),
        "gpu_hours_actual_sum": sum(float(s.get("gpu_hours_consumed") or 0.0) for s in summaries),
        "schedule_rows": schedule_rows,
        "retention_rows": retention_rows,
        "plot_csv_path": str(args.plot_csv),
        "retention_csv_path": str(args.retention_csv),
        "json_path": str(args.output_json),
        "safety": {
            "training_launched": False,
            "held_out_workflow_launched": False,
            "phase_d_launched": False,
            "human_eval_launched": False,
            "pruning_rl_launched": False,
            "gate_v1_modified": False,
            "gate_v2_activated": False,
            "reward_sigma_prompt_credit_definitions_changed": False,
        },
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(args.plot_csv, schedule_rows)
    _write_csv(args.retention_csv, retention_rows)
    _write_markdown(args.output_md, payload)
    print(json.dumps({"status": "PASS", "output_json": str(args.output_json), "plot_csv": str(args.plot_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
