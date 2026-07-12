from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "paper_prep/scripts/audit_pi_gold_judge_20260711.py"
SPEC = importlib.util.spec_from_file_location("audit_pi_gold_judge_20260711", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_real_pi_gold_judge_audit_is_complete_but_never_auto_passes():
    processed = ROOT / "paper_prep/pi_ratings_20260711/processed"
    result = MODULE.audit(
        ROOT,
        processed / "PI_GOLD_SMOKE.csv",
        ROOT / "paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_smoke_20260711.jsonl",
        processed / "PI_GOLD_SMOKE_JUDGE_SUMMARY.json",
        processed / "PI_GOLD_HELDOUT.csv",
        ROOT / "paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_heldout_20260711.jsonl",
        processed / "PI_GOLD_HELDOUT_JUDGE_SUMMARY.json",
    )
    assert result["judge_validation_status"] == "PI_BLOCKED"
    assert result["smoke"]["calls"] == 30
    assert result["heldout"]["calls"] == 315
    assert result["heldout"]["balanced_accuracy"] > 0.8
    assert result["stratified_500_launched"] is False
    assert result["a_prime_gate_changed"] is False
