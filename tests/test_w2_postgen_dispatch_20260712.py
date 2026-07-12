from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_postgen_dispatch_20260712.sh"


def test_postgen_dispatch_waits_for_both_cardinalities_and_uses_registered_workers():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "spine=4096" not in source  # it observes rather than fabricates status text
    assert '"$spine" -eq 4096' in source
    assert '"$positive" -eq 1024' in source
    assert "--num-workers 7" in source
    assert "--num-workers 4" in source
    assert "CUDA_VISIBLE_DEVICES" in source
