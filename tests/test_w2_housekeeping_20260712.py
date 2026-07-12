from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper_prep"


def test_t5_checksum_is_present_and_matches():
    import hashlib

    archive = PAPER / "rater_bundles_20260711/t5_sa3_calibration.zip"
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = (PAPER / "rater_bundles_20260711/SHA256SUMS").read_text(encoding="utf-8")
    assert f"{digest}  {archive.resolve()}" in sums


def test_static_demo_has_real_audio_figures_and_no_missing_references():
    demo = PAPER / "w2_execution_20260712/housekeeping/demo_site"
    html = (demo / "index.html").read_text(encoding="utf-8")
    for relative in [
        "assets/example_A.flac",
        "assets/example_B.flac",
        "assets/fig2_regime_plot.png",
        "assets/fig2_retry_regime_ecdf_forest.png",
        "styles.css",
        "app.js",
    ]:
        assert relative in html
        assert (demo / relative).is_file()
        assert (demo / relative).stat().st_size > 0


def test_hf_upload_is_human_and_environment_gated():
    script = (
        PAPER / "w2_execution_20260712/housekeeping/hf_release/upload_to_hf.py"
    ).read_text(encoding="utf-8")
    assert "--execute" in script
    assert "HF_TOKEN" in script
    assert "HF_REPO_ID" in script
    assert "hf_" not in script
