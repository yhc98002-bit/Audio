#!/usr/bin/env python
"""DECISIVE READ (§5, facts-only): per E2-tail prompt, clean probability p_hat under seed
resampling, the fraction of prompts with 0 clean (p≈0 candidate basins) with Wilson upper bounds,
detector (Demucs↔PANNs) agreement on those, and the empirical BoN curve. NO interpretation."""
from __future__ import annotations
import glob, json, math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main(tag="bon256"):
    # Codex D-review fix: de-duplicate (prompt_id, seed_idx) — worker-count changes across
    # resumed runs can append duplicate keys; counting them inflates n and biases p_hat.
    rows = []; seen = set(); dups = 0
    for f in sorted(glob.glob(str(HERE / "ledgers" / f"{tag}_w*.jsonl"))):
        for l in open(f):
            d = json.loads(l)
            if "error" in d:
                continue
            key = (d["prompt_id"], d.get("seed_idx"))
            if key in seen:
                dups += 1
                continue
            seen.add(key); rows.append(d)
    by = defaultdict(list)
    for r in rows:
        by[r["prompt_id"]].append(r)
    per = {}
    for pid, rs in by.items():
        n = len(rs); k = sum(r["type_correct"] for r in rs)
        lo, hi = wilson(k, n)
        req = "vocal" if rs[0]["requested_vocal"] else "instrumental"
        # detector agreement on this prompt's draws
        dd = [r for r in rs if r.get("panns_vocal") is not None]
        agree = (sum(1 - r["detector_disagree"] for r in dd) / len(dd)) if dd else None
        per[pid] = {"req": req, "n": n, "clean": k, "p_hat": round(k / n, 4),
                    "p_ci": [round(lo, 4), round(hi, 4)], "zero_clean": int(k == 0),
                    "demucs_panns_agree": (round(agree, 3) if agree is not None else None)}
    vocal = [v for v in per.values() if v["req"] == "vocal"]
    instr = [v for v in per.values() if v["req"] == "instrumental"]

    def frac0(grp):
        return (round(sum(v["zero_clean"] for v in grp) / len(grp), 3) if grp else None)

    # empirical BoN curve (over prompts, fixed-N): S_N = mean_p (1-(1-p_hat)^N)
    Ns = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    def curve(grp):
        return {str(N): round(sum(1 - (1 - v["p_hat"]) ** N for v in grp) / len(grp), 4)
                for N in Ns} if grp else {}

    zero_prompts = sorted([pid for pid, v in per.items() if v["zero_clean"]],
                          key=lambda p: per[p]["req"])
    out = {"tag": tag, "n_prompts": len(per), "total_draws": len(rows),
           "fixed_N_per_prompt": (max(v["n"] for v in per.values()) if per else 0),
           "DECISIVE": {
               "fraction_zero_clean_vocal": frac0(vocal),
               "fraction_zero_clean_instrumental": frac0(instr),
               "n_zero_clean": len(zero_prompts),
               "zero_clean_prompts": zero_prompts,
               "note": "zero_clean at this N = p≈0 CANDIDATE basin (needs N=512/1024 + audit + "
                       "intervention to qualify STRONG_ESCAPABLE_BASIN). p_ci upper bound on the "
                       "0-clean prompts bounds the true p."},
           "bon_curve_vocal": curve(vocal), "bon_curve_instrumental": curve(instr),
           "detector_agreement_overall": round(
               sum(v["demucs_panns_agree"] for v in per.values() if v["demucs_panns_agree"] is not None)
               / max(1, sum(1 for v in per.values() if v["demucs_panns_agree"] is not None)), 3),
           "per_prompt": per,
           "source_trace": {"ledgers": f"ledgers/{tag}_w*.jsonl", "n_rows": len(rows),
                            "duplicate_rows_dropped": dups, "script": "decisive_read.py"}}
    (HERE / "DECISIVE_READ.json").write_text(json.dumps(out, indent=2))
    md = ["# DECISIVE READ — E2 tail large-N BoN (facts-only)", "",
          f"- prompts: {len(per)} | draws: {len(rows)} | N/prompt up to {out['fixed_N_per_prompt']}",
          f"- **fraction 0-clean (p≈0 candidate): vocal {frac0(vocal)} ({sum(v['zero_clean'] for v in vocal)}/{len(vocal)}) "
          f"| instrumental {frac0(instr)} ({sum(v['zero_clean'] for v in instr)}/{len(instr)})**",
          f"- detector (Demucs↔PANNs) agreement overall: {out['detector_agreement_overall']}",
          "", "## 0-clean prompts (candidate basins; Wilson p upper-bound)", "",
          "| prompt | req | n | clean | p_hat | p_ci | D↔P agree |", "|---|---|---|---|---|---|---|"]
    for pid in zero_prompts:
        v = per[pid]
        md.append(f"| {pid} | {v['req']} | {v['n']} | {v['clean']} | {v['p_hat']} | {v['p_ci']} | {v['demucs_panns_agree']} |")
    md += ["", "## BoN curve (fixed-N, analytic from p_hat)", "",
           "| group | " + " | ".join(f"S_{n}" for n in Ns) + " |",
           "|---|" + "---|" * len(Ns),
           "| vocal | " + " | ".join(str(curve(vocal).get(str(n), "")) for n in Ns) + " |",
           "| instrumental | " + " | ".join(str(curve(instr).get(str(n), "")) for n in Ns) + " |",
           "", "_Source: `ledgers/" + tag + "_w*.jsonl`, `decisive_read.py`. Facts only; PI maps to claims._"]
    (HERE / "DECISIVE_READ.md").write_text("\n".join(md))
    print(json.dumps({"prompts": len(per), "draws": len(rows),
                      "frac0_vocal": frac0(vocal), "frac0_instr": frac0(instr),
                      "n_zero_clean": len(zero_prompts),
                      "detector_agree": out["detector_agreement_overall"]}, indent=2))


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "bon256")
