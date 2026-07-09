#!/usr/bin/env python
"""Phase 2 — counterfactual replays from the Batch-3 ledgers (offline-first, near-free).

CRN trick: every arm used the SAME seed for attempt index i of a (prompt, rep), so an outcome
unobserved in one arm (e.g., an aborted attempt) can be filled from a sibling arm that COMPLETED
the same seed (arms 1/7/8 are unprobed completions; arm 2 random). This enables bidirectional
threshold replay and hybrid-policy replay.

Studies (pre-registered in experiment_plan_current.md Phase 2):
  S1 cost-aware threshold: replay arm-4 abort decisions under a τ grid using evpd_p, outcomes
     filled via CRN siblings; report steps-per-clean vs τ (dev-free: τ grid is exploratory,
     confirmatory selection would be dev-fit — labeled exploratory).
  S2 probe-on-evidence: hybrid = run unprobed (arm-1 attempts) until first observed violation,
     then switch to arm-4 probing from the next seed; compare steps-per-clean vs pure arms.
  S3 portfolio allocation: donors (prompts whose first 2 arm-4 attempts show no flag) truncate
     at first clean completion; donated budget extends flagged-prompt sequences via CRN sibling
     completions; aggregate clean-yield at equal total budget vs fixed per-prompt.
Output: batch3/PHASE2_LEDGER_REPLAYS.{json,md}
"""
from __future__ import annotations
import glob, json
from collections import defaultdict
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
B3 = REPO / "orbit-research/adsr_phase2_20260604/batch3"
D = B3 / "online_run"
PROBE, CONT, FULL = 12, 18, 30
TAU0 = 0.728


def load():
    att = defaultdict(list)
    for f in glob.glob(str(D / "ledger_w*.jsonl")):
        for l in open(f):
            d = json.loads(l)
            if d.get("type") != "unit_selection":
                att[(d["prompt_id"], d["arm"], d["rep"])].append(d)
    for k in att:
        att[k].sort(key=lambda x: x["attempt"])
    # CRN sibling outcome map: (prompt, rep, attempt/seed-index) -> gate_pass (from any completion)
    sib = {}
    for (p, a, rep), rows in att.items():
        for r in rows:
            if r.get("completed"):
                sib.setdefault((p, rep, r["attempt"]), r["gate_pass"])
    return att, sib


def steps_per_clean(cost, clean):
    return cost / clean if clean else float("inf")


