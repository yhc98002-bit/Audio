from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper_prep"


def load_script(name: str):
    path = PAPER / f"scripts/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_t7_selection_is_hash_disjoint_and_frozen_before_ratings():
    out = PAPER / "t7_judge_gold_20260713"
    rows = read_csv(out / "T7_SELECTION_MANIFEST.csv")
    admin = read_csv(
        PAPER
        / "rater_admin_keys_20260712/t7_judge_gold_negatives/T7_JUDGE_GOLD_NEGATIVES_ADMIN.csv"
    )
    audit = json.loads((out / "T7_SELECTION_AUDIT.json").read_text())
    assert len(rows) == len(admin) == 40
    assert len({row["canonical_clip_id"] for row in rows}) == 40
    assert len({row["prompt_id"] for row in rows}) == 40
    assert len({row["media_sha256"] for row in rows}) == 40
    assert {row["request_mode"] for row in rows} == {"instrumental"}
    assert all(float(row["score_to_threshold_ratio"]) < 0.5 for row in rows)
    assert sorted(int(row["topup_order"]) for row in rows) == list(range(1, 41))
    assert sorted(int(row["topup_order"]) for row in admin) == list(range(1, 41))
    assert {row["rating_source_required"] for row in admin} == {"pi:Richard"}
    assert audit["selected_overlap_detector_selection_promotion"] == 0
    assert audit["selected_overlap_existing_judge_gold"] == 0
    assert audit["topup_order_rule"].startswith("ascending frozen sampling_rank")


def test_t7_expected_negative_yield_clears_required_topup():
    audit = json.loads(
        (PAPER / "t7_judge_gold_20260713/T7_SELECTION_AUDIT.json").read_text()
    )
    basis = audit["negative_yield_basis"]
    assert basis["t6_predicted_absent_decided"] == 14
    assert basis["t6_predicted_absent_human_no"] == 14
    assert basis["t7_conservative_expected_negatives"] > 23
    assert basis["t7_point_expected_negatives"] == 40


def test_t7_count_only_topup_consumes_frozen_order(tmp_path):
    module = load_script("ingest_t7_judge_gold_20260713")
    baseline = tmp_path / "baseline.csv"
    with baseline.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["true_label"], lineterminator="\n")
        writer.writeheader()
        writer.writerows([{"true_label": "no"}] * 27 + [{"true_label": "yes"}] * 149)
    module.BASE_GOLD = baseline
    admin = [
        {
            "rating_id": f"r{i:02d}",
            "topup_order": str(i),
            "media_path": f"/tmp/{i}.wav",
            "media_sha256": f"{i:064x}",
            "inclusion_probability": "0.25",
        }
        for i in range(1, 41)
    ]
    ratings = [
        {
            "rating_id": f"r{i:02d}",
            "label_a_voice_presence": "no" if i <= 23 else "yes",
            "rating_source": "pi:Richard",
        }
        for i in range(1, 41)
    ]
    rows, result = module.materialize_topup(ratings, admin)
    assert result["T7_RATINGS_STATUS"] == "PASS_TOPUP_READY"
    assert result["consumed_t7_presentations"] == 23
    assert result["additional_decided_negatives"] == 23
    assert result["combined_decided_negatives"] == 50
    assert len(rows) == 23


def test_t7_ingest_rejects_shortfall(tmp_path):
    module = load_script("ingest_t7_judge_gold_20260713")
    baseline = tmp_path / "baseline.csv"
    with baseline.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["true_label"], lineterminator="\n")
        writer.writeheader()
        writer.writerows([{"true_label": "no"}] * 27)
    module.BASE_GOLD = baseline
    admin = [
        {
            "rating_id": f"r{i:02d}",
            "topup_order": str(i),
            "media_path": f"/tmp/{i}.wav",
            "media_sha256": f"{i:064x}",
            "inclusion_probability": "0.25",
        }
        for i in range(1, 41)
    ]
    ratings = [
        {
            "rating_id": f"r{i:02d}",
            "label_a_voice_presence": "no" if i <= 22 else "yes",
            "rating_source": "pi:Richard",
        }
        for i in range(1, 41)
    ]
    _rows, result = module.materialize_topup(ratings, admin)
    assert result["T7_RATINGS_STATUS"] == "BLOCKED_NEGATIVE_COUNT_SHORTFALL"
    assert result["combined_decided_negatives"] == 49
    assert result["consumed_t7_presentations"] == 40


def test_w2_signature_verification_records_pi1_and_remains_fail_closed():
    amendment = (PAPER / "W2_AMENDMENT_20260712.md").read_text(encoding="utf-8")
    report = (
        PAPER / "t7_judge_gold_20260713/W2_SIGNATURE_VERIFICATION_REPORT.md"
    ).read_text(encoding="utf-8")
    assert "Name: Richard Ye" in amendment
    assert "Date: 2026-07-13" in amendment
    assert "Commit SHA: cf805a3dd88067931c1483d2bbe595d19f839b18" in amendment
    assert "PI 2 provenance: `pi:________________`" in amendment
    assert "Name: ______________________________" in amendment
    assert "W2_AMENDMENT_STATUS = PI1_SIGNED_PI2_PENDING" in report
    assert "LIVE_CONFIRM_STATUS = BLOCKED_UNSIGNED_W2_AMENDMENT" in report
    assert "prospective pre-rating signature" in report


def test_t7_report_records_local_download_and_checksum():
    report = (
        PAPER / "t7_judge_gold_20260713/T7_JUDGE_GOLD_NEGATIVES_REPORT.md"
    ).read_text(encoding="utf-8")
    assert "T7_PACKAGE_STATUS = READY" in report
    assert "Detector-selection/promotion hash overlap: 0" in report
    assert "Existing judge-gold hash overlap: 0" in report
    assert "d88c679d427baf0c021038b4b5d4f484968348e6f480a1e5b4235ff4a5d1a750" in report


def test_t7_chain_report_has_terminal_statuses_and_evidence():
    lines = (
        PAPER / "t7_judge_gold_20260713/T7_CHAIN_STATUS_REPORT.md"
    ).read_text(encoding="utf-8").splitlines()
    expected = {
        "W2_AMENDMENT_STATUS": "PI1_SIGNED_PI2_PENDING",
        "LIVE_CONFIRM_STATUS": "BLOCKED_UNSIGNED_W2_AMENDMENT",
        "T7_PACKAGE_STATUS": "READY",
        "T7_RATINGS_STATUS": "AWAITING_PI",
        "JUDGE_VALIDATION_STATUS": "BLOCKED_T7_RATINGS",
        "JUDGE_500_STATUS": "BLOCKED_T7_RATINGS",
        "A_PRIME_GATE": "BLOCKED_T7_RATINGS",
        "W2_ADOPTION": "PI1_SIGNED_PI2_PENDING",
        "PLAN_CLAIMS_SUPERSESSION": "NOT_APPLIED",
        "EVIDENCE_BUNDLE_REFRESH": "BLOCKED_W2_ADOPTION",
        "TEST_SUITE_STATUS": "PASS",
    }
    for key, value in expected.items():
        marker = f"`{key} = {value}`"
        index = lines.index(marker)
        assert lines[index + 1].startswith("evidence:")
        paths = lines[index + 1].split("`")[1::2]
        assert paths and all((ROOT / path).exists() for path in paths)
