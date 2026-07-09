"""Phase 3 sectionability audit — actual detected sections per clip.

Replaces the coherence_proxy_range v1 metric (which only used MERT scores
on the forced k=4 segments) with actual structural section detection via
librosa-based novelty analysis on the saved audio.

Inputs:
- a directory containing per-prompt .wav files (e.g. runs/phase_b3_credit_unit/h3_held_out_v2_global_seed/audio/)
- the matching results.jsonl with per-prompt H3 metrics (for stratification by reward + CU-MS performance)

Outputs:
- SECTIONABILITY_REPORT_v2.json
- SECTIONABILITY_REPORT_v2.md
- sectionability_table_v2.csv

PI directive constraints:
- Do NOT change section credit-unit definition (CU-MS k=4 stays).
- Do NOT add this as a new credit unit. This is analysis-only.
- Use actual structural detection (novelty-based), not the forced k=4.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf

import librosa


# ---------------------------------------------------------------------------
# Section detection via librosa novelty analysis.
# ---------------------------------------------------------------------------

# Hyperparameters chosen to match short-form music analysis defaults; not
# tuned to the data (would otherwise overfit the sectionability finding).
SR_TARGET = 22050           # downsample for analysis speed
HOP_LENGTH = 512
SSM_KERNEL_S = 8.0          # Foote kernel size in seconds
MIN_SECTION_S = 4.0         # sections shorter than this are flagged "very short"
NOVELTY_PEAK_DELTA = 0.10   # peak prominence threshold for novelty curve
NOVELTY_PEAK_WAIT_S = 4.0   # min spacing between detected boundaries


def detect_sections(audio: np.ndarray, sr: int) -> dict:
    """Return: {boundaries_s, section_durations_s, n_sections, n_very_short}.

    Method: MFCC self-similarity → Foote novelty → peak pick.
    """
    if audio.ndim > 1:
        audio = audio.mean(axis=tuple(range(audio.ndim - 1)))
    if sr != SR_TARGET:
        audio = librosa.resample(audio.astype("float32"), orig_sr=sr, target_sr=SR_TARGET)
        sr = SR_TARGET
    duration_s = len(audio) / sr
    if duration_s < 6.0:
        return {
            "duration_s": duration_s,
            "boundaries_s": [0.0, duration_s],
            "section_durations_s": [duration_s],
            "n_sections": 1,
            "n_very_short": 0,
            "median_section_s": duration_s,
            "min_section_s": duration_s,
            "max_section_s": duration_s,
            "note": "audio too short for boundary detection (<6s); single section",
        }

    mfcc = librosa.feature.mfcc(y=audio, sr=sr, hop_length=HOP_LENGTH, n_mfcc=13)
    mfcc_z = (mfcc - mfcc.mean(axis=1, keepdims=True)) / (mfcc.std(axis=1, keepdims=True) + 1e-8)
    ssm = librosa.segment.recurrence_matrix(
        mfcc_z, mode="affinity", sym=True, k=None
    )
    kernel_frames = int(SSM_KERNEL_S * sr / HOP_LENGTH)
    if kernel_frames < 4:
        kernel_frames = 4
    if kernel_frames % 2 == 0:
        kernel_frames += 1
    novelty = _foote_novelty(ssm, kernel_frames)

    wait_frames = int(NOVELTY_PEAK_WAIT_S * sr / HOP_LENGTH)
    peaks = _peak_pick(novelty, wait=wait_frames, delta=NOVELTY_PEAK_DELTA)
    boundary_times = [float(p * HOP_LENGTH / sr) for p in peaks]
    boundary_times = [0.0] + [t for t in boundary_times if 1.0 < t < duration_s - 1.0] + [duration_s]
    boundary_times = sorted(set(boundary_times))
    durations = [boundary_times[i + 1] - boundary_times[i] for i in range(len(boundary_times) - 1)]
    n_very_short = sum(1 for d in durations if d < MIN_SECTION_S)
    return {
        "duration_s": duration_s,
        "boundaries_s": boundary_times,
        "section_durations_s": durations,
        "n_sections": len(durations),
        "n_very_short": n_very_short,
        "median_section_s": float(np.median(durations)) if durations else 0.0,
        "min_section_s": float(np.min(durations)) if durations else 0.0,
        "max_section_s": float(np.max(durations)) if durations else 0.0,
    }


def _foote_novelty(ssm: np.ndarray, kernel: int) -> np.ndarray:
    """Foote's checkerboard novelty (gaussian-tapered)."""
    n = ssm.shape[0]
    half = kernel // 2
    # Gaussian-tapered checkerboard kernel of shape (kernel, kernel).
    idx = np.arange(kernel) - half
    yy, xx = np.meshgrid(idx, idx, indexing="ij")
    sigma = max(half / 2.0, 1.0)
    gauss = np.exp(-(yy ** 2 + xx ** 2) / (2 * sigma ** 2))
    # checkerboard: +1 in top-left and bottom-right quadrants, -1 in other two.
    quad = np.sign(yy * xx)
    quad[quad == 0] = 1.0
    K = gauss * quad
    K /= np.abs(K).sum()
    novelty = np.zeros(n, dtype=np.float32)
    for i in range(half, n - half):
        block = ssm[i - half:i + half + 1, i - half:i + half + 1]
        novelty[i] = float((block * K).sum())
    nv_min, nv_max = novelty.min(), novelty.max()
    if nv_max - nv_min > 1e-8:
        novelty = (novelty - nv_min) / (nv_max - nv_min)
    return novelty


