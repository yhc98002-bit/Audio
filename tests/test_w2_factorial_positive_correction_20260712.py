from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_factorial_positive_correction_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_factorial_positive", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sanitizer_removes_negative_vocal_and_lyrics_clauses():
    module = load_module()
    examples = [
        "A folk track. (fully instrumental, no vocals).",
        "A classical piece. Instrumental \u2014 no vocals.",
        "A synth piece. (instrumental piece, no lyrics, no vocal stem).",
        "A jazz song. (no vocals; the lead is the instrument named below).",
    ]
    for value in examples:
        corrected = module.full_positive_text(value)
        assert module.FORBIDDEN_RE.search(corrected) is None
        assert module.base.POSITIVE_TEXT in corrected


def test_all_frozen_factorial_prompts_pass_full_text_zero_lexeme_contract():
    module = load_module()
    prompts = module.read_jsonl(module.base.PROMPTS)
    assert len(prompts) == 32
    corrected = [module.full_positive_text(row["text"]) for row in prompts]
    assert all(module.FORBIDDEN_RE.search(value) is None for value in corrected)
    assert len(set(corrected)) == 32
