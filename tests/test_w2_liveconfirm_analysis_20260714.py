import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/analyze_w2_liveconfirm_20260714.py"


def load_module():
    spec = importlib.util.spec_from_file_location("analyze_w2_live", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_analysis_deduplicates_exact_rows_and_rejects_conflicts():
    module = load_module()
    row = {"unit_id": "u", "record_type": "slot", "slot": 0, "status": "COMPLETE"}
    rows, duplicates = module.deduplicate([row, dict(row)])
    assert rows == [row]
    assert duplicates == 1
    conflict = {**row, "status": "ABORTED"}
    try:
        module.deduplicate([row, conflict])
    except ValueError as exc:
        assert "conflicting live ledger duplicate" in str(exc)
    else:
        raise AssertionError("conflicting duplicate passed")


def test_live_analysis_contract_is_frozen_and_fail_closed_while_running():
    module = load_module()
    manifest = list(csv.DictReader(module.MANIFEST.open(newline="", encoding="utf-8")))
    assert len(manifest) == 64 * 4 * 2
    assert len({row["unit_id"] for row in manifest}) == 512
    source = SCRIPT.read_text(encoding="utf-8")
    assert "BOOTSTRAP_REPS = 20_000" in source
    assert "BOOTSTRAP_SEED = 2026071406" in source
    assert '"LIVE_CONFIRM_RESULT": "PI_CALL_PENDING" if mechanical' in source
    assert "No PASS is issued automatically" in source
    if "LIVE_CONFIRM_STATUS = RUNNING" in module.TERMINAL.read_text(encoding="utf-8"):
        try:
            module.analyze()
        except RuntimeError as exc:
            assert "not terminal" in str(exc)
        else:
            raise AssertionError("running live generation was analyzed as terminal")
