"""Analyze BoN-16 Early-Tweedie pruning subset records.

Offline analysis only. Requires complete BoN-16 candidate records. Does not
launch generation, training, Phase D, human evaluation, or pruning+RL.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PRIMARY_METRIC = "common_robust_lcb"
SIGMA_STEPS = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
FULL_STEPS = 30.0


def _load_etv_module():
    path = Path("scripts/early_trajectory_verifier_analysis.py")
    spec = importlib.util.spec_from_file_location("early_trajectory_verifier_analysis", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _finite(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _mean(xs: list[float]) -> float | None:
    vals = [x for x in xs if math.isfinite(x)]
    return statistics.mean(vals) if vals else None


def _median(xs: list[float]) -> float | None:
    vals = [x for x in xs if math.isfinite(x)]
    return statistics.median(vals) if vals else None


def _fmt(value: Any, digits: int = 4) -> str:
    val = _finite(value)
    return "NA" if val is None else f"{val:.{digits}f}"


def _read_records(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def _group_by_prompt(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[str(row["prompt_id"])].append(row)
    return dict(out)


def _rank_desc(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (_finite(r.get(key), float("-inf")), -int(r["candidate_index"])),
        reverse=True,
    )


def _top_by(rows: list[dict[str, Any]], key: str, n: int) -> list[dict[str, Any]]:
    return _rank_desc(rows, key)[:n]


def _compute_fraction(schedule: str) -> float:
    if schedule == "full_bon16":
        return 1.0
    if schedule in {"bon8_first8", "bon8_random_subset"}:
        return 0.5
    if schedule in {"raw_etp16_sigma0.9_top8_sigma0.7_top4", "random_prune16_keep8_keep4", "etv16_sigma0.9_top8_sigma0.7_top4"}:
        return (16 * SIGMA_STEPS["0.9"] + 8 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.9"]) + 4 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (16 * FULL_STEPS)
    if schedule in {"raw_etp16_sigma0.8_top12", "etv16_sigma0.8_top12"}:
        return (16 * SIGMA_STEPS["0.8"] + 12 * (FULL_STEPS - SIGMA_STEPS["0.8"])) / (16 * FULL_STEPS)
    raise KeyError(schedule)


def _add_bon16_rank_features(rows: list[dict[str, Any]]) -> None:
    by_prompt = _group_by_prompt(rows)
    for pid, group in by_prompt.items():
        group = sorted(group, key=lambda r: int(r["candidate_index"]))
        final_ranked = _rank_desc(group, f"final_{PRIMARY_METRIC}")
        final_rank = {int(r["candidate_index"]): i + 1 for i, r in enumerate(final_ranked)}
        for row in group:
            cid = int(row["candidate_index"])
            row["candidate_id"] = cid
            row["candidate_uid"] = f"{pid}__bon16_cand{cid:02d}"
            row["final_rank_common_robust_lcb"] = final_rank[cid]
            for sigma in ("0.9", "0.8", "0.7"):
                for metric in ("common_robust_lcb", "aesthetic_pq"):
                    ranked = _rank_desc(group, f"early_{sigma}_{metric}")
                    ranks = {int(r["candidate_index"]): i + 1 for i, r in enumerate(ranked)}
                    rank = ranks[cid]
                    row[f"early_{sigma}_{metric}_rank_within_prompt"] = rank
                    row[f"early_{sigma}_{metric}_rank_percentile"] = (16 - rank) / 15.0


def _select(
    rows: list[dict[str, Any]],
    schedule: str,
    rng: random.Random,
    learned_scores: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    if schedule == "full_bon16":
        return rows
    if schedule == "bon8_first8":
        return [r for r in rows if int(r["candidate_index"]) < 8]
    if schedule == "bon8_random_subset":
        return rng.sample(sorted(rows, key=lambda r: int(r["candidate_index"])), 8)
    if schedule == "random_prune16_keep8_keep4":
        keep8 = rng.sample(sorted(rows, key=lambda r: int(r["candidate_index"])), 8)
        return rng.sample(keep8, 4)
    if schedule == "raw_etp16_sigma0.9_top8_sigma0.7_top4":
        keep8 = _top_by(rows, f"early_0.9_{PRIMARY_METRIC}", 8)
        return _top_by(keep8, f"early_0.7_{PRIMARY_METRIC}", 4)
    if schedule == "raw_etp16_sigma0.8_top12":
        return _top_by(rows, f"early_0.8_{PRIMARY_METRIC}", 12)
    if learned_scores is None:
        raise RuntimeError(f"{schedule} requires learned scores")
    def score(row: dict[str, Any], stage: str) -> float:
        return learned_scores[stage][row["candidate_uid"]]
    if schedule == "etv16_sigma0.9_top8_sigma0.7_top4":
        keep8 = sorted(rows, key=lambda r: (score(r, "0.9"), -int(r["candidate_index"])), reverse=True)[:8]
        return sorted(keep8, key=lambda r: (score(r, "0.7"), -int(r["candidate_index"])), reverse=True)[:4]
    if schedule == "etv16_sigma0.8_top12":
        return sorted(rows, key=lambda r: (score(r, "0.8"), -int(r["candidate_index"])), reverse=True)[:12]
    raise KeyError(schedule)


def _analyze(
    rows: list[dict[str, Any]],
    schedules: tuple[str, ...],
    *,
    random_repeats: int,
    learned_scores: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    by_prompt = {pid: sorted(g, key=lambda r: int(r["candidate_index"])) for pid, g in _group_by_prompt(rows).items()}
    full_winners = {}
    full_scores = []
    for pid, group in by_prompt.items():
        ranked = _rank_desc(group, f"final_{PRIMARY_METRIC}")
        full_winners[pid] = ranked
        full_scores.append(float(ranked[0][f"final_{PRIMARY_METRIC}"]))
    full_mean = _mean(full_scores)
    out = []
    for schedule in schedules:
        repeats = random_repeats if schedule in {"bon8_random_subset", "random_prune16_keep8_keep4"} else 1
        n = 0
        selected_scores = []
        regrets = []
        winner_match = 0
        fn_top1 = 0
        top2_any = 0
        for repeat in range(repeats):
            rng = random.Random(20260528 + repeat)
            for pid, group in by_prompt.items():
                full_ranked = full_winners[pid]
                survivors = _select(group, schedule, rng, learned_scores)
                selected = _rank_desc(survivors, f"final_{PRIMARY_METRIC}")[0]
                survivor_ids = {int(r["candidate_index"]) for r in survivors}
                top2 = {int(r["candidate_index"]) for r in full_ranked[:2]}
                full_score = float(full_ranked[0][f"final_{PRIMARY_METRIC}"])
                selected_score = float(selected[f"final_{PRIMARY_METRIC}"])
                n += 1
                selected_scores.append(selected_score)
                regrets.append(full_score - selected_score)
                winner_match += int(int(selected["candidate_index"]) == int(full_ranked[0]["candidate_index"]))
                fn_top1 += int(int(full_ranked[0]["candidate_index"]) not in survivor_ids)
                top2_any += int(bool(top2 & survivor_ids))
        mean_selected = _mean(selected_scores)
        out.append(
            {
                "schedule": schedule,
                "compute_fraction": _compute_fraction(schedule),
                "n_prompt_evals": n,
                "reward_fraction": mean_selected / full_mean if mean_selected is not None and full_mean else None,
                "winner_match": winner_match / n if n else None,
                "false_negative_top1_prompt_rate": fn_top1 / n if n else None,
                "top2_any_retention": top2_any / n if n else None,
                "mean_selected_reward": mean_selected,
                "mean_full_bon16_reward": full_mean,
                "mean_regret": _mean(regrets),
                "median_regret": _median(regrets),
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _train_etv_models_from_bon8(training_records: list[dict[str, Any]], bon16_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    etv = _load_etv_module()
    bon8 = etv.enrich_records(training_records)
    etv._add_slope_features(bon8)
    etv._add_slope_features(bon16_rows)
    train = [r for r in bon8 if r["analysis_split"] == "train"]
    models = {stage: etv.train_ridge(train, stage=stage) for stage in ("0.9", "0.8", "0.7")}
    for model in models.values():
        etv.add_model_category_features_for_prediction(model, bon16_rows)
    scores = {stage: {} for stage in ("0.9", "0.8", "0.7")}
    for row in bon16_rows:
        for stage, model in models.items():
            scores[stage][row["candidate_uid"]] = model.predict(row)
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, nargs="+", required=True)
    parser.add_argument("--bon8-records", type=Path, nargs="+", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, default=Path("orbit-research/BON16_PRUNING_SUBSET_RESULTS.md"))
    parser.add_argument("--output-json", type=Path, default=Path("orbit-research/BON16_PRUNING_SUBSET_RESULTS.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("orbit-research/BON16_PRUNING_SUBSET_RESULTS.csv"))
    parser.add_argument("--random-repeats", type=int, default=100)
    args = parser.parse_args()

    rows = _read_records(args.records)
    by_prompt = _group_by_prompt(rows)
    incomplete = {pid: len(g) for pid, g in by_prompt.items() if len(g) != 16}
    if incomplete:
        raise SystemExit(f"incomplete BoN16 records: {dict(list(incomplete.items())[:10])}")
    if len(by_prompt) == 0:
        raise SystemExit("no BoN16 prompts found")
    _add_bon16_rank_features(rows)
    bon8_training = _read_records(args.bon8_records)
    learned_scores = _train_etv_models_from_bon8(bon8_training, rows)
    schedules = (
        "full_bon16",
        "bon8_first8",
        "bon8_random_subset",
        "raw_etp16_sigma0.9_top8_sigma0.7_top4",
        "raw_etp16_sigma0.8_top12",
        "random_prune16_keep8_keep4",
        "etv16_sigma0.9_top8_sigma0.7_top4",
        "etv16_sigma0.8_top12",
    )
    result_rows = _analyze(rows, schedules, random_repeats=args.random_repeats, learned_scores=learned_scores)
    gpu_hours = 0.0
    summaries = []
    for summary_path in sorted(args.run_root.glob("shard*/run_summary.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summaries.append(summary)
        gpu_hours += float(summary.get("gpu_hours_consumed") or 0.0)
    payload = {
        "schema_version": "bon16_pruning_subset_results_v1",
        "generated_at_utc": _now_utc(),
        "run_root": str(args.run_root),
        "n_prompts": len(by_prompt),
        "n_candidates": len(rows),
        "result_rows": result_rows,
        "gpu_hours_sum": gpu_hours,
        "shard_summaries": summaries,
        "safety": {
            "rl_training_launched": False,
            "pruning_rl_launched": False,
            "phase_d_launched": False,
            "human_crowdsourcing_launched": False,
            "gate_v1_modified": False,
            "reward_definitions_changed": False,
            "prompt_splits_changed": False,
        },
    }
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(args.output_csv, result_rows)
    lines = [
        "# BoN-16 Pruning Subset Results",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "BoN-16 subset validation on 128 stratified prompts. Inference/evaluation only: no RL training, pruning+RL, Phase D, human crowdsourcing, gate edit, or reward-definition change.",
        "",
        "## Results",
        "",
        "| schedule | compute | reward_fraction | winner_match | fn_top1 | top2_any | median_regret |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result_rows:
        lines.append(
            f"| {row['schedule']} | {_fmt(row['compute_fraction'], 3)} | {_fmt(row['reward_fraction'], 4)} | "
            f"{_fmt(row['winner_match'], 4)} | {_fmt(row['false_negative_top1_prompt_rate'], 4)} | "
            f"{_fmt(row['top2_any_retention'], 4)} | {_fmt(row['median_regret'], 4)} |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- JSON: `{args.output_json}`",
            f"- CSV: `{args.output_csv}`",
            f"- run_root: `{args.run_root}`",
            f"- GPU-hours sum: `{_fmt(gpu_hours, 4)}`",
        ]
    )
    args.output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "n_prompts": len(by_prompt), "gpu_hours": gpu_hours}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
