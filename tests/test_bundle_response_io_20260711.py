import csv
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/bundle_response_io.py"
SPEC = importlib.util.spec_from_file_location("bundle_response_io", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_key(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["bundle_rating_id", "scorer_rating_id"]
        )
        writer.writeheader()
        writer.writerows(
            [
                {"bundle_rating_id": "opaque_a", "scorer_rating_id": "source_1"},
                {"bundle_rating_id": "opaque_b", "scorer_rating_id": "source_2"},
            ]
        )


def test_nonce_ids_are_remapped_without_mutating_input(tmp_path):
    key = tmp_path / "key.csv"
    write_key(key)
    rows = [
        {"rating_id": "opaque_a", "rating_source": "human:CXY"},
        {"rating_id": "opaque_b", "rating_source": "human:CXY"},
    ]
    remapped = MODULE.remap_bundle_rows(rows, key, scorer_id_field="rating_id")
    assert [row["rating_id"] for row in remapped] == ["source_1", "source_2"]
    assert rows[0]["rating_id"] == "opaque_a"


def test_existing_scorer_ids_remain_valid(tmp_path):
    key = tmp_path / "key.csv"
    write_key(key)
    rows = [{"rating_id": "source_1"}, {"rating_id": "source_2"}]
    assert MODULE.remap_bundle_rows(rows, key, scorer_id_field="rating_id") == rows


@pytest.mark.parametrize(
    "rows,match",
    [
        ([{"rating_id": "opaque_a"}, {"rating_id": "unknown"}], "unknown IDs"),
        ([{"rating_id": ""}], "blank IDs"),
        ([], "empty"),
    ],
)
def test_partial_unknown_and_empty_inputs_fail_closed(tmp_path, rows, match):
    key = tmp_path / "key.csv"
    write_key(key)
    with pytest.raises(ValueError, match=match):
        MODULE.remap_bundle_rows(rows, key, scorer_id_field="rating_id")
