import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/build_rater_bundles_20260711.py"
SPEC = importlib.util.spec_from_file_location("build_rater_bundles_20260711", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_source_selection_has_exact_required_cardinalities():
    specs = MODULE.build_rows("test-nonce-not-used-for-production")
    assert {spec["name"]: len(spec["rows"]) for spec in specs} == {
        "t1_decisive": 42,
        "t2_aprime_core": 190,
        "t3_bprime_primary": 80,
        "t4_bprime_reverse": 24,
        "t5_sa3_calibration": 60,
    }


def test_nonce_changes_ids_and_order_tokens_deterministically():
    first = MODULE.opaque_digest("nonce-a", "t1", "source", "id")
    assert first == MODULE.opaque_digest("nonce-a", "t1", "source", "id")
    assert first != MODULE.opaque_digest("nonce-b", "t1", "source", "id")
    assert first != MODULE.opaque_digest("nonce-a", "t1", "source", "order")


def test_builder_fails_closed_without_nonce(monkeypatch, tmp_path):
    monkeypatch.delenv("ADSR_BLINDING_NONCE", raising=False)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(tmp_path / "out")])
    with pytest.raises(SystemExit, match="ADSR_BLINDING_NONCE is required"):
        MODULE.main()


def test_governing_question_wording_is_embedded_verbatim():
    html = MODULE.render_html(
        "test",
        {
            "bundle_id": "test",
            "title": "test",
            "mode": "pair",
            "wording_html": MODULE.QUALITY_WORDING,
            "rows": [],
        },
    )
    assert MODULE.QUALITY_WORDING in html
    assert (
        "Judge musical/audio quality while setting aside whether the clip correctly "
        "contains or omits vocals. Consider production quality, artifacts, musical "
        "coherence, naturalness, and listening quality."
        == MODULE.QUALITY_WORDING
    )
    assert "Do you hear any sound a reasonable listener" in MODULE.LABEL_A_WORDING
    assert "single isolated non-linguistic one-shot shorter than ~2 s" in MODULE.LABEL_B_WORDING


def write_synthetic_bundle(path: Path, rows: int, media: int) -> None:
    path.mkdir()
    (path / "media").mkdir()
    for index in range(media):
        (path / "media" / f"audio_{index}.flac").touch()
    (path / "README").write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    payload = {
        "bundle_id": path.name,
        "title": "test",
        "mode": "label",
        "wording_html": "safe",
        "rows": [{"rating_id": f"r_{index}", "media": "media/x.flac"} for index in range(rows)],
    }
    (path / "index.html").write_text(
        MODULE.render_html("test", payload), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "name,rows,media",
    [
        ("t1_decisive", 42, 42),
        ("t2_aprime_core", 190, 190),
        ("t3_bprime_primary", 80, 160),
        ("t4_bprime_reverse", 24, 48),
        ("t5_sa3_calibration", 60, 60),
    ],
)
def test_bundle_audit_enforces_counts_and_no_admin_fields(tmp_path, name, rows, media):
    bundle = tmp_path / name
    write_synthetic_bundle(bundle, rows, media)
    result = MODULE.audit_bundle(bundle, rows, media)
    assert result["leak_test"] == "PASS"


def test_bundle_audit_rejects_hidden_answer_field(tmp_path):
    bundle = tmp_path / "bad"
    write_synthetic_bundle(bundle, 1, 1)
    text = (bundle / "index.html").read_text(encoding="utf-8")
    marker = '<script id="bundle-data" type="application/json">'
    start = text.index(marker) + len(marker)
    end = text.index("</script>", start)
    payload = json.loads(text[start:end])
    payload["rows"][0]["expected_label"] = "yes"
    text = text[:start] + json.dumps(payload) + text[end:]
    (bundle / "index.html").write_text(text, encoding="utf-8")
    with pytest.raises(AssertionError, match="leaked"):
        MODULE.audit_bundle(bundle, 1, 1)


def test_recorded_production_audit_and_admin_separation():
    output = Path(__file__).parents[1] / "paper_prep/rater_bundles_20260711"
    audit = json.loads((output / "BUNDLE_AUDIT.json").read_text(encoding="utf-8"))
    assert audit["nonce_present"] is True
    assert {
        name: (values["rows"], values["leak_test"])
        for name, values in audit["bundles"].items()
    } == {
        "t1_decisive": (42, "PASS"),
        "t2_aprime_core": (190, "PASS"),
        "t3_bprime_primary": (80, "PASS"),
        "t4_bprime_reverse": (24, "PASS"),
        "t5_sa3_calibration": (60, "PASS"),
    }
    assert len(audit["archives"]) == 5
    for bundle in audit["bundles"]:
        html = (output / bundle / "index.html").read_text(encoding="utf-8")
        assert "human:CXY" in html
        assert "qwen_unvalidated" not in html
    old_admin_paths = [
        Path(__file__).parents[1] / "paper_prep/pi_decisive_packet_20260709/DECISIVE_PACKET_ADMIN.csv",
        Path(__file__).parents[1] / "paper_prep/validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_ADMIN.csv",
        Path(__file__).parents[1] / "paper_prep/validation_B_prime/pi_package_20260709/B_PRIME_ORDERED_ADMIN.csv",
        Path(__file__).parents[1] / "paper_prep/sao/stable_audio_3_medium/label_calibration/SA3_LABEL_CALIBRATION_ADMIN.csv",
    ]
    assert not any(path.exists() for path in old_admin_paths)
