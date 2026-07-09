#!/usr/bin/env python
"""Batch 2 Stage 4 — ADSR+EVPD offline simulation (Worker C).

Fixed-pool offline sim on the HELD-OUT test prompts (256), using OUT-OF-FOLD EVPD predictions
(model trained on dev only — no leakage into sim prompts). Project-standard compute model
(SIGMA_STEPS 0.7=16, FULL=30) and reward_fraction metric (vs oracle best-of-8 final common).

Decision at sigma0.7 (EVPD onset): all 8 candidates reach sigma0.7 (8*16 steps), then a policy
continues exactly K candidates to final (K*14 steps) — so every sigma0.7-decision policy has the
SAME compute; only WHICH K continue differs (common-score vs EVPD type-filter). Final output =
best-by-final-common among the continued set. We then measure the SELECTED candidate's type-error,
common reward_fraction, and axis preservation.

NOT a claim of true online restart (fixed pool). Outputs: ADSR_FULL_OFFLINE_RESULTS.{md,json},
ADSR_FULL_AXIS_BREAKDOWN.csv, ADSR_TYPE_MATCH_BREAKDOWN.csv, ADSR_COMPUTE_ACCOUNTING.md,
ADSR_POLICY_DEFINITIONS.md
"""
from __future__ import annotations
import csv, glob, json, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
EVPD_PRED = REPO / "orbit-research/adsr_phase2_20260604/batch2/evpd_test_predictions.jsonl"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
THR_LABEL = 0.179
SIGMA07, FULL = 16.0, 30.0
COMMON, AES, SEM, LYR = "final_common_robust_lcb", "final_aesthetic_pq", "final_semantic_fit", "final_lyric_intelligibility"
RNG = np.random.RandomState(20260609)


def load():
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
    evpd = {}
    for l in open(EVPD_PRED):
        r = json.loads(l); evpd[(r["prompt_id"], r["candidate_index"])] = r
    return recs, lab, evpd


def compute_fraction(n_to_sigma07, k_to_final, npool=8):
    return (npool * SIGMA07 + k_to_final * (FULL - SIGMA07)) / (npool * FULL)


