#!/usr/bin/env python
"""P0.7 — Batch-3 power simulation, calibrated from held_out (the actual Batch-3 population).

World model per prompt p (fresh seeds): candidate clean w.p. q_p (= Batch-1 clean fraction,
beta-binomial-shrunk); σ0.8 EVPD flags a truly-violating candidate w.p. TPR_s, a clean one w.p.
FPR_s (s = prompt stratum; measured from held_out OOF predictions). Budget 168 steps.

Arm 1 (BoN-Budget+gate): 5 completions (5x30=150).
Arm 4 (ADSR+EVPD seed-only): attempts cost 12 (probe); flagged -> abort & retry (<=6 aborts);
  unflagged -> +18 to complete. Clean yield = # completed & truly clean.
Arm 6 (conditioned respawn, tail only): as arm 4 but after the 1st abort, clean propensity gets
  +delta (intervention effect; simulated over a grid — P0.8 freezes the real ladder).

E1: relative clean-yield (arm4 vs arm1), stratified to canonical mix; support = point >= +10%
    and paired-bootstrap CI95 > 0. E2: P(selected clean) on the frozen n=32 tail subgroup
    (arm6 vs arm4); support = >= +20pp, CI > 0. R=2 replicates pooled. 1000 sim worlds.

Output: orbit-research/adsr_phase2_20260604/phase0/P0_7_POWER_SIM.json
"""
from __future__ import annotations
import glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
EVPD08 = REPO / "orbit-research/adsr_phase2_20260604/batch2/evpd_test_pred_s0.8.jsonl"
E2SUB = REPO / "orbit-research/adsr_phase2_20260604/batch3/E2_TAIL_SUBGROUP.jsonl"
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0"
THR = 0.1791
BUDGET, PROBE, CONT = 168, 12, 18
MAX_ABORT = 6
R = 2
NSIM, NBOOT = 1000, 800
rng = np.random.RandomState(20260610)


def calibrate():
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            r = json.loads(l)
            if r.get("split") == "held_out":
                recs[(r["prompt_id"], r["candidate_index"])] = r
    lab = {}
    for l in open(RAW):
        d = json.loads(l)
        if d.get("ok"):
            lab[(d["prompt_id"], d["candidate_index"])] = d
    ev = {}
    for l in open(EVPD08):
        d = json.loads(l); ev[(d["prompt_id"], d["candidate_index"])] = d
    qv = defaultdict(list); strat = {}
    conf = {"vocal": [0, 0, 0, 0], "instrumental": [0, 0, 0, 0]}  # [flag&viol, viol, flag&clean, clean]
    for k, r in recs.items():
        L = lab[k]
        clean = int(int((L["vocal_energy_ratio"] >= THR) and not L.get("near_silent"))
                    == int(r.get("vocal_stratum") == "vocal"))
        qv[k[0]].append(clean)
        strat[k[0]] = r.get("vocal_stratum")
        if k in ev:
            flag = int(ev[k]["evpd_pred_present"] != int(r.get("vocal_stratum") == "vocal"))
            c = conf[r.get("vocal_stratum")]
            if clean:
                c[3] += 1; c[2] += flag
            else:
                c[1] += 1; c[0] += flag
    # beta-binomial shrinkage toward stratum fits (P0.5): vocal a=.72 b=2.69 / instr a=.41 b=1.15 — on VIOLATION rate
    ab = {"vocal": (0.7194, 2.6926), "instrumental": (0.4065, 1.1518)}
    q = {}
    for p, v in qv.items():
        a, b = ab[strat[p]]
        viol8 = 8 - sum(v)
        q[p] = 1.0 - (viol8 + a) / (8 + a + b)
    rates = {s: {"TPR": c[0] / max(c[1], 1), "FPR": c[2] / max(c[3], 1)} for s, c in conf.items()}
    e2 = [json.loads(l)["prompt_id"] for l in open(E2SUB)]
    return q, strat, rates, e2


