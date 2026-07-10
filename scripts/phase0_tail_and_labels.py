#!/usr/bin/env python
"""P0.5 + P0.6(sweep/packet) — tail characterization, E2 subgroup freeze, label robustness.

P0.5: beta-binomial fit to per-prompt violation counts (overall + per stratum); qualitative
      table of ≥6/8 prompts; FREEZE the E2 tail subgroup = held_out prompts with Batch-1 ≥5/8
      violations → orbit-research/adsr_phase2_20260604/batch3/E2_TAIL_SUBGROUP.jsonl
P0.6a: label-threshold sweep θ∈[0.05,0.35] — candidate type-error, survivor-top1, gated-BoN-5 —
      shows conclusions are threshold-stable.
P0.6b: 150-case ambiguous rater packet (blinded order, instructions, response sheet, audio
      manifest) for PI distribution to the 5 students. 2 raters/case + tiebreak.
"""
from __future__ import annotations
import glob, hashlib, json, statistics
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
AMBIG = REPO / "orbit-research/adsr_phase2_20260604/vocal_ambiguous_check_packet.jsonl"
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0"
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
THR = VOCAL_PRESENCE_THRESHOLD


def load():
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            r = json.loads(l); recs[(r["prompt_id"], r["candidate_index"])] = r
    lab = {}
    for l in open(RAW):
        r = json.loads(l)
        if r.get("ok"):
            lab[(r["prompt_id"], r["candidate_index"])] = r
    return recs, lab


def beta_binom_fit(counts, n=8):
    """Method-of-moments beta-binomial fit; returns (alpha, beta, ICC)."""
    x = np.asarray(counts, float)
    m1, m2 = x.mean(), (x ** 2).mean()
    denom = n * (m2 / m1 - m1 - 1) + m1
    if denom == 0:
        return None, None, None
    a = (n * m1 - m2) / denom
    b = (n - m1) * (n - m2 / m1) / denom
    icc = 1 / (a + b + 1) if (a and b and a > 0 and b > 0) else None
    return (round(float(a), 4) if a else None, round(float(b), 4) if b else None,
            round(float(icc), 4) if icc else None)


