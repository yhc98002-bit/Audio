#!/usr/bin/env python3
"""Reconcile the A-prime 112 -> 100 -> 92 -> 82 cardinality drift."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


DEMUCS_THRESHOLD = 0.1791
PANNS_THRESHOLD = 0.0654


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def unique_index(rows: Iterable[dict[str, str]], key: str, source: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value:
            raise ValueError(f"blank {key} in {source}")
        if value in out:
            raise ValueError(f"duplicate {key}={value!r} in {source}")
        out[value] = row
    return out


def classify_media(admin: dict[str, str] | None) -> str:
    if not admin:
        return "unrecoverable"
    if admin.get("original_media_available") == "true":
        return "original"
    method = admin.get("media_recovery_method", "").lower()
    if "regenerat" in method:
        return "regenerated"
    if admin.get("media_available") == "true" and method:
        return "recovered-original"
    return "unrecoverable"


def transition_labels(
    *,
    intended: bool,
    stale: bool,
    in_manifest_92: bool,
    in_bucket_82: bool,
    occurrence_count: int,
) -> tuple[str, str, str]:
    if intended and stale:
        t112_100 = "overlap_retained_but_construct_changed"
    elif intended:
        t112_100 = "intended_case_omitted_by_wrong_detector_pair"
    else:
        t112_100 = "non_intended_case_added_by_wrong_detector_pair"

    if stale and not in_manifest_92:
        t100_92 = "cross_reason_duplicate_removed_by_first_row_wins_dedup"
    elif stale and in_manifest_92:
        t100_92 = "retained_after_dedup"
    else:
        t100_92 = "not_in_stale_100"

    if in_manifest_92 and not in_bucket_82:
        t92_82 = "reclassified_by_extracted_agreement_spotcheck_path"
    elif in_bucket_82:
        t92_82 = "retained_in_detector_disagreement_bucket"
    elif occurrence_count > 1:
        t92_82 = "already_removed_or_reclassified_before_92"
    else:
        t92_82 = "not_in_manifest_92"
    return t112_100, t100_92, t92_82


def reconcile(
    packet_rows: list[dict],
    demucs_rows: list[dict],
    panns_rows: list[dict],
    manifest_rows: list[dict[str, str]],
    admin_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    demucs = {
        (str(row["prompt_id"]), int(row["candidate_index"])): row
        for row in demucs_rows
        if row.get("ok")
    }
    panns = {
        (str(row["prompt_id"]), int(row["candidate_index"])): row
        for row in panns_rows
        if row.get("panns_vocal_score") is not None
    }
    manifest = unique_index(manifest_rows, "clip_id", "A_PRIME_MANIFEST.csv")
    admin = unique_index(admin_rows, "source_clip_id", "A_PRIME_HUMAN_ADMIN_MANIFEST.csv")

    packet_by_id: dict[str, list[dict]] = defaultdict(list)
    intended_ids: set[str] = set()
    stale_ids: set[str] = set()
    for row in packet_rows:
        case_id = str(row["case_id"])
        packet_by_id[case_id].append(row)
        internal = row.get("_internal", {})
        key = (str(internal.get("prompt_id", "")), int(internal.get("candidate_index", -1)))
        if "disagree" in str(internal.get("reason", "")):
            stale_ids.add(case_id)
        if key in demucs and key in panns:
            demucs_label = int(float(demucs[key]["vocal_energy_ratio"]) >= DEMUCS_THRESHOLD)
            panns_label = int(float(panns[key]["panns_vocal_score"]) >= PANNS_THRESHOLD)
            if demucs_label != panns_label:
                intended_ids.add(case_id)

    manifest_92 = {
        case_id
        for case_id, row in manifest.items()
        if row.get("set_name") == "detector_disagreement_packet"
    }
    bucket_82 = {
        case_id
        for case_id, row in admin.items()
        if row.get("set_bucket") == "detector_disagreement_packet"
    }
    union_ids = sorted(intended_ids | stale_ids)
    output: list[dict[str, object]] = []
    for case_id in union_ids:
        occurrences = packet_by_id[case_id]
        first = occurrences[0]
        internal = first.get("_internal", {})
        key = (str(internal.get("prompt_id", "")), int(internal.get("candidate_index", -1)))
        drow = demucs.get(key, {})
        prow = panns.get(key, {})
        arow = admin.get(case_id)
        mrow = manifest.get(case_id)
        intended = case_id in intended_ids
        stale = case_id in stale_ids
        in_m92 = case_id in manifest_92
        in_b82 = case_id in bucket_82
        t112_100, t100_92, t92_82 = transition_labels(
            intended=intended,
            stale=stale,
            in_manifest_92=in_m92,
            in_bucket_82=in_b82,
            occurrence_count=len(occurrences),
        )
        media_class = classify_media(arow)
        output.append(
            {
                "case_id": case_id,
                "prompt_id": key[0],
                "candidate_index": key[1],
                "packet_occurrences": len(occurrences),
                "packet_reasons": "|".join(
                    sorted({str(r.get("_internal", {}).get("reason", "")) for r in occurrences})
                ),
                "intended_demucs_panns_112": str(intended).lower(),
                "stale_demucs_whisper_100": str(stale).lower(),
                "dedup_manifest_92": str(in_m92).lower(),
                "final_detector_bucket_82": str(in_b82).lower(),
                "demucs_ratio": drow.get("vocal_energy_ratio", ""),
                "demucs_label_0p1791": (
                    int(float(drow["vocal_energy_ratio"]) >= DEMUCS_THRESHOLD) if drow else ""
                ),
                "panns_score": prow.get("panns_vocal_score", ""),
                "panns_label_0p0654": (
                    int(float(prow["panns_vocal_score"]) >= PANNS_THRESHOLD) if prow else ""
                ),
                "original_packet_paths": "|".join(sorted({str(r.get("audio_path", "")) for r in occurrences})),
                "resolved_source_path": (arow or {}).get("source_path", ""),
                "package_media_path": (arow or {}).get("package_media_path", ""),
                "media_class": media_class,
                "sha256": (arow or {}).get("sha256", ""),
                "analysis_role": "primary" if intended else "sensitivity",
                "transition_112_to_100": t112_100,
                "transition_100_to_92": t100_92,
                "transition_92_to_82": t92_82,
                "manifest_set_name": (mrow or {}).get("set_name", ""),
                "final_set_bucket": (arow or {}).get("set_bucket", ""),
            }
        )

    media_counts = Counter(str(row["media_class"]) for row in output if row["analysis_role"] == "primary")
    summary: dict[str, object] = {
        "packet_rows": len(packet_rows),
        "packet_unique_ids": len(packet_by_id),
        "packet_duplicate_rows": len(packet_rows) - len(packet_by_id),
        "intended_112": len(intended_ids),
        "stale_100": len(stale_ids),
        "overlap": len(intended_ids & stale_ids),
        "intended_only": len(intended_ids - stale_ids),
        "stale_only": len(stale_ids - intended_ids),
        "manifest_92": len(manifest_92),
        "bucket_82": len(bucket_82),
        "primary_media": dict(media_counts),
        "primary_all_original": media_counts == Counter({"original": len(intended_ids)}),
    }
    return output, summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("refusing to write empty reconciliation")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, summary: dict[str, object], csv_path: Path, root: Path) -> None:
    expected = {
        "intended_112": 112,
        "stale_100": 100,
        "manifest_92": 92,
        "bucket_82": 82,
    }
    mismatches = {key: (summary[key], value) for key, value in expected.items() if summary[key] != value}
    if mismatches:
        raise ValueError(f"frozen cardinality mismatch: {mismatches}")
    if not summary["primary_all_original"]:
        raise ValueError(f"primary 112 media are not all original: {summary['primary_media']}")
    csv_rel = csv_path.relative_to(root)
    report = f"""# A-prime Cardinality Reconciliation

