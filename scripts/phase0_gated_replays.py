#!/usr/bin/env python
"""P0.1–P0.3 — gated-frontier replays on held_out (the paper's money-figure backbone).

Gate = final Demucs type check (free, deployable): selection restricted to gate-passing
completions (best final common among passers); if none pass, output = best final common
(a violation). All on held_out (256 prompts), real seed order, prompt-level bootstrap CIs.

P0.1  Truncated BoN-k + final gate (k=4,5,6,8; real seed-order truncation) + held_out floor
      + per-stratum. BoN-5 is the 0.70-budget-matched baseline (5x30=150 of 168 steps).
P0.2  Oracle decomposition at σ0.8: EVPD vs oracle detector, with/without the k=4 structural
      constraint → splits the selection-policy gap into detector error vs policy structure.
P0.3  Final gate added to every Batch-2 σ0.8/σ0.7-style policy → do selection differences
      collapse?

Outputs → orbit-research/adsr_phase2_20260604/phase0/P0_{1,2,3}_*.{json,md}
"""
from __future__ import annotations
import glob, json, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
EVPD08 = REPO / "orbit-research/adsr_phase2_20260604/batch2/evpd_test_pred_s0.8.jsonl"
P0 = REPO / "orbit-research/adsr_phase2_20260604/phase0"
THR = VOCAL_PRESENCE_THRESHOLD
NBOOT = 2000
RNG = np.random.RandomState(20260610)


def load_heldout():
    recs = {}
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            r = json.loads(l)
            if r.get("split") == "held_out":
                recs[(r["prompt_id"], r["candidate_index"])] = r
    lab = {}
    for l in open(RAW):
        r = json.loads(l)
        if r.get("ok"):
            lab[(r["prompt_id"], r["candidate_index"])] = r
    evpd = {}
    for l in open(EVPD08):
        d = json.loads(l); evpd[(d["prompt_id"], d["candidate_index"])] = d
    by_p = defaultdict(list)
    for k, r in recs.items():
        L = lab[k]
        present = int((L["vocal_energy_ratio"] >= THR) and not L.get("near_silent"))
        req = int(r.get("vocal_stratum") == "vocal")
        by_p[k[0]].append({
            "ci": k[1], "present": present, "req": req, "clean": int(present == req),
            "vs": r.get("vocal_stratum"), "lang": r.get("language"),
            "final": r.get("final_common_robust_lcb"),
            "early08": r.get("early_0.8_common_robust_lcb"),
            "evpd_mismatch": (int(evpd[k]["evpd_pred_present"] != req) if k in evpd else None),
        })
    by_p = {p: sorted(g, key=lambda x: x["ci"]) for p, g in by_p.items() if len(g) == 8}
    return by_p


def gated_select(cands):
    """Best final common among gate-passers; violating fallback if none pass."""
    passers = [c for c in cands if c["clean"]]
    pool = passers if passers else cands
    sel = max(pool, key=lambda c: c["final"])
    return sel, int(not passers)          # (selected, violated)


def boot_ci(per_prompt_vals):
    arr = np.asarray(per_prompt_vals, float)
    bs = [arr[RNG.choice(len(arr), len(arr), True)].mean() for _ in range(NBOOT)]
    return [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]


def eval_policy(by_p, completed_fn, oracle_best):
    """completed_fn(g) -> list of candidates that reach final. Returns gated metrics."""
    viols, commons, strata_v = [], [], defaultdict(list)
    for p, g in by_p.items():
        comp = completed_fn(g)
        sel, v = gated_select(comp)
        viols.append(v); commons.append(sel["final"])
        strata_v[g[0]["vs"]].append(v)
    out = {"gated_type_error": round(float(np.mean(viols)), 4),
           "gated_type_error_ci95": boot_ci(viols),
           "mean_selected_common": round(float(np.mean(commons)), 4),
           "reward_fraction_vs_bon8_oracle": round(float(np.mean(commons)) / oracle_best, 4),
           "per_stratum_type_error": {s: round(float(np.mean(v)), 4) for s, v in strata_v.items()},
           "n_prompts": len(viols)}
    return out