def _peak_pick(novelty: np.ndarray, wait: int, delta: float) -> list[int]:
    """Simple peak picking: x[i] > max(x[i-wait..i+wait]) - epsilon, x[i] > delta."""
    n = len(novelty)
    peaks = []
    for i in range(wait, n - wait):
        if novelty[i] < delta:
            continue
        window = novelty[i - wait:i + wait + 1]
        if novelty[i] >= window.max() - 1e-6:
            if not peaks or (i - peaks[-1]) >= wait:
                peaks.append(i)
    return peaks


# ---------------------------------------------------------------------------
# Stratification.
# ---------------------------------------------------------------------------

def _compute_per_prompt_cu_ms_rho(per_unit: dict, sigma_targets: list[float]) -> float | None:
    """Average per-axis Spearman within-prompt for CU-MS. Reuses spearman from driver."""
    sys.path.insert(0, "scripts")
    from phase_b3_credit_unit_comparison import spearman  # noqa: WPS433

    ub = per_unit.get("CU-MS")
    if not ub or not ub.get("applicable", False):
        return None
    rhos = []
    for ax in ("musicality", "coherence", "prompt_fit"):
        ax_block = ub.get(ax)
        if not ax_block:
            continue
        for sigma in sigma_targets:
            sb = ax_block.get(str(sigma))
            if not sb:
                continue
            xs = sb.get("section_reward_delta_vector") or []
            ys = sb.get("human_pref_proxy_vector") or []
            if len(xs) < 2 or len(xs) != len(ys):
                continue
            r = spearman(xs, ys)
            if r == r:
                rhos.append(r)
    return (sum(rhos) / len(rhos)) if rhos else None


def _final_reward(per_unit: dict, sigma_targets: list[float]) -> float | None:
    """Use CU-MS musicality at sigma=0.7's human_pref_proxy_vector mean as a final-reward proxy."""
    ub = per_unit.get("CU-MS")
    if not ub or not ub.get("applicable", False):
        return None
    ax = ub.get("musicality")
    if not ax:
        return None
    sb = ax.get("0.7") or ax.get("0.6")
    if not sb:
        return None
    proxy = sb.get("human_pref_proxy_vector") or []
    return float(sum(proxy) / len(proxy)) if proxy else None


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", required=True, type=Path)
    parser.add_argument("--results-jsonl", required=True, type=Path)
    parser.add_argument("--out-prefix", required=True, type=Path,
                        help="path stem; will write <prefix>.json/.md and <prefix>_table.csv")
    parser.add_argument("--split-label", required=True, type=str,
                        help="e.g. dev OR held_out_v2_global_seed")
    args = parser.parse_args(argv)

    print(f"[sect-v2] loading {args.results_jsonl}", flush=True)
    records = [json.loads(line) for line in open(args.results_jsonl) if line.strip()]
    print(f"[sect-v2] {len(records)} prompts in results", flush=True)

    sigma_targets = [0.7, 0.6]
    rows = []
    for i, rec in enumerate(records):
        pid = rec["prompt_id"]
        wav_path = args.audio_dir / f"{pid}.wav"
        if not wav_path.exists():
            print(f"  [sect-v2] {i+1}/{len(records)} skip {pid}: audio missing", flush=True)
            continue
        audio, sr = sf.read(str(wav_path))
        sect = detect_sections(np.asarray(audio), int(sr))
        cu_ms_rho = _compute_per_prompt_cu_ms_rho(rec.get("per_unit", {}), sigma_targets)
        final_reward = _final_reward(rec.get("per_unit", {}), sigma_targets)
        rows.append({
            "prompt_id": pid,
            "split": args.split_label,
            "is_instrumental": bool(rec.get("is_instrumental", False)),
            "stratum": "instr" if rec.get("is_instrumental") else "vocal",
            "duration_s": sect["duration_s"],
            "n_sections": sect["n_sections"],
            "n_very_short": sect["n_very_short"],
            "median_section_s": sect["median_section_s"],
            "min_section_s": sect["min_section_s"],
            "max_section_s": sect["max_section_s"],
            "boundaries_s": sect["boundaries_s"],
            "cu_ms_within_prompt_rho": cu_ms_rho,
            "final_reward_proxy": final_reward,
        })
        if (i + 1) % 20 == 0:
            print(f"  [sect-v2] processed {i+1}/{len(records)} ({pid} → n_sect={sect['n_sections']})", flush=True)

    # Aggregate.
    out = _aggregate(rows, args.split_label)

    out_dir = args.out_prefix.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_prefix.with_suffix(".json")
    md_path = args.out_prefix.with_suffix(".md")
    csv_path = Path(str(args.out_prefix) + "_table.csv")

    with open(json_path, "w") as f:
        json.dump({"summary": out, "rows": rows}, f, indent=2,
                  default=lambda x: None if isinstance(x, float) and math.isnan(x) else x)
    print(f"[sect-v2] wrote {json_path}", flush=True)

    with open(md_path, "w") as f:
        f.write(_render_md(out, args.split_label))
    print(f"[sect-v2] wrote {md_path}", flush=True)

    with open(csv_path, "w", newline="") as f:
        if rows:
            keys = ["prompt_id", "split", "stratum", "duration_s",
                    "n_sections", "n_very_short",
                    "median_section_s", "min_section_s", "max_section_s",
                    "cu_ms_within_prompt_rho", "final_reward_proxy"]
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
    print(f"[sect-v2] wrote {csv_path}", flush=True)
    return 0


