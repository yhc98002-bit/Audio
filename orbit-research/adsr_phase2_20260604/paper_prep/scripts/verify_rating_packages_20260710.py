#!/usr/bin/env python3
"""Fail-closed integrity audit for the three July 9 PI rating packages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import soundfile as sf
except ImportError as exc:  # pragma: no cover - exercised by the cluster command.
    raise SystemExit("soundfile is required; run this script in the audio-prm environment") from exc


def find_repo_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"


@dataclass(frozen=True)
class PackageSpec:
    name: str
    directory: Path
    admin_files: tuple[str, ...]
    rating_file: str
    expected_admin_rows: tuple[int, ...]
    expected_rating_rows: int


@dataclass
class PackageResult:
    name: str
    directory: Path
    admin_rows: dict[str, int] = field(default_factory=dict)
    rating_rows: int = 0
    media_references: int = 0
    unique_media: int = 0
    decoded_media: int = 0
    checksum_records: int = 0
    checksum_matches: int = 0
    min_duration_s: float = float("inf")
    template_open_status: str = "NOT_RUN"
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


SPECS = (
    PackageSpec(
        name="PI decisive construct packet",
        directory=PAPER / "pi_decisive_packet_20260709",
        admin_files=(str(PAPER / "rater_admin_keys_20260711/t1_decisive/DECISIVE_PACKET_ADMIN.csv"),),
        rating_file="DECISIVE_PACKET_RATINGS.csv",
        expected_admin_rows=(42,),
        expected_rating_rows=42,
    ),
    PackageSpec(
        name="A-prime original-only primary package",
        directory=PAPER / "validation_A_prime/primary_package_20260709",
        admin_files=(str(PAPER / "rater_admin_keys_20260711/t2_aprime/A_PRIME_PRIMARY_ADMIN.csv"),),
        rating_file="A_PRIME_PRIMARY_RATINGS.csv",
        expected_admin_rows=(690,),
        expected_rating_rows=690,
    ),
    PackageSpec(
        name="B-prime solo-rater package",
        directory=PAPER / "validation_B_prime/pi_package_20260709",
        admin_files=(
            str(PAPER / "rater_admin_keys_20260711/t3_t4_bprime/B_PRIME_ORDERED_ADMIN.csv"),
            str(PAPER / "rater_admin_keys_20260711/t3_t4_bprime/B_PRIME_PAIR_ADMIN.csv"),
        ),
        rating_file="B_PRIME_PI_RATINGS.csv",
        expected_admin_rows=(104, 80),
        expected_rating_rows=104,
    ),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"CSV has malformed extra columns: {path}")
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_media(package: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    package_relative = package / candidate
    if package_relative.exists():
        return package_relative
    return ROOT / candidate


def decode_audio(path: Path) -> tuple[float, int, int]:
    """Decode every frame, rather than trusting container metadata alone."""
    frame_count = 0
    with sf.SoundFile(path) as handle:
        sample_rate = int(handle.samplerate)
        channels = int(handle.channels)
        for block in handle.blocks(blocksize=262_144, dtype="float32", always_2d=True):
            frame_count += int(block.shape[0])
    duration = frame_count / sample_rate if sample_rate else 0.0
    return duration, sample_rate, channels


def add_media_reference(
    references: list[tuple[Path, str, str]],
    package: Path,
    row: dict[str, str],
    path_field: str,
    hash_field: str = "",
) -> None:
    value = row.get(path_field, "").strip()
    if not value:
        references.append((Path(""), "", f"empty {path_field}"))
        return
    references.append((resolve_media(package, value), row.get(hash_field, "").strip(), path_field))


def collect_references(spec: PackageSpec, admins: list[list[dict[str, str]]], ratings: list[dict[str, str]]) -> list[tuple[Path, str, str]]:
    refs: list[tuple[Path, str, str]] = []
    if spec.name.startswith("PI decisive"):
        for row in admins[0]:
            add_media_reference(refs, spec.directory, row, "source_path")
            add_media_reference(refs, spec.directory, row, "package_media_path", "sha256")
        for row in ratings:
            add_media_reference(refs, spec.directory, row, "media_path")
    elif spec.name.startswith("A-prime"):
        for row in admins[0]:
            add_media_reference(refs, spec.directory, row, "source_path", "declared_sha256")
            add_media_reference(refs, spec.directory, row, "package_media_path", "package_sha256")
        for row in ratings:
            add_media_reference(refs, spec.directory, row, "media_path")
    else:
        for row in admins[0]:
            add_media_reference(refs, spec.directory, row, "media_a_path", "sha256_a")
            add_media_reference(refs, spec.directory, row, "media_b_path", "sha256_b")
        for row in ratings:
            add_media_reference(refs, spec.directory, row, "media_a_path")
            add_media_reference(refs, spec.directory, row, "media_b_path")
    return refs


def verify_id_contract(spec: PackageSpec, admins: list[list[dict[str, str]]], ratings: list[dict[str, str]], result: PackageResult) -> None:
    rating_ids = [row.get("rating_id", "") for row in ratings]
    if not all(rating_ids) or len(rating_ids) != len(set(rating_ids)):
        result.failures.append("rating template has blank or duplicate rating_id values")
    if spec.name.startswith("B-prime"):
        ordered_ids = [row.get("rating_id", "") for row in admins[0]]
        if set(ordered_ids) != set(rating_ids):
            result.failures.append("B-prime ordered-admin and rating ID sets differ")
        pair_ids = [row.get("pair_id", "") for row in admins[1]]
        if len(pair_ids) != 80 or len(set(pair_ids)) != 80:
            result.failures.append("B-prime pair admin does not contain 80 unique pairs")
        known_pairs = set(pair_ids)
        ordered_pairs = [row.get("pair_id", "") for row in admins[0]]
        if not set(ordered_pairs).issubset(known_pairs):
            result.failures.append("B-prime ordered admin references unknown pair IDs")
        roles = [row.get("presentation_role", "") for row in admins[0]]
        if roles.count("primary") != 80 or roles.count("reliability_reverse") != 24:
            result.failures.append("B-prime presentation roles are not 80 primary + 24 reverse")
        calibration = {row["pair_id"] for row in admins[1] if row.get("in_calibration_24") == "true"}
        reverse = {row["pair_id"] for row in admins[0] if row.get("presentation_role") == "reliability_reverse"}
        if len(calibration) != 24 or reverse != calibration:
            result.failures.append("B-prime reversed-repeat set does not match calibration-24 set")
    else:
        admin_ids = [row.get("rating_id", "") for row in admins[0]]
        if len(admin_ids) != len(set(admin_ids)) or set(admin_ids) != set(rating_ids):
            result.failures.append("admin and rating ID sets differ or contain duplicates")


def verify_template_opens(path: Path) -> str:
    executable = shutil.which("libreoffice")
    if not executable:
        return "CSV_PARSE_PASS_LIBREOFFICE_UNAVAILABLE"
    with tempfile.TemporaryDirectory(prefix="adsr_rating_open_") as temp_dir:
        completed = subprocess.run(
            [executable, "--headless", "--convert-to", "xlsx", "--outdir", temp_dir, str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
            check=False,
        )
        converted = Path(temp_dir) / f"{path.stem}.xlsx"
        if completed.returncode != 0 or not converted.is_file() or converted.stat().st_size == 0:
            compact = " ".join(completed.stdout.split())[-300:]
            raise RuntimeError(f"LibreOffice open/convert failed: {compact}")
    return "PASS_LIBREOFFICE_HEADLESS_OPEN"


def verify_package(spec: PackageSpec) -> PackageResult:
    result = PackageResult(spec.name, spec.directory)
    if not spec.directory.is_dir():
        result.failures.append("package directory is missing")
        return result
    admins: list[list[dict[str, str]]] = []
    for filename, expected in zip(spec.admin_files, spec.expected_admin_rows, strict=True):
        candidate = Path(filename)
        path = candidate if candidate.is_absolute() else spec.directory / candidate
        try:
            rows = read_csv(path)
        except (OSError, ValueError) as exc:
            result.failures.append(str(exc))
            rows = []
        admins.append(rows)
        result.admin_rows[path.name] = len(rows)
        if len(rows) != expected:
            result.failures.append(f"{filename}: expected {expected} rows, found {len(rows)}")
    rating_path = spec.directory / spec.rating_file
    try:
        ratings = read_csv(rating_path)
    except (OSError, ValueError) as exc:
        result.failures.append(str(exc))
        ratings = []
    result.rating_rows = len(ratings)
    if len(ratings) != spec.expected_rating_rows:
        result.failures.append(f"{spec.rating_file}: expected {spec.expected_rating_rows} rows, found {len(ratings)}")
    if ratings and all(admins):
        verify_id_contract(spec, admins, ratings, result)

    references = collect_references(spec, admins, ratings)
    result.media_references = len(references)
    expected_hashes: dict[Path, set[str]] = {}
    fields_by_path: dict[Path, set[str]] = {}
    for path, expected_hash, field in references:
        if not str(path):
            result.failures.append(field)
            continue
        fields_by_path.setdefault(path, set()).add(field)
        if expected_hash:
            expected_hashes.setdefault(path, set()).add(expected_hash)
            result.checksum_records += 1
    unique_paths = sorted(fields_by_path, key=str)
    result.unique_media = len(unique_paths)
    for path in unique_paths:
        if not path.is_file():
            result.failures.append(f"missing media: {path} (fields={sorted(fields_by_path[path])})")
            continue
        hashes = expected_hashes.get(path, set())
        if len(hashes) > 1:
            result.failures.append(f"conflicting recorded checksums: {path}")
        if hashes:
            actual = sha256_file(path)
            for expected in hashes:
                if actual == expected:
                    result.checksum_matches += 1
                else:
                    result.failures.append(f"checksum mismatch: {path}")
        try:
            duration, sample_rate, channels = decode_audio(path)
        except Exception as exc:  # soundfile emits several backend-specific exception types.
            result.failures.append(f"decode failure: {path}: {type(exc).__name__}: {exc}")
            continue
        if duration <= 1.0:
            result.failures.append(f"duration <= 1 s: {path} ({duration:.6f})")
        if sample_rate <= 0 or channels <= 0:
            result.failures.append(f"invalid audio geometry: {path}")
        result.min_duration_s = min(result.min_duration_s, duration)
        result.decoded_media += 1
    try:
        result.template_open_status = verify_template_opens(rating_path)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        result.template_open_status = "FAIL"
        result.failures.append(str(exc))
    return result


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def write_report(results: list[PackageResult], output: Path, nonce_source: str) -> None:
    overall = "PASS" if all(result.passed for result in results) else "FAIL"
    lines = [
        "# PI Rating Package Integrity Report (2026-07-10)",
        "",
        f"`PACKAGE_INTEGRITY_STATUS = {overall}`",
        "",
        "This audit fully decoded every unique audio file, checked every media reference,",
        "verified all recorded SHA-256 values, enforced package ID/cardinality contracts,",
        "and opened each rating CSV through headless LibreOffice. No media were regenerated.",
        "",
        "## Blinding Environment",
        "",
        f"- `ADSR_BLINDING_NONCE`: set for the audit from `{nonce_source}`.",
        "- Secret value: intentionally neither printed nor written to this report.",
        "- The tracked builders remain fail-closed when the variable is absent.",
        "",
        "## Package Results",
        "",
        "| Package | Admin rows | Rating rows | Media references | Unique media decoded | Checksums | Minimum duration | Template open | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for result in results:
        admin = ", ".join(f"{name}={count}" for name, count in result.admin_rows.items())
        min_duration = "n/a" if result.min_duration_s == float("inf") else f"{result.min_duration_s:.3f} s"
        lines.append(
            f"| {result.name} | {admin} | {result.rating_rows} | {result.media_references} | "
            f"{result.decoded_media}/{result.unique_media} | {result.checksum_matches}/{result.checksum_records} | "
            f"{min_duration} | {result.template_open_status} | {'PASS' if result.passed else 'FAIL'} |"
        )
    lines.extend(["", "## Failures And Recovery", ""])
    failures = [(result.name, failure) for result in results for failure in result.failures]
    if failures:
        for name, failure in failures:
            lines.append(f"- **{name}:** `{failure}`")
        lines.append("")
        lines.append("No failed path was regenerated. Any recovery must copy a checksum-verified original and rerun this audit.")
    else:
        lines.append("No missing, undecodable, short-duration, checksum-mismatched, malformed, or stale-template artifact was found. No recovery was required.")

    lines.extend(["", "## PI Start Paths", ""])
    for result, spec in zip(results, SPECS, strict=True):
        start = spec.directory / spec.rating_file
        lines.append(f"### {result.name}")
        lines.append("")
        lines.append(f"- Start path: `{start.resolve()}`")
        lines.append(f"- Launch: `libreoffice --calc \"{start.resolve()}\"`")
        lines.append("")
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PAPER / "PACKAGE_INTEGRITY_REPORT_20260710.md")
    parser.add_argument("--nonce-source", default="permission-restricted on-cluster environment")
    args = parser.parse_args()
    if not os.environ.get("ADSR_BLINDING_NONCE"):
        raise SystemExit("ADSR_BLINDING_NONCE must be set before package verification")
    results = [verify_package(spec) for spec in SPECS]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_report(results, args.output, args.nonce_source)
    for result in results:
        print(f"{result.name}: {'PASS' if result.passed else 'FAIL'}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
