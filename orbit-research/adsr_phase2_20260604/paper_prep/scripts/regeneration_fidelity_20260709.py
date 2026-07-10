#!/usr/bin/env python3
"""Build, run, and score the T2 ACE-Step regeneration-fidelity audit."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import socket
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np


DEMUCS_THRESHOLD = 0.1791
CONTROL_COUNT = 50
CONTROL_SELECTION_SEED = 20260709
PATH_PATTERN = re.compile(r"candidate_(\d+)_seed(\d+)\.(?:wav|flac)$")
RARE_PATTERN = re.compile(r"_s(\d+)_(\d+)\.flac$")


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PHASE = ROOT / "orbit-research/adsr_phase2_20260604"
PAPER = PHASE / "paper_prep"
A_DIR = PAPER / "validation_A_prime"
OUT_DIR = A_DIR / "regeneration_fidelity_20260709"
CONTROL_MANIFEST = OUT_DIR / "REGENERATION_CONTROL_MANIFEST.csv"
RELABEL_MANIFEST = OUT_DIR / "REGENERATION_RELABEL_MANIFEST.csv"
GENERATION_LEDGER = OUT_DIR / "CONTROL_GENERATION_LEDGER.jsonl"
CONTROL_RESULTS = A_DIR / "REGENERATION_FIDELITY_CONTROLS.csv"
RELABEL_RESULTS = OUT_DIR / "REGENERATION_RELABEL_RESULTS.csv"
REPORT = A_DIR / "REGENERATION_FIDELITY_REPORT.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_candidate_path(value: str) -> tuple[int, int]:
    for path_text in value.split("|"):
        match = PATH_PATTERN.search(path_text)
        if match:
            return int(match.group(1)), int(match.group(2))
    raise ValueError(f"cannot parse candidate index/seed from {value!r}")


def select_controls(rows: list[dict[str, str]], n: int = CONTROL_COUNT) -> list[dict[str, str]]:
    eligible = [
        row
        for row in rows
        if row.get("analysis_role") == "primary" and row.get("media_class") == "original"
    ]
    if len(eligible) < n:
        raise ValueError(f"need {n} original primary controls, found {len(eligible)}")
    rng = random.Random(CONTROL_SELECTION_SEED)
    positive = [row for row in eligible if row.get("demucs_label_0p1791") == "1"]
    negative = [row for row in eligible if row.get("demucs_label_0p1791") == "0"]
    rng.shuffle(positive)
    rng.shuffle(negative)
    # Keep every rare positive-side case; fill the rest from the much larger
    # negative-side stratum. This avoids silently dropping the smaller direction.
    selected = positive[:n]
    selected.extend(negative[: n - len(selected)])
    if len(selected) != n:
        raise ValueError(f"control selection produced {len(selected)} rows, expected {n}")
    return sorted(selected, key=lambda row: row["case_id"])


def atlas_ratio_index(ledger_dir: Path) -> dict[tuple[str, int], dict]:
    index: dict[tuple[str, int], dict] = {}
    for path in sorted(ledger_dir.glob("bon256_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("error") or row.get("condition") != "none":
                continue
            key = (str(row["prompt_id"]), int(row["seed"]))
            if key in index:
                previous = index[key]
                if float(previous["vocal_energy_ratio"]) != float(row["vocal_energy_ratio"]):
                    raise ValueError(f"conflicting atlas ratio for {key}")
                continue
            index[key] = {**row, "_ledger_path": str(path.relative_to(ROOT))}
    return index


def build_manifests() -> dict[str, int]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reconciliation = read_csv(A_DIR / "A_PRIME_CARDINALITY_RECONCILIATION.csv")
    controls = select_controls(reconciliation)
    control_rows: list[dict[str, object]] = []
    for index, row in enumerate(controls, start=1):
        candidate_index, seed = parse_candidate_path(row["original_packet_paths"])
        original = ROOT / row["package_media_path"]
        if not original.is_file():
            raise FileNotFoundError(original)
        replay = OUT_DIR / "audio/controls" / f"control_{index:03d}_{row['case_id']}_seed{seed}.wav"
        control_rows.append(
            {
                "control_id": f"regen_control_{index:03d}",
                "case_id": row["case_id"],
                "prompt_id": row["prompt_id"],
                "candidate_index": candidate_index,
                "source_seed": seed,
                "seed_policy": "exact_historical_source_seed_replay",
                "original_path": str(original.relative_to(ROOT)),
                "original_sha256": sha256_file(original),
                "replay_path": str(replay.relative_to(ROOT)),
                "recorded_demucs_ratio": row["demucs_ratio"],
                "recorded_demucs_label": row["demucs_label_0p1791"],
                "cfg_scale": 5.0,
                "steps": 30,
                "cfg_type": "cfg",
                "guidance_interval": 0.5,
                "dtype": "bfloat16",
                "selection_seed": CONTROL_SELECTION_SEED,
            }
        )
    write_csv(CONTROL_MANIFEST, control_rows)

    raw_index = {
        (str(row["prompt_id"]), int(row["candidate_index"])): row
        for row in read_jsonl(PHASE / "vocal_presence_raw.jsonl")
        if row.get("ok")
    }
    relabel_rows: list[dict[str, object]] = []
    recovered = read_csv(A_DIR / "recovered_media_20260708/A_PRIME_RECOVERED_MEDIA_MANIFEST.csv")
    for row in recovered:
        if row.get("status") != "PASS":
            raise ValueError(f"non-PASS recovered A-prime row: {row['clip_id']}")
        key = (row["prompt_id"], int(row["candidate_index"]))
        prior = raw_index.get(key)
        if prior is None:
            raise ValueError(f"missing original Demucs record for regenerated A-prime row {key}")
        audio = ROOT / row["recovered_path"]
        if not audio.is_file():
            raise FileNotFoundError(audio)
        relabel_rows.append(
            {
                "cohort": "a_prime_regenerated_100",
                "clip_id": row["clip_id"],
                "prompt_id": row["prompt_id"],
                "candidate_index": row["candidate_index"],
                "seed": row["candidate_seed"],
                "audio_path": row["recovered_path"],
                "prior_ratio": prior["vocal_energy_ratio"],
                "prior_near_silent": str(bool(prior.get("near_silent"))).lower(),
                "prior_label": int(
                    float(prior["vocal_energy_ratio"]) >= DEMUCS_THRESHOLD
                    and not bool(prior.get("near_silent"))
                ),
                "prior_ledger": "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl",
                "seed_idx": "",
            }
        )

    a_manifest = {row["clip_id"]: row for row in read_csv(A_DIR / "A_PRIME_MANIFEST.csv")}
    rare_rows = [
        row
        for row in read_csv(PAPER / "storage_triage/RARE_CLEAN_PROTECTED/manifest.csv")
        if row.get("source_family") == "regenerated_from_frozen_seed"
    ]
    if len(rare_rows) != 26:
        raise ValueError(f"expected 26 regenerated rare-clean rows, found {len(rare_rows)}")
    atlas = atlas_ratio_index(
        ROOT / "batch3/exploratory_auto/20260620_regime_atlas_autopilot_v3/01_core_basin_test/ledgers"
    )
    for row in rare_rows:
        match = RARE_PATTERN.search(row["source_path"])
        if not match:
            raise ValueError(f"cannot parse rare-clean seed from {row['source_path']}")
        seed_idx, seed = int(match.group(1)), int(match.group(2))
        key = (row["prompt_id"], seed)
        prior = atlas.get(key)
        if prior is None:
            raise ValueError(f"missing atlas prior for regenerated rare-clean row {key}")
        manifest = a_manifest.get(row["sample_id"])
        if manifest is None:
            raise ValueError(f"missing A-prime path for rare-clean row {row['sample_id']}")
        audio = ROOT / manifest["clip_path"]
        if not audio.is_file():
            raise FileNotFoundError(audio)
        relabel_rows.append(
            {
                "cohort": "rare_clean_regenerated_26",
                "clip_id": row["sample_id"],
                "prompt_id": row["prompt_id"],
                "candidate_index": "",
                "seed": seed,
                "audio_path": manifest["clip_path"],
                "prior_ratio": prior["vocal_energy_ratio"],
                "prior_near_silent": str(bool(prior.get("near_silent"))).lower(),
                "prior_label": int(
                    float(prior["vocal_energy_ratio"]) >= DEMUCS_THRESHOLD
                    and not bool(prior.get("near_silent"))
                ),
                "prior_ledger": prior["_ledger_path"],
                "seed_idx": seed_idx,
            }
        )
    write_csv(RELABEL_MANIFEST, relabel_rows)
    return {"controls": len(control_rows), "relabel_rows": len(relabel_rows)}


def prompt_index() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in (ROOT / "configs/prompts/dev.jsonl", ROOT / "configs/prompts/held_out.jsonl"):
        for row in read_jsonl(path):
            if row["prompt_id"] in result:
                raise ValueError(f"duplicate prompt id {row['prompt_id']}")
            result[row["prompt_id"]] = row
    return result


def shard_rows(rows: list[dict], shard_index: int, num_shards: int) -> list[dict]:
    if num_shards <= 0:
        raise ValueError("num_shards must be positive")
    if shard_index < 0 or shard_index >= num_shards:
        raise ValueError(f"shard_index must be in [0, {num_shards - 1}]")
    return [row for index, row in enumerate(rows) if index % num_shards == shard_index]


def generate_controls(
    device: str,
    force: bool,
    shard_index: int = 0,
    num_shards: int = 1,
) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row
    import torch
    import torchaudio

    prompts = prompt_index()
    model = AceStepModel(device=device, dtype="bfloat16")
    generated = 0
    controls = read_csv(CONTROL_MANIFEST)
    selected = shard_rows(controls, shard_index, num_shards)
    for row in selected:
        output = ROOT / row["replay_path"]
        if output.exists() and not force:
            continue
        prompt_row = prompts.get(row["prompt_id"])
        if prompt_row is None:
            raise ValueError(f"missing prompt {row['prompt_id']}")
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.time()
        status = "FAIL"
        error = ""
        try:
            seed = int(row["source_seed"])
            seed_everything(seed)
            result = model.sample(
                _prompt_from_row(prompt_row),
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
            save_audio(output, result.waveform, result.sample_rate)
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError("generation produced no audio")
            status = "PASS"
            generated += 1
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        ledger_row = {
            "ts": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "control_id": row["control_id"],
            "prompt_id": row["prompt_id"],
            "source_seed": int(row["source_seed"]),
            "output": row["replay_path"],
            "device": device,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "shard_index": shard_index,
            "num_shards": num_shards,
            "python_version": sys.version.split()[0],
            "torch_version": torch.__version__,
            "torchaudio_version": torchaudio.__version__,
            "torch_cuda_build": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
            "transformers_version": __import__("transformers").__version__,
            "diffusers_version": __import__("diffusers").__version__,
            "status": status,
            "error": error,
            "elapsed_s": round(time.time() - started, 6),
        }
        append_jsonl(GENERATION_LEDGER, ledger_row)
        print(json.dumps(ledger_row, sort_keys=True), flush=True)
        if status != "PASS":
            return 1
    return 0 if generated or all((ROOT / row["replay_path"]).is_file() for row in selected) else 1


def load_audio(path: Path):
    import soundfile as sf
    import torch

    data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    return torch.from_numpy(data.T.copy()), int(sample_rate)


def rms_dbfs(waveform) -> float:
    value = float((waveform.to(dtype=waveform.dtype).square().mean()).sqrt())
    return 20.0 * math.log10(max(value, 1e-12))


def decoded_waveform_sha256(waveform, sample_rate: int) -> str:
    """Hash canonical decoded float32 samples plus their audio dimensions."""
    if hasattr(waveform, "detach"):
        waveform = waveform.detach().cpu().numpy()
    samples = np.ascontiguousarray(np.asarray(waveform, dtype="<f4"))
    header = np.asarray((sample_rate, *samples.shape), dtype="<i8")
    digest = hashlib.sha256()
    digest.update(header.tobytes())
    digest.update(samples.tobytes())
    return digest.hexdigest()


def stable_scoring_seed(identity: str) -> int:
    return int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:4], "big")


def seed_scoring_rng(seed: int) -> None:
    """Seed every RNG used by Demucs shift and CLAP crop preprocessing."""
    import torch

    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def aligned_waveform_error(
    original: np.ndarray,
    replay: np.ndarray,
    sample_rate: int,
    max_lag_seconds: float = 1.0,
) -> tuple[int, float]:
    """Return replay lag in samples and RMS error normalized by original RMS."""
    original = np.asarray(original, dtype=np.float64).reshape(-1)
    replay = np.asarray(replay, dtype=np.float64).reshape(-1)
    stride = max(1, sample_rate // 2000)
    left = original[::stride]
    right = replay[::stride]
    full_size = len(right) + len(left) - 1
    fft_size = 1 << (full_size - 1).bit_length()
    circular = np.fft.irfft(
        np.fft.rfft(right, fft_size) * np.conj(np.fft.rfft(left, fft_size)),
        fft_size,
    )
    corr = np.concatenate((circular[-(len(left) - 1) :], circular[: len(right)]))
    lags = np.arange(-(len(left) - 1), len(right))
    limit = max(1, int(max_lag_seconds * sample_rate / stride))
    keep = np.abs(lags) <= limit
    lag = int(lags[keep][int(np.argmax(corr[keep]))]) * stride
    if lag >= 0:
        aligned_original = original[: max(0, min(len(original), len(replay) - lag))]
        aligned_replay = replay[lag : lag + len(aligned_original)]
    else:
        offset = -lag
        aligned_replay = replay[: max(0, min(len(replay), len(original) - offset))]
        aligned_original = original[offset : offset + len(aligned_replay)]
    if not len(aligned_original):
        return lag, math.inf
    rmse = float(np.sqrt(np.mean((aligned_original - aligned_replay) ** 2)))
    reference = float(np.sqrt(np.mean(aligned_original**2)))
    return lag, rmse / max(reference, 1e-12)


def unique_successful_generation_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not GENERATION_LEDGER.exists():
        return rows
    for row in read_jsonl(GENERATION_LEDGER):
        if row.get("status") == "PASS":
            rows[str(row["control_id"])] = row
    return rows


def _clap_embedding(reward, waveform, sample_rate: int):
    import torch
    import torchaudio

    reward._ensure_loaded()  # Reuse the project's pinned model-loading contract.
    # CLAP_Module does not reliably put the inner torch module into evaluation
    # mode. Without this, dropout makes embeddings of identical audio differ.
    reward._model.model.eval()
    if sample_rate != 48_000:
        waveform = torchaudio.functional.resample(waveform, sample_rate, 48_000)
    if waveform.dim() == 2:
        waveform = waveform.mean(dim=0, keepdim=True)
    with torch.no_grad():
        embedding = reward._model.get_audio_embedding_from_data(
            x=waveform.cpu().numpy(), use_tensor=False
        )
    tensor = torch.as_tensor(embedding, dtype=torch.float32).reshape(-1)
    return tensor / tensor.norm().clamp_min(1e-12)


def score_all(device: str) -> str:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    import torch
    from mprm.rewards.clap import ClapReward
    from scripts.batch3_online_harness import GateLabeler

    controls = read_csv(CONTROL_MANIFEST)
    relabel = read_csv(RELABEL_MANIFEST)
    successful = unique_successful_generation_rows()
    if set(successful) != {row["control_id"] for row in controls}:
        missing = sorted({row["control_id"] for row in controls} - set(successful))
        raise ValueError(f"missing successful generation ledger rows: {missing}")
    paths = {
        str(ROOT / row["original_path"]) for row in controls
    } | {
        str(ROOT / row["replay_path"]) for row in controls
    } | {
        str(ROOT / row["audio_path"]) for row in relabel
    }
    for path_text in paths:
        if not Path(path_text).is_file():
            raise FileNotFoundError(path_text)

    path_scoring_seeds: dict[str, int] = {}

    def register_seed(path_text: str, seed: int) -> None:
        previous = path_scoring_seeds.get(path_text)
        if previous is not None and previous != seed:
            raise ValueError(f"audio path assigned conflicting scoring seeds: {path_text}")
        path_scoring_seeds[path_text] = seed

    for row in controls:
        scoring_seed = stable_scoring_seed(f"control:{row['control_id']}")
        register_seed(str(ROOT / row["original_path"]), scoring_seed)
        register_seed(str(ROOT / row["replay_path"]), scoring_seed)
    for row in relabel:
        register_seed(
            str(ROOT / row["audio_path"]),
            stable_scoring_seed(f"relabel:{row['cohort']}:{row['clip_id']}"),
        )
    if set(path_scoring_seeds) != paths:
        raise ValueError("scoring seed registry does not exactly cover audio paths")

    gate = GateLabeler(device)
    demucs: dict[str, tuple[float, bool]] = {}
    for index, path_text in enumerate(sorted(paths), start=1):
        seed_scoring_rng(path_scoring_seeds[path_text])
        waveform, sample_rate = load_audio(Path(path_text))
        demucs[path_text] = gate.ratio(waveform, sample_rate)
        print(json.dumps({"stage": "demucs", "index": index, "total": len(paths), "path": path_text}), flush=True)
    del gate
    torch.cuda.empty_cache()

    clap = ClapReward(device=device)
    clap_embeddings: dict[str, object] = {}
    control_paths = sorted(
        {str(ROOT / row["original_path"]) for row in controls}
        | {str(ROOT / row["replay_path"]) for row in controls}
    )
    for index, path_text in enumerate(control_paths, start=1):
        seed_scoring_rng(path_scoring_seeds[path_text])
        waveform, sample_rate = load_audio(Path(path_text))
        clap_embeddings[path_text] = _clap_embedding(clap, waveform, sample_rate)
        print(json.dumps({"stage": "clap", "index": index, "total": len(control_paths), "path": path_text}), flush=True)

    control_results: list[dict[str, object]] = []
    for row in controls:
        original_path = ROOT / row["original_path"]
        replay_path = ROOT / row["replay_path"]
        original, original_sr = load_audio(original_path)
        replay_audio, replay_sr = load_audio(replay_path)
        if replay_sr != original_sr:
            import torchaudio

            replay_for_error = torchaudio.functional.resample(replay_audio, replay_sr, original_sr)
        else:
            replay_for_error = replay_audio
        lag, nrmse = aligned_waveform_error(
            original.mean(dim=0).numpy(), replay_for_error.mean(dim=0).numpy(), original_sr
        )
        original_ratio, original_near = demucs[str(original_path)]
        replay_ratio, replay_near = demucs[str(replay_path)]
        original_label = int(original_ratio >= DEMUCS_THRESHOLD and not original_near)
        replay_label = int(replay_ratio >= DEMUCS_THRESHOLD and not replay_near)
        cosine = float((clap_embeddings[str(original_path)] * clap_embeddings[str(replay_path)]).sum())
        original_file_sha = sha256_file(original_path)
        replay_file_sha = sha256_file(replay_path)
        original_waveform_sha = decoded_waveform_sha256(original, original_sr)
        replay_waveform_sha = decoded_waveform_sha256(replay_audio, replay_sr)
        exact = replay_waveform_sha == original_waveform_sha
        review_required = (not exact) or (original_label != replay_label) or cosine < 0.98
        control_results.append(
            {
                **row,
                "original_file_sha256": original_file_sha,
                "replay_file_sha256": replay_file_sha,
                "container_file_sha256_equal": str(replay_file_sha == original_file_sha).lower(),
                "original_waveform_sha256": original_waveform_sha,
                "replay_waveform_sha256": replay_waveform_sha,
                "waveform_sha256_equal": str(exact).lower(),
                "original_duration_s": original.shape[-1] / original_sr,
                "replay_duration_s": replay_audio.shape[-1] / replay_sr,
                "sample_rate_equal": str(original_sr == replay_sr).lower(),
                "duration_delta_s": replay_audio.shape[-1] / replay_sr - original.shape[-1] / original_sr,
                "aligned_lag_samples": lag,
                "aligned_waveform_nrmse": nrmse,
                "clap_audio_embedding_cosine": cosine,
                "original_demucs_ratio_rescored": original_ratio,
                "replay_demucs_ratio": replay_ratio,
                "abs_demucs_ratio_delta_vs_rescored": abs(replay_ratio - original_ratio),
                "recorded_demucs_ratio_delta": abs(replay_ratio - float(row["recorded_demucs_ratio"])),
                "original_demucs_label_rescored": original_label,
                "replay_demucs_label": replay_label,
                "demucs_label_flip": str(original_label != replay_label).lower(),
                "original_near_silent": str(original_near).lower(),
                "replay_near_silent": str(replay_near).lower(),
                "original_loudness_dbfs": rms_dbfs(original),
                "replay_loudness_dbfs": rms_dbfs(replay_audio),
                "manual_mismatch_flag": "UNRATED",
                "manual_review_required": str(review_required).lower(),
            }
        )
    write_csv(CONTROL_RESULTS, control_results)

    relabel_results: list[dict[str, object]] = []
    for row in relabel:
        path = ROOT / row["audio_path"]
        ratio, near_silent = demucs[str(path)]
        new_label = int(ratio >= DEMUCS_THRESHOLD and not near_silent)
        prior_ratio = float(row["prior_ratio"])
        prior_label = int(row["prior_label"])
        relabel_results.append(
            {
                **row,
                "canonical_model": "htdemucs",
                "canonical_split": "true",
                "canonical_overlap": 0.1,
                "canonical_near_silent_rms": "<1e-3",
                "canonical_threshold": DEMUCS_THRESHOLD,
                "relabel_ratio": ratio,
                "abs_ratio_delta": abs(ratio - prior_ratio),
                "relabel_near_silent": str(near_silent).lower(),
                "relabel_label": new_label,
                "label_flip": str(new_label != prior_label).lower(),
            }
        )
    write_csv(RELABEL_RESULTS, relabel_results)
    return write_report(control_results, relabel_results)


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return float(np.mean(values)) if values else math.nan


def write_report(controls: list[dict[str, object]], relabel: list[dict[str, object]]) -> str:
    exact_count = sum(row["waveform_sha256_equal"] == "true" for row in controls)
    control_flips = sum(row["demucs_label_flip"] == "true" for row in controls)
    by_cohort = Counter(str(row["cohort"]) for row in relabel)
    flips_by_cohort = Counter(
        str(row["cohort"]) for row in relabel if row["label_flip"] == "true"
    )
    if len(controls) != 50 or by_cohort != Counter(
        {"a_prime_regenerated_100": 100, "rare_clean_regenerated_26": 26}
    ):
        raise ValueError(f"unexpected T2 shapes: controls={len(controls)}, cohorts={by_cohort}")
    all_label_stable = control_flips == 0 and sum(flips_by_cohort.values()) == 0
    if exact_count == len(controls):
        status = "EXACT"
    elif all_label_stable:
        status = "LABEL_STABLE_ONLY"
    else:
        status = "NOT_REPRODUCIBLE"
    clap_values = [float(row["clap_audio_embedding_cosine"]) for row in controls]
    nrmse_values = [float(row["aligned_waveform_nrmse"]) for row in controls]
    delta_values = [float(row["abs_demucs_ratio_delta_vs_rescored"]) for row in controls]
    relabel_deltas = {
        cohort: [float(row["abs_ratio_delta"]) for row in relabel if row["cohort"] == cohort]
        for cohort in by_cohort
    }
    report = f"""# Regeneration Fidelity Report

