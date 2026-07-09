#!/usr/bin/env python
"""Batch 2 Stage 4b — σ-decision compute/type-error FRONTIER (addendum, runs on the secured an22).

Does the EVPD-aware-selection type-error win hold at EARLIER, CHEAPER σ decisions (σ0.9/σ0.8),
not just σ0.7? Sharpens the pilot's σ choice. Per-σ: 8 cands to σ (cost N*steps_σ) + continue 4 to
final; common_restart ranks by early_σ common; adsr_evpd_select uses the σ-specific EVPD model
(best-on-val) for type-filter + EVPD-aware output. Held-out, out-of-fold. Output: ADSR_SIGMA_FRONTIER.{json,md}
"""
from __future__ import annotations
import glob, json, statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
THR_LABEL = 0.179
STEPS = {"0.9": 7.0, "0.8": 12.0, "0.7": 16.0}
FULL = 30.0
K = 4


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
    frontier = []
    for sk in ["0.9", "0.8", "0.7"]:
        pred = {}
        pf = P2 / "batch2" / f"evpd_test_pred_s{sk}.jsonl"
        if not pf.exists():
            continue
        for l in open(pf):
            d = json.loads(l); pred[(d["prompt_id"], d["candidate_index"])] = d
        by_p = defaultdict(list)
        for k in pred:
            r, L = recs[k], lab[k]
            req = int(r.get("vocal_stratum") == "vocal")
            by_p[k[0]].append({"ci": k[1], "req": req,
                               "present": int((L["vocal_energy_ratio"] >= THR_LABEL) and not L.get("near_silent")),
                               "early_common": r.get(f"early_{sk}_common_robust_lcb"),
                               "final_common": r.get("final_common_robust_lcb"),
                               "evpd_mismatch": int(pred[k]["evpd_pred_present"] != req)})
        by_p = {p: g for p, g in by_p.items() if len(g) == 8}
        for g in by_p.values():
            for x in g:
                x["type_error"] = int(x["present"] != x["req"])
        comp = (8 * STEPS[sk] + K * (FULL - STEPS[sk])) / (8 * FULL)

        def sel_te(policy):
            te = 0
            for g in by_p.values():
                gg = sorted(g, key=lambda x: (x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)
                if policy == "common":
                    cont = gg[:K]
                    sel = max(cont, key=lambda x: x["final_common"])
                else:  # adsr_evpd_select
                    non = [x for x in gg if not x["evpd_mismatch"]]; mis = [x for x in gg if x["evpd_mismatch"]]
                    cont = (non + mis)[:K]
                    matches = [x for x in cont if not x["evpd_mismatch"]]
                    sel = max(matches if matches else cont, key=lambda x: x["final_common"])
                te += sel["type_error"]
            return round(te / len(by_p), 4)
        ct, at = sel_te("common"), sel_te("adsr_evpd_select")
        frontier.append({"decision_sigma": sk, "compute_fraction": round(comp, 4),
                         "evpd_model": next(iter(pred.values()))["evpd_model"],
                         "common_restart_type_error": ct, "adsr_evpd_select_type_error": at,
                         "abs_reduction": round(ct - at, 4),
                         "rel_reduction": round((ct - at) / ct, 4) if ct else None, "n_prompts": len(by_p)})
    out = {"frontier": frontier,
           "read": "Earlier σ = cheaper compute but weaker EVPD. The pilot should use the EARLIEST σ at which the type-error reduction still holds."}
    (P2 / "ADSR_SIGMA_FRONTIER.json").write_text(json.dumps(out, indent=2))
    md = ["# ADSR σ-decision compute/type-error frontier (Batch 2 addendum)", "",
          "| decision σ | compute | common_restart TE | adsr_evpd_select TE | abs Δ | rel Δ |",
          "|---|---|---|---|---|---|"]
    for r in frontier:
        md.append(f"| {r['decision_sigma']} | {r['compute_fraction']} | {r['common_restart_type_error']} | "
                  f"{r['adsr_evpd_select_type_error']} | {r['abs_reduction']} | {r['rel_reduction']} |")
    md += ["", out["read"]]
    (P2 / "ADSR_SIGMA_FRONTIER.md").write_text("\n".join(md))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
