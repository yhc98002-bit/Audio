#!/usr/bin/env python
"""Merge the original ADSR records with all resume-run records into one complete 4096 dataset.

Dedup by (prompt_id, candidate_index) with ORIGINAL-WINS precedence: the original run's
candidates are authoritative; resume runs only fill genuinely-missing (prompt,cand) pairs.
This sidesteps any cross-acquisition/cross-GPU non-determinism. See ADSR_RESUME_RUNBOOK_20260605.md.

Writes 8 shard dirs mirroring the original layout (prompt sharded by manifest_index//64).
"""
from __future__ import annotations
import argparse, glob, json, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MASTER = REPO / "orbit-research" / "EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"
ORIG_GLOB = "runs/adsr_recollect_20260604_full01/shard0*/candidate_records.jsonl"
RESUME_GLOB = "runs/adsr_recollect_resume/*/candidate_records.jsonl"
BON_N = 8
SHARD_SIZE = 64
SEED_BASE = 2026052700  # must match collect_early_tweedie_validation.py default


def expected_seed(manifest_index, ci):
    return SEED_BASE + int(manifest_index) * 1000 + int(ci)


def load(globpat):
    out = []
    for f in sorted(glob.glob(str(REPO / globpat))):
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # skip torn line
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path,
                    default=REPO / "runs" / "adsr_recollect_20260604_full01_merged")
    ap.add_argument("--allow-partial", action="store_true",
                    help="write what we have and report shortfall instead of failing the asserts")
    args = ap.parse_args()

    master_ids = [r["prompt_id"] for r in json.loads(MASTER.read_text())["prompts"]]
    master_set = set(master_ids)
    midx = {r["prompt_id"]: int(r["manifest_index"]) for r in json.loads(MASTER.read_text())["prompts"]}

    FULL = set(range(BON_N))
    kept = {}              # (pid,ci) -> record ; original-wins
    src_counts = defaultdict(int)
    dups_dropped = 0
    rejected = 0          # bad seed / out-of-range index / unknown prompt (Codex review #1/#2)
    for tag, recs in (("original", load(ORIG_GLOB)), ("resume", load(RESUME_GLOB))):
        for r in recs:
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
                rejected += 1  # malformed candidate_index/seed -> reject
                continue
            key = (pid, ci)
            if key in kept:
                dups_dropped += 1
                continue
            kept[key] = r
            src_counts[tag] += 1

    per_prompt = defaultdict(set)
    for (pid, ci) in kept:
        per_prompt[pid].add(ci)

    total = len(kept)
    # completeness requires the EXACT candidate set {0..7} per prompt, not just a count
    complete = sum(1 for p in master_ids if per_prompt.get(p, set()) == FULL)
    short = {p: sorted(per_prompt.get(p, set())) for p in master_ids if per_prompt.get(p, set()) != FULL}
    extra_ids = set(per_prompt) - master_set
    report = {
        "total_records": total, "from_original": src_counts["original"],
        "from_resume": src_counts["resume"], "overlap_dups_dropped": dups_dropped,
        "rejected_bad_seed_or_index": rejected,
        "prompts_complete_8of8": complete, "prompts_master": len(master_ids),
        "prompts_incomplete": len(short), "unknown_prompt_ids": sorted(extra_ids)[:5],
    }
    print(json.dumps(report, indent=2))

    ok = (total == BON_N * len(master_ids) and complete == len(master_ids) and not extra_ids)
    if not ok and not args.allow_partial:
        print(f"NOT COMPLETE — {len(short)} prompts != 8 candidates (first 5: "
              f"{dict(list(short.items())[:5])}); rerun after generation finishes "
              f"or pass --allow-partial.", file=sys.stderr)
        return 1

    # write 8 shards mirroring original layout (by manifest_index//64)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    buckets = defaultdict(list)
    for (pid, ci), r in kept.items():
        buckets[midx[pid] // SHARD_SIZE].append(r)
    for sh, rows in sorted(buckets.items()):
        d = args.out_dir / f"shard{sh:02d}"
        d.mkdir(parents=True, exist_ok=True)
        rows.sort(key=lambda r: (midx[r["prompt_id"]], r["candidate_index"]))
        with (d / "candidate_records.jsonl").open("w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    (args.out_dir / "MERGE_REPORT.json").write_text(json.dumps(report, indent=2))
    print(f"wrote merged dataset -> {args.out_dir}  ({'COMPLETE' if ok else 'PARTIAL'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