`REGENERATION_FIDELITY_STATUS = {status}`

## Protocol

- 50 controls were selected from the reconstructed 112-case primary A-prime
  universe; every source is original media.
- Historical candidate seeds were replayed in an isolated output directory.
- Generation settings match the frozen recollection summaries: ACE-Step v1,
  30 steps, CFG 5.0, `cfg_type=cfg`, guidance interval 0.5, bf16.
- Canonical relabeling uses `htdemucs`, `apply_model(..., shifts=1,
  split=True, overlap=0.1)`, `near_silent = rms < 1e-3`, and threshold
  0.1791. Original/replay pairs share a stable scoring seed so Demucs shift
  and CLAP crop randomness cannot masquerade as generation drift.
- CLAP comparison is audio-embedding cosine between the original and replay,
  using the project-pinned `630k-audioset-best` checkpoint.

## Control Results

| Measure | Result |
|---|---:|
| Controls completed | {len(controls)}/50 |
| Exact decoded-waveform SHA256 | {exact_count}/50 |
| Exact container-file SHA256 | {sum(row['container_file_sha256_equal'] == 'true' for row in controls)}/50 |
| Same sample rate | {sum(row['sample_rate_equal'] == 'true' for row in controls)}/50 |
| Demucs label flips | {control_flips}/50 |
| Mean absolute rescored Demucs-ratio delta | {_mean(delta_values):.6f} |
| Mean aligned waveform NRMSE | {_mean(nrmse_values):.6f} |
| Mean CLAP audio cosine | {_mean(clap_values):.6f} |
| Minimum CLAP audio cosine | {min(clap_values):.6f} |
| Manual mismatch flags completed | 0/50 (`UNRATED`; review queue is explicit in the CSV) |

