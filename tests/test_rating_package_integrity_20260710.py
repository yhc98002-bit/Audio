from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
import wave
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "paper_prep/scripts/verify_rating_packages_20260710.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_rating_packages_20260710", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_wav(path: Path, seconds: int = 2) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8_000)
        handle.writeframes(b"\0\0" * 8_000 * seconds)


def test_decisive_package_verifier_checks_media_ids_and_hashes(tmp_path, monkeypatch):
    module = load_module()
    package = tmp_path / "package"
    media = package / "media"
    media.mkdir(parents=True)
    source = tmp_path / "source.wav"
    packaged = media / "opaque.wav"
    write_wav(source)
    packaged.write_bytes(source.read_bytes())
    digest = hashlib.sha256(packaged.read_bytes()).hexdigest()
    write_csv(
        package / "admin.csv",
        [{
            "rating_id": "opaque",
            "source_path": str(source),
            "package_media_path": str(packaged),
            "sha256": digest,
        }],
    )
    write_csv(
        package / "ratings.csv",
        [{"rating_id": "opaque", "media_path": "media/opaque.wav", "label": ""}],
    )
    spec = module.PackageSpec(
        name="PI decisive construct packet",
        directory=package,
        admin_files=("admin.csv",),
        rating_file="ratings.csv",
        expected_admin_rows=(1,),
        expected_rating_rows=1,
    )
    monkeypatch.setattr(module, "verify_template_opens", lambda _path: "PASS_TEST")
    result = module.verify_package(spec)
    assert result.passed
    assert result.unique_media == 2
    assert result.decoded_media == 2
    assert result.checksum_matches == 1

    rows = list(csv.DictReader((package / "admin.csv").open()))
    rows[0]["sha256"] = "0" * 64
    write_csv(package / "admin.csv", rows)
    result = module.verify_package(spec)
    assert not result.passed
    assert any("checksum mismatch" in failure for failure in result.failures)


def test_b_prime_id_contract_requires_exact_reverse_set(tmp_path):
    module = load_module()
    result = module.PackageResult("B-prime solo-rater package", tmp_path)
    ordered = [{"rating_id": "r1", "pair_id": "p1", "presentation_role": "primary"}]
    pairs = [{"pair_id": "p1", "in_calibration_24": "false"}]
    ratings = [{"rating_id": "r1"}]
    spec = module.PackageSpec("B-prime solo-rater package", tmp_path, ("a", "b"), "r", (1, 1), 1)
    module.verify_id_contract(spec, [ordered, pairs], ratings, result)
    assert any("80 unique pairs" in failure for failure in result.failures)
    assert any("80 primary + 24 reverse" in failure for failure in result.failures)
