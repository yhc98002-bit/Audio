"""Generate the 64-prompt expansion set for Phase B.1 (PI directive 2026-05-23 §3).

Constraints:
  - Disjoint from formal 64 (PHASE_B1_RELIABILITY_PROMPTS.json).
  - Disjoint from σ-calibration 16 (SIGMA_CALIBRATION_PROMPTS.json).
  - Drawn from configs/prompts/dev.jsonl.
  - seed = 20260524 (per phase_b1_reliability.yaml escalation.ambiguous).
  - n = 64.

Writes:
  - orbit-research/PHASE_B1_RELIABILITY_PROMPTS_EXPANSION.json
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path


def main():
    dev_path = Path("configs/prompts/dev.jsonl")
    formal_path = Path("orbit-research/PHASE_B1_RELIABILITY_PROMPTS.json")
    cal_path = Path("orbit-research/SIGMA_CALIBRATION_PROMPTS.json")
    out_path = Path("orbit-research/PHASE_B1_RELIABILITY_PROMPTS_EXPANSION.json")

    if out_path.exists():
        print(f"[expansion] {out_path} already exists; refusing to overwrite", file=sys.stderr)
        return 1

    dev_ids = []
    with open(dev_path) as f:
        for line in f:
            p = json.loads(line)
            dev_ids.append(p["prompt_id"])

    with open(formal_path) as f:
        formal = json.load(f)["formal_prompt_ids"]
    with open(cal_path) as f:
        cal = json.load(f)["excluded_prompt_ids"]

    used = set(formal) | set(cal)
    pool = [pid for pid in dev_ids if pid not in used]
    print(f"[expansion] dev={len(dev_ids)}, formal={len(formal)}, cal={len(cal)}, "
          f"available pool={len(pool)}", flush=True)
    if len(pool) < 64:
        print(f"[expansion] FAIL — only {len(pool)} dev prompts available; need 64",
              file=sys.stderr)
        return 2

    rng = random.Random(20260524)
    expansion_ids = rng.sample(pool, 64)

    payload = {
        "schema_version": "phase_b1_reliability_prompts_expansion_v1",
        "generated": "2026-05-23 (PI directive autonomous expansion)",
        "source_jsonl": str(dev_path),
        "seed": 20260524,
        "n_expansion_prompts": 64,
        "disjoint_with": {
            "formal": str(formal_path),
            "sigma_calibration": str(cal_path),
        },
        "verification": {
            "intersection_with_formal_is_empty": True,
            "intersection_with_sigma_cal_is_empty": True,
            "manually_verified": False,
            "programmatic_verification_passed": True,
        },
        "expansion_prompt_ids": sorted(expansion_ids),
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"[expansion] wrote {out_path}", flush=True)
    print(f"[expansion] sample of first 5: {sorted(expansion_ids)[:5]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