## Regenerated-Cohort Relabeling

| Cohort | Rows | Label flips | Mean absolute ratio delta | Maximum absolute ratio delta |
|---|---:|---:|---:|---:|
| A-prime regenerated media | {by_cohort['a_prime_regenerated_100']} | {flips_by_cohort['a_prime_regenerated_100']} | {_mean(relabel_deltas['a_prime_regenerated_100']):.6f} | {max(relabel_deltas['a_prime_regenerated_100']):.6f} |
| Rare-clean regenerated media | {by_cohort['rare_clean_regenerated_26']} | {flips_by_cohort['rare_clean_regenerated_26']} | {_mean(relabel_deltas['rare_clean_regenerated_26']):.6f} | {max(relabel_deltas['rare_clean_regenerated_26']):.6f} |

## Interpretation

`{status}` is mechanical: `EXACT` requires all 50 waveform hashes to match;
`LABEL_STABLE_ONLY` requires zero canonical-label flips across controls and both
regenerated cohorts when hashes are not exact; otherwise the result is
`NOT_REPRODUCIBLE`.

Regenerated rows remain sensitivity-only unless this report is `EXACT` or
`LABEL_STABLE_ONLY` and dual-PI approval explicitly admits them. T1 separately
restored all 112 primary disagreement clips as originals, so the primary A-prime
gate does not depend on regenerated media.