def main():
    by_p = load_heldout()
    P0.mkdir(parents=True, exist_ok=True)
    oracle_best = float(np.mean([max(c["final"] for c in g) for g in by_p.values()]))

    # ---------------- P0.1 gated BoN-k frontier (real seed order) ----------------
    p01 = {"held_out_floor_all8_fail": round(float(np.mean(
        [int(not any(c["clean"] for c in g)) for g in by_p.values()])), 4)}
    frontier = {}
    for k in (4, 5, 6, 8):
        frontier[f"bon{k}_gated"] = {"compute_fraction": k / 8,
                                     **eval_policy(by_p, lambda g, k=k: g[:k], oracle_best)}
    p01["frontier"] = frontier
    p01["note"] = ("real seed-order truncation (candidates 0..k-1); BoN-5 = 0.70-budget-matched "
                   "baseline; floor = held_out prompts with zero gate-passers among all 8")
    (P0 / "P0_1_GATED_FRONTIER.json").write_text(json.dumps(p01, indent=2))

    # ---------------- P0.2 oracle decomposition at σ0.8 (k=4 policies) ----------------
    def cont_evpd(g):       # Batch-2 adsr_evpd continued-set, σ0.8 EVPD
        non = sorted([c for c in g if not c["evpd_mismatch"]],
                     key=lambda c: c["early08"] if c["early08"] is not None else -1e9, reverse=True)
        mis = sorted([c for c in g if c["evpd_mismatch"]],
                     key=lambda c: c["early08"] if c["early08"] is not None else -1e9, reverse=True)
        return (non + mis)[:4]

    def cont_oracle_k4(g):  # oracle detector, same k=4 structure
        non = sorted([c for c in g if c["clean"]],
                     key=lambda c: c["early08"] if c["early08"] is not None else -1e9, reverse=True)
        mis = sorted([c for c in g if not c["clean"]],
                     key=lambda c: c["early08"] if c["early08"] is not None else -1e9, reverse=True)
        return (non + mis)[:4]

    def cont_oracle_unconstrained(g):  # continue ALL truly-clean (no k cap); fallback top-4
        clean = [c for c in g if c["clean"]]
        return clean if clean else cont_oracle_k4(g)

    def ungated_te(by_p, cont_fn, select_evpd_guard):
        v = []
        for p, g in by_p.items():
            cont = cont_fn(g)
            if select_evpd_guard:   # Batch-2 adsr_evpd_select output guard
                key = "evpd_mismatch" if select_evpd_guard == "evpd" else None
                matches = ([c for c in cont if not c["evpd_mismatch"]] if key
                           else [c for c in cont if c["clean"]])
                pool = matches if matches else cont
            else:
                pool = cont
            sel = max(pool, key=lambda c: c["final"])
            v.append(int(sel["present"] != sel["req"]))
        return round(float(np.mean(v)), 4)

    p02 = {
        "ungated_selected_type_error": {
            "evpd_k4_select (Batch-2 σ0.8 repro)": ungated_te(by_p, cont_evpd, "evpd"),
            "oracle_k4_select": ungated_te(by_p, cont_oracle_k4, "oracle"),
            "oracle_unconstrained": ungated_te(by_p, cont_oracle_unconstrained, "oracle"),
        },
        "gated_selected_type_error": {
            "evpd_k4": eval_policy(by_p, cont_evpd, oracle_best)["gated_type_error"],
            "oracle_k4": eval_policy(by_p, cont_oracle_k4, oracle_best)["gated_type_error"],
            "oracle_unconstrained": eval_policy(by_p, cont_oracle_unconstrained, oracle_best)["gated_type_error"],
        },
        "note": ("detector-error contribution = evpd_k4 − oracle_k4; structure contribution = "
                 "oracle_k4 − oracle_unconstrained (all σ0.8-decision, held_out)")}
    (P0 / "P0_2_ORACLE_DECOMP.json").write_text(json.dumps(p02, indent=2))

    # ---------------- P0.3 gated re-sim of Batch-2 policy set (σ0.8 decision) ----------------
    rng = np.random.RandomState(7)
    def cont_random(g):
        idx = rng.choice(8, 4, replace=False)
        return [g[i] for i in idx]
    def cont_common(g):
        return sorted(g, key=lambda c: c["early08"] if c["early08"] is not None else -1e9,
                      reverse=True)[:4]
    policies = {"full_bon8": lambda g: g, "bon4_first4": lambda g: g[:4],
                "random_keep4": cont_random, "common_restart": cont_common,
                "adsr_evpd": cont_evpd}
    p03 = {name: eval_policy(by_p, fn, oracle_best) for name, fn in policies.items()}
    p03["_note"] = ("every policy now selects via the final gate; compute: full_bon8=1.0, "
                    "bon4=0.5, σ0.8-decision keep-4 = 0.700")
    (P0 / "P0_3_GATED_RESIM.json").write_text(json.dumps(p03, indent=2))

    # ---------------- combined markdown ----------------
    md = ["# P0.1–P0.3 Gated replays (held_out, n=%d)" % len(by_p), "",
          f"**Held_out all-8-fail floor: {p01['held_out_floor_all8_fail']}**", "",
          "## P0.1 Gated BoN-k frontier (real seed order)", "",
          "| policy | compute | gated type-error [CI95] | reward_frac |", "|---|---|---|---|"]
    for k, r in frontier.items():
        md.append(f"| {k} | {r['compute_fraction']} | {r['gated_type_error']} {r['gated_type_error_ci95']} | "
                  f"{r['reward_fraction_vs_bon8_oracle']} |")
    md += ["", "## P0.2 Oracle decomposition (σ0.8, ungated selected type-error)", "",
           "```json", json.dumps(p02["ungated_selected_type_error"], indent=2), "```",
           "", "## P0.3 Gated re-sim of Batch-2 policies", "",
           "| policy | gated type-error [CI95] | reward_frac |", "|---|---|---|"]
    for name in policies:
        r = p03[name]
        md.append(f"| {name} | {r['gated_type_error']} {r['gated_type_error_ci95']} | "
                  f"{r['reward_fraction_vs_bon8_oracle']} |")
    (P0 / "P0_123_GATED_REPLAYS.md").write_text("\n".join(md))
    print(json.dumps({"P0.1_floor": p01["held_out_floor_all8_fail"],
                      "P0.1_frontier": {k: (v["compute_fraction"], v["gated_type_error"])
                                        for k, v in frontier.items()},
                      "P0.2": p02["ungated_selected_type_error"],
                      "P0.3": {k: v["gated_type_error"] for k, v in p03.items() if not k.startswith("_")}},
                     indent=2))


if __name__ == "__main__":
    main()
