"""Final layered merge of the lyric-floor regeneration.

Priority per prompt_id (highest first):
  1. lyricfix2 (101 collision-repaired prompts, distinct composite lyrics)
  2. lyricfix_01 (132-prompt first pass) -> contributes the 31 non-broken prompts
  3. original full01 (the remaining 380 untouched prompts)

Writes a NEW merged shard; does not modify any read-only runs/**. Re-run the analysis on it.

Usage:  PYTHONPATH=src python scripts/merge_lyricfix_final.py
"""
from __future__ import annotations
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAYERS = [  # (glob, label) in PRIORITY order, highest first
    ("runs/early_tweedie_validation_lyricfix2_20260603_01/shard0*/candidate_records.jsonl", "lyricfix2"),
    ("runs/early_tweedie_validation_lyricfix_20260603_01/shard0*/candidate_records.jsonl", "lyricfix1"),
    ("runs/early_tweedie_validation_512_bon8_20260527_full01/shard0*/candidate_records.jsonl", "original"),
]
OUT = REPO / "runs/early_tweedie_validation_final_lyricfix_20260603/shard00/candidate_records.jsonl"


def _by_prompt(pattern):
    d = defaultdict(list)
    for f in sorted(glob.glob(str(REPO / pattern))):
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                d[r["prompt_id"]].append(r)
    return d


def main() -> int:
    layers = [( _by_prompt(p), lbl) for p, lbl in LAYERS]
    all_ids = set(layers[-1][0])  # original defines the full 512
    assert len(all_ids) == 512, f"original has {len(all_ids)} prompts"
    merged = []
    provenance = Counter()
    for pid in sorted(all_ids):
        for d, lbl in layers:
            if pid in d:
                recs = sorted(d[pid], key=lambda r: int(r["candidate_index"]))
                assert len(recs) == 8, f"{pid} in {lbl} has {len(recs)} cands"
                merged.extend(recs)
                provenance[lbl] += 1
                break
    assert len(merged) == 4096, f"merged {len(merged)} != 4096"
    per = Counter(r["prompt_id"] for r in merged)
    assert set(per.values()) == {8} and set(per) == all_ids
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"merged {len(merged)} records -> {OUT}")
    print(f"provenance by prompt: {dict(provenance)}")  # expect lyricfix2=101, lyricfix1=31, original=380
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