## Artifacts

- `paper_prep/validation_A_prime/REGENERATION_FIDELITY_CONTROLS.csv`
- `paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_CONTROL_MANIFEST.csv`
- `paper_prep/validation_A_prime/regeneration_fidelity_20260709/CONTROL_GENERATION_LEDGER.jsonl`
- `paper_prep/validation_A_prime/regeneration_fidelity_20260709/REGENERATION_RELABEL_RESULTS.csv`
- `paper_prep/SEED_REGISTRY.md`
"""
    REPORT.write_text(report, encoding="utf-8")
    if status == "NOT_REPRODUCIBLE":
        escalation = PAPER / "execution_20260709/ESCALATION_T2.md"
        escalation.write_text(
            "# Escalation T2: Regeneration Not Reproducible\n\n"
            "The mechanical regeneration-fidelity status is `NOT_REPRODUCIBLE`.\n\n"
            f"- Control label flips: {control_flips}/50\n"
            f"- A-prime regenerated label flips: {flips_by_cohort['a_prime_regenerated_100']}/100\n"
            f"- Rare-clean regenerated label flips: {flips_by_cohort['rare_clean_regenerated_26']}/26\n\n"
            "Regenerated rows are sensitivity-only. The reconstructed 112-case primary gate uses originals.\n",
            encoding="utf-8",
        )
    elif (PAPER / "execution_20260709/ESCALATION_T2.md").exists():
        (PAPER / "execution_20260709/ESCALATION_T2.md").write_text(
            "# Escalation T2: Resolved Audit Defect\n\n"
            f"Final `REGENERATION_FIDELITY_STATUS = {status}`.\n\n"
            "The earlier NOT_REPRODUCIBLE result compared WAV container hashes and\n"
            "used independent random Demucs shifts/CLAP crops for identical audio.\n"
            "That invalid report is retained under\n"
            "`regeneration_fidelity_20260709/invalid_pre_waveform_hash_fix/`.\n",
            encoding="utf-8",
        )
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build-manifests")
    generate = subparsers.add_parser("generate-controls")
    generate.add_argument("--device", default="cuda")
    generate.add_argument("--force", action="store_true")
    generate.add_argument("--shard-index", type=int, default=0)
    generate.add_argument("--num-shards", type=int, default=1)
    score = subparsers.add_parser("score")
    score.add_argument("--device", default="cuda")
    args = parser.parse_args()
    if args.command == "build-manifests":
        print(json.dumps(build_manifests(), indent=2, sort_keys=True))
        return 0
    if args.command == "generate-controls":
        return generate_controls(
            args.device,
            args.force,
            shard_index=args.shard_index,
            num_shards=args.num_shards,
        )
    status = score_all(args.device)
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
