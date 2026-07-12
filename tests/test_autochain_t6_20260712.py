from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter
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


def test_t6_reliability_and_promotion_are_artifact_backed_and_fail_closed():
    autochain = PAPER / "autochain_20260712"
    ingest = json.loads((autochain / "T6_INGEST_AUDIT.json").read_text())
    reliability = json.loads((autochain / "T6_RELIABILITY_RESULT.json").read_text())
    promotion = json.loads((autochain / "T6_PROMOTION_RESULT.json").read_text())
    assert ingest["rows"] == 201
    assert ingest["required_answer_blanks"] == 0
    assert reliability["RELIABILITY_STATUS"] == "PASS"
    assert reliability["label_a"]["exact_agreement_count"] == 20
    assert reliability["label_b"]["exact_agreement_count"] == 20
    assert reliability["satisfied_violated_reversals"] == 0
    assert promotion["CORRECTED_INSTRUMENT_STATUS"] == "PROMOTED"
    assert promotion["amendment_signature_status"] == "DRAFTED_AWAITING_SIGNATURE"
    assert promotion["adoption_status"] == "BLOCKED_UNTIL_BOTH_W2_SIGNATURES"
    assert promotion["plan_or_claim_status_changed"] is False


def test_corrected_recompute_is_complete_but_draft_only():
    out = PAPER / "autochain_20260712/recompute"
    target = read_csv(out / "CORRECTED_TARGET_ROWS.csv")
    publication = read_csv(out / "CORRECTED_PUBLICATION_RATES.csv")
    prompt = read_csv(out / "CORRECTED_PROMPT_RATES.csv")
    audit = json.loads((out / "CALIBRATION_MODEL_AUDIT.json").read_text())
    assert len(target) == 27_966
    assert len({row["record_id"] for row in target}) == 27_966
    assert len(publication) == 28
    assert len(prompt) == 876
    assert {row["publication_status"] for row in publication} == {
        "DRAFT_AWAITING_DUAL_PI_ADOPTION"
    }
    assert audit["train_rows_decided"] == 58
    assert audit["nested_bootstrap"]["valid_replicates"] == 2_000
    assert audit["adoption_status"] == "BLOCKED_UNTIL_BOTH_W2_SIGNATURES"


def test_factorial_primary_table_covers_frozen_design():
    rows = read_csv(PAPER / "autochain_20260712/factorial/FACTORIAL_CORRECTED_SCORE_ROWS.csv")
    assert len(rows) == 3_072
    assert len({row["task_id"] for row in rows}) == 3_072
    assert Counter(row["condition"] for row in rows) == Counter(
        {
            "plain_baseline": 512,
            "negative_text": 512,
            "positive_text": 512,
            "sampler_only": 512,
            "negative_sampler": 512,
            "positive_sampler": 512,
        }
    )
    assert {row["requested_vocal"] for row in rows} == {"0"}
    assert {row["instrument_status"] for row in rows} == {
        "PROMOTED_MECHANICAL_DRAFT_AWAITING_DUAL_PI_ADOPTION"
    }


def test_judge_gold_is_disjoint_and_class_count_fails_closed():
    out = PAPER / "autochain_20260712/judge_aprime"
    split = read_csv(out / "JUDGE_LABEL_A_GOLD_SPLIT.csv")
    build = json.loads((out / "JUDGE_LABEL_A_GOLD_BUILD.json").read_text())
    tuning = {row["media_sha256"] for row in split if row["judge_role"] == "judge_tuning_only"}
    evaluation = {row["media_sha256"] for row in split if row["judge_role"] == "judge_evaluation"}
    assert not tuning & evaluation
    assert build["evaluation_rows_decided"] == 176
    assert build["evaluation_counts"] == {"no": 27, "unsure": 4, "yes": 149}
    assert build["all_t1_t2_t6_available_counts"]["no"] == 43
    assert build["all_available_negative_shortfall"] == 7


