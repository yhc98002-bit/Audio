#!/usr/bin/env python3
"""Reconstruct, score, and exact-audit the 4,096-candidate ACE-Step v1 spine."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import socket
import subprocess
import sys
import time
from collections import Counter
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
sys.path.insert(0, str(ROOT / "paper_prep/w2_contingency_20260711"))
from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

PAPER = ROOT / "paper_prep"
OUT = PAPER / "w2_execution_20260712/spine_reconstruction"
MANIFEST = OUT / "SPINE_RECONSTRUCTION_MANIFEST.csv"
PROMPT_SNAPSHOT = OUT / "SPINE_PROMPT_SNAPSHOT.jsonl"
GENERATION_DIR = OUT / "generation_ledgers"
SCORING_DIR = OUT / "scoring_ledgers"
AUDIO_DIR = OUT / "audio"
SURVIVOR_REPLAY_DIR = OUT / "survivor_audit_replay"
AUDIT_JSON = OUT / "SPINE_RECONSTRUCTION_AUDIT.json"
AUDIT_MD = OUT / "SPINE_RECONSTRUCTION_AUDIT.md"
SPINE = ROOT / "orbit-research/trajectory_candidate_dataset.jsonl"
RETAINED = PAPER / "w2_contingency_20260711/W2_RETAINED_AUDIO_MANIFEST.jsonl"
RAW_OLD = ROOT / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
CONTROLS = PAPER / "validation_A_prime/regeneration_fidelity_20260709/REGENERATION_CONTROL_MANIFEST.csv"
MODEL_PATH = Path(
    os.environ.get(
        "MPRM_ACE_STEP_MODEL_PATH",
        Path.home() / ".cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B",
    )
)
OLD_THRESHOLD = VOCAL_PRESENCE_THRESHOLD
CANDIDATE_DEMUCS_THRESHOLD = 0.038639528676867485
CANDIDATE_PANNS_THRESHOLD = 0.03181814216077328
EXPECTED_ROWS = 4096
EXPECTED_MISSING = 4095
EXPECTED_SURVIVORS = 1


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_hash(row: dict) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def decoded_audio_hash(samples: np.ndarray, sample_rate: int) -> str:
    canonical = np.ascontiguousarray(samples.T, dtype="<f4")
    header = np.asarray((sample_rate, *canonical.shape), dtype="<i8")
    digest = hashlib.sha256(header.tobytes())
    digest.update(canonical.tobytes())
    return digest.hexdigest()


def _git_sha(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:  # noqa: BLE001
        return "NOT_A_GIT_CHECKOUT"


def prompt_index() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in (ROOT / "configs/prompts/dev.jsonl", ROOT / "configs/prompts/held_out.jsonl"):
        for row in read_jsonl(path):
            if row["prompt_id"] in result:
                raise ValueError(f"duplicate prompt id {row['prompt_id']}")
            result[row["prompt_id"]] = {**row, "_source_path": str(path.relative_to(ROOT))}
    return result


def build_manifest() -> dict:
    spine = read_jsonl(SPINE)
    if len(spine) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} spine rows, found {len(spine)}")
    keys = [(row["prompt_id"], int(row["candidate_index"])) for row in spine]
    if len(set(keys)) != EXPECTED_ROWS:
        raise ValueError("spine prompt/candidate keys are not unique")

    retained_rows = [row for row in read_jsonl(RETAINED) if row["cohort"] == "candidate_spine_4096"]
    retained = {row["record_id"]: row for row in retained_rows}
    survivors = [row for row in retained_rows if row.get("media_available")]
    if len(survivors) != EXPECTED_SURVIVORS:
        raise ValueError(f"expected one surviving original, found {len(survivors)}")

    old_rows = {
        (str(row["prompt_id"]), int(row["candidate_index"])): row
        for row in read_jsonl(RAW_OLD)
        if row.get("ok")
    }
    if len(old_rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} historical detector rows, found {len(old_rows)}")
    prompts = prompt_index()
    used_prompt_ids = sorted({row["prompt_id"] for row in spine})
    snapshot = []
    for prompt_id in used_prompt_ids:
        prompt = prompts.get(prompt_id)
        if prompt is None:
            raise ValueError(f"missing canonical prompt {prompt_id}")
        source = prompt.pop("_source_path")
        snapshot.append(
            {
                **prompt,
                "canonical_source_path": source,
                "serialized_sha256": canonical_json_hash(prompt),
            }
        )
        prompt["_source_path"] = source
    write_jsonl(PROMPT_SNAPSHOT, snapshot)
    snapshot_index = {row["prompt_id"]: row for row in snapshot}

    rows = []
    missing = 0
    survivor_count = 0
    for source_row, row in enumerate(spine, start=1):
        record_id = hashlib.sha256(
            f"candidate_spine_4096|{row['candidate_uid']}".encode()
        ).hexdigest()[:24]
        retained_row = retained.get(record_id)
        if retained_row is None:
            raise ValueError(f"retained inventory identity mismatch at source row {source_row}")
        source_audio = Path(str(retained_row.get("audio_path", "")))
        source_exists = bool(retained_row.get("media_available")) and source_audio.is_file()
        candidate_index = int(row["candidate_index"])
        seed = int(row["candidate_seed"])
        if source_exists:
            survivor_count += 1
            target = source_audio
            replay = SURVIVOR_REPLAY_DIR / row["prompt_id"] / (
                f"candidate_{candidate_index:02d}_seed{seed}.wav"
            )
            generation_role = "surviving_original_audit_replay"
        else:
            missing += 1
            target = AUDIO_DIR / row["prompt_id"] / f"candidate_{candidate_index:02d}_seed{seed}.wav"
            replay = target
            generation_role = "missing_spine_reconstruction"
        prior = old_rows[(row["prompt_id"], candidate_index)]
        prompt = snapshot_index[row["prompt_id"]]
        rows.append(
            {
                "task_id": str(row["candidate_uid"]),
                "source_spine_row": source_row,
                "record_id": record_id,
                "prompt_id": row["prompt_id"],
                "prompt_source": row["prompt_source"],
                "prompt_serialized_sha256": prompt["serialized_sha256"],
                "candidate_index": candidate_index,
                "candidate_seed": seed,
                "candidate_uid": row["candidate_uid"],
                "vocal_stratum": row["vocal_stratum"],
                "requested_vocal": int(row["vocal_stratum"] == "vocal"),
                "generation_role": generation_role,
                "source_audio_path": str(source_audio) if source_exists else "",
                "target_audio_path": str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target),
                "generation_output_path": str(replay.relative_to(ROOT)),
                "historical_old_ratio": prior["vocal_energy_ratio"],
                "historical_old_near_silent": str(bool(prior.get("near_silent"))).lower(),
                "historical_old_present_0p1791": int(
                    float(prior["vocal_energy_ratio"]) >= OLD_THRESHOLD
                    and not bool(prior.get("near_silent"))
                ),
                "historical_old_ledger": str(RAW_OLD.relative_to(ROOT)),
                "cfg_scale": 5.0,
                "steps": 30,
                "cfg_type": "cfg",
                "guidance_interval": 0.5,
                "dtype": "bfloat16",
            }
        )
    if missing != EXPECTED_MISSING or survivor_count != EXPECTED_SURVIVORS:
        raise AssertionError(f"unexpected reconstruction split: missing={missing}, survivor={survivor_count}")
    write_csv(MANIFEST, rows)
    return {
        "manifest_rows": len(rows),
        "missing_reconstruction_rows": missing,
        "surviving_original_audit_replays": survivor_count,
        "prompt_snapshot_rows": len(snapshot),
        "unique_identity_keys": len(set(keys)),
    }


def _latest_success(directory: Path, pattern: str, key: str) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for path in sorted(directory.glob(pattern)):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                latest[str(row[key])] = row
    return latest


def generate(worker_index: int, num_workers: int, limit: int) -> int:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("exactly one CUDA_VISIBLE_DEVICES entry is required")

    import soundfile as sf
    import torch

    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row

    tasks = read_csv(MANIFEST)
    mine = tasks[worker_index::num_workers]
    if limit:
        mine = mine[:limit]
    done = _latest_success(GENERATION_DIR, "generation_w*.jsonl", "task_id")
    prompts = {row["prompt_id"]: row for row in read_jsonl(PROMPT_SNAPSHOT)}
    ledger = GENERATION_DIR / f"generation_w{worker_index}.jsonl"
    model = AceStepModel(device="cuda", dtype="bfloat16")
    upstream = ROOT.parent.parent.parent / "source/ACE-Step"
    identity = {
        "repository_git_sha": _git_sha(ROOT),
        "upstream_ace_step_git_sha": _git_sha(upstream),
        "model_path": str(MODEL_PATH),
        "model_path_exists": MODEL_PATH.is_dir(),
        "python_version": sys.version.split()[0],
        "torch_version": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
        "gpu_name": torch.cuda.get_device_name(0),
    }
    written = 0
    for task in mine:
        if task["task_id"] in done:
            continue
        started = time.time()
        output = ROOT / task["generation_output_path"]
        record = {
            **task,
            **identity,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
            "status": "FAIL",
            "error": "",
        }
        try:
            prompt_row = prompts[task["prompt_id"]]
            prompt_payload = {
                key: value
                for key, value in prompt_row.items()
                if key not in {"canonical_source_path", "serialized_sha256"}
            }
            if canonical_json_hash(prompt_payload) != task["prompt_serialized_sha256"]:
                raise RuntimeError("prompt serialization hash mismatch")
            seed = int(task["candidate_seed"])
            seed_everything(seed)
            result = model.sample(
                _prompt_from_row(prompt_payload),
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
                raise RuntimeError(f"invalid output duration={duration:.6f}, rms={rms:.8g}")
            record.update(
                {
                    "status": "PASS",
                    "sample_rate": int(sample_rate),
                    "duration_s": round(duration, 6),
                    "rms": rms,
                    "near_silent": bool(20 * math.log10(max(rms, 1e-12)) < -60),
                    "waveform_sha256": sha256_file(output),
                    "decoded_audio_sha256": decoded_audio_hash(samples, sample_rate),
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_s"] = round(time.time() - started, 6)
        append_jsonl(ledger, record)
        print(json.dumps(record, sort_keys=True), flush=True)
        written += 1
        if record["status"] != "PASS":
            return 1
    return 0 if written or all(task["task_id"] in done for task in mine) else 1


def _seed_scoring(identity: str) -> None:
    import torch

    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:4], "big")
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def score(worker_index: int, num_workers: int, limit: int) -> int:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("exactly one CUDA_VISIBLE_DEVICES entry is required")
    from w2_instruments import CurrentDemucsInstrument, LivePannsInstrument

    tasks = read_csv(MANIFEST)
    mine = tasks[worker_index::num_workers]
    if limit:
        mine = mine[:limit]
    done = _latest_success(SCORING_DIR, "scoring_w*.jsonl", "task_id")
    demucs = CurrentDemucsInstrument(device="cuda", threshold=OLD_THRESHOLD)
    panns = LivePannsInstrument(device="cuda", threshold=CANDIDATE_PANNS_THRESHOLD)
    ledger = SCORING_DIR / f"scoring_w{worker_index}.jsonl"
    written = 0
    for task in mine:
        if task["task_id"] in done:
            continue
        started = time.time()
        path = ROOT / task["target_audio_path"] if not Path(task["target_audio_path"]).is_absolute() else Path(task["target_audio_path"])
        record = {
            "task_id": task["task_id"],
            "record_id": task["record_id"],
            "prompt_id": task["prompt_id"],
            "candidate_index": int(task["candidate_index"]),
            "candidate_seed": int(task["candidate_seed"]),
            "requested_vocal": int(task["requested_vocal"]),
            "target_audio_path": task["target_audio_path"],
            "historical_old_ratio": float(task["historical_old_ratio"]),
            "historical_old_present_0p1791": int(task["historical_old_present_0p1791"]),
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "status": "FAIL",
            "error": "",
        }
        try:
            if not path.is_file():
                raise FileNotFoundError(path)
            _seed_scoring(task["task_id"])
            old = demucs.score(path)
            _seed_scoring(task["task_id"] + "|panns")
            pann = panns.score(path)
            demucs_candidate = int(
                float(old["vocal_energy_ratio"]) >= CANDIDATE_DEMUCS_THRESHOLD
                and not bool(old["near_silent"])
            )
            panns_candidate = int(float(pann["panns_score"]) >= CANDIDATE_PANNS_THRESHOLD)
            candidate_present = int(demucs_candidate and panns_candidate)
            record.update(
                {
                    "status": "PASS",
                    "recomputed_demucs_score": float(old["vocal_energy_ratio"]),
                    "recomputed_old_present_0p1791": int(old["present"]),
                    "recomputed_near_silent": bool(old["near_silent"]),
                    "panns_score": float(pann["panns_score"]),
                    "panns_top_vocal_class": pann["panns_top_vocal_class"],
                    "candidate_demucs_threshold": CANDIDATE_DEMUCS_THRESHOLD,
                    "candidate_panns_threshold": CANDIDATE_PANNS_THRESHOLD,
                    "candidate_demucs_present": demucs_candidate,
                    "candidate_panns_present": panns_candidate,
                    "candidate_and_present": candidate_present,
                    "old_label_b_violation": int(int(old["present"]) != int(task["requested_vocal"])),
                    "candidate_label_b_violation": int(candidate_present != int(task["requested_vocal"])),
                    "instrument_status": "CANDIDATE_SENSITIVITY_ONLY_NOT_PROMOTED",
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_s"] = round(time.time() - started, 6)
        append_jsonl(ledger, record)
        print(json.dumps(record, sort_keys=True), flush=True)
        written += 1
        if record["status"] != "PASS":
            return 1
    return 0 if written or all(task["task_id"] in done for task in mine) else 1


def _decoded_from_path(path: Path) -> tuple[str, float, int]:
    import soundfile as sf

    samples, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    return decoded_audio_hash(samples, sample_rate), len(samples) / sample_rate, sample_rate


def audit() -> dict:
    tasks = read_csv(MANIFEST)
    generation = _latest_success(GENERATION_DIR, "generation_w*.jsonl", "task_id")
    scoring = _latest_success(SCORING_DIR, "scoring_w*.jsonl", "task_id")
    missing_generation = []
    invalid_media = []
    missing_scoring = []
    for task in tasks:
        generated = generation.get(task["task_id"])
        if not generated:
            missing_generation.append(task["task_id"])
            continue
        generated_path = ROOT / task["generation_output_path"]
        if not generated_path.is_file() or sha256_file(generated_path) != generated.get("waveform_sha256"):
            invalid_media.append(task["task_id"])
        if task["task_id"] not in scoring:
            missing_scoring.append(task["task_id"])

    survivor_rows = [row for row in tasks if row["generation_role"] == "surviving_original_audit_replay"]
    survivor_matches = []
    for task in survivor_rows:
        original = Path(task["source_audio_path"])
        replay = ROOT / task["generation_output_path"]
        original_hash, _, _ = _decoded_from_path(original)
        replay_hash, _, _ = _decoded_from_path(replay)
        survivor_matches.append(
            {
                "task_id": task["task_id"],
                "original_decoded_sha256": original_hash,
                "replay_decoded_sha256": replay_hash,
                "exact": original_hash == replay_hash,
            }
        )

    task_index = {(row["prompt_id"], int(row["candidate_index"])): row for row in tasks}
    control_matches = []
    for control in read_csv(CONTROLS):
        task = task_index[(control["prompt_id"], int(control["candidate_index"]))]
        reconstructed = ROOT / task["target_audio_path"]
        replay = ROOT / control["replay_path"]
        reconstructed_hash, _, _ = _decoded_from_path(reconstructed)
        control_hash, _, _ = _decoded_from_path(replay)
        control_matches.append(
            {
                "control_id": control["control_id"],
                "task_id": task["task_id"],
                "reconstructed_decoded_sha256": reconstructed_hash,
                "control_decoded_sha256": control_hash,
                "exact": reconstructed_hash == control_hash,
            }
        )

    generation_roles = Counter(row["generation_role"] for row in tasks)
    status = "PASS"
    if (
        len(tasks) != EXPECTED_ROWS
        or generation_roles["missing_spine_reconstruction"] != EXPECTED_MISSING
        or generation_roles["surviving_original_audit_replay"] != EXPECTED_SURVIVORS
        or missing_generation
        or invalid_media
        or missing_scoring
        or not all(row["exact"] for row in survivor_matches)
        or len(control_matches) != 50
        or not all(row["exact"] for row in control_matches)
    ):
        status = "FAIL"
    report = {
        "status": status,
        "spine_regen_status": (
            "COMPLETE_AUDIT_PASS" if status == "PASS" else "FAILED_ESCALATED"
        ),
        "manifest_rows": len(tasks),
        "generation_roles": dict(generation_roles),
        "successful_generation_rows": len(generation),
        "successful_scoring_rows": len(scoring),
        "missing_generation_count": len(missing_generation),
        "invalid_media_count": len(invalid_media),
        "missing_scoring_count": len(missing_scoring),
        "surviving_original_exact_matches": sum(row["exact"] for row in survivor_matches),
        "surviving_original_comparisons": len(survivor_matches),
        "control_exact_matches": sum(row["exact"] for row in control_matches),
        "control_comparisons": len(control_matches),
        "survivor_details": survivor_matches,
        "control_details": control_matches,
        "missing_generation_examples": missing_generation[:20],
        "invalid_media_examples": invalid_media[:20],
        "missing_scoring_examples": missing_scoring[:20],
        "instrument_scope": "candidate Demucs AND PANNs is sensitivity-only pending signed W2 promotion",
    }
    AUDIT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT_MD.write_text(
        "# W2 Spine Reconstruction Audit\n\n"
        f"`SPINE_REGEN_STATUS = {report['spine_regen_status']}`\n\n"
        f"`SPINE_REGEN_AUDIT = {status}`\n\n"
        f"- Manifest rows: {len(tasks)}\n"
        f"- Missing candidates reconstructed: {generation_roles['missing_spine_reconstruction']}\n"
        f"- Surviving-original audit replays: {generation_roles['surviving_original_audit_replay']}\n"
        f"- Successful generation rows: {len(generation)}\n"
        f"- Successful old/candidate instrument scoring rows: {len(scoring)}\n"
        f"- Missing generation rows: {len(missing_generation)}\n"
        f"- Invalid or checksum-mismatched media: {len(invalid_media)}\n"
        f"- Missing scoring rows: {len(missing_scoring)}\n"
        f"- Surviving originals exact by decoded hash: {sum(row['exact'] for row in survivor_matches)}/{len(survivor_matches)}\n"
        f"- Independent regeneration controls exact by decoded hash: {sum(row['exact'] for row in control_matches)}/{len(control_matches)}\n\n"
        "The Demucs-and-PANNs instrument is a candidate sensitivity instrument only. "
        "This audit does not promote it and does not change PLAN.md.\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-manifest")
    generate_parser = sub.add_parser("generate")
    generate_parser.add_argument("--worker-index", type=int, required=True)
    generate_parser.add_argument("--num-workers", type=int, required=True)
    generate_parser.add_argument("--limit", type=int, default=0)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("--worker-index", type=int, required=True)
    score_parser.add_argument("--num-workers", type=int, required=True)
    score_parser.add_argument("--limit", type=int, default=0)
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.command == "build-manifest":
        print(json.dumps(build_manifest(), indent=2, sort_keys=True))
        return 0
    if args.command == "generate":
        return generate(args.worker_index, args.num_workers, args.limit)
    if args.command == "score":
        return score(args.worker_index, args.num_workers, args.limit)
    if args.command == "audit":
        result = audit()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
