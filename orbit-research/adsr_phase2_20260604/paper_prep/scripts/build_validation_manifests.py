#!/usr/bin/env python3
"""Build A-prime and B-prime validation manifests from existing packets."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path


ROOT = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
PAPER = ROOT / "paper_prep"
A_OUT = PAPER / "validation_A_prime/A_PRIME_MANIFEST.csv"
B_OUT = PAPER / "validation_B_prime/B_PRIME_MANIFEST.csv"
SEED = 20260707
TAR_EXTRACT_ROOT = PAPER / "validation_A_prime/tar_extracted"


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def prompt_map() -> dict[str, dict]:
    out = {}
    with (ROOT / "configs/prompts/held_out.jsonl").open() as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[row["prompt_id"]] = row
    return out


def build_audio_suffix_index() -> dict[str, str]:
    index = {}
    for path in (ROOT / "runs").glob("**/audio/**/*.wav"):
        parts = path.parts
        if "audio" not in parts:
            continue
        i = parts.index("audio")
        suffix = "/".join(parts[i + 1 :])
        index.setdefault(suffix, rel(path))
    return index


def resolve_audio_path(path_value: str, suffix_index: dict[str, str]) -> str:
    if "::" in path_value:
        _archive, member = path_value.split("::", 1)
        candidate = TAR_EXTRACT_ROOT / "adsr_human_eval_pkg" / member
        return rel(candidate) if candidate.exists() else path_value

    path = ROOT / path_value
    if path.exists():
        return path_value

    if "/audio/" in path_value:
        suffix = path_value.split("/audio/", 1)[1]
        if suffix in suffix_index:
            return suffix_index[suffix]

    return path_value


def resolve_phase0_case_audio(case_id: str, audio_path: str, suffix_index: dict[str, str]) -> str:
    for subdir in ("2_label_adjudication", "2c_detector_agreement_spotcheck"):
        candidate = TAR_EXTRACT_ROOT / "adsr_human_eval_pkg" / subdir / "media" / f"{case_id}.wav"
        if candidate.exists():
            return rel(candidate)
    return resolve_audio_path(audio_path, suffix_index)


def add_a_row(rows: list[dict], seen: set[str], *, clip_path: str, set_name: str,
              clip_id: str, source_id: str, metadata: dict) -> None:
    if clip_path in seen:
        return
    seen.add(clip_path)
    path = ROOT / clip_path
    rows.append(
        {
            "clip_id": clip_id,
            "clip_path": clip_path,
            "set_name": set_name,
            "source_id": source_id,
            "exists": str(path.exists()).lower(),
            "expected_demucs_label": metadata.get("present", metadata.get("demucs_present_label", "")),
            "requested_vocal": metadata.get("requested_vocal", ""),
            "type_correct": metadata.get("type_correct", ""),
            "panns_vocal": metadata.get("panns_vocal", metadata.get("panns_vocal_score", "")),
            "vocal_energy_ratio": metadata.get("vocal_energy_ratio", ""),
            "prompt_id": metadata.get("prompt_id", ""),
            "source_path": metadata.get("source_path", ""),
            "metadata_json": json.dumps(metadata, sort_keys=True),
        }
    )


def build_a_prime() -> dict:
    A_OUT.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    seen: set[str] = set()
    suffix_index = build_audio_suffix_index()

    # 500 stratified random clips.
    with (PAPER / "storage_triage/A_PRIME_500_JUDGE_SAMPLE/manifest_enriched.csv").open() as f:
        for row in csv.DictReader(f):
            add_a_row(
                rows,
                seen,
                clip_path=resolve_audio_path(row["copied_path"], suffix_index),
                set_name="stratified_random_500",
                clip_id=row["sample_id"],
                source_id=row["source_path"],
                metadata=row,
            )

    # Rare basin human-package source references.
    with (PAPER / "storage_triage/HUMAN_PACKAGE_SOURCE_REFERENCES.csv").open() as f:
        for row in csv.DictReader(f):
            add_a_row(
                rows,
                seen,
                clip_path=resolve_audio_path(row["source_rel"], suffix_index),
                set_name="rare_basin_human_package",
                clip_id=row["case_id"],
                source_id=row["source_path"],
                metadata=row,
            )

    # Rare clean protected examples.
    with (PAPER / "storage_triage/RARE_CLEAN_PROTECTED/manifest.csv").open() as f:
        for row in csv.DictReader(f):
            add_a_row(
                rows,
                seen,
                clip_path=resolve_audio_path(row["copied_path"], suffix_index),
                set_name="rare_clean_protected",
                clip_id=row["sample_id"],
                source_id=row["source_path"],
                metadata=row,
            )

    # Phase-0 rater packet. The internal reason distinguishes the 112
    # Demucs/PANNs-style disagreement focus from near-threshold broader packet rows.
    with (ROOT / "orbit-research/adsr_phase2_20260604/phase0/rater_packet/cases_blinded.jsonl").open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            internal = row.get("_internal", {})
            reason = internal.get("reason", "phase0_packet")
            set_name = "detector_disagreement_packet" if "disagree" in reason else "phase0_near_threshold_packet"
            add_a_row(
                rows,
                seen,
                clip_path=resolve_phase0_case_audio(row["case_id"], row["audio_path"], suffix_index),
                set_name=set_name,
                clip_id=row["case_id"],
                source_id=row["audio_path"],
                metadata={"case_id": row["case_id"], "audio_path": row["audio_path"], **internal},
            )

    fieldnames = list(rows[0])
    with A_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "rows": len(rows),
        "missing": sum(r["exists"] != "true" for r in rows),
    }


def build_b_prime() -> dict:
    B_OUT.parent.mkdir(parents=True, exist_ok=True)
    prompts = prompt_map()
    pairs = {}
    with (ROOT / "orbit-research/adsr_phase2_20260604/phase3/human_ab/human_adsr_pairs.jsonl").open() as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                pairs[row["pair_id"]] = row

    key_rows = [json.loads(line) for line in (ROOT / "orbit-research/adsr_phase2_20260604/phase3/human_ab/UNBLINDING_KEY.jsonl").open() if line.strip()]
    rng = random.Random(SEED)
    selected = []
    quotas = {"tail": 16, "lyric": 13, "general": 11}
    for contrast in ("arm6_vs_arm1", "arm6_vs_arm4"):
        contrast_rows = [row for row in key_rows if row["contrast"] == contrast]
        by_group: dict[str, list[dict]] = {g: [] for g in quotas}
        for row in contrast_rows:
            by_group[pairs[row["pair_id"]]["group"]].append(row)
        for group, quota in quotas.items():
            group_rows = sorted(by_group[group], key=lambda r: r["pair_id"])
            rng.shuffle(group_rows)
            selected.extend(group_rows[:quota])

    out_rows = []
    for row in selected:
        pair = pairs[row["pair_id"]]
        prompt = prompts.get(row["prompt_id"], {})
        out_rows.append(
            {
                "pair_id": row["pair_id"],
                "path_a": pair["A"],
                "path_b": pair["B"],
                "request_text": prompt.get("text", ""),
                "contrast": row["contrast"],
                "prompt_id": row["prompt_id"],
                "group": pair["group"],
                "rep": row["rep"],
                "A_is": row["A_is"],
                "B_is": row["B_is"],
                "A_exists": str((ROOT / pair["A"]).exists()).lower(),
                "B_exists": str((ROOT / pair["B"]).exists()).lower(),
            }
        )

    with B_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)
    return {
        "rows": len(out_rows),
        "missing_pairs": sum(r["A_exists"] != "true" or r["B_exists"] != "true" for r in out_rows),
    }


def main() -> None:
    result = {"a_prime": build_a_prime(), "b_prime": build_b_prime()}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