def test_judge_weighted_metric_function_counts_abstention():
    module = load_script("autochain_judge_aprime_20260712")
    rows = [
        {"clip_id": "a", "true_label": "yes", "inclusion_probability": "1"},
        {"clip_id": "b", "true_label": "no", "inclusion_probability": "1"},
        {"clip_id": "c", "true_label": "no", "inclusion_probability": "1"},
    ]
    metrics = module._metrics(rows, {"a": "yes", "b": "no", "c": "unsure"})
    assert metrics["sensitivity"] == 1
    assert metrics["specificity"] == 1
    assert metrics["abstention_rate"] == 1 / 3


def test_live_confirm_remains_guarded_by_unsigned_amendment():
    report = (PAPER / "autochain_20260712/LIVE_CONFIRM_STATUS_REPORT.md").read_text()
    assert "LIVE_CONFIRM_STATUS = BLOCKED_UNSIGNED_W2_AMENDMENT" in report
    assert (PAPER / "autochain_20260712/LIVE_CONFIRM_GUARD_EXIT.txt").read_text().strip() == "1"


def test_evpd_mechanical_draft_mode_cannot_unlock_launch_guard():
    module = load_script("w2_evpd_liveconfirm_20260712")
    candidate = {"family": "or", "demucs_threshold": 0.1, "panns_threshold": 0.2}
    mechanical = {"CORRECTED_INSTRUMENT_STATUS": "PROMOTED", "heldout": {"selected_candidate": candidate}}
    assert module._promotion_candidate(mechanical, allow_mechanical_draft=True) == candidate
    try:
        module._promotion_candidate(mechanical)
    except ValueError as exc:
        assert "dual-PI" in str(exc)
    else:
        raise AssertionError("mechanical draft promotion unlocked the live path")


def test_corrected_evpd_target_is_direction_specific_violation():
    module = load_script("w2_evpd_liveconfirm_20260712")
    candidate = {"family": "or", "demucs_threshold": 0.1, "panns_threshold": 0.2}
    present = {"recomputed_demucs_score": 0.5, "panns_score": 0.0}
    absent = {"recomputed_demucs_score": 0.0, "panns_score": 0.0}
    assert module._present(present, candidate) == 1
    assert module._present(absent, candidate) == 0
    assert int(module._present(present, candidate) != 0) == 1
    assert int(module._present(present, candidate) != 1) == 0


def test_autochain_report_has_nine_terminal_statuses_and_evidence():
    report = PAPER / "autochain_20260712/AUTOCHAIN_REPORT.md"
    lines = report.read_text(encoding="utf-8").splitlines()
    expected = {
        "RELIABILITY_STATUS": "PASS",
        "CORRECTED_INSTRUMENT_STATUS": "PROMOTED",
        "RECOMPUTE_STATUS": "COMPLETE_DRAFT_AWAITING_ADOPTION",
        "FACTORIAL_SCORING_STATUS": "COMPLETE_PROMOTED_INSTRUMENT_DRAFT",
        "JUDGE_500_STATUS": "BLOCKED_JUDGE_GOLD_NEGATIVE_COUNT",
        "A_PRIME_GATE": "BLOCKED_JUDGE_GOLD_NEGATIVE_COUNT",
        "LIVE_CONFIRM_STATUS": "BLOCKED_UNSIGNED_W2_AMENDMENT",
        "EVIDENCE_BUNDLE_STATUS": "BUILT",
        "TEST_SUITE_STATUS": "PASS",
    }
    for key, value in expected.items():
        marker = f"`{key} = {value}`"
        index = lines.index(marker)
        assert lines[index + 1].startswith("evidence:")
        paths = [part for part in lines[index + 1].split("`")[1::2]]
        assert paths
        assert all((ROOT / path).exists() for path in paths)


def test_evidence_bundle_checksums_and_tarball_exist():
    bundle = PAPER / "paper_evidence_bundle_20260712"
    checksums = (bundle / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(checksums) == 60
    for line in checksums:
        digest, name = line.split("  ", 1)
        path = bundle / name
        assert path.is_file()
        import hashlib

        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert (PAPER / "paper_evidence_bundle_20260712.tar.gz").is_file()
