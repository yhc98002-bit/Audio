#!/usr/bin/env python3
"""Build the conservative judge smoke v2 manifest."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
PAPER = ROOT / "paper_prep"
IN_MANIFEST = PAPER / "storage_triage/A_PRIME_500_JUDGE_SAMPLE/manifest_enriched.csv"
PROMPTS = ROOT / "configs/prompts/held_out.jsonl"
OUT = PAPER / "judge_debug/judge_smoke_v2_manifest.csv"

POSITIVE_SAMPLE_IDS = [
    "aprime_0160",
    "aprime_0379",
    "aprime_0059",
    "aprime_0171",
    "aprime_0346",
]

NEGATIVE_SAMPLE_IDS = [
    "aprime_0406",  # prior clean jazz negative, passed both models
    "aprime_0241",  # fast classical, dense instrumental
    "aprime_0468",  # rock instrumentation, dense instrumental
    "aprime_0489",  # metal instrumentation, dense instrumental
    "aprime_0223",  # slow classical, low detector scores
]


def prompt_map() -> dict[str, dict]:
    out = {}
    with PROMPTS.open() as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[row["prompt_id"]] = row
    return out


def main() -> None:
    prompts = prompt_map()
    rows = list(csv.DictReader(IN_MANIFEST.open()))
    by_sample = {row["sample_id"]: row for row in rows}
    selected = [(sid, "yes") for sid in POSITIVE_SAMPLE_IDS] + [
        (sid, "no") for sid in NEGATIVE_SAMPLE_IDS
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "clip_path",
        "expected",
        "clip_id",
        "sample_id",
        "prompt_id",
        "label_source",
        "requested_vocal",
        "detector_present",
        "type_correct",
        "vocal_energy_ratio",
        "panns_vocal",
        "source_family",
        "source_path",
        "prompt_text",
        "prompt_strata",
        "dense_instrumental_probe",
        "flac_source_available",
        "wav_fallback_mode",
    ]
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for index, (sample_id, expected) in enumerate(selected, start=1):
            row = by_sample[sample_id]
            prompt = prompts.get(row["prompt_id"], {})
            dense = "no"
            if expected == "no":
                genre = (prompt.get("strata") or {}).get("genre", "")
                tempo = (prompt.get("strata") or {}).get("tempo_bin", "")
                if genre in {"rock", "metal"} or tempo in {"very_fast_160_plus"}:
                    dense = "yes"
            writer.writerow(
                {
                    "clip_path": row["copied_path"],
                    "expected": expected,
                    "clip_id": f"smoke_v2_{index:02d}",
                    "sample_id": sample_id,
                    "prompt_id": row["prompt_id"],
                    "label_source": (
                        "conservative detector-agreed positive"
                        if expected == "yes"
                        else "conservative detector-agreed instrumental negative"
                    ),
                    "requested_vocal": row["requested_vocal"],
                    "detector_present": row["present"],
                    "type_correct": row["type_correct"],
                    "vocal_energy_ratio": row["vocal_energy_ratio"],
                    "panns_vocal": row["panns_vocal"],
                    "source_family": row["source_family"],
                    "source_path": row["source_path"],
                    "prompt_text": prompt.get("text", ""),
                    "prompt_strata": json.dumps(prompt.get("strata", {}), sort_keys=True),
                    "dense_instrumental_probe": dense,
                    "flac_source_available": "yes",
                    "wav_fallback_mode": "judge_client transcodes FLAC source to 16kHz mono WAV",
                }
            )
    print(OUT)


if __name__ == "__main__":
    main()
