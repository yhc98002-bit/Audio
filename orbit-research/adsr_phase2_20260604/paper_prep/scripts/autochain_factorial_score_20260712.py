#!/usr/bin/env python3
"""Apply the T6 instrument and score all preregistered W2 factorial outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import socket
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
OUT = PAPER / "autochain_20260712/factorial"
AUTOCHAIN = PAPER / "autochain_20260712"
FACTORIAL = PAPER / "w2_execution_20260712/factorial"
CANONICAL = FACTORIAL / "FACTORIAL_CANONICAL_APPARENT_RESULTS.csv"
PROMPTS = FACTORIAL / "FACTORIAL_PROMPTS.jsonl"
PROMOTION = AUTOCHAIN / "T6_PROMOTION_RESULT.json"
RECOMPUTE_SCRIPT = PAPER / "scripts/autochain_corrected_recompute_20260712.py"
SCORE_TABLE = OUT / "FACTORIAL_CORRECTED_SCORE_ROWS.csv"
SECONDARY_DIR = OUT / "secondary_ledgers"
CONDITION_TABLE = OUT / "FACTORIAL_CONDITION_RESULTS.csv"
INTERACTIONS = OUT / "FACTORIAL_INTERACTION_CONTRASTS.csv"
REPORT = OUT / "FACTORIAL_SCORING_REPORT.md"
MODEL_AUDIT = OUT / "FACTORIAL_MODEL_AUDIT.json"
STDOUT = OUT / "FACTORIAL_PREPARE_RESULT.json"

CONDITIONS = (
    "plain_baseline",
    "negative_text",
    "positive_text",
    "sampler_only",
    "negative_sampler",
    "positive_sampler",
)
BOOTSTRAP_SEED = 20260715
BOOTSTRAP_REPLICATES = 10_000


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECOMPUTE = load_module(RECOMPUTE_SCRIPT, "autochain_corrected_recompute_for_factorial")
CAL = RECOMPUTE.CAL


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def latest_ledgers(pattern: str) -> dict[str, dict]:
    rows = {}
    for path in sorted(FACTORIAL.glob(pattern)):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[row["task_id"]] = row
    return rows


def prepare() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    canonical = read_csv(CANONICAL)
    if len(canonical) != 3_072 or Counter(row["condition"] for row in canonical) != Counter({condition: 512 for condition in CONDITIONS}):
        raise ValueError("factorial canonical cardinality changed")
    original = latest_ledgers("scoring_ledgers/factorial_score_w*.jsonl")
    positive = latest_ledgers("positive_correction_scoring_ledgers/positive_scoring_w*.jsonl")
    scores = {**original, **positive}
    if len(original) != 3_072 or len(positive) != 1_024:
        raise ValueError(f"factorial score ledgers incomplete: original={len(original)}, positive={len(positive)}")
    promotion = json.loads(PROMOTION.read_text(encoding="utf-8"))
    if promotion["CORRECTED_INSTRUMENT_STATUS"] != "PROMOTED":
        raise ValueError("factorial scoring requires mechanical promotion")
    candidate = promotion["heldout"]["selected_candidate"]
    calibration = RECOMPUTE.prepare_calibration()
    fit = CAL.select_model(calibration)
    model_audit = {key: value for key, value in fit.items() if key != "model"}
    prompt_rows = {row["prompt_id"]: row for row in read_jsonl(PROMPTS)}
    if any(row.get("vocal_stratum") != "instrumental" for row in prompt_rows.values()):
        raise ValueError("factorial prompt manifest contains a non-instrumental request")
    prepared = []
    for row in canonical:
        score = scores.get(row["task_id"])
        if score is None:
            raise ValueError(f"missing canonical score row {row['task_id']}")
        if score["output_path"] != row["output_path"]:
            raise ValueError(f"canonical path mismatch for {row['task_id']}")
        path = ROOT / row["output_path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        prepared.append(
            {
                **row,
                # Positive-v2 score ledgers omit this redundant field. The
                # preregistered factorial prompt manifest freezes all requests
                # as instrumental, so derive the value from that manifest.
                "requested_vocal": int(score.get("requested_vocal", 0)),
                "demucs_score": float(score["demucs_score"]),
                "panns_score": float(score["panns_score"]),
                "near_silent": int(bool(score["near_silent"])),
                "design_weight": 1.0,
                "apparent_violation": int(row["apparent_violation"]),
            }
        )
    probability = CAL.predict_probability(prepared, fit)
    output = []
    for row, value in zip(prepared, probability):
        present = RECOMPUTE.selected_present(row, candidate)
        violation = int(present != int(row["requested_vocal"]))
        output.append(
            {
                **row,
                "corrected_present": present,
                "corrected_violation": violation,
                "calibrated_violation_probability": float(value),
                "calibrated_satisfaction_probability": 1.0 - float(value),
                "instrument_status": "PROMOTED_MECHANICAL_DRAFT_AWAITING_DUAL_PI_ADOPTION",
            }
        )
    write_csv(SCORE_TABLE, output)
    MODEL_AUDIT.write_text(
        json.dumps(
            {
                "status": "TRAIN_ONLY_CALIBRATION_MODEL_APPLIED",
                "selection": model_audit,
                "candidate": candidate,
                "calibration_rows_decided": len(calibration),
                "rating_source": "pi:Richard",
                "publication_adoption": "BLOCKED_UNTIL_BOTH_W2_SIGNATURES",
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    result = {
        "status": "PREPARED",
        "rows": len(output),
        "condition_counts": dict(Counter(row["condition"] for row in output)),
        "selected_model": model_audit["selected"],
        "selected_candidate": candidate,
    }
    STDOUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _prompt_map() -> dict[str, object]:
    from mprm.data.prompts import Prompt

    result = {}
    for row in read_jsonl(PROMPTS):
        result[row["prompt_id"]] = Prompt(
            prompt_id=row["prompt_id"],
            text=row["text"],
            lyrics=row.get("lyrics"),
            structure_hint=row.get("structure_hint"),
            duration_target=float(row["duration_target"]),
            metadata={"source": row.get("source", "")},
            strata={"vocal_vs_instrumental": row.get("vocal_stratum", "instrumental")},
        )
    return result


def _completed_ids() -> set[str]:
    done = set()
    for path in SECONDARY_DIR.glob("secondary_w*.jsonl"):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                done.add(row["task_id"])
    return done


def _signal_metrics(wave, sample_rate: int) -> dict:
    import torch
    import torchaudio

    mono = wave.float().mean(dim=0)
    rms = float(torch.sqrt(torch.mean(mono.square())).item())
    peak = float(mono.abs().max().item())
    clipping = float((mono.abs() >= 0.999).float().mean().item())
    crest = peak / max(rms, 1e-12)
    n_fft = 2048
    spectrum = torch.stft(mono, n_fft=n_fft, hop_length=1024, return_complex=True).abs().square()
    energy = spectrum.sum(dim=1).clamp_min(1e-12)
    frequencies = torch.linspace(0, sample_rate / 2, spectrum.shape[0])
    centroid = float((frequencies * energy).sum().item() / energy.sum().item())
    mfcc = torchaudio.transforms.MFCC(
        sample_rate=sample_rate,
        n_mfcc=20,
        melkwargs={"n_fft": n_fft, "hop_length": 1024, "n_mels": 64},
    )(mono.unsqueeze(0)).squeeze(0)
    feature = torch.cat((mfcc.mean(dim=1), mfcc.std(dim=1))).cpu().numpy().astype(float)
    return {
        "rms": rms,
        "peak": peak,
        "clipping_fraction": clipping,
        "crest_factor": crest,
        "spectral_centroid_hz": centroid,
        "mfcc_summary": feature.tolist(),
    }


def score_secondary(worker_index: int, num_workers: int) -> dict:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    visible = [item for item in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if item]
    if len(visible) != 1:
        raise RuntimeError("exactly one CUDA_VISIBLE_DEVICES entry is required")
    import torch
    import torchaudio
    from mprm.rewards.audiobox import AudioboxReward
    from mprm.rewards.clap import ClapReward

    rows = read_csv(SCORE_TABLE)
    shard = rows[worker_index::num_workers]
    done = _completed_ids()
    prompts = _prompt_map()
    clap = ClapReward(device="cuda")
    aesthetics = AudioboxReward(target_axis="PQ", device="cuda")
    ledger = SECONDARY_DIR / f"secondary_w{worker_index}.jsonl"
    written = 0
    failures = 0
    for row in shard:
        if row["task_id"] in done:
            continue
        started = time.time()
        result = {
            "task_id": row["task_id"],
            "prompt_id": row["prompt_id"],
            "condition": row["condition"],
            "seed_idx": int(row["seed_idx"]),
            "seed": int(row["seed"]),
            "output_path": row["output_path"],
            "worker_index": worker_index,
            "num_workers": num_workers,
            "host": socket.gethostname(),
            "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
            "gpu_name": torch.cuda.get_device_name(0),
            "status": "FAIL",
            "error": "",
        }
        try:
            wave, sample_rate = torchaudio.load(str(ROOT / row["output_path"]))
            signal = _signal_metrics(wave, sample_rate)
            clap_score = clap.score(wave, sample_rate, prompts[row["prompt_id"]])
            aesthetic = aesthetics.score(wave, sample_rate, prompts[row["prompt_id"]])
            result.update(
                {
                    **signal,
                    "sample_rate": sample_rate,
                    "duration_seconds": wave.shape[-1] / sample_rate,
                    "clap_prompt_similarity": float(clap_score.value),
                    "aesthetic_pq": float(aesthetic.raw["PQ"]),
                    "aesthetic_pc": float(aesthetic.raw["PC"]),
                    "aesthetic_ce": float(aesthetic.raw["CE"]),
                    "aesthetic_cu": float(aesthetic.raw["CU"]),
                    "status": "PASS",
                }
            )
            written += 1
        except Exception as exc:  # noqa: BLE001
            result["error"] = repr(exc)
            failures += 1
        result["elapsed_s"] = round(time.time() - started, 3)
        append_jsonl(ledger, result)
        if (written + failures) % 25 == 0:
            print(f"worker={worker_index} completed={written + failures}/{len(shard)} failures={failures}", flush=True)
    return {"worker": worker_index, "shard_rows": len(shard), "written": written, "failures": failures}


def _secondary_rows() -> dict[str, dict]:
    rows = {}
    for path in sorted(SECONDARY_DIR.glob("secondary_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[row["task_id"]] = row
    return rows


def _bootstrap_condition(rows: list[dict], key: str, rng: np.random.Generator) -> tuple[float, float]:
    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(float(row[key]))
    prompts = sorted(by_prompt)
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(prompts, size=len(prompts), replace=True)
        estimates.append(float(np.mean([value for prompt in sampled for value in by_prompt[str(prompt)]])))
    return float(np.quantile(estimates, 0.025)), float(np.quantile(estimates, 0.975))


def _diversity(rows: list[dict]) -> float:
    values = []
    by_prompt: dict[str, list[np.ndarray]] = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(np.asarray(json.loads(row["mfcc_summary"]) if isinstance(row["mfcc_summary"], str) else row["mfcc_summary"], dtype=float))
    for vectors in by_prompt.values():
        matrix = np.stack(vectors)
        matrix = matrix / np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12, None)
        similarity = matrix @ matrix.T
        upper = np.triu_indices(len(vectors), k=1)
        values.extend((1 - similarity[upper]).tolist())
    return float(np.mean(values))


def finalize() -> dict:
    primary = read_csv(SCORE_TABLE)
    secondary = _secondary_rows()
    if len(primary) != 3_072 or len(secondary) != 3_072:
        raise ValueError(f"factorial secondary scoring incomplete: primary={len(primary)}, secondary={len(secondary)}")
    rows = [{**row, **secondary[row["task_id"]]} for row in primary]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    condition_rows = []
    for condition in CONDITIONS:
        group = [row for row in rows if row["condition"] == condition]
        ci = _bootstrap_condition(group, "calibrated_satisfaction_probability", rng)
        condition_rows.append(
            {
                "condition": condition,
                "rows": len(group),
                "prompts": len({row["prompt_id"] for row in group}),
                "apparent_satisfaction_rate": 1 - float(np.mean([int(row["apparent_violation"]) for row in group])),
                "corrected_instrument_satisfaction_rate": 1 - float(np.mean([int(row["corrected_violation"]) for row in group])),
                "calibrated_satisfaction_rate": float(np.mean([float(row["calibrated_satisfaction_probability"]) for row in group])),
                "calibrated_95_ci_low": ci[0],
                "calibrated_95_ci_high": ci[1],
                "clap_prompt_similarity_mean": float(np.mean([float(row["clap_prompt_similarity"]) for row in group])),
                "aesthetic_pq_mean": float(np.mean([float(row["aesthetic_pq"]) for row in group])),
                "near_silence_rate": float(np.mean([int(row["near_silent"]) for row in group])),
                "rms_mean": float(np.mean([float(row["rms"]) for row in group])),
                "clipping_fraction_mean": float(np.mean([float(row["clipping_fraction"]) for row in group])),
                "mfcc_pairwise_cosine_distance": _diversity(group),
                "status": "DRAFT_AWAITING_DUAL_PI_ADOPTION",
            }
        )
    by_condition = {row["condition"]: row for row in condition_rows}
    interactions = []
    for wording in ("negative", "positive"):
        text = by_condition[f"{wording}_text"]["calibrated_satisfaction_rate"]
        combined = by_condition[f"{wording}_sampler"]["calibrated_satisfaction_rate"]
        baseline = by_condition["plain_baseline"]["calibrated_satisfaction_rate"]
        sampler = by_condition["sampler_only"]["calibrated_satisfaction_rate"]
        interactions.append(
            {
                "wording_factor": wording,
                "interaction_contrast": (combined - sampler) - (text - baseline),
                "definition": f"({wording}_sampler - sampler_only) - ({wording}_text - plain_baseline)",
                "status": "DRAFT_AWAITING_DUAL_PI_ADOPTION",
            }
        )
    write_csv(CONDITION_TABLE, condition_rows)
    write_csv(INTERACTIONS, interactions)
    best = max(condition_rows, key=lambda row: (row["calibrated_satisfaction_rate"], row["condition"]))
    REPORT.write_text(
        "# Instrumental Factorial Scoring\n\n"
        "`FACTORIAL_SCORING_STATUS = COMPLETE_PROMOTED_INSTRUMENT_DRAFT`\n\n"
        "All 3,072 preregistered clips were scored with the mechanically promoted instrument and the train-only calibrated model. "
        "Publication adoption remains blocked on both W2 signatures.\n\n"
        "| Condition | Calibrated satisfaction | 95% prompt-bootstrap CI | Corrected hard satisfaction | CLAP | Audiobox PQ | Near silent | Diversity distance |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
        + "\n".join(
            f"| {row['condition']} | {row['calibrated_satisfaction_rate']:.4f} | "
            f"[{row['calibrated_95_ci_low']:.4f}, {row['calibrated_95_ci_high']:.4f}] | "
            f"{row['corrected_instrument_satisfaction_rate']:.4f} | {row['clap_prompt_similarity_mean']:.4f} | "
            f"{row['aesthetic_pq_mean']:.4f} | {row['near_silence_rate']:.4f} | {row['mfcc_pairwise_cosine_distance']:.4f} |"
            for row in condition_rows
        )
        + "\n\n"
        + "## Interaction Contrasts\n\n"
        + "\n".join(f"- {row['wording_factor']}: {row['interaction_contrast']:.6f}." for row in interactions)
        + "\n\n"
        + f"Best draft calibrated condition: `{best['condition']}` ({best['calibrated_satisfaction_rate']:.4f}). "
        "The existing 20-pair blinded PI spot-check bundle remains staged and unscored.\n",
        encoding="utf-8",
    )
    return {
        "FACTORIAL_SCORING_STATUS": "COMPLETE_PROMOTED_INSTRUMENT_DRAFT",
        "rows": len(rows),
        "best_condition": best["condition"],
        "best_calibrated_satisfaction": best["calibrated_satisfaction_rate"],
        "condition_table": str(CONDITION_TABLE.relative_to(ROOT)),
        "interaction_table": str(INTERACTIONS.relative_to(ROOT)),
        "report": str(REPORT.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    score = sub.add_parser("score-secondary")
    score.add_argument("--worker-index", type=int, required=True)
    score.add_argument("--num-workers", type=int, required=True)
    sub.add_parser("finalize")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "score-secondary":
        result = score_secondary(args.worker_index, args.num_workers)
    elif args.command == "finalize":
        result = finalize()
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
