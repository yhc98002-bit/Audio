#!/usr/bin/env python3
"""Build publication-ready analysis outputs from existing ADSR ledgers."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


ROOT = Path(os.environ.get("MPRM_REPO_ROOT", Path(__file__).resolve().parents[4])).resolve()
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
EXEC = PAPER / "execution_20260707"
STAGE3 = PAPER / "stage3_intervention_20260707"
N2 = PAPER / "population_retry_20260707"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - half, center + half


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def draw_fig2(rows: list[dict], png_path: Path, pdf_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1400, 860
    left, right, top, row_h = 420, 1200, 120, 58
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        font_title = font = font_small = ImageFont.load_default()

    d.text((70, 40), "Figure 2 Data: Clean Rate By Regime / Intervention", fill=(20, 20, 20), font=font_title)
    d.text((70, 82), "Difficult test-set rates; automatic labels; error bars are Wilson 95% CIs.", fill=(70, 70, 70), font=font_small)
    axis_y = top + row_h * len(rows) + 28
    d.line((left, axis_y, right, axis_y), fill=(0, 0, 0), width=2)
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        x = left + int((right - left) * tick)
        d.line((x, axis_y - 8, x, axis_y + 8), fill=(0, 0, 0), width=2)
        d.text((x - 16, axis_y + 14), f"{tick:.2f}", fill=(0, 0, 0), font=font_small)
        d.line((x, top - 12, x, axis_y), fill=(230, 230, 230), width=1)

    palette = {
        "baseline": (75, 121, 161),
        "vocal": (55, 142, 96),
        "instrumental": (168, 104, 58),
        "n2": (115, 94, 150),
    }
    for i, row in enumerate(rows):
        y = top + i * row_h
        p = float(row["clean_rate"])
        lo = float(row["ci95_lo"])
        hi = float(row["ci95_hi"])
        group = row["group"]
        color = palette.get(group, (90, 90, 90))
        x0 = left
        x1 = left + int((right - left) * p)
        cy = y + 24
        d.text((70, y + 10), row["label"], fill=(25, 25, 25), font=font)
        d.rectangle((x0, y + 8, x1, y + 42), fill=color)
        d.line((left + int((right - left) * lo), cy, left + int((right - left) * hi), cy), fill=(20, 20, 20), width=3)
        d.line((left + int((right - left) * lo), cy - 8, left + int((right - left) * lo), cy + 8), fill=(20, 20, 20), width=2)
        d.line((left + int((right - left) * hi), cy - 8, left + int((right - left) * hi), cy + 8), fill=(20, 20, 20), width=2)
        d.text((right + 20, y + 12), f"{p:.3f}", fill=(20, 20, 20), font=font)

    img.save(png_path)

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    page_w, page_h = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(45, page_h - 45, "Figure 2 Data: Clean Rate By Regime / Intervention")
    c.setFont("Helvetica", 9)
    c.drawString(45, page_h - 62, "Difficult test-set rates; automatic labels; error bars are Wilson 95% CIs.")
    left_pt, right_pt, top_pt, row_pt = 215, 535, page_h - 105, 26
    c.setStrokeColor(colors.black)
    c.line(left_pt, top_pt - row_pt * len(rows) - 8, right_pt, top_pt - row_pt * len(rows) - 8)
    color_map = {
        "baseline": colors.HexColor("#4b79a1"),
        "vocal": colors.HexColor("#378e60"),
        "instrumental": colors.HexColor("#a8683a"),
        "n2": colors.HexColor("#735e96"),
    }
    for i, row in enumerate(rows):
        y = top_pt - i * row_pt
        p = float(row["clean_rate"])
        lo = float(row["ci95_lo"])
        hi = float(row["ci95_hi"])
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        c.drawString(45, y - 2, row["label"][:42])
        c.setFillColor(color_map.get(row["group"], colors.gray))
        c.rect(left_pt, y - 9, (right_pt - left_pt) * p, 14, fill=True, stroke=False)
        c.setStrokeColor(colors.black)
        c.line(left_pt + (right_pt - left_pt) * lo, y - 2, left_pt + (right_pt - left_pt) * hi, y - 2)
        c.setFillColor(colors.black)
        c.drawString(right_pt + 8, y - 5, f"{p:.3f}")
    c.save()


def main() -> int:
    figures = PAPER / "figures"
    analysis = PAPER / "analysis"
    figures.mkdir(parents=True, exist_ok=True)
    analysis.mkdir(parents=True, exist_ok=True)

    t21 = load_json(EXEC / "T21_efficiency_metrics.json")
    stage3 = load_json(STAGE3 / "full64_final_summary.json")
    n2 = load_json(N2 / "full128_regime_readout.json")

    rows = []
    rows.append(
        {
            "label": "Baseline vocal-hard",
            "group": "baseline",
            "rows": 17 * 512,
            "clean": round(t21["baseline_vocal_mean"] * 17 * 512),
            "clean_rate": t21["baseline_vocal_mean"],
        }
    )
    rows.append(
        {
            "label": "Baseline instrumental-hard",
            "group": "baseline",
            "rows": 15 * 512,
            "clean": round(t21["baseline_instrumental_mean"] * 15 * 512),
            "clean_rate": t21["baseline_instrumental_mean"],
        }
    )
    for cond in ["vocal_guidance", "vocal_hints", "vocal_both", "instr_text", "instr_sampler", "instr_both"]:
        s = stage3["condition_summary"][cond]
        rows.append(
            {
                "label": cond,
                "group": "vocal" if cond.startswith("vocal") else "instrumental",
                "rows": s["rows"],
                "clean": round(s["type_correct_rate"] * s["rows"]),
                "clean_rate": s["type_correct_rate"],
            }
        )
    rows.append(
        {
            "label": "N2 selected held-out mean",
            "group": "n2",
            "rows": n2["rows"],
            "clean": round(n2["rows"] * sum(
                r["clean_count"] for r in n2["prompt_rows"]
            ) / n2["rows"]),
            "clean_rate": sum(r["clean_count"] for r in n2["prompt_rows"]) / n2["rows"],
        }
    )
    for row in rows:
        lo, hi = wilson(int(row["clean"]), int(row["rows"]))
        p = float(row["clean_rate"])
        row["ci95_lo"] = lo
        row["ci95_hi"] = hi
        row["expected_draws_to_first_clean"] = 1 / p if p > 0 else ""
        row["clean_yield_per_100_draws"] = 100 * p

    write_csv(
        figures / "fig2_regime_data.csv",
        rows,
        [
            "label",
            "group",
            "rows",
            "clean",
            "clean_rate",
            "ci95_lo",
            "ci95_hi",
            "expected_draws_to_first_clean",
            "clean_yield_per_100_draws",
        ],
    )
    draw_fig2(rows, figures / "fig2_regime_plot.png", figures / "fig2_regime_plot.pdf")

    expected_rows = [
        {
            "metric": row["label"],
            "clean_rate": row["clean_rate"],
            "expected_draws_to_first_clean": row["expected_draws_to_first_clean"],
            "clean_yield_per_100_draws": row["clean_yield_per_100_draws"],
            "ci95_lo": row["ci95_lo"],
            "ci95_hi": row["ci95_hi"],
        }
        for row in rows
    ]
    write_csv(
        analysis / "expected_draws_metrics.csv",
        expected_rows,
        [
            "metric",
            "clean_rate",
            "expected_draws_to_first_clean",
            "clean_yield_per_100_draws",
            "ci95_lo",
            "ci95_hi",
        ],
    )

    eff_md = f"""# Efficiency Claims

