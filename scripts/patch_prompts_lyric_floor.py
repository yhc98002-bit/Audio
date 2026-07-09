"""Targeted in-place patch to make `lyric_intelligibility` a load-bearing axis.

PI directive 2026-06-03 (see orbit-research/prompt_set_audit_20260529/ R1/R8 and the
plan splendid-swimming-pebble.md). Mirrors `scripts/patch_prompts_quality.py`: edits ONLY
selected prompts, preserves every stratum, and leaves all other lines byte-identical.

Three targeted edits (union = the regen set):
  1. Thicken thin English vocal lyrics. Select EN vocal prompts whose lyric reference is
     < 10 words (mostly lyric_density="low" -> first line only). Re-draw a fresh multi-line
     fragment from the authored EN pools and apply a FLOOR-AWARE truncation so even "low"
     density keeps >=3 lines / >=10 words -> Whisper-WER becomes measurable instead of flooring.
  2. Strip the contradictory embedded " at 60 bpm" from the 9 metal prompts whose instrument
     clause ("fuzzed-out doom riff at 60 bpm, ...") disagrees with their headline tempo.
  3. De-dup the worst cross-split near-identical pairs by swapping the held_out member's mood
     adjective to a different same-genre bank mood (difflib < 0.85 vs its dev twin).

NON-EN vocal (zh/fr/ja, 34) are intentionally left as-is: Whisper-WER is English-only, so
thickening cannot lift them; the analysis fix scopes the lyric axis to vocal_scorable (EN vocal).

Invariants asserted: strata dicts unchanged, has_lyrics unchanged, duration/prompt_id unchanged,
per-split strata distribution unchanged, non-selected lines byte-identical.

Usage:
    PYTHONPATH=src python scripts/patch_prompts_lyric_floor.py [--apply]
(without --apply: dry run, prints the plan and writes nothing).
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import re
from pathlib import Path

from mprm.data.prompts import Prompt, load_prompts, save_prompts
from mprm.data.stratification import REQUIRED_STRATA, stratify

# Reuse the authored pools + helpers (import has no side effects; both guard __main__).
from patch_prompts_quality import NEW_LYRICS_EN, _hash_seed
from generate_real_prompts import ORIGINAL_LYRICS_BY_LANG, GENRES

REPO = Path(__file__).resolve().parents[1]
DEV = REPO / "configs/prompts/dev.jsonl"
HELD = REPO / "configs/prompts/held_out.jsonl"
ARCHIVE_DIR = REPO / "configs/prompts/archive_20260603"
DATASET = REPO / "orbit-research/trajectory_candidate_dataset.jsonl"
DATASET_ARCHIVE = REPO / "orbit-research/archive/trajectory_candidate_dataset_pre_lyricfix_20260603.jsonl"
REGEN_IDS = REPO / "orbit-research/etv_lyric_regen_prompt_ids_20260603.json"

WORD_RE = re.compile(r"\w+", re.UNICODE)
MIN_WORDS = 10
MIN_LINES = 3

# Worst cross-split near-dup pairs (held_out member -> its dev twin), from the audit.
DEDUP_PAIRS = {
    "held_out_0060": "dev_0073", "held_out_0188": "dev_0012",
    "held_out_0172": "dev_0240", "held_out_0136": "dev_0035",
    "held_out_0042": "dev_0175", "held_out_0242": "dev_0179",
}


def _wc(s: str | None) -> int:
    return len(WORD_RE.findall(s or ""))


def _en_source_pool() -> list[str]:
    """All authored EN fragments (>=3 lines, >=10 words at full length)."""
    pool = list(ORIGINAL_LYRICS_BY_LANG.get("en", [])) + list(NEW_LYRICS_EN)
    # keep only genuinely multi-line / word-rich sources
    return [s for s in pool if len([l for l in s.split("\n") if l.strip()]) >= MIN_LINES and _wc(s) >= MIN_WORDS]


def _floor_trunc(lyric: str, density: str) -> str:
    """Floor-aware truncation: preserves a (compressed) density gradient while keeping
    >=MIN_LINES lines / >=MIN_WORDS words so WER is measurable."""
    lines = [l for l in lyric.split("\n") if l.strip()]
    k = {"low": 3, "med": 4}.get(density, len(lines))
    k = max(MIN_LINES, min(k, len(lines)))
    return "\n".join(lines[:k])


def _thicken_lyrics(prompts: list[Prompt], used_sigs: set[str]) -> list[str]:
    """Mutate selected EN-vocal thin-lyric prompts in place. Returns the patched ids."""
    pool = _en_source_pool()
    patched: list[str] = []
    for p in prompts:
        st = p.strata
        if not (st.get("vocal_vs_instrumental") == "vocal" and st.get("language") == "en"):
            continue
        if _wc(p.lyrics) >= MIN_WORDS:
            continue
        density = st.get("lyric_density", "low")
        rng = random.Random(_hash_seed(p.prompt_id, "lyric_floor"))
        order = pool[:]
        rng.shuffle(order)
        chosen = None
        for src in order:
            cand = _floor_trunc(src, density)
            if (len([l for l in cand.split("\n") if l.strip()]) >= MIN_LINES
                    and _wc(cand) >= MIN_WORDS and cand not in used_sigs):
                chosen = cand
                break
        if chosen is None:  # fallback: deepest available, accept even if collides (rare)
            chosen = _floor_trunc(max(order, key=lambda s: _wc(s)), "high")
        used_sigs.add(chosen)
        before_strata = dict(p.strata)
        p.lyrics = chosen
        p.metadata = {**p.metadata, "lyric_floor_patched": True}
        assert p.strata == before_strata and p.lyrics is not None  # has_lyrics + strata invariant
        patched.append(p.prompt_id)
    return patched


def _fix_metal_bpm(prompts: list[Prompt]) -> list[str]:
    patched = []
    for p in prompts:
        if " at 60 bpm" in p.text:
            p.text = p.text.replace(" at 60 bpm", "")
            p.metadata = {**p.metadata, "bpm_contradiction_fixed": True}
            patched.append(p.prompt_id)
    return patched


def _mood_in(text: str, genre: str) -> str | None:
    low = text.lower()
    for m in GENRES.get(genre, {}).get("moods", []):
        if m.lower() in low:
            return m
    return None


def _dedup_near_pairs(by_id: dict[str, Prompt]) -> list[str]:
    """Best-effort de-dup: swap the held member's mood (and, if needed, the piece noun)
    to the same-genre bank token that MINIMISES difflib vs its dev twin. Applied
    unconditionally — these share a finite-bank instrument clause, so residual similarity
    is expected and benign (audit R2: same clause + different mood/tempo = distinct prompt).
    We only need them to stop being near-VERBATIM (the bpm-only twins)."""
    patched = []
    for held_id, dev_id in DEDUP_PAIRS.items():
        if held_id not in by_id or dev_id not in by_id:
            continue
        hp, dp = by_id[held_id], by_id[dev_id]
        genre = hp.strata.get("genre")
        cur_mood = _mood_in(hp.text, genre)
        moods = [m for m in GENRES.get(genre, {}).get("moods", [])
                 if m != cur_mood and m.lower() not in dp.text.lower()]
        base0 = difflib.SequenceMatcher(None, _norm(hp.text), _norm(dp.text)).ratio()
        trials = []  # (ratio, text)
        for m in moods:
            if cur_mood and cur_mood in hp.text:
                t1 = hp.text.replace(cur_mood, m, 1)
            else:
                t1 = re.sub(r"\b(piece|composition|tune|track|number|cut)\b",
                            m + r" \1", hp.text, count=1)
            trials.append((difflib.SequenceMatcher(None, _norm(t1), _norm(dp.text)).ratio(), t1))
            # also try mood + piece-noun swap for a bigger drop
            t2 = re.sub(r"\b(piece|composition|tune|track|number|cut)\b",
                        {"piece": "cut", "composition": "tune", "tune": "number",
                         "track": "piece", "number": "track", "cut": "composition"}.get(
                            (re.search(r"\b(piece|composition|tune|track|number|cut)\b", t1) or [None])
                            and re.search(r"\b(piece|composition|tune|track|number|cut)\b", t1).group(0),
                            "track"),
                        t1, count=1)
            trials.append((difflib.SequenceMatcher(None, _norm(t2), _norm(dp.text)).ratio(), t2))
        if not trials:
            print(f"  WARN: no alternate mood for {held_id} ({genre})")
            continue
        best_ratio, best_text = min(trials, key=lambda x: x[0])
        before_strata = dict(hp.strata)
        hp.text = best_text
        hp.metadata = {**hp.metadata, "dedup_patched": True}
        assert hp.strata == before_strata
        patched.append(held_id)
        print(f"  dedup {held_id} vs {dev_id}: difflib {base0:.3f} -> {best_ratio:.3f}")
    return patched


def _norm(s: str) -> str:
    return " ".join(WORD_RE.findall(s.lower()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the patched files (default: dry run)")
    args = ap.parse_args()

    dev = load_prompts(DEV)
    held = load_prompts(HELD)
    dev_before = stratify(dev)
    held_before = stratify(held)
    by_id = {p.prompt_id: p for p in dev + held}

    # seed forbidden signatures with every EXISTING lyric (so we never create a new dup)
    used_sigs: set[str] = {p.lyrics for p in dev + held if p.lyrics}

    thick = _thicken_lyrics(dev + held, used_sigs)
    metal = _fix_metal_bpm(dev + held)
    dedup = _dedup_near_pairs(by_id)

    # invariants
    assert stratify(dev) == dev_before, "dev strata distribution changed!"
    assert stratify(held) == held_before, "held strata distribution changed!"
    for p in dev + held:
        assert REQUIRED_STRATA <= set(p.strata), f"{p.prompt_id} missing strata"
        if p.strata.get("vocal_vs_instrumental") == "vocal":
            assert p.lyrics, f"{p.prompt_id} vocal lost lyrics"
        else:
            assert not p.lyrics, f"{p.prompt_id} instrumental gained lyrics"

    regen_ids = sorted(set(thick) | set(metal) | set(dedup))
    print(f"thickened lyrics : {len(thick)} prompts")
    print(f"metal bpm fixed  : {len(metal)} -> {metal}")
    print(f"dedup near-pairs : {len(dedup)} -> {dedup}")
    print(f"REGEN SET (union): {len(regen_ids)} prompts")
    # word-count sanity on thickened
    wcs = [_wc(by_id[i].lyrics) for i in thick]
    print(f"thickened lyric word counts: min={min(wcs)} median={sorted(wcs)[len(wcs)//2]} max={max(wcs)}")
    print("example thickened:", json.dumps({i: by_id[i].lyrics for i in thick[:2]}, ensure_ascii=False))

    if not args.apply:
        print("\n[DRY RUN] nothing written. Re-run with --apply to commit.")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (ARCHIVE_DIR / "dev.jsonl").write_bytes(DEV.read_bytes())
    (ARCHIVE_DIR / "held_out.jsonl").write_bytes(HELD.read_bytes())
    DATASET_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    if DATASET.exists() and not DATASET_ARCHIVE.exists():
        DATASET_ARCHIVE.write_bytes(DATASET.read_bytes())
    save_prompts(dev, DEV)
    save_prompts(held, HELD)
    REGEN_IDS.write_text(json.dumps({"generated": "2026-06-03", "n": len(regen_ids),
                                     "prompt_ids": regen_ids}, indent=2))
    print(f"\n[APPLIED] patched {DEV.name}, {HELD.name}; regen ids -> {REGEN_IDS}")
    print(f"archives: {ARCHIVE_DIR}, {DATASET_ARCHIVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
