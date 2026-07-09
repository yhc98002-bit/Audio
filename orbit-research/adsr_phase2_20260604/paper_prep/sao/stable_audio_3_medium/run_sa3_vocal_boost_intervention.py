#!/usr/bin/env python3
"""Run a paired SA3 prompt intervention for vocal-miss failures."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path

import torch
import torchaudio

from stable_audio_3.loading_utils import load_diffusion_cond
from stable_audio_3.model import StableAudioModel


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
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


def boosted(prompt: str) -> str:
    return (
        "Clear lead human singing with audible vocals, prominent sung vocal melody, "
        "lead voice present throughout, intelligible vocal line. "
        + prompt
        + " The human voice must be clearly audible and central in the mix."
    )


def rms_tensor(audio: torch.Tensor) -> float:
    return float(torch.sqrt(torch.mean(audio.float() ** 2)).item())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-prompts", type=int, default=32)
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--cfg-scale", type=float, default=1.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float16", choices=["float16", "bfloat16", "float32"])
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "audio").mkdir(exist_ok=True)
    baseline_manifest = read_jsonl(args.baseline_dir / "SA3_PREVALENCE_MANIFEST.jsonl")
    baseline_scores = [
        row
        for row in read_jsonl(args.baseline_dir / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl")
        if row.get("ok") and row.get("vocal_stratum") == "vocal"
    ]
    manifest_by_key = {
        (row["prompt_id"], int(row["seed_idx"])): row for row in baseline_manifest
    }
    by_prompt: dict[str, list[dict]] = defaultdict(list)
    for row in baseline_scores:
        by_prompt[row["prompt_id"]].append(row)
    selected_prompts = [
        pid for pid, rows in by_prompt.items() if any(int(r["type_correct"]) == 0 for r in rows)
    ][: args.max_prompts]
    rows = []
    for pid in selected_prompts:
        for score_row in sorted(by_prompt[pid], key=lambda r: int(r["seed_idx"])):
            key = (pid, int(score_row["seed_idx"]))
            base_manifest = manifest_by_key[key]
            out_rel = (
                Path("audio")
                / pid
                / f"sa3_vocal_boost_{pid}_s{int(score_row['seed_idx']):02d}_{int(score_row['seed'])}.wav"
            )
            rows.append(
                {
                    "row_index": len(rows),
                    "baseline_row_index": score_row["row_index"],
                    "prompt_id": pid,
                    "prompt_index": base_manifest["prompt_index"],
                    "stratum": base_manifest.get("stratum", ""),
                    "vocal_stratum": "vocal",
                    "seed_idx": int(score_row["seed_idx"]),
                    "seed": int(score_row["seed"]),
                    "duration_s": args.duration,
                    "condition": "vocal_boost",
                    "prompt": boosted(base_manifest["prompt"]),
                    "output_rel": str(out_rel),
                }
            )
    manifest_path = args.out_dir / "SA3_INTERVENTION_MANIFEST.jsonl"
    with manifest_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    model = load_model(args.model_dir, args.device, args.dtype)
    sample_size = int(model.model_config["sample_size"])
    sample_rate = int(model.model.sample_rate)
    ledger_path = args.out_dir / "SA3_PREVALENCE_LEDGER.jsonl"
    for row in rows:
        out_path = args.out_dir / row["output_rel"]
        if out_path.exists():
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
        except Exception as exc:  # noqa: BLE001
            error = repr(exc)
        ledger_row = {
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
            "row_index": row["row_index"],
            "baseline_row_index": row["baseline_row_index"],
            "prompt_id": row["prompt_id"],
            "prompt_index": row["prompt_index"],
            "stratum": row.get("stratum", ""),
            "vocal_stratum": row.get("vocal_stratum", ""),
            "seed_idx": row["seed_idx"],
            "seed": row["seed"],
            "duration_s_requested": row["duration_s"],
            "condition": row["condition"],
            "steps": args.steps,
            "cfg_scale": args.cfg_scale,
            "status": status,
            "error": error,
            "output_path": str(out_path) if out_path.exists() else "",
            "sample_rate": sample_rate,
            "frames": frames,
            "rms": measured_rms,
            "elapsed_s": time.time() - started,
            "max_memory_allocated": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,
        }
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(ledger_row, sort_keys=True) + "\n")
        print(json.dumps(ledger_row, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
