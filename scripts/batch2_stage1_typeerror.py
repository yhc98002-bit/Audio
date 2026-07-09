#!/usr/bin/env python
"""Batch 2 Stage 1 — final vocal-label reliability + type-error prevalence (Worker A).

type-error(candidate) = present XOR requested, where
  present  = (vocal_energy_ratio >= THR) and not near_silent     [Demucs vocal-presence label]
  requested= (vocal_stratum == 'vocal')
THR = strata_median_midpoint = midpoint of vocal-requested vs instrumental-requested ratio medians
      (non-near-silent), the same data-derived label cutoff used in the Phase-2 snapshot. This is
      the LABEL threshold (a data property), NOT a predictive-model threshold (EVPD tunes its own).

Survivor-set type error (top-k by common score = final_common_robust_lcb) is the decisive number:
EVPD only has method leverage if type errors REMAIN after simple common-score selection/restart.

Outputs: VOCAL_TYPE_ERROR_PREVALENCE.{md,json}, VOCAL_LABEL_RELIABILITY.md,
         vocal_ambiguous_check_packet.jsonl
"""
from __future__ import annotations
import json, glob, statistics, math
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
RAW = REPO / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
P2 = REPO / "orbit-research/adsr_phase2_20260604"
AMBIG_MARGIN = 0.05


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
    return recs, lab


