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


def test_t7_real_export_accepts_optional_annotation_blanks_and_rechecks_hashes():
    module = load_script("ingest_t7_judge_gold_20260713")
    ratings, admin, audit = module.validate(module.DEFAULT_INPUT)
    assert len(ratings) == len(admin) == 40
    assert audit["label_a_counts"] == {"no": 40}
    assert audit["optional_label_b_blanks"] == 2
    assert audit["optional_confidence_blanks"] == 40
    assert audit["hash_disjointness"]["detector_selection_promotion_overlap"] == 0
    assert audit["hash_disjointness"]["prior_judge_gold_overlap"] == 0
    all_gold = module.materialize_all_gold(ratings, admin)
    assert len(all_gold) == 40
    assert {row["true_label"] for row in all_gold} == {"no"}


def test_t7_pooled_gold_and_deduplicated_global_manifests_are_ready():
    module = load_script("complete_t7_judge_aprime_20260713")
    pooled = read_csv(module.POOLED_GOLD)
    global_rows = read_csv(module.GLOBAL_MANIFEST)
    mapping = read_csv(module.GLOBAL_MAPPING)
    assert len(pooled) == 216
    assert sum(row["true_label"] == "yes" for row in pooled) == 149
    assert sum(row["true_label"] == "no" for row in pooled) == 67
    assert len({row["media_sha256"] for row in pooled}) == 216
    assert len(global_rows) == len({row["media_sha256"] for row in global_rows}) == 493
    assert len(mapping) == 500
    assert set(row["judge_clip_id"] for row in mapping) == {
        row["clip_id"] for row in global_rows
    }


def test_t7_judge_majority_requires_three_calls():
    module = load_script("complete_t7_judge_aprime_20260713")
    raw = [
        {"clip_id": "a", "call_index": 0, "parsed_label": "no"},
        {"clip_id": "a", "call_index": 1, "parsed_label": "no"},
        {"clip_id": "a", "call_index": 2, "parsed_label": "yes"},
    ]
    assert module.majorities(raw) == {"a": "no"}


def test_t7_human_core_terminal_path_is_provenance_enforced():
    module = load_script("complete_t7_judge_aprime_20260713")
    buckets, provenance = module._human_core_buckets()
    assert provenance == {"pi": 190, "human": 0}
    assert buckets["detector_disagreement_112"]["rows"] == 112
    assert buckets["rare_basin_48"]["rows"] == 48
    assert buckets["agreement_spotcheck_30"]["rows"] == 30
    assert sum(bucket["rows"] for bucket in buckets.values()) == 190


def test_gpu_queue_is_nonpreemptive_four_gpu_same_node_and_signature_gated():
    module = load_script("watch_gpu_queue_20260713")
    rows = [
        {"index": 0, "compute_process": False, "memory_mib": 2, "utilization_pct": 0},
        {"index": 1, "compute_process": True, "memory_mib": 2, "utilization_pct": 0},
        {"index": 2, "compute_process": False, "memory_mib": 2048, "utilization_pct": 0},
        {"index": 3, "compute_process": False, "memory_mib": 2, "utilization_pct": 2},
    ]
    assert module.free_indices(rows) == [0]
    assert str(module.PROJECT_TIMEZONE) == "Asia/Shanghai"
    assert module.signature_ready() is False
    source = (PAPER / "scripts/watch_gpu_queue_20260713.py").read_text(encoding="utf-8")
    assert "required = 4" in source
    assert "idle-seconds" in source and "default=1200" in source
    assert 'default_nodes = ["an29"] if args.job == "judge" else ["an12", "an29"]' in source
    assert "nodes = args.nodes or default_nodes" in source
    assert "judge_runtime_ready(node)" in source


def test_live_confirm_manifest_preserves_crn_across_four_policies():
    rows = read_csv(
        PAPER
        / "w2_execution_20260712/evpd_liveconfirm_torch251_recovery/LIVE_CONFIRM_MANIFEST.csv"
    )
    assert len(rows) == 64 * 4 * 2 == 512
    grouped = {}
    for row in rows:
        key = (row["prompt_id"], row["rep"])
        grouped.setdefault(key, []).append(row)
    assert len(grouped) == 64 * 2
    for group in grouped.values():
        assert len(group) == 4
        assert len({row["policy"] for row in group}) == 4
        assert len({row["seed"] for row in group}) == 1

    launcher = (PAPER / "scripts/run_w2_liveconfirm_20260713.sh").read_text(
        encoding="utf-8"
    )
    assert launcher.index("launch-guard") < launcher.index("ACTUAL_LAUNCH_TIMESTAMP.txt")
    assert launcher.index("ACTUAL_LAUNCH_TIMESTAMP.txt") < launcher.index("for worker in 0 1 2 3")


def test_judge_chain_has_terminal_human_core_fallback_and_conditional_bulk_run():
    source = (PAPER / "scripts/run_t7_judge_chain_on_an29.sh").read_text(
        encoding="utf-8"
    )
    fail_index = source.index("finalize-core-only")
    global_index = source.index("A_PRIME_STRATIFIED_500_PENDING_MANIFEST.csv")
    assert fail_index < global_index
    assert "judge validation terminal status" in source
    assert "--infrastructure-only" in source


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
