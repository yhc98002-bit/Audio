#!/usr/bin/env python3
"""Local-only Stable Audio 3 Medium smoke using downloaded ModelScope files."""

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


PROMPT = "30-second instrumental electronic track, no vocals, no speech, clean mix, steady beat, melodic synthesizer, high quality."


def patch_local_paths(model_config: dict, model_dir: Path) -> None:
    for cond in model_config["model"]["conditioning"]["configs"]:
        if cond.get("id") == "prompt" and cond.get("type") == "t5gemma":
            cfg = cond["config"]
            cfg["model_path"] = str(model_dir / "t5gemma-b-b-ul2")
            cfg.pop("repo_id", None)
            cfg.pop("subfolder", None)


def rms(path: Path) -> float:
    audio, _sr = torchaudio.load(str(path))
    return float(torch.sqrt(torch.mean(audio.float() ** 2)).item())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--cfg-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260708)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float16", choices=["float16", "bfloat16", "float32"])
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = args.out_dir / "audio"
    audio_dir.mkdir(exist_ok=True)
    ledger = args.out_dir / "SA3_SMOKE_LEDGER.jsonl"
    started = time.time()
    status = "FAIL"
    error = ""
    out_path = audio_dir / f"sa3_smoke_seed{args.seed}_dur{int(args.duration)}s.wav"
    try:
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
        torch.manual_seed(args.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(args.seed)
        model_config_path = args.model_dir / "model_config.json"
        ckpt_path = args.model_dir / "model.safetensors"
        with model_config_path.open() as handle:
            model_config = json.load(handle)
        patch_local_paths(model_config, args.model_dir)
        sample_rate = int(model_config["sample_rate"])
        model_half = args.dtype == "float16"
        model = load_diffusion_cond(
            model_config,
            str(ckpt_path),
            device=args.device,
            model_half=model_half,
        )
        if args.dtype == "bfloat16":
            model = model.to(torch.bfloat16)
        wrapped = StableAudioModel(model, model_config, args.device, model_half=model_half)
        with torch.inference_mode():
            output = wrapped.generate(
                prompt=PROMPT,
                negative_prompt="vocals, singing, speech, voice, choir",
                duration=float(args.duration),
                steps=args.steps,
                cfg_scale=args.cfg_scale,
                seed=args.seed,
                batch_size=1,
                sample_size=int(model_config["sample_size"]),
                sampler_type="pingpong",
                chunked_decode=True,
            )
        output = output[0]
        peak = torch.max(torch.abs(output)).detach()
        if not torch.isfinite(peak) or float(peak) <= 0:
            raise RuntimeError("generated waveform has invalid or zero peak")
        output = output.to(torch.float32).div(peak).clamp(-1, 1).cpu()
        torchaudio.save(str(out_path), output, sample_rate)
        measured_rms = rms(out_path)
        if not math.isfinite(measured_rms) or measured_rms <= 1e-5:
            raise RuntimeError(f"generated waveform is silent or near-silent: rms={measured_rms}")
        status = "PASS"
    except Exception as exc:  # noqa: BLE001 - ledger must keep exact failure.
        error = repr(exc)
        measured_rms = float("nan")
        sample_rate = ""
    elapsed = time.time() - started
    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "host": os.uname().nodename,
        "model_dir": str(args.model_dir),
        "prompt": PROMPT,
        "seed": args.seed,
        "duration_s_requested": args.duration,
        "steps": args.steps,
        "cfg_scale": args.cfg_scale,
        "device": args.device,
        "dtype": args.dtype,
        "status": status,
        "error": error,
        "output_path": str(out_path) if out_path.exists() else "",
        "sample_rate": sample_rate,
        "rms": measured_rms,
        "elapsed_s": elapsed,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "max_memory_allocated": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    if status != "PASS":
        raise SystemExit(error)
    print(json.dumps(row, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