def main():
    recs, lab = load()
    P0.mkdir(parents=True, exist_ok=True); B3.mkdir(parents=True, exist_ok=True)
    viol = defaultdict(int); meta = {}
    for k, r in recs.items():
        L = lab[k]
        present = int((L["vocal_energy_ratio"] >= THR) and not L.get("near_silent"))
        req = int(r.get("vocal_stratum") == "vocal")
        if present != req:
            viol[k[0]] += 1
        meta.setdefault(k[0], {"vs": r.get("vocal_stratum"), "lang": r.get("language"),
                               "genre": r.get("genre"), "split": r.get("split"),
                               "lyric_density": r.get("lyric_density")})
    pids = sorted(meta)
    counts = [viol[p] for p in pids]

    # ---------- P0.5 ----------
    a, b, icc = beta_binom_fit(counts)
    fits = {"all": {"mean": round(float(np.mean(counts)), 3), "var": round(float(np.var(counts)), 3),
                    "binomial_var_at_same_mean": round(float(np.mean(counts) * (1 - np.mean(counts) / 8)), 3),
                    "beta_binom_alpha": a, "beta_binom_beta": b, "ICC": icc}}
    for s in ("vocal", "instrumental"):
        cs = [viol[p] for p in pids if meta[p]["vs"] == s]
        aa, bb, ii = beta_binom_fit(cs)
        fits[s] = {"n_prompts": len(cs), "mean": round(float(np.mean(cs)), 3),
                   "frac_ge6": round(float(np.mean([c >= 6 for c in cs])), 4),
                   "beta_binom_alpha": aa, "beta_binom_beta": bb, "ICC": ii}
    tail66 = [{"prompt_id": p, **meta[p], "violations": viol[p]}
              for p in pids if viol[p] >= 6]
    tail66.sort(key=lambda d: -d["violations"])
    e2 = [{"prompt_id": p, **meta[p], "batch1_violations": viol[p]}
          for p in pids if viol[p] >= 5 and meta[p]["split"] == "held_out"]
    with (B3 / "E2_TAIL_SUBGROUP.jsonl").open("w") as fh:
        for r in e2:
            fh.write(json.dumps(r) + "\n")
    p05 = {"beta_binomial": fits, "n_ge6_prompts": len(tail66),
           "E2_subgroup_frozen": {"definition": "held_out AND Batch-1 violations >= 5/8",
                                  "n": len(e2),
                                  "by_stratum": dict(Counter(r["vs"] for r in e2))},
           "ge6_qualitative_table": tail66}
    (P0 / "P0_5_TAIL_CHARACTERIZATION.json").write_text(json.dumps(p05, indent=2))

    # ---------- P0.6a threshold sweep ----------
    sweep = []
    for th in np.arange(0.05, 0.351, 0.02):
        v = defaultdict(int)
        cand_te = 0
        for k, r in recs.items():
            L = lab[k]
            present = int((L["vocal_energy_ratio"] >= th) and not L.get("near_silent"))
            req = int(r.get("vocal_stratum") == "vocal")
            if present != req:
                cand_te += 1; v[k[0]] += 1
        # survivor top-1 (final common) + gated BoN-5 on held_out
        by_p = defaultdict(list)
        for k, r in recs.items():
            L = lab[k]
            present = int((L["vocal_energy_ratio"] >= th) and not L.get("near_silent"))
            by_p[k[0]].append({"ci": k[1], "clean": int(present == int(r.get("vocal_stratum") == "vocal")),
                               "final": r.get("final_common_robust_lcb"), "split": r.get("split")})
        s1 = []
        g5 = []
        for p, g in by_p.items():
            g.sort(key=lambda c: c["ci"])
            top = max(g, key=lambda c: c["final"])
            s1.append(1 - top["clean"])
            if g[0]["split"] == "held_out":
                comp = g[:5]
                passers = [c for c in comp if c["clean"]]
                g5.append(int(not passers))
        sweep.append({"threshold": round(float(th), 3),
                      "candidate_type_error": round(cand_te / len(recs), 4),
                      "survivor_top1_te": round(float(np.mean(s1)), 4),
                      "gated_bon5_te_heldout": round(float(np.mean(g5)), 4)})
    (P0 / "P0_6_THRESHOLD_SWEEP.json").write_text(json.dumps(sweep, indent=2))

    # ---------- P0.6b rater packet ----------
    cases = [json.loads(l) for l in open(AMBIG)]
    # blind: deterministic hash order, hide ratios/labels from the response sheet
    for c in cases:
        c["_blind"] = hashlib.md5(f"{c['prompt_id']}_{c['candidate_index']}".encode()).hexdigest()[:10]
    cases.sort(key=lambda c: c["_blind"])
    audio_of = {}
    for k, r in recs.items():
        audio_of[k] = r.get("audio_path")
    pk = REPO / "orbit-research/adsr_phase2_20260604/phase0/rater_packet"
    pk.mkdir(parents=True, exist_ok=True)
    with (pk / "cases_blinded.jsonl").open("w") as fh, \
         (pk / "response_sheet.csv").open("w") as cs, \
         (pk / "audio_manifest.csv").open("w") as am:
        cs.write("case_id,rater_initials,vocals_present(0/1/unsure),comment\n")
        am.write("case_id,audio_path\n")
        for c in cases:
            key = (c["prompt_id"], c["candidate_index"])
            fh.write(json.dumps({"case_id": c["_blind"], "audio_path": audio_of.get(key),
                                 "_internal": {"prompt_id": c["prompt_id"],
                                               "candidate_index": c["candidate_index"],
                                               "reason": c.get("reason")}}) + "\n")
            cs.write(f"{c['_blind']},,,\n")
            am.write(f"{c['_blind']},{audio_of.get(key)}\n")
    (pk / "INSTRUCTIONS.md").write_text(
        "# Vocal-presence adjudication — instructions for raters\n\n"
        f"{len(cases)} short music clips (manifest: audio_manifest.csv; paths relative to the repo root).\n"
        "For each case, listen (headphones recommended) and answer ONE question on the response sheet:\n\n"
        "**Are there human vocals present in this clip?**\n"
        "- `1` = yes — any audible human singing/voice (incl. wordless vocals, chants, vocal chops)\n"
        "- `0` = no — purely instrumental\n"
        "- `unsure` = genuinely cannot tell\n\n"
        "Do not consider lyric intelligibility or quality — presence only. Work independently; "
        "do not discuss cases with other raters. Each case is assigned to 2 raters; disagreements "
        "go to a third tiebreak rater.\n\nReturn the filled `response_sheet.csv` (one row per case, "
        "your initials in column 2).\n")
    print(json.dumps({"P0.5": {k: v for k, v in p05.items() if k != "ge6_qualitative_table"},
                      "sweep_ends": [sweep[0], sweep[-1]],
                      "packet_cases": len(cases)}, indent=2, default=str))


if __name__ == "__main__":
    main()