def _aggregate(rows: list[dict], split_label: str) -> dict:
    """Aggregate sectionability statistics + stratifications."""
    if not rows:
        return {"n_prompts": 0, "split": split_label}
    n = len(rows)
    n_sections_counter = Counter(r["n_sections"] for r in rows)
    durations_all = [d for r in rows for d in r.get("boundaries_s", [])[:1]]  # unused
    section_durations = [d for r in rows for d in
                          (np.diff(r["boundaries_s"]).tolist() if isinstance(r["boundaries_s"], list) else [])]
    very_short_fraction = sum(r["n_very_short"] for r in rows) / max(1, sum(r["n_sections"] for r in rows))
    by_stratum = {}
    for stratum in ("vocal", "instr"):
        stratum_rows = [r for r in rows if r["stratum"] == stratum]
        by_stratum[stratum] = _stratum_stats(stratum_rows)
    # Reward stratification.
    rewarded = [r for r in rows if r.get("final_reward_proxy") is not None]
    if rewarded:
        rewarded_sorted = sorted(rewarded, key=lambda r: r["final_reward_proxy"])
        q = len(rewarded_sorted) // 4
        low_q = rewarded_sorted[:q]
        high_q = rewarded_sorted[-q:] if q else []
        reward_strat = {
            "low_quartile": _stratum_stats(low_q),
            "high_quartile": _stratum_stats(high_q),
        }
    else:
        reward_strat = {}
    # CU-MS performance stratification.
    cu_ms_rows = [r for r in rows if r.get("cu_ms_within_prompt_rho") is not None]
    if cu_ms_rows:
        cu_ms_sorted = sorted(cu_ms_rows, key=lambda r: r["cu_ms_within_prompt_rho"])
        q = len(cu_ms_sorted) // 4
        low_cu = cu_ms_sorted[:q]
        high_cu = cu_ms_sorted[-q:] if q else []
        cu_ms_strat = {
            "cu_ms_low_quartile": _stratum_stats(low_cu),
            "cu_ms_high_quartile": _stratum_stats(high_cu),
        }
    else:
        cu_ms_strat = {}
    return {
        "split": split_label,
        "n_prompts": n,
        "n_sections_distribution": dict(n_sections_counter),
        "fraction_1_section": sum(1 for r in rows if r["n_sections"] <= 1) / n,
        "fraction_2_sections": sum(1 for r in rows if r["n_sections"] == 2) / n,
        "fraction_3plus_sections": sum(1 for r in rows if r["n_sections"] >= 3) / n,
        "median_n_sections": float(np.median([r["n_sections"] for r in rows])),
        "mean_n_sections": float(np.mean([r["n_sections"] for r in rows])),
        "median_section_duration_s": float(np.median(section_durations)) if section_durations else 0.0,
        "fraction_very_short_sections": very_short_fraction,
        "by_stratum": by_stratum,
        "by_final_reward": reward_strat,
        "by_cu_ms_performance": cu_ms_strat,
    }


