#!/usr/bin/env python3
"""Correct the W2 factorial positive-only full-prompt implementation."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import re
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
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
sys.path.insert(0, str(ROOT / "paper_prep/w2_contingency_20260711"))
import w2_factorial_20260712 as base  # noqa: E402


OUT = base.OUT
MANIFEST = OUT / "FACTORIAL_POSITIVE_CORRECTION_MANIFEST.csv"
LEXICAL_AUDIT = OUT / "FACTORIAL_POSITIVE_CORRECTION_LEXICAL_AUDIT.json"
LEDGER_DIR = OUT / "positive_correction_ledgers"
SCORING_DIR = OUT / "positive_correction_scoring_ledgers"
GEN_AUDIT = OUT / "FACTORIAL_POSITIVE_CORRECTION_GENERATION_AUDIT.json"
CANONICAL_RESULTS = OUT / "FACTORIAL_CANONICAL_APPARENT_RESULTS.csv"
REPORT = OUT / "FACTORIAL_CANONICAL_READOUT.md"
POSITIVE_CONDITIONS = ("positive_text", "positive_sampler")
FORBIDDEN_WORDS = (
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
    "lyric",
    "lyrics",
)
FORBIDDEN_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in FORBIDDEN_WORDS) + r")\b",
    re.IGNORECASE,
)
PAREN_RE = re.compile(
    r"\s*\([^)]*\b(?:"
    + "|".join(re.escape(word) for word in FORBIDDEN_WORDS)
    + r")\b[^)]*\)",
    re.IGNORECASE,
)


def sanitize_positive_base(text: str) -> str:
    value = PAREN_RE.sub("", text)
    value = re.sub(
        r"\bInstrumental\s*(?:\u2014|--?|-|:)\s*no\s+vocals?\.?",
        "Instrumental.",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(?:with\s+)?no\s+(?:vocals?|voices?|singing|speech|rap)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    value = re.sub(r"([,;:])\s*([.])", r"\2", value)
    value = re.sub(r"\.{2,}", ".", value)
    value = value.strip(" ,;")
    if not value:
        raise ValueError("sanitization removed the complete prompt")
    leaked = sorted(set(match.group(0).lower() for match in FORBIDDEN_RE.finditer(value)))
    if leaked:
        raise ValueError(f"sanitized base still contains vocal/lyrics lexemes: {leaked}: {value}")
    return value


def full_positive_text(text: str) -> str:
    base_text = sanitize_positive_base(text).rstrip(". ")
    result = base_text + ". " + base.POSITIVE_TEXT + "."
    leaked = sorted(set(match.group(0).lower() for match in FORBIDDEN_RE.finditer(result)))
    if leaked:
        raise ValueError(f"full positive prompt contains forbidden lexemes: {leaked}")
    return result


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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def build_manifest() -> dict:
    original_tasks = read_csv(base.MANIFEST)
    prompts = {row["prompt_id"]: row for row in read_jsonl(base.PROMPTS)}
    rows = []
    prompt_audit = []
    for prompt_id, prompt in sorted(prompts.items(), key=lambda item: int(item[1]["factorial_prompt_rank"])):
        source_text = prompt["text"]
        corrected = full_positive_text(source_text)
        original_matches = sorted(set(match.group(0).lower() for match in FORBIDDEN_RE.finditer(source_text)))
        prompt_audit.append(
            {
                "prompt_id": prompt_id,
                "source_had_forbidden_lexeme": bool(original_matches),
                "source_forbidden_lexemes": original_matches,
                "corrected_forbidden_lexemes": [match.group(0) for match in FORBIDDEN_RE.finditer(corrected)],
                "source_text_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
                "corrected_text_sha256": hashlib.sha256(corrected.encode()).hexdigest(),
            }
        )
    corrected_text = {
        row["prompt_id"]: full_positive_text(row["text"])
        for row in prompts.values()
    }
    for task in original_tasks:
        if task["condition"] not in POSITIVE_CONDITIONS:
            continue
        output = OUT / "audio_positive_v2" / task["condition"] / task["prompt_id"] / (
            f"{task['condition']}_v2_s{int(task['seed_idx']):02d}_{task['seed']}.flac"
        )
        rows.append(
            {
                "task_id": task["task_id"] + "_positive_v2",
                "original_task_id": task["task_id"],
                "prompt_rank": task["prompt_rank"],
                "prompt_id": task["prompt_id"],
                "condition": task["condition"],
                "seed_idx": task["seed_idx"],
                "seed": task["seed"],
                "cfg_scale": task["cfg_scale"],
                "duration_seconds": task["duration_seconds"],
                "corrected_full_text": corrected_text[task["prompt_id"]],
                "corrected_text_sha256": hashlib.sha256(corrected_text[task["prompt_id"]].encode()).hexdigest(),
                "output_path": str(output.relative_to(ROOT)),
                "analysis_role": "PRIMARY_CORRECTED_POSITIVE_ONLY_REPLACEMENT",
                "invalid_predecessor_path": task["output_path"],
                "seed_policy": "exact_CRN_replacement_not_independent_observation",
            }
        )
    if len(rows) != 1024:
        raise ValueError(f"expected 1024 positive corrections, found {len(rows)}")
    if len({(row["prompt_id"], row["condition"], row["seed_idx"]) for row in rows}) != 1024:
        raise ValueError("positive correction keys are not unique")
    write_csv(MANIFEST, rows)
    audit = {
        "status": "PASS_ZERO_VOCAL_OR_LYRICS_LEXEMES",
        "prompts": len(prompt_audit),
        "source_prompts_with_forbidden_lexemes": sum(row["source_had_forbidden_lexeme"] for row in prompt_audit),
        "corrected_prompts_with_forbidden_lexemes": sum(bool(row["corrected_forbidden_lexemes"]) for row in prompt_audit),
        "replacement_tasks": len(rows),
        "same_seed_as_invalid_predecessor": all(int(row["seed"]) == int(next(task["seed"] for task in original_tasks if task["task_id"] == row["original_task_id"])) for row in rows),
        "prompt_details": prompt_audit,
    }
    LEXICAL_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def _latest(directory: Path, pattern: str) -> dict[str, dict]:
    rows = {}
    for path in sorted(directory.glob(pattern)):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[row["task_id"]] = row
    return rows


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

    prompts = {row["prompt_id"]: row for row in read_jsonl(base.PROMPTS)}
    tasks = read_csv(MANIFEST)
    mine = tasks[worker_index::num_workers]
    if limit:
        mine = mine[:limit]
    done = _latest(LEDGER_DIR, "positive_generation_w*.jsonl")
    ledger = LEDGER_DIR / f"positive_generation_w{worker_index}.jsonl"
    model = AceStepModel(device="cuda", dtype="bfloat16")
    written = 0
    for task in mine:
        if task["task_id"] in done:
            continue
        output = ROOT / task["output_path"]
        started = time.time()
        record = {
            **task,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "status": "FAIL",
            "error": "",
        }
        try:
            source = prompts[task["prompt_id"]]
            prompt = _prompt_from_row(source)
            prompt = dataclasses.replace(
                prompt,
                text=task["corrected_full_text"],
                lyrics=None,
                duration_target=base.DURATION_SECONDS,
            )
            if hashlib.sha256(prompt.text.encode()).hexdigest() != task["corrected_text_sha256"]:
                raise RuntimeError("corrected prompt hash mismatch")
            if FORBIDDEN_RE.search(prompt.text):
                raise RuntimeError("vocal/lyrics lexeme reached corrected generation")
            seed = int(task["seed"])
            seed_everything(seed)
            result = model.sample(
                prompt,
                seed=seed,
                cfg_scale=float(task["cfg_scale"]),
                steps=30,
                return_trajectory=False,
                extras=base.BASE_EXTRAS,
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            scratch = Path(f"/dev/shm/w2fact_positive_v2_{worker_index}_{task['task_id']}.wav")
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
                    "waveform_sha256": base.sha256_file(output),
                    "decoded_audio_sha256": base.decoded_hash(decoded, decoded_sr),
                    "gpu_name": torch.cuda.get_device_name(0),
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


def score(worker_index: int, num_workers: int, limit: int) -> int:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    from w2_instruments import CurrentDemucsInstrument, LivePannsInstrument

    tasks = read_csv(MANIFEST)
    mine = tasks[worker_index::num_workers]
    if limit:
        mine = mine[:limit]
    done = _latest(SCORING_DIR, "positive_scoring_w*.jsonl")
    demucs = CurrentDemucsInstrument(device="cuda", threshold=base.OLD_THRESHOLD)
    panns = LivePannsInstrument(device="cuda", threshold=base.CANDIDATE_PANNS_THRESHOLD)
    ledger = SCORING_DIR / f"positive_scoring_w{worker_index}.jsonl"
    written = 0
    for task in mine:
        if task["task_id"] in done:
            continue
        started = time.time()
        path = ROOT / task["output_path"]
        record = {
            "task_id": task["task_id"],
            "original_task_id": task["original_task_id"],
            "prompt_id": task["prompt_id"],
            "condition": task["condition"],
            "seed_idx": int(task["seed_idx"]),
            "seed": int(task["seed"]),
            "output_path": task["output_path"],
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "status": "FAIL",
            "error": "",
        }
        try:
            base._seed_scoring(task["task_id"] + "|demucs")
            d = demucs.score(path)
            base._seed_scoring(task["task_id"] + "|panns")
            p = panns.score(path)
            candidate_d = int(d["vocal_energy_ratio"] >= base.CANDIDATE_DEMUCS_THRESHOLD and not d["near_silent"])
            candidate_p = int(p["panns_score"] >= base.CANDIDATE_PANNS_THRESHOLD)
            candidate = int(candidate_d and candidate_p)
            record.update(
                {
                    "status": "PASS",
                    "demucs_score": float(d["vocal_energy_ratio"]),
                    "near_silent": bool(d["near_silent"]),
                    "old_present": int(d["present"]),
                    "panns_score": float(p["panns_score"]),
                    "panns_top_vocal_class": p["panns_top_vocal_class"],
                    "candidate_demucs_present": candidate_d,
                    "candidate_panns_present": candidate_p,
                    "candidate_present": candidate,
                    "old_violation": int(d["present"]),
                    "candidate_violation": candidate,
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


def audit() -> dict:
    tasks = read_csv(MANIFEST)
    generation = _latest(LEDGER_DIR, "positive_generation_w*.jsonl")
    scoring = _latest(SCORING_DIR, "positive_scoring_w*.jsonl")
    invalid = []
    for task in tasks:
        generated = generation.get(task["task_id"])
        path = ROOT / task["output_path"]
        if not generated or not path.is_file() or base.sha256_file(path) != generated.get("waveform_sha256"):
            invalid.append(task["task_id"])
    status = "PASS" if len(tasks) == len(generation) == len(scoring) == 1024 and not invalid else "FAIL"
    result = {
        "status": status,
        "manifest_rows": len(tasks),
        "generation_rows": len(generation),
        "scoring_rows": len(scoring),
        "invalid_media_count": len(invalid),
        "lexical_audit_sha256": base.sha256_file(LEXICAL_AUDIT),
    }
    GEN_AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def analyze() -> dict:
    original_scores = base._latest_scoring()
    corrected_scores = _latest(SCORING_DIR, "positive_scoring_w*.jsonl")
    if len(original_scores) != 3072 or len(corrected_scores) != 1024:
        raise ValueError(f"scoring incomplete: original={len(original_scores)}, corrected={len(corrected_scores)}")
    original_tasks = {row["task_id"]: row for row in read_csv(base.MANIFEST)}
    corrected_tasks = {row["task_id"]: row for row in read_csv(MANIFEST)}
    rows = []
    for task_id, task in original_tasks.items():
        if task["condition"] in POSITIVE_CONDITIONS:
            continue
        score_row = original_scores[task_id]
        rows.append(
            {
                "task_id": task_id,
                "prompt_id": task["prompt_id"],
                "condition": task["condition"],
                "seed_idx": int(task["seed_idx"]),
                "seed": int(task["seed"]),
                "output_path": task["output_path"],
                "apparent_violation": score_row["old_violation"],
                "candidate_violation": score_row["candidate_violation"],
                "implementation_role": "ORIGINAL_UNAFFECTED_PRIMARY",
            }
        )
    for task_id, task in corrected_tasks.items():
        score_row = corrected_scores[task_id]
        rows.append(
            {
                "task_id": task_id,
                "prompt_id": task["prompt_id"],
                "condition": task["condition"],
                "seed_idx": int(task["seed_idx"]),
                "seed": int(task["seed"]),
                "output_path": task["output_path"],
                "apparent_violation": score_row["old_violation"],
                "candidate_violation": score_row["candidate_violation"],
                "implementation_role": "CORRECTED_POSITIVE_ONLY_PRIMARY",
            }
        )
    if len(rows) != 3072:
        raise AssertionError(f"canonical factorial rows={len(rows)}")
    rows.sort(key=lambda row: (base.CONDITIONS.index(row["condition"]), row["prompt_id"], row["seed_idx"]))
    write_csv(CANONICAL_RESULTS, rows)
    summaries = []
    for condition in base.CONDITIONS:
        group = [row for row in rows if row["condition"] == condition]
        summaries.append(
            {
                "condition": condition,
                "rows": len(group),
                "apparent_rate": float(np.mean([row["apparent_violation"] for row in group])),
                "candidate_rate": float(np.mean([row["candidate_violation"] for row in group])),
                "candidate_95_ci": base._cluster_bootstrap(group, "candidate_violation"),
            }
        )
    spot = base.build_spotcheck(CANONICAL_RESULTS)
    invalid_summary = {}
    for condition in POSITIVE_CONDITIONS:
        invalid_rows = [
            original_scores[task_id]
            for task_id, task in original_tasks.items()
            if task["condition"] == condition
        ]
        invalid_summary[condition] = {
            "rows": len(invalid_rows),
            "candidate_rate": float(np.mean([row["candidate_violation"] for row in invalid_rows])),
            "role": "INVALID_PREEXISTING_VOCAL_LEXEME_SENSITIVITY_ONLY",
        }
    lines = [
        "# W2 Instrumental Factorial Canonical Readout",
        "",
        "`FACTORIAL_STATUS = PREREGISTERED_GENERATED`",
        "",
        "Primary positive-condition rows use the committed full-prompt lexical correction. The first 1,024 positive rows remain an invalid implementation-sensitivity cohort.",
        "",
        "| condition | rows | current apparent violation | candidate sensitivity violation | candidate 95% prompt-bootstrap CI |",
        "|---|---:|---:|---:|---|",
    ]
    for row in summaries:
        lines.append(
            f"| `{row['condition']}` | {row['rows']} | {row['apparent_rate']:.6f} | {row['candidate_rate']:.6f} | [{row['candidate_95_ci'][0]:.6f}, {row['candidate_95_ci'][1]:.6f}] |"
        )
    lines.extend(
        [
            "",
            "All rates are apparent or candidate-instrument sensitivity results. Promoted-instrument scoring remains blocked on W2 ratings and signatures.",
            f"The 20-pair blinded PI spot check uses `{spot['apparent_best_condition']}` selected by `{spot['selection_metric']}`.",
            "",
            "## Invalid First Positive Cohort",
            "",
            f"- `positive_text`: n={invalid_summary['positive_text']['rows']}, candidate rate={invalid_summary['positive_text']['candidate_rate']:.6f}.",
            f"- `positive_sampler`: n={invalid_summary['positive_sampler']['rows']}, candidate rate={invalid_summary['positive_sampler']['candidate_rate']:.6f}.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "PREREGISTERED_GENERATED", "canonical_rows": len(rows), "summaries": summaries, "spot": spot, "invalid_positive": invalid_summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-manifest")
    generation = sub.add_parser("generate")
    generation.add_argument("--worker-index", type=int, required=True)
    generation.add_argument("--num-workers", type=int, required=True)
    generation.add_argument("--limit", type=int, default=0)
    scoring = sub.add_parser("score")
    scoring.add_argument("--worker-index", type=int, required=True)
    scoring.add_argument("--num-workers", type=int, required=True)
    scoring.add_argument("--limit", type=int, default=0)
    sub.add_parser("audit")
    sub.add_parser("analyze")
    args = parser.parse_args()
    if args.command == "build-manifest":
        result = build_manifest()
    elif args.command == "generate":
        return generate(args.worker_index, args.num_workers, args.limit)
    elif args.command == "score":
        return score(args.worker_index, args.num_workers, args.limit)
    elif args.command == "audit":
        result = audit()
    else:
        result = analyze()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
