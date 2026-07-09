"""Repair the degenerate fallback-lyric collision from patch_prompts_lyric_floor.py.

The first pass exhausted the small EN pool (110 sources mostly already consumed by existing
prompts) and assigned ONE fallback lyric to 101 of the 122 thickened prompts. This reassigns
each of those 101 a DISTINCT original composite lyric (two already-vetted original fragments
concatenated -> still original, >=10 words, guaranteed unique, no real-song risk). The 21
cleanly-thickened prompts and the metal/dedup edits are left untouched.

Emits the 101 ids that must be RE-regenerated (their audio currently sings the fallback lyric).

Usage:
    PYTHONPATH=src python scripts/fix_lyric_floor_collisions.py [--apply]
"""
from __future__ import annotations
import argparse
import collections
import json
import re
from pathlib import Path

from mprm.data.prompts import load_prompts, save_prompts
from mprm.data.stratification import stratify
from patch_prompts_lyric_floor import _en_source_pool, _hash_seed, _wc, MIN_WORDS

REPO = Path(__file__).resolve().parents[1]
DEV = REPO / "configs/prompts/dev.jsonl"
HELD = REPO / "configs/prompts/held_out.jsonl"
REGEN2_IDS = REPO / "orbit-research/etv_lyric_regen2_prompt_ids_20260603.json"


def _first_lines(s: str, k: int) -> list[str]:
    return [l for l in s.split("\n") if l.strip()][:k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    dev = load_prompts(DEV)
    held = load_prompts(HELD)
    dev_before, held_before = stratify(dev), stratify(held)
    allp = dev + held
    patched = [p for p in allp if p.metadata.get("lyric_floor_patched")]

    counts = collections.Counter(p.lyrics for p in patched)
    fallback, n = counts.most_common(1)[0]
    targets = [p for p in patched if p.lyrics == fallback]
    print(f"thickened={len(patched)} distinct_lyrics={len(counts)} fallback_count={n}")
    assert n == len(targets)
    if len(targets) <= 1:
        print("no collision to fix."); return 0

    pool = _en_source_pool()
    forbidden = {p.lyrics for p in allp if p.lyrics}          # every current lyric
    # deterministic distinct composites: first2(pool[i]) + first2(pool[j])
    reassigned = {}
    P = len(pool)
    for p in sorted(targets, key=lambda x: x.prompt_id):
        seed = _hash_seed(p.prompt_id, "lyric_fix_composite")
        chosen = None
        for t in range(4000):
            i = (seed + t) % P
            j = (seed // P + t * 7 + 1) % P
            if i == j:
                j = (j + 1) % P
            cand = "\n".join(_first_lines(pool[i], 2) + _first_lines(pool[j], 2))
            if (len([l for l in cand.split("\n") if l.strip()]) >= 3
                    and _wc(cand) >= MIN_WORDS and cand not in forbidden):
                chosen = cand
                break
        assert chosen is not None, f"could not compose distinct lyric for {p.prompt_id}"
        forbidden.add(chosen)
        before_strata = dict(p.strata)
        p.lyrics = chosen
        p.metadata = {**p.metadata, "lyric_floor_patched": True, "lyric_composite_fixed": True}
        assert p.strata == before_strata and p.lyrics
        reassigned[p.prompt_id] = chosen

    # invariants + distinctness
    assert stratify(dev) == dev_before and stratify(held) == held_before, "strata changed!"
    patched2 = [p for p in dev + held if p.metadata.get("lyric_floor_patched")]
    lyr2 = [p.lyrics for p in patched2]
    assert len(set(lyr2)) == len(lyr2), f"thickened lyrics still not distinct: {len(set(lyr2))}/{len(lyr2)}"
    # cross-split identical among ALL prompts
    dl = {p.lyrics for p in dev if p.lyrics}
    hl = {p.lyrics for p in held if p.lyrics}
    print(f"reassigned={len(reassigned)} | all {len(patched2)} thickened lyrics now distinct: True")
    print(f"cross-split identical lyric strings now: {len(dl & hl)}")
    wcs = [_wc(v) for v in reassigned.values()]
    print(f"reassigned word counts: min={min(wcs)} median={sorted(wcs)[len(wcs)//2]} max={max(wcs)}")
    print("example:", json.dumps(dict(list(reassigned.items())[:2]), ensure_ascii=False))

    if not args.apply:
        print("\n[DRY RUN] nothing written.")
        return 0
    save_prompts(dev, DEV)
    save_prompts(held, HELD)
    ids = sorted(reassigned)
    REGEN2_IDS.write_text(json.dumps({"generated": "2026-06-03", "reason": "fallback-lyric collision repair",
                                      "n": len(ids), "prompt_ids": ids}, indent=2))
    print(f"\n[APPLIED] {DEV.name},{HELD.name}; re-regen ids -> {REGEN2_IDS} ({len(ids)} prompts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
