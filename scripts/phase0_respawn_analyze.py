#!/usr/bin/env python
"""P0.8 stage 2 — Demucs-gate the respawn-screen outputs and freeze the escalation ladder.

Waits for phase0_respawn_screen.py's GENERATION_COMPLETE (or --no-wait), labels every generated
wav with the production Demucs vocal-presence labeler (reuses adsr_downstream._label_one),
computes per-direction × per-condition clean rates (paired across the shared seeds), and freezes
the 2-level ladder per error direction → batch3/RESPAWN_LADDER.json (Batch-3 arm 6 input).
"""
from __future__ import annotations
import argparse, importlib.util, json, time
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import os, sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0/respawn_screen"
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
THR = VOCAL_PRESENCE_THRESHOLD

# import by real module name so ProcessPoolExecutor children can re-import (picklable)
sys.path.insert(0, str(REPO / "scripts"))
import adsr_downstream as ad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--workers", type=int, default=14)
    args = ap.parse_args()
    log = P0 / "gen.log"
    while not args.no_wait:
        if log.exists() and "GENERATION_COMPLETE" in log.read_text()[-2000:]:
            break
        time.sleep(60)
    rows = [json.loads(l) for l in open(P0 / "gen_ledger.jsonl")]
    os.environ["ADSR_THREADS"] = "4"
    out_f = P0 / "labels.jsonl"
    done = set()
    if out_f.exists():
        for l in open(out_f):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["cond"], d["seed"]))
            except Exception:
                pass
    tasks = []
    for r in rows:
        if (r["prompt_id"], r["cond"], r["seed"]) in done:
            continue
        wav = REPO / r["wav"]
        # _label_one(args): (prompt_id, prompt_dir, cand_idx, final_path)
        tasks.append(((r["prompt_id"], str(wav.parent), int(wav.name.split("_")[1]), str(wav)), r))
    print(f"labeling {len(tasks)} wavs ({len(done)} done)", flush=True)
    with out_f.open("a") as fh, ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(ad._label_one, t): r for t, r in tasks}
        for fu in as_completed(futs):
            r = futs[fu]; res = fu.result()
            fh.write(json.dumps({**r, "ok": res.get("ok"),
                                 "ratio": res.get("vocal_energy_ratio"),
                                 "near_silent": res.get("near_silent")}) + "\n")
            fh.flush()
    # ---- analyze ----
    labs = [json.loads(l) for l in open(out_f)]
    res = defaultdict(lambda: defaultdict(list))
    for d in labs:
        if not d.get("ok"):
            continue
        present = int((d["ratio"] >= THR) and not d.get("near_silent"))
        req = int(d["direction"] == "vocal_miss")     # vocal_miss prompts request vocals
        res[d["direction"]][d["cond"]].append(int(present == req))
    summary, ladder = {}, {}
    for direction, conds in res.items():
        summary[direction] = {c: {"n": len(v), "clean_rate": round(sum(v) / len(v), 4)}
                              for c, v in sorted(conds.items())}
        ranked = sorted([c for c in conds if c != "B"],
                        key=lambda c: -sum(conds[c]) / len(conds[c]))
        ladder[direction] = {"level1": ranked[0], "level2": ranked[1] if len(ranked) > 1 else ranked[0],
                             "baseline_clean_rate": round(sum(conds["B"]) / len(conds["B"]), 4)}
    B3.mkdir(parents=True, exist_ok=True)
    cond_defs = {
        "B": "plain reseed", "V1": "guidance_scale_text=5.0, guidance_scale_lyric=7.5",
        "V2": "structure-hint inject [verse/chorus]", "V3": "V1+V2",
        "I1": "text += ', pure instrumental, no vocals, no singing, no voice'",
        "I2": "cfg_scale=7.5", "I3": "I1+I2"}
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "screen_summary": summary, "ladder": ladder, "condition_definitions": cond_defs,
           "note": "Batch-3 arm 6: restart1=new seed, restart2=level1 intervention, restart3+=level2. Dev-fit only; held_out untouched."}
    (B3 / "RESPAWN_LADDER.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
