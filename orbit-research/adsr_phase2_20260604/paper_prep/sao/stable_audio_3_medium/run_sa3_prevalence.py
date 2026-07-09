#!/usr/bin/env python3
"""Run a deterministic SA3 Medium prevalence pilot from ADSR prompt files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import time
from pathlib import Path

import torch
import torchaudio

from stable_audio_3.loading_utils import load_diffusion_cond
from stable_audio_3.model import StableAudioModel


DEFAULT_SELECTED = Path("orbit-research/adsr_phase2_20260604/batch3/batch3_selected_prompts_256.jsonl")
DEFAULT_HELD_OUT = Path("configs/prompts/held_out.jsonl")
DEFAULT_DEV = Path("configs/prompts/dev.jsonl")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_prompt_index(paths: list[Path]) -> dict[str, dict]:
    prompts: dict[str, dict] = {}
    for path in paths:
        for row in read_jsonl(path):
            prompts[row["prompt_id"]] = row
    return prompts


def compose_prompt(prompt_row: dict, selected_row: dict) -> str:
    text = prompt_row["text"].strip()
    lyrics = prompt_row.get("lyrics")
    vocal_stratum = selected_row.get("vocal_stratum") or prompt_row.get("strata", {}).get("vocal_vs_instrumental")
    parts = [text]
    if lyrics:
        parts.append("Lyrics: " + str(lyrics).replace("\n", " / "))
    if vocal_stratum == "instrumental" and "no vocals" not in text.lower():
        parts.append("Instrumental only; no vocals, no singing, no speech.")
    return " ".join(parts)


def build_manifest(
    selected_path: Path,
    prompt_paths: list[Path],
    manifest_path: Path,
    limit_prompts: int,
    seeds_per_prompt: int,
    duration: float,
) -> list[dict]:
    selected = read_jsonl(selected_path)[:limit_prompts]
    prompt_index = load_prompt_index(prompt_paths)
    rows: list[dict] = []
    for prompt_idx, selected_row in enumerate(selected):
        prompt_id = selected_row["prompt_id"]
        prompt_row = prompt_index.get(prompt_id)
        if prompt_row is None:
            raise RuntimeError(f"prompt_id {prompt_id} not found in prompt sources")
        for seed_idx in range(seeds_per_prompt):
            seed = 2026070800 + prompt_idx * 100 + seed_idx
            out_rel = (
                Path("audio")
                / f"{prompt_id}"
                / f"sa3_{prompt_id}_s{seed_idx:02d}_{seed}.wav"
            )
            rows.append(
                {
                    "row_index": len(rows),
                    "prompt_id": prompt_id,
                    "prompt_index": prompt_idx,
                    "selected_row": selected_row,
                    "prompt_source": selected_row.get("prompt_source", ""),
                    "vocal_stratum": selected_row.get("vocal_stratum")
                    or prompt_row.get("strata", {}).get("vocal_vs_instrumental", ""),
                    "stratum": selected_row.get("stratum", ""),
                    "prompt": compose_prompt(prompt_row, selected_row),
                    "duration_s": duration,
                    "seed_idx": seed_idx,
                    "seed": seed,
                    "output_rel": str(out_rel),
                }
            )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return rows


def patch_local_paths(model_config: dict, model_dir: Path) -> None:
    for cond in model_config["model"]["conditioning"]["configs"]:
        if cond.get("id") == "prompt" and cond.get("type") == "t5gemma":
            cfg = cond["config"]
            cfg["model_path"] = str(model_dir / "t5gemma-b-b-ul2")
            cfg.pop("repo_id", None)
            cfg.pop("subfolder", None)


def load_model(model_dir: Path, device: str, dtype: str) -> StableAudioModel:
    with (model_dir / "model_config.json").open("r", encoding="utf-8") as handle:
        model_config = json.load(handle)
    patch_local_paths(model_config, model_dir)
    model_half = dtype == "float16"
    model = load_diffusion_cond(
        model_config,
        str(model_dir / "model.safetensors"),
        device=device,
        model_half=model_half,
    )
    if dtype == "bfloat16":
        model = model.to(torch.bfloat16)
    return StableAudioModel(model, model_config, device, model_half=model_half)


def rms_tensor(audio: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean(audio.float() ** 2)).item())


def existing_pass_keys(ledger_path: Path) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    if not ledger_path.exists():
        return keys
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("status") == "PASS":
                keys.add((str(row.get("prompt_id")), int(row.get("seed_idx"))))
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--selected-prompts", type=Path, default=DEFAULT_SELECTED)
    parser.add_argument("--prompt-jsonl", type=Path, action="append")
    parser.add_argument("--limit-prompts", type=int, default=128)
    parser.add_argument("--seeds-per-prompt", type=int, default=8)
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--cfg-scale", type=float, default=1.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float16", choices=["float16", "bfloat16", "float32"])
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    prompt_paths = args.prompt_jsonl or [DEFAULT_HELD_OUT, DEFAULT_DEV]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "audio").mkdir(exist_ok=True)
    manifest_path = args.out_dir / "SA3_PREVALENCE_MANIFEST.jsonl"
    if manifest_path.exists():
        rows = read_jsonl(manifest_path)
    else:
        rows = build_manifest(
            args.selected_prompts,
            prompt_paths,
            manifest_path,
            args.limit_prompts,
            args.seeds_per_prompt,
            args.duration,
        )

    shard_rows = [
        row for row in rows if int(row["row_index"]) % args.num_shards == args.shard_index
    ]
    if args.max_rows > 0:
        shard_rows = shard_rows[: args.max_rows]

    ledger_path = args.out_dir / "SA3_PREVALENCE_LEDGER.jsonl"
    pass_keys = existing_pass_keys(ledger_path)
    model = load_model(args.model_dir, args.device, args.dtype)
    sample_size = int(model.model_config["sample_size"])
    sample_rate = int(model.model.sample_rate)

    for row in shard_rows:
        key = (row["prompt_id"], int(row["seed_idx"]))
        out_path = args.out_dir / row["output_rel"]
        if key in pass_keys and out_path.exists():
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.time()
        status = "FAIL"
        error = ""
        measured_rms = float("nan")
        frames = 0
        try:
            seed = int(row["seed"])
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
            with torch.inference_mode():
                audio = model.generate(
                    prompt=row["prompt"],
                    negative_prompt=None,
                    duration=float(row["duration_s"]),
                    steps=args.steps,
                    cfg_scale=args.cfg_scale,
                    seed=seed,
                    batch_size=1,
                    sample_size=sample_size,
                    sampler_type="pingpong",
                    chunked_decode=True,
                    disable_tqdm=True,
                )
            audio = audio[0].detach().to(torch.float32).clamp(-1, 1).cpu()
            measured_rms = rms_tensor(audio)
            if not math.isfinite(measured_rms) or measured_rms <= 1e-5:
                raise RuntimeError(f"near-silent or invalid output rms={measured_rms}")
            torchaudio.save(str(out_path), audio, sample_rate)
            frames = int(audio.shape[-1])
            status = "PASS"
        except Exception as exc:  # noqa: BLE001 - row ledger must keep exact failure.
            error = repr(exc)
        elapsed = time.time() - started
        ledger_row = {
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
            "row_index": row["row_index"],
            "prompt_id": row["prompt_id"],
            "prompt_index": row["prompt_index"],
            "stratum": row.get("stratum", ""),
            "vocal_stratum": row.get("vocal_stratum", ""),
            "seed_idx": row["seed_idx"],
            "seed": row["seed"],
            "duration_s_requested": row["duration_s"],
            "steps": args.steps,
            "cfg_scale": args.cfg_scale,
            "status": status,
            "error": error,
            "output_path": str(out_path) if out_path.exists() else "",
            "sample_rate": sample_rate,
            "frames": frames,
            "rms": measured_rms,
            "elapsed_s": elapsed,
            "max_memory_allocated": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,
        }
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(ledger_row, sort_keys=True) + "\n")
        print(json.dumps(ledger_row, sort_keys=True), flush=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
