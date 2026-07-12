from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_evpd_liveconfirm_20260712.py"


def load_module():
    spec = importlib.util.spec_from_file_location("w2_evpd_live", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_manifest_contract_and_crn_formula():
    module = load_module()
    assert len(module.POLICIES) == 4
    seeds = {
        module.SEED_BASE + prompt_rank * 100 + rep
        for prompt_rank in range(64)
        for rep in range(2)
    }
    assert len(seeds) == 128
    assert min(seeds) == 2_035_000_000
    assert max(seeds) == 2_035_006_301
    registry = (ROOT / "paper_prep/SEED_REGISTRY.md").read_text(encoding="utf-8")
    assert "2035006301" in registry


def test_launch_guard_rejects_unsigned_amendment(tmp_path):
    module = load_module()
    amendment = tmp_path / "amendment.md"
    amendment.write_text("W2_AMENDMENT_STATUS = DRAFTED_AWAITING_SIGNATURE\n", encoding="utf-8")
    promotion = tmp_path / "promotion.json"
    promotion.write_text(json.dumps({"CORRECTED_INSTRUMENT_STATUS": "PASS_DUAL_PI_ADOPTED"}), encoding="utf-8")
    try:
        module.launch_guard(amendment, promotion, "not-a-real-hash")
    except ValueError as exc:
        assert "not signed" in str(exc)
    else:
        raise AssertionError("unsigned amendment passed launch guard")


def test_recovery_evpd_and_spine_paths_can_be_versioned():
    module = load_module()
    relative = module.resolve_repo_path("paper_prep/recovery_evpd", "unused")
    assert relative == module.ROOT / "paper_prep/recovery_evpd"
    absolute = module.ROOT / "paper_prep/recovery_spine"
    assert module.resolve_repo_path(str(absolute), "unused") == absolute
