from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "paper_prep/scripts/ingest_pi_ratings_20260711.py"
SPEC = importlib.util.spec_from_file_location("ingest_pi_ratings_20260711", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_current_exports_have_exact_ids_provenance_and_zero_required_blanks():
    prep = ROOT / "paper_prep"
    input_dir = prep / "pi_ratings_20260711"
    keys = prep / "rater_admin_keys_20260711"
    _payload, raw = MODULE.read_export(input_dir / "t1_decisive.json", "t1_decisive_v2")
    rows, key_rows = MODULE.keyed_rows(raw, keys / "t1_decisive/T1_BUNDLE_KEY_V2.csv", 42)
    admin = MODULE.read_csv(keys / "t1_decisive/DECISIVE_PACKET_ADMIN.csv")
    MODULE.require_complete(rows, MODULE.T1_REQUIRED, "T1")
    inconsistencies = MODULE.validate_t1(rows, key_rows, admin)
    assert len(inconsistencies) == 1

    _payload, raw = MODULE.read_export(input_dir / "t2_aprime_core.json", "t2_aprime_core")
    rows, _keys = MODULE.keyed_rows(raw, keys / "t2_aprime/T2_BUNDLE_KEY.csv", 190)
    MODULE.require_complete(rows, MODULE.T2_REQUIRED, "T2")
    assert {row["rating_source"] for row in rows} == {"pi:Richard"}


def test_unknown_or_blank_provenance_fails_closed(tmp_path):
    payload = {
        "bundle_id": "t2_aprime_core",
        "rating_source": "qwen_unvalidated",
        "responses": [],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="rating_source"):
        MODULE.read_export(path, "t2_aprime_core")


def test_hard_label_a_b_contradiction_is_adjudication_not_silent_rewrite():
    prep = ROOT / "paper_prep"
    keys = prep / "rater_admin_keys_20260711"
    _payload, raw = MODULE.read_export(
        prep / "pi_ratings_20260711/t1_decisive.json", "t1_decisive_v2"
    )
    rows, key_rows = MODULE.keyed_rows(raw, keys / "t1_decisive/T1_BUNDLE_KEY_V2.csv", 42)
    admin = MODULE.read_csv(keys / "t1_decisive/DECISIVE_PACKET_ADMIN.csv")
    inconsistent = MODULE.validate_t1(rows, key_rows, admin)
    assert inconsistent[0]["label_a_voice_presence"] == "no"
    assert inconsistent[0]["label_b_constraint"] == "satisfied"
    assert inconsistent[0]["adjudication_status"] == "PENDING_PI"


def test_pi_gold_split_is_media_disjoint_and_excludes_amended_t1():
    prep = ROOT / "paper_prep"
    keys = prep / "rater_admin_keys_20260711"
    _p1, raw1 = MODULE.read_export(prep / "pi_ratings_20260711/t1_decisive.json", "t1_decisive_v2")
    _p2, raw2 = MODULE.read_export(prep / "pi_ratings_20260711/t2_aprime_core.json", "t2_aprime_core")
    t1, key1 = MODULE.keyed_rows(raw1, keys / "t1_decisive/T1_BUNDLE_KEY_V2.csv", 42)
    t2, _key2 = MODULE.keyed_rows(raw2, keys / "t2_aprime/T2_BUNDLE_KEY.csv", 190)
    admin1 = MODULE.read_csv(keys / "t1_decisive/DECISIVE_PACKET_ADMIN.csv")
    admin2 = MODULE.read_csv(keys / "t2_aprime/A_PRIME_PRIMARY_ADMIN.csv")
    inconsistent = MODULE.validate_t1(t1, key1, admin1)
    gold, calibration, heldout, smoke, exclusions = MODULE.build_pi_gold(
        t1, t2, admin1, admin2, {row["rating_id"] for row in inconsistent}
    )
    assert len(gold) == 208
    assert len(smoke) == 10
    assert {row["audio_sha256"] for row in calibration}.isdisjoint(
        {row["audio_sha256"] for row in heldout}
    )
    assert any("amended" in row["reason"] for row in exclusions)
    assert {row["true_label"] for row in smoke} == {"yes", "no"}
