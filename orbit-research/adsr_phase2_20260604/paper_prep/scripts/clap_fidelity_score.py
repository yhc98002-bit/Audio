#!/usr/bin/env python3
"""Score CLAP fidelity for selected online outputs against original prompts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import torch
import torchaudio

from mprm.data.prompts import Prompt, load_prompts
from mprm.rewards.clap import ClapReward


ROOT = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
SOURCE_MANIFEST = PAPER / "storage_triage/CLAP_FIDELITY_INPUT_MANIFEST.csv"
PROMPTS = ROOT / "configs/prompts/held_out.jsonl"
OUTDIR = PAPER / "clap_fidelity"
MANIFEST_OUT = OUTDIR / "CLAP_FIDELITY_MANIFEST.csv"
RESULTS_OUT = OUTDIR / "CLAP_FIDELITY_RESULTS.csv"
LEDGER_OUT = OUTDIR / "CLAP_FIDELITY_RESULTS.jsonl"
REPORT_OUT = OUTDIR / "CLAP_FIDELITY_REPORT.md"


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def median(xs: list[float]) -> float:
    return statistics.median(xs) if xs else float("nan")


def mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else float("nan")


def stderr(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    return statistics.stdev(xs) / math.sqrt(len(xs))


def build_manifest() -> list[dict]:
    prompts = {p.prompt_id: p for p in load_prompts(PROMPTS)}
    rows = []
    for r in read_rows(SOURCE_MANIFEST):
        p = prompts.get(r["prompt_id"])
        rows.append(
            {
                **r,
                "prompt_text": p.text if p else "",
                "prompt_lyrics_present": int(bool(p and p.lyrics)),
                "prompt_duration_target": p.duration_target if p else "",
                "prompt_vocal_stratum": (
                    p.strata.get("vocal_vs_instrumental", "") if p else ""
                ),
            }
        )
    write_csv(MANIFEST_OUT, rows, list(rows[0]))
    return rows


def existing_scores() -> set[str]:
    done = set()
    if RESULTS_OUT.exists():
        for r in read_rows(RESULTS_OUT):
            if r.get("status") == "ok":
                done.add(r["source_path"])
    return done


def append_result(row: dict) -> None:
    fieldnames = [
        "source_path",
        "prompt_id",
        "arm",
        "rep",
        "attempt",
        "seed",
        "requested_vocal",
        "type_correct",
        "prompt_vocal_stratum",
        "clap_score",
        "status",
        "error",
        "elapsed_s",
        "device",
    ]
    exists = RESULTS_OUT.exists()
    with RESULTS_OUT.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})
    with LEDGER_OUT.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_report() -> None:
    if not RESULTS_OUT.exists():
        return
    rows = [r for r in read_rows(RESULTS_OUT) if r.get("status") == "ok"]
    by_arm = defaultdict(list)
    by_prompt_arm = defaultdict(lambda: defaultdict(list))
    for r in rows:
        score = float(r["clap_score"])
        arm = str(r["arm"])
        by_arm[arm].append(score)
        by_prompt_arm[r["prompt_id"]][arm].append(score)
    paired = []
    for pid, arms in by_prompt_arm.items():
        if "1" in arms and "6" in arms:
            paired.append(
                {
                    "prompt_id": pid,
                    "arm1_mean": mean(arms["1"]),
                    "arm6_mean": mean(arms["6"]),
                    "delta_arm6_minus_arm1": mean(arms["6"]) - mean(arms["1"]),
                    "n_arm1": len(arms["1"]),
                    "n_arm6": len(arms["6"]),
                }
            )
    paired_path = OUTDIR / "CLAP_FIDELITY_PROMPT_PAIRED.csv"
    if paired:
        write_csv(
            paired_path,
            paired,
            ["prompt_id", "arm1_mean", "arm6_mean", "delta_arm6_minus_arm1", "n_arm1", "n_arm6"],
        )
    deltas = [p["delta_arm6_minus_arm1"] for p in paired]
    delta_mean = mean(deltas) if deltas else float("nan")
    delta_med = median(deltas) if deltas else float("nan")
    delta_se = stderr(deltas)
    ci_lo = delta_mean - 1.96 * delta_se if not math.isnan(delta_se) else float("nan")
    ci_hi = delta_mean + 1.96 * delta_se if not math.isnan(delta_se) else float("nan")
    verdict = "PASS_NON_NEGATIVE" if deltas and ci_lo >= 0 else ("AMBIGUOUS" if deltas else "INCOMPLETE")
    if deltas and delta_mean < 0:
        verdict = "BLOCKED_NEGATIVE"
    md = [
        "# CLAP Fidelity Report",
        "",
        f"Generated: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "",
        f"Manifest: `{rel(MANIFEST_OUT)}`",
        f"Results: `{rel(RESULTS_OUT)}`",
        f"JSONL ledger: `{rel(LEDGER_OUT)}`",
        f"Prompt-paired CSV: `{rel(paired_path)}`",
        "",
        "## Status",
        "",
        f"- Scored rows: {len(rows)}",
        f"- Verdict: **{verdict}**",
        "",
        "## Arm Summary",
        "",
        "| Arm | Rows | Mean CLAP | Median CLAP |",
        "|---:|---:|---:|---:|",
    ]
    for arm in sorted(by_arm, key=lambda x: int(x) if x.isdigit() else x):
        vals = by_arm[arm]
        md.append(f"| {arm} | {len(vals)} | {mean(vals):.6f} | {median(vals):.6f} |")
    md += [
        "",
        "## Prompt-Paired Arm 6 vs Arm 1",
        "",
        f"- Paired prompts with both arms: {len(paired)}",
        f"- Mean delta arm6-arm1: {delta_mean:.6f}",
        f"- Median delta arm6-arm1: {delta_med:.6f}",
        f"- Approximate 95% CI for mean delta: [{ci_lo:.6f}, {ci_hi:.6f}]",
        "",
        "## Wording",
        "",
    ]
    if verdict == "PASS_NON_NEGATIVE":
        md.append("Paper-safe claim: CLAP semantic fidelity against original prompts is non-negative for arm 6 versus arm 1 on the paired scored subset.")
    elif verdict == "AMBIGUOUS":
        md.append("Paper-safe claim: CLAP fidelity is not negative on average, but the confidence interval crosses zero; describe as ambiguous rather than positive.")
    elif verdict == "BLOCKED_NEGATIVE":
        md.append("Blocker: CLAP fidelity is negative on average; reduce or remove any semantic-preservation claim unless another validated metric resolves the conflict.")
    else:
        md.append("Incomplete: scoring has not finished.")
    md.append("")
    REPORT_OUT.write_text("\n".join(md))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = build_manifest()
    if args.limit:
        rows = rows[: args.limit]
    done = existing_scores()
    scorer = ClapReward(device=args.device)
    prompts = {p.prompt_id: p for p in load_prompts(PROMPTS)}
    for i, row in enumerate(rows, 1):
        if row["source_path"] in done:
            continue
        t0 = time.time()
        out = {
            "source_path": row["source_path"],
            "prompt_id": row["prompt_id"],
            "arm": row["arm"],
            "rep": row["rep"],
            "attempt": row["attempt"],
            "seed": row["seed"],
            "requested_vocal": row["requested_vocal"],
            "type_correct": row["type_correct"],
            "prompt_vocal_stratum": row["prompt_vocal_stratum"],
            "device": args.device,
        }
        try:
            path = ROOT / row["source_path"]
            prompt = prompts[row["prompt_id"]]
            wave, sr = torchaudio.load(str(path))
            score = scorer.score(wave, sr, prompt)
            out.update(
                {
                    "clap_score": score.value,
                    "status": "ok",
                    "error": "",
                    "elapsed_s": round(time.time() - t0, 3),
                }
            )
        except Exception as e:
            out.update(
                {
                    "clap_score": "",
                    "status": "error",
                    "error": repr(e),
                    "elapsed_s": round(time.time() - t0, 3),
                }
            )
        append_result(out)
        if i % 25 == 0:
            print(f"scored_index={i} path={row['source_path']} status={out['status']}", flush=True)
            write_report()
    write_report()
    print(REPORT_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

