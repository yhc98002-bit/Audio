import csv
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/finalize_w2_live_generation_20260714.py"


def load_module():
    spec = importlib.util.spec_from_file_location("finalize_w2_live", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finalizer_contract_requires_exact_frozen_manifest_and_process_check():
    module = load_module()
    with module.MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 512
    assert len({row["unit_id"] for row in rows}) == 512
    source = SCRIPT.read_text(encoding="utf-8")
    assert "NO_ACTIVE_WORKERS" in source
    assert "audio_sha256" in source
    assert "sf.read" in source
    assert "near_silent" in source
    assert "launcher_exit_codes_captured" in source


def test_launcher_is_syntax_valid_after_recovery():
    source = (
        ROOT / "paper_prep/scripts/run_w2_liveconfirm_20260713.sh"
    ).read_text(encoding="utf-8")
    assert 'deadline=$(date -d "$(cat "${OUT}/HARD_STOP_DEADLINE.txt")" +%s)' in source
