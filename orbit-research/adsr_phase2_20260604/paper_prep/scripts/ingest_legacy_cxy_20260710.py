#!/usr/bin/env python3
"""Ingest pre-amendment CXY ratings without touching A-prime or B-prime gates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import stat
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def find_repo_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError("repository root not found")


ROOT = find_repo_root(Path(__file__).resolve())
PHASE = ROOT / "orbit-research/adsr_phase2_20260604"
PAPER = ROOT / "paper_prep"
DEFAULT_INCOMING = PAPER / "legacy_human_results_20260710/incoming/result"
DEFAULT_OUTPUT = PAPER / "legacy_human_results_20260710"
CLASSIFICATION = "LEGACY_NON_PRIMARY"


@dataclass(frozen=True)
class LabelPacket:
    name: str
    bucket: str
    csv_path: Path
    backup_path: Path


LABEL_PACKETS = (
    LabelPacket(
        "June atlas label adjudication",
        "adjudication",
        Path("2_label_adjudication_result/adjudication_responses_CXY.csv"),
        Path("2_label_adjudication_result/adj_backup_CXY.json"),
    ),
    LabelPacket(
        "July 6 rare-basin audit",
        "rare_basin",
        Path("2b_rare_basin_audit_result/rare_basin_audit_responses_CXY.csv"),
        Path("2b_rare_basin_audit_result/rare_basin_audit_backup_CXY.json"),
    ),
    LabelPacket(
        "July 6 detector-agreement spotcheck",
        "spotcheck",
        Path("2c_detector_agreement_spotcheck_result/detector_agreement_spotcheck_responses_CXY.csv"),
        Path("2c_detector_agreement_spotcheck_result/detector_agreement_spotcheck_backup_CXY.json"),
    ),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"malformed CSV row: {path}")
    return rows


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    if not rows and fieldnames is None:
        raise ValueError(f"refusing to write headerless empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_index(rows: list[dict], key: str, label: str) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if not value:
            raise ValueError(f"{label}: blank {key}")
        if value in output:
            raise ValueError(f"{label}: duplicate {key}={value}")
        output[value] = row
    return output


def multi_index(rows: list[dict], key: str) -> dict[str, list[dict]]:
    output: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        output[str(row.get(key, "")).strip()].append(row)
    return output


def normalize_label(value: str) -> str:
    normalized = value.strip().lower()
    return {"1": "yes", "0": "no", "yes": "yes", "no": "no", "unsure": "unsure"}.get(normalized, "")


def normalize_preference(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"a", "b", "tie"}:
        raise ValueError(f"invalid legacy preference: {value!r}")
    return normalized


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return center - half, center + half


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def verify_pi_only_key(path: Path) -> None:
    if "PI_ONLY_KEY" not in str(path):
        raise ValueError("unblinding key must be supplied from an on-cluster PI_ONLY_KEY path")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(f"PI-only key permissions are too broad: {oct(mode)}")


def validate_backup(csv_rows: list[dict[str, str]], backup_path: Path, *, id_field: str, fields: dict[str, str]) -> None:
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    if not isinstance(backup, dict):
        raise ValueError(f"backup is not an object: {backup_path}")
    row_index = unique_index(csv_rows, id_field, str(backup_path))
    if set(row_index) != set(backup):
        raise ValueError(f"CSV/backup ID-set mismatch: {backup_path}")
    for row_id, row in row_index.items():
        saved = backup[row_id]
        if not isinstance(saved, dict):
            raise ValueError(f"backup row is not an object: {row_id}")
        for csv_field, backup_field in fields.items():
            if row[csv_field].strip().lower() != str(saved.get(backup_field, "")).strip().lower():
                raise ValueError(f"CSV/backup response mismatch: {row_id}:{csv_field}")


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def map_arm_preference(response: str, key_row: dict[str, str]) -> str:
    response = normalize_preference(response)
    if response == "tie":
        return "tie"
    chosen = key_row["A_is"] if response == "a" else key_row["B_is"]
    if chosen == "arm6":
        return "method"
    if chosen in {"arm1", "arm4"}:
        return "baseline"
    raise ValueError(f"unknown unblinded arm: {chosen}")


def heldout_split(rows: list[dict[str, object]], fraction: float = 0.20) -> None:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["source_bucket"]), str(row["true_label"]))].append(row)
    for values in groups.values():
        values.sort(key=lambda row: hashlib.sha256(f"20260710:{row['clip_id']}".encode()).hexdigest())
        count = max(1, int(round(len(values) * fraction))) if values else 0
        for index, row in enumerate(values):
            row["split"] = "heldout" if index < count else "reference_only"


def expected_label_for(
    clip_id: str,
    admin: dict[str, dict[str, str]],
    relabel: dict[str, dict[str, str]],
) -> tuple[str, str, bool]:
    values: list[tuple[str, str]] = []
    admin_value = normalize_label(admin[clip_id].get("expected_present_label", ""))
    if admin_value:
        values.append((admin_value, "A_PRIME_HUMAN_ADMIN_MANIFEST"))
    if clip_id in relabel:
        relabel_value = normalize_label(relabel[clip_id].get("relabel_label", ""))
        if relabel_value:
            values.append((relabel_value, "canonical_regeneration_relabel"))
    unique = {value for value, _source in values}
    if len(unique) != 1:
        return "", "+".join(source for _value, source in values) or "missing", len(unique) > 1
    return next(iter(unique)), "+".join(source for _value, source in values), False


def preference_summary(mapped_rows: list[dict[str, str]], question: str, contrast: str = "all") -> dict[str, object]:
    rows = [row for row in mapped_rows if contrast == "all" or row["contrast"] == contrast]
    counts = Counter(row[question] for row in rows)
    decided = counts["method"] + counts["baseline"]
    lower, upper = wilson_interval(counts["method"], decided)
    return {
        "rows": len(rows),
        "method": counts["method"],
        "baseline": counts["baseline"],
        "ties": counts["tie"],
        "decided": decided,
        "tie_excluded": counts["method"] / decided if decided else math.nan,
        "tie_excluded_ci_low": lower,
        "tie_excluded_ci_high": upper,
        "ties_as_half": (counts["method"] + 0.5 * counts["tie"]) / len(rows) if rows else math.nan,
        "ties_against_method": counts["method"] / len(rows) if rows else math.nan,
    }


def label_summary(rows: list[dict[str, object]], media_class: str = "all") -> dict[str, object]:
    selected = [row for row in rows if media_class == "all" or row["media_class"] == media_class]
    expected = Counter(str(row["expected_label"]) for row in selected)
    judged = [row for row in selected if row["human_label"] in {"yes", "no"} and row["expected_label"] in {"yes", "no"}]
    matches = sum(row["human_label"] == row["expected_label"] for row in judged)
    low, high = wilson_interval(matches, len(judged))
    return {
        "rows": len(selected),
        "expected_yes": expected["yes"],
        "expected_no": expected["no"],
        "expected_missing": len(selected) - expected["yes"] - expected["no"],
        "decided": len(judged),
        "matches": matches,
        "errors": len(judged) - matches,
        "match_rate": matches / len(judged) if judged else math.nan,
        "ci_low": low,
        "ci_high": high,
    }


def fmt(value: float) -> str:
    return "NA" if not math.isfinite(value) else f"{value:.6f}"


def input_record(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    return {
        "path": str(resolved.relative_to(ROOT.resolve())),
        "sha256": sha256_file(resolved),
        "mtime_utc": utc_mtime(resolved),
        "bytes": resolved.stat().st_size,
    }


def build_report(
    *,
    input_records: list[dict[str, object]],
    label_rows: list[dict[str, object]],
    mapped_quality: list[dict[str, str]],
    quality_summaries: dict[tuple[str, str], dict[str, object]],
    label_summaries: dict[tuple[str, str], dict[str, object]],
    mapping_issues: list[str],
    canonical_conflicts: list[str],
    overlap_count: int,
    gold_rows: list[dict[str, object]],
    output: Path,
) -> None:
    lines = [
        "# Legacy CXY Scoring Report",
        "",
        "> **PI: read after your fresh sittings.** This file contains per-clip and",
        "> per-bucket legacy outcomes and can spoil the blinded July 9 packages.",
        "",
        "`LEGACY_CLASSIFICATION = LEGACY_NON_PRIMARY`",
        "",
        "All ratings were collected before the signed amendment, against historical",
        "manifests and the old B-prime question set. They are descriptive legacy",
        "evidence only. They were not passed to either primary gate scorer, and no",
        "A-prime or B-prime status changes are authorized by this report.",
        "",
        "## Input Custody",
        "",
        "| Input | UTC modification time | Bytes | SHA-256 |",
        "|---|---|---:|---|",
    ]
    for record in input_records:
        lines.append(f"| `{record['path']}` | {record['mtime_utc']} | {record['bytes']} | `{record['sha256']}` |")
    lines.extend(
        [
            "",
            "Each CSV has a matching browser-backup JSON with an identical ID set and",
            "identical saved answers. The A/B arm mapping was joined only through the",
            "permission-restricted on-cluster PI-only key; the key content is not reproduced here.",
            "",
            "## Manifest And Mapping Audit",
            "",
            "| Incoming result | Historical GUI row manifest | Media/key provenance | Join result |",
            "|---|---|---|---|",
            "| `1_quality_AB_result/ab_responses_CXY.csv` | `phase3/human_ab/response_sheet.csv`; `phase3/human_ab/human_adsr_pairs.jsonl` | `phase3/human_ab/audio_manifest.csv`; on-cluster mode-600 PI-only `UNBLINDING_KEY.jsonl` | exact one-to-one pair/key join |",
            "| `2_label_adjudication_result/adjudication_responses_CXY.csv` | `validation_A_prime/tar_extracted/adsr_human_eval_pkg/2_label_adjudication/response_sheet.csv`; `phase0/rater_packet/cases_blinded.jsonl` | extracted original packet media plus A-prime admin hashes | exact one-to-one case/media join |",
            "| `2b_rare_basin_audit_result/rare_basin_audit_responses_CXY.csv` | `validation_A_prime/A_PRIME_MANIFEST.csv` | `storage_triage/HUMAN_PACKAGE_SOURCE_REFERENCES.csv`; `storage_triage/RARE_CLEAN_PROTECTED/manifest.csv`; A-prime admin hashes | exact one-to-one case/media join |",
            "| `2c_detector_agreement_spotcheck_result/detector_agreement_spotcheck_responses_CXY.csv` | extracted `2c_detector_agreement_spotcheck/response_sheet.csv` | extracted `manifest.csv` and original packet media plus A-prime admin hashes | exact one-to-one case/media join |",
            "",
            f"- Legacy rows classified: {len(label_rows) + len(mapped_quality)} / {len(label_rows) + len(mapped_quality)} as `{CLASSIFICATION}`.",
            f"- Missing or ambiguous manifest/key mappings: {len(mapping_issues)}.",
            f"- Legacy rows overlapping a July 9 primary or decisive packet: {overlap_count}.",
            f"- Cross-manifest canonical-label conflicts: {len(canonical_conflicts)}.",
            "- The rare-basin regenerated cohort is marked `flip-risk`; it is sensitivity-only and excluded from judge gold.",
            "",
            "## Human Versus Demucs By Bucket",
            "",
            "Match means the CXY voice-presence answer equals the canonical Demucs label",
            "attached to the exact rated media. Intervals are two-sided 95% Wilson intervals.",
            "",
            "| Bucket | Media scope | Rows | Expected yes | Expected no | Missing expected | Decided | Matches | Errors | Match rate | Wilson CI |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for (bucket, scope), summary in label_summaries.items():
        lines.append(
            f"| {bucket} | {scope} | {summary['rows']} | {summary['expected_yes']} | {summary['expected_no']} | "
            f"{summary['expected_missing']} | {summary['decided']} | {summary['matches']} | {summary['errors']} | "
            f"{fmt(float(summary['match_rate']))} | [{fmt(float(summary['ci_low']))}, {fmt(float(summary['ci_high']))}] |"
        )
    lines.extend(
        [
            "",
            "## Legacy A/B Arm-Mapped Preferences",
            "",
            "The method arm is historical `arm6`; baselines are `arm1` or `arm4` as",
            "specified by the PI-only key. These are not amended B-prime quality ratings.",
            "",
            "| Contrast | Question | Rows | Method | Baseline | Ties | Tie-excluded method rate | Wilson CI | Ties-as-half | Ties-against-method |",
            "|---|---|---:|---:|---:|---:|---:|---|---:|---:|",
        ]
    )
    display_questions = {
        "overall": "overall preference",
        "prompt_fit": "prompt fit",
        "vocal_artifacts": "fewer vocal artifacts",
    }
    for (contrast, question), summary in quality_summaries.items():
        lines.append(
            f"| {contrast} | {display_questions[question]} | {summary['rows']} | {summary['method']} | "
            f"{summary['baseline']} | {summary['ties']} | {fmt(float(summary['tie_excluded']))} | "
            f"[{fmt(float(summary['tie_excluded_ci_low']))}, {fmt(float(summary['tie_excluded_ci_high']))}] | "
            f"{fmt(float(summary['ties_as_half']))} | {fmt(float(summary['ties_against_method']))} |"
        )
    lines.extend(
        [
            "",
            "## Per-Clip Label Results",
            "",
            "| Packet | Clip ID | Human Label A | Demucs expected | Match | Media class | Flip-risk | New primary ID | Decisive ID | Canonical conflict |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in sorted(label_rows, key=lambda value: (str(value["source_bucket"]), str(value["clip_id"]))):
        lines.append(
            f"| {row['source_bucket']} | `{row['clip_id']}` | {row['human_label']} | {row['expected_label'] or 'missing'} | "
            f"{row['match']} | {row['media_class']} | {row['flip_risk']} | {row['new_primary_rating_ids'] or '-'} | "
            f"{row['decisive_rating_ids'] or '-'} | {row['canonical_conflict']} |"
        )
    lines.extend(
        [
            "",
            "## Per-Pair Legacy B Results",
            "",
            "| Pair ID | Contrast | A arm | B arm | Overall mapped | Prompt-fit mapped | Artifact mapped | Flip-risk |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in sorted(mapped_quality, key=lambda value: value["pair_id"]):
        lines.append(
            f"| `{row['pair_id']}` | {row['contrast']} | {row['A_is']} | {row['B_is']} | {row['overall']} | "
            f"{row['prompt_fit']} | {row['vocal_artifacts']} | {row['flip_risk']} |"
        )
    heldout = sum(row["split"] == "heldout" for row in gold_rows)
    labels = Counter(str(row["true_label"]) for row in gold_rows)
    lines.extend(
        [
            "",
            "## Judge Gold",
            "",
            f"`JUDGE_GOLD_CXY_20260710.csv` contains {len(gold_rows)} unique original-media, unambiguous Label-A-equivalent rows: "
            f"{labels['yes']} yes and {labels['no']} no. The deterministic stratified held-out split contains {heldout} rows.",
            "",
            "This gold is **single-rater evidence pending PI or second-rater inter-rater",
            "agreement (kappa)**. It may support provisional T7 diagnostics but cannot by",
            "itself auto-pass judge validation or either human gate.",
            "",
            "## Escalation Evaluation",
            "",
            f"- Missing/ambiguous key rate: {len(mapping_issues)}/{len(label_rows) + len(mapped_quality)}.",
            f"- Spotcheck human-versus-Demucs errors: {label_summaries[('spotcheck', 'all')]['errors']}/30.",
            f"- Legacy overall method preference among decided pairs: {fmt(float(quality_summaries[('all', 'overall')]['tie_excluded']))}.",
            f"- Conflicting canonical labels on rows overlapping the new primary package: {len(canonical_conflicts)}.",
            "",
            "The mechanical escalation packet, when required, points back to this section",
            "rather than duplicating spoiler numbers elsewhere.",
        ]
    )
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_flags(path: Path, flags: dict[str, tuple[str, str]]) -> None:
    lines = [
        "# Legacy Flags For PI",
        "",
        "Read this coarse-only page before fresh sittings; do not open the scoring report.",
        "",
    ]
    for key in ("rare_basin", "disagreement", "spotcheck", "B_prime"):
        status, reason = flags[key]
        lines.append(f"- `{key}: {status}` - {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", type=Path, default=DEFAULT_INCOMING)
    parser.add_argument("--pi-only-key", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    verify_pi_only_key(args.pi_only_key)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    quality_csv = args.incoming / "1_quality_AB_result/ab_responses_CXY.csv"
    quality_backup = args.incoming / "1_quality_AB_result/ab_backup_CXY.json"
    quality_rows = read_csv(quality_csv)
    if len(quality_rows) != 80 or {row["rater_initials"] for row in quality_rows} != {"CXY"}:
        raise ValueError("legacy quality input must contain 80 CXY rows")
    validate_backup(
        quality_rows,
        quality_backup,
        id_field="pair_id",
        fields={
            "overall_preference(A/B/tie)": "overall_preference",
            "prompt_fit(A/B/tie)": "prompt_fit",
            "vocal_artifacts(A/B/tie)": "vocal_artifacts",
        },
    )

    label_inputs: list[tuple[LabelPacket, list[dict[str, str]]]] = []
    expected_counts = {"adjudication": 112, "rare_basin": 60, "spotcheck": 30}
    for packet in LABEL_PACKETS:
        rows = read_csv(args.incoming / packet.csv_path)
        if len(rows) != expected_counts[packet.bucket] or {row["rater_initials"] for row in rows} != {"CXY"}:
            raise ValueError(f"legacy {packet.bucket} input has wrong row count or rater")
        validate_backup(
            rows,
            args.incoming / packet.backup_path,
            id_field="case_id",
            fields={"vocals_present(0/1/unsure)": "v"},
        )
        label_inputs.append((packet, rows))

    key_rows = read_jsonl(args.pi_only_key)
    key_index = unique_index(key_rows, "pair_id", "PI-only A/B key")
    historical_quality_sheet = unique_index(read_csv(PHASE / "phase3/human_ab/response_sheet.csv"), "pair_id", "historical A/B response sheet")
    historical_pairs = unique_index(read_jsonl(PHASE / "phase3/human_ab/human_adsr_pairs.jsonl"), "pair_id", "historical A/B GUI manifest")
    historical_audio = multi_index(read_csv(PHASE / "phase3/human_ab/audio_manifest.csv"), "pair_id")

    regenerated_rows = read_csv(PAPER / "validation_A_prime/regeneration_fidelity_20260709/REGENERATION_RELABEL_RESULTS.csv")
    regenerated_index = unique_index(regenerated_rows, "clip_id", "regeneration relabel results")
    regenerated_paths = {
        str(resolve_repo_path(row["audio_path"]).resolve())
        for row in regenerated_rows
        if row.get("audio_path") and resolve_repo_path(row["audio_path"]).exists()
    }

    mapping_issues: list[str] = []
    mapped_quality: list[dict[str, str]] = []
    for row in quality_rows:
        pair_id = row["pair_id"]
        if pair_id not in key_index or pair_id not in historical_quality_sheet or pair_id not in historical_pairs:
            mapping_issues.append(f"quality:{pair_id}:missing_key_or_gui_manifest")
            continue
        audio_rows = historical_audio.get(pair_id, [])
        if len(audio_rows) != 2 or {item.get("slot", "").upper() for item in audio_rows} != {"A", "B"}:
            mapping_issues.append(f"quality:{pair_id}:ambiguous_audio_manifest")
            continue
        missing_audio = [item["path"] for item in audio_rows if not resolve_repo_path(item["path"]).is_file()]
        if missing_audio:
            mapping_issues.append(f"quality:{pair_id}:missing_media")
            continue
        key = key_index[pair_id]
        if {key.get("A_is"), key.get("B_is")} not in ({"arm6", "arm1"}, {"arm6", "arm4"}):
            mapping_issues.append(f"quality:{pair_id}:ambiguous_arm_mapping")
            continue
        pair = historical_pairs[pair_id]
        pair_paths = [resolve_repo_path(str(pair[side])).resolve() for side in ("A", "B")]
        flip_risk = "yes" if any(str(path) in regenerated_paths for path in pair_paths) else "no"
        mapped_quality.append(
            {
                "pair_id": pair_id,
                "contrast": key["contrast"],
                "A_is": key["A_is"],
                "B_is": key["B_is"],
                "overall": map_arm_preference(row["overall_preference(A/B/tie)"], key),
                "prompt_fit": map_arm_preference(row["prompt_fit(A/B/tie)"], key),
                "vocal_artifacts": map_arm_preference(row["vocal_artifacts(A/B/tie)"], key),
                "flip_risk": flip_risk,
            }
        )

    a_manifest = unique_index(read_csv(PAPER / "validation_A_prime/A_PRIME_MANIFEST.csv"), "clip_id", "A-prime legacy manifest")
    a_admin = unique_index(
        read_csv(PAPER / "validation_A_prime/human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv"),
        "source_clip_id",
        "A-prime human admin manifest",
    )
    primary_rows = read_csv(PAPER / "rater_admin_keys_20260711/t2_aprime/A_PRIME_PRIMARY_ADMIN.csv")
    primary_by_source = multi_index(primary_rows, "source_clip_id")
    decisive_by_source = multi_index(
        read_csv(PAPER / "rater_admin_keys_20260711/t1_decisive/DECISIVE_PACKET_ADMIN.csv"),
        "source_id",
    )
    adj_sheet = unique_index(
        read_csv(PAPER / "validation_A_prime/tar_extracted/adsr_human_eval_pkg/2_label_adjudication/response_sheet.csv"),
        "case_id",
        "historical adjudication GUI sheet",
    )
    spot_sheet = unique_index(
        read_csv(PAPER / "validation_A_prime/tar_extracted/adsr_human_eval_pkg/2c_detector_agreement_spotcheck/response_sheet.csv"),
        "case_id",
        "historical spotcheck GUI sheet",
    )
    spot_manifest = unique_index(
        read_csv(PAPER / "validation_A_prime/tar_extracted/adsr_human_eval_pkg/2c_detector_agreement_spotcheck/manifest.csv"),
        "case_id",
        "historical spotcheck media manifest",
    )
    rare_sources = unique_index(read_csv(PAPER / "storage_triage/HUMAN_PACKAGE_SOURCE_REFERENCES.csv"), "case_id", "rare-basin source manifest")
    rare_protected = unique_index(read_csv(PAPER / "storage_triage/RARE_CLEAN_PROTECTED/manifest.csv"), "sample_id", "rare-clean source manifest")

    label_rows: list[dict[str, object]] = []
    canonical_conflicts: list[str] = []
    for packet, rows in label_inputs:
        for response in rows:
            clip_id = response["case_id"]
            if clip_id not in a_manifest or clip_id not in a_admin:
                mapping_issues.append(f"{packet.bucket}:{clip_id}:missing_A_manifest_mapping")
                continue
            if packet.bucket == "adjudication" and clip_id not in adj_sheet:
                mapping_issues.append(f"{packet.bucket}:{clip_id}:missing_historical_GUI_row")
                continue
            if packet.bucket == "spotcheck" and (clip_id not in spot_sheet or clip_id not in spot_manifest):
                mapping_issues.append(f"{packet.bucket}:{clip_id}:missing_historical_GUI_or_media_row")
                continue
            if packet.bucket == "rare_basin" and clip_id not in rare_sources and clip_id not in rare_protected:
                mapping_issues.append(f"{packet.bucket}:{clip_id}:missing_July6_manifest_row")
                continue
            admin = a_admin[clip_id]
            media_path = resolve_repo_path(admin["package_media_path"])
            if not media_path.is_file():
                mapping_issues.append(f"{packet.bucket}:{clip_id}:missing_rated_media")
                continue
            if admin.get("sha256") and sha256_file(media_path) != admin["sha256"]:
                mapping_issues.append(f"{packet.bucket}:{clip_id}:rated_media_hash_mismatch")
                continue
            expected, expected_source, ambiguous = expected_label_for(clip_id, a_admin, regenerated_index)
            if ambiguous or expected not in {"yes", "no"}:
                mapping_issues.append(f"{packet.bucket}:{clip_id}:missing_or_ambiguous_canonical_label")
            human = normalize_label(response["vocals_present(0/1/unsure)"])
            if human not in {"yes", "no", "unsure"}:
                mapping_issues.append(f"{packet.bucket}:{clip_id}:invalid_human_label")
                continue
            primary = primary_by_source.get(clip_id, [])
            new_labels = {normalize_label(item.get("expected_demucs_label", "")) for item in primary}
            new_labels.discard("")
            conflict = bool(expected and new_labels and new_labels != {expected})
            if conflict:
                canonical_conflicts.append(clip_id)
            media_class = "regenerated" if clip_id in regenerated_index else "original"
            decisive = decisive_by_source.get(clip_id, [])
            label_rows.append(
                {
                    "clip_id": clip_id,
                    "source_bucket": packet.bucket,
                    "human_label": human,
                    "expected_label": expected,
                    "expected_label_source": expected_source,
                    "match": "yes" if human == expected else "no",
                    "media_class": media_class,
                    "flip_risk": "yes" if media_class == "regenerated" else "no",
                    "rated_media_path": str(media_path.relative_to(ROOT)),
                    "rated_media_sha256": admin["sha256"],
                    "new_primary_rating_ids": ";".join(item["rating_id"] for item in primary),
                    "decisive_rating_ids": ";".join(item["rating_id"] for item in decisive),
                    "canonical_conflict": "yes" if conflict else "no",
                    "classification": CLASSIFICATION,
                }
            )

    total_input_rows = len(quality_rows) + sum(len(rows) for _packet, rows in label_inputs)
    if len(mapped_quality) + len(label_rows) + len(mapping_issues) < total_input_rows:
        raise RuntimeError("internal ingest accounting error")

    label_by_bucket = {
        bucket: [row for row in label_rows if row["source_bucket"] == bucket]
        for bucket in ("adjudication", "rare_basin", "spotcheck")
    }
    label_summaries: dict[tuple[str, str], dict[str, object]] = {}
    for bucket, rows in label_by_bucket.items():
        label_summaries[(bucket, "all")] = label_summary(rows)
        if bucket == "rare_basin":
            label_summaries[(bucket, "original-only")] = label_summary(rows, "original")

    quality_summaries = {
        (contrast, question): preference_summary(mapped_quality, question, contrast)
        for contrast in ("all", "arm6_vs_arm1", "arm6_vs_arm4")
        for question in ("overall", "prompt_fit", "vocal_artifacts")
    }

    gold_rows: list[dict[str, object]] = []
    for row in label_rows:
        if row["media_class"] != "original" or row["human_label"] not in {"yes", "no"}:
            continue
        primary = primary_by_source.get(str(row["clip_id"]), [])
        if len(primary) != 1:
            continue
        primary_media = resolve_repo_path(primary[0]["package_media_path"])
        if not primary_media.is_file() or sha256_file(primary_media) != primary[0]["package_sha256"]:
            continue
        gold_rows.append(
            {
                "clip_id": row["clip_id"],
                "label_a_equivalent": row["human_label"],
                "true_label": row["human_label"],
                "provenance": f"CXY;{row['source_bucket']};legacy_pre_amendment;original_media;single_rater",
                "source_bucket": row["source_bucket"],
                "rater": "CXY",
                "classification": CLASSIFICATION,
                "media_class": "original",
                "clip_path": str(primary_media.resolve()),
                "media_sha256": primary[0]["package_sha256"],
                "split": "",
            }
        )
    if len({row["clip_id"] for row in gold_rows}) != len(gold_rows):
        raise ValueError("judge gold has duplicate clip IDs")
    heldout_split(gold_rows)

    classification_rows = [
        {
            "legacy_packet": row["source_bucket"],
            "legacy_row_id": row["clip_id"],
            "classification": CLASSIFICATION,
            "pre_amendment": "true",
            "primary_gate_eligible": "false",
        }
        for row in label_rows
    ] + [
        {
            "legacy_packet": "quality_AB",
            "legacy_row_id": row["pair_id"],
            "classification": CLASSIFICATION,
            "pre_amendment": "true",
            "primary_gate_eligible": "false",
        }
        for row in mapped_quality
    ]
    overlap_rows = [
        {
            "legacy_packet": row["source_bucket"],
            "legacy_row_id": row["clip_id"],
            "media_class": row["media_class"],
            "flip_risk": row["flip_risk"],
            "new_primary_rating_ids": row["new_primary_rating_ids"],
            "decisive_rating_ids": row["decisive_rating_ids"],
            "canonical_conflict": row["canonical_conflict"],
            "classification": CLASSIFICATION,
        }
        for row in label_rows
    ]
    write_csv(args.output_dir / "LEGACY_ROW_CLASSIFICATION.csv", classification_rows)
    write_csv(args.output_dir / "LEGACY_OVERLAP_MAP.csv", overlap_rows)
    write_csv(args.output_dir / "JUDGE_GOLD_CXY_20260710.csv", gold_rows)
    heldout_manifest = [
        {
            "clip_id": row["clip_id"],
            "clip_path": row["clip_path"],
            "true_label": row["true_label"],
            "provenance": row["provenance"],
        }
        for row in gold_rows
        if row["split"] == "heldout"
    ]
    write_csv(args.output_dir / "JUDGE_GOLD_CXY_HELDOUT_MANIFEST.csv", heldout_manifest)

    input_paths = [quality_csv, quality_backup]
    for packet in LABEL_PACKETS:
        input_paths.extend([args.incoming / packet.csv_path, args.incoming / packet.backup_path])
    inputs = [input_record(path) for path in input_paths]
    overlap_count = sum(bool(row["new_primary_rating_ids"] or row["decisive_rating_ids"]) for row in label_rows)
    build_report(
        input_records=inputs,
        label_rows=label_rows,
        mapped_quality=mapped_quality,
        quality_summaries=quality_summaries,
        label_summaries=label_summaries,
        mapping_issues=mapping_issues,
        canonical_conflicts=canonical_conflicts,
        overlap_count=overlap_count,
        gold_rows=gold_rows,
        output=args.output_dir / "LEGACY_SCORING_REPORT.md",
    )

    rare = label_summaries[("rare_basin", "original-only")]
    disagreement = label_summaries[("adjudication", "all")]
    spot = label_summaries[("spotcheck", "all")]
    overall = quality_summaries[("all", "overall")]
    flags = {
        "rare_basin": (
            "PASS-trend" if float(rare["match_rate"]) >= 0.90 else "RISK",
            "Original-media legacy labels align strongly with the canonical detector." if float(rare["match_rate"]) >= 0.90 else "Original-media legacy labels show meaningful detector disagreement.",
        ),
        "disagreement": (
            "PASS-trend" if float(disagreement["match_rate"]) >= 0.70 else "RISK",
            "Legacy adjudication trends toward detector agreement." if float(disagreement["match_rate"]) >= 0.70 else "Legacy adjudication trends away from the required detector agreement.",
        ),
        "spotcheck": (
            "PASS-trend" if int(spot["errors"]) <= 2 else "RISK",
            "Agreement controls remain directionally consistent." if int(spot["errors"]) <= 2 else "Agreement controls contain more discordance than the frozen tolerance.",
        ),
        "B_prime": (
            "RISK" if float(overall["tie_excluded"]) < 0.40 else "AMBIGUOUS",
            "Legacy arm mapping trends below the historical preference floor." if float(overall["tie_excluded"]) < 0.40 else "Preference direction is encouraging, but the legacy questions cannot validate the amended endpoint.",
        ),
    }
    write_flags(args.output_dir / "LEGACY_FLAGS_FOR_PI.md", flags)

    key_issue_rate = len(mapping_issues) / total_input_rows
    triggers = []
    if key_issue_rate > 0.05:
        triggers.append("missing_or_ambiguous_keys_above_tolerance")
    if int(spot["errors"]) > 2:
        triggers.append("spotcheck_errors_above_frozen_tolerance")
    if float(overall["tie_excluded"]) < 0.40:
        triggers.append("legacy_method_preference_materially_below_floor")
    if canonical_conflicts:
        triggers.append("legacy_to_primary_canonical_label_conflict")
    escalation_path = PAPER / "execution_20260709/ESCALATION_LEGACY_INGEST.md"
    if triggers:
        escalation_lines = [
            "# Legacy Human Results Ingest Escalation",
            "",
            "The following standing trigger or triggers fired:",
            "",
            *[f"- `{trigger}`" for trigger in triggers],
            "",
            "Exact evidence is confined to `paper_prep/legacy_human_results_20260710/LEGACY_SCORING_REPORT.md`,",
            "under **Escalation Evaluation**, to avoid spoiling the fresh PI packets.",
            "Legacy rows remain non-primary and no A-prime or B-prime gate status changed.",
        ]
        escalation_path.write_text("\n".join(escalation_lines) + "\n", encoding="utf-8")

    write_json(
        args.output_dir / "LEGACY_INGEST_AUDIT.json",
        {
            "classification": CLASSIFICATION,
            "input_rows": total_input_rows,
            "classified_rows": len(classification_rows),
            "mapping_issue_count": len(mapping_issues),
            "canonical_conflict_count": len(canonical_conflicts),
            "judge_gold_rows": len(gold_rows),
            "judge_heldout_rows": len(heldout_manifest),
            "unblinding_key_path": str(args.pi_only_key),
            "unblinding_key_sha256": sha256_file(args.pi_only_key),
            "unblinding_key_content_logged": False,
            "gate_scorers_invoked": False,
            "section_7_status_changed": False,
            "escalation_triggers": triggers,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    print(json.dumps({
        "classification": CLASSIFICATION,
        "input_rows": total_input_rows,
        "mapping_issues": len(mapping_issues),
        "judge_gold_rows": len(gold_rows),
        "heldout_rows": len(heldout_manifest),
        "escalation_required": bool(triggers),
    }, sort_keys=True))
    return 2 if key_issue_rate > 0.05 else 0


if __name__ == "__main__":
    raise SystemExit(main())