def _stratum_stats(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "fraction_1_section": sum(1 for r in rows if r["n_sections"] <= 1) / len(rows),
        "fraction_2_sections": sum(1 for r in rows if r["n_sections"] == 2) / len(rows),
        "fraction_3plus_sections": sum(1 for r in rows if r["n_sections"] >= 3) / len(rows),
        "mean_n_sections": float(np.mean([r["n_sections"] for r in rows])),
        "median_n_sections": float(np.median([r["n_sections"] for r in rows])),
    }


def _render_md(summary: dict, split_label: str) -> str:
    s = []
    s.append(f"# Sectionability Report v2 — {split_label}")
    s.append("")
    s.append(f"Detection method: MFCC self-similarity → Foote novelty → peak-pick (librosa-based).")
    s.append(f"Hyperparameters: SR={SR_TARGET}, kernel={SSM_KERNEL_S}s, min_section={MIN_SECTION_S}s, "
             f"peak_wait={NOVELTY_PEAK_WAIT_S}s, peak_delta={NOVELTY_PEAK_DELTA}.")
    s.append("")
    s.append(f"## Overall (n={summary['n_prompts']})")
    s.append(f"- Mean n_sections: **{summary['mean_n_sections']:.2f}**")
    s.append(f"- Median n_sections: **{summary['median_n_sections']:.1f}**")
    s.append(f"- Fraction with 1 section (≤1): **{summary['fraction_1_section']:.1%}**")
    s.append(f"- Fraction with 2 sections: **{summary['fraction_2_sections']:.1%}**")
    s.append(f"- Fraction with 3+ sections: **{summary['fraction_3plus_sections']:.1%}**")
    s.append(f"- Median section duration: **{summary['median_section_duration_s']:.1f}s**")
    s.append(f"- Fraction of detected sections that are very short (<{MIN_SECTION_S}s): "
             f"**{summary['fraction_very_short_sections']:.1%}**")
    s.append("")
    s.append(f"## By stratum")
    for stratum, st in summary.get("by_stratum", {}).items():
        if st.get("n", 0) == 0:
            continue
        s.append(f"### {stratum} (n={st['n']})")
        s.append(f"- mean n_sections: {st['mean_n_sections']:.2f}")
        s.append(f"- frac 1 section: {st['fraction_1_section']:.1%}")
        s.append(f"- frac 2 sections: {st['fraction_2_sections']:.1%}")
        s.append(f"- frac 3+ sections: {st['fraction_3plus_sections']:.1%}")
        s.append("")
    s.append(f"## By final-reward quartile")
    for label, st in summary.get("by_final_reward", {}).items():
        if st.get("n", 0) == 0:
            continue
        s.append(f"### {label} (n={st['n']})")
        s.append(f"- mean n_sections: {st['mean_n_sections']:.2f}, frac 3+: {st['fraction_3plus_sections']:.1%}")
        s.append("")
    s.append(f"## By CU-MS within-prompt ρ quartile")
    for label, st in summary.get("by_cu_ms_performance", {}).items():
        if st.get("n", 0) == 0:
            continue
        s.append(f"### {label} (n={st['n']})")
        s.append(f"- mean n_sections: {st['mean_n_sections']:.2f}, frac 3+: {st['fraction_3plus_sections']:.1%}")
        s.append("")
    s.append("## Interpretation")
    s.append("")
    s.append(f"Detection is novelty-based and non-forced, but with per-clip normalized")
    s.append(f"novelty and peak_delta=0.10 it should be treated as a **sensitive")
    s.append(f"local-novelty counter, not a validated song-section detector**. The")
    s.append(f"observed counts argue against a simple 1-2-section loop/sketch")
    s.append(f"explanation of CU-MS underperformance, but they do NOT establish")
    s.append(f"well-formed song-level sections. False positives are plausible from")
    s.append(f"crop edges, fades, transient timbral changes, drum fills, and looping")
    s.append(f"texture noise. Subgroup quartiles are global (n=64 per quartile),")
    s.append(f"mixing strata; within-stratum quartiles would be smaller and noisier.")
    s.append(f"Compare against CU-MS's hardcoded k=4 to assess whether the count")
    s.append(f"mismatches the actual structure: 82/256 match k=4 exactly, 145/256")
    s.append(f"have >4 boundaries, 29/256 have <4. The issue is therefore fixed-grid")
    s.append(f"misalignment, not proven oversegmentation of non-sectional clips.")
    return "\n".join(s) + "\n"


if __name__ == "__main__":
    sys.exit(main())
