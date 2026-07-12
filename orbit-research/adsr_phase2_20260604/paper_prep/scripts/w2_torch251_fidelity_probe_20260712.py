#!/usr/bin/env python3
"""Replay 50 frozen controls plus the lone spine survivor under torch 2.5.1."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
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
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))

import w2_spine_reconstruct_20260712 as spine  # noqa: E402


OUT = ROOT / "paper_prep/w2_execution_20260712/spine_torch251_fidelity_probe"
MANIFEST = OUT / "SPINE_TORCH251_FIDELITY_MANIFEST.csv"
LEDGER_DIR = OUT / "ledgers"
AUDIO_DIR = OUT / "audio"
AUDIT_JSON = OUT / "SPINE_TORCH251_FIDELITY_AUDIT.json"
AUDIT_MD = OUT / "SPINE_TORCH251_FIDELITY_REPORT.md"
CONTROLS = ROOT / "paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_CONTROL_MANIFEST.csv"
EXPECTED_ROWS = 51


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_manifest() -> dict:
    spine_rows = read_csv(spine.MANIFEST)
    by_key = {(row["prompt_id"], int(row["candidate_index"])): row for row in spine_rows}
    rows = []
    for control in read_csv(CONTROLS):
        source = by_key[(control["prompt_id"], int(control["candidate_index"]))]
        rows.append(
            {
                "probe_id": control["control_id"],
                "role": "frozen_regeneration_control",
                "task_id": source["task_id"],
                "prompt_id": source["prompt_id"],
                "candidate_index": source["candidate_index"],
                "seed": control["source_seed"],
                "prompt_serialized_sha256": source["prompt_serialized_sha256"],
                "expected_path": control["replay_path"],
                "output_path": str((AUDIO_DIR / f"{control['control_id']}.wav").relative_to(ROOT)),
            }
        )
    survivor = next(row for row in spine_rows if row["generation_role"] == "surviving_original_audit_replay")
    rows.append(
        {
            "probe_id": "surviving_original_dev_0000_cand00",
            "role": "surviving_original",
            "task_id": survivor["task_id"],
            "prompt_id": survivor["prompt_id"],
            "candidate_index": survivor["candidate_index"],
            "seed": survivor["candidate_seed"],
            "prompt_serialized_sha256": survivor["prompt_serialized_sha256"],
            "expected_path": survivor["source_audio_path"],
            "output_path": str((AUDIO_DIR / "surviving_original_dev_0000_cand00.wav").relative_to(ROOT)),
        }
    )
    if len(rows) != EXPECTED_ROWS or len({row["probe_id"] for row in rows}) != EXPECTED_ROWS:
        raise AssertionError("fidelity probe cardinality mismatch")
    write_csv(MANIFEST, rows)
    return {"rows": len(rows), "controls": 50, "survivors": 1}


def latest() -> dict[str, dict]:
    result = {}
    for path in sorted(LEDGER_DIR.glob("probe_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                result[row["probe_id"]] = row
    return result


def probe_passes(successful_rows: int, details: list[dict]) -> bool:
    return (
        successful_rows == EXPECTED_ROWS
        and len(details) == EXPECTED_ROWS
        and all(bool(row.get("exact")) for row in details)
    )


def generate(worker_index: int, num_workers: int) -> int:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("exactly one CUDA_VISIBLE_DEVICES entry is required")

    import soundfile as sf
    import torch
    import torchaudio
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row

    if torch.__version__ != "2.5.1+cu121" or torchaudio.__version__ != "2.5.1+cu121":
        raise RuntimeError(f"wrong replay runtime: torch={torch.__version__}, torchaudio={torchaudio.__version__}")
    tasks = read_csv(MANIFEST)
    mine = tasks[worker_index::num_workers]
    done = latest()
    prompts = spine.prompt_index()
    model = AceStepModel(device="cuda", dtype="bfloat16")
    ledger = LEDGER_DIR / f"probe_w{worker_index}.jsonl"
    for task in mine:
        if task["probe_id"] in done:
            continue
        started = time.time()
        output = ROOT / task["output_path"]
        record = {
            **task,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "torch_version": torch.__version__,
            "torchaudio_version": torchaudio.__version__,
            "torch_cuda_build": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(0),
            "status": "FAIL",
            "error": "",
        }
        try:
            prompt = prompts[task["prompt_id"]]
            prompt.pop("_source_path")
            if spine.canonical_json_hash(prompt) != task["prompt_serialized_sha256"]:
                raise RuntimeError("prompt serialization hash mismatch")
            seed = int(task["seed"])
            seed_everything(seed)
            result = model.sample(
                _prompt_from_row(prompt),
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
            output.parent.mkdir(parents=True, exist_ok=True)
            save_audio(output, result.waveform, result.sample_rate)
            samples, sample_rate = sf.read(str(output), always_2d=True, dtype="float32")
            duration = len(samples) / sample_rate
            rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
            if duration <= 1 or rms <= 1e-7:
                raise RuntimeError(f"invalid output duration={duration}, rms={rms}")
            record.update(
                {
                    "status": "PASS",
                    "sample_rate": sample_rate,
                    "duration_s": duration,
                    "rms": rms,
                    "near_silent": bool(20 * math.log10(max(rms, 1e-12)) < -60),
                    "waveform_sha256": spine.sha256_file(output),
                    "decoded_audio_sha256": spine.decoded_audio_hash(samples, sample_rate),
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_s"] = round(time.time() - started, 6)
        append_jsonl(ledger, record)
        print(json.dumps(record, sort_keys=True), flush=True)
        if record["status"] != "PASS":
            return 1
    return 0


def audit() -> dict:
    import soundfile as sf

    tasks = read_csv(MANIFEST)
    results = latest()
    details = []
    for task in tasks:
        result = results.get(task["probe_id"])
        output = ROOT / task["output_path"]
        expected = Path(task["expected_path"])
        if not expected.is_absolute():
            expected = ROOT / expected
        exact = False
        if result and output.is_file() and expected.is_file():
            generated_samples, generated_sr = sf.read(str(output), always_2d=True, dtype="float32")
            expected_samples, expected_sr = sf.read(str(expected), always_2d=True, dtype="float32")
            exact = spine.decoded_audio_hash(generated_samples, generated_sr) == spine.decoded_audio_hash(expected_samples, expected_sr)
        details.append({"probe_id": task["probe_id"], "role": task["role"], "exact": exact})
    controls = [row for row in details if row["role"] == "frozen_regeneration_control"]
    survivors = [row for row in details if row["role"] == "surviving_original"]
    passed = probe_passes(len(results), details)
    report = {
        "status": "PASS_EXACT_51_OF_51" if passed else "FAIL_STOP_FULL_REPLAY",
        "manifest_rows": len(tasks),
        "successful_rows": len(results),
        "exact_controls": sum(row["exact"] for row in controls),
        "control_rows": len(controls),
        "exact_survivors": sum(row["exact"] for row in survivors),
        "survivor_rows": len(survivors),
        "full_replay_authorized_by_probe": passed,
        "details": details,
    }
    AUDIT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT_MD.write_text(
        "# Spine torch-2.5.1 Fidelity Probe\n\n"
        f"`SPINE_TORCH251_PROBE_STATUS = {report['status']}`\n\n"
        f"- Successful rows: {len(results)}/{EXPECTED_ROWS}\n"
        f"- Exact frozen controls: {report['exact_controls']}/{report['control_rows']}\n"
        f"- Exact surviving originals: {report['exact_survivors']}/{report['survivor_rows']}\n"
        f"- Full replay authorized by the probe: {str(passed).lower()}\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-manifest")
    generation = sub.add_parser("generate")
    generation.add_argument("--worker-index", type=int, required=True)
    generation.add_argument("--num-workers", type=int, required=True)
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.command == "build-manifest":
        print(json.dumps(build_manifest(), indent=2, sort_keys=True))
        return 0
    if args.command == "generate":
        return generate(args.worker_index, args.num_workers)
    report = audit()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["full_replay_authorized_by_probe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
