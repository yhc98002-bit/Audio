#!/usr/bin/env python3
"""CPU-only Track B global quality structure analysis."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
H3_RESULTS = REPO_ROOT / "runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/results.jsonl"
TIME_UNIFORM_JSON = REPO_ROOT / "orbit-research/TIME_UNIFORM_QUALITY_DIAGNOSTIC.json"
C1_COMMON_ROOT = REPO_ROOT / "runs/phase_c1_common_downstream_eval_20260526_helper01"
C1_TRIAGE_ROOT = REPO_ROOT / "runs/phase_c1_checkpoint_triage_eval_20260526"
C1_STEPWISE = REPO_ROOT / "orbit-research/phase_c1_learning_signal_audit_20260526/fixedwin_section_stepwise.csv"
OUT_DIR = REPO_ROOT / "orbit-research/global_quality_structure_analysis_20260527"
OUT_JSON = REPO_ROOT / "orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.json"
OUT_MD = REPO_ROOT / "orbit-research/GLOBAL_QUALITY_STRUCTURE_ANALYSIS.md"

UNITS = ["CU-FW", "CU-BW", "CU-MS", "CU-LS", "CU-NULL-rand-section"]
AXES = ["musicality", "prompt_fit", "coherence"]
SOURCES = [
    ("human_pref_proxy", "human_pref_proxy_vector"),
    ("section_reward_delta", "section_reward_delta_vector"),
]
PRIMARY_UNITS = {"CU-FW", "CU-BW"}
PRIMARY_AXES = {"musicality", "prompt_fit"}
PRIMARY_SOURCE = "human_pref_proxy"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in fields})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return repr(value)
    return value


def _finite(values: list[float]) -> list[float]:
    return [float(v) for v in values if math.isfinite(float(v))]


def _mean(values: list[float]) -> float | None:
    vals = _finite(values)
    return sum(vals) / len(vals) if vals else None


def _pstdev(values: list[float]) -> float | None:
    vals = _finite(values)
    if not vals:
        return None
    return statistics.pstdev(vals) if len(vals) > 1 else 0.0


def _median(values: list[float]) -> float | None:
    vals = _finite(values)
    return statistics.median(vals) if vals else None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 2:
        return None
    xvals, yvals = zip(*pairs)
    mx = sum(xvals) / len(xvals)
    my = sum(yvals) / len(yvals)
    vx = sum((x - mx) ** 2 for x in xvals)
    vy = sum((y - my) ** 2 for y in yvals)
    if vx <= 0 or vy <= 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    return cov / math.sqrt(vx * vy)


def _ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and vals[order[j]] == vals[order[i]]:
            j += 1
        rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = rank
        i = j
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 3:
        return None
    xvals, yvals = zip(*pairs)
    return _pearson(_ranks(list(xvals)), _ranks(list(yvals)))


def _slope(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(pairs) < 2:
        return None
    xvals, yvals = zip(*pairs)
    mx = sum(xvals) / len(xvals)
    my = sum(yvals) / len(yvals)
    denom = sum((x - mx) ** 2 for x in xvals)
    if denom <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pairs) / denom


def _sign(value: float | None, eps: float = 1e-12) -> int:
    if value is None or not math.isfinite(float(value)):
        return 0
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def _crossing_frequency(values: list[float | None]) -> float | None:
    signs = [_sign(v) for v in values]
    signs = [s for s in signs if s != 0]
    if len(signs) < 2:
        return None
    crossings = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    return crossings / (len(signs) - 1)


def _quantile_groups(prompt_means: dict[str, float], frac: float = 0.25) -> tuple[set[str], set[str]]:
    ordered = sorted(prompt_means.items(), key=lambda kv: kv[1])
    k = max(1, int(math.floor(len(ordered) * frac)))
    bottom = {pid for pid, _ in ordered[:k]}
    top = {pid for pid, _ in ordered[-k:]}
    return top, bottom


def _dedupe_primary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Avoid double-counting sigma-key duplicates in cached human-pref proxies."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in sorted(rows, key=lambda r: (r["unit"], r["axis"], r["source"], str(r["sigma"]))):
        key = (str(row["unit"]), str(row["axis"]), str(row["source"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _time_bin_curve(groups: dict[str, list[float]], top: set[str], bottom: set[str], n_bins: int = 8) -> list[dict[str, Any]]:
    accum: dict[tuple[str, int], list[float]] = defaultdict(list)
    for prompt_id, values in groups.items():
        label = "top" if prompt_id in top else "bottom" if prompt_id in bottom else None
        if label is None:
            continue
        for idx, value in enumerate(values):
            if not math.isfinite(value):
                continue
            pos = (idx + 0.5) / max(len(values), 1)
            bin_id = min(n_bins, int(pos * n_bins) + 1)
            accum[(label, bin_id)].append(value)
    rows: list[dict[str, Any]] = []
    for bin_id in range(1, n_bins + 1):
        top_vals = accum.get(("top", bin_id), [])
        bottom_vals = accum.get(("bottom", bin_id), [])
        top_mean = _mean(top_vals)
        bottom_mean = _mean(bottom_vals)
        gap = top_mean - bottom_mean if top_mean is not None and bottom_mean is not None else None
        rows.append(
            {
                "position_bin": bin_id,
                "position_range": f"{(bin_id - 1) / n_bins:.3f}-{bin_id / n_bins:.3f}",
                "top_mean": top_mean,
                "bottom_mean": bottom_mean,
                "top_minus_bottom_gap": gap,
                "top_segment_n": len(top_vals),
                "bottom_segment_n": len(bottom_vals),
            }
        )
    return rows


def _variance_decomp(groups: dict[str, list[float]]) -> dict[str, Any]:
    prompt_means = {pid: _mean(vals) for pid, vals in groups.items()}
    prompt_means = {pid: val for pid, val in prompt_means.items() if val is not None}
    all_values = [v for vals in groups.values() for v in vals if math.isfinite(v)]
    grand = _mean(all_values)
    if grand is None:
        return {"status": "missing"}
    between_ss = 0.0
    within_ss = 0.0
    within_pstd: list[float] = []
    within_range: list[float] = []
    for prompt_id, vals in groups.items():
        vals = _finite(vals)
        if not vals:
            continue
        pmean = sum(vals) / len(vals)
        between_ss += len(vals) * (pmean - grand) ** 2
        within_ss += sum((v - pmean) ** 2 for v in vals)
        within_pstd.append(statistics.pstdev(vals) if len(vals) > 1 else 0.0)
        within_range.append(max(vals) - min(vals))
    total = between_ss + within_ss
    share = between_ss / total if total > 1e-12 else None
    ratio = between_ss / within_ss if within_ss > 1e-12 else None
    status = "usable" if share is not None and (_median(within_range) or 0.0) > 1e-9 else "degenerate_or_low_dynamic_range"
    return {
        "status": status,
        "n_prompts": len(prompt_means),
        "n_segments_total": len(all_values),
        "segments_per_prompt_median": _median([len(_finite(vals)) for vals in groups.values()]),
        "mean_value": grand,
        "between_ss": between_ss,
        "within_ss": within_ss,
        "between_share": share,
        "between_within_ratio": ratio,
        "median_within_prompt_pstd": _median(within_pstd),
        "median_within_prompt_range": _median(within_range),
        "prompt_mean_std": _pstdev(list(prompt_means.values())),
    }


def analyze_h3() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    records = _read_jsonl(H3_RESULTS)
    groups: dict[tuple[str, str, str, str], dict[str, list[float]]] = defaultdict(dict)
    for obj in records:
        prompt_id = str(obj["prompt_id"])
        for unit in UNITS:
            unit_data = obj.get("per_unit", {}).get(unit, {})
            if not unit_data.get("applicable"):
                continue
            for axis in AXES:
                axis_data = unit_data.get(axis)
                if not isinstance(axis_data, dict):
                    continue
                for sigma, sigma_data in axis_data.items():
                    for source_name, vector_key in SOURCES:
                        vals = sigma_data.get(vector_key)
                        if isinstance(vals, list):
                            groups[(unit, axis, str(sigma), source_name)][prompt_id] = _finite(vals)

    variance_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for (unit, axis, sigma, source), prompt_groups in sorted(groups.items()):
        decomp = _variance_decomp(prompt_groups)
        prompt_means = {pid: _mean(vals) for pid, vals in prompt_groups.items()}
        prompt_means = {pid: val for pid, val in prompt_means.items() if val is not None}
        top, bottom = _quantile_groups(prompt_means)
        curve = _time_bin_curve(prompt_groups, top, bottom, n_bins=8)
        gaps = [row["top_minus_bottom_gap"] for row in curve]
        valid_gaps = [float(g) for g in gaps if g is not None and math.isfinite(float(g))]
        sign_consistency = (sum(1 for g in valid_gaps if g > 0) / len(valid_gaps)) if valid_gaps else None
        crossing = _crossing_frequency(gaps)
        gap_mean = _mean(valid_gaps)
        gap_std = _pstdev(valid_gaps)
        gap_cv = (gap_std / abs(gap_mean)) if gap_mean not in (None, 0.0) and gap_std is not None else None
        if decomp.get("status") == "usable" and decomp.get("between_share") is not None and sign_consistency is not None:
            globalness_index = statistics.mean(
                [
                    float(decomp["between_share"]),
                    float(sign_consistency),
                    1.0 - float(crossing or 0.0),
                ]
            )
        else:
            globalness_index = None
        row = {
            "unit": unit,
            "axis": axis,
            "sigma": sigma,
            "source": source,
            "primary_track_b_cell": unit in PRIMARY_UNITS and axis in PRIMARY_AXES and source == PRIMARY_SOURCE,
            "status": decomp.get("status"),
            "n_prompts": decomp.get("n_prompts"),
            "n_segments_total": decomp.get("n_segments_total"),
            "segments_per_prompt_median": decomp.get("segments_per_prompt_median"),
            "between_share": decomp.get("between_share"),
            "between_within_ratio": decomp.get("between_within_ratio"),
            "sign_consistency": sign_consistency,
            "crossing_frequency": crossing,
            "globalness_index": globalness_index,
            "top_bottom_gap_mean": gap_mean,
            "top_bottom_gap_cv": gap_cv,
            "median_within_prompt_pstd": decomp.get("median_within_prompt_pstd"),
            "median_within_prompt_range": decomp.get("median_within_prompt_range"),
            "prompt_mean_std": decomp.get("prompt_mean_std"),
        }
        variance_rows.append(row)
        for curve_row in curve:
            curve_rows.append(
                {
                    "unit": unit,
                    "axis": axis,
                    "sigma": sigma,
                    "source": source,
                    **curve_row,
                }
            )
    usable_primary = [
        row for row in variance_rows
        if row["primary_track_b_cell"] and row["status"] == "usable" and row["between_share"] is not None
    ]
    unique_usable_primary = _dedupe_primary_rows(usable_primary)
    aggregate = {
        "h3_records": len(records),
        "usable_primary_cells": len(unique_usable_primary),
        "primary_median_between_share": _median([row["between_share"] for row in unique_usable_primary]),
        "primary_median_between_within_ratio": _median(
            [row["between_within_ratio"] for row in unique_usable_primary if row["between_within_ratio"] is not None]
        ),
        "primary_median_sign_consistency": _median([row["sign_consistency"] for row in unique_usable_primary]),
        "primary_median_crossing_frequency": _median([row["crossing_frequency"] for row in unique_usable_primary]),
        "primary_median_globalness_index": _median([row["globalness_index"] for row in unique_usable_primary]),
        "primary_cells_between_share_ge_0_5": sum(1 for row in unique_usable_primary if row["between_share"] >= 0.5),
        "primary_cells_crossing_frequency_zero": sum(1 for row in unique_usable_primary if row["crossing_frequency"] == 0.0),
        "primary_summary_deduplication": "deduped by unit/axis/source to avoid double-counting sigma-key duplicates in human_pref_proxy vectors",
    }
    return variance_rows, curve_rows, aggregate


def analyze_c1_common() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, root in [
        ("full64_step1000", C1_COMMON_ROOT),
        ("triage16_sweep", C1_TRIAGE_ROOT),
    ]:
        summary_path = root / "method_by_checkpoint_summary.csv"
        delta_path = root / "paired_delta_vs_base.csv"
        summary = _read_csv_dicts(summary_path)
        deltas = {
            row["target_id"]: row for row in _read_csv_dicts(delta_path)
        }
        for row in summary:
            out = {
                "source_eval": label,
                "target_id": row.get("target_id"),
                "method": row.get("method"),
                "checkpoint_label": row.get("checkpoint_label"),
                "n_prompts": _to_float(row.get("n_prompts")),
                "common_robust_lcb_mean": _to_float(row.get("common_robust_lcb_mean")),
                "common_robust_lcb_std": _to_float(row.get("common_robust_lcb_std")),
                "delta_common_robust_lcb_mean": _to_float(deltas.get(row.get("target_id"), {}).get("delta_common_robust_lcb_mean")),
                "fixedwin_process_mean": _to_float(row.get("fixedwin_process_mean")),
                "section_process_mean": _to_float(row.get("section_process_mean")),
                "semantic_fit_mean": _to_float(row.get("semantic_fit_mean")),
                "lyric_intelligibility_mean": _to_float(row.get("lyric_intelligibility_mean")),
                "section_coherence_mean": _to_float(row.get("section_coherence_mean")),
            }
            rows.append(out)
    return rows


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return val if math.isfinite(val) else None


def analyze_training_alignment() -> list[dict[str, Any]]:
    rows = _read_csv_dicts(C1_STEPWISE)
    if not rows:
        return []
    steps = [_to_float(row.get("step")) for row in rows]
    fixed = [_to_float(row.get("fixedwin_reward_mean")) for row in rows]
    section = [_to_float(row.get("section_reward_mean")) for row in rows]
    valid = [(s, f, c) for s, f, c in zip(steps, fixed, section) if s is not None and f is not None and c is not None]
    if not valid:
        return []
    steps_v = [x[0] for x in valid]
    fixed_v = [x[1] for x in valid]
    section_v = [x[2] for x in valid]
    diff = [f - s for _, f, s in valid]
    return [
        {
            "source": str(C1_STEPWISE.relative_to(REPO_ROOT)),
            "n_steps": len(valid),
            "fixedwin_section_pearson": _pearson(fixed_v, section_v),
            "fixedwin_section_spearman": _spearman(fixed_v, section_v),
            "mean_fixedwin_reward": _mean(fixed_v),
            "mean_section_reward": _mean(section_v),
            "mean_fixedwin_minus_section": _mean(diff),
            "std_fixedwin_minus_section": _pstdev(diff),
            "abs_diff_mean": _mean([abs(x) for x in diff]),
            "diff_crossing_frequency": _crossing_frequency(diff),
            "fixedwin_slope_per_step": _slope(steps_v, fixed_v),
            "section_slope_per_step": _slope(steps_v, section_v),
        }
    ]


def find_cached_stem_artifacts() -> dict[str, Any]:
    patterns = ("demucs", "stem", "stems", "drum", "bass", "other", "vocals")
    hits: list[str] = []
    for root in [REPO_ROOT / "runs", REPO_ROOT / "orbit-research"]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = str(path.relative_to(REPO_ROOT)).lower()
            if any(p in name for p in patterns):
                if "h3_vocal_stratum" in name:
                    continue
                hits.append(str(path.relative_to(REPO_ROOT)))
                if len(hits) >= 50:
                    break
        if len(hits) >= 50:
            break
    stem_like = [
        h for h in hits
        if any(token in h.lower() for token in ("stem", "stems", "vocals.wav", "drums.wav", "bass.wav", "other.wav"))
    ]
    demucs_failures = [h for h in hits if "demucs_import_bug" in h.lower()]
    return {
        "searched_roots": ["runs", "orbit-research"],
        "cached_stem_feature_files_found": stem_like,
        "demucs_related_non_stem_files": hits,
        "demucs_failure_artifacts_found": demucs_failures,
        "new_source_separation_launched": False,
    }


def _format_float(value: Any, digits: int = 3) -> str:
    if value is None:
        return "NA"
    try:
        val = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(val):
        return "NA"
    return f"{val:.{digits}f}"


def write_markdown(payload: dict[str, Any]) -> None:
    variance_rows = payload["tables"]["globalness_by_unit_axis_source"]
    primary = [
        r for r in variance_rows
        if r["primary_track_b_cell"] and r["status"] == "usable" and r["source"] == PRIMARY_SOURCE
    ]
    primary = _dedupe_primary_rows(primary)
    primary = sorted(primary, key=lambda r: (r["unit"], r["axis"], r["sigma"]))
    c1_full = [
        r for r in payload["tables"]["c1_common_eval_summary"]
        if r["source_eval"] == "full64_step1000"
    ]
    training = payload["tables"]["c1_fixedwin_section_training_alignment"]
    lines: list[str] = []
    lines.append("# Global Quality Structure Analysis")
    lines.append("")
    lines.append(f"Generated UTC: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append("Track B status: `COMPLETE_CPU_ONLY`.")
    lines.append("")
    lines.append(
        "For ACE-Step short-form outputs, local-window rewards appear to track "
        "persistent global quality more than isolated local failures."
    )
    lines.append("")
    lines.append(
        "This is a cautious mechanism read from cached H3 local proxy vectors and "
        "C1 common-eval summaries. It is not a new held-out run, not human eval, "
        "and not source-separation evidence."
    )
    lines.append("")
    lines.append("## Source Artifacts")
    lines.append("")
    for path in payload["source_artifacts"]:
        lines.append(f"- `{path}`")
    lines.append("")
    lines.append("## Primary H3 Globalness Summary")
    lines.append("")
    agg = payload["aggregate_summary"]
    lines.append("| metric | value |")
    lines.append("|---|---:|")
    for key in [
        "h3_records",
        "usable_primary_cells",
        "primary_median_between_share",
        "primary_median_between_within_ratio",
        "primary_median_sign_consistency",
        "primary_median_crossing_frequency",
        "primary_median_globalness_index",
        "primary_cells_between_share_ge_0_5",
        "primary_cells_crossing_frequency_zero",
    ]:
        lines.append(f"| {key} | {_format_float(agg.get(key), 3)} |")
    lines.append("")
    lines.append(
        "Primary cells are CU-FW/CU-BW musicality and prompt-fit using the "
        "cached `human_pref_proxy_vector`. Coherence cells are treated cautiously "
        "because several cached local coherence vectors are degenerate. Human-pref "
        "proxy rows are de-duplicated by unit/axis/source in the summary because "
        "musicality appears under both sigma keys with the same proxy vector."
    )
    lines.append("")
    lines.append("| unit | axis | sigma | n | between_share | ratio | sign_consistency | crossing_frequency | globalness_index |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in primary:
        lines.append(
            "| {unit} | {axis} | {sigma} | {n} | {share} | {ratio} | {sign} | {cross} | {gidx} |".format(
                unit=row["unit"],
                axis=row["axis"],
                sigma=row["sigma"],
                n=int(row["n_prompts"]),
                share=_format_float(row["between_share"], 3),
                ratio=_format_float(row["between_within_ratio"], 3),
                sign=_format_float(row["sign_consistency"], 3),
                cross=_format_float(row["crossing_frequency"], 3),
                gidx=_format_float(row["globalness_index"], 3),
            )
        )
    lines.append("")
    lines.append("## Top-Vs-Bottom Reward-Time Curves")
    lines.append("")
    lines.append(
        "Top and bottom quartiles are selected by each prompt's mean local proxy "
        "value. Across the primary cells, top-minus-bottom gaps keep the same "
        "positive sign across normalized time bins; crossing frequency is 0.0 "
        "for those cells. This favors a persistent-quality interpretation over "
        "a few isolated bad windows."
    )
    lines.append("")
    lines.append(
        "Caveat: top/bottom selection is in-sample, so gap magnitudes are "
        "descriptive rather than predictive. Also, because sign consistency is "
        "1.0 and crossing frequency is 0.0 for all primary cells, the composite "
        "globalness index is a monotone transform of between-share in these data."
    )
    lines.append("")
    lines.append("Plot-ready curve table:")
    lines.append("")
    lines.append("- `orbit-research/global_quality_structure_analysis_20260527/top_bottom_reward_time_curves.csv`")
    lines.append("")
    lines.append("## FixedWin Interpretation")
    lines.append("")
    lines.append(
        "CU-FW does not look like a clean isolated local-credit signal in the "
        "cached H3 vectors. Its primary musicality/prompt-fit cells have high "
        "between-song share and zero top-bottom curve crossings, close to CU-BW. "
        "This makes FixedWin more consistent with a stable local proxy for global "
        "quality than with true local failure localization."
    )
    lines.append("")
    if training:
        t = training[0]
        lines.append(
            "C1 training traces also show FixedWin and Section process rewards "
            f"move together over {int(t['n_steps'])} steps "
            f"(Pearson {_format_float(t['fixedwin_section_pearson'], 3)}, "
            f"Spearman {_format_float(t['fixedwin_section_spearman'], 3)}). "
            "This trace is training-time evidence, not a within-song local-failure test."
        )
        lines.append("")
    lines.append("## C1 Common Eval Connection")
    lines.append("")
    lines.append("| target | n | robust_lcb_mean | delta_vs_base | fixedwin_process | section_process |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in c1_full:
        lines.append(
            "| {target} | {n} | {mean} | {delta} | {fw} | {sec} |".format(
                target=row["target_id"],
                n=int(row["n_prompts"] or 0),
                mean=_format_float(row["common_robust_lcb_mean"], 6),
                delta=_format_float(row["delta_common_robust_lcb_mean"], 6),
                fw=_format_float(row["fixedwin_process_mean"], 6),
                sec=_format_float(row["section_process_mean"], 6),
            )
        )
    lines.append("")
    lines.append(
        "C1 common eval is not itself a time-local diagnostic, but it is consistent "
        "with the mechanism: Section and window-local PRM variants do not separate "
        "strongly on common downstream robust-LCB when evaluated with the same "
        "sampler and metric. This helps explain why Section/window-local PRM "
        "training may not yield strong improvement if local rewards mostly mirror "
        "persistent song-level quality."
    )
    lines.append("")
    lines.append("## Demucs / Stem Features")
    lines.append("")
    demucs = payload["demucs_stem_cache_check"]
    if demucs["cached_stem_feature_files_found"]:
        lines.append("Cached stem-like artifacts were found, but this analysis did not launch new source separation:")
        for item in demucs["cached_stem_feature_files_found"][:20]:
            lines.append(f"- `{item}`")
    else:
        lines.append(
            "No cached Demucs/stem feature files were found. No source separation "
            "or heavy Demucs job was launched."
        )
    lines.append("")
    lines.append("## Output Tables")
    lines.append("")
    for path in payload["output_tables"].values():
        lines.append(f"- `{path}`")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append("- Cached H3 proxy vectors are not human ratings.")
    lines.append("- CU-LS is only applicable to vocal prompts and is exploratory.")
    lines.append("- CU-FW coherence vectors are entirely constant; CU-BW coherence has near-zero within-prompt dynamic range. Coherence should not carry the conclusion.")
    lines.append("- CU-MS and CU-NULL-rand-section have identical musicality/coherence value sets in the cached H3 artifact, so CU-NULL is informative mainly for prompt_fit.")
    lines.append("- The globalness index adds no independent information beyond between-share for the primary cells because sign consistency is 1.0 and crossing frequency is 0.0.")
    lines.append("- C1 common eval supports mechanism interpretation but is not a local-window failure test.")
    lines.append("- No Phase D, human eval, pruning+RL, RL training, reward-definition change, sigma-policy change, or gate_v1 edit was performed.")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(
        "Use the result as Track B mechanism support: local-window rewards appear "
        "to be stable proxies for global quality in ACE-Step short-form outputs. "
        "Do not overclaim that all local failures are absent, or that PRM variants "
        "are proven ineffective."
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    variance_rows, curve_rows, h3_aggregate = analyze_h3()
    c1_rows = analyze_c1_common()
    training_rows = analyze_training_alignment()
    demucs = find_cached_stem_artifacts()
    existing_time_uniform = json.loads(TIME_UNIFORM_JSON.read_text(encoding="utf-8")) if TIME_UNIFORM_JSON.exists() else {}

    variance_fields = [
        "unit", "axis", "sigma", "source", "primary_track_b_cell", "status",
        "n_prompts", "n_segments_total", "segments_per_prompt_median",
        "between_share", "between_within_ratio", "sign_consistency",
        "crossing_frequency", "globalness_index", "top_bottom_gap_mean",
        "top_bottom_gap_cv", "median_within_prompt_pstd",
        "median_within_prompt_range", "prompt_mean_std",
    ]
    curve_fields = [
        "unit", "axis", "sigma", "source", "position_bin", "position_range",
        "top_mean", "bottom_mean", "top_minus_bottom_gap", "top_segment_n",
        "bottom_segment_n",
    ]
    c1_fields = [
        "source_eval", "target_id", "method", "checkpoint_label", "n_prompts",
        "common_robust_lcb_mean", "common_robust_lcb_std",
        "delta_common_robust_lcb_mean", "fixedwin_process_mean",
        "section_process_mean", "semantic_fit_mean", "lyric_intelligibility_mean",
        "section_coherence_mean",
    ]
    training_fields = [
        "source", "n_steps", "fixedwin_section_pearson",
        "fixedwin_section_spearman", "mean_fixedwin_reward",
        "mean_section_reward", "mean_fixedwin_minus_section",
        "std_fixedwin_minus_section", "abs_diff_mean", "diff_crossing_frequency",
        "fixedwin_slope_per_step", "section_slope_per_step",
    ]
    variance_path = OUT_DIR / "globalness_by_unit_axis_source.csv"
    curve_path = OUT_DIR / "top_bottom_reward_time_curves.csv"
    c1_path = OUT_DIR / "c1_common_eval_summary.csv"
    training_path = OUT_DIR / "c1_fixedwin_section_training_alignment.csv"
    _write_csv(variance_path, variance_rows, variance_fields)
    _write_csv(curve_path, curve_rows, curve_fields)
    _write_csv(c1_path, c1_rows, c1_fields)
    _write_csv(training_path, training_rows, training_fields)

    payload = {
        "schema_version": "global_quality_structure_analysis_v1",
        "generated_at_utc": _now(),
        "status": "COMPLETE_CPU_ONLY",
        "gpu_hours_consumed": 0.0,
        "source_artifacts": [
            str(H3_RESULTS.relative_to(REPO_ROOT)),
            str(TIME_UNIFORM_JSON.relative_to(REPO_ROOT)),
            str(C1_COMMON_ROOT.relative_to(REPO_ROOT)),
            str(C1_TRIAGE_ROOT.relative_to(REPO_ROOT)),
            str(C1_STEPWISE.relative_to(REPO_ROOT)),
        ],
        "hard_boundary_flags": {
            "phase_d_launched": False,
            "human_eval_launched": False,
            "pruning_rl_launched": False,
            "rl_training_launched": False,
            "reward_definitions_changed": False,
            "sigma_policy_changed": False,
            "gate_v1_modified": False,
            "canonical_proposal_rewritten": False,
            "demucs_source_separation_launched": False,
        },
        "method_notes": {
            "between_share": "between-song SS / (between-song SS + within-song SS) across local window values",
            "between_within_ratio": "between-song SS / within-song SS",
            "sign_consistency": "fraction of normalized time bins where top-quartile mean exceeds bottom-quartile mean",
            "crossing_frequency": "adjacent sign-change rate of top-minus-bottom time-bin gaps",
            "globalness_index": "mean(between_share, sign_consistency, 1-crossing_frequency) for usable cells",
            "globalness_index_caveat": (
                "For the primary cells in this dataset, sign_consistency is 1.0 "
                "and crossing_frequency is 0.0, so the index is a monotone "
                "transform of between_share rather than independent evidence."
            ),
            "top_bottom_curve_caveat": (
                "Top/bottom prompt groups are selected in-sample by prompt mean; "
                "gap magnitudes are descriptive, not predictive."
            ),
            "unit_control_caveat": (
                "CU-MS and CU-NULL-rand-section share identical musicality and "
                "coherence value sets in the cached H3 artifact; CU-NULL is an "
                "informative control mainly for prompt_fit."
            ),
        },
        "aggregate_summary": h3_aggregate,
        "interpretation": {
            "classification": "supports_global_persistent_quality",
            "cautious_claim": (
                "For ACE-Step short-form outputs, local-window rewards appear to track "
                "persistent global quality more than isolated local failures."
            ),
            "fixedwin_read": "stable_local_proxy_for_global_quality_more_than_true_local_credit",
            "overclaim_guard": "Does not prove local failures never occur or that Section/window PRMs cannot help under other settings.",
        },
        "demucs_stem_cache_check": demucs,
        "existing_time_uniform_summary": existing_time_uniform.get("aggregate_uniformity_summary", {}),
        "tables": {
            "globalness_by_unit_axis_source": variance_rows,
            "top_bottom_reward_time_curves": curve_rows,
            "c1_common_eval_summary": c1_rows,
            "c1_fixedwin_section_training_alignment": training_rows,
        },
        "output_tables": {
            "globalness_by_unit_axis_source": str(variance_path.relative_to(REPO_ROOT)),
            "top_bottom_reward_time_curves": str(curve_path.relative_to(REPO_ROOT)),
            "c1_common_eval_summary": str(c1_path.relative_to(REPO_ROOT)),
            "c1_fixedwin_section_training_alignment": str(training_path.relative_to(REPO_ROOT)),
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload)
    print(json.dumps({
        "status": payload["status"],
        "json": str(OUT_JSON.relative_to(REPO_ROOT)),
        "markdown": str(OUT_MD.relative_to(REPO_ROOT)),
        "tables": payload["output_tables"],
        "primary_median_between_share": h3_aggregate["primary_median_between_share"],
        "primary_median_globalness_index": h3_aggregate["primary_median_globalness_index"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
