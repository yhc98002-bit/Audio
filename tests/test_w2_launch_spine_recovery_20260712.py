from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/w2_launch_spine_recovery_20260712.sh"


def test_recovery_launcher_is_probe_manifest_generation_and_memory_gated():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'probe.get("full_replay_authorized_by_probe") is not True' in source
    assert "len(rows) != 4096" in source
    assert "len(latest) != 4096 or failures" in source
    assert "MIN_FREE_MIB" in source
    assert "MPRM_W2_SPINE_OUT" in source
    assert "num-workers 16" in source


def test_recovery_launcher_never_targets_the_failed_default_root():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "spine_reconstruction_torch251_recovery" in source
    assert "tmux kill-session" not in source