def main():
    att, sib = load()
    prompts = sorted({k[0] for k in att})
    reps = (0, 1)

    # ---------- S1 cost-aware threshold replay (arm 4) ----------
    s1 = {}
    for tau in (0.3, 0.5, 0.728, 0.85, 0.95):
        tot_c = tot_y = filled = missing = 0
        for p in prompts:
            for rep in reps:
                rows = att.get((p, 4, rep))
                if not rows:
                    continue
                budget = 168
                req = rows[0].get("requested_vocal")
                for r in rows:
                    if budget < FULL:
                        break
                    if r.get("probed") and r.get("evpd_p") is not None:
                        flag = (int(r["evpd_p"] >= tau) != req)
                    else:
                        flag = False
                    if flag:
                        budget -= PROBE; tot_c += PROBE
                        continue
                    # would complete: outcome = own if completed, else CRN sibling
                    if r.get("completed"):
                        g = r["gate_pass"]
                    else:
                        g = sib.get((p, rep, r["attempt"]))
                        if g is None:
                            missing += 1
                            continue
                        filled += 1
                    budget -= FULL; tot_c += FULL; tot_y += g
        s1[f"tau={tau}"] = {"steps_per_clean": round(steps_per_clean(tot_c, tot_y), 1),
                            "clean_yield_total": tot_y, "sibling_filled": filled,
                            "unfillable_attempts": missing}

    # ---------- S2 probe-on-evidence hybrid ----------
    def pure(arm):
        c = y = 0
        for p in prompts:
            for rep in reps:
                rows = att.get((p, arm, rep)) or []
                for r in rows:
                    c += r["cost"]
                    if r.get("completed"):
                        y += r["gate_pass"]
        return c, y
    c1, y1 = pure(1); c4, y4 = pure(4)
    ch = yh = 0
    for p in prompts:
        for rep in reps:
            r1 = att.get((p, 1, rep)) or []
            r4 = {r["attempt"]: r for r in (att.get((p, 4, rep)) or [])}
            budget = 168; switched = False; viol_seen = False
            for r in r1:
                if budget < FULL:
                    break
                if not switched:
                    ch += FULL; budget -= FULL
                    if r.get("completed"):
                        yh += r["gate_pass"]
                        if not r["gate_pass"]:
                            viol_seen = True; switched = True
                else:
                    rr = r4.get(r["attempt"])
                    if rr is None:
                        g = sib.get((p, rep, r["attempt"]))
                        if g is None:
                            continue
                        ch += FULL; budget -= FULL; yh += g
                    elif rr.get("aborted"):
                        ch += PROBE; budget -= PROBE
                    else:
                        ch += FULL; budget -= FULL
                        yh += rr["gate_pass"] if rr.get("completed") else (sib.get((p, rep, r["attempt"])) or 0)
    s2 = {"pure_bon_arm1": {"steps_per_clean": round(steps_per_clean(c1, y1), 1), "yield": y1},
          "pure_evpd_arm4": {"steps_per_clean": round(steps_per_clean(c4, y4), 1), "yield": y4},
          "hybrid_probe_on_evidence": {"steps_per_clean": round(steps_per_clean(ch, yh), 1), "yield": yh}}

    # ---------- S3 portfolio allocation ----------
    base_c = base_y = 0; saved = 0
    flagged_prompts = []
    for p in prompts:
        for rep in reps:
            rows = att.get((p, 4, rep)) or []
            flags2 = sum(1 for r in rows[:2] if r.get("aborted"))
            spent = sum(r["cost"] for r in rows)
            yld = sum(r["gate_pass"] for r in rows if r.get("completed"))
            base_c += spent; base_y += yld
            if flags2 == 0:
                # donor: truncate at first clean completion
                c = y = 0
                for r in rows:
                    c += r["cost"]
                    if r.get("completed"):
                        y += r["gate_pass"]
                        if r["gate_pass"]:
                            break
                saved += spent - c
            else:
                flagged_prompts.append((p, rep))
    # recipients: extend flagged prompts with CRN sibling completions beyond their last attempt
    extra_y = 0; budget_pool = saved
    for p, rep in flagged_prompts:
        rows = att.get((p, 4, rep)) or []
        last = rows[-1]["attempt"] if rows else -1
        for a in range(last + 1, last + 7):
            if budget_pool < FULL:
                break
            g = sib.get((p, rep, a))
            if g is None:
                continue
            budget_pool -= FULL; extra_y += g
    s3 = {"fixed_budget": {"total_steps": base_c, "clean_yield": base_y,
                           "steps_per_clean": round(steps_per_clean(base_c, base_y), 1)},
          "portfolio": {"budget_saved_by_donors": saved, "extra_clean_from_recipients": extra_y,
                        "net_yield": base_y + extra_y,
                        "steps_per_clean": round(steps_per_clean(base_c, base_y + extra_y), 1)},
          "note": "recipient extension limited by CRN sibling coverage (conservative lower bound)"}

    out = {"S1_cost_aware_threshold": s1, "S2_probe_on_evidence": s2, "S3_portfolio": s3,
           "label": "EXPLORATORY (Phase-2); confirmatory claims require the pre-registered online confirmatory run"}
    (B3 / "PHASE2_LEDGER_REPLAYS.json").write_text(json.dumps(out, indent=2))
    md = ["# Phase 2 — ledger counterfactual replays (exploratory)", "",
          "## S1 cost-aware threshold (arm-4 replay, CRN-filled)", "",
          "| τ | steps/clean | yield |", "|---|---|---|"]
    for k, v in s1.items():
        md.append(f"| {k} | {v['steps_per_clean']} | {v['clean_yield_total']} |")
    md += ["", "## S2 probe-on-evidence", "```json", json.dumps(s2, indent=2), "```",
           "", "## S3 portfolio allocation", "```json", json.dumps(s3, indent=2), "```"]
    (B3 / "PHASE2_LEDGER_REPLAYS.md").write_text("\n".join(md))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