def sim_arm(qp, tpr, fpr, n_rep, mode, delta=0.0):
    """Return clean-yield (mode 'yield') or selected-clean (mode 'sel') per replicate."""
    out = np.zeros(n_rep)
    for i in range(n_rep):
        budget, aborts, yield_, any_clean = BUDGET, 0, 0, 0
        qcur = qp
        while budget >= PROBE + CONT or (budget >= PROBE and aborts < MAX_ABORT):
            clean = rng.rand() < qcur
            flag = rng.rand() < (fpr if clean else tpr)
            if flag and aborts < MAX_ABORT and budget >= PROBE:
                budget -= PROBE; aborts += 1
                if delta > 0 and aborts >= 1:
                    qcur = min(1.0, qp + delta)
                continue
            if budget >= PROBE + CONT:
                budget -= PROBE + CONT
                if clean:
                    yield_ += 1; any_clean = 1
            else:
                break
        out[i] = yield_ if mode == "yield" else any_clean
    return out


def sim_bon(qp, k, n_rep, mode):
    draws = rng.rand(n_rep, k) < qp
    return draws.sum(1) if mode == "yield" else (draws.any(1)).astype(float)


def main():
    q, strat, rates, e2 = calibrate()
    pids = sorted(q)
    P0.mkdir(parents=True, exist_ok=True)
    # canonical-mix stratified weights (512 mix: 316 vocal / 196 instr; held_out counts may differ)
    n_v = sum(1 for p in pids if strat[p] == "vocal"); n_i = len(pids) - n_v
    w = {p: ((316 / 512) / n_v if strat[p] == "vocal" else (196 / 512) / n_i) for p in pids}

    e1_hits = 0; e1_effects = []
    e2_grid = {}
    for sim in range(NSIM):
        y1 = np.zeros(len(pids)); y4 = np.zeros(len(pids))
        for j, p in enumerate(pids):
            tpr, fpr = rates[strat[p]]["TPR"], rates[strat[p]]["FPR"]
            y1[j] = sim_bon(q[p], 5, R, "yield").mean()
            y4[j] = sim_arm(q[p], tpr, fpr, R, "yield").mean()
        wts = np.array([w[p] for p in pids])
        rel = float((y4 * wts).sum() / max((y1 * wts).sum(), 1e-9) - 1)
        e1_effects.append(rel)
        bs = []
        for _ in range(NBOOT):
            idx = rng.choice(len(pids), len(pids), True)
            bs.append(float((y4[idx] * wts[idx]).sum() / max((y1[idx] * wts[idx]).sum(), 1e-9) - 1))
        ci_lo = np.percentile(bs, 2.5)
        e1_hits += int(rel >= 0.10 and ci_lo > 0)
    e1_power = e1_hits / NSIM

    for delta in (0.10, 0.20, 0.30, 0.40):
        hits = 0
        for sim in range(300):
            d = np.zeros(len(e2))
            for j, p in enumerate(e2):
                tpr, fpr = rates[strat[p]]["TPR"], rates[strat[p]]["FPR"]
                a4 = sim_arm(q[p], tpr, fpr, R, "sel").mean()
                a6 = sim_arm(q[p], tpr, fpr, R, "sel", delta=delta).mean()
                d[j] = a6 - a4
            bs = [d[rng.choice(len(d), len(d), True)].mean() for _ in range(NBOOT)]
            hits += int(d.mean() >= 0.20 and np.percentile(bs, 2.5) > 0)
        e2_grid[f"delta={delta}"] = round(hits / 300, 3)

    out = {"calibration": {"evpd_sigma08_rates": {s: {k: round(v, 4) for k, v in r.items()}
                                                  for s, r in rates.items()},
                           "n_prompts": len(pids), "e2_subgroup_n": len(e2), "replicates_R": R},
           "E1_expected_relative_effect_mean": round(float(np.mean(e1_effects)), 4),
           "E1_power_at_frozen_criterion(>=+10%, CI>0)": round(e1_power, 3),
           "E2_power_vs_intervention_delta": e2_grid,
           "note": "world calibrated from held_out propensities (beta-binom shrunk) + OOF σ0.8 EVPD confusion; arm6 delta frozen later by P0.8"}
    (P0 / "P0_7_POWER_SIM.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
