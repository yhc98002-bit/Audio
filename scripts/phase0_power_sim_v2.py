#!/usr/bin/env python
"""P0.7-v2 — power simulation for REDESIGNED endpoints (after v1 showed the proposed E1/E2
are miscalibrated: E1 true effect ~+1%, E2 saturates at 0.88 ceiling).

Candidate endpoints simulated here (same calibrated world as v1):
  E1a steps-to-first-clean: mean steps until first gate-passing completion (censored at 168),
      arm4 vs arm1; support = >=15% relative reduction, CI95 > 0.
  E1b budget-sweep yield: clean yield at a 90-step checkpoint (tight budget, where reallocation
      bites), arm4 vs arm1; support = >=+15% relative, CI > 0.
  E2a per-draw clean rate on the n=32 tail subgroup: completions' clean fraction, arm6 vs arm4;
      support = >=+15pp absolute, CI > 0. (Non-saturating; directly measures the intervention.)
  E2b any-clean at the 90-step checkpoint on the subgroup (pre-saturation), arm6 vs arm4, >=+20pp.
--delta = arm-6 intervention effect on clean propensity (from RESPAWN_LADDER once measured).
"""
from __future__ import annotations
import argparse, glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

REPO = Path(__file__).resolve().parent.parent
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0"
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
THR = VOCAL_PRESENCE_THRESHOLD
BUDGET, PROBE, CONT, FULL = 168, 12, 18, 30
MAX_ABORT = 6
R = 2
CHECK = 90
rng = np.random.RandomState(20260611)

import importlib.util
spec = importlib.util.spec_from_file_location("ps1", REPO / "scripts/phase0_power_sim.py")
ps1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(ps1)


def sim_traces(qp, tpr, fpr, n_rep, delta=0.0):
    """Per replicate: list of (cost, completed, clean) attempt records (arm-4/6 mechanics)."""
    out = []
    for _ in range(n_rep):
        budget, aborts, qcur, tr = BUDGET, 0, qp, []
        while budget >= PROBE + CONT or (budget >= PROBE and aborts < MAX_ABORT):
            clean = rng.rand() < qcur
            flag = rng.rand() < (fpr if clean else tpr)
            if flag and aborts < MAX_ABORT and budget >= PROBE:
                budget -= PROBE; aborts += 1; tr.append((PROBE, 0, 0))
                if delta > 0:
                    qcur = min(1.0, qp + delta)
                continue
            if budget >= PROBE + CONT:
                budget -= PROBE + CONT; tr.append((FULL, 1, int(clean)))
            else:
                break
        out.append(tr)
    return out


def sim_bon_traces(qp, n_rep, k=None):
    out = []
    for _ in range(n_rep):
        n = k if k else BUDGET // FULL
        tr = [(FULL, 1, int(rng.rand() < qp)) for _ in range(n)]
        out.append(tr)
    return out


def ep_steps_to_first_clean(tr):
    c = 0
    for cost, comp, clean in tr:
        c += cost
        if clean:
            return c
    return BUDGET  # censored


def ep_yield_at(tr, checkpoint):
    c = y = 0
    for cost, comp, clean in tr:
        if c + cost > checkpoint:
            break
        c += cost; y += clean
    return y


def ep_per_draw_clean(tr):
    comps = [(clean) for cost, comp, clean in tr if comp]
    return (np.mean(comps) if comps else np.nan)


