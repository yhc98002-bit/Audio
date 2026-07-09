#!/usr/bin/env python
"""Phase-3 T2I — replicate the three music-paper signatures on SDXL presence/absence data.

S1 violations survive reward selection: constraint-violation rate of the PickScore-selected
   candidate vs pool prevalence (held_out).
S2 probe-AUC-vs-step: OWLv2 confidence on x0 previews at steps {6,10,14,16,20}/30 predicting the
   FINAL violation label — the observability curve analog.
S3 gated frontier + probe-gated restart sim: BoN-k + final-detector gate (k=2,4,6,8) vs a
   probe-gated restart policy at the best early step, matched expected compute (steps model:
   probe=capture step, full=30).
Detector decision thresholds calibrated on DEV split only; all reported numbers = held_out.
Output: t2i/T2I_SIGNATURES.{json,md}
"""
from __future__ import annotations
import glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
T2I = REPO / "orbit-research/adsr_phase2_20260604/t2i"
STEPS = [6, 10, 14, 16, 20]
FULL = 30
rng = np.random.RandomState(20260612)


def main():
    recs = []
    for f in glob.glob(str(T2I / "records_w*.jsonl")):
        for l in open(f):
            d = json.loads(l)
            if "det_final" in d:
                recs.append(d)
    prompts = {json.loads(l)["prompt_id"]: json.loads(l) for l in open(T2I / "t2i_prompts.jsonl")}
    # split is read from the CURRENT prompts file (records carry a stale confounded split field
    # from the first build — kind⊗split bug, fixed in t2i_build_prompts.py)
    for r in recs:
        r["split"] = prompts[r["prompt_id"]]["split"]
    dev = [r for r in recs if r["split"] == "dev"]
    ho = [r for r in recs if r["split"] == "held_out"]
    s_dev = np.array([r["det_final"] for r in dev])
    kind_dev = np.array([1 if r["constraint_kind"] == "presence" else 0 for r in dev])
    best_t, best_sep = 0.3, -1
    for t in np.percentile(s_dev, np.linspace(5, 95, 40)):
        # presence wants det>=t (satisfied); absence wants det<t
        sat = (s_dev >= t).astype(int)
        ok = (sat == kind_dev).mean()
        if ok > best_sep:
            best_sep, best_t = ok, float(t)
    def violated(r, t=best_t):
        det = r["det_final"] >= t
        return int(det != (r["constraint_kind"] == "presence"))
    for r in recs:
        r["viol"] = violated(r)
    prev_ho = float(np.mean([r["viol"] for r in ho]))
    by_kind = {k: round(float(np.mean([r["viol"] for r in ho if r["constraint_kind"] == k])), 4)
               for k in ("presence", "absence")}

    # ---- S1 violations survive reward selection ----
    by_p = defaultdict(list)
    for r in ho:
        by_p[r["prompt_id"]].append(r)
    sel_viol = [max(g, key=lambda r: r["pickscore"])["viol"] for g in by_p.values() if len(g) == 8]
    s1 = {"pool_violation_rate_heldout": round(prev_ho, 4), "by_kind": by_kind,
          "pickscore_top1_violation_rate": round(float(np.mean(sel_viol)), 4),
          "survives_selection": bool(np.mean(sel_viol) > 0.05),
          "n_prompts": len(sel_viol), "owlv2_final_thr_devfit": round(best_t, 4)}

    # ---- S2 probe AUC vs step ----
    from sklearn.metrics import roc_auc_score
    s2 = {}
    for st in STEPS:
        # probe score oriented toward violation: presence-viol = LOW det; absence-viol = HIGH det
        xs, ys = [], []
        for r in ho:
            p = r["det_probe"].get(str(st))
            if p is None:
                continue
            xs.append(p if r["constraint_kind"] == "absence" else -p)
            ys.append(r["viol"])
        if len(set(ys)) == 2:
            s2[f"step{st}"] = {"auc_violation": round(float(roc_auc_score(ys, xs)), 4), "n": len(ys)}

    # ---- S3 gated frontier + probe-gated restart sim ----
    s3 = {"frontier": {}}
    for k in (2, 4, 6, 8):
        v = []
        for g in by_p.values():
            if len(g) < 8:
                continue
            comp = sorted(g, key=lambda r: r["cand"])[:k]
            passers = [r for r in comp if not r["viol"]]
            v.append(int(not passers))
        s3["frontier"][f"bon{k}_gated"] = {"compute": k / 8,
                                           "type_error": round(float(np.mean(v)), 4)}
    # probe-gated restart: decide at the best probe step (by S2), abort if probe predicts violation
    best_step = max(s2, key=lambda s: s2[s]["auc_violation"])
    bs = int(best_step.replace("step", ""))
    # dev-fit probe threshold (oriented score) at balanced accuracy
    xs_d, ys_d = [], []
    for r in dev:
        p = r["det_probe"].get(str(bs))
        if p is not None:
            xs_d.append(p if r["constraint_kind"] == "absence" else -p); ys_d.append(violated(r))
    xs_d, ys_d = np.array(xs_d), np.array(ys_d)
    bt, bba = 0.0, -1
    for t in np.percentile(xs_d, np.linspace(5, 95, 40)):
        pred = (xs_d >= t).astype(int)
        tp = ((pred == 1) & (ys_d == 1)).sum(); tn = ((pred == 0) & (ys_d == 0)).sum()
        ba = (tp / max((ys_d == 1).sum(), 1) + tn / max((ys_d == 0).sum(), 1)) / 2
        if ba > bba:
            bba, bt = ba, float(t)
    budget = 8 * FULL * 0.7
    v_pol, costs = [], []
    for g in by_p.values():
        if len(g) < 8:
            continue
        g = sorted(g, key=lambda r: r["cand"])
        b = budget; comp = []
        for r in g:
            if b < FULL:
                break
            p = r["det_probe"].get(str(bs))
            sc = (p if r["constraint_kind"] == "absence" else -(p or 0)) if p is not None else None
            if sc is not None and sc >= bt and b >= bs:
                b -= bs
                continue
            b -= FULL; comp.append(r)
        passers = [r for r in comp if not r["viol"]]
        v_pol.append(int(not passers)); costs.append(budget - b)
    s3["probe_gated_restart"] = {"decision_step": bs, "compute": round(float(np.mean(costs)) / (8 * FULL), 3),
                                 "type_error": round(float(np.mean(v_pol)), 4),
                                 "probe_thr_devfit": round(bt, 4)}
    out = {"S1_violations_survive_selection": s1, "S2_probe_auc_by_step": s2,
           "S3_gated_frontier_and_restart": s3,
           "read": "music-paper signatures replicated on SDXL presence/absence constraints"}
    (T2I / "T2I_SIGNATURES.json").write_text(json.dumps(out, indent=2))
    md = ["# T2I transfer — three signatures (SDXL, 500 prompts x 8 seeds)", "",
          "```json", json.dumps(out, indent=2), "```"]
    (T2I / "T2I_SIGNATURES.md").write_text("\n".join(md))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
