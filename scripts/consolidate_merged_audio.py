#!/usr/bin/env python
"""Consolidate per-candidate audio into the merged dataset tree so the downstream pipeline
(adsr_downstream.py) can label/mel the full 4096 set from ONE RUN root.

The merge (merge_resume_records.py) wrote only candidate_records.jsonl per shard. Each record
carries the authoritative paths to ITS OWN wavs (the generation that produced its rewards):
  audio_path                final wav
  early_0.9/0.8/0.7_audio_path   early-Tweedie wavs at sigma 0.9/0.8/0.7
These live in either the original run tree or a resume tree; original-wins precedence is already
baked into which record survived the merge, so symlinking the record's own paths keeps audio and
rewards consistent by construction.

We create:  <merged>/shard{midx//64:02d}/audio/<prompt_id>/<basename>  ->  (absolute) source wav
mirroring the original layout exactly, so adsr_downstream.py works by only re-pointing RUN.

Symlinks (absolute targets; same Lustre FS). Idempotent: re-links if target differs. Strict QA at
the end; exits nonzero if anything is missing/inconsistent so it can gate the labeling step.
"""
from __future__ import annotations
import argparse, glob, json, os, sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MERGED = REPO / "runs" / "adsr_recollect_20260604_full01_merged"
MASTER = REPO / "orbit-research" / "EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json"
BON_N = 8
SHARD_SIZE = 64
EARLY_KEYS = ["early_0.9_audio_path", "early_0.8_audio_path", "early_0.7_audio_path"]
FINAL_KEY = "audio_path"
SEED_BASE = 2026052700


def resolve(p):
    if not p:
        return None
    p = Path(p)
    return p if p.is_absolute() else (REPO / p)


def expected_basename(ci, seed, key):
    """The wav basename a record MUST point to, derived from its own candidate_index +
    candidate_seed + sigma. Guards against a malformed record whose path key points at the
    wrong candidate/sigma (Codex review hardening): per-candidate, per-sigma correctness, not
    just aggregate counts."""
    if key == FINAL_KEY:
        return f"candidate_{ci:02d}_seed{seed}.wav"
    sk = key.split("_")[1]  # "early_0.9_audio_path" -> "0.9"
    return f"candidate_{ci:02d}_seed{seed}_early{sk}.wav"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only; create no symlinks")
    args = ap.parse_args()

    master = json.loads(MASTER.read_text())["prompts"]
    master_ids = {r["prompt_id"] for r in master}
    midx_of = {r["prompt_id"]: int(r["manifest_index"]) for r in master}

    recs = []
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for line in open(f):
            line = line.strip()
            if line:
                recs.append(json.loads(line))

    # ---- integrity of the record set BEFORE touching the FS ----
    seen = defaultdict(set)
    bad_seed = unknown = 0
    for r in recs:
        pid, ci = r.get("prompt_id"), r.get("candidate_index")
        if pid not in master_ids:
            unknown += 1; continue
        ci = int(ci)
        if int(r.get("candidate_seed", -1)) != SEED_BASE + midx_of[pid] * 1000 + ci:
            bad_seed += 1
        seen[pid].add(ci)
    dup = len(recs) - sum(len(v) for v in seen.values())  # records minus unique (pid,ci)
    incomplete = {p: sorted(seen.get(p, set())) for p in master_ids if seen.get(p, set()) != set(range(BON_N))}

    linked = 0
    missing_src = []   # (pid, ci, key, path)
    basename_mismatch = []  # (pid, ci, key, got, expected) — wrong cand/seed/sigma in the path
    per_prompt_final = defaultdict(int)
    per_prompt_early = defaultdict(int)
    for r in recs:
        pid = r.get("prompt_id"); ci = int(r.get("candidate_index"))
        if pid not in master_ids:
            continue
        seed = int(r.get("candidate_seed", -1))
        shard = midx_of[pid] // SHARD_SIZE
        ddir = MERGED / f"shard{shard:02d}" / "audio" / pid
        for key in (FINAL_KEY, *EARLY_KEYS):
            src = resolve(r.get(key))
            if src is None or not src.exists():
                missing_src.append((pid, ci, key, str(r.get(key)))); continue
            exp = expected_basename(ci, seed, key)
            if src.name != exp:
                basename_mismatch.append((pid, ci, key, src.name, exp)); continue
            if not args.dry_run:
                ddir.mkdir(parents=True, exist_ok=True)
                dst = ddir / src.name
                tgt = str(src.resolve())
                if dst.is_symlink() or dst.exists():
                    if os.path.realpath(dst) == os.path.realpath(tgt):
                        pass
                    else:
                        dst.unlink(); dst.symlink_to(tgt)
                else:
                    dst.symlink_to(tgt)
            linked += 1
            if key == FINAL_KEY:
                per_prompt_final[pid] += 1
            else:
                per_prompt_early[pid] += 1

    # ---- strict QA over what we just created ----
    report = {
        "records": len(recs),
        "unique_prompt_cand": sum(len(v) for v in seen.values()),
        "duplicate_records": dup,
        "unknown_prompt_ids": unknown,
        "bad_seed_records": bad_seed,
        "prompts_incomplete_8of8": len(incomplete),
        "expected_links": len(recs) * 4,
        "links_made_or_present": linked,
        "missing_source_wavs": len(missing_src),
        "basename_mismatches": len(basename_mismatch),
        "basename_mismatch_examples": basename_mismatch[:5],
        "prompts_with_8_final": sum(1 for p in master_ids if per_prompt_final.get(p, 0) == BON_N),
        "prompts_with_24_early": sum(1 for p in master_ids if per_prompt_early.get(p, 0) == BON_N * 3),
        "missing_examples": missing_src[:5],
        "incomplete_examples": dict(list(incomplete.items())[:5]),
    }
    print(json.dumps(report, indent=2))

    ok = (len(recs) == BON_N * len(master_ids) and dup == 0 and unknown == 0 and bad_seed == 0
          and len(incomplete) == 0 and len(missing_src) == 0 and len(basename_mismatch) == 0
          and report["links_made_or_present"] == report["expected_links"])
    if args.dry_run:
        print("DRY-RUN (no symlinks created)")
        return 0
    if not ok:
        print("CONSOLIDATION QA FAILED", file=sys.stderr)
        return 1
    # post-FS verification: every merged prompt dir resolves 8 final + 24 early through the symlinks
    fs_bad = []
    for pid in master_ids:
        shard = midx_of[pid] // SHARD_SIZE
        ddir = MERGED / f"shard{shard:02d}" / "audio" / pid
        finals = [p for p in ddir.glob("candidate_*_seed*.wav") if "_early" not in p.name] if ddir.is_dir() else []
        earlys = list(ddir.glob("candidate_*_seed*_early*.wav")) if ddir.is_dir() else []
        broken = [p for p in (finals + earlys) if not p.resolve().exists()]
        if len(finals) != BON_N or len(earlys) != BON_N * 3 or broken:
            fs_bad.append((pid, len(finals), len(earlys), len(broken)))
    print(json.dumps({"fs_verify_bad_prompts": len(fs_bad), "examples": fs_bad[:5]}, indent=2))
    if fs_bad:
        print("FS VERIFY FAILED", file=sys.stderr)
        return 1
    print("CONSOLIDATION COMPLETE — 512 prompts x (8 final + 24 early) symlinks verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