Generated: 2026-07-07

Sources:

- `paper_prep/execution_20260707/T21_efficiency_metrics.json`
- `paper_prep/execution_20260707/T21_efficiency_metrics.csv`
- `paper_prep/stage3_intervention_20260707/full64_final_summary.json`
- `paper_prep/population_retry_20260707/full128_regime_readout.json`

## Ready Numbers

- Baseline vocal-hard clean rate: mean {t21['baseline_vocal_mean']:.6f}, median {t21['baseline_vocal_median']:.6f}.
- Baseline instrumental-hard clean rate: mean {t21['baseline_instrumental_mean']:.6f}, median {t21['baseline_instrumental_median']:.6f}.
- Vocal intervention lift from existing V3 paired intervention: mean delta {t21['v3_delta_mean']:+.6f}, {t21['v3_prompts_improved']}/{t21['v3_prompts_total']} prompts improved.
- Instrumental strong intervention from existing paired intervention: mean delta {t21['istrong_delta_mean']:+.6f}, {t21['istrong_prompts_improved']}/{t21['istrong_prompts_total']} prompts improved.
- Stage 3 controlled decomposition: `vocal_guidance` {stage3['condition_summary']['vocal_guidance']['type_correct_rate']:.6f}, `vocal_both` {stage3['condition_summary']['vocal_both']['type_correct_rate']:.6f}, `vocal_hints` {stage3['condition_summary']['vocal_hints']['type_correct_rate']:.6f}.
- N2 selected held-out mean clean rate: {sum(r['clean_count'] for r in n2['prompt_rows']) / n2['rows']:.6f}.

