#!/usr/bin/env python3
"""Build the blinded 60-clip SA3 detector-threshold calibration package."""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import random
import shutil
from pathlib import Path


THRESHOLD = 0.1791
SELECTION_SEED = 20260709
LABEL_A = (
    "Do you hear any sound a reasonable listener would perceive as a human voice or vocalization? "
    "Includes singing, rap, speech, chant, humming, wordless vocals, choir, ooh/ah, vocal chops. "
    "Answer Yes / No / Unsure; then select perceived vocal type and whether it is isolated, "
    "intermittent, or sustained."
)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def select_calibration_rows(rows: list[dict], per_cell: int = 10) -> list[dict]:
    valid = [row for row in rows if row.get("ok") and row.get("vocal_stratum") in {"vocal", "instrumental"}]
    selected: list[dict] = []
    used: set[str] = set()
    for request in ("instrumental", "vocal"):
        pool = [row for row in valid if row["vocal_stratum"] == request]
        bands = (
            ("far_below", sorted(pool, key=lambda row: float(row["vocal_energy_ratio"]))),
            ("far_above", sorted(pool, key=lambda row: float(row["vocal_energy_ratio"]), reverse=True)),
            ("near_threshold", sorted(pool, key=lambda row: abs(float(row["vocal_energy_ratio"]) - THRESHOLD))),
        )
        for band, ordered in bands:
            chosen = []
            for row in ordered:
                source = str(row["audio_path"])
                if source in used:
                    continue
                chosen.append({**row, "calibration_band": band})
                used.add(source)
                if len(chosen) == per_cell:
                    break
            if len(chosen) != per_cell:
                raise ValueError(f"need {per_cell} rows for {request}/{band}, found {len(chosen)}")
            selected.extend(chosen)
    return selected


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-ledger", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    nonce = os.environ.get("ADSR_BLINDING_NONCE")
    if not nonce:
        raise RuntimeError("ADSR_BLINDING_NONCE is required; do not hard-code blinding keys")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = args.out_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    selected = select_calibration_rows(read_jsonl(args.score_ledger))
    rng = random.Random(SELECTION_SEED)
    rng.shuffle(selected)
    admin_rows = []
    rating_rows = []
    for index, row in enumerate(selected, 1):
        source_key = f"{row['prompt_id']}:{row['seed_idx']}:{row['audio_path']}"
        digest = hmac.new(nonce.encode(), source_key.encode(), hashlib.sha256).hexdigest()[:12]
        blind_id = f"sa3cal_{index:03d}_{digest}"
        destination = audio_dir / f"{blind_id}.wav"
        source = Path(row["audio_path"])
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, destination)
        admin_rows.append(
            {
                "blind_id": blind_id,
                "audio_path": str(destination),
                "source_audio_path": str(source),
                "prompt_id": row["prompt_id"],
                "seed_idx": row["seed_idx"],
                "seed": row["seed"],
                "request_type": row["vocal_stratum"],
                "calibration_band": row["calibration_band"],
                "demucs_ratio": row["vocal_energy_ratio"],
                "demucs_present_0p1791": row["present"],
                "selection_seed": SELECTION_SEED,
            }
        )
        rating_rows.append(
            {
                "blind_id": blind_id,
                "audio_path": f"audio/{blind_id}.wav",
                "request_type": row["vocal_stratum"],
                "label_a_voice_presence": "",
                "perceived_vocal_type": "",
                "vocal_extent": "",
                "label_b_constraint": "",
                "confidence_1_to_5": "",
                "rating_source": "",
                "notes": "",
            }
        )
    write_csv(args.out_dir / "SA3_LABEL_CALIBRATION_ADMIN.csv", admin_rows, list(admin_rows[0]))
    write_csv(args.out_dir / "SA3_LABEL_CALIBRATION_RATINGS.csv", rating_rows, list(rating_rows[0]))
    instructions = f"""# SA3 Label Calibration Instructions

`SA3_LABEL_CALIBRATION_STATUS = PACKAGE_READY`

The package has 60 blinded clips: 20 far below, 20 near, and 20 far above
the ACE-Step Demucs threshold, with 10 vocal-request and 10
instrumental-request clips per band. Detector ratio and band are absent from
the rater sheet.

## Label A (voice presence)

"{LABEL_A}"

Allowed values: `Yes`, `No`, `Unsure`.

## Label B (constraint satisfaction)

Vocal request → *Satisfied* only when clearly audible vocals function as an
intentional musical element; a fleeting isolated chop, ambiguous voice-like
texture, or background artifact is not sufficient. Instrumental request →
*Violated* when perceived vocal content is salient, recurrent, or functions as
a musical element, or when any phrase is clearly sung, spoken, or rapped; a
single isolated non-linguistic one-shot shorter than ~2 s is normally not a
violation unless unusually prominent.

Choir-pad rule: perceived as human choir → A=Yes and instrumental request
normally violated; perceived as synth timbre → A=No; ambiguous → Unsure.

Run `score_sa3_label_calibration.py` with the completed ratings file. The
scorer fails on missing, duplicate, or unknown IDs and reports the fixed
0.1791 threshold plus a labeled SA3-specific threshold estimate.
"""
    (args.out_dir / "SA3_LABEL_CALIBRATION_REPORT.md").write_text(instructions, encoding="utf-8")
    print(json.dumps({"status": "PACKAGE_READY", "rows": len(admin_rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
