"""Generate 256 dev + 256 held-out original prompts for ACE-Step M1a pre-flight.

Replaces `scripts/prepare_prompts.py` (which only emitted template stubs with
TODO lyrics). This script writes stratified prompts with:
  - per-genre phrase banks (mood / instruments / lyric themes / structural cues)
  - original short lyrics (2-4 lines) for vocal prompts; empty + explicit
    instrumental metadata for instrumental prompts
  - English-dominant (~85%) + small zh/es/ja/fr subset (~15% combined)
  - duration_target biased toward 30-45 s for an affordable early audit
  - dev and held-out drawn from disjoint random pools (seed 42 vs seed 1042)

Lyrics are mini and original; not copied from real songs. PI must still review
before unlocking production — `MISSING_REAL_PROMPTS.flag` is NOT removed by
this script. Run validation via `--validate`; emit a generation report via
`--report orbit-research/PROMPT_GENERATION_REPORT.md`.

Usage:
    python scripts/generate_real_prompts.py \
        --dev-size 256 --held-out-size 256 \
        --out-dir configs/prompts \
        --report orbit-research/PROMPT_GENERATION_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

from mprm.data.prompts import Prompt, save_prompts
from mprm.data.stratification import REQUIRED_STRATA


# ============================================================================
# Per-genre phrase banks. Each genre has mood adjectives, instrument groupings,
# lyric themes (only used for vocal prompts), and structural tags. Designed to
# combine into ~10^4 distinct surface forms without template-feel.
# ============================================================================

_VOCAL_TERM_PATTERN = re.compile(
    r"\b(vocal|vocals|voice|voices|singing|singer|singers|sung|chorus|"
    r"verse|verses|falsetto|hook|harmony|harmonies|chant|chanted|"
    r"a-cappella|acappella|sing-along|backing vocals?|choir|choir-like|"
    r"spoken|spoken-word|refrain|refrains|word(?:less)?)\b",
    re.IGNORECASE
)


def _is_vocal_free(s: str) -> bool:
    """STOP-B-8 Phase-1 (Codex Q1 fix): return False if `s` mentions a vocal
    artifact — used to filter instrument/structure phrases for instrumental
    prompts so we don't end up with text like '...sparse vocal...' on an
    instrumental piece."""
    return not _VOCAL_TERM_PATTERN.search(s)


GENRES = {
    "pop": {
        "moods": ["sun-soaked", "bittersweet", "anthemic", "wistful", "shimmering",
                   "yearning", "crisp", "playful", "earnest", "neon-lit",
                   "spacious", "warmly nostalgic"],
        "instruments": [
            "bright synth pads with a punchy 808",
            "muted electric piano under airy female vocals",
            "warm bass groove with strummed acoustic guitar",
            "glassy keys and a subtle clap pattern",
            "syncopated synth bass and reverb-washed snare",
            "layered choir-like vocal stacks over plucked guitar",
            "minimal piano, soft kick, lone vocal",
            "vintage drum machine and bell-like leads",
        ],
        "lyric_themes": ["small heartbreaks", "summer evenings", "late-night drives",
                          "a phone call you didn't make", "a city that feels new",
                          "the quiet between texts", "starting over slowly"],
        "structure_extras": ["with a sing-along chorus", "with a half-time bridge",
                              "with a falsetto pre-chorus", "with a tight 8-bar hook"],
    },
    "rock": {
        "moods": ["driving", "raw", "anthemic", "bruised", "stomping", "wide-open",
                   "garage-energy", "mid-90s alt-rock", "gritty", "swaggering",
                   "tender-yet-loud", "midwest-emo-tinged"],
        "instruments": [
            "distorted guitars, tight drums, bass walking under the riff",
            "open-chord rhythm guitar, hi-hat counting eighths, snare on 2 and 4",
            "two interlocking guitars, one clean one driven, with a melodic bassline",
            "single-coil guitar tone, brushed snare, a soft Hammond pad",
            "wall of fuzz, kick on every beat, sparse vocal",
            "palm-muted verses opening into a roomy chorus",
        ],
        "lyric_themes": ["a town you outgrew", "what you said in the car",
                          "leaving on a Sunday", "small revolts", "the long way home",
                          "what the radio kept playing"],
        "structure_extras": ["with a quiet-loud-quiet arc",
                              "with a guitar solo over the second chorus",
                              "with an outro that drops to just bass and voice"],
    },
    "hip_hop": {
        "moods": ["smoky", "head-nod", "introspective", "boom-bap-flavored",
                   "trap-inflected", "warm and dusty", "late-night radio",
                   "minimalist", "sample-heavy", "summer-block-party",
                   "vintage soul-flip", "moody"],
        "instruments": [
            "dusty drum break, upright bass, sparse keys, vocal pocket",
            "rolling 808s, snappy hats, soulful Rhodes chops",
            "boom-bap kick-snare, jazz-guitar loop, vinyl crackle",
            "minimal piano riff, low sub, distant strings",
            "syncopated bass slides and a brass-stab sample",
            "wide trap snares with detuned synth bass",
        ],
        "lyric_themes": ["a block that raised you", "first paycheck",
                          "an old hoodie that still smells like home",
                          "a friend who moved away", "what your mom used to say",
                          "the long bus ride", "summers between jobs"],
        "structure_extras": ["with a 16-bar verse and an 8-bar hook",
                              "with two verses framing a sung bridge",
                              "with a beat-switch into the second half"],
    },
    "classical": {
        "moods": ["austere", "luminous", "melancholic", "stately", "playful",
                   "pastoral", "stormy", "contemplative", "sparse and chamber-like",
                   "richly polyphonic", "harmonically restless", "tonally ambiguous"],
        "instruments": [
            "solo piano, mostly mid-register, with sustained pedal",
            "string quartet, with a melodic viola counter-line",
            "woodwind ensemble: flute, clarinet, bassoon",
            "harp arpeggios under a single sustained cello note",
            "piano left-hand ostinato beneath a singing right-hand melody",
            "string orchestra plus solo violin",
        ],
        "lyric_themes": [],  # classical defaults to instrumental
        "structure_extras": ["with an ABA' formal arc",
                              "with a quiet codetta returning the opening motif",
                              "with a contrasting middle section in the relative minor"],
    },
    "jazz": {
        "moods": ["smoky", "modal", "bossa-flavored", "post-bop", "swinging",
                   "introspective", "after-hours", "Coltrane-tinged",
                   "ECM-flavored", "free-leaning", "trio-intimate",
                   "ballad-tempo"],
        "instruments": [
            "upright bass walking under brushed drums, piano comping",
            "trio: piano, bass, drums; head-solo-head form",
            "tenor sax leading a quartet through a modal vamp",
            "guitar trio with hollow-body tone and brushed snare",
            "muted trumpet over a sustained Rhodes chord",
            "vibraphone, bass, and light cymbal washes",
        ],
        "lyric_themes": ["walking home at 3 a.m.", "rain you didn't notice starting",
                          "the bar near 4th", "calling someone you shouldn't",
                          "things left unsaid at dinner"],
        "structure_extras": ["with a 32-bar AABA head",
                              "with an extended solo section over the changes",
                              "with a rubato intro into in-time at bar 9"],
    },
    "electronic": {
        "moods": ["minimal", "deep-house", "ambient-techno", "garage-flavored",
                   "synthwave-leaning", "warm analog", "glitch-tinged",
                   "trance-leaning", "lo-fi", "dub-flavored", "leftfield",
                   "club-ready"],
        "instruments": [
            "four-on-the-floor kick, hi-hats on offbeats, sub bass, evolving pad",
            "syncopated drum machine, side-chained pad, glassy lead",
            "warm analog bass, claps on 2 and 4, slowly opening filter",
            "layered arpeggios with a quarter-note kick and reverb-washed snares",
            "shuffled hats, off-grid percussion, deep sub, sparse vocal chop",
            "broken-beat drums under a Rhodes-flavored synth lead",
        ],
        "lyric_themes": ["dancing alone", "looking for the after-party",
                          "a friend's empty apartment", "what neon does to skin",
                          "going home at sunrise"],
        "structure_extras": ["with a 16-bar build into a release",
                              "with a breakdown at 1:30 and a drop at 1:45",
                              "with two intertwined synth lines panned wide"],
    },
    "folk": {
        "moods": ["plain-spoken", "wide-sky", "campfire-warm", "lonesome",
                   "tender", "wry", "Appalachian", "Celtic-tinged",
                   "windswept", "back-porch", "front-room", "after-dinner"],
        "instruments": [
            "fingerpicked steel-string guitar with a single voice",
            "acoustic guitar, mandolin, upright bass, brushed snare",
            "banjo and fiddle, sometimes a bowed bass",
            "two-part harmony over strummed guitar",
            "harmonium drone under a melodic vocal",
            "pump organ, acoustic guitar, distant violin",
        ],
        "lyric_themes": ["the road back from the coast",
                          "a grandmother's hand on a screen door",
                          "winter in a small town",
                          "what the river kept", "first frost"],
        "structure_extras": ["with three verses and a recurring refrain",
                              "with a wordless harmony bridge",
                              "with a half-spoken outro verse"],
    },
    "metal": {
        "moods": ["bludgeoning", "atmospheric", "post-metal", "doomy",
                   "djent-tinged", "thrash-paced", "blackened-tremolo",
                   "stoner-fuzz", "progressive", "slowcore-heavy",
                   "industrial-edged", "doom-doom-doom"],
        "instruments": [
            "dropped-tuning guitars, double-kick drums, growled vocals",
            "tremolo-picked rhythm guitar, blast beats, layered screams",
            "down-tuned bass walking under a half-time groove",
            "atmospheric clean section opening into a heavy chorus",
            "polyrhythmic riff in 7/8, syncopated drums, layered guitars",
            "fuzzed-out doom riff at 60 bpm, slow kick, room reverb",
        ],
        "lyric_themes": ["something you fed for years",
                          "what stayed after the fire",
                          "the price of silence",
                          "the long climb out"],
        "structure_extras": ["with a clean intro into a heavy main riff",
                              "with a half-time breakdown at 2:00",
                              "with an instrumental coda built on the opening motif"],
    },
}

TEMPO_PHRASES = {
    "slow_60_90": ["a slow", "at a gentle tempo around 75 bpm", "ballad-paced",
                    "lingering", "around 80 bpm"],
    "med_90_120": ["at mid-tempo around 105 bpm", "with a steady beat near 100 bpm",
                    "around 110 bpm", "at a comfortable swing"],
    "fast_120_160": ["upbeat around 130 bpm", "driving at 140 bpm",
                      "energetic around 135 bpm", "at a brisk 145 bpm"],
    "very_fast_160_plus": ["frantic, around 170 bpm", "very fast, 175+ bpm",
                            "blistering 180 bpm", "double-time at 168 bpm"],
}

LANGUAGES = {"en": "English", "zh": "Chinese (Mandarin)", "es": "Spanish",
              "ja": "Japanese", "fr": "French"}

# ============================================================================
# Mini original lyrics. 2-4 lines each. Never copied from real songs.
# Indexed by language. Vocal prompts pick from the matching language pool;
# instrumental prompts get None. Lyric density is enforced separately.
# ============================================================================

FUSION_PAIRS = [
    ("hip_hop", "jazz"), ("electronic", "folk"), ("rock", "electronic"),
    ("classical", "electronic"), ("metal", "jazz"), ("pop", "hip_hop"),
    ("folk", "hip_hop"), ("jazz", "electronic"), ("classical", "folk"),
]
PIECE_NOUNS = ["song", "piece", "track", "tune", "number", "cut", "composition"]

ORIGINAL_LYRICS_BY_LANG = {
    "en": [
        "left my keys on the windowsill\nthe morning came in sideways\ncall me when the air feels different",
        "I keep the porch light on\neven in summer\neven when no one is coming",
        "we walked the long way home\nso the song wouldn't end\nso the streetlights wouldn't notice",
        "the kettle remembered\neverything I forgot\nin a kitchen I will not return to",
        "winter took its time\nthe roof learned a new noise\nI started saying your name out loud again",
        "I taught myself to hum the bridge\nbefore I learned the words\nbefore I knew the song was about leaving",
        "the lights along the river\ndo not ask where I have been\nthey only count me back",
        "I keep a folded napkin\nwith your handwriting on it\nlike I'm trying to remember a phone number",
        "the radio knew\nthe radio always knew\nthe radio kept it to itself",
        "I emptied my pockets at the airport\nand most of what fell out\nwas you",
        "if the door is open\nit's open for you\nif it's closed I am working on it",
        "we will meet again\nin a small town we never named\nthat will know us anyway",
        "the bus pulled away\nwith my better answer in it\nand I am still standing here",
        "I packed light\nfor a place I would not stay\nfor a person I would not become",
        "you said the rain stops\nyou said the rain always stops\nI am still listening",
        "I left the lamp on\nfor the version of you that might come back\nfor the version of me that might let you",
        "the same dog\non the same corner\nat the same hour every winter",
        "a song my mother hummed\nwhile cutting onions\nwhile pretending not to cry",
        "I keep the receipts\nfor a year I cannot return\nfor a closet you'll never see",
        "we said we would write\nwe said we would call\nthe ceiling fan kept its end of the deal",
        "I'm not waiting up\nI'm just awake\nthe difference matters this week",
        "tell me again\nabout the boat\nabout the lake\nabout the silence",
        "you taught me a chord\nI never learned its name\nI play it when no one is in the room",
        "if I write you a letter\nit will be short\nit will be true\nit will not be sent",
        "the fluorescent light hummed\nthrough the dinner\nthrough the silence after the dinner",
        "I am building a house\nfrom what you didn't take\nit is mostly windows",
        "the kid next door\nasked who I was waiting for\nI didn't have a name yet",
        "summer happens\nwhether or not we attend\nsomeone has to lock the gate",
        "we set the table for four\nbecause we always did\nbecause it felt like a small act of war",
        "I keep my receipts\nin the same drawer\nas your handwriting\nas the train tickets",
        "the laundry never ended\nthe seasons changed without warning\nI taught myself to fold sheets alone",
        "the bus to the coast\nleaves at four-fifteen\nI have been pretending to want to get on it",
        "we counted the streetlights\nbetween two apartments\nbetween two lives we did not name yet",
        "I put the photograph back\nin the back of the drawer\nwhere you used to keep the spare key",
        "you used to say\nthe rain has a memory\nI am starting to believe it now",
        "no one was hurt\nno one was sorry\nno one is sleeping tonight",
        "I left a note on the fridge\nthat said be careful with the milk\nthat said I love you in a smaller font",
        "the old hotel sign\nflickers on and off in the rain\nthe same hour every Sunday",
        "we forgot the umbrella\nwe forgot most things actually\nwe are good at most things actually",
        "I bought a new map\nfor a city I am not moving to\nfor a friend I am not calling",
        "the diner stays open all night\nbecause someone always shows up at three\nbecause someone always doesn't",
        "I waited for the song\nI waited for the radio\nI waited for you to remember the lyrics",
        "you said be kind to the day\nyou said be kind to yourself\nI am still trying to know the difference",
        "the elevator stopped\nbetween two floors\nlong enough for me to forget what I was carrying",
        "if love is a small room\nI keep walking out of it\nlooking for a bigger one",
        "the radio in the kitchen\nplayed a song you almost knew\nyou hummed the wrong part on purpose",
        "the lake had no ducks today\nthe lake had no excuse\nI sat by the lake anyway",
        "we used to count the planes\nfrom your father's roof\nfrom before they painted it green",
        "I left the umbrella in the cab\nI left the receipt at the bar\nI left a lot of things at the bar",
        "tomorrow is a list of small things\nthat I will not do\nthat I have not learned to mind",
        "winter is six months long\nthen it is over\nthen it is six months long again",
    ],
    "zh": [
        "灯还亮着\n屋里没人\n我不打算走得太远",
        "雨停了又下\n你说的话还在\n地铁口的风也在",
        "我把信折了三次\n才放进口袋\n才决定不寄出去",
        "桌子上有一杯凉茶\n没有人喝\n没有人收",
        "如果天亮了\n我们就不说昨晚的事\n我们就走到地铁口分手",
    ],
    "es": [
        "dejé las llaves en la ventana\nla mañana llegó de lado\nllámame cuando el aire cambie",
        "tomamos el camino largo\npara que la canción no terminara\npara que las farolas no se enteraran",
        "el invierno se tomó su tiempo\nel techo aprendió un ruido nuevo\nempecé a decir tu nombre en voz alta otra vez",
        "hay un perro en la misma esquina\na la misma hora\ncada invierno",
    ],
    "ja": [
        "鍵を窓辺に置いてきた\n朝が横から入ってきた\n空気が変わったら電話して",
        "ポーチの灯りはつけておく\n夏でも\n誰も来なくても",
        "雪が降る前の沈黙\n屋根が新しい音を覚えた\n君の名前を声に出してみた",
    ],
    "fr": [
        "j'ai laissé mes clés sur le rebord\nle matin est entré de travers\nappelle-moi quand l'air aura changé",
        "on a pris le long chemin\npour que la chanson ne finisse pas\npour que les lampadaires ne sachent rien",
        "l'hiver a pris son temps\nle toit a appris un bruit\nje me suis remis à dire ton prénom",
    ],
}

INSTRUMENTAL_TAGS = [
    "fully instrumental, no vocals",
    "instrumental piece, no lyrics, no vocal stem",
    "no vocals; the lead is the instrument named below",
    "purely instrumental; treat lyrics field as empty",
]


# ============================================================================
# Stratum definitions (must match `mprm.data.stratification.REQUIRED_STRATA`)
# ============================================================================

GENRE_KEYS = list(GENRES.keys())
TEMPO_BINS = ["slow_60_90", "med_90_120", "fast_120_160", "very_fast_160_plus"]
VOCAL_KEYS = ["vocal", "instrumental"]
LYRIC_DENSITIES = ["high", "med", "low", "n_a_instrumental"]
STRUCTURES = ["simple_AB", "AABA", "verse_chorus", "complex_multi_section"]
LANGUAGE_KEYS = ["en", "zh", "es", "ja", "fr"]
SPECIFICITY = ["broad", "medium", "specific"]
LENGTH_BINS = ["short_30_60s", "med_60_90s"]   # avoid long_90_120s in M1a early audit

LANGUAGE_WEIGHTS = {"en": 0.85, "zh": 0.06, "es": 0.04, "ja": 0.03, "fr": 0.02}
DURATION_TARGETS = {"short_30_60s": (30.0, 45.0),     # uniform in this range
                    "med_60_90s": (60.0, 75.0)}


# ============================================================================
# Generation
# ============================================================================


def _weighted_choice(rng: random.Random, choices: list, weights: dict | list) -> any:
    """Choice with optional dict-keyed weights."""
    if isinstance(weights, dict):
        w = [weights.get(c, 1.0) for c in choices]
    else:
        w = list(weights)
    total = sum(w)
    r = rng.uniform(0, total)
    s = 0.0
    for c, wi in zip(choices, w):
        s += wi
        if r <= s:
            return c
    return choices[-1]


def _pick_strata(rng: random.Random) -> dict:
    """Draw a stratified prompt cell. Instrumental ⇒ lyric_density=n_a_instrumental.
    Some genres (classical) skew heavily instrumental."""
    genre = rng.choice(GENRE_KEYS)
    # Classical and (mostly) jazz lean instrumental; pop/rock/hip_hop lean vocal.
    p_vocal = {"pop": 0.85, "rock": 0.80, "hip_hop": 0.95, "folk": 0.70,
               "metal": 0.70, "electronic": 0.45, "jazz": 0.35, "classical": 0.10}[genre]
    vocal = "vocal" if rng.random() < p_vocal else "instrumental"
    if vocal == "vocal":
        lyric_density = rng.choice(["high", "med", "low"])
    else:
        lyric_density = "n_a_instrumental"

    tempo = rng.choice(TEMPO_BINS)
    structure = rng.choice(STRUCTURES)
    language = (_weighted_choice(rng, LANGUAGE_KEYS, LANGUAGE_WEIGHTS)
                if vocal == "vocal" else "en")  # instrumental: language is metadata-only
    specificity = rng.choice(SPECIFICITY)
    length_bin = rng.choices(LENGTH_BINS, weights=[0.8, 0.2])[0]  # bias short

    return {
        "genre": genre,
        "tempo_bin": tempo,
        "vocal_vs_instrumental": vocal,
        "lyric_density": lyric_density,
        "structural_complexity": structure,
        "language": language,
        "prompt_specificity": specificity,
        "length_bin": length_bin,
    }


def _compose_text(strata: dict, rng: random.Random,
                   fusion: tuple[str, str] | None = None) -> str:
    """Build a prompt text string with variety, NOT a strict template.

    If `fusion` is given (genre_a, genre_b) where genre_a is the primary genre,
    we describe a genre-fusion piece drawing moods from both. This gives the
    M1a audit some "unusual genre fusion" coverage per the PI spec.
    """
    primary = strata["genre"]
    g = GENRES[primary]
    # STOP-B-8 Phase-1 + cycle-2 (Codex Q1 follow-up): for instrumental prompts,
    # filter moods, instruments, and structure_extras through _is_vocal_free()
    # so the prompt text doesn't contradict the strata. Mood filtering matters
    # because adjectives like "plain-spoken" trip the regex even though they
    # are nominally tone descriptors.
    if strata["vocal_vs_instrumental"] == "instrumental":
        mood_pool = [m for m in g["moods"] if _is_vocal_free(m)] or g["moods"]
        instr_pool = [i for i in g["instruments"] if _is_vocal_free(i)] or g["instruments"]
    else:
        mood_pool = g["moods"]
        instr_pool = g["instruments"]
    mood = rng.choice(mood_pool)
    instrument = rng.choice(instr_pool)
    tempo_phrase = rng.choice(TEMPO_PHRASES[strata["tempo_bin"]])
    piece_noun = rng.choice(PIECE_NOUNS)

    genre_phrase = primary
    if fusion is not None and fusion[1] != primary:
        # E.g. "hip_hop × jazz" fusion. Drop underscores for readability.
        # STOP-B-8 Phase-1 cycle-2 (Codex Q1 follow-up final): also filter the
        # secondary genre's mood pool through _is_vocal_free for instrumental
        # prompts, so e.g. "plain-spoken" from folk doesn't leak into an
        # instrumental fusion piece's text.
        other = fusion[1]
        other_moods = GENRES[other]["moods"]
        if strata["vocal_vs_instrumental"] == "instrumental":
            other_moods = [m for m in other_moods if _is_vocal_free(m)] or other_moods
        other_mood = rng.choice(other_moods)
        genre_phrase = (f"{primary.replace('_', '-')} × {other.replace('_', '-')} fusion "
                         f"({other_mood} touches)")

    article = "An" if mood[0].lower() in "aeiou" else "A"

    parts = []
    if strata["prompt_specificity"] == "broad":
        parts.append(f"{article} {mood} {genre_phrase} {piece_noun} {tempo_phrase}.")
    elif strata["prompt_specificity"] == "medium":
        parts.append(f"{article} {mood} {genre_phrase} {piece_noun} {tempo_phrase}, "
                      f"featuring {instrument}.")
    else:  # specific
        # STOP-B-8 Phase-1 (Codex Q1 fix): same vocal-term filter for structure
        # extras when the prompt is instrumental (e.g. drop "with a sing-along
        # chorus" on instrumental pieces).
        struct_pool = (g["structure_extras"] if strata["vocal_vs_instrumental"] == "vocal"
                        else [s for s in g["structure_extras"] if _is_vocal_free(s)])
        struct_extra = (rng.choice(struct_pool) if struct_pool else "")
        parts.append(f"{article} {mood} {genre_phrase} {piece_noun} {tempo_phrase}, "
                      f"featuring {instrument}")
        # STOP-B-8 Phase-1 cycle-2 (Codex Q1 follow-up): instrumental prompts get
        # vocal-free structural language. "verse-chorus form" is a literal
        # structural label that conflicts with `vocal_vs_instrumental == "instrumental"`,
        # even though the label is shape-only.
        is_instr = strata["vocal_vs_instrumental"] == "instrumental"
        if strata["structural_complexity"] == "AABA":
            parts.append("in 32-bar AABA form")
        elif strata["structural_complexity"] == "verse_chorus":
            parts.append("in alternating-section form" if is_instr else "in verse-chorus form")
        elif strata["structural_complexity"] == "complex_multi_section":
            parts.append("with a multi-section arc")
        else:
            parts.append("in a simple two-section form")
        if struct_extra:
            parts.append(struct_extra)
        parts.append(f"in {LANGUAGES[strata['language']]}"
                     if strata["vocal_vs_instrumental"] == "vocal"
                     else f"({rng.choice(INSTRUMENTAL_TAGS)})")
        return ", ".join(parts) + "."

    if strata["vocal_vs_instrumental"] == "vocal":
        parts.append(f"Lyrics in {LANGUAGES[strata['language']]}.")
    else:
        parts.append(f"({rng.choice(INSTRUMENTAL_TAGS)}).")
    return " ".join(parts)


def _compose_lyrics(strata: dict, rng: random.Random,
                     used_sigs: set[str] | None = None,
                     attempts: int = 20) -> str | None:
    """STOP-B-8 Phase-1 (Codex Q2 fix): try up to `attempts` times to draw a
    lyric signature not in `used_sigs`. Falls back to a random pick after that.
    The density truncation creates new signatures from the same source lyric,
    so the effective unique-signature space is ~3× the pool size per language."""
    if strata["vocal_vs_instrumental"] != "vocal":
        return None
    pool = ORIGINAL_LYRICS_BY_LANG.get(strata["language"]) or ORIGINAL_LYRICS_BY_LANG["en"]
    used_sigs = used_sigs if used_sigs is not None else set()

    def _trim(lyric: str) -> str:
        lines = lyric.split("\n")
        if strata["lyric_density"] == "low":
            lines = lines[:1]
        elif strata["lyric_density"] == "med":
            lines = lines[:max(2, len(lines) // 2)]
        return "\n".join(lines)

    for _ in range(attempts):
        candidate = _trim(rng.choice(pool))
        if candidate not in used_sigs:
            return candidate
    # Fallback: accept duplicate after attempts exhausted.
    return _trim(rng.choice(pool))


def _compose_structure_hint(strata: dict, rng: random.Random) -> str | None:
    if strata["prompt_specificity"] == "broad":
        return None
    mapping = {
        "simple_AB": "AB",
        "AABA": "AABA",
        "verse_chorus": "verse-chorus-verse",
        "complex_multi_section": "intro-A-B-A'-bridge-A''",
    }
    return mapping.get(strata["structural_complexity"])


def generate_prompt(idx: int, prefix: str, rng: random.Random,
                     fusion_rate: float = 0.10,
                     used_lyric_sigs: set[str] | None = None) -> Prompt:
    """Generate one prompt; ~`fusion_rate` of prompts use a cross-genre fusion.

    STOP-B-8 Phase-1 (Codex Q2 fix): if `used_lyric_sigs` is given, the lyric
    composer tries to avoid sigs already in that set. Caller is responsible
    for updating the set with the chosen lyric after each call.
    """
    strata = _pick_strata(rng)
    fusion = None
    if rng.random() < fusion_rate:
        candidates = [pair for pair in FUSION_PAIRS if pair[0] == strata["genre"]]
        if candidates:
            fusion = rng.choice(candidates)
    text = _compose_text(strata, rng, fusion=fusion)
    lyrics = _compose_lyrics(strata, rng, used_sigs=used_lyric_sigs)
    structure_hint = _compose_structure_hint(strata, rng)
    lo, hi = DURATION_TARGETS[strata["length_bin"]]
    duration = round(rng.uniform(lo, hi), 1)
    pid = f"{prefix}_{idx:04d}"
    metadata = {
        "generator": "scripts/generate_real_prompts.py",
        "schema_version": "1.1",
        "generator_seed": rng.getstate()[1][0],
    }
    if strata["vocal_vs_instrumental"] == "instrumental":
        metadata["instrumental"] = True
    if fusion is not None:
        metadata["fusion_with"] = fusion[1]
    return Prompt(
        prompt_id=pid,
        text=text,
        lyrics=lyrics,
        structure_hint=structure_hint,
        duration_target=duration,
        metadata=metadata,
        strata=strata,
    )


def _generate_split(prefix: str, n: int, seed: int,
                     forbidden_text_sigs: set[str] | None = None,
                     forbidden_lyric_sigs: set[str] | None = None,
                     max_attempts_per_slot: int = 8) -> list[Prompt]:
    """Generate one split, regenerating any prompt whose text duplicates a
    prompt already in this split OR in `forbidden_text_sigs` (e.g. the dev
    split when generating held-out). STOP-B-8 Phase-1 (Codex Q2 fix): also
    tracks lyric signatures across both the within-split history AND any
    `forbidden_lyric_sigs` (e.g. dev lyric sigs when generating held-out)
    so the lyric composer avoids them."""
    rng = random.Random(seed)
    forbidden_text_sigs = set(forbidden_text_sigs or set())
    used_lyric_sigs = set(forbidden_lyric_sigs or set())
    out: list[Prompt] = []
    seen_text: set[str] = set()
    for i in range(n):
        for attempt in range(max_attempts_per_slot):
            p = generate_prompt(i, prefix, rng, used_lyric_sigs=used_lyric_sigs)
            t_sig = p.text
            if t_sig in forbidden_text_sigs or t_sig in seen_text:
                continue
            seen_text.add(t_sig)
            if p.lyrics:
                used_lyric_sigs.add(p.lyrics)
            out.append(p)
            break
        else:
            # Fell through max_attempts: accept the last (rare with a deep bank).
            out.append(p)
            seen_text.add(p.text)
            if p.lyrics:
                used_lyric_sigs.add(p.lyrics)
    return out


# ============================================================================
# Validation
# ============================================================================

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _normalize_for_dedup(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(_WORD_RE.findall(text.lower()))


def validate(dev: list[Prompt], held: list[Prompt]) -> list[str]:
    """Return list of error strings; empty list = valid."""
    errors: list[str] = []

    # 1) required fields + types
    for p in dev + held:
        if not p.prompt_id:
            errors.append(f"missing prompt_id on prompt {p!r}")
        if not p.text:
            errors.append(f"{p.prompt_id}: empty text")
        if "TODO" in (p.text or "") or "TODO" in (p.lyrics or ""):
            errors.append(f"{p.prompt_id}: TODO placeholder present")
        if not isinstance(p.strata, dict):
            errors.append(f"{p.prompt_id}: strata is not a dict")
            continue
        missing_strata = REQUIRED_STRATA - set(p.strata.keys())
        if missing_strata:
            errors.append(f"{p.prompt_id}: missing strata {sorted(missing_strata)}")
        # Vocal/lyric consistency
        if p.strata.get("vocal_vs_instrumental") == "vocal" and not p.lyrics:
            errors.append(f"{p.prompt_id}: vocal prompt has empty lyrics")
        if p.strata.get("vocal_vs_instrumental") == "instrumental" and p.lyrics:
            errors.append(f"{p.prompt_id}: instrumental prompt has non-empty lyrics")
        if p.duration_target <= 0:
            errors.append(f"{p.prompt_id}: nonpositive duration_target {p.duration_target}")

    # 2) Duplicate prompt_id
    all_ids = [p.prompt_id for p in dev + held]
    dup_ids = [i for i, c in Counter(all_ids).items() if c > 1]
    if dup_ids:
        errors.append(f"duplicate prompt_ids: {dup_ids[:5]}…")

    # 3) Dev/held-out leakage by normalized text+lyrics
    sig_dev = {_normalize_for_dedup(p.text + " " + (p.lyrics or "")) for p in dev}
    sig_held = {_normalize_for_dedup(p.text + " " + (p.lyrics or "")) for p in held}
    overlap = sig_dev & sig_held
    if overlap:
        errors.append(f"dev↔held-out exact-text overlap: {len(overlap)} duplicates")

    # 4) Intra-split duplicate normalized text+lyrics
    for name, group in [("dev", dev), ("held_out", held)]:
        sigs = Counter(_normalize_for_dedup(p.text + " " + (p.lyrics or "")) for p in group)
        intra_dups = [s for s, c in sigs.items() if c > 1]
        if intra_dups:
            errors.append(f"{name}: {len(intra_dups)} intra-split duplicate sigs")

    return errors


def strata_distribution(prompts: list[Prompt]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for k in sorted(REQUIRED_STRATA):
        out[k] = dict(Counter(p.strata.get(k, "<missing>") for p in prompts))
    return out


# ============================================================================
# Report
# ============================================================================


def _format_dist(dist: dict[str, dict]) -> str:
    lines = []
    for k in sorted(dist):
        counts = dist[k]
        total = sum(counts.values())
        items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        formatted = ", ".join(f"{v}={n} ({n/total*100:.0f}%)" for v, n in items)
        lines.append(f"- **{k}**: {formatted}")
    return "\n".join(lines)


def _format_examples(prompts: list[Prompt], rng: random.Random, n: int) -> str:
    sample = rng.sample(prompts, min(n, len(prompts)))
    lines = []
    for p in sample:
        lyric_disp = (p.lyrics or "(instrumental)").replace("\n", " / ")
        if len(lyric_disp) > 80:
            lyric_disp = lyric_disp[:77] + "…"
        lines.append(f"- **`{p.prompt_id}`** [{p.strata.get('genre')}/"
                      f"{p.strata.get('vocal_vs_instrumental')}/{p.strata.get('language')}, "
                      f"{p.duration_target}s]: {p.text}\n  → _{lyric_disp}_")
    return "\n".join(lines)


def write_report(out_path: Path, dev: list[Prompt], held: list[Prompt],
                  errors: list[str]) -> None:
    rng = random.Random(2026)
    dev_dist = strata_distribution(dev)
    held_dist = strata_distribution(held)
    parts = [
        "# Prompt Generation Report",
        "",
        "Generated by `scripts/generate_real_prompts.py`. See script for the per-genre",
        "phrase banks, original lyric pools, and stratification logic.",
        "",
        f"- **Dev set**: {len(dev)} prompts → `configs/prompts/dev.jsonl`",
        f"- **Held-out set**: {len(held)} prompts → `configs/prompts/held_out.jsonl`",
        f"- **Validation errors**: {len(errors)}",
        "",
        "## Validation",
        "",
        ("✅ All validation checks passed." if not errors
         else "❌ Validation errors:\n" + "\n".join(f"- {e}" for e in errors[:30])),
        "",
        "## Strata distribution — dev",
        "",
        _format_dist(dev_dist),
        "",
        "## Strata distribution — held-out",
        "",
        _format_dist(held_dist),
        "",
        "## 20 representative dev prompts",
        "",
        _format_examples(dev, rng, 20),
        "",
        "## 20 representative held-out prompts",
        "",
        _format_examples(held, rng, 20),
        "",
        "## PI review checklist",
        "",
        "- [ ] Confirm none of the lyric fragments are accidentally close to known songs.",
        "- [ ] Confirm genre coverage matches the proposal's intended audit breadth.",
        "- [ ] Confirm the dev/held-out split is acceptable (random with disjoint seeds).",
        "- [ ] Decide whether short_30_60s bias is acceptable for M1a (saves GPU-h).",
        "- [ ] If any prompt is unsuitable, edit `configs/prompts/*.jsonl` in place; the validation rules in this script can be re-run via `python scripts/generate_real_prompts.py --validate-only`.",
        "",
        "If acceptable, remove `configs/prompts/MISSING_REAL_PROMPTS.flag` and mark approval in `orbit-research/PROMPT_READY_FOR_PI_REVIEW.md` (created by the generator if validation passed).",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")


def write_pi_review_marker(out_path: Path, dev: list[Prompt], held: list[Prompt]) -> None:
    parts = [
        "# Prompts ready for PI review — STOP-B-8 phase 1",
        "",
        f"- Dev prompts: {len(dev)} at `configs/prompts/dev.jsonl`",
        f"- Held-out prompts: {len(held)} at `configs/prompts/held_out.jsonl`",
        "- Validation: all script-level checks passed (see `PROMPT_GENERATION_REPORT.md`).",
        "- `configs/prompts/MISSING_REAL_PROMPTS.flag` is **still in place** — only the PI",
        "  may remove it after reviewing the 40 representative examples in the report.",
        "",
        "## What \"approval\" means here",
        "",
        "By removing the flag, the PI confirms:",
        "1. The lyric fragments are not copies / near-copies of real songs.",
        "2. The strata coverage matches the proposal's audit intent.",
        "3. The dev/held-out split is acceptable.",
        "4. The duration bias (mostly 30-60s) is acceptable for M1a GPU cost.",
        "",
        "## To approve",
        "",
        "```bash",
        "rm configs/prompts/MISSING_REAL_PROMPTS.flag",
        "echo \"approved by $(whoami) at $(date -u +%Y-%m-%dT%H:%M:%SZ)\" \\",
        "  >> orbit-research/PROMPT_READY_FOR_PI_REVIEW.md",
        "```",
        "",
        "## To reject and regenerate",
        "",
        "```bash",
        "# edit scripts/generate_real_prompts.py phrase banks / lyric pools",
        "PYTHONPATH=src python scripts/generate_real_prompts.py \\",
        "  --report orbit-research/PROMPT_GENERATION_REPORT.md",
        "```",
        "",
        "## Approval log (append below this line)",
        "",
    ]
    out_path.write_text("\n".join(parts), encoding="utf-8")


# ============================================================================
# CLI
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-size", type=int, default=256)
    parser.add_argument("--held-out-size", type=int, default=256)
    parser.add_argument("--dev-seed", type=int, default=42)
    parser.add_argument("--held-out-seed", type=int, default=1042)
    parser.add_argument("--out-dir", default="configs/prompts")
    parser.add_argument("--report", default="orbit-research/PROMPT_GENERATION_REPORT.md")
    parser.add_argument("--pi-review-marker",
                         default="orbit-research/PROMPT_READY_FOR_PI_REVIEW.md")
    parser.add_argument("--validate-only", action="store_true",
                         help="Skip generation; load existing JSONL and re-validate.")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    if args.validate_only:
        from mprm.data.prompts import load_prompts
        dev = load_prompts(out_dir / "dev.jsonl")
        held = load_prompts(out_dir / "held_out.jsonl")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        # Generate dev first, then held-out forbidding dev's exact text sigs to
        # avoid cross-split exact-text leakage.
        dev = _generate_split("dev", args.dev_size, args.dev_seed)
        dev_text_sigs = {p.text for p in dev}
        # STOP-B-8 Phase-1 + Codex Q2 (refined): intra-split lyric dedup only.
        # Forbidding cross-split lyric sigs would starve held-out (~158 vocal
        # prompts × ~186 distinct lyric sigs total), causing collapse to random
        # reuse. Cross-split lyric-only overlap is acceptable since two prompts
        # with the same lyric but different genre/mood/tempo/instrument are
        # methodologically distinct — and the validator's combined text+lyrics
        # dedup still enforces real prompt-level uniqueness.
        held = _generate_split("held_out", args.held_out_size, args.held_out_seed,
                                  forbidden_text_sigs=dev_text_sigs)
        save_prompts(dev, out_dir / "dev.jsonl")
        save_prompts(held, out_dir / "held_out.jsonl")

    errors = validate(dev, held)

    write_report(Path(args.report), dev, held, errors)

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s). See {args.report}.")
        for e in errors[:10]:
            print(f"  - {e}")
        return 1

    write_pi_review_marker(Path(args.pi_review_marker), dev, held)
    print(f"OK: wrote {len(dev)} dev + {len(held)} held-out prompts to {out_dir}.")
    print(f"  Report: {args.report}")
    print(f"  PI review marker: {args.pi_review_marker}")
    print(f"  `configs/prompts/MISSING_REAL_PROMPTS.flag` is STILL PRESENT;"
          f" PI must approve before removal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
