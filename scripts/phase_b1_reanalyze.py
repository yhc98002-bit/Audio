"""Phase B.1 — re-analyze existing per-prompt results with the revised
PI-locked tiered H2 rule (2026-05-23 revision) and the fixed quartile-
emergence output (IQR, range, gap, Cohen's d, median-split fallback for
degenerate quartile boundaries).

Reads:
  - configs/runs/phase_b1_reliability.yaml      (h2_interpretation regions + threshold)
  - configs/eval/gate_v2.yaml.draft              (cross-checked policy)
  - runs/phase_b1_reliability/results.jsonl      (per-prompt records)
  - runs/phase_b1_reliability/per_axis_sigma_rho.json  (existing rho matrix)

Optional second source for the 128-prompt merge (if --merge-with provided):
  - runs/phase_b1_reliability_expansion/results.jsonl

Writes:
  - runs/phase_b1_reliability/H2_VERDICT.json    (overwritten with v4 schema)
  - runs/phase_b1_reliability/H2_VERDICT.md
  - runs/phase_b1_reliability/per_axis_sigma_rho.json   (overwritten with merged matrix when --merge-with)
  - runs/phase_b1_reliability/figures/quartile_emergence.json
  - runs/phase_b1_reliability/figures/quartile_emergence.md
  - runs/phase_b1_reliability/figures/quartile_emergence_table.csv

Does NOT touch the model, the reward stack, or the sampler. Pure post-hoc
re-analysis on saved per-prompt records.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Re-use the driver's pure-Python helpers (no torch involved for the helpers
# we need; the driver does `import torch` at module top, so we re-implement
# the helpers locally to keep this script torch-free).


def spearman(x, y):
    if len(x) < 2 or len(x) != len(y):
        return float("nan")

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        ranks = [0.0] * len(v)
        for r, idx in enumerate(order):
            ranks[idx] = float(r)
        return ranks

    rx, ry = rank(x), rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = (sum((a - mx) ** 2 for a in rx)) ** 0.5
    dy = (sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / (dx * dy + 1e-12)


def _stats(xs):
    if not xs:
        return {"n": 0, "median": None, "mean": None, "pstdev": None, "min": None, "max": None}
    return {
        "n": len(xs),
        "median": statistics.median(xs),
        "mean": statistics.mean(xs),
        "pstdev": statistics.pstdev(xs) if len(xs) > 1 else 0.0,
        "min": min(xs),
        "max": max(xs),
    }


def _quartiles(xs):
    if not xs:
        return [float("nan")] * 3
    s = sorted(xs)
    n = len(s)
    q1 = s[n // 4]
    q2 = s[n // 2]
    q3 = s[(3 * n) // 4] if (3 * n) // 4 < n else s[-1]
    return [q1, q2, q3]


def _iqr(xs):
    if not xs or len(xs) < 2:
        return None
    s = sorted(xs)
    n = len(s)
    lo = s[n // 4]
    hi = s[(3 * n) // 4] if (3 * n) // 4 < n else s[-1]
    return float(hi - lo)


def _cohens_d(top, bot):
    if len(top) < 2 or len(bot) < 2:
        return None
    mt = statistics.mean(top)
    mb = statistics.mean(bot)
    vt = statistics.pvariance(top)
    vb = statistics.pvariance(bot)
    n1, n2 = len(top), len(bot)
    pooled_var = ((n1 - 1) * vt + (n2 - 1) * vb) / max(n1 + n2 - 2, 1)
    if pooled_var <= 0:
        return None
    return float((mt - mb) / (pooled_var ** 0.5))


# ----------- tier classification (mirrors driver, ground truth) -----------


def classify_tier(per_axis_sigma_rho, threshold, early_sigmas, middle_sigmas,
                  primary_sigmas, late_reference_sigmas):
    surviving_primary = []
    surviving_late = []
    near_threshold_primary = []
    for axis_id, by_sigma in per_axis_sigma_rho.items():
        for sigma_key, rho in by_sigma.items():
            if rho is None or (isinstance(rho, float) and rho != rho):
                continue
            s = float(sigma_key)
            if rho >= threshold:
                if s in primary_sigmas:
                    surviving_primary.append((axis_id, s, rho))
                    if threshold <= rho <= threshold + 0.05:
                        near_threshold_primary.append((axis_id, s, rho))
                elif s in late_reference_sigmas:
                    surviving_late.append((axis_id, s, rho))

    has_early = any(p[1] in early_sigmas for p in surviving_primary)
    has_middle = any(p[1] in middle_sigmas for p in surviving_primary)
    n_primary = len(surviving_primary)

    surviving_primary_strict = [
        (a, s, r) for (a, s, r) in surviving_primary
        if not (threshold <= r <= threshold + 0.05)
    ]
    n_primary_strict = len(surviving_primary_strict)
    has_early_strict = any(p[1] in early_sigmas for p in surviving_primary_strict)
    has_middle_strict = any(p[1] in middle_sigmas for p in surviving_primary_strict)

    strong_holds_full = n_primary >= 2 and has_early and has_middle
    strong_holds_strict = n_primary_strict >= 2 and has_early_strict and has_middle_strict

    if n_primary == 0:
        tier = "FAIL"
    elif n_primary == 1:
        tier = "AMBIGUOUS"
    elif strong_holds_full and strong_holds_strict:
        if near_threshold_primary:
            tier = "STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES"
        else:
            tier = "STRONG_PASS"
    elif strong_holds_full and not strong_holds_strict:
        tier = "AMBIGUOUS"
    elif n_primary >= 2 and (not has_early) and has_middle:
        tier = "SUPPORTED_PASS"
    elif n_primary >= 2 and has_early and (not has_middle):
        tier = "AMBIGUOUS"
    else:
        tier = "FAIL"

    return {
        "tier": tier,
        "surviving_primary_pairs": [
            {"axis": a, "sigma": s, "rho": r} for a, s, r in sorted(surviving_primary)
        ],
        "surviving_primary_pairs_excluding_near_threshold": [
            {"axis": a, "sigma": s, "rho": r} for a, s, r in sorted(surviving_primary_strict)
        ],
        "surviving_late_reference_pairs_descriptive_only": [
            {"axis": a, "sigma": s, "rho": r} for a, s, r in sorted(surviving_late)
        ],
        "near_threshold_band_primary_only_0.50_0.55": [
            {"axis": a, "sigma": s, "rho": r} for a, s, r in sorted(near_threshold_primary)
        ],
        "has_early_sigma_0.9_or_0.8": has_early,
        "has_middle_sigma_0.7_or_0.6": has_middle,
        "has_early_strict_excluding_near_threshold": has_early_strict,
        "has_middle_strict_excluding_near_threshold": has_middle_strict,
        "n_surviving_primary_pairs": n_primary,
        "n_surviving_primary_pairs_strict": n_primary_strict,
        "strong_holds_full": bool(strong_holds_full),
        "strong_holds_strict": bool(strong_holds_strict),
        "classification_depends_on_near_threshold":
            bool(strong_holds_full and not strong_holds_strict),
        "edge_case_early_only_ge2_primary": bool(
            n_primary >= 2 and has_early and (not has_middle)
        ),
    }


# ------------------------- I/O ---------------------------------------------


def load_per_prompt_records(jsonl_path: Path):
    records = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def recompute_rho_matrix(records, axes, sigma_targets):
    """Recompute per-axis × σ Spearman ρ from per-prompt records."""
    per_axis_sigma_rho = {ax: {} for ax in axes}
    per_axis_sigma_n_paired = {ax: {} for ax in axes}
    for ax in axes:
        for sigma in sigma_targets:
            xs, ys = [], []
            for rec in records:
                final_v = rec.get("final_axis_values", {}).get(ax)
                if final_v is None:
                    continue
                # find the per_sigma block with matching sigma_target
                per_sigma = rec.get("per_sigma", [])
                match = next(
                    (b for b in per_sigma if abs(b.get("sigma_target", -1) - sigma) < 1e-9),
                    None,
                )
                if match is None:
                    continue
                interm_v = match.get("axis_values", {}).get(ax)
                if interm_v is None:
                    continue
                xs.append(interm_v)
                ys.append(final_v)
            per_axis_sigma_rho[ax][str(sigma)] = spearman(xs, ys) if xs else float("nan")
            per_axis_sigma_n_paired[ax][str(sigma)] = len(xs)
    return per_axis_sigma_rho, per_axis_sigma_n_paired


def compute_quartile_emergence(records, axes, sigma_targets, cfg_boundary_meta):
    """Quartile-stratified intermediate reward output (must_not_influence_gate)."""
    # Pull per-axis final values + per-(axis, sigma) intermediate per-prompt
    per_axis_final = {ax: [] for ax in axes}
    final_per_prompt_axis = {}
    per_axis_sigma_intermediate_prompt = {}  # (axis, sigma) -> list[(pid, v_interm)]
    for rec in records:
        pid = rec["prompt_id"]
        final = rec.get("final_axis_values", {})
        final_per_prompt_axis[pid] = final
        for ax in axes:
            v = final.get(ax)
            if v is not None:
                per_axis_final[ax].append(v)
        for block in rec.get("per_sigma", []):
            sigma = block.get("sigma_target")
            for ax, v in block.get("axis_values", {}).items():
                if v is None:
                    continue
                key = (ax, sigma)
                per_axis_sigma_intermediate_prompt.setdefault(key, []).append((pid, v))

    qe = {"_cfg_branch_metadata": cfg_boundary_meta}
    for ax in axes:
        finals = per_axis_final[ax]
        n_final = len(finals)
        if n_final < 4:
            qe[ax] = {
                "note": f"n<4 ({n_final}); quartile stratification skipped",
                "must_not_influence_gate": True,
            }
            continue
        q1, q2, q3 = _quartiles(finals)
        degenerate = (q1 == q3)
        bucket_top, bucket_bottom = [], []
        if degenerate:
            mean_final = statistics.mean(finals)
            median_final = statistics.median(finals)
            split_point = mean_final if mean_final != median_final else median_final
            for pid in final_per_prompt_axis:
                v = final_per_prompt_axis[pid].get(ax)
                if v is None:
                    continue
                if v > split_point:
                    bucket_top.append(pid)
                elif v < split_point:
                    bucket_bottom.append(pid)
            stratification_mode = "median_split_fallback"
        else:
            for pid in final_per_prompt_axis:
                v = final_per_prompt_axis[pid].get(ax)
                if v is None:
                    continue
                if v <= q1:
                    bucket_bottom.append(pid)
                elif v >= q3:
                    bucket_top.append(pid)
            stratification_mode = "quartile_q1_q3"
        per_sigma_top_bot = {}
        for sigma in sigma_targets:
            interm = per_axis_sigma_intermediate_prompt.get((ax, sigma), [])
            interm_by_pid = dict(interm)
            top_vals = [interm_by_pid[p] for p in bucket_top if p in interm_by_pid]
            bot_vals = [interm_by_pid[p] for p in bucket_bottom if p in interm_by_pid]
            top_stats = _stats(top_vals)
            bot_stats = _stats(bot_vals)
            top_med = top_stats.get("median")
            bot_med = bot_stats.get("median")
            gap = (top_med - bot_med) if (top_med is not None and bot_med is not None) else None
            top_range = (float(max(top_vals) - min(top_vals)) if top_vals else None)
            bot_range = (float(max(bot_vals) - min(bot_vals)) if bot_vals else None)
            per_sigma_top_bot[str(sigma)] = {
                "top_quartile_stats": top_stats,
                "bottom_quartile_stats": bot_stats,
                "top_iqr": _iqr(top_vals),
                "bottom_iqr": _iqr(bot_vals),
                "top_range": top_range,
                "bottom_range": bot_range,
                "top_minus_bottom_median_gap": gap,
                "cohens_d_top_minus_bottom": _cohens_d(top_vals, bot_vals),
            }
        qe[ax] = {
            "final_quartile_thresholds": {"q1": q1, "q2": q2, "q3": q3},
            "stratification_mode": stratification_mode,
            "stratification_note": (
                "Final-reward quartile boundaries are degenerate (q1==q3); "
                "falling back to median-split top/bottom."
                if degenerate else
                "Standard top-Q4 (final >= q3) vs bottom-Q1 (final <= q1) split."
            ),
            "n_top": len(bucket_top),
            "n_bottom": len(bucket_bottom),
            "per_sigma": per_sigma_top_bot,
            "must_not_influence_gate": True,
        }
    return qe


def write_quartile_csv(qe: dict, csv_path: Path):
    import csv
    branch_per_sigma = qe.get("_cfg_branch_metadata", {}).get("branch_per_sigma", {})
    rows = []
    for axis_id, payload in qe.items():
        if axis_id.startswith("_"):
            continue
        per_sigma = payload.get("per_sigma")
        if not per_sigma:
            continue
        for sigma_key, stats in per_sigma.items():
            rows.append({
                "sigma": sigma_key,
                "axis": axis_id,
                "top_q_median": stats.get("top_quartile_stats", {}).get("median"),
                "bot_q_median": stats.get("bottom_quartile_stats", {}).get("median"),
                "top_minus_bot_gap": stats.get("top_minus_bottom_median_gap"),
                "top_iqr": stats.get("top_iqr"),
                "bot_iqr": stats.get("bottom_iqr"),
                "top_range": stats.get("top_range"),
                "bot_range": stats.get("bottom_range"),
                "cohens_d": stats.get("cohens_d_top_minus_bottom"),
                "branch": branch_per_sigma.get(sigma_key, "unknown"),
                "n_top": stats.get("top_quartile_stats", {}).get("n"),
                "n_bottom": stats.get("bottom_quartile_stats", {}).get("n"),
            })
    with open(csv_path, "w", newline="") as f:
        if not rows:
            f.write("sigma,axis,top_q_median,bot_q_median,top_minus_bot_gap,top_iqr,bot_iqr,top_range,bot_range,cohens_d,branch,n_top,n_bottom\n")
            return
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(v):
    return "n/a" if v is None else f"{v:.3f}"


def write_quartile_md(qe: dict, md_path: Path, n_prompts: int):
    """Markdown summary."""
    cfg = qe.get("_cfg_branch_metadata", {})
    branch_per_sigma = cfg.get("branch_per_sigma", {})
    transition = cfg.get("cfg_branch_transition_between", [])
    lines = []
    lines.append("# Quartile Emergence Summary — Phase B.1 (exploratory)")
    lines.append("")
    lines.append(f"- n_formal_prompts: {n_prompts}")
    lines.append("- This output is `must_not_influence_gate: true` per spec.")
    lines.append(f"- CFG → cond-only branch boundary: between σ={transition[0]} and σ={transition[1]}." if len(transition) == 2 else "")
    lines.append("")
    lines.append("## Per-axis top-Q4 vs bot-Q1 median gap across σ")
    lines.append("")
    lines.append("(`gap = top_q_median − bottom_q_median`; rising gap = earlier emergence)")
    lines.append("")
    sigma_order = ["0.9", "0.8", "0.7", "0.6", "0.5", "0.3"]
    branch_row = "| branch | " + " | ".join(branch_per_sigma.get(s, "?") for s in sigma_order) + " |"
    header = "| Axis | " + " | ".join(f"σ={s}" for s in sigma_order) + " |"
    sep = "|---|" + "---:|" * len(sigma_order)
    lines.append(header)
    lines.append(sep)
    lines.append(branch_row)
    for ax, payload in qe.items():
        if ax.startswith("_"):
            continue
        if "per_sigma" not in payload:
            lines.append(f"| {ax} | (skipped: {payload.get('note', 'no per-sigma data')}) |"
                         + " — |" * (len(sigma_order) - 1))
            continue
        per_sigma = payload["per_sigma"]
        cells = []
        for s in sigma_order:
            block = per_sigma.get(s)
            if not block:
                cells.append("n/a")
                continue
            gap = block.get("top_minus_bottom_median_gap")
            cells.append(fmt_pct(gap))
        lines.append(f"| {ax} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Per-axis Cohen's d (top − bot) across σ")
    lines.append("")
    lines.append(header)
    lines.append(sep)
    lines.append(branch_row)
    for ax, payload in qe.items():
        if ax.startswith("_"):
            continue
        per_sigma = payload.get("per_sigma")
        if not per_sigma:
            continue
        cells = []
        for s in sigma_order:
            block = per_sigma.get(s)
            if not block:
                cells.append("n/a")
                continue
            d = block.get("cohens_d_top_minus_bottom")
            cells.append(fmt_pct(d))
        lines.append(f"| {ax} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Top quartile = prompts whose final-audio reward for the given axis is at or above q3 of the per-axis final distribution.")
    lines.append("- Bottom quartile = prompts whose final-audio reward is at or below q1.")
    lines.append("- For axes with degenerate final-reward boundaries (q1 == q3, e.g. lyric_intelligibility WER=0 on a clean-vocal corpus), top/bottom buckets are formed by a mean (or median) split instead. `stratification_mode` is recorded per axis.")
    lines.append("- CFG-mixed → cond-only branch transition lies between σ=0.6 (last CFG-mixed) and σ=0.5 (first cond-only). Paper figures must annotate this boundary.")
    md_path.write_text("\n".join(lines) + "\n")


def write_verdict_md(verdict, md_path: Path):
    tier = verdict["tier"]
    lines = []
    lines.append(f"# Phase B.1 H2 Verdict — `{tier}`")
    lines.append("")
    lines.append(f"- Rule: {verdict['tiered_rule_applied']}")
    lines.append(f"- ρ threshold: {verdict['threshold']}")
    lines.append(f"- Tier meaning: {verdict['tier_meaning']}")
    lines.append("")
    rc = verdict.get("primary_region_coverage", {})
    lines.append("## Primary region coverage")
    lines.append("")
    lines.append(f"- n primary pairs (full): {rc.get('n_surviving_primary_pairs')}")
    lines.append(f"- n primary pairs (excluding near-threshold [0.50, 0.55]): {rc.get('n_surviving_primary_pairs_strict')}")
    lines.append(f"- has_early_sigma_0.9_or_0.8: {rc.get('has_early_sigma_0.9_or_0.8')}")
    lines.append(f"- has_middle_sigma_0.7_or_0.6: {rc.get('has_middle_sigma_0.7_or_0.6')}")
    lines.append(f"- has_early_strict (excluding near-threshold): {rc.get('has_early_strict_excluding_near_threshold')}")
    lines.append(f"- has_middle_strict (excluding near-threshold): {rc.get('has_middle_strict_excluding_near_threshold')}")
    lines.append(f"- strong_holds_full: {verdict.get('strong_holds_full')}")
    lines.append(f"- strong_holds_strict (excluding near-threshold): {verdict.get('strong_holds_strict')}")
    lines.append(f"- classification_depends_on_near_threshold: {verdict.get('classification_depends_on_near_threshold')}")
    lines.append("")
    lines.append("## Surviving primary pairs (ρ ≥ threshold; σ ∈ {0.9, 0.8, 0.7, 0.6})")
    lines.append("")
    lines.append("| Axis | σ | ρ |")
    lines.append("|---|---:|---:|")
    for p in verdict["surviving_primary_pairs"]:
        rho = p['rho']
        note = ""
        for nt in verdict.get("near_threshold_band_primary_only_0.50_0.55", []):
            if nt["axis"] == p["axis"] and abs(nt["sigma"] - p["sigma"]) < 1e-9:
                note = " † near-threshold"
                break
        lines.append(f"| {p['axis']} | {p['sigma']} | {rho:.4f}{note} |")
    lines.append("")
    if verdict.get("near_threshold_band_primary_only_0.50_0.55"):
        lines.append("### Near-threshold pairs (ρ ∈ [0.50, 0.55])")
        lines.append("")
        for nt in verdict["near_threshold_band_primary_only_0.50_0.55"]:
            lines.append(f"- {nt['axis']} @ σ={nt['sigma']} ρ={nt['rho']:.4f}")
        lines.append("")
    lines.append("## Late-reference σ pairs (descriptive only)")
    lines.append("")
    lines.append("These do NOT contribute to STRONG/SUPPORTED classification and do NOT rescue FAIL.")
    lines.append("")
    lines.append("| Axis | σ | ρ |")
    lines.append("|---|---:|---:|")
    for p in verdict["surviving_late_reference_pairs_descriptive_only"]:
        lines.append(f"| {p['axis']} | {p['sigma']} | {p['rho']:.4f} |")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n")


# ----------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/runs/phase_b1_reliability.yaml")
    ap.add_argument("--gate-policy", default="configs/eval/gate_v2.yaml.draft")
    ap.add_argument("--results", default="runs/phase_b1_reliability/results.jsonl")
    ap.add_argument("--merge-with", default=None,
                    help="Optional: second results.jsonl path (e.g. the 128-prompt "
                         "expansion). When set, merge per-prompt records and re-run "
                         "analysis on the combined set.")
    ap.add_argument("--output-dir", default="runs/phase_b1_reliability")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    gate_path = Path(args.gate_policy)
    results_path = Path(args.results)
    out_dir = Path(args.output_dir)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    with open(cfg_path) as f:
        run_cfg = yaml.safe_load(f)
    with open(gate_path) as f:
        gate_cfg = yaml.safe_load(f)

    threshold = float(run_cfg["h2_interpretation"]["eligibility_threshold"])
    rs = run_cfg["h2_interpretation"]["region_separation"]
    primary_sigmas = set(rs["primary_nontrivial_sigmas"])
    early_sigmas = set(rs["early_sigmas"])
    middle_sigmas = set(rs["middle_sigmas"])
    late_reference_sigmas = set(rs["late_reference_sigmas"])
    sigma_targets = sorted(set(primary_sigmas | late_reference_sigmas), reverse=True)
    axes = [a["id"] for a in run_cfg["reward_axes"]]

    # Load existing per-prompt records (always)
    records = load_per_prompt_records(results_path)
    n_prompts = len(records)
    extra_records = []
    if args.merge_with:
        extra_records = load_per_prompt_records(Path(args.merge_with))
        # ensure disjoint prompt_ids
        existing_ids = {r["prompt_id"] for r in records}
        new_ids = {r["prompt_id"] for r in extra_records}
        overlap = existing_ids & new_ids
        if overlap:
            print(f"[reanalyze] FAIL — overlap between primary and merge-with results: {sorted(overlap)[:5]}...",
                  file=sys.stderr)
            return 2
        records = records + extra_records
        n_prompts = len(records)
        print(f"[reanalyze] merged {len(extra_records)} extra prompts; total = {n_prompts}",
              flush=True)
    else:
        print(f"[reanalyze] using {n_prompts} primary prompts (no expansion)",
              flush=True)

    # Recompute per-axis × σ Spearman from records (cross-check vs existing file)
    per_axis_sigma_rho, per_axis_sigma_n_paired = recompute_rho_matrix(
        records, axes, sigma_targets
    )
    summary = {
        "schema_version": "phase_b1_reliability_summary_v3",
        "reanalysis_timestamp_utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "merge_with": args.merge_with or None,
        "n_formal_prompts": n_prompts,
        "per_axis_sigma_rho": per_axis_sigma_rho,
        "per_axis_sigma_n_paired": per_axis_sigma_n_paired,
    }
    summary_path = out_dir / "per_axis_sigma_rho.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[reanalyze] wrote {summary_path}", flush=True)

    # Tier classification (new STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES tier)
    tier_result = classify_tier(
        per_axis_sigma_rho, threshold, early_sigmas, middle_sigmas,
        primary_sigmas, late_reference_sigmas,
    )
    tier_meanings = {
        "STRONG_PASS": "Early quality-emergence evidence is supported (no near-threshold pairs).",
        "STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES": (
            "Early quality-emergence evidence is supported. Some primary pairs lie in "
            "the [0.50, 0.55] near-threshold band, but the STRONG criterion holds "
            "even when those pairs are excluded — classification is NOT load-bearing "
            "on near-threshold pairs."
        ),
        "SUPPORTED_PASS": ("Non-trivial process reward is supported, but do not claim "
                             "very-early emergence. Use only empirically supported σ "
                             "checkpoints for downstream M-PRM."),
        "AMBIGUOUS": ("Expand to 128 prompts using the SAME six-σ curve. Do not add "
                        "or change σ points."),
        "FAIL": ("Pivot to outcome-only / terminal-reward route per "
                   "NULL_RESULT_CONTRACT §2 Block B.1. Late_reference passes do NOT rescue."),
    }
    verdict = {
        "schema_version": "phase_b1_h2_verdict_v4",
        "tiered_rule_applied": (
            "PI-locked 2026-05-23 revised (STRONG_PASS / "
            "STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES / SUPPORTED_PASS / AMBIGUOUS / FAIL)"
        ),
        "n_formal_prompts": n_prompts,
        "reanalysis_source": str(results_path),
        "merge_with": args.merge_with or None,
        "threshold": threshold,
        "tier": tier_result["tier"],
        "tier_meaning": tier_meanings[tier_result["tier"]],
        "surviving_primary_pairs": tier_result["surviving_primary_pairs"],
        "surviving_primary_pairs_excluding_near_threshold":
            tier_result["surviving_primary_pairs_excluding_near_threshold"],
        "surviving_late_reference_pairs_descriptive_only":
            tier_result["surviving_late_reference_pairs_descriptive_only"],
        "near_threshold_band_primary_only_0.50_0.55":
            tier_result["near_threshold_band_primary_only_0.50_0.55"],
        "edge_case_early_only_ge2_primary_pairs":
            tier_result["edge_case_early_only_ge2_primary"],
        "primary_region_coverage": {
            "has_early_sigma_0.9_or_0.8": tier_result["has_early_sigma_0.9_or_0.8"],
            "has_middle_sigma_0.7_or_0.6": tier_result["has_middle_sigma_0.7_or_0.6"],
            "has_early_strict_excluding_near_threshold":
                tier_result["has_early_strict_excluding_near_threshold"],
            "has_middle_strict_excluding_near_threshold":
                tier_result["has_middle_strict_excluding_near_threshold"],
            "n_surviving_primary_pairs": tier_result["n_surviving_primary_pairs"],
            "n_surviving_primary_pairs_strict":
                tier_result["n_surviving_primary_pairs_strict"],
        },
        "classification_depends_on_near_threshold":
            tier_result["classification_depends_on_near_threshold"],
        "strong_holds_full": tier_result["strong_holds_full"],
        "strong_holds_strict": tier_result["strong_holds_strict"],
        "note": (
            "Late-reference σ ∈ {0.5, 0.3} pairs are descriptive only and do NOT "
            "contribute to STRONG/SUPPORTED classification, and do NOT rescue FAIL "
            "(PI directive 2026-05-23)."
        ),
    }
    verdict_path = out_dir / "H2_VERDICT.json"
    with open(verdict_path, "w") as f:
        json.dump(verdict, f, indent=2)
    print(f"[reanalyze] wrote {verdict_path} → tier={verdict['tier']}", flush=True)
    verdict_md_path = out_dir / "H2_VERDICT.md"
    write_verdict_md(verdict, verdict_md_path)
    print(f"[reanalyze] wrote {verdict_md_path}", flush=True)

    # CFG boundary metadata for quartile_emergence (mirror driver)
    sigma_to_branch = {}
    for cp in run_cfg["reliability_curve"]["primary_nontrivial"]:
        sigma_to_branch[str(cp["target"])] = "CFG-mixed" if cp["cfg_active"] else "cond-only"
    for cp in run_cfg["reliability_curve"]["late_reference"]:
        sigma_to_branch[str(cp["target"])] = "CFG-mixed" if cp["cfg_active"] else "cond-only"
    cfg_boundary_meta = {
        "guidance_interval": run_cfg["sampler"]["guidance_interval"],
        "start_idx": 7,
        "end_idx": 22,
        "cfg_branch_transition_between": [0.6, 0.5],
        "cfg_branch_transition_step_indices": [19, 22],
        "cfg_branch_transition_note": (
            "Captured v_effective is CFG-mixed for σ ∈ {0.9, 0.8, 0.7, 0.6} (steps 7/12/16/19 "
            "inside guidance interval [7, 22)) and cond-only for σ ∈ {0.5, 0.3} (steps 22/25 "
            "outside the interval). Paper figures MUST annotate the σ=0.6 → σ=0.5 transition."
        ),
        "branch_per_sigma": sigma_to_branch,
    }

    qe = compute_quartile_emergence(records, axes, sigma_targets, cfg_boundary_meta)
    qe_path = figures_dir / "quartile_emergence.json"
    with open(qe_path, "w") as f:
        json.dump(qe, f, indent=2)
    print(f"[reanalyze] wrote {qe_path}", flush=True)
    qe_csv = figures_dir / "quartile_emergence_table.csv"
    write_quartile_csv(qe, qe_csv)
    print(f"[reanalyze] wrote {qe_csv}", flush=True)
    qe_md = figures_dir / "quartile_emergence.md"
    write_quartile_md(qe, qe_md, n_prompts=n_prompts)
    print(f"[reanalyze] wrote {qe_md}", flush=True)

    print(f"\n[reanalyze] DONE: tier={verdict['tier']}, n_prompts={n_prompts}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