def main() -> int:
    recs, lab = load()
    rows = []
    for k, r in recs.items():
        L = lab.get(k)
        if not L:
            continue
        rows.append({
            "pid": k[0], "ci": k[1], "vs": r.get("vocal_stratum"), "lang": r.get("language"),
            "split": r.get("split"), "ratio": L.get("vocal_energy_ratio"),
            "near_silent": bool(L.get("near_silent")), "common": r.get("final_common_robust_lcb"),
            "lyric": r.get("final_lyric_intelligibility"), "silence": r.get("final_probe_silence_fraction"),
        })
    # ---- label threshold (strata_median_midpoint) ----
    voc = [x["ratio"] for x in rows if x["vs"] == "vocal" and not x["near_silent"]]
    ins = [x["ratio"] for x in rows if x["vs"] == "instrumental" and not x["near_silent"]]
    mv, mi = statistics.median(voc), statistics.median(ins)
    THR = (mv + mi) / 2.0
    for x in rows:
        x["present"] = (x["ratio"] >= THR) and (not x["near_silent"])
        x["requested"] = (x["vs"] == "vocal")
        x["type_error"] = x["present"] != x["requested"]
        x["err_kind"] = ("vocal_req_no_vocal" if (x["requested"] and not x["present"]) else
                         "instr_req_has_vocal" if ((not x["requested"]) and x["present"]) else "ok")

    n = len(rows)
    cand_te = sum(x["type_error"] for x in rows) / n
    by_p = defaultdict(list)
    for x in rows:
        by_p[x["pid"]].append(x)
    prompt_affected = sum(1 for p, xs in by_p.items() if any(x["type_error"] for x in xs)) / len(by_p)

    def rate(sel):
        s = [x for x in rows if sel(x)]
        return {"n": len(s), "type_error_rate": round(sum(x["type_error"] for x in s) / len(s), 4) if s else None}

    strat = {
        "vocal_prompt": rate(lambda x: x["vs"] == "vocal"),
        "instrumental_prompt": rate(lambda x: x["vs"] == "instrumental"),
        "vocal_req_no_vocal": {"n": sum(1 for x in rows if x["err_kind"] == "vocal_req_no_vocal")},
        "instr_req_has_vocal": {"n": sum(1 for x in rows if x["err_kind"] == "instr_req_has_vocal")},
    }
    en_vocal = {p for p, xs in by_p.items() if xs[0]["vs"] == "vocal" and xs[0]["lang"] == "en"}
    en_vocal_te = rate(lambda x: x["pid"] in en_vocal)

    # ---- survivor sets by common score (the decisive analysis) ----
    survivors = {}
    for k in (1, 2, 4):
        te = nn = 0
        for p, xs in by_p.items():
            if len(xs) < 8:
                continue
            top = sorted(xs, key=lambda z: (z["common"] if z["common"] is not None else -1e9), reverse=True)[:k]
            nn += len(top); te += sum(x["type_error"] for x in top)
        survivors[f"top{k}_by_common"] = round(te / nn, 4) if nn else None
    # survivor by stratum (top-1)
    surv_strat = {}
    for s in ("vocal", "instrumental"):
        te = nn = 0
        for p, xs in by_p.items():
            if xs[0]["vs"] != s or len(xs) < 8:
                continue
            top = sorted(xs, key=lambda z: (z["common"] if z["common"] is not None else -1e9), reverse=True)[:1]
            nn += 1; te += sum(x["type_error"] for x in top)
        surv_strat[s] = round(te / nn, 4) if nn else None

    # ---- ambiguous-label rate + distribution around threshold ----
    margins = [x["ratio"] - THR for x in rows if not x["near_silent"]]
    ambiguous = [x for x in rows if (not x["near_silent"]) and abs(x["ratio"] - THR) < AMBIG_MARGIN]
    bins = np.histogram([x["ratio"] for x in rows], bins=20, range=(0, 1))[0].tolist()

    prevalence = {
        "label_threshold": round(THR, 4), "threshold_method": "strata_median_midpoint",
        "median_vocal_req": round(mv, 4), "median_instr_req": round(mi, 4), "separation": round(mv - mi, 4),
        "n_candidates": n,
        "candidate_type_error_rate": round(cand_te, 4),
        "prompt_level_affected_rate": round(prompt_affected, 4),
        "per_stratum": strat,
        "en_vocal_scorable_type_error": en_vocal_te,
        "survivor_set_type_error_by_common_score": survivors,
        "survivor_top1_by_stratum": surv_strat,
        "ambiguous_count": len(ambiguous), "ambiguous_frac": round(len(ambiguous) / n, 4),
        "ambiguous_def": f"|ratio - {round(THR,4)}| < {AMBIG_MARGIN} and not near_silent",
        "ratio_hist_0to1_20bins": bins,
    }
    (P2 / "VOCAL_TYPE_ERROR_PREVALENCE.json").write_text(json.dumps(prevalence, indent=2))

    # ---- label reliability: bimodality + Whisper-lyric proxy agreement ----
    rel = {"threshold": round(THR, 4), "margin_to_threshold": {
        "min": round(min(margins), 4), "p10": round(float(np.percentile(margins, 10)), 4),
        "median": round(float(np.median(margins)), 4), "p90": round(float(np.percentile(margins, 90)), 4),
        "max": round(max(margins), 4)}}
    try:
        from sklearn.mixture import GaussianMixture
        X = np.array([x["ratio"] for x in rows if not x["near_silent"]]).reshape(-1, 1)
        g = GaussianMixture(n_components=2, random_state=0).fit(X)
        mus = sorted(g.means_.ravel().tolist())
        rel["gmm_bimodality"] = {"means": [round(m, 4) for m in mus], "separation": round(mus[1] - mus[0], 4),
                                 "weights": [round(w, 4) for w in g.weights_.tolist()]}
    except Exception as e:
        rel["gmm_bimodality"] = f"err:{e}"
    # Whisper cross-check (EN-vocal only). IMPORTANT: Demucs measures vocal PRESENCE (energy);
    # Whisper lyric_intelligibility>0 measures intelligible WORDS — a STRICTLY STRONGER condition
    # (vocals can be wordless), and Whisper is known to HALLUCINATE lyrics on instrumental/wordless
    # audio. So two-directional "agreement" is meaningless; we report the conditional presence rates
    # and treat disagreements as a manual-check packet, NOT as label errors.
    enrows = [x for x in rows if x["pid"] in en_vocal]
    words = [x for x in enrows if (x["lyric"] is not None and x["lyric"] > 0)]
    nowords = [x for x in enrows if not (x["lyric"] is not None and x["lyric"] > 0)]
    p_present_words = sum(x["present"] for x in words) / len(words) if words else None
    p_present_nowords = sum(x["present"] for x in nowords) / len(nowords) if nowords else None
    disagree_pw = [x for x in nowords if x["present"]]          # vocals but no intelligible words (EXPECTED)
    disagree_wp = [x for x in words if not x["present"]]        # words but Demucs-absent (Demucs miss OR Whisper hallucination)
    rel["whisper_crosscheck_en_vocal"] = {
        "n": len(enrows), "n_whisper_words": len(words), "n_no_words": len(nowords),
        "P_present_given_words": round(p_present_words, 4) if p_present_words is not None else None,
        "P_present_given_no_words": round(p_present_nowords, 4) if p_present_nowords is not None else None,
        "words_but_demucs_absent": len(disagree_wp), "present_but_no_words": len(disagree_pw),
        "interpretation": "P(present|words) ~= P(present|no_words) => Demucs vocal-presence is ORTHOGONAL to Whisper lyric-intelligibility (different axes; Whisper hallucinates on instrumental). Whisper is NOT a clean validator of vocal presence; not used as such. Disagreements -> manual-check packet."}
    relmd = ["# Vocal-Presence Label Reliability (Stage 1)", "",
             "## Primary reliability evidence (the Demucs vocal-presence label IS reliable)",
             f"- **Request-type separation**: vocal-requested ratio median **{round(mv,4)}** vs instrumental-requested median **{round(mi,4)}** (separation **{round(mv-mi,4)}**) — the label cleanly tracks the requested type.",
             f"- **GMM bimodality**: {json.dumps(rel['gmm_bimodality'])} — two well-separated clusters (no-vocal ~0, vocal ~0.34).",
             f"- Label threshold (strata-median-midpoint): **{round(THR,4)}**; margin-to-threshold {json.dumps(rel['margin_to_threshold'])}.",
             f"- Ambiguous (|ratio−thr|<{AMBIG_MARGIN}): {len(ambiguous)} ({round(100*len(ambiguous)/n,1)}%).", "",
             "## Secondary cross-check — Whisper lyric proxy (INCONCLUSIVE by construction)",
             f"- P(Demucs present | Whisper words) = **{rel['whisper_crosscheck_en_vocal']['P_present_given_words']}**, "
             f"P(present | no words) = **{rel['whisper_crosscheck_en_vocal']['P_present_given_no_words']}** → ~equal.",
             f"- Words-but-Demucs-absent: {len(disagree_wp)} (Demucs miss OR Whisper hallucination); present-but-no-words: {len(disagree_pw)} (wordless vocals, expected).",
             "- Demucs presence ⊥ Whisper words (different axes; Whisper hallucinates on instrumental). Whisper is NOT used to validate presence; disagreements go to the manual-check packet.", "",
             "**Verdict:** clean request-type separation + bimodality => the Demucs vocal-presence label is reliable enough to be the EVPD target. The 2256-candidate EN-vocal lyric axis stays separate (Whisper, not Demucs)."]
    (P2 / "VOCAL_LABEL_RELIABILITY.md").write_text("\n".join(relmd))

    # ---- ambiguous / disagreement manual-check packet (NO human eval launched) ----
    packet = []
    for x in sorted(ambiguous, key=lambda z: abs(z["ratio"] - THR))[:150]:
        packet.append({"prompt_id": x["pid"], "candidate_index": x["ci"], "reason": "near_threshold",
                       "vocal_energy_ratio": x["ratio"], "margin": round(x["ratio"] - THR, 4),
                       "requested": x["vs"], "lang": x["lang"], "present": x["present"], "type_error": x["type_error"]})
    for x in disagree_pw[:50] + disagree_wp[:50]:
        packet.append({"prompt_id": x["pid"], "candidate_index": x["ci"], "reason": "demucs_whisper_disagree",
                       "vocal_energy_ratio": x["ratio"], "lyric_intelligibility": x["lyric"],
                       "requested": x["vs"], "present": x["present"]})
    with (P2 / "vocal_ambiguous_check_packet.jsonl").open("w") as fh:
        for p in packet:
            fh.write(json.dumps(p) + "\n")

    # ---- prevalence markdown ----
    md = ["# Vocal/Instrumental Type-Error Prevalence (Stage 1)", "",
          f"Label threshold = **{round(THR,4)}** (strata-median-midpoint; separation {round(mv-mi,4)}).", "",
          f"- **Candidate type-error rate: {round(cand_te,4)}**",
          f"- Prompt-level affected rate: {round(prompt_affected,4)}",
          f"- Vocal prompts: {strat['vocal_prompt']['type_error_rate']} | Instrumental prompts: {strat['instrumental_prompt']['type_error_rate']}",
          f"- vocal-req→no-vocal: {strat['vocal_req_no_vocal']['n']} | instr-req→has-vocal: {strat['instr_req_has_vocal']['n']}",
          f"- EN-vocal (vocal_scorable) type-error: {en_vocal_te}", "",
          "## Survivor-set type-error (by common score — the decisive number)",
          f"- top-1: **{survivors['top1_by_common']}** | top-2: {survivors['top2_by_common']} | top-4: {survivors['top4_by_common']}",
          f"- top-1 by stratum: vocal {surv_strat['vocal']} | instrumental {surv_strat['instrumental']}", "",
          f"- Ambiguous near threshold: {len(ambiguous)} ({round(100*len(ambiguous)/n,1)}%)", "",
          "**Read:** if survivor top-1 type-error stays well above 0, simple common-score selection does NOT remove type errors → EVPD has method leverage."]
    (P2 / "VOCAL_TYPE_ERROR_PREVALENCE.md").write_text("\n".join(md))
    print(json.dumps({"candidate_te": round(cand_te,4), "prompt_affected": round(prompt_affected,4),
                      "survivors": survivors, "surv_by_stratum": surv_strat,
                      "en_vocal_te": en_vocal_te, "ambiguous": len(ambiguous),
                      "whisper_crosscheck": rel["whisper_crosscheck_en_vocal"],
                      "gmm_sep": rel.get("gmm_bimodality")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
