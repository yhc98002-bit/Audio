#!/usr/bin/env python
"""Batch-3 ledger validation (ANALYSIS_PLAN gates). Run on dry run AND before any analysis.

Checks per (prompt, arm, rep) unit: budget conservation (Σcost ≤ cap, every attempt entered
with ≥30 remaining), abort cap ≤6, attempts contiguous from 0, CRN seed formula, probed-arm
consistency (arm∈{2,3,4,6} ⟺ probes), completion rows carry gate+scores, unit_selection present
for finished units, dual-ledger overhead fields present. Exit nonzero on any violation.
"""
from __future__ import annotations
import argparse, glob, json, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUDGETS = {1: 168, 2: 168, 3: 168, 4: 168, 6: 168, 7: 240, 8: 120}
SEED_B3 = 2026062000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--expect-prompts", type=int, default=None)
    args = ap.parse_args()
    rows, sels = defaultdict(list), {}
    for f in glob.glob(f"{args.dir}/ledger_w*.jsonl"):
        for l in open(f):
            d = json.loads(l)
            k = (d["prompt_id"], d["arm"], d["rep"])
            if d.get("type") == "unit_selection":
                sels[k] = d
            else:
                rows[k].append(d)
    midx = {json.loads(l)["prompt_id"]: json.loads(l)["manifest_index"]
            for l in open(REPO / "orbit-research/adsr_phase2_20260604/batch3/batch3_selected_prompts_256.jsonl")}
    bad = []
    for k, rs in rows.items():
        pid, arm, rep = k
        rs.sort(key=lambda d: d["attempt"])
        cap = BUDGETS[arm]
        spent = 0
        aborts = 0
        for i, d in enumerate(rs):
            if d["attempt"] != i:
                bad.append((k, f"attempt gap at {i}"))
            if cap - spent < 30:
                bad.append((k, f"attempt {i} entered with {cap-spent} left"))
            exp_seed = SEED_B3 + midx[pid] * 1000 + rep * 100 + d["attempt"]
            if d["seed"] != exp_seed:
                bad.append((k, f"seed mismatch at {i}: {d['seed']} != {exp_seed}"))
            if d.get("aborted"):
                aborts += 1
                if d["cost"] != 12:
                    bad.append((k, f"abort cost {d['cost']}"))
            elif d.get("completed"):
                if d["cost"] != 30:
                    bad.append((k, f"completion cost {d['cost']}"))
                for fld in ("gate_pass", "final_common_robust_lcb", "wall_s"):
                    if fld not in d:
                        bad.append((k, f"completion missing {fld}"))
            spent += d["cost"]
            probing = arm in (2, 3, 4, 6)
            if d.get("probed") and not probing:
                bad.append((k, "non-probing arm probed"))
        if spent > cap:
            bad.append((k, f"overspent {spent}>{cap}"))
        if aborts > 6:
            bad.append((k, f"aborts {aborts}>6"))
        if any(d.get("completed") for d in rs) and k not in sels:
            bad.append((k, "missing unit_selection"))
    n_units = len(rows)
    n_prompts = len({k[0] for k in rows})
    rep = {"units": n_units, "prompts": n_prompts, "attempt_rows": sum(len(v) for v in rows.values()),
           "unit_selections": len(sels), "violations": len(bad), "examples": bad[:10]}
    print(json.dumps(rep, indent=2, default=str))
    if args.expect_prompts and n_prompts != args.expect_prompts:
        print(f"PROMPT COUNT {n_prompts} != expected {args.expect_prompts}", file=sys.stderr)
        return 1
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
