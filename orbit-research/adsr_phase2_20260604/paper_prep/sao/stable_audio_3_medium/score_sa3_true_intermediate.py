#!/usr/bin/env python3
"""Canonical Demucs scoring for decoded SA3 same-trajectory previews."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import soundfile as sf
import torch


def find_repo_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"cannot locate repository root from {path}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT))
THRESHOLD = 0.1791


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def successful_rows(rows: list[dict]) -> list[dict]:
    index: dict[int, dict] = {}
    for row in rows:
        if row.get("status") != "PASS":
            continue
        key = int(row["row_index"])
        if key in index and row["output_sha256"] != index[key]["output_sha256"]:
            raise ValueError(f"conflicting successful generation attempts for row {key}")
        index[key] = row
    return [index[key] for key in sorted(index)]


def load_audio(path: Path) -> tuple[torch.Tensor, int]:
    data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    return torch.from_numpy(data.T.copy()), int(sample_rate)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intermediate-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    args = parser.parse_args()
    if args.num_shards <= 0 or not 0 <= args.shard_index < args.num_shards:
        raise ValueError("invalid shard")

    from scripts.batch3_online_harness import GateLabeler

    generation = successful_rows(read_jsonl(args.intermediate_dir / "SA3_INTERMEDIATE_LEDGER.jsonl"))
    generation = [row for row in generation if int(row["row_index"]) % args.num_shards == args.shard_index]
    score_path = args.intermediate_dir / "SA3_INTERMEDIATE_DEMUCS_LEDGER.jsonl"
    done = {
        (int(row["row_index"]), str(row["stage"]))
        for row in read_jsonl(score_path)
        if score_path.exists() and row.get("ok")
    } if score_path.exists() else set()
    gate = GateLabeler(args.device)
    for row in generation:
        for stage, path_text in sorted(row["output_paths"].items()):
            key = (int(row["row_index"]), stage)
            if key in done:
                continue
            started = time.time()
            out = {
                "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
                "host": os.uname().nodename,
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
                "row_index": row["row_index"],
                "split": row["split"],
                "prompt_id": row["prompt_id"],
                "seed_idx": row["seed_idx"],
                "seed": row["seed"],
                "vocal_stratum": row["vocal_stratum"],
                "stage": stage,
                "audio_path": path_text,
                "threshold": THRESHOLD,
                "ok": False,
                "error": "",
            }
            try:
                waveform, sample_rate = load_audio(Path(path_text))
                ratio, near_silent = gate.ratio(waveform, sample_rate)
                out.update(
                    {
                        "vocal_energy_ratio": ratio,
                        "near_silent": near_silent,
                        "present": int(ratio >= THRESHOLD and not near_silent),
                        "input_rms": float(torch.sqrt(torch.mean(waveform.float() ** 2))),
                        "sample_rate": sample_rate,
                        "duration_s": waveform.shape[-1] / sample_rate,
                        "ok": True,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - exact row failure is evidence.
                out["error"] = f"{type(exc).__name__}: {exc}"
            out["elapsed_s"] = time.time() - started
            append_jsonl(score_path, out)
            print(json.dumps(out, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