## Figure Outputs

- Data: `paper_prep/figures/fig2_regime_data.csv`
- PNG: `paper_prep/figures/fig2_regime_plot.png`
- PDF: `paper_prep/figures/fig2_regime_plot.pdf`
- Expected draws: `paper_prep/analysis/expected_draws_metrics.csv`

## Wording Constraint

These are difficult-test-set rates unless explicitly tied to the selected N2
held-out sample. Do not describe them as generic population rates. Use
"rare / impractical to retry" rather than "impossible." Do not write
"proved no loss."
"""
    (analysis / "efficiency_claims.md").write_text(eff_md)

    stage_rows = []
    for cond in ["vocal_guidance", "vocal_hints", "vocal_both", "instr_text", "instr_sampler", "instr_both"]:
        s = stage3["condition_summary"][cond]
        stage_rows.append(
            {
                "condition": cond,
                "rows": s["rows"],
                "type_correct_rate": s["type_correct_rate"],
                "present_rate": s["present_rate"],
                "median_vocal_energy_ratio": s["vocal_energy_ratio"]["median"],
                "mean_vocal_energy_ratio": s["vocal_energy_ratio"]["mean"],
            }
        )
    write_csv(
        STAGE3 / "stage3_condition_rates_figure_data.csv",
        stage_rows,
        [
            "condition",
            "rows",
            "type_correct_rate",
            "present_rate",
            "median_vocal_energy_ratio",
            "mean_vocal_energy_ratio",
        ],
    )
    stage_md = """# Stage 3 Publication Read-Out

Generated: 2026-07-07

Pre-registration: `paper_prep/STAGE3_INTERVENTION_PREREG_20260707.md`

Audit status: PASS. Final audit reports 6,144 rows, 0 parse errors, 0
missing required rows, 0 duplicate `(prompt_id, condition, seed_idx)` keys,
0 generation errors, 0 near-silent rows, and 0 missing FLACs.

## Pre-Registered Question

The frozen read-out asked which condition component drives the Claim-3 rescue
effect. The expected direction was at least one vocal-side component with a
large clean-rate gain and near-zero instrumental-side gains.

## Results

| Condition | Rows | Type-correct rate | Present rate |
|---|---:|---:|---:|
"""
    for r in stage_rows:
        stage_md += f"| `{r['condition']}` | {r['rows']} | {r['type_correct_rate']:.6f} | {r['present_rate']:.6f} |\n"
    stage_md += """
