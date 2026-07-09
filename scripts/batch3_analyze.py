#!/usr/bin/env python
"""Batch-3 FROZEN analysis (ANALYSIS_PLAN.md implementation). Runs BLINDED by default
(arm labels permuted with a session key); --unblind reveals true arm labels (only after the
Codex results audit).

Outputs (blinded or unblinded per flag):
  batch3/ADSR_ONLINE_COMPREHENSIVE_RESULTS.{json,md}
  batch3/ADSR_ONLINE_AXIS_BREAKDOWN.csv  batch3/ADSR_ONLINE_TYPE_RISK_BREAKDOWN.csv
  batch3/ADSR_ONLINE_COST_ACCOUNTING.md
"""
from __future__ import annotations
import argparse, csv, glob, json, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
D = B3 / "online_run"
BUDGETS = {1: 168, 2: 168, 3: 168, 4: 168, 6: 168, 7: 240, 8: 120}
CHECKPOINTS = [30, 60, 90, 120, 150, 168]
NBOOT = 10000
rng = np.random.RandomState(20260612)


def load():
    att, sel = defaultdict(list), {}
    for f in glob.glob(str(D / "ledger_w*.jsonl")):
        for l in open(f):
            d = json.loads(l)
            k = (d["prompt_id"], d["arm"], d["rep"])
            if d.get("type") == "unit_selection":
                sel[k] = d
            else:
                att[k].append(d)
    for k in att:
        att[k].sort(key=lambda x: x["attempt"])
    strata = {json.loads(l)["prompt_id"]: json.loads(l)
              for l in open(B3 / "batch3_selected_prompts_256.jsonl")}
    e2 = {json.loads(l)["prompt_id"] for l in open(B3 / "E2_TAIL_SUBGROUP.jsonl")}
    return att, sel, strata, e2


def selected_candidate(rows):
    """ANALYSIS selection = gated best final common (mirrors harness keeps)."""
    comp = [r for r in rows if r.get("completed")]
    if not comp:
        return None
    passers = [r for r in comp if r.get("gate_pass")]
    pool = passers if passers else comp
    return max(pool, key=lambda r: r.get("final_common_robust_lcb") or -1e9)


