#!/usr/bin/env python3
"""Generate one sharded ACE-Step 1.5 replication manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
import time
import traceback
from pathlib import Path

import numpy as np


SOURCE_COMMIT = "6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0"
MODEL_ID = "ACE-Step/Ace-Step1.5:acestep-v15-turbo"


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


def unique_keys(rows: list[dict]) -> set[tuple[str, str, int]]:
    keys = []
    for row in rows:
        key = (str(row["prompt_id"]), str(row["condition"]), int(row["seed"]))
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate (prompt_id, condition, seed) rows")
    return set(keys)


def completed_keys(
    rows: list[dict], expected: set[tuple[str, str, int]]
) -> set[tuple[str, str, int]]:
    """Return successful keys while retaining failed attempts for audit."""
    pass_counts: dict[tuple[str, str, int], int] = {}
    for row in rows:
        row_key = (str(row["prompt_id"]), str(row["condition"]), int(row["seed"]))
        if row_key not in expected:
            raise ValueError(f"generation ledger key outside manifest: {row_key}")
        if row.get("status") == "PASS":
            pass_counts[row_key] = pass_counts.get(row_key, 0) + 1
    duplicates = [row_key for row_key, count in pass_counts.items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate successful generation key {duplicates[0]}")
    return set(pass_counts)


def conditioned_inputs(row: dict) -> tuple[str, str, bool]:
    text = str(row["text"])
    lyrics = str(row.get("lyrics") or "")
    instrumental = int(row["requested_vocal"]) == 0
    if row["condition"] == "recondition":
        if instrumental:
            text += ", strictly instrumental, no vocals, no singing, no speech, no choir"
        else:
            text += ", prominent clear human singing, lead vocal present throughout"
            structure = str(row.get("structure_hint") or "").strip()
            if structure:
                text += f", song structure: {structure}"
    elif row["condition"] != "baseline":
        raise ValueError(f"unknown condition {row['condition']!r}")
    return text, (lyrics if lyrics else "[Instrumental]"), instrumental


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def initialize_handler(source_root: Path, checkpoints_dir: Path):
    import torch
    from acestep.handler import AceStepHandler

    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(checkpoints_dir)
    handler = AceStepHandler()
    message, success = handler.initialize_service(
        project_root=str(source_root),
        config_path="acestep-v15-turbo",
        device="cuda",
        use_flash_attention=False,
        compile_model=False,
        offload_to_cpu=False,
        offload_dit_to_cpu=False,
        quantization=None,
        prefer_source="modelscope",
        use_mlx_dit=False,
    )
    if not success:
        raise RuntimeError(message)
    return handler, message, torch


def materialize_generated_audio(source: Path, save_dir: Path) -> Path:
    """Atomically copy a closed node-local audio file into shared evidence storage."""
    if not source.is_file():
        raise FileNotFoundError(source)
    save_dir.mkdir(parents=True, exist_ok=True)
    destination = save_dir / source.name
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite prior attempt: {destination}")
    partial = destination.with_name(f".{destination.name}.partial.{os.getpid()}")
    shutil.copy2(source, partial)
    os.replace(partial, destination)
    return destination.resolve()


def generate_one(
    handler, row: dict, save_dir: Path, scratch_dir: Path
) -> tuple[Path, Path]:
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    text, lyrics, instrumental = conditioned_inputs(row)
    params = GenerationParams(
        task_type="text2music",
        caption=text,
        lyrics=lyrics,
        instrumental=instrumental,
        vocal_language="unknown" if instrumental else "en",
        duration=float(row["duration_target"]),
        inference_steps=8,
        seed=int(row["seed"]),
        guidance_scale=1.0,
        shift=3.0,
        infer_method="ode",
        thinking=False,
        use_cot_metas=False,
        use_cot_caption=False,
        use_cot_lyrics=False,
        use_cot_language=False,
    )
    config = GenerationConfig(
        batch_size=1,
        use_random_seed=False,
        seeds=[int(row["seed"])],
        audio_format="flac",
    )
    scratch_dir.mkdir(parents=True, exist_ok=True)
    result = generate_music(handler, None, params, config, save_dir=str(scratch_dir))
    if not result.success or len(result.audios) != 1:
        raise RuntimeError(result.error or f"expected one audio, got {len(result.audios)}")
    path = Path(result.audios[0]["path"])
    if not path.is_file() and not path.is_absolute():
        path = scratch_dir / path
    if not path.is_file():
        raise FileNotFoundError(path)
    return materialize_generated_audio(path, save_dir), path.resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--checkpoints-dir", type=Path, required=True)
    parser.add_argument("--worker-index", type=int, required=True)
    parser.add_argument("--num-workers", type=int, required=True)
    parser.add_argument(
        "--scratch-root", type=Path, default=Path("/dev/shm/adsr_v15_replication")
    )
    args = parser.parse_args()
    if not 0 <= args.worker_index < args.num_workers:
        raise ValueError("worker index must be in [0, num_workers)")
    manifest = read_jsonl_strict(args.manifest)
    expected_keys = unique_keys(manifest)
    ledger_path = args.out_dir / "ledgers" / f"generation_w{args.worker_index}.jsonl"
    prior = read_jsonl_strict(ledger_path) if ledger_path.is_file() else []
    prior_keys = completed_keys(prior, expected_keys)
    work = [
        row
        for index, row in enumerate(manifest)
        if index % args.num_workers == args.worker_index
        and (row["prompt_id"], row["condition"], int(row["seed"])) not in prior_keys
    ]
    if not work:
        print("NO_PENDING_ROWS")
        return 0
    handler, init_message, torch = initialize_handler(args.source_root, args.checkpoints_dir)
    for row in work:
        started = time.time()
        status = "PASS"
        error = None
        audio_path = None
        scratch_audio_path = None
        audio_sha = None
        sample_rate = None
        duration_s = None
        rms = None
        try:
            clip_dir = args.out_dir / "audio" / row["prompt_id"] / row["condition"] / str(row["seed"])
            clip_dir.mkdir(parents=True, exist_ok=True)
            scratch_dir = (
                args.scratch_root
                / f"{socket.gethostname()}_{os.getpid()}"
                / row["prompt_id"]
                / row["condition"]
                / str(row["seed"])
            )
            audio_path, scratch_audio_path = generate_one(
                handler, row, clip_dir, scratch_dir
            )
            import soundfile as sf

            info = sf.info(audio_path)
            data, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)
            duration_s = len(data) / int(sample_rate)
            rms = float(np.sqrt(np.mean(np.square(data, dtype=np.float64))))
            if duration_s <= 5 or rms <= 1e-5:
                raise ValueError(f"invalid output duration={duration_s:.3f}, rms={rms:.8f}")
            audio_sha = sha256_file(audio_path)
        except Exception as exc:  # noqa: BLE001
            status = "FAIL"
            error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        ledger_row = {
            **row,
            "status": status,
            "error": error,
            "audio_path": str(audio_path) if audio_path else None,
            "scratch_audio_path": str(scratch_audio_path) if scratch_audio_path else None,
            "audio_sha256": audio_sha,
            "sample_rate": sample_rate,
            "duration_s": duration_s,
            "rms": rms,
            "runtime_s": time.time() - started,
            "host": socket.gethostname(),
            "gpu": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "model_id": MODEL_ID,
            "source_commit": SOURCE_COMMIT,
            "source_root": str(args.source_root.resolve()),
            "checkpoints_dir": str(args.checkpoints_dir.resolve()),
            "inference": {"steps": 8, "shift": 3.0, "method": "ode", "thinking": False},
            "model_init_message": init_message,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "worker_index": args.worker_index,
        }
        append_jsonl(ledger_path, ledger_row)
        print(json.dumps({"prompt_id": row["prompt_id"], "seed": row["seed"], "status": status}), flush=True)
        if status != "PASS":
            # A NaN generation can leave the loaded model in a poisoned state;
            # stop this process and let the append-only retry path reinitialize.
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
