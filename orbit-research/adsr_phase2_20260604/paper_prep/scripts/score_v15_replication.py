#!/usr/bin/env python3
"""Canonical Demucs scoring for generated ACE-Step 1.5 replication clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import socket
import time
from pathlib import Path

import numpy as np

from mprm.common.thresholds import is_vocal_present


def read_jsonl_strict(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line at {path}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"non-object JSON at {path}:{line_number}")
            rows.append(row)
    return rows


def key(row: dict) -> tuple[str, str, int]:
    return str(row["prompt_id"]), str(row["condition"]), int(row["seed"])


def unique_map(rows: list[dict], label: str) -> dict[tuple[str, str, int], dict]:
    output = {}
    for row in rows:
        row_key = key(row)
        if row_key in output:
            raise ValueError(f"duplicate {label} key {row_key}")
        output[row_key] = row
    return output


def successful_generation_map(rows: list[dict]) -> dict[tuple[str, str, int], dict]:
    """Select one PASS per key while preserving failed attempts in raw ledgers."""
    output = {}
    for row in rows:
        if row.get("status") != "PASS":
            continue
        row_key = key(row)
        if row_key in output:
            raise ValueError(f"duplicate successful generation key {row_key}")
        output[row_key] = row
    return output


def seed_rng(identity: tuple[str, str, int]) -> int:
    import torch

    seed = int.from_bytes(hashlib.sha256(repr(identity).encode()).digest()[:4], "big")
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    return seed


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--generation-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--worker-index", type=int, required=True)
    parser.add_argument("--num-workers", type=int, required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    if not 0 <= args.worker_index < args.num_workers:
        raise ValueError("worker index must be in [0, num_workers)")
    manifest = unique_map(read_jsonl_strict(args.manifest), "manifest")
    generation_rows = []
    for path in sorted((args.generation_dir / "ledgers").glob("generation_w*.jsonl")):
        generation_rows.extend(read_jsonl_strict(path))
    generated = successful_generation_map(generation_rows)
    if set(generated) != set(manifest):
        raise ValueError(
            f"generation keys differ from manifest: missing={len(set(manifest)-set(generated))}, "
            f"extra={len(set(generated)-set(manifest))}"
        )
    ledger_path = args.out_dir / "ledgers" / f"score_w{args.worker_index}.jsonl"
    prior = unique_map(read_jsonl_strict(ledger_path), "prior score") if ledger_path.is_file() else {}
    if not set(prior).issubset(manifest):
        raise ValueError("score ledger contains keys outside manifest")
    pending = [
        row_key
        for index, row_key in enumerate(sorted(manifest))
        if index % args.num_workers == args.worker_index and row_key not in prior
    ]
    if not pending:
        print("NO_PENDING_ROWS")
        return 0
    import soundfile as sf
    import torch
    from scripts.batch3_online_harness import GateLabeler

    gate = GateLabeler(args.device)
    for row_key in pending:
        started = time.time()
        generation = generated[row_key]
        audio_path = Path(generation["audio_path"])
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        data, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)
        waveform = torch.from_numpy(data.T.copy())
        scoring_seed = seed_rng(row_key)
        ratio, near_silent = gate.ratio(waveform, int(sample_rate))
        present = int(is_vocal_present(ratio, near_silent))
        requested_vocal = int(manifest[row_key]["requested_vocal"])
        result = {
            **{field: manifest[row_key][field] for field in manifest[row_key]},
            "audio_path": str(audio_path),
            "vocal_energy_ratio": ratio,
            "near_silent": bool(near_silent),
            "present": present,
            "type_correct": int(present == requested_vocal),
            "scoring_seed": scoring_seed,
            "detector": "htdemucs/apply_model(shifts=1,split=True,overlap=0.1)",
            "runtime_s": time.time() - started,
            "host": socket.gethostname(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        }
        append_jsonl(ledger_path, result)
        print(json.dumps({"key": row_key, "type_correct": result["type_correct"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