def ep_any_clean_at(tr, checkpoint):
    return int(ep_yield_at(tr, checkpoint) > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", type=float, default=None,
                    help="arm-6 intervention effect; default = read RESPAWN_LADDER screen delta")
    ap.add_argument("--nsim", type=int, default=400)
    args = ap.parse_args()
    delta = args.delta
    if delta is None:
        lad = json.loads((B3 / "RESPAWN_LADDER.json").read_text())
        ds = []
        for direction, d in lad["screen_summary"].items():
            base = d["B"]["clean_rate"]
            best = max(v["clean_rate"] for c, v in d.items() if c != "B")
            ds.append(best - base)
        delta = float(np.mean(ds))
        print(f"measured ladder delta = {delta:.3f}")
    q, strat, rates, e2 = ps1.calibrate()
    pids = sorted(q)
    n_v = sum(1 for p in pids if strat[p] == "vocal"); n_i = len(pids) - n_v
    w = np.array([((316 / 512) / n_v if strat[p] == "vocal" else (196 / 512) / n_i) for p in pids])

    res = defaultdict(int); eff = defaultdict(list)
    for sim in range(args.nsim):
        s1 = np.zeros(len(pids)); s4 = np.zeros(len(pids))
        y1c = np.zeros(len(pids)); y4c = np.zeros(len(pids))
        for j, p in enumerate(pids):
            tpr, fpr = rates[strat[p]]["TPR"], rates[strat[p]]["FPR"]
            t1 = sim_bon_traces(q[p], R); t4 = sim_traces(q[p], tpr, fpr, R)
            s1[j] = np.mean([ep_steps_to_first_clean(t) for t in t1])
            s4[j] = np.mean([ep_steps_to_first_clean(t) for t in t4])
            y1c[j] = np.mean([ep_yield_at(t, CHECK) for t in t1])
            y4c[j] = np.mean([ep_yield_at(t, CHECK) for t in t4])
        # E1a: relative reduction in stratified mean steps-to-first-clean
        rel = 1 - float((s4 * w).sum() / max((s1 * w).sum(), 1e-9))
        eff["E1a"].append(rel)
        bs = []
        for _ in range(400):
            idx = rng.choice(len(pids), len(pids), True)
            bs.append(1 - float((s4[idx] * w[idx]).sum() / max((s1[idx] * w[idx]).sum(), 1e-9)))
        res["E1a"] += int(rel >= 0.15 and np.percentile(bs, 2.5) > 0)
        # E1b: relative yield gain at 90-step checkpoint
        relb = float((y4c * w).sum() / max((y1c * w).sum(), 1e-9) - 1)
        eff["E1b"].append(relb)
        bs = []
        for _ in range(400):
            idx = rng.choice(len(pids), len(pids), True)
            bs.append(float((y4c[idx] * w[idx]).sum() / max((y1c[idx] * w[idx]).sum(), 1e-9) - 1))
        res["E1b"] += int(relb >= 0.15 and np.percentile(bs, 2.5) > 0)
    # E2 endpoints on the subgroup
    for sim in range(args.nsim):
        d_pd = np.zeros(len(e2)); d_any = np.zeros(len(e2))
        for j, p in enumerate(e2):
            tpr, fpr = rates[strat[p]]["TPR"], rates[strat[p]]["FPR"]
            t4 = sim_traces(q[p], tpr, fpr, R); t6 = sim_traces(q[p], tpr, fpr, R, delta=delta)
            d_pd[j] = (np.nanmean([ep_per_draw_clean(t) for t in t6]) -
                       np.nanmean([ep_per_draw_clean(t) for t in t4]))
            d_any[j] = (np.mean([ep_any_clean_at(t, CHECK) for t in t6]) -
                        np.mean([ep_any_clean_at(t, CHECK) for t in t4]))
        for name, dvec, crit in (("E2a", d_pd, 0.15), ("E2b", d_any, 0.20)):
            m = float(np.nanmean(dvec))
            bs = [float(np.nanmean(dvec[rng.choice(len(dvec), len(dvec), True)]))
                  for _ in range(400)]
            res[name] += int(m >= crit and np.percentile(bs, 2.5) > 0)
            eff[name].append(m)
    out = {"delta_used": round(delta, 4),
           "expected_effects": {k: round(float(np.mean(v)), 4) for k, v in eff.items()},
           "power": {k: round(res[k] / args.nsim, 3) for k in res},
           "criteria": {"E1a": ">=15% rel reduction steps-to-first-clean, CI>0",
                        "E1b": ">=+15% rel clean-yield at 90-step checkpoint, CI>0",
                        "E2a": ">=+15pp per-draw clean rate on n=32 subgroup, CI>0",
                        "E2b": ">=+20pp any-clean at 90-step checkpoint on subgroup, CI>0"}}
    (P0 / "P0_7_POWER_SIM_V2.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
