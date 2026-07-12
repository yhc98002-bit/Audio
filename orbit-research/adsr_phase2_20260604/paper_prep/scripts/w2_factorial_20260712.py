#!/usr/bin/env python3
"""Build, generate, audit, and stage the W2 instrumental factorial."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import socket
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

PAPER = ROOT / "paper_prep"
OUT = PAPER / "w2_execution_20260712/factorial"
PROMPTS = OUT / "FACTORIAL_PROMPTS.jsonl"
MANIFEST = OUT / "FACTORIAL_GENERATION_MANIFEST.csv"
LEDGER_DIR = OUT / "ledgers"
AUDIO_DIR = OUT / "audio"
AUDIT_JSON = OUT / "FACTORIAL_GENERATION_AUDIT.json"
AUDIT_MD = OUT / "FACTORIAL_GENERATION_AUDIT.md"
SPOT_MANIFEST = OUT / "FACTORIAL_PI_SPOTCHECK_MANIFEST.csv"
SEED_BASE = 2_034_000_000
N_PROMPTS = 32
N_SEEDS = 16
DURATION_SECONDS = 15.0
POSITIVE_TEXT = (
    "instrumental arrangement led by synthesizer, drums, bass, and melodic instruments"
)
NEGATIVE_TEXT = "pure instrumental, no vocals, no singing, no voice"
FORBIDDEN_POSITIVE_LEXEMES = {
    "vocal",
    "vocals",
    "voice",
    "voices",
    "sing",
    "singing",
    "singer",
    "choir",
    "chant",
    "speech",
    "spoken",
    "rap",
}
CONDITIONS = (
    "plain_baseline",
    "negative_text",
    "positive_text",
    "sampler_only",
    "negative_sampler",
    "positive_sampler",
)
BASE_EXTRAS = {
    "cfg_type": "apg",
    "guidance_interval": 0.5,
    "use_erg_tag": False,
    "use_erg_lyric": False,
    "use_erg_diffusion": False,
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decoded_hash(samples: np.ndarray, sample_rate: int) -> str:
    canonical = np.ascontiguousarray(samples.T, dtype="<f4")
    header = np.asarray((sample_rate, *canonical.shape), dtype="<i8")
    digest = hashlib.sha256(header.tobytes())
    digest.update(canonical.tobytes())
    return digest.hexdigest()


def condition_spec(condition: str) -> tuple[str | None, float]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    text = None
    if condition in {"negative_text", "negative_sampler"}:
        text = NEGATIVE_TEXT
    elif condition in {"positive_text", "positive_sampler"}:
        text = POSITIVE_TEXT
    cfg = 7.5 if condition in {"sampler_only", "negative_sampler", "positive_sampler"} else 5.0
    return text, cfg


def assert_positive_text_contract() -> None:
    tokens = set(POSITIVE_TEXT.lower().replace(",", " ").split())
    leaked = sorted(tokens & FORBIDDEN_POSITIVE_LEXEMES)
    if leaked:
        raise AssertionError(f"positive-only intervention contains forbidden vocal lexemes: {leaked}")


def build_manifest() -> dict:
    assert_positive_text_contract()
    prompt_rows = {
        row["prompt_id"]: row
        for row in read_jsonl(PAPER / "population_retry_20260707/population_retry_manifest_128.jsonl")
    }
    with (PAPER / "population_retry_20260707/full128_prompt_clean_rates.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rates = list(csv.DictReader(handle))
    ranked = sorted(
        (row for row in rates if row["vocal_stratum"] == "instrumental"),
        key=lambda row: (float(row["clean_rate"]), row["prompt_id"]),
    )
    if len(ranked) < N_PROMPTS:
        raise ValueError(f"need {N_PROMPTS} instrumental prompts, found {len(ranked)}")

    selected: list[dict] = []
    tasks: list[dict] = []
    seen_seeds: set[tuple[str, int]] = set()
    for prompt_rank, rate in enumerate(ranked[:N_PROMPTS]):
        prompt = prompt_rows.get(rate["prompt_id"])
        if prompt is None:
            raise ValueError(f"missing canonical N2 prompt {rate['prompt_id']}")
        if prompt.get("vocal_stratum") != "instrumental":
            raise ValueError(f"non-instrumental prompt selected: {prompt['prompt_id']}")
        selected.append(
            {
                **prompt,
                "factorial_prompt_rank": prompt_rank,
                "n2_clean_rate": float(rate["clean_rate"]),
                "n2_clean_count": int(rate["clean_count"]),
                "n2_rows": int(rate["rows"]),
                "selection_rule": "instrumental_ascending_n2_clean_rate_then_prompt_id",
            }
        )
        for condition_index, condition in enumerate(CONDITIONS):
            text_intervention, cfg_scale = condition_spec(condition)
            for seed_idx in range(N_SEEDS):
                seed = SEED_BASE + prompt_rank * 1000 + seed_idx
                seen_seeds.add((prompt["prompt_id"], seed))
                output = AUDIO_DIR / condition / prompt["prompt_id"] / (
                    f"{condition}_s{seed_idx:02d}_{seed}.flac"
                )
                tasks.append(
                    {
                        "task_id": f"w2fact_{prompt_rank:02d}_{condition_index}_{seed_idx:02d}",
                        "prompt_rank": prompt_rank,
                        "prompt_id": prompt["prompt_id"],
                        "condition_index": condition_index,
                        "condition": condition,
                        "seed_idx": seed_idx,
                        "seed": seed,
                        "cfg_scale": cfg_scale,
                        "text_intervention": text_intervention or "",
                        "duration_seconds": DURATION_SECONDS,
                        "output_path": str(output.relative_to(ROOT)),
                    }
                )
    if len(selected) != N_PROMPTS or len(tasks) != N_PROMPTS * len(CONDITIONS) * N_SEEDS:
        raise AssertionError("factorial cardinality mismatch")
    if len(seen_seeds) != N_PROMPTS * N_SEEDS:
        raise AssertionError("CRN seed cardinality mismatch")
    if min(int(row["seed"]) for row in tasks) != SEED_BASE:
        raise AssertionError("unexpected minimum seed")
    if max(int(row["seed"]) for row in tasks) > 2_034_031_015:
        raise AssertionError("factorial seed exceeded registered range")
    write_jsonl(PROMPTS, selected)
    write_csv(MANIFEST, tasks)
    return {
        "prompts": len(selected),
        "tasks": len(tasks),
        "unique_prompt_seed_pairs": len(seen_seeds),
        "conditions": list(CONDITIONS),
        "min_seed": min(int(row["seed"]) for row in tasks),
        "max_seed": max(int(row["seed"]) for row in tasks),
    }


def _done_keys() -> set[str]:
    done: set[str] = set()
    for path in sorted(LEDGER_DIR.glob("factorial_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                done.add(str(row["task_id"]))
    return done


def generate(worker_index: int, num_workers: int, limit: int) -> int:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    if not MANIFEST.is_file() or not PROMPTS.is_file():
        raise FileNotFoundError("run build-manifest first")
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if len([value for value in visible.split(",") if value.strip()]) != 1:
        raise RuntimeError("exactly one CUDA_VISIBLE_DEVICES entry is required")

    import soundfile as sf
    import torch

    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row

    prompts = {row["prompt_id"]: row for row in read_jsonl(PROMPTS)}
    tasks = read_csv(MANIFEST)
    mine = tasks[worker_index::num_workers]
    if limit:
        mine = mine[:limit]
    done = _done_keys()
    ledger = LEDGER_DIR / f"factorial_w{worker_index}.jsonl"
    model = AceStepModel(device="cuda", dtype="bfloat16")
    written = 0
    for task in mine:
        if task["task_id"] in done:
            continue
        started = time.time()
        output = ROOT / task["output_path"]
        record = {
            **task,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "cuda_visible_devices": visible,
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "status": "FAIL",
            "error": "",
        }
        try:
            row = prompts[task["prompt_id"]]
            prompt = _prompt_from_row(row)
            prompt = dataclasses.replace(prompt, duration_target=DURATION_SECONDS)
            intervention, cfg_scale = condition_spec(task["condition"])
            if intervention:
                prompt = dataclasses.replace(
                    prompt,
                    text=prompt.text.rstrip(". ") + ", " + intervention,
                    lyrics=None,
                )
            seed = int(task["seed"])
            seed_everything(seed)
            result = model.sample(
                prompt,
                seed=seed,
                cfg_scale=cfg_scale,
                steps=30,
                return_trajectory=False,
                extras=BASE_EXTRAS,
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            scratch = Path(f"/dev/shm/w2fact_{worker_index}_{task['task_id']}.wav")
            save_audio(scratch, result.waveform, result.sample_rate)
            samples, sample_rate = sf.read(str(scratch), always_2d=True, dtype="float32")
            sf.write(str(output), samples, sample_rate, format="FLAC")
            if scratch.exists():
                scratch.unlink()
            decoded, decoded_sr = sf.read(str(output), always_2d=True, dtype="float32")
            rms = float(np.sqrt(np.mean(np.square(decoded, dtype=np.float64))))
            duration = len(decoded) / decoded_sr
            if duration <= 5 or rms <= 1e-7:
                raise RuntimeError(f"invalid output duration={duration:.6f}, rms={rms:.8g}")
            record.update(
                {
                    "status": "PASS",
                    "sample_rate": int(decoded_sr),
                    "duration_s": round(duration, 6),
                    "rms": rms,
                    "near_silent": bool(20 * math.log10(max(rms, 1e-12)) < -60),
                    "waveform_sha256": sha256_file(output),
                    "decoded_audio_sha256": decoded_hash(decoded, decoded_sr),
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
    return 0 if written or all(row["task_id"] in done for row in mine) else 1


def audit() -> dict:
    tasks = read_csv(MANIFEST)
    latest: dict[str, dict] = {}
    parse_errors: list[str] = []
    for path in sorted(LEDGER_DIR.glob("factorial_w*.jsonl")):
        try:
            rows = read_jsonl(path)
        except Exception as exc:  # noqa: BLE001
            parse_errors.append(f"{path}: {exc}")
            continue
        for row in rows:
            latest[str(row.get("task_id"))] = row
    missing = []
    invalid = []
    for task in tasks:
        row = latest.get(task["task_id"])
        if not row or row.get("status") != "PASS":
            missing.append(task["task_id"])
            continue
        output = ROOT / task["output_path"]
        if not output.is_file() or output.stat().st_size == 0:
            invalid.append(task["task_id"])
            continue
        if sha256_file(output) != row.get("waveform_sha256"):
            invalid.append(task["task_id"])
    keys = [(row["prompt_id"], row["condition"], int(row["seed_idx"])) for row in tasks]
    report = {
        "status": "PASS" if not parse_errors and not missing and not invalid and len(set(keys)) == 3072 else "FAIL",
        "manifest_rows": len(tasks),
        "unique_keys": len(set(keys)),
        "successful_latest_rows": sum(row.get("status") == "PASS" for row in latest.values()),
        "missing_or_failed_count": len(missing),
        "invalid_media_count": len(invalid),
        "parse_errors": parse_errors,
        "missing_or_failed_examples": missing[:20],
        "invalid_media_examples": invalid[:20],
        "condition_counts": dict(Counter(row["condition"] for row in tasks)),
    }
    AUDIT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT_MD.write_text(
        "# W2 Factorial Generation Audit\n\n"
        f"`FACTORIAL_GENERATION_AUDIT = {report['status']}`\n\n"
        f"- Manifest rows: {report['manifest_rows']}\n"
        f"- Unique `(prompt_id, condition, seed_idx)` keys: {report['unique_keys']}\n"
        f"- Successful latest ledger rows: {report['successful_latest_rows']}\n"
        f"- Missing or failed: {report['missing_or_failed_count']}\n"
        f"- Invalid or checksum-mismatched media: {report['invalid_media_count']}\n"
        f"- JSONL parse errors: {len(report['parse_errors'])}\n",
        encoding="utf-8",
    )
    return report


def build_spotcheck(apparent_results: Path) -> dict:
    """Stage 20 baseline-vs-best pairs without interpreting them as promotion."""
    rows = read_csv(apparent_results)
    required = {"prompt_id", "condition", "seed_idx", "apparent_violation", "output_path"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"apparent results need columns {sorted(required)}")
    by_condition: dict[str, list[int]] = {condition: [] for condition in CONDITIONS}
    for row in rows:
        by_condition[row["condition"]].append(int(row["apparent_violation"]))
    means = {key: sum(values) / len(values) for key, values in by_condition.items() if values}
    eligible = [condition for condition in CONDITIONS if condition != "plain_baseline"]
    best = min(eligible, key=lambda condition: (means[condition], CONDITIONS.index(condition)))
    index = {(row["prompt_id"], row["condition"], int(row["seed_idx"])): row for row in rows}
    pairs = []
    for prompt_rank, prompt in enumerate(read_jsonl(PROMPTS)):
        seed_idx = prompt_rank % N_SEEDS
        left = index[(prompt["prompt_id"], "plain_baseline", seed_idx)]
        right = index[(prompt["prompt_id"], best, seed_idx)]
        pairs.append(
            {
                "pair_id": f"factorial_spot_{prompt_rank:02d}",
                "prompt_id": prompt["prompt_id"],
                "seed_idx": seed_idx,
                "baseline_path": left["output_path"],
                "comparison_path": right["output_path"],
                "comparison_condition": best,
                "selection_role": "apparent_candidate_only_not_promotion_evidence",
            }
        )
    pairs = sorted(pairs, key=lambda row: hashlib.sha256(row["pair_id"].encode()).hexdigest())[:20]
    write_csv(SPOT_MANIFEST, sorted(pairs, key=lambda row: row["pair_id"]))
    return {"pairs": len(pairs), "apparent_best_condition": best}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-manifest")
    generate_parser = sub.add_parser("generate")
    generate_parser.add_argument("--worker-index", type=int, required=True)
    generate_parser.add_argument("--num-workers", type=int, required=True)
    generate_parser.add_argument("--limit", type=int, default=0)
    sub.add_parser("audit")
    spot = sub.add_parser("build-spotcheck")
    spot.add_argument("--apparent-results", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build-manifest":
        print(json.dumps(build_manifest(), indent=2, sort_keys=True))
        return 0
    if args.command == "generate":
        return generate(args.worker_index, args.num_workers, args.limit)
    if args.command == "audit":
        result = audit()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    if args.command == "build-spotcheck":
        print(json.dumps(build_spotcheck(args.apparent_results), indent=2, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())