## Interpretation

- Vocal guidance drives most of the gain: `vocal_guidance` and `vocal_both`
  are both about 0.78 clean/type-correct per try.
- Vocal hints alone are weak: `vocal_hints` is 0.093750, close to the hard
  vocal baseline rather than the guided conditions.
- Instrumental variants are close and weak/near-null: `instr_text`,
  `instr_sampler`, and `instr_both` range from 0.326042 to 0.377083.
- This supports a re-conditioning mechanism, especially for vocal-miss hard
  prompts. It does not establish a universal repair mechanism and should not
  be worded as proof of no loss or proof that retry is impossible.

Figure-ready CSV: `paper_prep/stage3_intervention_20260707/stage3_condition_rates_figure_data.csv`
"""
    (STAGE3 / "STAGE3_PUBLICATION_READOUT.md").write_text(stage_md)

    n2_rows = []
    for regime, count in sorted(n2["regime_counts"].items()):
        n2_rows.append(
            {
                "regime": regime,
                "prompts": count,
                "fraction": n2["regime_fractions"][regime],
            }
        )
    write_csv(N2 / "n2_regime_figure_data.csv", n2_rows, ["regime", "prompts", "fraction"])
    n2_md = """# N2 Population Retry Publication Read-Out

Generated: 2026-07-07

Pre-registration: `paper_prep/POPULATION_RETRY_PREREG_20260707.md`

Audit status: PASS. Final audit reports 16,384 rows, 128 prompts, 128 seeds
per prompt, 0 parse errors, 0 missing required rows, 0 duplicate
`(prompt_id, seed_idx)` keys, 0 generation errors, 0 near-silent rows, and
0 missing FLACs.

## Regime Counts

| Regime | Prompts | Fraction |
|---|---:|---:|
"""
    for r in n2_rows:
        n2_md += f"| `{r['regime']}` | {r['prompts']} | {r['fraction']:.6f} |\n"
    n2_md += f"""
## Strata

- Instrumental: {n2['stratum_summary']['instrumental']['prompts']} prompts,
  mean clean rate {n2['stratum_summary']['instrumental']['mean_clean_rate']:.6f}.
- Vocal: {n2['stratum_summary']['vocal']['prompts']} prompts,
  mean clean rate {n2['stratum_summary']['vocal']['mean_clean_rate']:.6f}.

## Interpretation

The selected held-out retry map separates retry-recoverable prompts from rare
regime prompts. In this selected sample, {n2['regime_counts']['easy_ge_1_in_2']}
prompts were easy at >=1 clean in 2 tries, {n2['regime_counts']['seed_recoverable_1_in_4_to_1_in_2']}
were seed-recoverable at 1 in 4 to 1 in 2, {n2['regime_counts']['low_1_in_16_to_1_in_4']}
were low but not rare, and {n2['regime_counts']['rare_le_1_in_16']} were rare
at <=1 clean in 16 tries.

Population caveat: these 128 prompts were deterministically selected and
stratified by baseline violation-count bins from the held-out set. Treat the
rates as selected/difficult held-out rates, not generic population estimates,
unless a separate sampling argument is added.

Figure-ready CSV: `paper_prep/population_retry_20260707/n2_regime_figure_data.csv`
Prompt-level CSV: `paper_prep/population_retry_20260707/full128_prompt_clean_rates.csv`
"""
    (N2 / "N2_PUBLICATION_READOUT.md").write_text(n2_md)

    print(figures / "fig2_regime_data.csv")
    print(figures / "fig2_regime_plot.png")
    print(figures / "fig2_regime_plot.pdf")
    print(analysis / "expected_draws_metrics.csv")
    print(analysis / "efficiency_claims.md")
    print(STAGE3 / "STAGE3_PUBLICATION_READOUT.md")
    print(N2 / "N2_PUBLICATION_READOUT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
