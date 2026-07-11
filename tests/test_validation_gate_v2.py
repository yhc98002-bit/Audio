from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/validation_gate_v2.py"
SPEC = importlib.util.spec_from_file_location("validation_gate_v2", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def a_fixture():
    admin = []
    for bucket, count, role in (
        ("detector_disagreement_112", 112, "primary"),
        ("rare_basin_48", 48, "primary"),
        ("agreement_spotcheck_30", 30, "primary"),
        ("stratified_random_500", 500, "global_bound"),
    ):
        for _ in range(count):
            index = len(admin)
            admin.append(
                {
                    "rating_id": f"a{index:04d}",
                    "source_clip_id": f"clip{index:04d}",
                    "set_bucket": bucket,
                    "analysis_role": role,
                    "media_class": "original",
                    "expected_demucs_label": str(index % 2),
                    "requested_vocal": str(index % 2),
                }
            )
    ratings = []
    for row in admin:
        expected = row["expected_demucs_label"] == "1"
        ratings.append(
            {
                "rating_id": row["rating_id"],
                "label_a_voice_presence": "Yes" if expected else "No",
                "label_b_constraint": "Satisfied",
                "rating_source": "pi:Test Rater",
            }
        )
    return admin, ratings


def b_fixture():
    pairs = []
    ordered = []
    ratings = []
    for index in range(80):
        pair_id = f"p{index:03d}"
        calibration = index < 24
        pairs.append({"pair_id": pair_id, "in_calibration_24": str(calibration).lower()})
        primary = {
            "rating_id": f"{pair_id}_primary",
            "pair_id": pair_id,
            "presentation_role": "primary",
            "presented_a_is": "arm1",
            "presented_b_is": "arm6",
        }
        ordered.append(primary)
        ratings.append(
            {
                "rating_id": primary["rating_id"],
                "quality_preference": "B",
                "overall_preference": "B",
                "constraint_preference": "B",
                "rating_source": "pi:Test Rater",
            }
        )
        if calibration:
            reverse = {
                "rating_id": f"{pair_id}_reverse",
                "pair_id": pair_id,
                "presentation_role": "reliability_reverse",
                "presented_a_is": "arm6",
                "presented_b_is": "arm1",
            }
            ordered.append(reverse)
            ratings.append(
                {
                    "rating_id": reverse["rating_id"],
                    "quality_preference": "A",
                    "overall_preference": "A",
                    "constraint_preference": "A",
                    "rating_source": "pi:Test Rater",
                }
            )
    return pairs, ordered, ratings


def test_a_pass_shape_and_stratified_500_not_in_pass_shape():
    admin, ratings = a_fixture()
    # Deliberately disagree on every global-bound row; core criteria still pass.
    ids = {row["rating_id"] for row in admin if row["analysis_role"] == "global_bound"}
    for row in ratings:
        if row["rating_id"] in ids:
            row["label_a_voice_presence"] = "No" if row["label_a_voice_presence"] == "Yes" else "Yes"
            row["label_b_constraint"] = "Violated"
    result = MODULE.score_a_prime(admin, ratings)
    assert result["status"] == "CRITERIA_MET_AWAITING_PI_GATE_CALL"
    assert result["criteria_status"] == "PASS"


def test_a_fail_shape_and_abstains_reported():
    admin, ratings = a_fixture()
    rare_ids = [row["rating_id"] for row in admin if row["set_bucket"] == "rare_basin_48"]
    for row in ratings:
        if row["rating_id"] in rare_ids[:10]:
            row["label_b_constraint"] = "Unsure"
    result = MODULE.score_a_prime(admin, ratings, abstain_policy="count-as-disagree")
    assert result["status"] == "FAIL"
    assert result["constructs"]["label_b"]["rare_basin_48"]["abstains"] == 10


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "unknown"])
def test_a_exact_id_set_failures(mutation):
    admin, ratings = a_fixture()
    if mutation == "duplicate":
        ratings.append(dict(ratings[0]))
    elif mutation == "missing":
        ratings.pop()
    else:
        ratings[-1]["rating_id"] = "unknown"
    with pytest.raises(ValueError):
        MODULE.score_a_prime(admin, ratings)


def test_a_regenerated_primary_is_excluded():
    admin, ratings = a_fixture()
    extra = {
        "rating_id": "regen",
        "source_clip_id": "regen_clip",
        "set_bucket": "rare_basin_48",
        "analysis_role": "primary",
        "media_class": "regenerated",
        "expected_demucs_label": "1",
        "requested_vocal": "1",
    }
    admin.append(extra)
    ratings.append({"rating_id": "regen", "label_a_voice_presence": "No", "label_b_constraint": "Violated", "rating_source": "pi:Test Rater"})
    result = MODULE.score_a_prime(admin, ratings)
    assert result["status"] == "CRITERIA_MET_AWAITING_PI_GATE_CALL"
    assert result["criteria_status"] == "PASS"
    assert result["excluded_regenerated_primary"] == 1


def test_a_cardinality_short_fails_closed():
    admin, ratings = a_fixture()
    removed = admin.pop(0)
    ratings = [row for row in ratings if row["rating_id"] != removed["rating_id"]]
    with pytest.raises(ValueError, match="cardinality-short"):
        MODULE.score_a_prime(admin, ratings)


def test_b_pass_shape_scores_three_questions_and_reliability():
    pairs, ordered, ratings = b_fixture()
    result = MODULE.score_b_prime(pairs, ordered, ratings)
    assert result["status"] == "CRITERIA_MET_AWAITING_PI_GATE_CALL"
    assert result["criteria_status"] == "PASS"
    assert set(result["endpoints"]) == {"quality_preference", "overall_preference", "constraint_preference"}
    assert result["reliability"]["quality_preference"]["agreement_rate"] == pytest.approx(1.0)


def test_b_missing_reverse_order_fails_closed():
    pairs, ordered, ratings = b_fixture()
    reverse_index = next(index for index, row in enumerate(ordered) if row["presentation_role"] == "reliability_reverse")
    removed = ordered.pop(reverse_index)
    ratings = [row for row in ratings if row["rating_id"] != removed["rating_id"]]
    with pytest.raises(ValueError, match="missing reverse"):
        MODULE.score_b_prime(pairs, ordered, ratings)


def test_b_duplicate_pair_fails_closed():
    pairs, ordered, ratings = b_fixture()
    pairs.append(dict(pairs[0]))
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.score_b_prime(pairs, ordered, ratings)


@pytest.mark.parametrize("source", ["", "qwen_unvalidated", "automatic_model", "unknown"])
def test_unvalidated_source_can_never_produce_a_prime_pass(source):
    admin, ratings = a_fixture()
    for row in ratings:
        row["rating_source"] = source
    with pytest.raises(ValueError, match="rating_source"):
        MODULE.score_a_prime(admin, ratings)


@pytest.mark.parametrize("source", ["", "qwen_unvalidated", "automatic_model", "unknown"])
def test_unvalidated_source_can_never_produce_b_prime_pass(source):
    pairs, ordered, ratings = b_fixture()
    for row in ratings:
        row["rating_source"] = source
    with pytest.raises(ValueError, match="rating_source"):
        MODULE.score_b_prime(pairs, ordered, ratings)
