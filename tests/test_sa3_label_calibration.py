import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/sao/stable_audio_3_medium/build_sa3_label_calibration.py"
SPEC = importlib.util.spec_from_file_location("build_sa3_label_calibration", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_selection_has_all_six_balanced_cells_without_duplicates():
    rows = []
    for request in ("instrumental", "vocal"):
        for index in range(60):
            rows.append(
                {
                    "ok": True,
                    "vocal_stratum": request,
                    "vocal_energy_ratio": index / 59,
                    "audio_path": f"/{request}_{index}.wav",
                }
            )
    selected = MODULE.select_calibration_rows(rows, per_cell=5)
    cells = {(row["vocal_stratum"], row["calibration_band"]) for row in selected}
    assert len(selected) == 30
    assert len(cells) == 6
    assert len({row["audio_path"] for row in selected}) == 30


def test_scorer_requires_real_rating_provenance():
    scorer_path = (
        Path(__file__).parents[1]
        / "paper_prep/rater_admin_keys_20260711/t5_sa3_calibration/score_sa3_label_calibration.py"
    )
    spec = importlib.util.spec_from_file_location("score_sa3_label_calibration", scorer_path)
    scorer = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(scorer)
    with pytest.raises(ValueError, match="rating_source"):
        scorer.validate_real_provenance([{"blind_id": "x", "rating_source": "synthetic"}])
    scorer.validate_real_provenance([{"blind_id": "x", "rating_source": "pi:Test Rater"}])
    with pytest.raises(ValueError, match="rating_source"):
        scorer.validate_real_provenance(
            [{"blind_id": "x", "rating_source": "qwen_unvalidated"}]
        )
