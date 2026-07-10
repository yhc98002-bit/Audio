import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "paper_prep/scripts/build_validation_packages_20260709.py"
SPEC = importlib.util.spec_from_file_location("build_validation_packages_20260709", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_materialize_rejects_stale_existing_file(tmp_path):
    source = tmp_path / "source.flac"
    destination = tmp_path / "package.flac"
    source.write_bytes(b"source")
    destination.write_bytes(b"stale")
    with pytest.raises(ValueError, match="stale package"):
        MODULE.materialize_fail_closed(source, destination)


def test_materialize_is_idempotent_when_hash_matches(tmp_path):
    source = tmp_path / "source.flac"
    destination = tmp_path / "package.flac"
    source.write_bytes(b"same")
    first = MODULE.materialize_fail_closed(source, destination)
    second = MODULE.materialize_fail_closed(source, destination)
    assert first == second


def test_blind_id_depends_on_environment_nonce():
    assert MODULE.blind_id("a", "clip", 1, "nonce-a") != MODULE.blind_id("a", "clip", 1, "nonce-b")
