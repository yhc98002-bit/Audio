from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for name in ("bolt_core", "bolt_prepare"):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
prepare = sys.modules["bolt_prepare"]


def test_seed_collision_detection(monkeypatch, tmp_path):
    fake_root = tmp_path
    (fake_root / "paper_prep").mkdir()
    (fake_root / "orbit-research").mkdir()
    (fake_root / "paper_prep/SEED_REGISTRY.md").write_text("base 2040000001\n")
    (fake_root / "orbit-research/RUN_LEDGER.jsonl").write_text("")
    monkeypatch.setattr(prepare, "ROOT", fake_root)
    monkeypatch.setattr(prepare, "OUT", fake_root / "bolt")
    result = prepare.collision_scan(2_040_000_000)
    assert result["status"] == "FAIL"
    assert result["collisions"][0]["seed"] == 2_040_000_001


def test_prompt_leakage_filter_is_explicit():
    source = Path(prepare.__file__).read_text(encoding="utf-8")
    assert 'row["prompt_id"].startswith("dev_")' in source
    assert 'row["prompt_split"] not in {"train", "val"}' in source


def test_genre_allocation_represents_every_available_genre_and_fills_slots():
    pool = [{"genre": "a"}] * 20 + [{"genre": "b"}] * 8 + [{"genre": "c"}] * 2
    allocation = prepare.genre_allocations(pool, 12)
    assert set(allocation) == {"a", "b", "c"}
    assert all(value >= 1 for value in allocation.values())
    assert sum(allocation.values()) == 12
    assert allocation["a"] > allocation["b"] > allocation["c"]
