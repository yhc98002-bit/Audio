"""Merge the lyric-floor regen records back into the full 512-prompt record set.

For each of the 132 patched prompt_ids, drop its 8 OLD candidate records and insert
its 8 NEW ones; every other prompt's records are passed through byte-for-byte. Writes a
NEW merged shard (does NOT modify the read-only original runs/**). Re-run the analysis on
the merged records to derive the corrected dataset + headline numbers.

Usage:
    PYTHONPATH=src python scripts/merge_lyricfix_records.py
"""
from __future__ import annotations
import glob
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OLD = sorted(glob.glob(str(REPO / "runs/early_tweedie_validation_512_bon8_20260527_full01/shard0*/candidate_records.jsonl")))
NEW = sorted(glob.glob(str(REPO / "runs/early_tweedie_validation_lyricfix_20260603_01/shard0*/candidate_records.jsonl")))
REGEN = set(json.loads((REPO / "orbit-research/etv_lyric_regen_prompt_ids_20260603.json").read_text())["prompt_ids"])
OUT_DIR = REPO / "runs/early_tweedie_validation_merged_lyricfix_20260603/shard00"


def _read(paths):
    rows = []
    for p in paths:
        with open(p) as f:
            rows += [json.loads(l) for l in f if l.strip()]
    return rows


def main() -> int:
    old = _read(OLD)
    new = _read(NEW)
    assert len(old) == 4096, f"old records {len(old)} != 4096"
    assert len(new) == len(REGEN) * 8 == 1056, f"new {len(new)} != {len(REGEN)*8}"
    old_ids = {r["prompt_id"] for r in old}

    kept = [r for r in old if r["prompt_id"] not in REGEN]
    merged = kept + new
    # integrity asserts
    assert len(merged) == 4096, f"merged {len(merged)} != 4096"
    per = Counter(r["prompt_id"] for r in merged)
    assert set(per.values()) == {8}, f"not all prompts have 8 candidates: {Counter(per.values())}"
    assert set(per) == old_ids, "prompt-id set changed!"
    # every regen prompt's records came from NEW (carry a patched marker or new scores)
    new_ids = {r["prompt_id"] for r in new}
    assert new_ids == REGEN, "new records prompt set != regen set"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "candidate_records.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"merged {len(merged)} records ({len(kept)} kept old + {len(new)} new) -> {out}")
    print(f"prompts: {len(per)} | candidates/prompt: {set(per.values())} | regen replaced: {len(REGEN)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