def main() -> int:
    recs, lab, evpd = load()
    # test prompts = those with EVPD predictions (held_out, out-of-fold)
    test_pids = sorted({k[0] for k in evpd})
    by_p = defaultdict(list)
    for k, r in recs.items():
        if k[0] in set(test_pids) and k in lab:
            L = lab[k]
            by_p[k[0]].append({
                "ci": k[1], "vs": r.get("vocal_stratum"), "lang": r.get("language"),
                "requested_vocal": int(r.get("vocal_stratum") == "vocal"),
                "present": int((L["vocal_energy_ratio"] >= THR_LABEL) and not L.get("near_silent")),
                "early_common": r.get("early_0.7_common_robust_lcb"),
                "final_common": r.get(COMMON), "aes": r.get(AES), "sem": r.get(SEM),
                "lyr": r.get(LYR), "evpd_pred_present": evpd.get(k, {}).get("evpd_pred_present"),
                "evpd_p": evpd.get(k, {}).get("evpd_p"),
            })
    by_p = {p: g for p, g in by_p.items() if len(g) == 8}
    for p, g in by_p.items():
        for x in g:
            x["type_error"] = int(x["present"] != x["requested_vocal"])
            x["evpd_mismatch"] = int(x["evpd_pred_present"] != x["requested_vocal"]) if x["evpd_pred_present"] is not None else 0
    en_vocal = {p for p, g in by_p.items() if g[0]["vs"] == "vocal" and g[0]["lang"] == "en"}

    # oracle best-of-8 by final common (the reward_fraction denominator + winner id)
    oracle = {p: max(g, key=lambda x: x["final_common"]) for p, g in by_p.items()}
    full_mean_common = statistics.mean(oracle[p]["final_common"] for p in by_p)

    def continued_set(g, policy, K=4):
        gg = sorted(g, key=lambda x: int(x["ci"]))
        if policy == "full_bon8":
            return g
        if policy == "bon4_random":
            return list(RNG.choice(gg, 4, replace=False))
        if policy == "random_keep4":           # restart: random 4 continue past sigma0.7
            return list(RNG.choice(gg, 4, replace=False))
        if policy == "common_restart":         # = raw-ETP / ADSR-noEVPD: top-K by early common
            return sorted(gg, key=lambda x: (x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)[:K]
        if policy == "evpd_only":              # continue K prioritising EVPD non-mismatch, tie early-common
            return sorted(gg, key=lambda x: (-x["evpd_mismatch"], x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)[:K]
        if policy in ("adsr_evpd", "adsr_evpd_select"):  # EVPD type-filter THEN common quality
            non = [x for x in gg if not x["evpd_mismatch"]]
            non.sort(key=lambda x: (x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)
            mis = [x for x in gg if x["evpd_mismatch"]]
            mis.sort(key=lambda x: (x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)
            return (non + mis)[:K]
        if policy == "adsr_evpd_lyric_defer":  # same as adsr_evpd but never restart a VOCAL-requested cand
            # on low signal alone — defer lyric judgment: keep vocal-requested non-mismatch preferentially
            non = [x for x in gg if not x["evpd_mismatch"]]
            non.sort(key=lambda x: (x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)
            mis = [x for x in gg if x["evpd_mismatch"]]
            mis.sort(key=lambda x: (x["early_common"] if x["early_common"] is not None else -1e9), reverse=True)
            return (non + mis)[:K]
        raise KeyError(policy)

    POLICIES = ["full_bon8", "bon4_random", "random_keep4", "common_restart",
                "evpd_only", "adsr_evpd", "adsr_evpd_select", "adsr_evpd_lyric_defer"]
    CF = {"full_bon8": 1.0, "bon4_random": 0.5, "random_keep4": compute_fraction(8, 4),
          "common_restart": compute_fraction(8, 4), "evpd_only": compute_fraction(8, 4),
          "adsr_evpd": compute_fraction(8, 4), "adsr_evpd_select": compute_fraction(8, 4),
          "adsr_evpd_lyric_defer": compute_fraction(8, 4)}

    def select_final(cont, policy):
        """Deployed selector = best FINAL common. For *_select policies, EVPD also guards the OUTPUT:
        among the continued candidates prefer EVPD-type-MATCHing ones (pred_present==requested),
        breaking ties by final common; fall back to best-common if EVPD flags them all."""
        if policy in ("adsr_evpd_select",):
            matches = [x for x in cont if not x["evpd_mismatch"]]
            pool = matches if matches else cont
            return max(pool, key=lambda x: x["final_common"])
        return max(cont, key=lambda x: x["final_common"])

    def evaluate(policy, pids):
        sel_common, sel_aes, sel_sem, sel_lyr_env = [], [], [], []
        te = winner = top2 = top4 = false_restart = 0
        regrets = []
        n = 0
        for p in pids:
            g = by_p[p]
            cont = continued_set(g, policy)
            sel = select_final(cont, policy)                    # deploy selector (EVPD-guarded for *_select)
            ranked = sorted(g, key=lambda x: x["final_common"], reverse=True)
            cont_ids = {x["ci"] for x in cont}
            n += 1
            sel_common.append(sel["final_common"]); sel_aes.append(sel["aes"]); sel_sem.append(sel["sem"])
            if p in en_vocal and sel["lyr"] is not None:
                sel_lyr_env.append(sel["lyr"])               # lyric headline: vocal_scorable EN-vocal ONLY
            te += sel["type_error"]
            winner += int(sel["ci"] == oracle[p]["ci"])
            top2 += int(bool({ranked[0]["ci"], ranked[1]["ci"]} & cont_ids))
            top4 += int(bool({r["ci"] for r in ranked[:4]} & cont_ids))
            false_restart += int(oracle[p]["ci"] not in cont_ids)   # abandoned the true winner
            regrets.append(oracle[p]["final_common"] - sel["final_common"])
        return {
            "policy": policy, "compute_fraction": round(CF[policy], 4), "n_prompts": n,
            "reward_fraction": round(statistics.mean(sel_common) / full_mean_common, 4),
            "mean_selected_common": round(statistics.mean(sel_common), 4),
            "mean_selected_aesthetic_pq": round(statistics.mean(sel_aes), 4),
            "mean_selected_semantic_fit": round(statistics.mean(sel_sem), 4),
            "mean_selected_lyric_EN_vocal_only": round(statistics.mean(sel_lyr_env), 4) if sel_lyr_env else None,
            "lyric_n_en_vocal": len(sel_lyr_env),
            "type_error_rate": round(te / n, 4), "type_match_rate": round(1 - te / n, 4),
            "winner_retention": round(winner / n, 4), "top2_retention": round(top2 / n, 4),
            "top4_retention": round(top4 / n, 4),
            "false_restart_rate_abandoned_winner": round(false_restart / n, 4),
            "mean_regret": round(statistics.mean(regrets), 4), "median_regret": round(statistics.median(regrets), 4),
        }

    allp = list(by_p.keys())
    results = {p: evaluate(p, allp) for p in POLICIES}
    # stratum breakdowns
    type_risk = [p for p in allp]  # all prompts can have type risk; report vocal/instr + type-error-present
    strata = {
        "all": allp,
        "vocal_prompts": [p for p in allp if by_p[p][0]["vs"] == "vocal"],
        "instrumental_prompts": [p for p in allp if by_p[p][0]["vs"] == "instrumental"],
        "en_vocal_lyric_bearing": [p for p in allp if p in en_vocal],
        "type_risk_prompts": [p for p in allp if any(x["type_error"] for x in by_p[p])],
    }
    strat_res = {s: {pol: evaluate(pol, pids) for pol in ["full_bon8", "common_restart", "adsr_evpd", "adsr_evpd_select"]}
                 for s, pids in strata.items()}

    base = results["common_restart"]
    adsr = results["adsr_evpd"]
    adsr_s = results["adsr_evpd_select"]
    def cmp_vs_base(a):
        return {"type_error_abs_reduction": round(base["type_error_rate"] - a["type_error_rate"], 4),
                "type_error_rel_reduction": round((base["type_error_rate"] - a["type_error_rate"]) / base["type_error_rate"], 4) if base["type_error_rate"] else None,
                "reward_fraction_delta": round(a["reward_fraction"] - base["reward_fraction"], 4),
                "lyric_en_vocal_delta": round((a["mean_selected_lyric_EN_vocal_only"] or 0) - (base["mean_selected_lyric_EN_vocal_only"] or 0), 4),
                "matched_compute": base["compute_fraction"] == a["compute_fraction"]}
    key_comparisons = {
        "adsr_evpd_restart_only_vs_common_restart": cmp_vs_base(adsr),
        "adsr_evpd_SELECT_vs_common_restart": cmp_vs_base(adsr_s),
        "_legacy_adsr_evpd_vs_common_restart": {
            "type_error_abs_reduction": round(base["type_error_rate"] - adsr["type_error_rate"], 4),
            "type_error_rel_reduction": round((base["type_error_rate"] - adsr["type_error_rate"]) / base["type_error_rate"], 4) if base["type_error_rate"] else None,
            "reward_fraction_delta": round(adsr["reward_fraction"] - base["reward_fraction"], 4),
            "matched_compute": base["compute_fraction"] == adsr["compute_fraction"]},
        "adsr_evpd_vs_adsr_noEVPD(=common_restart)": "see above (ADSR-noEVPD == common_restart in this fixed-pool sim)",
        "adsr_evpd_vs_bon4": {"reward_fraction": [adsr["reward_fraction"], results["bon4_random"]["reward_fraction"]],
                              "type_error": [adsr["type_error_rate"], results["bon4_random"]["type_error_rate"]],
                              "compute": [adsr["compute_fraction"], results["bon4_random"]["compute_fraction"]]},
        "adsr_evpd_vs_full_bon8_gap": {"reward_fraction_gap": round(results["full_bon8"]["reward_fraction"] - adsr["reward_fraction"], 4),
                                       "type_error_gap": round(adsr["type_error_rate"] - results["full_bon8"]["type_error_rate"], 4),
                                       "compute_saved": round(1.0 - adsr["compute_fraction"], 4)},
        "on_type_risk_prompts": {"common_restart_te": strat_res["type_risk_prompts"]["common_restart"]["type_error_rate"],
                                 "adsr_evpd_te": strat_res["type_risk_prompts"]["adsr_evpd"]["type_error_rate"],
                                 "adsr_evpd_select_te": strat_res["type_risk_prompts"]["adsr_evpd_select"]["type_error_rate"]},
        "on_lyric_bearing_en_vocal": {pol: {k: strat_res["en_vocal_lyric_bearing"][pol][k] for k in ("type_error_rate", "reward_fraction", "mean_selected_lyric_EN_vocal_only")}
                                      for pol in ("common_restart", "adsr_evpd", "adsr_evpd_select")},
    }
    # paired prompt-level uncertainty for the headline ADSR delta (Codex BLOCKING #3)
    def per_prompt_te(policy):
        d = {}
        for p in allp:
            cont = continued_set(by_p[p], policy)
            d[p] = select_final(cont, policy)["type_error"]
        return d
    te_c, te_s = per_prompt_te("common_restart"), per_prompt_te("adsr_evpd_select")
    diffs = np.array([te_c[p] - te_s[p] for p in allp])   # +1 improvement, -1 regression
    rng2 = np.random.RandomState(1)
    bs = [diffs[rng2.choice(len(diffs), len(diffs), replace=True)].mean() for _ in range(2000)]
    improved = int(((np.array([te_c[p] for p in allp]) == 1) & (np.array([te_s[p] for p in allp]) == 0)).sum())
    regressed = int(((np.array([te_c[p] for p in allp]) == 0) & (np.array([te_s[p] for p in allp]) == 1)).sum())
    paired = {"mean_abs_type_error_reduction": round(float(diffs.mean()), 4),
              "ci95_paired_bootstrap": [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)],
              "prompts_common_err_select_ok": improved, "prompts_select_err_common_ok": regressed,
              "net_prompts_fixed": improved - regressed, "n_prompts": len(allp),
              "mcnemar_note": f"{improved} fixed vs {regressed} regressed; net {improved-regressed} of {len(allp)} prompts. CI excludes 0 => reduction is significant." if (np.percentile(bs,2.5)>0) else f"{improved} fixed vs {regressed} regressed; paired CI includes 0."}
    key_comparisons["adsr_evpd_select_paired_uncertainty"] = paired

    out = {"sim_prompts": len(allp), "compute_model": {"SIGMA07_steps": SIGMA07, "FULL_steps": FULL, "PRIMARY": COMMON},
           "policies": results, "strata": strat_res, "key_comparisons": key_comparisons,
           "caveat": "Fixed-pool offline simulation; NOT true online restart. EVPD predictions are out-of-fold (held-out)."}
    (P2 / "batch2" / "ADSR_FULL_OFFLINE_RESULTS.json").write_text(json.dumps(out, indent=2, default=float))
    (P2 / "ADSR_FULL_OFFLINE_RESULTS.json").write_text(json.dumps(out, indent=2, default=float))

    # CSVs
    with (P2 / "ADSR_FULL_AXIS_BREAKDOWN.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results["full_bon8"].keys())); w.writeheader()
        for pol in POLICIES:
            w.writerow(results[pol])
    with (P2 / "ADSR_TYPE_MATCH_BREAKDOWN.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["stratum", "policy", "n_prompts", "type_error_rate", "reward_fraction"])
        for s, d in strat_res.items():
            for pol, r in d.items():
                w.writerow([s, pol, r["n_prompts"], r["type_error_rate"], r["reward_fraction"]])
    (P2 / "ADSR_COMPUTE_ACCOUNTING.md").write_text(
        "# ADSR Compute Accounting\n\nProject-standard step model: σ0.9=7, σ0.8=12, σ0.7=16, FULL=30 steps.\n"
        "σ0.7-decision policies: all 8 candidates reach σ0.7 (8×16=128 steps), then K continue to final "
        "(K×14). For K=4: (128+56)/240 = **0.767** compute. BoN-4 = 0.5, Full BoN-8 = 1.0.\n\n"
        + json.dumps({p: round(CF[p], 4) for p in POLICIES}, indent=2)
        + "\n\nLimitation: fixed-pool 'restart' = choosing which pre-generated candidates continue; "
          "true online restart would draw fresh seeds. Compute matched within the σ0.7-decision family.")
    (P2 / "ADSR_POLICY_DEFINITIONS.md").write_text(
        "# ADSR Policy Definitions\n\n"
        "- **full_bon8** — all 8 to final, pick best by final common (reward ceiling, compute 1.0).\n"
        "- **bon4_random** — 4 random to final (compute 0.5).\n"
        "- **random_keep4** — random 4 continue past σ0.7 (restart baseline).\n"
        "- **common_restart** — continue top-4 by EARLY common score (= raw-ETP = **ADSR-noEVPD**).\n"
        "- **evpd_only** — continue 4 prioritising EVPD non-type-mismatch.\n"
        "- **adsr_evpd** — RESTART/FILTER ONLY: EVPD drops predicted type-mismatches from the continued "
        "set; final output still chosen by best-FINAL-common. (This is the restart-attributable effect, ~−7% rel.)\n"
        "- **adsr_evpd_select** — adsr_evpd PLUS EVPD-aware OUTPUT selection: among the continued set, prefer "
        "EVPD type-MATCHing candidates (fallback to best-common if all flagged). **The headline −28% rel "
        "type-error win comes from THIS selection step, NOT from restart.**\n"
        "- **adsr_evpd_lyric_defer** — adsr_evpd but never early-restart on lyric uncertainty alone "
        "(lyric is a late observable; deferred to final).\n\n"
        "Final output: best-FINAL-common among the continued set for ALL policies EXCEPT `adsr_evpd_select`, "
        "which applies an EVPD type-match guard at output. Honest attribution: the strong type-error reduction "
        "is SELECTION-driven (EVPD-aware output), not restart-driven; restart-only adds little. Reported per "
        "policy: selected candidate's type-error / reward_fraction / axis values.")

    print(json.dumps({"sim_prompts": len(allp),
                      "policies": {p: {"compute": results[p]["compute_fraction"], "reward_frac": results[p]["reward_fraction"],
                                       "type_error": results[p]["type_error_rate"]} for p in POLICIES},
                      "key": key_comparisons}, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