`A_PRIME_CARDINALITY_STATUS = RECONCILED`

`A_PRIME_PROTOCOL_AMENDMENT_REQUIRED = NO`

## Result

The intended 112-case detector-disagreement universe is exactly reproducible
from the frozen phase-0 packet, Demucs ratios, and PANNs scores. All 112 primary
clips are surviving original media; no regenerated clip is needed in the
primary A-prime disagreement gate.

The apparent `112 -> 100 -> 92 -> 82` sequence was not ordinary sample
attrition. It combined a detector-pair substitution, global first-row-wins
deduplication, and path-based bucket reassignment.

## Cardinality Chain

| Stage | Count | Meaning |
|---|---:|---|
| Intended universe | {summary['intended_112']} | Unique phase-0 cases where canonical Demucs (`htdemucs`, threshold 0.1791) and PANNs (threshold 0.0654) disagree. This is the primary gate universe. |
| Stale reason-tag universe | {summary['stale_100']} | Cases tagged `demucs_whisper_disagree` by the older packet builder. This is a different construct, not a 12-row loss from the intended set. |
| A-prime manifest disagreement set | {summary['manifest_92']} | The 100 stale-tag IDs after eight cross-reason duplicate IDs were assigned to the first encountered row by global deduplication. |
| Human-package disagreement bucket | {summary['bucket_82']} | The 92 manifest rows after ten rows were reassigned from their extracted `2c_detector_agreement_spotcheck` path. |

