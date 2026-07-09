#!/usr/bin/env python
"""Sanity-gate analyzer (facts-only). Aggregates the smoke ledgers → SANITY_GATE_RESULTS.md +
SANITY_GATE_AUDIO_MANIFEST.csv + PI_SANITY_GATE_REQUEST.md. Computes auto-FLAGS for the hard
interrupt conditions (§13) but does NOT self-certify PASS — the PI decides (non-self-certified gate)."""
from __future__ import annotations
import csv, glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = Path("/HOME/paratera_xy/pxy1289/HDD_POOL/HaocunYe/Research/AudioDiffusion")
CATS = ["A_trivial_vocal", "B_trivial_instrumental", "C_contradictory",
        "D_e2_vocal_tail", "E_instrumental_risk"]


def main():
    rows = []
    for f in glob.glob(str(HERE / "ledger_w*.jsonl")):
        for l in open(f):
            d = json.loads(l)
            if "error" not in d:
                rows.append(d)
    errs = sum(1 for f in glob.glob(str(HERE / "ledger_w*.jsonl"))
               for l in open(f) if '"error"' in l)
    by = defaultdict(list)
    for r in rows:
        by[r["control_category"]].append(r)

    # manifest
    with (HERE / "SANITY_GATE_AUDIO_MANIFEST.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["flac", "control_category", "prompt_id", "requested_vocal", "seed",
                    "vocal_energy_ratio", "near_silent", "present", "type_correct", "panns_vocal",
                    "common", "semantic", "aesthetic_pq", "lyric"])
        for r in sorted(rows, key=lambda x: (x["control_category"], x["prompt_id"], x["seed_index"])):
            w.writerow([r.get("flac"), r["control_category"], r["prompt_id"], r["requested_vocal"],
                        r["seed"], r["vocal_energy_ratio"], r["near_silent"], r["present"],
                        r["type_correct"], r.get("panns_vocal"), r.get("score_common_robust_lcb"),
                        r.get("score_semantic_fit"), r.get("score_aesthetic_pq"),
                        r.get("score_lyric_intelligibility")])

    def agg(rs):
        tc = np.mean([r["type_correct"] for r in rs])
        ratio = np.mean([r["vocal_energy_ratio"] for r in rs])
        pann = [r["panns_vocal"] for r in rs if r.get("panns_vocal") is not None]
        # detector agreement: Demucs present vs PANNs present (thr 0.0654 from project calib)
        agr = np.mean([int((r["vocal_energy_ratio"] >= 0.1791) == (r["panns_vocal"] >= 0.0654))
                       for r in rs if r.get("panns_vocal") is not None]) if pann else None
        nsil = np.mean([int(r["near_silent"]) for r in rs])
        return dict(n=len(rs), type_correct_rate=round(float(tc), 3),
                    mean_ratio=round(float(ratio), 4),
                    demucs_panns_agree=(round(float(agr), 3) if agr is not None else None),
                    near_silent_frac=round(float(nsil), 3))

    summ = {c: agg(by[c]) for c in CATS if by[c]}

    # auto-flags (hard interrupt conditions — for PI attention, not self-certification)
    flags = []
    if by["A_trivial_vocal"] and summ["A_trivial_vocal"]["type_correct_rate"] < 0.6:
        flags.append(f"A_trivial_vocal type-correct {summ['A_trivial_vocal']['type_correct_rate']} < 0.6 "
                     "(trivial vocal controls not near-clean — possible label/gen bug, §13 hard interrupt)")
    if by["B_trivial_instrumental"] and summ["B_trivial_instrumental"]["type_correct_rate"] < 0.6:
        flags.append(f"B_trivial_instrumental type-correct {summ['B_trivial_instrumental']['type_correct_rate']} < 0.6 "
                     "(trivial instrumental controls not near-clean — possible label/gen bug)")
    allr = [r["vocal_energy_ratio"] for r in rows]
    if allr and (np.std(allr) < 1e-3):
        flags.append("vocal_energy_ratio is near-constant across all clips (degenerate labels)")
    if any(summ.get(c, {}).get("near_silent_frac", 0) > 0.2 for c in CATS):
        flags.append("a category has >20% near-silent clips (possible corrupted/empty audio)")
    nan_scores = sum(1 for r in rows if r.get("score_common_robust_lcb") is None)
    if rows and nan_scores / len(rows) > 0.1:
        flags.append(f"{nan_scores}/{len(rows)} rows missing common score (score pipeline issue)")

    out = {"n_rows": len(rows), "n_gen_errors": errs, "by_category": summ,
           "auto_flags": flags, "expected_reference": {
               "A_trivial_vocal": "type_correct should be HIGH (≈≥0.8) if pipeline healthy",
               "B_trivial_instrumental": "type_correct should be HIGH (≈≥0.8)",
               "C_contradictory": "defines the bad/ill-posed reference signature (no expectation)",
               "D_e2_vocal_tail": "expected LOW type_correct (these are the frozen failing vocal tail)",
               "E_instrumental_risk": "expected MIXED/low (instrumental-leak risk prompts)"}}
    (HERE / "SANITY_GATE_RESULTS.json").write_text(json.dumps(out, indent=2))

    # results md
    md = ["# SANITY GATE RESULTS (facts-only)", "",
          f"- rows: {len(rows)}  | generation errors: {errs}",
          f"- source ledgers: `ledger_w*.jsonl` ({len(glob.glob(str(HERE/'ledger_w*.jsonl')))} workers)",
          f"- audio manifest: `SANITY_GATE_AUDIO_MANIFEST.csv` (all {len(rows)} clips kept as FLAC under `keep/`)",
          "", "## By control category", "",
          "| category | n | type-correct | mean Demucs ratio | Demucs↔PANNs agree | near-silent |",
          "|---|---|---|---|---|---|"]
    for c in CATS:
        s = summ.get(c)
        if s:
            md.append(f"| {c} | {s['n']} | {s['type_correct_rate']} | {s['mean_ratio']} | "
                      f"{s['demucs_panns_agree']} | {s['near_silent_frac']} |")
    md += ["", "## Auto-flags (hard-interrupt conditions, §13)",
           ("- " + "\n- ".join(flags)) if flags else "- none triggered",
           "", "## Expected reference (NOT a pass/fail by the agent — PI decides)"]
    for k, v in out["expected_reference"].items():
        md.append(f"- **{k}**: {v}")
    md += ["", "## Source trace", f"- analysis script: `sanity_gate_analyze.py`",
           f"- inputs: `ledger_w*.jsonl` ({len(rows)} rows, {errs} gen-errors excluded)",
           f"- outputs: `SANITY_GATE_RESULTS.{{md,json}}`, `SANITY_GATE_AUDIO_MANIFEST.csv`"]
    (HERE / "SANITY_GATE_RESULTS.md").write_text("\n".join(md))

    # PI request — pick a few representative clips per category to listen to
    def pick(c, k=3):
        rs = sorted(by[c], key=lambda r: r["vocal_energy_ratio"])
        out = []
        if rs:
            out += [rs[0], rs[len(rs) // 2], rs[-1]][:k]
        return out
    req = ["# PI SANITY GATE REQUEST — 10-minute inspection (MANDATORY, non-self-certified)", "",
           "Large-N ACE-Step generation is **blocked** until you pass this gate (§10/§13).", "",
           "## Please inspect", "1. A few audio files (paths below), 2. the labels/scores table in "
           "`SANITY_GATE_RESULTS.md`, 3. whether trivial controls behave as expected, 4. any obvious "
           "detector mismatch.", "",
           "## Headline numbers", "| category | n | type-correct | mean ratio | D↔PANNs |",
           "|---|---|---|---|---|"]
    for c in CATS:
        s = summ.get(c)
        if s:
            req.append(f"| {c} | {s['n']} | {s['type_correct_rate']} | {s['mean_ratio']} | {s['demucs_panns_agree']} |")
    req += ["", "## Suggested clips to listen to (path · req-type · ratio · type-correct)"]
    for c in CATS:
        for r in pick(c):
            rt = "vocal" if r["requested_vocal"] else "instrumental"
            req.append(f"- [{c}] `{r.get('flac')}` · req={rt} · ratio={r['vocal_energy_ratio']} · "
                       f"type_correct={r['type_correct']}")
    req += ["", "## Auto-flags", ("- " + "\n- ".join(flags)) if flags else "- none",
            "", "## Your decision (reply with one)",
            "- **PASS** → I proceed autonomously to large-N critical path + concurrent exploration.",
            "- **FAIL / FIX** → tell me what looks wrong; I hold large-N and fix.",
            "", "_Manifest: `SANITY_GATE_AUDIO_MANIFEST.csv`. Audio kept as FLAC under `keep/`._"]
    (HERE / "PI_SANITY_GATE_REQUEST.md").write_text("\n".join(req))
    print(json.dumps({"rows": len(rows), "errors": errs,
                      "type_correct": {c: summ[c]["type_correct_rate"] for c in CATS if c in summ},
                      "flags": flags}, indent=2))


if __name__ == "__main__":
    main()
