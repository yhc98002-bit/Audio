#!/usr/bin/env python3
"""Replay SA3 seeds while decoding clean-latent estimates from one trajectory."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

import torch
import torchaudio


def find_repo_root(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"cannot locate repository root from {path}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "src"))

from mprm.data.prompts import Prompt  # noqa: E402
from mprm.inference.sa3 import StableAudio3MediumModel  # noqa: E402


SELECTION_SEED = 20260709
DEFAULT_FULL = ROOT / "paper_prep/sao/stable_audio_3_medium/prevalence_full500"
DEFAULT_LOW = ROOT / "paper_prep/sao/stable_audio_3_medium/observability/lowstep_full500"


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
    return rows


def unique_index(rows: list[dict], keys: tuple[str, ...], source: str) -> dict[tuple, dict]:
    index: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        if key in index and row != index[key]:
            raise ValueError(f"conflicting duplicate {source} key {key}")
        index[key] = row
    return index


def select_manifest_rows(
    full_manifest: list[dict],
    full_scores: list[dict],
    low_scores: list[dict],
    *,
    per_request_stratum: int = 48,
    seed: int = SELECTION_SEED,
) -> list[dict]:
    manifest = unique_index(full_manifest, ("prompt_id", "seed_idx"), "full manifest")
    full = unique_index([row for row in full_scores if row.get("ok")], ("prompt_id", "seed_idx"), "full score")
    low = unique_index([row for row in low_scores if row.get("ok")], ("prompt_id", "seed_idx"), "low score")
    common = sorted(set(manifest) & set(full) & set(low))
    by_request: dict[str, dict[str, list[tuple]]] = {"vocal": {}, "instrumental": {}}
    for key in common:
        row = full[key]
        request = str(row["vocal_stratum"])
        if request not in by_request:
            continue
        by_request[request].setdefault(str(row["prompt_id"]), []).append(key)

    rng = random.Random(seed)
    output: list[dict] = []
    for request in ("instrumental", "vocal"):
        prompt_ids = sorted(by_request[request])
        rng.shuffle(prompt_ids)
        if len(prompt_ids) < per_request_stratum:
            raise ValueError(f"need {per_request_stratum} {request} prompts, found {len(prompt_ids)}")
        chosen = prompt_ids[:per_request_stratum]
        rng.shuffle(chosen)
        for request_index, prompt_id in enumerate(chosen):
            candidates = sorted(by_request[request][prompt_id])
            key = candidates[rng.randrange(len(candidates))]
            source = manifest[key]
            final = full[key]
            independent = low[key]
            split = "test" if request_index % 2 else "development"
            output.append(
                {
                    "row_index": len(output),
                    "split": split,
                    "selection_seed": seed,
                    "prompt_id": prompt_id,
                    "seed_idx": int(source["seed_idx"]),
                    "seed": int(source["seed"]),
                    "prompt": source["prompt"],
                    "duration_s": float(source["duration_s"]),
                    "vocal_stratum": request,
                    "stratum": source.get("stratum", ""),
                    "old_final_audio_path": final["audio_path"],
                    "old_final_ratio": float(final["vocal_energy_ratio"]),
                    "old_final_present": int(final["present"]),
                    "independent_lowstep_audio_path": independent["audio_path"],
                    "independent_lowstep_ratio": float(independent["vocal_energy_ratio"]),
                    "independent_lowstep_present": int(independent["present"]),
                }
            )
    return sorted(output, key=lambda row: int(row["row_index"]))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_pass_rows(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {int(row["row_index"]) for row in read_jsonl(path) if row.get("status") == "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--full-dir", type=Path, default=DEFAULT_FULL)
    parser.add_argument("--low-dir", type=Path, default=DEFAULT_LOW)
    parser.add_argument("--per-request-stratum", type=int, default=48)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--capture-steps", default="0,1,2,3")
    parser.add_argument("--dtype", choices=["float16", "bfloat16", "float32"], default="bfloat16")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "SA3_INTERMEDIATE_MANIFEST.jsonl"
    if manifest_path.exists():
        rows = read_jsonl(manifest_path)
    else:
        rows = select_manifest_rows(
            read_jsonl(args.full_dir / "SA3_PREVALENCE_MANIFEST.jsonl"),
            read_jsonl(args.full_dir / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"),
            read_jsonl(args.low_dir / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"),
            per_request_stratum=args.per_request_stratum,
        )
        for row in rows:
            append_jsonl(manifest_path, row)

    shard = [row for row in rows if int(row["row_index"]) % args.num_shards == args.shard_index]
    if args.max_rows:
        shard = shard[: args.max_rows]
    ledger_path = args.out_dir / "SA3_INTERMEDIATE_LEDGER.jsonl"
    done = existing_pass_rows(ledger_path)
    model = StableAudio3MediumModel(args.model_dir, device=args.device, dtype=args.dtype)
    capture_steps = [int(value) for value in args.capture_steps.split(",") if value.strip()]

    for row in shard:
        if int(row["row_index"]) in done:
            continue
        started = time.time()
        base = args.out_dir / "audio" / row["prompt_id"] / f"seed_{int(row['seed'])}"
        base.mkdir(parents=True, exist_ok=True)
        output_paths: dict[str, str] = {}
        status = "FAIL"
        error = ""
        capture_metadata: list[dict] = []
        try:
            prompt = Prompt(
                prompt_id=row["prompt_id"],
                text=row["prompt"],
                lyrics=None,
                structure_hint=None,
                duration_target=float(row["duration_s"]),
            )
            result = model.sample(
                prompt,
                seed=int(row["seed"]),
                cfg_scale=1.0,
                steps=args.steps,
                return_trajectory=True,
                extras={"capture_steps": capture_steps, "duration_s": float(row["duration_s"])},
            )
            for step, audio in zip(capture_steps, result.trajectory or []):
                path = base / f"same_trajectory_step_{step}.wav"
                torchaudio.save(str(path), audio[0], result.sample_rate)
                output_paths[f"same_trajectory_step_{step}"] = str(path)
            final_path = base / "final_replay.wav"
            torchaudio.save(str(final_path), result.waveform[0], result.sample_rate)
            output_paths["final_replay"] = str(final_path)
            capture_metadata = result.extras["capture_metadata"]
            status = "PASS"
        except Exception as exc:  # noqa: BLE001 - exact row failure is ledger evidence.
            error = f"{type(exc).__name__}: {exc}"
        ledger_row = {
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            **row,
            "steps": args.steps,
            "capture_steps": capture_steps,
            "status": status,
            "error": error,
            "output_paths": output_paths,
            "output_sha256": {name: sha256_file(Path(path)) for name, path in output_paths.items()},
            "capture_metadata": capture_metadata,
            "elapsed_s": time.time() - started,
            "max_memory_allocated": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,
        }
        append_jsonl(ledger_path, ledger_row)
        print(json.dumps(ledger_row, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