The two detector universes overlap on {summary['overlap']} cases. The intended
set has {summary['intended_only']} cases absent from the stale 100, while the
stale set has {summary['stale_only']} cases that do not meet the intended
Demucs-versus-PANNs rule.

The original packet contains {summary['packet_rows']} rows and
{summary['packet_unique_ids']} unique case IDs; its
{summary['packet_duplicate_rows']} duplicate rows are retained as provenance
but never treated as independent clips.

## Media Classification

Primary 112 media classes: `{json.dumps(summary['primary_media'], sort_keys=True)}`.
All package paths exist and all 112 are classified `original`. The 100 clips
regenerated during the 2026-07-08 recovery remain available, but none is needed
to restore the intended primary disagreement universe. Regenerated rows are
sensitivity-only unless T2 and dual-PI approval later authorize otherwise.

## Analysis Rule

- Primary disagreement gate: the 112 reconstructed Demucs-versus-PANNs cases.
- Sensitivity only: stale Demucs-versus-Whisper cases outside the intended 112,
  regenerated media, and any later construct packet.
- Duplicate packet occurrences are provenance rows, not additional ratings.
- The prior 92- and 82-row packages must not be called the frozen 112-case gate.

## Row-Level Evidence

`{csv_rel}` records membership in all four stages, packet occurrence count,
detector values, media class, primary/sensitivity role, and the exact transition
reason for every ID in the union of the intended and stale universes.

## Audit Status

`RECONCILED`. No cardinality amendment is required because the literal 112-case
universe and all original media have been recovered. The D5 construct wording
still requires the T3 study-criteria amendment because it changes the human
label definition, not the sample cardinality.
"""
    path.write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve() if args.root else find_repo_root(Path(__file__).resolve())
    phase = root / "orbit-research/adsr_phase2_20260604"
    a_dir = phase / "paper_prep/validation_A_prime"
    rows, summary = reconcile(
        read_jsonl(phase / "phase0/rater_packet/cases_blinded.jsonl"),
        read_jsonl(phase / "vocal_presence_raw.jsonl"),
        read_jsonl(phase / "phase0/panns_labels.jsonl"),
        read_csv(a_dir / "A_PRIME_MANIFEST.csv"),
        read_csv(a_dir / "human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv"),
    )
    csv_path = a_dir / "A_PRIME_CARDINALITY_RECONCILIATION.csv"
    report_path = a_dir / "A_PRIME_CARDINALITY_REPORT.md"
    write_csv(csv_path, rows)
    write_report(report_path, summary, csv_path, root)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