def paired_boot(diffs):
    d = np.asarray(diffs, float)
    bs = [d[rng.choice(len(d), len(d), True)].mean() for _ in range(NBOOT)]
    return round(float(d.mean()), 4), [round(float(np.percentile(bs, 2.5)), 4),
                                       round(float(np.percentile(bs, 97.5)), 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unblind", action="store_true")
    args = ap.parse_args()
    att, sel, strata, e2 = load()
    arms = sorted({k[1] for k in att})
    if args.unblind:
        label = {a: f"arm{a}" for a in arms}
    else:
        key = hashlib.md5(b"batch3-blind-20260612").hexdigest()
        perm = sorted(arms, key=lambda a: hashlib.md5(f"{key}{a}".encode()).hexdigest())
        label = {a: f"ARM_{chr(65+i)}" for i, a in enumerate(perm)}

    # ---------------- PRIMARY: restart2+ per-draw clean rate, arm6 vs arm4, E2 subgroup ----------------
    def r2_cleanrate(pid, arm):
        vals = []
        for (p, a, rep), rows in att.items():
            if p != pid or a != arm:
                continue
            aborts = 0
            for r in rows:
                if r.get("aborted"):
                    aborts += 1
                elif r.get("completed") and aborts >= 2:
                    vals.append(r["gate_pass"])
        return vals
    prim_d, prim_dir = [], {"vocal": [], "instrumental": []}
    n_contrib = 0
    for pid in e2:
        v4, v6 = r2_cleanrate(pid, 4), r2_cleanrate(pid, 6)
        if v4 and v6:
            d = float(np.mean(v6) - np.mean(v4))
            prim_d.append(d); n_contrib += 1
            prim_dir[strata[pid]["vocal_stratum"]].append(d)
    prim_est, prim_ci = paired_boot(prim_d) if prim_d else (None, None)
    primary = {"endpoint": "restart2+ per-draw clean rate, arm6-arm4, E2 tail n=32",
               "n_prompts_contributing": n_contrib, "estimate": prim_est, "ci95": prim_ci,
               "criterion": ">=+0.15 and CI>0",
               "pass": bool(prim_est is not None and prim_est >= 0.15 and prim_ci[0] > 0),
               "by_direction": {s: round(float(np.mean(v)), 4) if v else None
                                for s, v in prim_dir.items()}}

    # ---------------- SECONDARY: E2a full-trajectory per-draw clean rate ----------------
    def all_cleanrate(pid, arm):
        vals = []
        for (p, a, rep), rows in att.items():
            if p == pid and a == arm:
                vals += [r["gate_pass"] for r in rows if r.get("completed")]
        return vals
    sec_d = []
    for pid in e2:
        v4, v6 = all_cleanrate(pid, 4), all_cleanrate(pid, 6)
        if v4 and v6:
            sec_d.append(float(np.mean(v6) - np.mean(v4)))
    sec_est, sec_ci = paired_boot(sec_d) if sec_d else (None, None)
    secondary = {"endpoint": "E2a full per-draw clean rate (Bonferroni)", "estimate": sec_est,
                 "ci95": sec_ci, "criterion": ">=+0.15 and CI>0 (alpha=0.025)",
                 "pass": bool(sec_est is not None and sec_est >= 0.15 and sec_ci[0] > 0)}

    # ---------------- DESCRIPTIVE: yield-vs-compute curves + axis deltas + type error ----------------
    n_v = sum(1 for p in strata.values() if p["vocal_stratum"] == "vocal")
    n_i = len(strata) - n_v
    w_of = {p: ((316 / 512) / n_v if s["vocal_stratum"] == "vocal" else (196 / 512) / n_i)
            for p, s in strata.items()}
    curves, sel_axis, te_rates = {}, {}, {}
    for arm in arms:
        ys = {c: [] for c in CHECKPOINTS}
        axis_vals = defaultdict(list); te = []
        ws = []
        per_prompt = defaultdict(list)
        for (p, a, rep), rows in att.items():
            if a != arm:
                continue
            per_prompt[p].append(rows)
        for p, units in per_prompt.items():
            ws.append(w_of[p])
            for c in CHECKPOINTS:
                yy = []
                for rows in units:
                    spent = y = 0
                    for r in rows:
                        if spent + r["cost"] > c:
                            break
                        spent += r["cost"]
                        if r.get("completed") and r.get("gate_pass"):
                            y += 1
                    yy.append(y)
                ys[c].append(float(np.mean(yy)))
            sels = [selected_candidate(rows) for rows in units]
            sels = [s for s in sels if s]
            if sels:
                te.append(float(np.mean([1 - s["gate_pass"] for s in sels])))
                for ax in ("final_common_robust_lcb", "final_semantic_fit",
                           "final_aesthetic_pq", "final_lyric_intelligibility"):
                    vv = [s.get(ax) for s in sels if s.get(ax) is not None]
                    if ax == "final_lyric_intelligibility":
                        if strata[p]["vocal_stratum"] != "vocal" or strata[p]["language"] != "en":
                            continue
                    if vv:
                        axis_vals[ax].append(float(np.mean(vv)))
        wsa = np.array(ws)
        curves[label[arm]] = {str(c): round(float((np.array(ys[c]) * wsa).sum() / wsa.sum()), 4)
                              for c in CHECKPOINTS}
        te_rates[label[arm]] = round(float((np.array(te) * wsa[:len(te)]).sum() / wsa[:len(te)].sum()), 4) if te else None
        sel_axis[label[arm]] = {ax: round(float(np.mean(v)), 4) for ax, v in axis_vals.items()}

    # ---------------- cost accounting ----------------
    cost = {}
    for arm in arms:
        spent, probes, aborts, comps, wall, oh = [], 0, 0, 0, 0.0, 0.0
        for (p, a, rep), rows in att.items():
            if a != arm:
                continue
            spent.append(sum(r["cost"] for r in rows))
            for r in rows:
                probes += int(bool(r.get("probed"))); aborts += int(bool(r.get("aborted")))
                comps += int(bool(r.get("completed"))); wall += r.get("wall_s", 0)
                oh += r.get("probe_overhead_s", 0)
        cost[label[arm]] = {"mean_nominal_steps": round(float(np.mean(spent)), 1),
                            "budget": BUDGETS[arm], "n_units": len(spent),
                            "probes": probes, "aborts": aborts, "completions": comps,
                            "gpu_h_wall": round(wall / 3600, 1),
                            "probe_overhead_h": round(oh / 3600, 2),
                            "nominal_vs_budget_dev": round(float(np.mean(spent)) / BUDGETS[arm] - 1, 3)}

    out = {"blinded": not args.unblind, "primary": primary, "secondary": secondary,
           "selected_output_type_error": te_rates, "yield_vs_compute": curves,
           "selected_axis_means": sel_axis, "cost_accounting": cost,
           "n_units_total": len(att), "n_prompts": len({k[0] for k in att})}
    tag = "" if args.unblind else "_BLINDED"
    (B3 / f"ADSR_ONLINE_COMPREHENSIVE_RESULTS{tag}.json").write_text(json.dumps(out, indent=2))
    with (B3 / "ADSR_ONLINE_AXIS_BREAKDOWN.csv").open("w", newline="") as f:
        wcsv = csv.writer(f); wcsv.writerow(["arm", "axis", "mean"])
        for a, d in sel_axis.items():
            for ax, v in d.items():
                wcsv.writerow([a, ax, v])
    with (B3 / "ADSR_ONLINE_TYPE_RISK_BREAKDOWN.csv").open("w", newline="") as f:
        wcsv = csv.writer(f); wcsv.writerow(["arm", "selected_type_error"])
        for a, v in te_rates.items():
            wcsv.writerow([a, v])
    (B3 / "ADSR_ONLINE_COST_ACCOUNTING.md").write_text(
        "# Batch-3 cost accounting\n\n```json\n" + json.dumps(cost, indent=2) + "\n```\n")
    print(json.dumps(out, indent=2)[:4000])


if __name__ == "__main__":
    main()
