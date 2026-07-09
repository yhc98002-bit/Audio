"""Merge candidate-level Early-Tweedie BoN shards and compute pruning tables."""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from pathlib import Path
from typing import Any


PRIMARY_AXIS = "aesthetic_pq"
SIGMA_STEPS = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
FULL_STEPS = 30.0


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    return records


def _rank_desc(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda row: (float(row.get(key, float("-inf"))), -int(row["candidate_index"])),
        reverse=True,
    )


def _bottom(items: list[dict[str, Any]], key: str, fraction: float) -> list[dict[str, Any]]:
    ordered = sorted(
        items,
        key=lambda row: (float(row.get(key, float("inf"))), int(row["candidate_index"])),
    )
    n = max(1, int(len(ordered) * fraction + 0.999999))
    return ordered[:n]


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def _compute_fraction(kind: str) -> float:
    if kind == "full":
        return 1.0
    if kind == "a":
        return (8 * SIGMA_STEPS["0.9"] + 4 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.9"]) + 2 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if kind == "b":
        return (8 * SIGMA_STEPS["0.8"] + 4 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.8"]) + 2 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if kind == "c":
        return (8 * SIGMA_STEPS["0.8"] + 6 * (FULL_STEPS - SIGMA_STEPS["0.8"])) / (8 * FULL_STEPS)
    if kind == "random_a":
        return _compute_fraction("a")
    raise KeyError(kind)


def _analyze(records: list[dict[str, Any]], *, primary_axis: str, random_seed: int) -> dict[str, Any]:
    by_prompt: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_prompt.setdefault(rec["prompt_id"], []).append(rec)

    duplicates = []
    for prompt_id, rows in by_prompt.items():
        seen = set()
        for row in rows:
            key = int(row["candidate_index"])
            if key in seen:
                duplicates.append({"prompt_id": prompt_id, "candidate_index": key})
            seen.add(key)

    retention: dict[str, Any] = {}
    for sigma in ("0.9", "0.8", "0.7"):
        early_key = f"early_{sigma}_{primary_axis}"
        counts = {
            "n": 0,
            "top1": 0,
            "top2": 0,
            "top4": 0,
            "bottom50_final_top1": 0,
            "bottom50_final_top2": 0,
            "bottom25_final_top1": 0,
            "bottom25_final_top2": 0,
        }
        for rows in by_prompt.values():
            if len(rows) != 8 or any(row.get(early_key) is None for row in rows):
                continue
            final_ranked = _rank_desc(rows, f"final_{primary_axis}")
            final_top1 = int(final_ranked[0]["candidate_index"])
            final_top2 = {int(row["candidate_index"]) for row in final_ranked[:2]}
            early_order = [int(row["candidate_index"]) for row in _rank_desc(rows, early_key)]
            bottom50 = {int(row["candidate_index"]) for row in _bottom(rows, early_key, 0.50)}
            bottom25 = {int(row["candidate_index"]) for row in _bottom(rows, early_key, 0.25)}
            counts["n"] += 1
            counts["top1"] += int(final_top1 in set(early_order[:1]))
            counts["top2"] += int(final_top1 in set(early_order[:2]))
            counts["top4"] += int(final_top1 in set(early_order[:4]))
            counts["bottom50_final_top1"] += int(final_top1 in bottom50)
            counts["bottom50_final_top2"] += int(bool(final_top2 & bottom50))
            counts["bottom25_final_top1"] += int(final_top1 in bottom25)
            counts["bottom25_final_top2"] += int(bool(final_top2 & bottom25))
        n = counts["n"]
        retention[sigma] = {
            "n_prompts": n,
            "winner_retention_top1": counts["top1"] / n if n else None,
            "winner_retention_top2": counts["top2"] / n if n else None,
            "winner_retention_top4": counts["top4"] / n if n else None,
            "bottom50_false_negative_final_top1": counts["bottom50_final_top1"] / n if n else None,
            "bottom50_false_negative_final_top2": counts["bottom50_final_top2"] / n if n else None,
            "bottom25_false_negative_final_top1": counts["bottom25_final_top1"] / n if n else None,
            "bottom25_false_negative_final_top2": counts["bottom25_final_top2"] / n if n else None,
        }

    rng = random.Random(random_seed)
    schedule_defs = [
        ("full_bon8", "full"),
        ("schedule_a_sigma0.9_top4_sigma0.7_top2_final_top1", "a"),
        ("schedule_b_sigma0.8_top4_sigma0.7_top2_final_top1", "b"),
        ("schedule_c_sigma0.8_prune_bottom25_final_top1", "c"),
        ("random_schedule_a_keep4_keep2_final_top1", "random_a"),
    ]
    schedules: list[dict[str, Any]] = []
    full_scores: list[float] = []
    for rows in by_prompt.values():
        if len(rows) == 8:
            full_scores.append(float(_rank_desc(rows, f"final_{primary_axis}")[0][f"final_{primary_axis}"]))
    full_mean = statistics.mean(full_scores) if full_scores else float("nan")

    for name, kind in schedule_defs:
        selected_scores: list[float] = []
        regrets: list[float] = []
        exact = 0
        retained = 0
        n = 0
        for prompt_id, rows in by_prompt.items():
            if len(rows) != 8:
                continue
            final_key = f"final_{primary_axis}"
            final_ranked = _rank_desc(rows, final_key)
            full_winner = final_ranked[0]
            survivors = list(rows)
            if kind == "a":
                if any(row.get(f"early_0.9_{primary_axis}") is None or row.get(f"early_0.7_{primary_axis}") is None for row in rows):
                    continue
                keep4 = _rank_desc(rows, f"early_0.9_{primary_axis}")[:4]
                survivors = _rank_desc(keep4, f"early_0.7_{primary_axis}")[:2]
            elif kind == "b":
                if any(row.get(f"early_0.8_{primary_axis}") is None or row.get(f"early_0.7_{primary_axis}") is None for row in rows):
                    continue
                keep4 = _rank_desc(rows, f"early_0.8_{primary_axis}")[:4]
                survivors = _rank_desc(keep4, f"early_0.7_{primary_axis}")[:2]
            elif kind == "c":
                if any(row.get(f"early_0.8_{primary_axis}") is None for row in rows):
                    continue
                pruned = {int(row["candidate_index"]) for row in _bottom(rows, f"early_0.8_{primary_axis}", 0.25)}
                survivors = [row for row in rows if int(row["candidate_index"]) not in pruned]
            elif kind == "random_a":
                keep4 = rng.sample(sorted(rows, key=lambda row: int(row["candidate_index"])), 4)
                survivors = rng.sample(keep4, 2)
            selected = _rank_desc(survivors, final_key)[0]
            winner_idx = int(full_winner["candidate_index"])
            survivor_ids = {int(row["candidate_index"]) for row in survivors}
            n += 1
            retained += int(winner_idx in survivor_ids)
            exact += int(int(selected["candidate_index"]) == winner_idx)
            selected_score = float(selected[final_key])
            full_score = float(full_winner[final_key])
            selected_scores.append(selected_score)
            regrets.append(full_score - selected_score)
        mean_score = _mean(selected_scores)
        winner_retention = retained / n if n else None
        schedules.append(
            {
                "schedule": name,
                "n_prompts": n,
                "compute_fraction": _compute_fraction(kind),
                "mean_primary_reward": mean_score,
                "reward_fraction": mean_score / full_mean if mean_score is not None and full_mean else None,
                "winner_retention": winner_retention,
                "false_negative_rate": 1.0 - winner_retention if winner_retention is not None else None,
                "median_regret": _median(regrets),
                "mean_regret": _mean(regrets),
                "exact_winner_match": exact / n if n else None,
            }
        )

    return {
        "primary_axis": primary_axis,
        "n_prompts": len(by_prompt),
        "n_candidates": len(records),
        "duplicate_prompt_candidate_pairs": duplicates,
        "winner_retention_by_sigma": retention,
        "schedules": schedules,
    }


def _write_outputs(prefix: Path, payload: dict[str, Any]) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = prefix.with_suffix(".json")
    md_path = prefix.with_suffix(".md")
    csv_path = prefix.with_suffix(".csv")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "schedule",
            "compute_fraction",
            "reward_fraction",
            "winner_retention",
            "false_negative_rate",
            "median_regret",
            "exact_winner_match",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["analysis"]["schedules"]:
            writer.writerow({k: row.get(k) for k in fieldnames})
    lines = [
        "# Early-Tweedie Pruning Retrospective 128",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "Candidate-level BoN-8 retrospective from isolated dev-prompt artifacts. No Phase C training, held-out, Phase D, human eval, paper rewrite, or pruning+RL was launched.",
        "",
        "## Inputs",
        "",
        f"- record files: `{payload['record_paths']}`",
        f"- n_prompts: `{payload['analysis']['n_prompts']}`",
        f"- n_candidates: `{payload['analysis']['n_candidates']}`",
        f"- primary_axis: `{payload['analysis']['primary_axis']}`",
        "",
        "## Winner Retention",
        "",
        "| sigma | n | top1 | top2 | top4 | bottom50_fn_top1 | bottom50_fn_top2 | bottom25_fn_top1 | bottom25_fn_top2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sigma, row in payload["analysis"]["winner_retention_by_sigma"].items():
        lines.append(
            f"| {sigma} | {row['n_prompts']} | {row['winner_retention_top1']:.3f} | "
            f"{row['winner_retention_top2']:.3f} | {row['winner_retention_top4']:.3f} | "
            f"{row['bottom50_false_negative_final_top1']:.3f} | "
            f"{row['bottom50_false_negative_final_top2']:.3f} | "
            f"{row['bottom25_false_negative_final_top1']:.3f} | "
            f"{row['bottom25_false_negative_final_top2']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Compute-Quality Pareto",
            "",
            "| schedule | compute_fraction | reward_fraction | winner_retention | false_negative_rate | median_regret | exact_winner_match |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["analysis"]["schedules"]:
        lines.append(
            f"| {row['schedule']} | {row['compute_fraction']:.3f} | "
            f"{row['reward_fraction']:.3f} | {row['winner_retention']:.3f} | "
            f"{row['false_negative_rate']:.3f} | {row['median_regret']:.6f} | "
            f"{row['exact_winner_match']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This is an H2 inference-time side diagnostic only. It does not change Phase C methods or paper claims.",
            "",
            f"Plot-ready CSV: `{csv_path}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, nargs="+", required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--primary-axis", default=PRIMARY_AXIS)
    parser.add_argument("--random-seed", type=int, default=20260524)
    args = parser.parse_args()

    records = _read_records(args.records)
    payload = {
        "schema_version": "early_tweedie_bon_merge_v1",
        "generated_at_utc": _now_utc(),
        "record_paths": [str(p) for p in args.records],
        "analysis": _analyze(records, primary_axis=args.primary_axis, random_seed=args.random_seed),
        "safety": {
            "held_out_launched": False,
            "phase_d_launched": False,
            "human_eval_launched": False,
            "pruning_rl_launched": False,
            "reward_sigma_prompt_credit_definitions_changed": False,
        },
    }
    _write_outputs(args.output_prefix, payload)
    print(json.dumps({"status": "PASS", "output_prefix": str(args.output_prefix)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
