#!/usr/bin/env python3
"""Regenerate missing A-prime media from recorded ACE-Step prompt/seed metadata.

The source A-prime rows point at dangling legacy `runs/**` symlinks. This script
does not mutate `runs/**`. It writes regenerated WAVs into
`paper_prep/validation_A_prime/recovered_media_20260708/` and records the exact
candidate metadata used for each row.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import torch

def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "configs/prompts/dev.jsonl").exists() and (parent / "runs").exists():
            return parent
    raise RuntimeError(f"could not find repo root from {here}")


ROOT = find_repo_root()
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

MISSING_CSV = ROOT / "paper_prep/validation_A_prime/A_PRIME_MISSING_MEDIA_RESOLUTION_20260708.csv"
OUT_DIR = ROOT / "paper_prep/validation_A_prime/recovered_media_20260708"
RECOVERY_MANIFEST = OUT_DIR / "A_PRIME_RECOVERED_MEDIA_MANIFEST.csv"
LEDGER = OUT_DIR / "A_PRIME_RECOVERED_MEDIA_LEDGER.jsonl"

PAT = re.compile(r"audio/([^/]+)/candidate_(\d+)_seed(\d+)\.wav$")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_prompt_index() -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for source in (ROOT / "configs/prompts/dev.jsonl", ROOT / "configs/prompts/held_out.jsonl"):
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                out[(str(source.relative_to(ROOT)), row["prompt_id"])] = row
    return out


def parse_expected(row: dict[str, str]) -> tuple[str, int, int]:
    for key in ("expected_clip_path", "source_id", "symlink_target"):
        value = row.get(key, "")
        m = PAT.search(value)
        if m:
            return m.group(1), int(m.group(2)), int(m.group(3))
    raise RuntimeError(f"cannot parse missing row: {row}")


def index_candidate_records(missing_rows: list[dict[str, str]]) -> dict[tuple[str, int, int], dict]:
    want = {parse_expected(r) for r in missing_rows}
    found: dict[tuple[str, int, int], dict] = {}
    record_roots = [
        ROOT / "runs/adsr_recollect_20260604_full01",
        ROOT / "runs/adsr_recollect_resume",
    ]
    for record_root in record_roots:
        for path in record_root.glob("**/candidate_records.jsonl"):
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = (
                        str(rec.get("prompt_id")),
                        int(rec.get("candidate_index")),
                        int(rec.get("candidate_seed")),
                    )
                    if key in want and key not in found:
                        found[key] = {**rec, "_record_path": str(path.relative_to(ROOT))}
    return found


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audio_stats(path: Path) -> tuple[float, int, int]:
    import soundfile as sf

    info = sf.info(str(path))
    duration = info.frames / float(info.samplerate)
    return duration, int(info.samplerate), int(info.channels)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    missing_rows = list(csv.DictReader(MISSING_CSV.open(newline="", encoding="utf-8")))
    if args.limit:
        missing_rows = missing_rows[: args.limit]
    prompt_index = load_prompt_index()
    record_index = index_candidate_records(missing_rows)

    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.data.prompts import Prompt
    from mprm.inference.ace_step import AceStepModel

    model = AceStepModel(device=args.device, dtype=args.dtype)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "audio").mkdir(exist_ok=True)
    recovered_rows: list[dict] = []

    existing: dict[str, dict] = {}
    if RECOVERY_MANIFEST.exists() and not args.force:
        with RECOVERY_MANIFEST.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("status") == "PASS" and Path(ROOT / row["recovered_path"]).exists():
                    existing[row["clip_id"]] = row

    for row in missing_rows:
        if row["clip_id"] in existing:
            recovered_rows.append(existing[row["clip_id"]])
            continue
        prompt_id, candidate_index, seed = parse_expected(row)
        key = (prompt_id, candidate_index, seed)
        rec = record_index.get(key)
        status = "FAIL"
        error = ""
        recovered_rel = ""
        duration_s = ""
        sample_rate = ""
        channels = ""
        digest = ""
        started = time.time()
        try:
            if rec is None:
                raise RuntimeError(f"missing candidate record for {key}")
            prompt_source = str(rec["prompt_source"])
            prompt_row = prompt_index.get((prompt_source, prompt_id))
            if prompt_row is None:
                raise RuntimeError(f"missing prompt row for {(prompt_source, prompt_id)}")
            prompt = Prompt(
                prompt_id=prompt_row["prompt_id"],
                text=prompt_row.get("text", ""),
                lyrics=prompt_row.get("lyrics"),
                structure_hint=prompt_row.get("structure_hint"),
                duration_target=float(prompt_row.get("duration_target", 30.0)),
                metadata=prompt_row.get("metadata", {}),
                strata=prompt_row.get("strata", {}),
            )
            seed_everything(seed)
            result = model.sample(
                prompt,
                seed=seed,
                cfg_scale=5.0,
                steps=30,
                return_trajectory=False,
                extras={
                    "cfg_type": "cfg",
                    "guidance_interval": 0.5,
                    "use_erg_tag": False,
                    "use_erg_lyric": False,
                    "use_erg_diffusion": False,
                },
            )
            out_path = OUT_DIR / "audio" / prompt_id / f"candidate_{candidate_index:02d}_seed{seed}_regenerated.wav"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            save_audio(out_path, result.waveform, result.sample_rate)
            duration, sr, ch = audio_stats(out_path)
            if duration <= 1.0:
                raise RuntimeError(f"generated audio too short: {duration:.3f}s")
            recovered_rel = str(out_path.relative_to(ROOT))
            duration_s = f"{duration:.3f}"
            sample_rate = str(sr)
            channels = str(ch)
            digest = sha256(out_path)
            status = "PASS"
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        out = {
            "clip_id": row["clip_id"],
            "set_name": row["set_name"],
            "expected_clip_path": row["expected_clip_path"],
            "source_id": row.get("source_id", ""),
            "prompt_id": prompt_id,
            "candidate_index": candidate_index,
            "candidate_seed": seed,
            "record_path": rec.get("_record_path", "") if rec else "",
            "recovery_method": "regenerated_from_prompt_seed_ace_step_v1",
            "recovered_path": recovered_rel,
            "duration_s": duration_s,
            "sample_rate": sample_rate,
            "channels": channels,
            "sha256": digest,
            "status": status,
            "error": error,
        }
        recovered_rows.append(out)
        ledger_row = {
            **out,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "elapsed_s": time.time() - started,
        }
        with LEDGER.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(ledger_row, sort_keys=True) + "\n")
        print(json.dumps(ledger_row, sort_keys=True), flush=True)

    fieldnames = [
        "clip_id",
        "set_name",
        "expected_clip_path",
        "source_id",
        "prompt_id",
        "candidate_index",
        "candidate_seed",
        "record_path",
        "recovery_method",
        "recovered_path",
        "duration_s",
        "sample_rate",
        "channels",
        "sha256",
        "status",
        "error",
    ]
    # Preserve rows from the existing complete manifest plus this invocation,
    # deduplicated by clip_id.
    merged = {}
    if RECOVERY_MANIFEST.exists() and not args.force:
        with RECOVERY_MANIFEST.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                merged[row["clip_id"]] = row
    for row in recovered_rows:
        merged[row["clip_id"]] = row
    write_csv(RECOVERY_MANIFEST, list(merged.values()), fieldnames)
    n_pass = sum(1 for r in merged.values() if r["status"] == "PASS")
    print(json.dumps({"status": "DONE", "manifest": str(RECOVERY_MANIFEST), "pass": n_pass, "rows": len(merged)}, indent=2))
    return 0 if n_pass >= len(list(csv.DictReader(MISSING_CSV.open(newline="", encoding="utf-8")))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
