"""Paper-grade Early Trajectory Verifier analysis from candidate records.

This script is offline analysis only. It does not launch generation, training,
human evaluation, Phase D, pruning+RL, or gate activation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SIGMA_STEPS = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
FULL_STEPS = 30.0
PRIMARY_METRIC = "common_robust_lcb"
EVAL_METRICS = (
    "common_robust_lcb",
    "aesthetic_pq",
    "aesthetic_cu",
    "semantic_fit",
    "lyric_intelligibility",
    "section_coherence",
)
STRATA = ("all", "vocal", "instrumental")
# vocal_scorable = vocal AND English. The honest support for lyric_intelligibility:
# Whisper-WER is computed English-only (mprm/rewards/whisper_wer.py) and instrumental
# prompts carry a constant 1.0 sentinel, so a lyric number aggregated over "all" or even
# "vocal" is contaminated. PROMPT_SET_AUDIT_20260529 R1/R8.
STRATA_EXT = ("all", "vocal", "instrumental", "vocal_scorable")
RAW_SCHEDULES = (
    "full_bon8",
    "bon4_first4",
    "bon4_random_subset",
    "raw_schedule_a_sigma0.9_top4_sigma0.7_top2",
    "raw_schedule_b_sigma0.8_top4_sigma0.7_top2",
    "raw_schedule_c_sigma0.8_top6",
    "raw_bottom_prune_sigma0.8_remove_bottom25",
    "raw_bottom_prune_sigma0.7_remove_bottom25",
    "random_prune_keep4_keep2",
)
LEARNED_SCHEDULES = (
    "etv_schedule_a_sigma0.9_top4_sigma0.7_top2",
    "etv_schedule_b_sigma0.8_top4_sigma0.7_top2",
    "etv_schedule_c_sigma0.8_top6",
    "etv_bottom_prune_sigma0.7_remove_bottom25",
)


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _wilson_ci(rate: float | None, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if rate is None or n <= 0:
        return None, None
    p = min(1.0, max(0.0, float(rate)))
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _fmt(value: Any, digits: int = 4) -> str:
    val = _finite(value)
    return "NA" if val is None else f"{val:.{digits}f}"


def _read_records(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def _group_by_prompt(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["prompt_id"])].append(row)
    return dict(grouped)


def _rank_desc(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            _finite(r.get(key), float("-inf")),
            -int(r["candidate_index"]),
        ),
        reverse=True,
    )


def _rank_values(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(x: list[float], y: list[float]) -> float | None:
    pairs = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    if len(pairs) < 3:
        return None
    xr = _rank_values([p[0] for p in pairs])
    yr = _rank_values([p[1] for p in pairs])
    mx = statistics.mean(xr)
    my = statistics.mean(yr)
    num = sum((a - mx) * (b - my) for a, b in zip(xr, yr))
    denx = math.sqrt(sum((a - mx) ** 2 for a in xr))
    deny = math.sqrt(sum((b - my) ** 2 for b in yr))
    if denx == 0.0 or deny == 0.0:
        return None
    return num / (denx * deny)


def _compute_fraction(schedule: str, prune_bottom: int | None = None) -> float:
    if schedule == "full_bon8":
        return 1.0
    if schedule in {"bon4_first4", "bon4_random_subset"}:
        return 0.5
    if schedule.endswith("sigma0.9_top4_sigma0.7_top2") or schedule == "random_prune_keep4_keep2":
        return (8 * SIGMA_STEPS["0.9"] + 4 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.9"]) + 2 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if schedule.endswith("sigma0.8_top4_sigma0.7_top2"):
        return (8 * SIGMA_STEPS["0.8"] + 4 * (SIGMA_STEPS["0.7"] - SIGMA_STEPS["0.8"]) + 2 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if schedule.endswith("sigma0.8_top6") or schedule == "raw_bottom_prune_sigma0.8_remove_bottom25":
        return (8 * SIGMA_STEPS["0.8"] + 6 * (FULL_STEPS - SIGMA_STEPS["0.8"])) / (8 * FULL_STEPS)
    if schedule in {"raw_bottom_prune_sigma0.7_remove_bottom25", "etv_bottom_prune_sigma0.7_remove_bottom25"}:
        return (8 * SIGMA_STEPS["0.7"] + 6 * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    if schedule == "risk_controlled_bottom_prune_sigma0.7":
        assert prune_bottom is not None
        keep = 8 - prune_bottom
        return (8 * SIGMA_STEPS["0.7"] + keep * (FULL_STEPS - SIGMA_STEPS["0.7"])) / (8 * FULL_STEPS)
    raise KeyError(schedule)


def _filter_stratum(rows: list[dict[str, Any]], stratum: str) -> list[dict[str, Any]]:
    if stratum == "all":
        return rows
    if stratum == "vocal_scorable":
        # English vocal only: the support on which Whisper-WER lyric_intelligibility is
        # actually meaningful (instrumental=1.0 sentinel and non-EN are excluded).
        return [r for r in rows if r.get("vocal_stratum") == "vocal" and r.get("language") == "en"]
    return [r for r in rows if r.get("vocal_stratum") == stratum]


def _bottom_by(rows: list[dict[str, Any]], key: str, n: int) -> set[int]:
    ordered = sorted(
        rows,
        key=lambda r: (
            _finite(r.get(key), float("inf")),
            int(r["candidate_index"]),
        ),
    )
    return {int(r["candidate_index"]) for r in ordered[:n]}


def _top_by(rows: list[dict[str, Any]], key: str, n: int) -> list[dict[str, Any]]:
    return _rank_desc(rows, key)[:n]


def _select_survivors(
    rows: list[dict[str, Any]],
    schedule: str,
    *,
    metric: str,
    rng: random.Random,
    learned_scores: dict[str, dict[str, float]] | None = None,
    risk_prune_bottom: int | None = None,
) -> list[dict[str, Any]]:
    if schedule == "full_bon8":
        return rows
    if schedule == "bon4_first4":
        return [r for r in rows if int(r["candidate_index"]) < 4]
    if schedule == "bon4_random_subset":
        return rng.sample(sorted(rows, key=lambda r: int(r["candidate_index"])), 4)
    if schedule == "random_prune_keep4_keep2":
        keep4 = rng.sample(sorted(rows, key=lambda r: int(r["candidate_index"])), 4)
        return rng.sample(keep4, 2)
    if schedule == "raw_schedule_a_sigma0.9_top4_sigma0.7_top2":
        keep4 = _top_by(rows, f"early_0.9_{metric}", 4)
        return _top_by(keep4, f"early_0.7_{metric}", 2)
    if schedule == "raw_schedule_b_sigma0.8_top4_sigma0.7_top2":
        keep4 = _top_by(rows, f"early_0.8_{metric}", 4)
        return _top_by(keep4, f"early_0.7_{metric}", 2)
    if schedule == "raw_schedule_c_sigma0.8_top6":
        return _top_by(rows, f"early_0.8_{metric}", 6)
    if schedule == "raw_bottom_prune_sigma0.8_remove_bottom25":
        pruned = _bottom_by(rows, f"early_0.8_{metric}", 2)
        return [r for r in rows if int(r["candidate_index"]) not in pruned]
    if schedule == "raw_bottom_prune_sigma0.7_remove_bottom25":
        pruned = _bottom_by(rows, f"early_0.7_{metric}", 2)
        return [r for r in rows if int(r["candidate_index"]) not in pruned]

    if learned_scores is None:
        raise RuntimeError(f"{schedule} requires learned_scores")
    def score(row: dict[str, Any], stage: str) -> float:
        return learned_scores[stage][row["candidate_uid"]]
    if schedule == "etv_schedule_a_sigma0.9_top4_sigma0.7_top2":
        keep4 = sorted(rows, key=lambda r: (score(r, "0.9"), -int(r["candidate_index"])), reverse=True)[:4]
        return sorted(keep4, key=lambda r: (score(r, "0.7"), -int(r["candidate_index"])), reverse=True)[:2]
    if schedule == "etv_schedule_b_sigma0.8_top4_sigma0.7_top2":
        keep4 = sorted(rows, key=lambda r: (score(r, "0.8"), -int(r["candidate_index"])), reverse=True)[:4]
        return sorted(keep4, key=lambda r: (score(r, "0.7"), -int(r["candidate_index"])), reverse=True)[:2]
    if schedule == "etv_schedule_c_sigma0.8_top6":
        return sorted(rows, key=lambda r: (score(r, "0.8"), -int(r["candidate_index"])), reverse=True)[:6]
    if schedule == "etv_bottom_prune_sigma0.7_remove_bottom25":
        ordered = sorted(rows, key=lambda r: (score(r, "0.7"), int(r["candidate_index"])))
        pruned = {int(r["candidate_index"]) for r in ordered[:2]}
        return [r for r in rows if int(r["candidate_index"]) not in pruned]
    if schedule == "risk_controlled_bottom_prune_sigma0.7":
        n = int(risk_prune_bottom or 0)
        if n <= 0:
            return rows
        ordered = sorted(rows, key=lambda r: (score(r, "0.7"), int(r["candidate_index"])))
        pruned = {int(r["candidate_index"]) for r in ordered[:n]}
        return [r for r in rows if int(r["candidate_index"]) not in pruned]
    raise KeyError(schedule)


def _prompt_split(prompt_id: str, split: str) -> str:
    if split == "held_out":
        return "test"
    h = int(_sha256_text(prompt_id)[:8], 16) % 4
    return "validation" if h == 0 else "train"


def enrich_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_prompt = _group_by_prompt(records)
    out: list[dict[str, Any]] = []
    for prompt_id, rows in by_prompt.items():
        rows = sorted(rows, key=lambda r: int(r["candidate_index"]))
        final_ranked = _rank_desc(rows, f"final_{PRIMARY_METRIC}")
        final_rank = {int(r["candidate_index"]): i + 1 for i, r in enumerate(final_ranked)}
        top2 = {int(r["candidate_index"]) for r in final_ranked[:2]}
        top4 = {int(r["candidate_index"]) for r in final_ranked[:4]}
        early_ranks: dict[tuple[str, str], dict[int, int]] = {}
        for sigma in ("0.9", "0.8", "0.7"):
            for metric in EVAL_METRICS:
                key = f"early_{sigma}_{metric}"
                ranked = _rank_desc(rows, key)
                early_ranks[(sigma, metric)] = {int(r["candidate_index"]): i + 1 for i, r in enumerate(ranked)}
        for row in rows:
            r = dict(row)
            cid = int(r["candidate_index"])
            r["candidate_id"] = cid
            r["candidate_uid"] = f"{prompt_id}__cand{cid:02d}"
            r["analysis_split"] = _prompt_split(str(prompt_id), str(r.get("split")))
            r["final_rank_common_robust_lcb"] = final_rank[cid]
            r["label_final_winner"] = final_rank[cid] == 1
            r["label_final_top2"] = cid in top2
            r["label_final_top4"] = cid in top4
            r["full_bon8_step_units"] = 8 * FULL_STEPS
            for sigma in ("0.9", "0.8", "0.7"):
                r[f"early_{sigma}_step_units_per_candidate"] = SIGMA_STEPS[sigma]
                for metric in EVAL_METRICS:
                    rank = early_ranks[(sigma, metric)][cid]
                    r[f"early_{sigma}_{metric}_rank_within_prompt"] = rank
                    r[f"early_{sigma}_{metric}_rank_percentile"] = (8 - rank) / 7.0
            out.append(r)
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def analyze_schedules(
    records: list[dict[str, Any]],
    schedules: tuple[str, ...],
    *,
    metric: str,
    strata: tuple[str, ...],
    random_repeats: int,
    random_seed: int,
    learned_scores: dict[str, dict[str, float]] | None = None,
    risk_prune_bottom: int | None = None,
) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for stratum in strata:
        subset = _filter_stratum(records, stratum)
        by_prompt = {
            pid: sorted(rows, key=lambda r: int(r["candidate_index"]))
            for pid, rows in _group_by_prompt(subset).items()
            if len(rows) == 8
        }
        final_key = f"final_{metric}"
        full_scores = []
        full_rankings: dict[str, list[dict[str, Any]]] = {}
        for pid, rows in by_prompt.items():
            if any(_finite(r.get(final_key)) is None for r in rows):
                continue
            ranked = _rank_desc(rows, final_key)
            full_rankings[pid] = ranked
            full_scores.append(float(ranked[0][final_key]))
        full_mean = _mean(full_scores)
        for schedule in schedules:
            repeats = random_repeats if schedule in {"bon4_random_subset", "random_prune_keep4_keep2"} else 1
            n = 0
            selected_scores: list[float] = []
            regrets: list[float] = []
            winner_match = 0
            fn_top1 = 0
            top2_all_retained = 0
            top2_any_retained = 0
            top4_all_retained = 0
            top4_any_retained = 0
            top2_candidate_pruned = 0
            top2_candidate_total = 0
            for repeat in range(repeats):
                rng = random.Random(random_seed + repeat)
                for pid, rows in by_prompt.items():
                    if pid not in full_rankings:
                        continue
                    full_ranked = full_rankings[pid]
                    full_winner = full_ranked[0]
                    full_top2 = {int(r["candidate_index"]) for r in full_ranked[:2]}
                    full_top4 = {int(r["candidate_index"]) for r in full_ranked[:4]}
                    survivors = _select_survivors(
                        rows,
                        schedule,
                        metric=metric,
                        rng=rng,
                        learned_scores=learned_scores,
                        risk_prune_bottom=risk_prune_bottom,
                    )
                    if not survivors:
                        continue
                    survivor_ids = {int(r["candidate_index"]) for r in survivors}
                    selected = _rank_desc(survivors, final_key)[0]
                    selected_score = float(selected[final_key])
                    full_score = float(full_winner[final_key])
                    n += 1
                    selected_scores.append(selected_score)
                    regrets.append(full_score - selected_score)
                    winner_match += int(int(selected["candidate_index"]) == int(full_winner["candidate_index"]))
                    fn_top1 += int(int(full_winner["candidate_index"]) not in survivor_ids)
                    top2_all_retained += int(full_top2.issubset(survivor_ids))
                    top2_any_retained += int(bool(full_top2 & survivor_ids))
                    top4_all_retained += int(full_top4.issubset(survivor_ids))
                    top4_any_retained += int(bool(full_top4 & survivor_ids))
                    pruned_top2 = len(full_top2 - survivor_ids)
                    top2_candidate_pruned += pruned_top2
                    top2_candidate_total += len(full_top2)
            selected_mean = _mean(selected_scores)
            rows_out.append(
                {
                    "schedule": schedule,
                    "compute_fraction": _compute_fraction(schedule, risk_prune_bottom),
                    "metric": metric,
                    "stratum": stratum,
                    "n_prompt_evals": n,
                    "reward_fraction": selected_mean / full_mean if selected_mean is not None and full_mean else None,
                    "mean_selected_reward": selected_mean,
                    "mean_full_bon8_reward": full_mean,
                    "winner_match": winner_match / n if n else None,
                    "top2_all_retention": top2_all_retained / n if n else None,
                    "top2_any_retention": top2_any_retained / n if n else None,
                    "top4_all_retention": top4_all_retained / n if n else None,
                    "top4_any_retention": top4_any_retained / n if n else None,
                    "false_negative_top1_prompt_rate": fn_top1 / n if n else None,
                    "false_negative_top2_candidate_rate": top2_candidate_pruned / top2_candidate_total if top2_candidate_total else None,
                    "mean_regret": _mean(regrets),
                    "median_regret": _median(regrets),
                }
            )
    return rows_out


def analyze_cross_axis_generalization(
    records: list[dict[str, Any]],
    schedules: tuple[str, ...],
    *,
    selection_metric: str,
    evaluation_metrics: tuple[str, ...],
    random_repeats: int,
    random_seed: int,
    strata: tuple[str, ...] = ("all",),
) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for stratum in strata:
        # lyric_intelligibility is only meaningful on vocal_scorable (EN vocal); skip the
        # contaminated all/instrumental aggregations for that axis but keep them for others.
        subset = _filter_stratum(records, stratum)
        rows_out.extend(
            _cross_axis_for_subset(
                subset, schedules, stratum=stratum,
                selection_metric=selection_metric, evaluation_metrics=evaluation_metrics,
                random_repeats=random_repeats, random_seed=random_seed,
            )
        )
    return rows_out


def _cross_axis_for_subset(
    records: list[dict[str, Any]],
    schedules: tuple[str, ...],
    *,
    stratum: str,
    selection_metric: str,
    evaluation_metrics: tuple[str, ...],
    random_repeats: int,
    random_seed: int,
) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    by_prompt = {
        pid: sorted(rows, key=lambda r: int(r["candidate_index"]))
        for pid, rows in _group_by_prompt(records).items()
        if len(rows) == 8
    }
    for eval_metric in evaluation_metrics:
        final_key = f"final_{eval_metric}"
        full_scores: list[float] = []
        full_rankings: dict[str, list[dict[str, Any]]] = {}
        for pid, rows in by_prompt.items():
            if any(_finite(r.get(final_key)) is None for r in rows):
                continue
            ranked = _rank_desc(rows, final_key)
            full_rankings[pid] = ranked
            full_scores.append(float(ranked[0][final_key]))
        full_mean = _mean(full_scores)
        for schedule in schedules:
            repeats = random_repeats if schedule in {"bon4_random_subset", "random_prune_keep4_keep2"} else 1
            n = 0
            selected_scores: list[float] = []
            regrets: list[float] = []
            winner_match = 0
            for repeat in range(repeats):
                rng = random.Random(random_seed + repeat)
                for pid, rows in by_prompt.items():
                    if pid not in full_rankings:
                        continue
                    survivors = _select_survivors(
                        rows,
                        schedule,
                        metric=selection_metric,
                        rng=rng,
                    )
                    selected = _rank_desc(survivors, final_key)[0]
                    full_winner = full_rankings[pid][0]
                    full_score = float(full_winner[final_key])
                    selected_score = float(selected[final_key])
                    n += 1
                    selected_scores.append(selected_score)
                    regrets.append(full_score - selected_score)
                    winner_match += int(int(selected["candidate_index"]) == int(full_winner["candidate_index"]))
            selected_mean = _mean(selected_scores)
            rows_out.append(
                {
                    "schedule": schedule,
                    "compute_fraction": _compute_fraction(schedule),
                    "selection_metric": selection_metric,
                    "evaluation_metric": eval_metric,
                    "stratum": stratum,
                    "n_prompt_evals": n,
                    "reward_fraction": selected_mean / full_mean if selected_mean is not None and full_mean else None,
                    "winner_match": winner_match / n if n else None,
                    "mean_regret": _mean(regrets),
                    "median_regret": _median(regrets),
                }
            )
    return rows_out


def paired_bon4_bootstrap(
    records: list[dict[str, Any]],
    *,
    metric: str,
    random_repeats: int,
    bootstrap_repeats: int,
    random_seed: int,
) -> list[dict[str, Any]]:
    final_key = f"final_{metric}"
    by_prompt = {
        pid: sorted(rows, key=lambda r: int(r["candidate_index"]))
        for pid, rows in _group_by_prompt(records).items()
        if len(rows) == 8 and all(_finite(r.get(final_key)) is not None for r in rows)
    }
    prompt_rows = []
    for pid, rows in by_prompt.items():
        full = _rank_desc(rows, final_key)[0]
        raw_survivors = _select_survivors(
            rows,
            "raw_schedule_a_sigma0.9_top4_sigma0.7_top2",
            metric=metric,
            rng=random.Random(random_seed),
        )
        raw_selected = _rank_desc(raw_survivors, final_key)[0]
        bon4_scores = []
        for repeat in range(random_repeats):
            survivors = _select_survivors(
                rows,
                "bon4_random_subset",
                metric=metric,
                rng=random.Random(random_seed + repeat),
            )
            bon4_scores.append(float(_rank_desc(survivors, final_key)[0][final_key]))
        prompt_rows.append(
            {
                "prompt_id": pid,
                "full_score": float(full[final_key]),
                "etp_score": float(raw_selected[final_key]),
                "bon4_random_mean_score": _mean(bon4_scores),
                "paired_delta": float(raw_selected[final_key]) - float(_mean(bon4_scores) or 0.0),
            }
        )
    full_mean = _mean([r["full_score"] for r in prompt_rows])
    delta_mean = _mean([r["paired_delta"] for r in prompt_rows])
    rng = random.Random(random_seed + 999)
    n = len(prompt_rows)
    boot = []
    if n:
        for _ in range(bootstrap_repeats):
            sample = [prompt_rows[rng.randrange(n)] for _ in range(n)]
            boot.append(_mean([r["paired_delta"] for r in sample]) or 0.0)
    boot_sorted = sorted(boot)
    def q(frac: float) -> float | None:
        if not boot_sorted:
            return None
        idx = min(len(boot_sorted) - 1, max(0, int(round(frac * (len(boot_sorted) - 1)))))
        return boot_sorted[idx]
    return [
        {
            "comparison": "raw_etp_schedule_a_vs_bon4_random_subset",
            "metric": metric,
            "n_prompts": n,
            "random_repeats_per_prompt": random_repeats,
            "bootstrap_repeats": bootstrap_repeats,
            "mean_full_bon8_score": full_mean,
            "mean_delta_score": delta_mean,
            "delta_reward_fraction": delta_mean / full_mean if delta_mean is not None and full_mean else None,
            "ci95_low_delta_reward_fraction": (q(0.025) / full_mean) if q(0.025) is not None and full_mean else None,
            "ci95_high_delta_reward_fraction": (q(0.975) / full_mean) if q(0.975) is not None and full_mean else None,
        }
    ]


def _numeric_feature_keys(stage: str) -> list[str]:
    sigmas = [s for s in ("0.9", "0.8", "0.7") if float(s) >= float(stage)]
    # The string comparison is not enough for sigma order; keep explicit stage map.
    if stage == "0.9":
        sigmas = ["0.9"]
    elif stage == "0.8":
        sigmas = ["0.9", "0.8"]
    else:
        sigmas = ["0.9", "0.8", "0.7"]
    axes = (
        "common_robust_lcb",
        "common_mean_cells",
        "common_std_cells",
        "common_probe_penalty",
        "semantic_fit",
        "aesthetic_pq",
        "aesthetic_pc",
        "aesthetic_ce",
        "aesthetic_cu",
        "lyric_intelligibility",
        "section_coherence",
        "probe_silence_fraction",
        "probe_autocorr_repetition",
        "probe_hf_artifact_score",
    )
    keys: list[str] = []
    for sigma in sigmas:
        for axis in axes:
            keys.append(f"early_{sigma}_{axis}")
        keys.append(f"early_{sigma}_common_robust_lcb_rank_percentile")
        keys.append(f"early_{sigma}_aesthetic_pq_rank_percentile")
    if len(sigmas) >= 2:
        for axis in ("common_robust_lcb", "aesthetic_pq", "semantic_fit", "lyric_intelligibility", "section_coherence"):
            keys.append(f"slope_{sigmas[-1]}_minus_{sigmas[0]}_{axis}")
    return keys


def _add_slope_features(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        for a, b in (("0.8", "0.9"), ("0.7", "0.9"), ("0.7", "0.8")):
            for axis in ("common_robust_lcb", "aesthetic_pq", "semantic_fit", "lyric_intelligibility", "section_coherence"):
                va = _finite(row.get(f"early_{a}_{axis}"))
                vb = _finite(row.get(f"early_{b}_{axis}"))
                row[f"slope_{a}_minus_{b}_{axis}"] = (va - vb) if va is not None and vb is not None else None


class RidgeModel:
    def __init__(
        self,
        *,
        stage: str,
        feature_names: list[str],
        means: list[float],
        scales: list[float],
        weights: list[float],
    ) -> None:
        self.stage = stage
        self.feature_names = feature_names
        self.means = means
        self.scales = scales
        self.weights = weights

    def predict(self, row: dict[str, Any]) -> float:
        total = self.weights[0]
        for i, name in enumerate(self.feature_names):
            val = _finite(row.get(name), self.means[i])
            assert val is not None
            z = (val - self.means[i]) / self.scales[i]
            total += self.weights[i + 1] * z
        return total


def _solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    mat = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(mat[r][col]))
        if abs(mat[pivot][col]) < 1e-12:
            mat[pivot][col] = 1e-12
        if pivot != col:
            mat[col], mat[pivot] = mat[pivot], mat[col]
        div = mat[col][col]
        for j in range(col, n + 1):
            mat[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = mat[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                mat[r][j] -= factor * mat[col][j]
    return [mat[i][n] for i in range(n)]


def train_ridge(rows: list[dict[str, Any]], *, stage: str, alpha: float = 1.0) -> RidgeModel:
    base_numeric = _numeric_feature_keys(stage)
    cat_fields = ("vocal_stratum", "genre", "lyric_density", "length_bin")
    cats: dict[str, list[str]] = {}
    for field in cat_fields:
        vals = sorted({str(r.get(field)) for r in rows if r.get(field) is not None})
        cats[field] = vals
    feature_names = list(base_numeric)
    for field in cat_fields:
        for val in cats[field]:
            feature_names.append(f"cat__{field}__{val}")

    expanded_rows: list[dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        for field in cat_fields:
            for val in cats[field]:
                r[f"cat__{field}__{val}"] = 1.0 if str(row.get(field)) == val else 0.0
        expanded_rows.append(r)

    means = []
    scales = []
    for name in feature_names:
        vals = [_finite(r.get(name), 0.0) or 0.0 for r in expanded_rows]
        mean = statistics.mean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        means.append(mean)
        scales.append(sd if sd > 1e-9 else 1.0)

    p = len(feature_names) + 1
    xtx = [[0.0 for _ in range(p)] for _ in range(p)]
    xty = [0.0 for _ in range(p)]
    for row in expanded_rows:
        y = _finite(row.get(f"final_{PRIMARY_METRIC}"))
        if y is None:
            continue
        x = [1.0]
        for i, name in enumerate(feature_names):
            val = _finite(row.get(name), means[i])
            assert val is not None
            x.append((val - means[i]) / scales[i])
        for i in range(p):
            xty[i] += x[i] * y
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
    for i in range(1, p):
        xtx[i][i] += alpha
    weights = _solve_linear_system(xtx, xty)
    return RidgeModel(stage=stage, feature_names=feature_names, means=means, scales=scales, weights=weights)


def add_model_category_features_for_prediction(model: RidgeModel, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        for name in model.feature_names:
            if not name.startswith("cat__"):
                continue
            _, field, val = name.split("__", 2)
            row[name] = 1.0 if str(row.get(field)) == val else 0.0


def evaluate_models(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, float]], list[dict[str, Any]]]:
    _add_slope_features(rows)
    train = [r for r in rows if r["analysis_split"] == "train"]
    validation = [r for r in rows if r["analysis_split"] == "validation"]
    test = [r for r in rows if r["analysis_split"] == "test"]
    models = {stage: train_ridge(train, stage=stage) for stage in ("0.9", "0.8", "0.7")}
    for model in models.values():
        add_model_category_features_for_prediction(model, rows)
    learned_scores = {stage: {} for stage in ("0.9", "0.8", "0.7")}
    for row in rows:
        for stage, model in models.items():
            learned_scores[stage][row["candidate_uid"]] = model.predict(row)
            row[f"etv_ridge_{stage}_score"] = learned_scores[stage][row["candidate_uid"]]

    eval_rows = []
    for split_name, split_rows in (("train", train), ("validation", validation), ("test", test)):
        y = [_finite(r.get(f"final_{PRIMARY_METRIC}"), 0.0) or 0.0 for r in split_rows]
        raw07 = [_finite(r.get(f"early_0.7_{PRIMARY_METRIC}"), 0.0) or 0.0 for r in split_rows]
        for stage in ("0.9", "0.8", "0.7"):
            pred = [learned_scores[stage][r["candidate_uid"]] for r in split_rows]
            eval_rows.append(
                {
                    "split": split_name,
                    "model": f"ridge_stage_{stage}",
                    "spearman_final_common": _spearman(pred, y),
                    "prompt_ndcg": _prompt_ndcg(split_rows, pred),
                }
            )
        eval_rows.append(
            {
                "split": split_name,
                "model": "raw_early_0.7_common",
                "spearman_final_common": _spearman(raw07, y),
                "prompt_ndcg": _prompt_ndcg(split_rows, raw07),
            }
        )

    feature_importance = []
    model = models["0.7"]
    for name, weight in zip(model.feature_names, model.weights[1:]):
        feature_importance.append({"model": "ridge_stage_0.7", "feature": name, "abs_weight": abs(weight), "weight": weight})
    feature_importance.sort(key=lambda r: r["abs_weight"], reverse=True)

    summary = {
        "split_counts_candidates": dict(Counter(r["analysis_split"] for r in rows)),
        "split_counts_prompts": {
            split: len({r["prompt_id"] for r in rows if r["analysis_split"] == split})
            for split in ("train", "validation", "test")
        },
        "model_eval_rows": eval_rows,
        "models": {
            stage: {
                "feature_count": len(model.feature_names),
                "ridge_alpha": 1.0,
                "train_candidates": len(train),
                "train_prompts": len({r["prompt_id"] for r in train}),
            }
            for stage, model in models.items()
        },
    }
    return summary, learned_scores, feature_importance


def _prompt_ndcg(rows: list[dict[str, Any]], scores: list[float]) -> float | None:
    score_by_uid = {r["candidate_uid"]: s for r, s in zip(rows, scores)}
    vals = []
    for _pid, group in _group_by_prompt(rows).items():
        if len(group) < 2:
            continue
        pred_order = sorted(group, key=lambda r: (score_by_uid[r["candidate_uid"]], -int(r["candidate_index"])), reverse=True)
        ideal_order = _rank_desc(group, f"final_{PRIMARY_METRIC}")
        def dcg(order: list[dict[str, Any]]) -> float:
            out = 0.0
            for i, row in enumerate(order):
                rel = _finite(row.get(f"final_{PRIMARY_METRIC}"), 0.0) or 0.0
                out += rel / math.log2(i + 2.0)
            return out
        ideal = dcg(ideal_order)
        if ideal > 0:
            vals.append(dcg(pred_order) / ideal)
    return _mean(vals)


def calibrate_risk_thresholds(
    records: list[dict[str, Any]],
    learned_scores: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    rows_out = []
    validation = [r for r in records if r["analysis_split"] == "validation"]
    test = [r for r in records if r["analysis_split"] == "test"]
    for target in ("top1_prompt", "top2_candidate"):
        for eps in (0.01, 0.03, 0.05):
            best_m = 0
            best_val = 0.0
            for m in range(0, 5):
                val_metrics = analyze_schedules(
                    validation,
                    ("risk_controlled_bottom_prune_sigma0.7",),
                    metric=PRIMARY_METRIC,
                    strata=("all",),
                    random_repeats=1,
                    random_seed=20260528,
                    learned_scores=learned_scores,
                    risk_prune_bottom=m,
                )[0]
                val_fn = (
                    val_metrics["false_negative_top1_prompt_rate"]
                    if target == "top1_prompt"
                    else val_metrics["false_negative_top2_candidate_rate"]
                )
                if val_fn is not None and val_fn <= eps:
                    best_m = m
                    best_val = val_fn
            test_metrics = analyze_schedules(
                test,
                ("risk_controlled_bottom_prune_sigma0.7",),
                metric=PRIMARY_METRIC,
                strata=("all",),
                random_repeats=1,
                random_seed=20260528,
                learned_scores=learned_scores,
                risk_prune_bottom=best_m,
            )[0]
            top1_ci = _wilson_ci(test_metrics["false_negative_top1_prompt_rate"], int(test_metrics["n_prompt_evals"]))
            top2_ci = _wilson_ci(test_metrics["false_negative_top2_candidate_rate"], int(test_metrics["n_prompt_evals"]) * 2)
            rows_out.append(
                {
                    "target": target,
                    "epsilon": eps,
                    "calibrated_prune_bottom_candidates": best_m,
                    "validation_false_negative": best_val,
                    "test_false_negative_top1_prompt_rate": test_metrics["false_negative_top1_prompt_rate"],
                    "test_false_negative_top1_ci95_low": top1_ci[0],
                    "test_false_negative_top1_ci95_high": top1_ci[1],
                    "test_false_negative_top2_candidate_rate": test_metrics["false_negative_top2_candidate_rate"],
                    "test_false_negative_top2_ci95_low": top2_ci[0],
                    "test_false_negative_top2_ci95_high": top2_ci[1],
                    "test_compute_fraction": test_metrics["compute_fraction"],
                    "test_reward_fraction": test_metrics["reward_fraction"],
                    "test_winner_match": test_metrics["winner_match"],
                    "test_median_regret": test_metrics["median_regret"],
                }
            )
    return rows_out


def select_human_pairs(records: list[dict[str, Any]], learned_scores: dict[str, dict[str, float]], out_dir: Path) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260528)
    pairs = []
    prompts = sorted(_group_by_prompt(records).items())
    rng.shuffle(prompts)
    comparison_types = (
        "full_bon8_vs_raw_etp50",
        "bon4_vs_raw_etp50",
        "random_prune_vs_raw_etp50",
        "raw_etp50_vs_learned_etv50",
    )
    per_type_target = 8
    counts = Counter()
    for pid, rows in prompts:
        if len(rows) != 8:
            continue
        final_key = f"final_{PRIMARY_METRIC}"
        full = _rank_desc(rows, final_key)[0]
        raw = _rank_desc(_select_survivors(rows, "raw_schedule_a_sigma0.9_top4_sigma0.7_top2", metric=PRIMARY_METRIC, rng=rng), final_key)[0]
        bon4 = _rank_desc(_select_survivors(rows, "bon4_first4", metric=PRIMARY_METRIC, rng=rng), final_key)[0]
        rand = _rank_desc(_select_survivors(rows, "random_prune_keep4_keep2", metric=PRIMARY_METRIC, rng=rng), final_key)[0]
        etv = _rank_desc(
            _select_survivors(rows, "etv_schedule_a_sigma0.9_top4_sigma0.7_top2", metric=PRIMARY_METRIC, rng=rng, learned_scores=learned_scores),
            final_key,
        )[0]
        candidates = {
            "full_bon8_vs_raw_etp50": (full, raw),
            "bon4_vs_raw_etp50": (bon4, raw),
            "random_prune_vs_raw_etp50": (rand, raw),
            "raw_etp50_vs_learned_etv50": (raw, etv),
        }
        for comp in comparison_types:
            if counts[comp] >= per_type_target:
                continue
            a, b = candidates[comp]
            if int(a["candidate_index"]) == int(b["candidate_index"]):
                continue
            flip = rng.random() < 0.5
            left, right = (b, a) if flip else (a, b)
            pairs.append(
                {
                    "pair_id": f"{comp}__{pid}__{counts[comp]:02d}",
                    "comparison_type": comp,
                    "prompt_id": pid,
                    "split": left.get("split"),
                    "vocal_stratum": left.get("vocal_stratum"),
                    "genre": left.get("genre"),
                    "left_candidate_uid": left["candidate_uid"],
                    "right_candidate_uid": right["candidate_uid"],
                    "left_candidate_seed": left["candidate_seed"],
                    "right_candidate_seed": right["candidate_seed"],
                    "left_candidate_index": left["candidate_index"],
                    "right_candidate_index": right["candidate_index"],
                    "left_audio_path": left.get("audio_path"),
                    "right_audio_path": right.get("audio_path"),
                    "audio_status": "missing_regenerate_from_seed" if not left.get("audio_path") or not right.get("audio_path") else "present",
                    "rater_blinding": "comparison labels hidden; A/B order randomized",
                }
            )
            counts[comp] += 1
        if all(counts[c] >= per_type_target for c in comparison_types):
            break
    return pairs


def write_dataset_card(path: Path, records: list[dict[str, Any]], source_paths: list[Path], dataset_path: Path) -> None:
    prompt_counts = Counter(r["split"] for r in records if int(r["candidate_index"]) == 0)
    split_counts = Counter(r["analysis_split"] for r in records if int(r["candidate_index"]) == 0)
    stratum_counts = Counter(r["vocal_stratum"] for r in records if int(r["candidate_index"]) == 0)
    lines = [
        "# Trajectory Candidate Dataset Card",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        "## Source",
        "",
        "- Existing Early-Tweedie BoN-8 validation artifacts only.",
        "- No new generation, training, pruning+RL, Phase D, human evaluation, or reward-definition change was launched by dataset construction.",
        "",
        "## Files",
        "",
        f"- Dataset JSONL: `{dataset_path}`",
        f"- Source record files: `{[str(p) for p in source_paths]}`",
        "",
        "## Size",
        "",
        f"- Candidate records: `{len(records)}`",
        f"- Prompts: `{len({r['prompt_id'] for r in records})}`",
        "- BoN candidates per prompt: `8`",
        f"- Original split prompts: `{dict(prompt_counts)}`",
        f"- Analysis split prompts: `{dict(split_counts)}`",
        f"- Vocal/instrumental prompts: `{dict(stratum_counts)}`",
        "",
        "## Split Rule",
        "",
        "- Splits are by `prompt_id`, never by candidate.",
        "- `held_out` prompts are used only as `test` for learned-verifier evaluation.",
        "- `dev` prompts are deterministically split into train/validation by prompt hash.",
        "",
        "## Main Fields",
        "",
        "- prompt/candidate metadata: `prompt_id`, `candidate_id`, `candidate_uid`, `split`, `analysis_split`, `vocal_stratum`, `genre`, `candidate_seed`.",
        "- final labels: final reward axes, `final_common_robust_lcb`, final rank, top1/top2/top4 labels.",
        "- early features: sigma 0.9/0.8/0.7 reward vectors, robust axes, probes, ranks within prompt, and step metadata.",
        "- compute metadata: full BoN-8 step units and per-candidate early step units.",
        "",
        "## Leakage Controls",
        "",
        "- Learned models may use only early sigma features and prompt metadata.",
        "- Final labels are used only as offline training targets or evaluation labels.",
        "- Risk thresholds are calibrated on validation prompts and evaluated on held-out/test prompts.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_main_results(path: Path, payload: dict[str, Any]) -> None:
    primary = [
        r for r in payload["main_rows"]
        if r["metric"] == PRIMARY_METRIC and r["stratum"] == "all"
    ]
    lines = [
        "# Early-Tweedie Main Results",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "Paper-grade offline validation from existing 512-prompt BoN-8 artifacts. No RL training, pruning+RL, Phase D, human crowdsourcing, gate edit, or reward-definition change was launched.",
        "",
        "## Primary Robust/Common Metric",
        "",
        "| schedule | compute | reward_fraction | winner_match | top2_any | fn_top1 | fn_top2_candidate | median_regret |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in primary:
        lines.append(
            f"| {row['schedule']} | {_fmt(row['compute_fraction'], 3)} | {_fmt(row['reward_fraction'], 4)} | "
            f"{_fmt(row['winner_match'], 4)} | {_fmt(row['top2_any_retention'], 4)} | "
            f"{_fmt(row['false_negative_top1_prompt_rate'], 4)} | {_fmt(row['false_negative_top2_candidate_rate'], 4)} | "
            f"{_fmt(row['median_regret'], 4)} |"
        )
    raw_a = next(r for r in primary if r["schedule"] == "raw_schedule_a_sigma0.9_top4_sigma0.7_top2")
    bon4 = next(r for r in primary if r["schedule"] == "bon4_random_subset")
    verdict = "PASS" if (raw_a["reward_fraction"] or 0.0) > (bon4["reward_fraction"] or 0.0) else "MAJOR_RISK"
    lines.extend(
        [
            "",
            "## Same-Compute BoN-4 Check",
            "",
            f"- Raw ETP@50 reward fraction: `{_fmt(raw_a['reward_fraction'], 4)}`.",
            f"- Random-subset BoN-4 reward fraction: `{_fmt(bon4['reward_fraction'], 4)}`.",
            f"- Reviewer-risk verdict: `{verdict}`.",
        ]
    )
    bootstrap_rows = payload.get("bon4_bootstrap_rows") or []
    if bootstrap_rows:
        b = bootstrap_rows[0]
        lines.append(
            f"- Paired bootstrap delta reward fraction: `{_fmt(b.get('delta_reward_fraction'), 4)}` "
            f"(95% CI `{_fmt(b.get('ci95_low_delta_reward_fraction'), 4)}`, "
            f"`{_fmt(b.get('ci95_high_delta_reward_fraction'), 4)}`)."
        )
    cross_axis = {
        r["evaluation_metric"]: r
        for r in payload.get("cross_axis_rows", [])
        if r["schedule"] == "raw_schedule_a_sigma0.9_top4_sigma0.7_top2"
        and r.get("stratum", "all") == ("vocal_scorable" if r["evaluation_metric"] == "lyric_intelligibility" else "all")
    }
    if cross_axis:
        lines.extend(
            [
                "",
                "## Cross-Axis Caveat",
                "",
                "When pruning selects by `common_robust_lcb`, the same 50% schedule preserves the primary/common and aesthetic axes better than random BoN-4, but it does not uniformly preserve all non-primary axes. The semantic and lyric axes are the main limitation to report rather than overclaiming axis-general quality.",
            ]
        )
    lines.extend(
        [
            "",
            "## Output Tables",
            "",
            "- `orbit-research/EARLY_TWEEDIE_PARETO.csv`",
            "- `orbit-research/EARLY_TWEEDIE_AXIS_BREAKDOWN.csv`",
            "- `orbit-research/EARLY_TWEEDIE_STRATUM_BREAKDOWN.csv`",
            "- `orbit-research/EARLY_TWEEDIE_CROSS_AXIS_GENERALIZATION.csv`",
            "- `orbit-research/EARLY_TWEEDIE_BON4_BOOTSTRAP.csv`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_etv_results(path: Path, payload: dict[str, Any]) -> None:
    model_rows = payload["model_summary"]["model_eval_rows"]
    risk_rows = payload["risk_control_rows"]
    learned_primary = [
        r for r in payload["learned_rows"]
        if r["metric"] == PRIMARY_METRIC and r["stratum"] == "all"
    ]
    lines = [
        "# Early Trajectory Verifier Results",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "## Models",
        "",
        "Lightweight ridge regressors predict final robust/common reward from early sigma reward vectors, slopes, early ranks, and prompt metadata. No large neural audio model is used.",
        "",
        "## Rank/Value Prediction",
        "",
        "| split | model | spearman | prompt_ndcg |",
        "|---|---|---:|---:|",
    ]
    for row in model_rows:
        lines.append(
            f"| {row['split']} | {row['model']} | {_fmt(row['spearman_final_common'], 4)} | {_fmt(row['prompt_ndcg'], 4)} |"
        )
    lines.extend(
        [
        "",
        "## Learned Pruning Schedules",
        "",
        "The pruning schedule table is evaluated on held-out/test prompts only. Train/validation prompts are used only for fitting ridge weights and selecting risk thresholds.",
        "",
        "| schedule | compute | reward_fraction | winner_match | fn_top1 | median_regret |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in learned_primary:
        lines.append(
            f"| {row['schedule']} | {_fmt(row['compute_fraction'], 3)} | {_fmt(row['reward_fraction'], 4)} | "
            f"{_fmt(row['winner_match'], 4)} | {_fmt(row['false_negative_top1_prompt_rate'], 4)} | {_fmt(row['median_regret'], 4)} |"
        )
    lines.extend(
        [
            "",
            "## Empirically Calibrated Bottom Pruning",
            "",
            "Thresholds are calibrated on validation prompts and measured on held-out/test prompts. The confidence intervals are Wilson binomial intervals; this is empirical risk calibration, not a distribution-free guarantee.",
            "",
            "| target | epsilon | prune_bottom | test_compute | test_reward_fraction | test_fn_top1 [95% CI] | test_fn_top2_candidate [95% CI] |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in risk_rows:
        lines.append(
            f"| {row['target']} | {_fmt(row['epsilon'], 2)} | {row['calibrated_prune_bottom_candidates']} | "
            f"{_fmt(row['test_compute_fraction'], 3)} | {_fmt(row['test_reward_fraction'], 4)} | "
            f"{_fmt(row['test_false_negative_top1_prompt_rate'], 4)} "
            f"[{_fmt(row.get('test_false_negative_top1_ci95_low'), 4)}, {_fmt(row.get('test_false_negative_top1_ci95_high'), 4)}] | "
            f"{_fmt(row['test_false_negative_top2_candidate_rate'], 4)} "
            f"[{_fmt(row.get('test_false_negative_top2_ci95_low'), 4)}, {_fmt(row.get('test_false_negative_top2_ci95_high'), 4)}] |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_global_quality_outputs(md_path: Path, csv_path: Path) -> None:
    src = Path("orbit-research/global_quality_structure_analysis_20260527/globalness_by_unit_axis_source.csv")
    rows = []
    if src.exists():
        with src.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    out_rows = []
    for row in rows:
        out_rows.append(
            {
                "unit": row.get("unit"),
                "axis": row.get("axis"),
                "source": row.get("source"),
                "between_share": row.get("between_share"),
                "between_within_ratio": row.get("ratio") or row.get("between_within_ratio"),
                "sign_consistency": row.get("sign_consistency"),
                "crossing_frequency": row.get("crossing_frequency"),
                "globalness_index": row.get("globalness_index"),
            }
        )
    if out_rows:
        _write_csv(csv_path, out_rows)
    lines = [
        "# Global Quality Mechanism Figures",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        "## Scope",
        "",
        "Plot-ready mechanism summary from cached Track B outputs. No new source separation, human evaluation, Phase D, RL training, or reward change was launched.",
        "",
        "## Interpretation",
        "",
        "For ACE-Step short-form outputs, local-window rewards appear to sample persistent global trajectory quality more than isolated local failures. This does not imply music has no local structure, and it does not establish FixedWin as causal local credit.",
        "",
        "## Plot Tables",
        "",
        f"- Mechanism table: `{csv_path}`",
        "- Existing top/bottom curves: `orbit-research/global_quality_structure_analysis_20260527/top_bottom_reward_time_curves.csv`",
        "- Existing C1 common eval summary: `orbit-research/global_quality_structure_analysis_20260527/c1_common_eval_summary.csv`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reviewer_risk_audit(
    path: Path,
    main_rows: list[dict[str, Any]],
    model_summary: dict[str, Any],
    cross_axis_rows: list[dict[str, Any]],
) -> None:
    primary = [r for r in main_rows if r["metric"] == PRIMARY_METRIC and r["stratum"] == "all"]
    by_sched = {r["schedule"]: r for r in primary}
    etp = by_sched.get("raw_schedule_a_sigma0.9_top4_sigma0.7_top2", {})
    bon4 = by_sched.get("bon4_random_subset", {})
    etp_beats_bon4 = (etp.get("reward_fraction") or 0.0) > (bon4.get("reward_fraction") or 0.0)
    # Per-axis headline stratum: lyric_intelligibility is only meaningful on vocal_scorable
    # (EN vocal); every other axis uses "all". Older rows had no stratum field -> default "all".
    def _headline_stratum_for(metric: str) -> str:
        return "vocal_scorable" if metric == "lyric_intelligibility" else "all"
    cross_axis_etp = [
        r for r in cross_axis_rows
        if r["schedule"] == "raw_schedule_a_sigma0.9_top4_sigma0.7_top2"
        and r["evaluation_metric"] != PRIMARY_METRIC
        and r.get("stratum", "all") == _headline_stratum_for(r["evaluation_metric"])
    ]
    if cross_axis_etp:
        cross_axis_text = "; ".join(
            f"{r['evaluation_metric']}={_fmt(r.get('reward_fraction'), 4)}"
            f"{' [EN-vocal n='+str(r.get('n_prompt_evals'))+']' if r['evaluation_metric']=='lyric_intelligibility' else ''}"
            for r in cross_axis_etp
        )
        circularity_evidence = (
            "Primary pruning uses robust/common reward; cross-axis evaluation after common-selected pruning is available "
            f"({cross_axis_text}) and separates selection from non-primary axes."
        )
    else:
        circularity_evidence = (
            "Primary pruning and evaluation both include robust/common reward; axis breakdown and human packet mitigate "
            "but do not eliminate circularity."
        )
    risks = [
        ("Is pruning too naive?", "Raw ETP has strong reward retention; learned ETV is evaluated separately.", "Human spot-check and failure-case examples remain useful.", "Required for main claim: partly."),
        ("Is this just BoN-4?", f"ETP@50 reward fraction {_fmt(etp.get('reward_fraction'))} vs BoN-4 {_fmt(bon4.get('reward_fraction'))}; verdict {'passes' if etp_beats_bon4 else 'major risk'}.", "Need emphasize same-compute comparison in paper.", "Required for main claim: yes."),
        ("Is evaluation circular?", circularity_evidence, "Human spot-check not yet launched.", "Required for ICLR: likely."),
        ("Does it work beyond ACE-Step?", "Current evidence is ACE-Step-only.", "Cross-backbone validation absent by boundary.", "Required for main claim: no if scope is ACE-Step."),
        ("Why is late sigma not trivial?", "Schedules prune at 0.9/0.8/0.7 before final generation and report compute fractions.", "Need visualize quality-vs-sigma retention.", "Required for main claim: yes."),
        ("What does learned ETV add?", "Learned ridge verifier is compared against raw ETP; if no improvement, raw ETP remains the method and ETV is analysis.", "No GBDT/LambdaMART package available in current env.", "Required: no, but helps novelty."),
        ("Does human listening support this?", "Packet manifest prepared only; no crowdsourcing launched.", "PI spot-check needed before paper claim.", "Required for final paper: strongly recommended."),
        ("Why not RL?", "C1 backend worked but common dev eval had no clear win; RL rescue stopped.", "None for current inference-time paper.", "Required: boundary explanation yes."),
        ("Failure cases / late bloomers?", "False-negative and regret columns identify late-bloomer risk.", "Need qualitative packet examples.", "Required: yes for reviewer trust."),
    ]
    lines = [
        "# ICLR Reviewer-Risk Audit",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        "| Risk | Current Evidence | Missing Evidence | Main-Claim Requirement |",
        "|---|---|---|---|",
    ]
    for risk in risks:
        lines.append(f"| {risk[0]} | {risk[1]} | {risk[2]} | {risk[3]} |")
    lines.extend(
        [
            "",
            "## Boundary Note",
            "",
            "This audit does not authorize Phase D, human crowdsourcing, pruning+RL, new RL training, reward-definition changes, or a canonical proposal rewrite.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("orbit-research"))
    parser.add_argument("--random-repeats", type=int, default=100)
    args = parser.parse_args()

    records = enrich_records(_read_records(args.records))
    _add_slope_features(records)
    dataset_path = args.output_dir / "trajectory_candidate_dataset.jsonl"
    _write_jsonl(dataset_path, records)
    write_dataset_card(args.output_dir / "TRAJECTORY_CANDIDATE_DATASET_CARD.md", records, args.records, dataset_path)

    model_summary, learned_scores, feature_importance = evaluate_models(records)
    main_rows = []
    for metric in EVAL_METRICS:
        main_rows.extend(
            analyze_schedules(
                records,
                RAW_SCHEDULES,
                metric=metric,
                strata=STRATA_EXT,
                random_repeats=args.random_repeats,
                random_seed=20260528,
            )
        )
    learned_rows = analyze_schedules(
        [r for r in records if r["analysis_split"] == "test"],
        LEARNED_SCHEDULES,
        metric=PRIMARY_METRIC,
        strata=STRATA,
        random_repeats=1,
        random_seed=20260528,
        learned_scores=learned_scores,
    )
    risk_rows = calibrate_risk_thresholds(records, learned_scores)
    cross_axis_rows = analyze_cross_axis_generalization(
        records,
        RAW_SCHEDULES,
        selection_metric=PRIMARY_METRIC,
        evaluation_metrics=EVAL_METRICS,
        random_repeats=args.random_repeats,
        random_seed=20260528,
        strata=STRATA_EXT,
    )
    bon4_bootstrap_rows = paired_bon4_bootstrap(
        records,
        metric=PRIMARY_METRIC,
        random_repeats=args.random_repeats,
        bootstrap_repeats=5000,
        random_seed=20260528,
    )
    all_pareto_rows = main_rows + learned_rows
    payload = {
        "schema_version": "early_trajectory_verifier_analysis_v1",
        "generated_at_utc": _now_utc(),
        "source_records": [str(p) for p in args.records],
        "dataset_path": str(dataset_path),
        "n_candidates": len(records),
        "n_prompts": len({r["prompt_id"] for r in records}),
        "splits": dict(Counter(r["analysis_split"] for r in records)),
        "main_rows": main_rows,
        "learned_rows": learned_rows,
        "cross_axis_rows": cross_axis_rows,
        "bon4_bootstrap_rows": bon4_bootstrap_rows,
        "model_summary": model_summary,
        "risk_control_rows": risk_rows,
        "safety": {
            "rl_training_launched": False,
            "pruning_rl_launched": False,
            "phase_d_launched": False,
            "human_crowdsourcing_launched": False,
            "gate_v1_modified": False,
            "reward_definitions_changed": False,
            "prompt_splits_changed": False,
            "canonical_proposal_rewritten": False,
        },
    }
    (args.output_dir / "EARLY_TWEEEDIE_MAIN_RESULTS.typo_guard").unlink(missing_ok=True)
    (args.output_dir / "EARLY_TWEEDIE_MAIN_RESULTS.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_main_results(args.output_dir / "EARLY_TWEEDIE_MAIN_RESULTS.md", payload)
    _write_csv(args.output_dir / "EARLY_TWEEDIE_PARETO.csv", all_pareto_rows)
    # stratum=all retained verbatim for audit trail (NOTE: the lyric_intelligibility rows here
    # are contaminated by the 196 instrumental 1.0 sentinels + non-EN floor — see *_HEADLINE).
    _write_csv(args.output_dir / "EARLY_TWEEDIE_AXIS_BREAKDOWN.csv", [r for r in all_pareto_rows if r["stratum"] == "all"])
    # Headline view: lyric_intelligibility on vocal_scorable (EN vocal), every other axis on "all".
    _headline_stratum = lambda m: "vocal_scorable" if m == "lyric_intelligibility" else "all"
    _write_csv(
        args.output_dir / "EARLY_TWEEDIE_AXIS_BREAKDOWN_HEADLINE.csv",
        [r for r in all_pareto_rows if r["stratum"] == _headline_stratum(r["metric"])],
    )
    _write_csv(
        args.output_dir / "EARLY_TWEEDIE_STRATUM_BREAKDOWN.csv",
        [r for r in all_pareto_rows if r["metric"] in (PRIMARY_METRIC, "lyric_intelligibility")],
    )
    _write_csv(args.output_dir / "EARLY_TWEEDIE_CROSS_AXIS_GENERALIZATION.csv", cross_axis_rows)
    _write_csv(args.output_dir / "EARLY_TWEEDIE_BON4_BOOTSTRAP.csv", bon4_bootstrap_rows)
    (args.output_dir / "EARLY_TRAJECTORY_VERIFIER_RESULTS.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_etv_results(args.output_dir / "EARLY_TRAJECTORY_VERIFIER_RESULTS.md", payload)
    _write_csv(args.output_dir / "EARLY_VALUE_FEATURE_IMPORTANCE.csv", feature_importance[:100])
    _write_csv(args.output_dir / "RISK_CONTROLLED_PRUNING_TABLE.csv", risk_rows)

    human_dir = args.output_dir / "human_spotcheck_packet_20260528"
    pairs = select_human_pairs(records, learned_scores, human_dir)
    _write_jsonl(human_dir / "human_spotcheck_pairs.jsonl", pairs)
    (human_dir / "scoring_sheet_template.csv").write_text(
        "pair_id,left_or_right_preferred,overall_preference,musicality_preference,prompt_fit_preference,vocal_lyric_issue,notes\n",
        encoding="utf-8",
    )
    (human_dir / "HUMAN_SPOTCHECK_PACKET_MANIFEST.md").write_text(
        "\n".join(
            [
                "# Human Spot-Check Packet Manifest",
                "",
                f"Generated UTC: `{_now_utc()}`",
                "",
                "This packet is prepared for PI/manual listening only. No crowdsourcing or human eval was launched.",
                "",
                f"- Pair manifest: `{human_dir / 'human_spotcheck_pairs.jsonl'}`",
                f"- Scoring template: `{human_dir / 'scoring_sheet_template.csv'}`",
                f"- Pairs: `{len(pairs)}`",
                "- Audio status: existing validation run did not save audio; rows marked `missing_regenerate_from_seed` need deterministic audio regeneration before listening.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    write_global_quality_outputs(
        args.output_dir / "GLOBAL_QUALITY_MECHANISM_FIGURES.md",
        args.output_dir / "GLOBAL_QUALITY_MECHANISM_TABLES.csv",
    )
    write_reviewer_risk_audit(args.output_dir / "ICLR_REVIEWER_RISK_AUDIT.md", main_rows, model_summary, cross_axis_rows)
    print(json.dumps({"status": "PASS", "dataset": str(dataset_path), "prompts": payload["n_prompts"], "candidates": payload["n_candidates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
