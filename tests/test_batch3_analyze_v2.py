import json
from pathlib import Path

import pytest

from scripts import batch3_analyze_v2 as module


def test_load_jsonl_strict_rejects_invalid_and_blank(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"ok": 1}\n\n')
    with pytest.raises(ValueError, match="blank"):
        module.load_jsonl_strict(path)
    path.write_text('{bad}\n')
    with pytest.raises(ValueError, match="invalid JSON"):
        module.load_jsonl_strict(path)


def test_selected_candidate_treats_zero_as_valid_score():
    rows = [
        {"completed": True, "gate_pass": 1, "final_common_robust_lcb": 0.0, "attempt": 0},
        {"completed": True, "gate_pass": 1, "final_common_robust_lcb": -0.2, "attempt": 1},
    ]
    assert module.selected_candidate(rows)["attempt"] == 0


def test_expected_cells_include_only_tail_rep2_for_arms4_and6():
    keys = module.expected_unit_keys(["a", "b"], {"b"})
    assert len(keys) == 2 * len(module.ARMS) * 2 + 2
    assert ("b", 4, 2) in keys and ("b", 6, 2) in keys
    assert ("a", 4, 2) not in keys and ("b", 1, 2) not in keys
