"""In-place quality patch for the existing dev / held-out prompt JSONL.

Goals (PI directive 2026-05-17):
  1. Keep current strata distribution exactly. Do NOT regenerate from scratch.
  2. Regenerate ONLY duplicated/reused lyric fragments, especially held-out.
  3. Reduce dev↔held-out lyric-only overlap from ~128 to <10 (ideally).
  4. Rewrite 20–30 % of broad/template prompts into natural human-request style.
  5. Keep combined text+lyrics overlap at 0.
  6. Keep instrumental lyrics empty/None.
  7. Re-validate and regenerate `PROMPT_GENERATION_REPORT.md`.
  8. Do NOT delete `configs/prompts/MISSING_REAL_PROMPTS.flag`.

Strategy:
  - Author ~60 new original short-lyric fragments in English (existing pool was
    ~62 fragments × 3 truncation densities; that wasn't enough for ~314 vocal
    prompts with low cross-split overlap). Reserve the expansion as a
    HELD_OUT-PREFERRED pool — when patching held-out lyric collisions, draw
    from this fresh pool first, falling back to the original pool's non-dev
    sigs as a last resort.
  - Identify held-out vocal prompts whose `lyrics` value equals any dev lyric;
    replace each with a freshly-drawn fragment + density-correct truncation.
  - Identify ~25 % of prompts (deterministic by `prompt_id` hash; targeted at
    `prompt_specificity == "broad"` first, then medium until quota is met)
    and rewrite their `text` into a natural human-request style. Strata
    remain unchanged; only the surface text changes.
  - Re-run the generator's `--validate-only` path (or inline equivalent).
  - Rewrite the PROMPT_GENERATION_REPORT.md.

Usage:
    PYTHONPATH=src python scripts/patch_prompts_quality.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

from mprm.data.prompts import Prompt, load_prompts, save_prompts
from mprm.data.stratification import REQUIRED_STRATA

# ============================================================================
# NEW lyric fragments — original short fragments authored 2026-05-17 to
# expand the held-out lyric pool. Each fragment is 3-5 lines; not copied
# from any real song. Style intentionally varied (narrative / imagistic /
# question / observation) to avoid template-feel.
# ============================================================================

NEW_LYRICS_EN: list[str] = [
    "the train pulled out at six\nI did not wave\nI stood by the window and counted the cars",
    "winter is generous with silence\nwe took what it offered\nwe slept past noon and pretended",
    "the old house remembers\nthe stairs creak in the same places\nthe rooms hold a different light now",
    "I called your name twice\nthe second time was for me\nthe second time was for habit",
    "morning sun came through the curtain\nlike it owed us an apology\nlike we were both still here",
    "I will not unpack tonight\nthe bags can sit by the door\nthe bags can listen to the radio with me",
    "we passed three lighthouses\nnone of them blinked\nwe took it as a sign of something",
    "you wore your father's coat\nit was too long at the sleeves\nit fit you in places you did not ask about",
    "the dog learned the new house\nbefore I did\nthe dog learned the slope of the new yard",
    "I keep your handwriting\non a piece of paper in the bedside drawer\nin case I forget what a 'g' looks like",
    "the diner had two specials\nwe chose the third option\nwe chose to leave without ordering",
    "we set out at dawn\nwithout the maps\nwithout the conversation about the maps",
    "I taught the cat the lights\nI taught the cat the silence\nthe cat is teaching me nothing back",
    "your sweater on the chair\nyour shape inside the sweater\nyour shape leaving the room",
    "the train station has changed\nthe pigeons have not\nthe pigeons know who is leaving",
    "if I were the kind of person\nwho wrote down the things I almost said\nI would have a small book by now",
    "the radio in the truck\nhas one good station\nit is enough for the long drive",
    "she opened the window and waited\nfor the right kind of weather\nfor the right kind of memory",
    "we left the porch light on\nbecause your sister might come back\nbecause we wanted to believe that",
    "the sea was loud that day\nthe sea was always loud\nwe just stopped listening for the difference",
    "the new neighbors have a piano\nthey play it badly\nthey play it every Tuesday at six",
    "I bought you a sweater\nin a color I would never wear\nI hope it fits",
    "the bridge over the river\nstill has our initials\nthough I had to look twice",
    "I baked the same bread\nfor a week\nuntil it tasted the way I remembered",
    "the calendar in the kitchen\nis stuck on March\nit has been June for a while",
    "we sat on the curb until the rain\nwe sat on the curb in the rain\nwe sat on the curb after the rain",
    "the long table at Christmas\nhas one chair we no longer mention\nhas a place setting we no longer make",
    "I told the dentist about my week\nshe nodded and kept working\nshe is the only one listening",
    "the airport at night\nhas a kind of mercy\neveryone is going somewhere they do not live",
    "you said 'oh' in three different ways\nin the same conversation\nI was paying attention to that",
    "the cinnamon in the cupboard\nis the same cinnamon\nfrom the morning you left",
    "I am keeping a list\nof things you would have liked\nso far it is mostly small dogs",
    "we drove past the lake five times\nbefore I let you stop\nbefore I let you say the thing",
    "the elevator song\nis still the same\nthe elevator song knows us",
    "I learned a new chord progression\nfor a song I am not writing\nfor a person I am not telling",
    "the front door has a new key\nthe front door has the same hinge\nthe hinge still complains in February",
    "the woman at the bakery\nknows my order on Tuesdays\nshe does not know I cancelled the rest",
    "I left the kettle on\nthe kettle did not mind\nthe kettle has seen worse",
    "we counted to thirteen\nbefore the next car passed\nit was a quiet night for a quiet town",
    "I packed the books last\nyour books and my books\nyour books on the bottom",
    "the moths at the porch light\ndo not know the difference\nbetween the lamp and the love it stood in for",
    "you sent me three photos\nof a tree at sunset\nfrom a city I have never been to",
    "the song in the grocery store\nhad your name in the chorus line\nthough not your name exactly",
    "I changed all the locks\nand then changed them again\nthe locksmith was not amused",
    "the postcard came late\nlike a friend who has been thinking\nlike a friend who is still thinking",
    "I am learning to whistle\nthe way my mother whistled\nin the kitchen on Saturdays",
    "the way you fold a towel\nis not the way I fold a towel\nI think about this on Sundays",
    "we agreed on a meeting place\nwe agreed on a time\nwe both arrived at the wrong day",
    "I tell the cab driver about you\nin small doses\nso the ride feels longer",
    "the porch swing knows my weight\nthe porch swing knows the weight of waiting\nthe porch swing keeps quiet about it",
    "the cat sleeps on the laundry\nthe cat sleeps on the books\nthe cat refuses the bed I bought",
    "you taught me to make coffee\nyou taught me badly\nthe coffee has improved without you",
    "I called my mother from a payphone\nshe asked which city\nI lied and said the one closer",
    "the museum is empty on Mondays\nthe museum is mine on Mondays\nthe museum is patient with me",
    "we played that record so many times\nthe needle wore a path\nthe path is also a kind of song",
    "the parking lot in winter\nholds the cold like a glass\nholds the cold and offers it back",
    "I keep almost calling\nI keep almost writing\nI keep almost driving over",
    "the field behind the house\nhas a new fence\nthe deer have not been told",
    "the wedding was small\nthe wedding was correct\nthe wedding had your father in it",
    "I planted the same tomatoes\nin the same soil\nin a different year",
]

NEW_LYRICS_OTHER: dict[str, list[str]] = {
    "zh": [
        "厨房的水龙头滴了一夜\n我没有起来关\n我假装没听见",
        "公交车开过的时候\n窗户上有你的呼吸\n你的呼吸不冷不热",
        "我把信揉成一团\n又重新展开\n字迹还在原来的位置",
        "茶杯的把手不见了\n茶杯还能用\n我也还能用",
        "周末的电梯里\n只有一个人\n我以为我会更喜欢一点",
    ],
    "es": [
        "el reloj de la cocina\nse paró en marzo\nllevo desde entonces sin reparar nada",
        "compré flores que no necesito\npara una casa que no es nuestra\npara un fin de semana que no fue",
        "el café se enfría dos veces\nporque dejo de prestar atención\nporque dejo de prestar atención otra vez",
        "la radio del taxi\ntenía una canción tuya\nel taxista no se dio cuenta",
        "guardé tu carta entre dos libros\nque no leo\ndonde no la voy a encontrar pronto",
    ],
    "ja": [
        "台所の蛇口が一晩中漏れていた\n私は止めなかった\n聞こえないふりをした",
        "電車の窓に\nあなたの息が残っていた\n冷たくも暖かくもなく",
        "手紙を丸めて\nまた広げた\n文字は同じ場所にあった",
        "週末のエレベーターには\n一人だけだった\nもっと好きだと思っていた",
        "三月で時計が止まった\nそれから何も直していない\n時計が止まったままでいい",
    ],
    "fr": [
        "le robinet de la cuisine\na coulé toute la nuit\nje n'ai pas voulu l'arrêter",
        "j'ai gardé ta lettre\nentre deux livres que je ne lis pas\nlà où je ne la retrouverai pas",
        "l'horloge s'est arrêtée en mars\ndepuis je ne répare rien\ndepuis je laisse tout comme ça",
        "le café refroidit deux fois\nparce que j'oublie\nparce que j'oublie encore",
        "j'ai acheté des fleurs inutiles\npour une maison qui n'est pas à nous\npour un week-end qui n'a pas eu lieu",
    ],
}


def _truncate_for_density(lyric: str, density: str) -> str:
    """Mirror generator's per-density truncation rule."""
    lines = lyric.split("\n")
    if density == "low":
        return "\n".join(lines[:1])
    if density == "med":
        return "\n".join(lines[: max(2, len(lines) // 2)])
    return "\n".join(lines)  # high (or unknown)


# ============================================================================
# Natural-language prompt rewrites — used for ~25 % of prompts (broad first,
# then medium) to break the "A {mood} {genre} {piece_noun} {tempo_phrase}."
# template feel.
# ============================================================================

GENRE_SURFACE = {
    "pop": "pop", "rock": "rock", "hip_hop": "hip-hop",
    "classical": "classical", "jazz": "jazz", "electronic": "electronic",
    "folk": "folk", "metal": "metal",
}

LANGUAGE_SURFACE = {"en": "English", "zh": "Chinese", "es": "Spanish",
                     "ja": "Japanese", "fr": "French"}

# Per-genre mood pool for rewrite text (subset of the generator's bank;
# duplicating here keeps the patcher self-contained).
REWRITE_MOODS = {
    "pop": ["sun-soaked", "bittersweet", "anthemic", "wistful", "shimmering"],
    "rock": ["driving", "raw", "anthemic", "stomping", "gritty"],
    "hip_hop": ["smoky", "head-nod", "introspective", "boom-bap-flavored", "late-night"],
    "classical": ["austere", "luminous", "melancholic", "stately", "pastoral"],
    "jazz": ["smoky", "modal", "after-hours", "trio-intimate", "ballad-tempo"],
    "electronic": ["minimal", "deep-house", "ambient-techno", "warm analog", "club-ready"],
    "folk": ["plain-spoken", "wide-sky", "campfire-warm", "lonesome", "tender"],
    "metal": ["bludgeoning", "atmospheric", "doomy", "thrash-paced", "progressive"],
}

TEMPO_SURFACE = {
    "slow_60_90": ["around 75 bpm", "ballad-paced", "slow"],
    "med_90_120": ["around 100 bpm", "mid-tempo", "steady"],
    "fast_120_160": ["around 130 bpm", "upbeat", "around 140 bpm"],
    "very_fast_160_plus": ["around 170 bpm", "very fast", "really driving, 175+ bpm"],
}


def _natural_phrase(strata: dict, rng: random.Random) -> str:
    """Return a natural human-request style prompt text. Mostly English; if
    `strata['language'] != 'en'` and `vocal`, we mention 'lyrics in <lang>'."""
    genre = GENRE_SURFACE[strata["genre"]]
    mood_pool = REWRITE_MOODS.get(strata["genre"], ["warm"])
    mood = rng.choice(mood_pool)
    tempo = rng.choice(TEMPO_SURFACE[strata["tempo_bin"]])
    is_vocal = strata["vocal_vs_instrumental"] == "vocal"
    lang_hint = (f" Lyrics in {LANGUAGE_SURFACE[strata['language']]}."
                  if is_vocal and strata["language"] != "en" else "")
    if not is_vocal:
        lang_hint = " Instrumental — no vocals."

    # 18 distinct templates, mixing imperative / question / casual / mood-first.
    templates = [
        f"Could you make me a {mood} {genre} piece, {tempo}?{lang_hint}",
        f"I'd love a {mood}, {genre}-leaning tune {tempo}.{lang_hint}",
        f"Let's do a {genre} track — {mood}, {tempo}.{lang_hint}",
        f"How about something {mood} and {genre}-flavored, {tempo}?{lang_hint}",
        f"I want a {mood} {genre} thing {tempo}.{lang_hint}",
        f"Make me a short {genre} piece — {mood} feel, {tempo}.{lang_hint}",
        f"Give me a {mood} {genre} number, {tempo}.{lang_hint}",
        f"Something {mood} in the {genre} vein — {tempo}.{lang_hint}",
        f"A {mood} {genre} piece, please — {tempo}.{lang_hint}",
        f"{mood.capitalize()} {genre} mood. {tempo.capitalize()}.{lang_hint}",
        f"Write me a {mood} {genre} cut — {tempo}.{lang_hint}",
        f"Generate a {mood}, {genre}-style piece {tempo}.{lang_hint}",
        f"Can I get a {mood} {genre} track {tempo}?{lang_hint}",
        f"Got a {mood} {genre} tune for me? {tempo.capitalize()}.{lang_hint}",
        f"Something {mood}: a {genre} piece {tempo}.{lang_hint}",
        f"I'm in the mood for {mood} {genre} — {tempo}, if you can.{lang_hint}",
        f"Quick {mood} {genre} number, {tempo}. Keep it tight.{lang_hint}",
        f"Could we try a {mood} {genre} piece {tempo}? Nothing fancy.{lang_hint}",
    ]
    return rng.choice(templates).strip()


# ============================================================================
# Patching logic
# ============================================================================


def _hash_seed(prompt_id: str, namespace: str) -> int:
    """Deterministic per-prompt seed so reruns produce the same patches."""
    h = hashlib.sha256(f"{namespace}:{prompt_id}".encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def patch_held_out_lyric_overlaps(dev: list[Prompt], held: list[Prompt]) -> dict:
    """Replace held-out lyrics that collide with dev's lyric set.

    Replacement source: first try NEW_LYRICS_EN (or NEW_LYRICS_OTHER for the
    matching language); reject any candidate whose density-truncated sig is
    already in `dev` lyric sigs OR in `held` (held-out's own seen sigs).
    """
    dev_lyric_sigs: set[str] = {p.lyrics for p in dev if p.lyrics}
    # Build a fresh source pool per language. We use the per-prompt
    # `lyric_density` to compute the sig.
    new_pool_by_lang: dict[str, list[str]] = {
        "en": list(NEW_LYRICS_EN),
        "zh": list(NEW_LYRICS_OTHER["zh"]),
        "es": list(NEW_LYRICS_OTHER["es"]),
        "ja": list(NEW_LYRICS_OTHER["ja"]),
        "fr": list(NEW_LYRICS_OTHER["fr"]),
    }
    used_in_held: set[str] = set(p.lyrics for p in held if p.lyrics)
    patches = 0
    fallbacks = 0
    for p in held:
        if not p.lyrics:
            continue
        if p.lyrics not in dev_lyric_sigs:
            continue
        # This held-out prompt's lyric collides with dev — replace.
        density = p.strata.get("lyric_density", "med")
        lang = p.strata.get("language", "en")
        # Drop the old sig from used_in_held first, since we'll re-add the new one.
        used_in_held.discard(p.lyrics)
        rng = random.Random(_hash_seed(p.prompt_id, "patch_lyric"))
        source_pool = new_pool_by_lang.get(lang) or new_pool_by_lang["en"]
        rng.shuffle(source_pool)
        new_lyric = None
        for source in source_pool:
            candidate = _truncate_for_density(source, density)
            if candidate not in dev_lyric_sigs and candidate not in used_in_held:
                new_lyric = candidate
                break
        if new_lyric is None:
            # Fallback: accept any new-pool source even if cross-collides
            # (gives us a different sig anyway since the source is brand new).
            new_lyric = _truncate_for_density(source_pool[0], density)
            fallbacks += 1
        p.lyrics = new_lyric
        used_in_held.add(new_lyric)
        patches += 1
    return {"patches": patches, "fallbacks": fallbacks}


def patch_natural_text(prompts: list[Prompt], target_fraction: float = 0.25
                        ) -> dict:
    """Rewrite ~`target_fraction` of prompts into natural-language style.
    Selection: ALL `broad`-specificity prompts first, then `medium` until quota.

    Strata are NOT changed — only `text` and the prompt's `metadata['rewrite']`
    flag. Lyrics are untouched.
    """
    target = int(round(len(prompts) * target_fraction))
    broads = [p for p in prompts if p.strata.get("prompt_specificity") == "broad"]
    mediums = [p for p in prompts if p.strata.get("prompt_specificity") == "medium"]
    # Deterministic order by prompt_id so the patch is reproducible.
    broads.sort(key=lambda p: p.prompt_id)
    mediums.sort(key=lambda p: p.prompt_id)
    chosen = broads[:target]
    if len(chosen) < target:
        chosen.extend(mediums[: target - len(chosen)])
    rewrites = 0
    for p in chosen:
        rng = random.Random(_hash_seed(p.prompt_id, "patch_text"))
        new_text = _natural_phrase(p.strata, rng)
        if not new_text or new_text == p.text:
            continue
        p.text = new_text
        if not isinstance(p.metadata, dict):
            p.metadata = {}
        p.metadata["rewritten_to_natural_style"] = True
        rewrites += 1
    return {"target": target, "rewrites": rewrites,
            "broads_total": len(broads), "mediums_total": len(mediums)}


# ============================================================================
# Validation (mirrors generator validate)
# ============================================================================


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _norm(text: str | None) -> str:
    return " ".join(_WORD_RE.findall(text.lower())) if text else ""


def validate(dev: list[Prompt], held: list[Prompt]) -> list[str]:
    errs: list[str] = []
    for p in dev + held:
        if not p.prompt_id:
            errs.append(f"missing prompt_id on {p!r}")
        if not p.text:
            errs.append(f"{p.prompt_id}: empty text")
        if "TODO" in (p.text or "") or "TODO" in (p.lyrics or ""):
            errs.append(f"{p.prompt_id}: TODO placeholder present")
        if p.strata.get("vocal_vs_instrumental") == "vocal" and not p.lyrics:
            errs.append(f"{p.prompt_id}: vocal prompt has empty lyrics")
        if p.strata.get("vocal_vs_instrumental") == "instrumental" and p.lyrics:
            errs.append(f"{p.prompt_id}: instrumental prompt has non-empty lyrics")
        missing = REQUIRED_STRATA - set(p.strata.keys())
        if missing:
            errs.append(f"{p.prompt_id}: missing strata {sorted(missing)}")
        if p.duration_target <= 0:
            errs.append(f"{p.prompt_id}: nonpositive duration_target")
    all_ids = [p.prompt_id for p in dev + held]
    dup_ids = [i for i, c in Counter(all_ids).items() if c > 1]
    if dup_ids:
        errs.append(f"duplicate prompt_ids: {dup_ids[:5]}…")
    # Combined text+lyrics overlap
    sig_dev = {_norm(p.text + " " + (p.lyrics or "")) for p in dev}
    sig_held = {_norm(p.text + " " + (p.lyrics or "")) for p in held}
    overlap = sig_dev & sig_held
    if overlap:
        errs.append(f"dev↔held-out combined overlap: {len(overlap)}")
    return errs


# ============================================================================
# Report
# ============================================================================


def write_report(out_path: Path, dev: list[Prompt], held: list[Prompt],
                  errors: list[str], lyric_patch_stats: dict,
                  text_patch_stats: dict) -> None:
    rng = random.Random(2026)
    from mprm.data.stratification import stratify
    dev_dist = stratify(dev)
    held_dist = stratify(held)

    def fmt_dist(dist: dict) -> str:
        lines = []
        for k in sorted(dist):
            counts = dist[k]
            total = sum(counts.values())
            items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
            formatted = ", ".join(f"{v}={n} ({n/total*100:.0f}%)" for v, n in items)
            lines.append(f"- **{k}**: {formatted}")
        return "\n".join(lines)

    def fmt_examples(prompts: list[Prompt], rng_: random.Random, n: int) -> str:
        sample = rng_.sample(prompts, min(n, len(prompts)))
        out = []
        for p in sample:
            lyric_disp = (p.lyrics or "(instrumental)").replace("\n", " / ")
            if len(lyric_disp) > 90:
                lyric_disp = lyric_disp[:87] + "…"
            rwflag = " [rewritten]" if (p.metadata or {}).get("rewritten_to_natural_style") else ""
            out.append(f"- **`{p.prompt_id}`**{rwflag} [{p.strata.get('genre')}/"
                        f"{p.strata.get('vocal_vs_instrumental')}/{p.strata.get('language')}, "
                        f"{p.duration_target}s]: {p.text}\n  → _{lyric_disp}_")
        return "\n".join(out)

    # Cross-split lyric-only overlap (post-patch)
    dev_l = {p.lyrics for p in dev if p.lyrics}
    held_l = {p.lyrics for p in held if p.lyrics}
    cross_lyric_overlap = len(dev_l & held_l)

    parts = [
        "# Prompt Generation Report (post-quality-patch)",
        "",
        "Generated by `scripts/generate_real_prompts.py`, then in-place patched",
        "by `scripts/patch_prompts_quality.py` per the PI directive 2026-05-17:",
        "expand the lyric pool, replace held-out lyric collisions, rewrite ~25 %",
        "of broad-style prompts into natural human-request style. Strata are unchanged.",
        "",
        f"- **Dev set**: {len(dev)} prompts → `configs/prompts/dev.jsonl`",
        f"- **Held-out set**: {len(held)} prompts → `configs/prompts/held_out.jsonl`",
        f"- **Lyric collision patches** (held-out lyrics replaced): "
        f"{lyric_patch_stats['patches']} (fallbacks: {lyric_patch_stats['fallbacks']})",
        f"- **Text rewrites** (broad-style → natural language): "
        f"{text_patch_stats['rewrites']} of {len(dev) + len(held)} "
        f"({text_patch_stats['rewrites'] / (len(dev) + len(held)) * 100:.1f} %)",
        f"- **Cross-split lyric-only overlap (post-patch)**: {cross_lyric_overlap}",
        f"- **Validation errors**: {len(errors)}",
        "",
        "## Validation",
        "",
        ("✅ All validation checks passed." if not errors
         else "❌ Validation errors:\n" + "\n".join(f"- {e}" for e in errors[:30])),
        "",
        "## Strata distribution — dev (unchanged by patch)",
        "",
        fmt_dist(dev_dist),
        "",
        "## Strata distribution — held-out (unchanged by patch)",
        "",
        fmt_dist(held_dist),
        "",
        "## 20 representative dev prompts",
        "",
        fmt_examples(dev, rng, 20),
        "",
        "## 20 representative held-out prompts",
        "",
        fmt_examples(held, rng, 20),
        "",
        "## PI review checklist (unchanged)",
        "",
        "- [ ] Confirm none of the lyric fragments are accidentally close to known songs.",
        "- [ ] Confirm the rewritten natural-style prompts still cover the proposal's audit breadth.",
        "- [ ] Confirm the dev/held-out split is acceptable (random with disjoint seeds + lyric-pool partitioning).",
        "- [ ] Decide whether short_30_60s bias is acceptable for M1a (saves GPU-h).",
        "- [ ] If any prompt is unsuitable, edit `configs/prompts/*.jsonl` in place; revalidate via `PYTHONPATH=src python scripts/generate_real_prompts.py --validate-only`.",
        "",
        "`configs/prompts/MISSING_REAL_PROMPTS.flag` is **still in place**. Only the PI may remove it.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="configs/prompts")
    parser.add_argument("--report", default="orbit-research/PROMPT_GENERATION_REPORT.md")
    parser.add_argument("--target-fraction", type=float, default=0.25,
                         help="Fraction of prompts to rewrite into natural style (default 0.25).")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    dev = load_prompts(out_dir / "dev.jsonl")
    held = load_prompts(out_dir / "held_out.jsonl")

    # Snapshot strata distribution BEFORE for sanity-check
    from mprm.data.stratification import stratify
    dev_dist_before = stratify(dev)
    held_dist_before = stratify(held)

    # 1) Lyric overlap patch — held-out lyrics only.
    lyric_stats = patch_held_out_lyric_overlaps(dev, held)
    print(f"Lyric patches: {lyric_stats['patches']} replaced"
          f" (fallbacks: {lyric_stats['fallbacks']})")

    # 2) Natural-style text rewrite across both splits.
    text_stats = patch_natural_text(dev + held, target_fraction=args.target_fraction)
    print(f"Text rewrites: {text_stats['rewrites']} of"
          f" {len(dev) + len(held)} (target {text_stats['target']};"
          f" broads available: {text_stats['broads_total']},"
          f" mediums available: {text_stats['mediums_total']})")

    # Verify strata distributions did NOT change.
    dev_dist_after = stratify(dev)
    held_dist_after = stratify(held)
    if dev_dist_before != dev_dist_after:
        raise RuntimeError("Patch changed dev strata distribution — aborting.")
    if held_dist_before != held_dist_after:
        raise RuntimeError("Patch changed held-out strata distribution — aborting.")
    print("Strata distributions unchanged ✓")

    # 3) Save patched JSONL.
    save_prompts(dev, out_dir / "dev.jsonl")
    save_prompts(held, out_dir / "held_out.jsonl")

    # 4) Re-validate.
    errors = validate(dev, held)
    if errors:
        print(f"VALIDATION ERRORS: {len(errors)}")
        for e in errors[:10]:
            print(f"  - {e}")

    # 5) Report.
    write_report(Path(args.report), dev, held, errors, lyric_stats, text_stats)
    print(f"Wrote report to {args.report}")

    # 6) Flag presence reminder.
    flag = out_dir / "MISSING_REAL_PROMPTS.flag"
    if flag.exists():
        print(f"NOTE: {flag} is STILL PRESENT (correct — PI must remove).")
    else:
        print(f"WARN: {flag} is NOT PRESENT — re-create or confirm PI approval.")

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
