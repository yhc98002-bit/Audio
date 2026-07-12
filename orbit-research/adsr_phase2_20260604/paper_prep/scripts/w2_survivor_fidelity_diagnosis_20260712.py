#!/usr/bin/env python3
"""Diagnose the first-candidate survivor under exact historical initialization paths."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
PAPER = ROOT / "paper_prep"
OUT = PAPER / "w2_execution_20260712/spine_reconstruction/survivor_fidelity_diagnosis"
LEDGER = OUT / "SURVIVOR_FIDELITY_LEDGER.jsonl"
REPORT = OUT / "SURVIVOR_FIDELITY_REPORT.md"
ORIGINAL = ROOT / "runs/adsr_recollect_smoke_20260604/shard00/audio/dev_0000/candidate_00_seed2026052700.wav"
FINAL_ONLY = PAPER / "w2_execution_20260712/spine_reconstruction/survivor_audit_replay/dev_0000/candidate_00_seed2026052700.wav"
SEED = 2026052700


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append(row: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decoded_hash(path: Path) -> str:
    import soundfile as sf

    samples, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    canonical = np.ascontiguousarray(samples.T, dtype="<f4")
    header = np.asarray((sample_rate, *canonical.shape), dtype="<i8")
    digest = hashlib.sha256(header.tobytes())
    digest.update(canonical.tobytes())
    return digest.hexdigest()


def generate(mode: str) -> dict:
    if mode not in {"trajectory_capture", "historical_reward_init"}:
        raise ValueError(mode)
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("exactly one visible GPU is required")
    import torch

    from mprm.common.config import load_config
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row
    from scripts.launch_baseline import _assert_reward_axes_match_policy, _build_reward_models, load_gate_eval_policy

    if mode == "historical_reward_init":
        gate_policy, _ = load_gate_eval_policy(ROOT / "configs/eval/gate_v2.yaml.draft")
        config = load_config(ROOT / "configs/baselines/r2_bon.yaml")
        reward_models = _build_reward_models(config.reward)
        _assert_reward_axes_match_policy(reward_models, gate_policy)
    prompt = next(row for row in read_jsonl(ROOT / "configs/prompts/dev.jsonl") if row["prompt_id"] == "dev_0000")
    model = AceStepModel(device="cuda", dtype="bfloat16")
    output = OUT / f"{mode}.wav"
    if output.exists():
        raise FileExistsError(output)
    started = time.time()
    seed_everything(SEED)
    result = model.sample(
        _prompt_from_row(prompt),
        seed=SEED,
        cfg_scale=5.0,
        steps=30,
        return_trajectory=True,
        extras={
            "cfg_type": "cfg",
            "guidance_interval": 0.5,
            "use_erg_tag": False,
            "use_erg_lyric": False,
            "use_erg_diffusion": False,
        },
    )
    save_audio(output, result.waveform, result.sample_rate)
    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "mode": mode,
        "seed": SEED,
        "return_trajectory": True,
        "historical_reward_models_constructed": mode == "historical_reward_init",
        "trajectory_steps": len(result.trajectory or []),
        "output_path": str(output.relative_to(ROOT)),
        "waveform_sha256": file_hash(output),
        "decoded_audio_sha256": decoded_hash(output),
        "original_decoded_audio_sha256": decoded_hash(ORIGINAL),
        "exact_vs_original": decoded_hash(output) == decoded_hash(ORIGINAL),
        "elapsed_s": round(time.time() - started, 6),
        "torch_version": torch.__version__,
        "gpu_name": torch.cuda.get_device_name(0),
        "status": "PASS",
    }
    append(record)
    return record


def report() -> dict:
    rows = [row for row in read_jsonl(LEDGER) if row.get("status") == "PASS"]
    by_mode = {row["mode"]: row for row in rows}
    original_hash = decoded_hash(ORIGINAL)
    final_hash = decoded_hash(FINAL_ONLY)
    exact_modes = [mode for mode, row in by_mode.items() if row["exact_vs_original"]]
    status = "PASS_EXACT_PATH_FOUND" if exact_modes else "FAIL_NO_EXACT_PATH"
    REPORT.write_text(
        "# First-Candidate Survivor Fidelity Diagnosis\n\n"
        f"`SURVIVOR_FIDELITY_STATUS = {status}`\n\n"
        f"- Historical survivor decoded hash: `{original_hash}`\n"
        f"- Final-only replay decoded hash: `{final_hash}` (exact: {final_hash == original_hash})\n"
        f"- Exact historical initialization modes: {', '.join(exact_modes) if exact_modes else 'none'}\n\n"
        "The lone survivor is the first candidate generated by the original collection process. "
        "This diagnosis isolates trajectory capture and historical reward-model construction from "
        "the 50 independent final-only controls. No frozen artifact was changed.\n",
        encoding="utf-8",
    )
    return {"status": status, "exact_modes": exact_modes, "modes_run": sorted(by_mode)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generation = sub.add_parser("generate")
    generation.add_argument("--mode", choices=["trajectory_capture", "historical_reward_init"], required=True)
    sub.add_parser("report")
    args = parser.parse_args()
    result = generate(args.mode) if args.command == "generate" else report()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status", "PASS").startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
