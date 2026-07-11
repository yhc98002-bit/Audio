import csv
import importlib.util
import json
import subprocess
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


def test_v2_selects_only_affected_bundles_and_preserves_source_order():
    nonce = "test-nonce-not-used-for-production"
    v1 = {spec["name"]: spec for spec in MODULE.build_rows(nonce)}
    v2 = {spec["name"]: spec for spec in MODULE.build_v2_rows(nonce)}
    assert set(v2) == {
        "t1_decisive_v2",
        "t3_bprime_primary_v2",
        "t4_bprime_reverse_v2",
    }
    for new_name, old_name in MODULE.V2_IDENTITY_NAMES.items():
        new = v2[new_name]
        old = v1[old_name]
        id_field = old["id_field"]
        assert new["identity_name"] == old_name
        assert [row[id_field] for row in new["rows"]] == [
            row[id_field] for row in old["rows"]
        ]
        assert [
            MODULE.opaque_digest(nonce, new["identity_name"], row[id_field], "id")
            for row in new["rows"]
        ] == [
            MODULE.opaque_digest(nonce, old_name, row[id_field], "id")
            for row in old["rows"]
        ]


def test_v2_request_context_comes_from_authoritative_metadata():
    specs = {spec["name"]: spec for spec in MODULE.build_v2_rows("test-nonce")}
    t1 = specs["t1_decisive_v2"]
    assert {row["request_mode"] for row in t1["rows"]} == {
        "vocal",
        "instrumental",
    }
    assert all(row["request_mode"] == row["request_type"] for row in t1["rows"])
    for name in ("t3_bprime_primary_v2", "t4_bprime_reverse_v2"):
        assert all(row["prompt_text"] == row["request_text"] for row in specs[name]["rows"])
        assert {row["request_mode"] for row in specs[name]["rows"]} == {
            "vocal",
            "instrumental",
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


def run_policy(expression: str) -> object:
    policy = (
        MODULE.STAGE_POLICY_JS.replace(
            "__VOCAL_RULE_JSON__", json.dumps(MODULE.VOCAL_LABEL_B_RULE)
        ).replace(
            "__INSTRUMENTAL_RULE_JSON__",
            json.dumps(MODULE.INSTRUMENTAL_LABEL_B_RULE),
        )
    )
    result = subprocess.run(
        [
            "node",
            "-e",
            policy
            + "\nconsole.log(JSON.stringify("
            + expression
            + "));",
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_t1_staged_reveal_locks_label_a_and_tracks_amendment():
    empty = run_policy('stagePolicy("decisive_staged",{})')
    assert empty["reveal_enabled"] is False
    assert empty["label_b_enabled"] is False

    complete = run_policy(
        'stagePolicy("decisive_staged",'
        '{label_a_voice_presence:"yes",perceived_vocal_type:"singing",vocal_extent:"sustained"})'
    )
    assert complete["reveal_enabled"] is True
    assert complete["label_a_enabled"] is True
    assert complete["label_b_enabled"] is False

    revealed = run_policy(
        'stagePolicy("decisive_staged",'
        '{label_a_voice_presence:"yes",perceived_vocal_type:"singing",vocal_extent:"sustained",request_revealed:true})'
    )
    assert revealed["label_a_enabled"] is False
    assert revealed["label_b_enabled"] is True
    amended = run_policy(
        '(()=>{const r={request_revealed:true};setLabelAEditing(r,true);'
        'return {response:r,policy:stagePolicy("decisive_staged",r)}})()'
    )
    assert amended["response"]["label_a_amended"] is True
    assert amended["policy"]["label_a_enabled"] is True


def test_t3_t4_quality_is_blind_and_secondary_questions_require_reveal():
    initial = run_policy('stagePolicy("pair_staged",{})')
    assert initial == {
        "reveal_enabled": False,
        "context_visible": False,
        "quality_enabled": True,
        "secondary_enabled": False,
    }
    quality_answered = run_policy(
        'stagePolicy("pair_staged",{quality_preference:"A"})'
    )
    assert quality_answered["reveal_enabled"] is True
    assert quality_answered["context_visible"] is False
    revealed = run_policy(
        'stagePolicy("pair_staged",{quality_preference:"A",request_revealed:true})'
    )
    assert revealed["context_visible"] is True
    assert revealed["quality_enabled"] is False
    assert revealed["secondary_enabled"] is True


def test_v2_export_contract_records_context_amendment_and_event_order():
    decisive = run_policy('exportFieldNames("decisive_staged")')
    assert {"request_mode", "label_a_amended", "reveal_sequence"}.issubset(decisive)
    pair = run_policy('exportFieldNames("pair_staged")')
    assert {
        "prompt_text",
        "request_mode",
        "request_revealed",
        "quality_answer_sequence",
        "reveal_sequence",
        "constraint_answer_sequence",
        "overall_answer_sequence",
    }.issubset(pair)


def test_t1_reveal_displays_only_the_matching_verbatim_label_b_rule():
    assert run_policy('matchingLabelBRule("vocal")') == MODULE.VOCAL_LABEL_B_RULE
    assert (
        run_policy('matchingLabelBRule("instrumental")')
        == MODULE.INSTRUMENTAL_LABEL_B_RULE
    )
    assert "Instrumental request" not in MODULE.VOCAL_LABEL_B_RULE
    assert "Vocal request" not in MODULE.INSTRUMENTAL_LABEL_B_RULE


def test_input_save_immediately_refreshes_reveal_button_state():
    html = MODULE.render_html(
        "test",
        {
            "bundle_id": "test",
            "title": "test",
            "mode": "decisive_staged",
            "wording_html": "safe",
            "rows": [],
        },
    )
    assert "persist();refreshStageAvailability();updateProgress()" in html


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


def write_synthetic_bundle(
    path: Path,
    rows: int,
    media: int,
    *,
    mode: str = "label",
    task_fields: dict[str, str] | None = None,
) -> None:
    path.mkdir()
    (path / "media").mkdir()
    for index in range(media):
        (path / "media" / f"audio_{index}.flac").touch()
    (path / "README").write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    public_rows = []
    for index in range(rows):
        row = {"rating_id": f"r_{index}", "media": "media/x.flac"}
        row.update(task_fields or {})
        public_rows.append(row)
    payload = {
        "bundle_id": path.name,
        "title": "test",
        "mode": mode,
        "wording_html": "safe",
        "rows": public_rows,
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


def test_bundle_audit_explicitly_allows_only_staged_request_task_fields(tmp_path):
    bundle = tmp_path / "pair_v2"
    bundle.mkdir()
    (bundle / "media").mkdir()
    (bundle / "media/audio_a.flac").touch()
    (bundle / "media/audio_b.flac").touch()
    (bundle / "README").write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    payload = {
        "bundle_id": "pair_v2",
        "title": "test",
        "mode": "pair_staged",
        "wording_html": "safe",
        "rows": [
            {
                "rating_id": "r_1",
                "media_a": "media/audio_a.flac",
                "media_b": "media/audio_b.flac",
                "prompt_text": "A test music request",
                "request_mode": "instrumental",
            }
        ],
    }
    (bundle / "index.html").write_text(
        MODULE.render_html("test", payload), encoding="utf-8"
    )
    result = MODULE.audit_bundle(bundle, 1, 2)
    assert result["allowed_task_fields"] == ["prompt_text", "request_mode"]


def read_bundle_payload(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    marker = '<script id="bundle-data" type="application/json">'
    start = text.index(marker) + len(marker)
    end = text.index("</script>", start)
    return json.loads(text[start:end])


def test_recorded_production_audit_and_admin_separation():
    output = Path(__file__).parents[1] / "paper_prep/rater_bundles_20260711"
    audit = json.loads((output / "BUNDLE_AUDIT.json").read_text(encoding="utf-8"))
    assert audit["nonce_present"] is True
    assert {
        name: (values["rows"], values["leak_test"])
        for name, values in audit["bundles"].items()
    } == {
        "t1_decisive_v2": (42, "PASS"),
        "t2_aprime_core": (190, "PASS"),
        "t3_bprime_primary_v2": (80, "PASS"),
        "t4_bprime_reverse_v2": (24, "PASS"),
        "t5_sa3_calibration": (60, "PASS"),
    }
    assert len(audit["archives"]) == 5
    for bundle in audit["bundles"]:
        html = (output / bundle / "index.html").read_text(encoding="utf-8")
        assert "human:CXY" in html
        assert "qwen_unvalidated" not in html
    for bundle in ("t2_aprime_core", "t5_sa3_calibration"):
        payload = read_bundle_payload(output / bundle / "index.html")
        assert payload["mode"] == "label"
        assert "Label B" not in payload["wording_html"]
        assert all(
            not {"request_mode", "prompt_text", "request_text"}.intersection(row)
            for row in payload["rows"]
        )
    old_admin_paths = [
        Path(__file__).parents[1] / "paper_prep/pi_decisive_packet_20260709/DECISIVE_PACKET_ADMIN.csv",
        Path(__file__).parents[1] / "paper_prep/validation_A_prime/primary_package_20260709/A_PRIME_PRIMARY_ADMIN.csv",
        Path(__file__).parents[1] / "paper_prep/validation_B_prime/pi_package_20260709/B_PRIME_ORDERED_ADMIN.csv",
        Path(__file__).parents[1] / "paper_prep/sao/stable_audio_3_medium/label_calibration/SA3_LABEL_CALIBRATION_ADMIN.csv",
    ]
    assert not any(path.exists() for path in old_admin_paths)


def test_production_v2_keys_preserve_v1_rating_ids_positions_and_seed():
    keys = Path(__file__).parents[1] / "paper_prep/rater_admin_keys_20260711"
    comparisons = [
        ("t1_decisive/T1_BUNDLE_KEY.csv", "t1_decisive/T1_BUNDLE_KEY_V2.csv"),
        ("t3_t4_bprime/T3_BUNDLE_KEY.csv", "t3_t4_bprime/T3_BUNDLE_KEY_V2.csv"),
        ("t3_t4_bprime/T4_BUNDLE_KEY.csv", "t3_t4_bprime/T4_BUNDLE_KEY_V2.csv"),
    ]
    for old_rel, new_rel in comparisons:
        with (keys / old_rel).open(newline="", encoding="utf-8") as handle:
            old = list(csv.DictReader(handle))
        with (keys / new_rel).open(newline="", encoding="utf-8") as handle:
            new = list(csv.DictReader(handle))
        assert [row["bundle_rating_id"] for row in new] == [
            row["bundle_rating_id"] for row in old
        ]
        assert [row["scorer_rating_id"] for row in new] == [
            row["scorer_rating_id"] for row in old
        ]
        assert [row["position"] for row in new] == [row["position"] for row in old]
        assert {row["shuffle_seed"] for row in new} == {str(MODULE.SHUFFLE_SEED)}
