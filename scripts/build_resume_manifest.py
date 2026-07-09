#!/usr/bin/env python
"""Build a rescue manifest of the prompts still needing generation, for resuming the
ADSR re-collection after the GPUs were lost.

Recomputes the remaining set R live from on-disk records (original run + any resume run
dirs), so it is always correct after preemption. Preserves each prompt's GLOBAL
`manifest_index` so the collector reproduces identical seeds
(seed = seed_base + manifest_index*1000 + cand_idx) — see ADSR_RESUME_RUNBOOK_20260605.md.

For multi-node "both generate" use, an optional stride partition (--num-workers/--worker-index)
hands each concurrent worker a disjoint slice of R; any residual overlap is removed later by the
original-wins merge (merge_resume_records.py). Single-worker default => the whole of R.
"""
from __future__ import annotations
import argparse, glob, json, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MASTER = REPO / "orbit-research" / "EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"
DEFAULT_RECORD_GLOBS = [
    "runs/adsr_recollect_20260604_full01/shard0*/candidate_records.jsonl",
    "runs/adsr_recollect_resume/*/candidate_records.jsonl",
]
BON_N = 8
SEED_BASE = 2026052700  # must match collect_early_tweedie_validation.py default


def expected_seed(manifest_index, ci):
    return SEED_BASE + int(manifest_index) * 1000 + int(ci)


def count_candidates(record_globs, midx):
    """prompt_id -> set(valid candidate_index) seen on disk (across all run dirs).
    A record only counts as a real, done candidate if its index is in [0,BON_N) AND its
    candidate_seed matches seed_base+manifest_index*1000+ci (Codex review #1/#2) — this rejects
    stray/wrong-seed/out-of-range records so they get regenerated instead of masking a gap.
    """
    seen = defaultdict(set)
    rejected = 0
    for g in record_globs:
        for f in glob.glob(str(REPO / g)):
            try:
                fh = open(f)
            except OSError:
                continue
            with fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # ignore a torn final line from an abrupt kill
                    pid = r.get("prompt_id")
                    ci = r.get("candidate_index")
                    if pid is None or ci is None or pid not in midx:
                        rejected += 1
                        continue
                    try:
                        ci = int(ci)
                        if not (0 <= ci < BON_N) or int(r.get("candidate_seed", -1)) != expected_seed(midx[pid], ci):
                            rejected += 1
                            continue
                    except (TypeError, ValueError):
                        rejected += 1  # malformed candidate_index/seed -> reject, regenerate
                        continue
                    seen[pid].add(ci)
    return seen, rejected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None, help="output manifest path (omit for --dry-run)")
    ap.add_argument("--order", choices=["forward", "reverse"], default="forward",
                    help="manifest_index ascending (forward) or descending (reverse)")
    ap.add_argument("--num-workers", type=int, default=1)
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--record-glob", action="append", default=None,
                    help="override record globs (repeatable); default = original + resume dirs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.num_workers < 1 or not (0 <= args.worker_index < args.num_workers):
        print("bad --num-workers/--worker-index", file=sys.stderr)
        return 2

    globs = args.record_glob or DEFAULT_RECORD_GLOBS
    master = json.loads(MASTER.read_text())
    rows = master["prompts"]
    midx = {r["prompt_id"]: int(r["manifest_index"]) for r in rows}
    seen, rejected = count_candidates(globs, midx)

    FULL = set(range(BON_N))
    # "complete" requires the EXACT set {0..7}, not just a count of 8 (Codex review #2)
    remaining = [r for r in rows if seen.get(r["prompt_id"], set()) != FULL]
    remaining.sort(key=lambda r: int(r["manifest_index"]), reverse=(args.order == "reverse"))
    # stride partition for concurrent workers (disjoint slices of the SAME R)
    my_rows = remaining[args.worker_index::args.num_workers]

    complete = sum(1 for r in rows if seen.get(r["prompt_id"], set()) == FULL)
    partial = sum(1 for r in rows if 0 < len(seen.get(r["prompt_id"], set())) < BON_N)
    notstarted = sum(1 for r in rows if len(seen.get(r["prompt_id"], set())) == 0)
    gens_remaining = sum(BON_N - len(seen.get(r["prompt_id"], set()) & FULL) for r in rows)
    print(json.dumps({
        "master_prompts": len(rows),
        "complete_8of8": complete, "partial": partial, "not_started": notstarted,
        "rejected_records_bad_seed_or_index": rejected,
        "remaining_prompts_total": len(remaining), "remaining_candidate_gens": gens_remaining,
        "this_worker_prompts": len(my_rows), "num_workers": args.num_workers,
        "worker_index": args.worker_index, "order": args.order,
    }, indent=2))

    if args.dry_run or args.out is None:
        return 0

    out = dict(master)
    out["prompts"] = my_rows
    out["n_prompts"] = len(my_rows)
    out["description"] = (master.get("description", "") +
                          f" | RESCUE order={args.order} worker={args.worker_index}/{args.num_workers}")
    # recompute split/vocal counts for the slice (informational; collector reads per-row meta)
    sc, vc = defaultdict(int), defaultdict(int)
    for r in my_rows:
        sc[r.get("split", "?")] += 1
        vc[r.get("vocal_stratum", "?")] += 1
    out["split_counts"], out["vocal_counts"] = dict(sc), dict(vc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"wrote {args.out} ({len(my_rows)} prompts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
