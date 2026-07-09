"""Sectionability analysis on H3a-dev results — REVISED.

The first version naively counted "n_sections per clip", but CU-MS uses a
hardcoded ``n_sections_prior=4`` and ``librosa.segment.agglomerative(k=4)``
ALWAYS produces 4 segments. The section count is therefore an algorithmic
artifact, not a measured property of the audio.

This revised version uses the per-section **MERT section_coherence
heterogeneity** (range / IQR of final-audio per-section MERT scores) as
the sectionability proxy:

- Low heterogeneity (range ≪ 1) → the 4 "sections" have nearly identical
  MERT-section coherence → no real section structure; clip is a single
  texture sliced into arbitrary quarters.
- High heterogeneity (range close to 1) → the 4 sections genuinely differ
  in musical-coherence profile → real section structure.

Also reports the per-prompt CU-MS Spearman distribution (within-prompt ρ
of intermediate vs final per-section MERT scores) and correlates that
with the heterogeneity proxy.

Inputs:
  runs/phase_b3_credit_unit/h3a/results.jsonl
Outputs:
  runs/phase_b3_credit_unit/h3a/SECTIONABILITY_REPORT.{json,md}
  runs/phase_b3_credit_unit/h3a/sectionability_table.csv
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "scripts")
from phase_b3_credit_unit_comparison import spearman  # noqa: E402


def _range(xs):
    return (max(xs) - min(xs)) if xs and len(xs) >= 2 else 0.0


def _iqr(xs):
    if not xs or len(xs) < 2:
        return 0.0
    s = sorted(xs)
    n = len(s)
    lo = s[n // 4]
    hi = s[(3 * n) // 4] if (3 * n) // 4 < n else s[-1]
    return float(hi - lo)


def main():
    results_path = Path("runs/phase_b3_credit_unit/h3a/results.jsonl")
    out_dir = Path("runs/phase_b3_credit_unit/h3a")
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    with open(results_path) as f:
        for line in f:
            records.append(json.loads(line))
    print(f"[sectionability] loaded {len(records)} prompts", flush=True)

    per_prompt = []
    for rec in records:
        pid = rec["prompt_id"]
        is_instr = rec["is_instrumental"]
        seg_counts = rec.get("per_unit_segments_count", {})
        n_ms = seg_counts.get("CU-MS")
        n_fw = seg_counts.get("CU-FW")
        n_bw = seg_counts.get("CU-BW")
        duration = rec.get("duration_actual_s")
        median_section_len = duration / n_ms if (n_ms and duration) else None

        # The "real" sectionability signal: per-section MERT section_coherence
        # range / IQR on the final audio. Read the CU-MS coherence proxy
        # vector at σ=0.6 (most-supported H2 axis for coherence).
        cu_ms_block = rec.get("per_unit", {}).get("CU-MS", {})
        coh_06 = cu_ms_block.get("coherence", {}).get("0.6", {})
        coh_proxy = coh_06.get("human_pref_proxy_vector") or []
        coh_delta = coh_06.get("section_reward_delta_vector") or []
        coherence_range = _range(coh_proxy)
        coherence_iqr = _iqr(coh_proxy)

        # Per-prompt CU-MS Spearman ρ on each (axis, σ) — within-prompt only.
        per_prompt_rho_ms: dict[str, dict[str, float]] = {}
        for axis in ("musicality", "coherence", "prompt_fit"):
            for sigma in ("0.6", "0.7"):
                block = cu_ms_block.get(axis, {}).get(sigma, {})
                if not block:
                    continue
                d = block.get("section_reward_delta_vector") or []
                p = block.get("human_pref_proxy_vector") or []
                if len(d) >= 2 and len(d) == len(p):
                    r = spearman(d, p)
                    if r == r:
                        per_prompt_rho_ms.setdefault(axis, {})[sigma] = r

        # Per-prompt mean ρ across (axis, σ): cheap aggregate.
        all_rhos = [r for ax in per_prompt_rho_ms.values() for r in ax.values()]
        mean_ms_rho = statistics.mean(all_rhos) if all_rhos else None

        # Final-audio quality proxy: mean of per-section musicality proxy at σ=0.6.
        mus_06 = cu_ms_block.get("musicality", {}).get("0.6", {})
        section_proxy_mus = mus_06.get("human_pref_proxy_vector") or []
        final_quality_proxy = statistics.mean(section_proxy_mus) if section_proxy_mus else None

        per_prompt.append({
            "prompt_id": pid,
            "is_instrumental": is_instr,
            "duration_s": duration,
            "n_sections_cu_ms": n_ms,
            "n_fw_windows": n_fw,
            "n_bw_bars": n_bw,
            "median_section_len_s": median_section_len,
            "coherence_proxy_range": coherence_range,
            "coherence_proxy_iqr": coherence_iqr,
            "cu_ms_mean_within_prompt_rho": mean_ms_rho,
            "final_quality_proxy": final_quality_proxy,
        })

    # Aggregate.
    n_total = len(per_prompt)
    n_vocal = sum(1 for p in per_prompt if not p["is_instrumental"])
    n_instr = sum(1 for p in per_prompt if p["is_instrumental"])

    # Sectionability buckets — based on coherence_proxy_range (a measured
    # property, not the hardcoded k=4 count).
    # Define: "weak sectionability" if range < 0.05 (sections within 5% of MERT range),
    # "strong sectionability" if range >= 0.20.
    weak = [p for p in per_prompt if (p["coherence_proxy_range"] or 0) < 0.05]
    medium = [p for p in per_prompt if 0.05 <= (p["coherence_proxy_range"] or 0) < 0.20]
    strong = [p for p in per_prompt if (p["coherence_proxy_range"] or 0) >= 0.20]

    # Stratified summaries.
    def _stratify(group):
        ranges = [p["coherence_proxy_range"] for p in group if p["coherence_proxy_range"] is not None]
        return {
            "n": len(group),
            "coherence_range_median": statistics.median(ranges) if ranges else None,
            "coherence_range_p10": (sorted(ranges)[max(0, len(ranges)//10)] if ranges else None),
            "coherence_range_p90": (sorted(ranges)[min(len(ranges)-1, 9*len(ranges)//10)] if ranges else None),
        }

    vocal_stats = _stratify([p for p in per_prompt if not p["is_instrumental"]])
    instr_stats = _stratify([p for p in per_prompt if p["is_instrumental"]])

    # High vs low quality stratification using musicality proxy.
    qualities = [p["final_quality_proxy"] for p in per_prompt if p["final_quality_proxy"] is not None]
    if qualities:
        q_split = statistics.median(qualities)
        high_q = [p for p in per_prompt if (p["final_quality_proxy"] or 0) >= q_split]
        low_q = [p for p in per_prompt
                 if p["final_quality_proxy"] is not None and p["final_quality_proxy"] < q_split]
        high_q_stats = _stratify(high_q)
        low_q_stats = _stratify(low_q)
    else:
        q_split = None
        high_q_stats = low_q_stats = None

    # Correlation: coherence_range vs CU-MS within-prompt mean ρ.
    pairs = [(p["coherence_proxy_range"], p["cu_ms_mean_within_prompt_rho"])
             for p in per_prompt
             if p["coherence_proxy_range"] is not None
             and p["cu_ms_mean_within_prompt_rho"] is not None]
    if len(pairs) >= 2:
        xs, ys = zip(*pairs)
        corr_sectionability_msperf = spearman(list(xs), list(ys))
    else:
        corr_sectionability_msperf = None

    report = {
        "schema_version": "h3a_sectionability_v2_coherence_range_proxy",
        "input_path": str(results_path),
        "n_prompts": n_total,
        "n_vocal": n_vocal,
        "n_instrumental": n_instr,
        "sectionability_proxy": (
            "coherence_proxy_range: per-prompt range (max-min) of the 4 "
            "CU-MS sections' final-audio MERT section_coherence values at "
            "σ=0.6. Low range → 4 'sections' have similar coherence "
            "profile → weak / absent section structure. High range → "
            "sections are heterogeneous → real section structure."
        ),
        "duration_stats_s": {
            "median": statistics.median(p["duration_s"] for p in per_prompt),
            "min": min(p["duration_s"] for p in per_prompt),
            "max": max(p["duration_s"] for p in per_prompt),
        },
        "n_sections_cu_ms_distribution": dict(Counter(p["n_sections_cu_ms"] for p in per_prompt)),
        "note_on_n_sections": (
            "CU-MS uses hardcoded n_sections_prior=4 → every clip is forced "
            "to 4 segments. Section count is therefore an algorithmic "
            "artifact, NOT a measured property of the audio. The real "
            "sectionability signal is `coherence_proxy_range` below."
        ),
        "coherence_proxy_range_overall": {
            "median": statistics.median(p["coherence_proxy_range"] for p in per_prompt
                                         if p["coherence_proxy_range"] is not None),
            "p10": sorted(p["coherence_proxy_range"] for p in per_prompt
                          if p["coherence_proxy_range"] is not None)[6],
            "p90": sorted(p["coherence_proxy_range"] for p in per_prompt
                          if p["coherence_proxy_range"] is not None)[-7],
            "min": min(p["coherence_proxy_range"] for p in per_prompt
                       if p["coherence_proxy_range"] is not None),
            "max": max(p["coherence_proxy_range"] for p in per_prompt
                       if p["coherence_proxy_range"] is not None),
        },
        "sectionability_buckets": {
            "weak (range < 0.05)": {"count": len(weak), "frac": len(weak) / n_total},
            "medium (0.05 ≤ range < 0.20)": {"count": len(medium), "frac": len(medium) / n_total},
            "strong (range ≥ 0.20)": {"count": len(strong), "frac": len(strong) / n_total},
        },
        "vocal_vs_instrumental_sectionability": {
            "vocal": vocal_stats, "instrumental": instr_stats,
        },
        "high_vs_low_quality_sectionability": {
            "median_quality_split_aesthetic_pq_06": q_split,
            "high_quality": high_q_stats, "low_quality": low_q_stats,
        },
        "correlation_sectionability_vs_cu_ms_within_prompt_rho": {
            "spearman_rho_coherence_range_vs_mean_ms_rho": corr_sectionability_msperf,
            "interpretation": (
                "If positive: prompts with stronger section heterogeneity "
                "(higher coherence_range) get higher CU-MS within-prompt ρ — "
                "i.e., section credit performs better when audio is actually "
                "section-structured. If near zero or negative: section structure "
                "is not the deciding factor for CU-MS performance."
            ),
        },
    }

    json_path = out_dir / "SECTIONABILITY_REPORT.json"
    json_path.write_text(json.dumps(report, indent=2))
    print(f"[sectionability] wrote {json_path}", flush=True)

    csv_path = out_dir / "sectionability_table.csv"
    fieldnames = [
        "prompt_id", "is_instrumental", "duration_s",
        "n_sections_cu_ms", "median_section_len_s",
        "coherence_proxy_range", "coherence_proxy_iqr",
        "cu_ms_mean_within_prompt_rho", "final_quality_proxy",
    ]
    with open(csv_path, "w", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        for p in per_prompt:
            w.writerow({k: p.get(k) for k in fieldnames})
    print(f"[sectionability] wrote {csv_path}", flush=True)

    md_path = out_dir / "SECTIONABILITY_REPORT.md"
    lines = []
    lines.append("# H3a-dev Sectionability Report (v2 — coherence-range proxy)")
    lines.append("")
    lines.append("## Methodology note")
    lines.append("")
    lines.append("The naive metric *number of CU-MS sections per clip* is uninformative")
    lines.append("because CU-MS uses a hardcoded `n_sections_prior=4` and")
    lines.append("`librosa.segment.agglomerative(k=4)` ALWAYS produces 4 segments,")
    lines.append("regardless of the audio's true structure. **Every clip has exactly 4")
    lines.append("CU-MS 'sections' by construction.**")
    lines.append("")
    lines.append("This report uses a MEASURED proxy instead: the **per-prompt range of")
    lines.append("the 4 sections' final-audio MERT section_coherence scores** at σ=0.6.")
    lines.append("Low range (e.g., < 0.05) means the 4 segments have nearly identical")
    lines.append("coherence profile — there is no real section structure to detect; the")
    lines.append("clip is a single texture sliced into arbitrary quarters. High range")
    lines.append("(e.g., ≥ 0.20) means the segments genuinely differ in musical-coherence")
    lines.append("profile.")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- n_prompts: {n_total} ({n_vocal} vocal, {n_instr} instrumental)")
    cd = report["duration_stats_s"]
    lines.append(f"- audio duration (s): median {cd['median']:.1f}, range [{cd['min']:.1f}, {cd['max']:.1f}]")
    cr = report["coherence_proxy_range_overall"]
    lines.append(f"- coherence_proxy_range: median {cr['median']:.4f}, range [{cr['min']:.4f}, {cr['max']:.4f}]")
    lines.append(f"  (MERT section_coherence values typically lie in [0.5, 1.0]; a range")
    lines.append(f"  of 0.01 means all 4 'sections' score within 1% of each other.)")
    lines.append("")
    lines.append("## Sectionability buckets")
    lines.append("")
    for label, stats in report["sectionability_buckets"].items():
        lines.append(f"- **{label}**: {stats['count']}/{n_total} ({100*stats['frac']:.0f}%)")
    lines.append("")
    lines.append("## Vocal vs Instrumental")
    lines.append("")
    lines.append("| Stratum | n | range median | range p10 | range p90 |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, stats in [("vocal", vocal_stats), ("instrumental", instr_stats)]:
        lines.append(f"| {label} | {stats['n']} | {stats['coherence_range_median']:.4f} | "
                     f"{stats['coherence_range_p10']:.4f} | {stats['coherence_range_p90']:.4f} |")
    lines.append("")
    lines.append("## High vs Low final quality (musicality @ σ=0.6 median split)")
    lines.append("")
    if high_q_stats and low_q_stats:
        lines.append(f"- median split point: {q_split:.3f}")
        lines.append("| Stratum | n | range median | range p10 | range p90 |")
        lines.append("|---|---:|---:|---:|---:|")
        for label, stats in [("high_q", high_q_stats), ("low_q", low_q_stats)]:
            lines.append(f"| {label} | {stats['n']} | {stats['coherence_range_median']:.4f} | "
                         f"{stats['coherence_range_p10']:.4f} | {stats['coherence_range_p90']:.4f} |")
    lines.append("")
    lines.append("## Correlation: sectionability proxy vs CU-MS within-prompt ρ")
    lines.append("")
    sp = report["correlation_sectionability_vs_cu_ms_within_prompt_rho"]
    if sp["spearman_rho_coherence_range_vs_mean_ms_rho"] is not None:
        lines.append(f"- Spearman ρ(coherence_range, CU-MS mean within-prompt ρ) = "
                     f"**{sp['spearman_rho_coherence_range_vs_mean_ms_rho']:.4f}**")
        lines.append("")
        lines.append("Interpretation: a positive correlation would support the hypothesis")
        lines.append("that section credit works better on clips that are actually section-")
        lines.append("structured. A near-zero correlation would mean section structure does")
        lines.append("NOT predict CU-MS performance — section credit struggles for some")
        lines.append("other reason.")
    lines.append("")
    lines.append("## PI-pending interpretation")
    lines.append("")
    lines.append("- If the **weak** bucket dominates (e.g., > 50% with range < 0.05), this")
    lines.append("  supports PI's pre-launch hypothesis that ACE-Step 30-50 s generations")
    lines.append("  often lack stable section structure, and section-credit underperforms")
    lines.append("  because the task output isn't section-structured.")
    lines.append("- If the **strong** bucket dominates, section structure IS present but")
    lines.append("  the failure is in the credit-unit comparison itself, not the audio.")
    lines.append("- The correlation result tells us whether sectionability (when present)")
    lines.append("  predicts CU-MS performance.")
    md_path.write_text("\n".join(lines) + "\n")
    print(f"[sectionability] wrote {md_path}", flush=True)


if __name__ == "__main__":
    main()
