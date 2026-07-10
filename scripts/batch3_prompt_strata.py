#!/usr/bin/env python
"""Batch 3 — stratified online-pilot prompt selection (≥128, from HELD-OUT prompts only).

held_out (256) is used so the EVPD (trained on dev) never saw these prompts' candidates. Strata
(from Batch-1 labels): (A) type-risk = prompts with >=2 type-error candidates (vocal→no-vocal and
instrumental→vocal), the MAIN group; (B) balanced vocal/instrumental low-risk; (C) lyric-bearing
EN-vocal (for the lyric-first eval); (D) general sanity. Preserves EN-vocal for lyric analysis.
Writes BATCH3_PROMPT_STRATA.{json,md} + the selected manifest rows.
"""
from __future__ import annotations
import glob, json
from collections import defaultdict
from pathlib import Path

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
MASTER = REPO / "orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
THR = VOCAL_PRESENCE_THRESHOLD
TARGET = 192   # if cheap; will be trimmed to >=128 across strata


def main():
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            if l.strip():
                r = json.loads(l); recs[(r["prompt_id"], r["candidate_index"])] = r
    lab = {}
    for l in open(RAW):
        r = json.loads(l)
        if r.get("ok"):
            lab[(r["prompt_id"], r["candidate_index"])] = r
    master = {r["prompt_id"]: r for r in json.loads(MASTER.read_text())["prompts"]}
    # per-prompt: split, vocal_stratum, language, type-error count
    pinfo = {}
    te_count = defaultdict(int)
    for (pid, ci), r in recs.items():
        L = lab.get((pid, ci))
        if not L:
            continue
        present = int((L["vocal_energy_ratio"] >= THR) and not L.get("near_silent"))
        req = int(r.get("vocal_stratum") == "vocal")
        if present != req:
            te_count[pid] += 1
        pinfo.setdefault(pid, {"split": r.get("split"), "vs": r.get("vocal_stratum"),
                               "lang": r.get("language"), "midx": int(r.get("manifest_index")),
                               "has_lyrics": bool(r.get("has_lyrics"))})
    held = {p: i for p, i in pinfo.items() if i["split"] == "held_out"}

    A = sorted([p for p in held if te_count[p] >= 2], key=lambda p: -te_count[p])          # type-risk (main)
    en_vocal = [p for p in held if held[p]["vs"] == "vocal" and held[p]["lang"] == "en"]
    C = sorted([p for p in en_vocal if te_count[p] < 2], key=lambda p: -held[p]["midx"])    # lyric-bearing low-risk
    low = [p for p in held if te_count[p] < 2]
    B_voc = [p for p in low if held[p]["vs"] == "vocal"]
    B_ins = [p for p in low if held[p]["vs"] == "instrumental"]
    used = set()

    def take(lst, n):
        out = []
        for p in lst:
            if p not in used and len(out) < n:
                out.append(p); used.add(p)
        return out

    sel = {}
    sel["A_type_risk"] = take(A, 80)                       # main analysis group
    sel["C_lyric_bearing_en_vocal"] = take(C, 40)         # lyric-first
    sel["B_balanced_vocal"] = take(B_voc, 24)
    sel["B_balanced_instrumental"] = take(B_ins, 24)
    sel["D_general_sanity"] = take([p for p in held], 24)  # remaining held-out, any
    all_sel = [p for g in sel.values() for p in g]
    # ensure >=128
    if len(all_sel) < 128:
        sel["D_general_sanity"] += take([p for p in held], 128 - len(all_sel))
        all_sel = [p for g in sel.values() for p in g]

    en_in_sel = [p for p in all_sel if held[p]["vs"] == "vocal" and held[p]["lang"] == "en"]
    report = {
        "n_selected": len(all_sel), "target": TARGET,
        "strata_sizes": {k: len(v) for k, v in sel.items()},
        "en_vocal_in_selection_for_lyric": len(en_in_sel),
        "vocal_in_sel": sum(1 for p in all_sel if held[p]["vs"] == "vocal"),
        "instrumental_in_sel": sum(1 for p in all_sel if held[p]["vs"] == "instrumental"),
        "all_held_out": True, "source_split": "held_out",
        "type_risk_definition": ">=2 type-error candidates in Batch-1 (of 8)",
    }
    manifest = []
    for g, ps in sel.items():
        for p in ps:
            m = master[p]
            manifest.append({"prompt_id": p, "stratum": g, "manifest_index": held[p]["midx"],
                             "prompt_source": m.get("prompt_source"), "vocal_stratum": held[p]["vs"],
                             "language": held[p]["lang"], "te_count_batch1": te_count[p],
                             "split": "held_out"})
    (P2 / "batch3").mkdir(parents=True, exist_ok=True)
    (P2 / "batch3" / "BATCH3_PROMPT_STRATA.json").write_text(json.dumps(report, indent=2))
    with (P2 / "batch3" / "batch3_selected_prompts.jsonl").open("w") as fh:
        for m in manifest:
            fh.write(json.dumps(m) + "\n")
    md = ["# Batch 3 — Stratified online-pilot prompt selection", "",
          f"**{len(all_sel)} prompts** (all held_out; EVPD never trained on them). "
          f"EN-vocal for lyric eval: {len(en_in_sel)}.", "", "| stratum | n |", "|---|---|"]
    for k, v in report["strata_sizes"].items():
        md.append(f"| {k} | {v} |")
    md += ["", f"vocal {report['vocal_in_sel']} / instrumental {report['instrumental_in_sel']}; "
           f"type-risk = ≥2 type-error candidates in Batch-1."]
    (P2 / "batch3" / "BATCH3_PROMPT_STRATA.md").write_text("\n".join(md))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
