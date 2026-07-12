from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper_prep/scripts/build_w2_factorial_spotcheck_20260712.py"


def test_factorial_spotcheck_is_blinded_staged_and_pi_restricted():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"pairs": 20' in source
    assert "pair_staged" in source
    assert 'return v==="pi:Richard"' in source
    assert "PI_SPOTCHECK_NOT_PROMOTION_GATE" in source
    assert "arm_a" in source and "arm_b" in source  # keys-side mapping exists
    assert "public.append" in source
