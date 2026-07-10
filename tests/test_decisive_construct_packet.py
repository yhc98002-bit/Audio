import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/pi_decisive_packet_20260709/score_decisive_packet.py"
SPEC = importlib.util.spec_from_file_location("score_decisive_packet", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def fixture(human_presence: int, construct_mismatch: bool = False):
    admin = []
    ratings = []
    categories = ["failed_smoke_negative_4"] * 4 + ["judge_yes_demucs_no_20"] * 20
    categories += ["rare_basin_6"] * 6 + ["threshold_near_6"] * 6
    categories += ["obvious_agreement_control_6"] * 6
    for index, category in enumerate(categories):
        rating_id = f"r{index}"
        requested = "0"
        expected = "yes" if category == "obvious_agreement_control_6" and index % 2 else "no"
        admin.append(
            {
                "rating_id": rating_id,
                "category": category,
                "requested_vocal": requested,
                "qwen_label": "yes" if category in {"failed_smoke_negative_4", "judge_yes_demucs_no_20"} else expected,
                "demucs_label": "no" if category in {"failed_smoke_negative_4", "judge_yes_demucs_no_20"} else expected,
            }
        )
        presence = human_presence if category in {"failed_smoke_negative_4", "judge_yes_demucs_no_20"} else int(expected == "yes")
        label_a = 1 - presence if construct_mismatch and category in {"failed_smoke_negative_4", "judge_yes_demucs_no_20"} else presence
        ratings.append(
            {
                "rating_id": rating_id,
                "label_a_voice_presence": "yes" if label_a else "no",
                "label_b_constraint": "violated" if presence else "satisfied",
                "rating_source": "pi",
            }
        )
    return admin, ratings


def test_judge_overcalling_branch():
    admin, ratings = fixture(0)
    assert MODULE.score(admin, ratings)["branch_verdict"] == "judge_over_calling"


def test_demucs_missing_branch():
    admin, ratings = fixture(1)
    assert MODULE.score(admin, ratings)["branch_verdict"] == "demucs_missing"


def test_construct_mismatch_branch():
    admin, ratings = fixture(1, construct_mismatch=True)
    assert MODULE.score(admin, ratings)["branch_verdict"] == "construct_mismatch"


def test_blank_provenance_cannot_choose_branch():
    admin, ratings = fixture(1)
    for row in ratings:
        row["rating_source"] = ""
    assert MODULE.score(admin, ratings)["branch_verdict"] == "AWAITING_RATINGS"


def test_id_mismatch_fails_closed():
    admin, ratings = fixture(0)
    with pytest.raises(ValueError, match="ID mismatch"):
        MODULE.score(admin, ratings[:-1])
