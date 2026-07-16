#!/usr/bin/env python3
"""Reproducible Exit-1 evaluator, recipe, and unconditional-base-rate analyses."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
OUT = ROOT / "analysis_exit1"
CANONICAL_ROOT = Path(
    os.environ.get(
        "AUDIO_DIFFUSION_CANONICAL_ROOT",
        "/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion",
    )
)

ADMIN_690 = PAPER / "rater_admin_keys_20260711/t2_aprime/A_PRIME_PRIMARY_ADMIN.csv"
GOLD_690 = PAPER / (
    "t7_judge_gold_20260713/judge_completion/A_PRIME_INSTRUMENT_MERGED_690.csv"
)
APRIME_MANIFEST = PAPER / "validation_A_prime/A_PRIME_MANIFEST.csv"
APRIME_CARDINALITY = PAPER / "validation_A_prime/A_PRIME_CARDINALITY_RECONCILIATION.csv"
HUMAN_ADMIN = PAPER / "validation_A_prime/human_package/A_PRIME_HUMAN_ADMIN_MANIFEST.csv"
MERGE_AUDIT = PAPER / (
    "t7_judge_gold_20260713/judge_completion/A_PRIME_INSTRUMENT_MERGE_REPORT.json"
)
HISTORICAL_CALIBRATION = PAPER / (
    "w2_contingency_20260711/activated_20260711/calibration/"
    "W2_INSTRUMENT_CALIBRATION.json"
)

FACTORIAL_SCORES = PAPER / (
    "autochain_20260712/factorial/FACTORIAL_CORRECTED_SCORE_ROWS.csv"
)
FACTORIAL_SECONDARY = PAPER / "autochain_20260712/factorial/secondary_ledgers"
LIVE_LEDGERS = PAPER / "w2_execution_20260712/live_confirmation_20260713/live_ledgers"

EVAL_ROWS = OUT / "EVALUATOR_INPUT_ROWS.csv"
EVAL_MEDIA = OUT / "EVALUATOR_MEDIA_MANIFEST.csv"
EVAL_PREP_AUDIT = OUT / "EVALUATOR_PREP_AUDIT.json"
EVAL_LEDGER_DIR = OUT / "evaluator_score_ledgers"
EVAL_WHISPER_CSV = OUT / "EVALUATOR_WHISPER_SCORES.csv"
EVAL_AUDIOSET_CSV = OUT / "EVALUATOR_AUDIOSET_SCORES.csv"
EVAL_AUDIOSET_META = OUT / "EVALUATOR_AUDIOSET_MODEL_METADATA.json"
EVAL_TABLE = OUT / "EVALUATOR_COMPARISON_TABLE.md"
EVAL_AUDIT = OUT / "EVALUATOR_COMPARISON_AUDIT.json"

RECIPE_CSV = OUT / "RECIPE_CURVES.csv"
RECIPE_REPORT = OUT / "RECIPE_CURVES.md"
RECIPE_AUDIT = OUT / "RECIPE_CURVES_AUDIT.json"

NEUTRAL_PROMPTS = OUT / "neutral_prompts.csv"
UNCONDITIONAL_PREREG = OUT / "UNCONDITIONAL_PREREGISTRATION.json"
UNCONDITIONAL_MANIFEST = OUT / "UNCONDITIONAL_GENERATION_MANIFEST.csv"
UNCONDITIONAL_PREP_AUDIT = OUT / "UNCONDITIONAL_PREP_AUDIT.json"
UNCONDITIONAL_RUN = OUT / "unconditional_run_20260716"
UNCONDITIONAL_LEDGER_DIR = UNCONDITIONAL_RUN / "ledgers"
UNCONDITIONAL_SCORES = OUT / "UNCONDITIONAL_SCORES.csv"
UNCONDITIONAL_SHA = OUT / "UNCONDITIONAL_AUDIO_SHA256SUMS"
UNCONDITIONAL_RUN_MANIFEST = OUT / "UNCONDITIONAL_RUN_MANIFEST.json"
UNCONDITIONAL_REPORT = OUT / "UNCONDITIONAL_BASE_RATE.md"

TEST_RESULTS = OUT / "TEST_RESULTS.txt"
TEST_SUMMARY = OUT / "TEST_RESULT_SUMMARY.json"
BUNDLE_REPORT = OUT / "EXIT1_BUNDLE_REPORT.md"

LEGACY_DEMUCS_THRESHOLD = 0.1791
AND_DEMUCS_THRESHOLD = 0.038639528676867485
AND_PANNS_THRESHOLD = 0.03181814216077328
EVALUATOR_SPLIT_SEED = 2026071601
EVALUATOR_TRAIN_FRACTION = 0.40
EVALUATOR_BOOTSTRAP_SEED = 2026071602
RECIPE_BOOTSTRAP_SEED = 2026071603
BOOTSTRAP_REPLICATES = 10_000
UNCONDITIONAL_SEED_BASE = 2_036_000_000


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_hash() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _write_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite differing output: {path}")
        return
    path.write_text(content, encoding="utf-8")


def write_json_once(path: Path, value: object) -> None:
    _write_once(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def csv_text(rows: Sequence[dict]) -> str:
    if not rows:
        raise ValueError("refusing to serialize an empty CSV")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_csv_once(path: Path, rows: Sequence[dict]) -> None:
    _write_once(path, csv_text(rows))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def resolve_media_path(relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute() and raw.is_file():
        return raw
    candidates = (ROOT / raw, CANONICAL_ROOT / raw)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"media not found in worktree or canonical root: {relative}")


def binary_metrics(truth: Sequence[int], prediction: Sequence[int]) -> dict[str, float | int]:
    if len(truth) != len(prediction) or not truth:
        raise ValueError("truth and prediction must be non-empty and equally sized")
    tp = sum(y == 1 and p == 1 for y, p in zip(truth, prediction))
    tn = sum(y == 0 and p == 0 for y, p in zip(truth, prediction))
    fp = sum(y == 0 and p == 1 for y, p in zip(truth, prediction))
    fn = sum(y == 1 and p == 0 for y, p in zip(truth, prediction))
    positives = tp + fn
    negatives = tn + fp
    if not positives or not negatives:
        raise ValueError("both truth classes are required")
    sensitivity = tp / positives
    specificity = tn / negatives
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / denominator if denominator else 0.0
    return {
        "n": len(truth),
        "positives": positives,
        "negatives": negatives,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "mcc": mcc,
    }


def select_threshold(
    truth: Sequence[int], scores: Sequence[float], eligible: Sequence[bool] | None = None
) -> dict:
    if len(truth) != len(scores) or not truth:
        raise ValueError("threshold inputs must be non-empty and equally sized")
    eligible = list(eligible) if eligible is not None else [True] * len(scores)
    usable = sorted({float(score) for score, use in zip(scores, eligible) if use})
    if not usable:
        raise ValueError("threshold selection has no eligible scores")
    candidates = usable + [math.nextafter(usable[-1], math.inf)]
    best = None
    for threshold in candidates:
        prediction = [int(use and score >= threshold) for score, use in zip(scores, eligible)]
        metrics = binary_metrics(truth, prediction)
        key = (
            metrics["balanced_accuracy"],
            min(metrics["sensitivity"], metrics["specificity"]),
            metrics["mcc"],
            metrics["specificity"],
            -threshold,
        )
        if best is None or key > best[0]:
            best = (key, threshold, metrics)
    assert best is not None
    return {
        "threshold": float(best[1]),
        "train_metrics": best[2],
        "selection_rule": (
            "maximize balanced accuracy, then min(sensitivity,specificity), MCC, "
            "specificity, then lower threshold"
        ),
        "candidate_count": len(candidates),
    }


def _assign_component_split(rows: list[dict], train_fraction: float) -> None:
    parents: dict[str, str] = {}

    def find(value: str) -> str:
        parents.setdefault(value, value)
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parents[max(a, b)] = min(a, b)

    by_media: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        find(row["prompt_id"])
        by_media[row["media_sha256"]].append(row["prompt_id"])
    for prompts in by_media.values():
        for prompt in prompts[1:]:
            union(prompts[0], prompt)
    components: dict[str, list[str]] = defaultdict(list)
    for prompt in parents:
        components[find(prompt)].append(prompt)
    component_split = {}
    for root, prompts in components.items():
        key = "|".join(sorted(prompts))
        value = int(stable_hash(f"{EVALUATOR_SPLIT_SEED}|{key}")[:16], 16) / 16**16
        component_split[root] = "train" if value < train_fraction else "heldout"
    for row in rows:
        root = find(row["prompt_id"])
        row["split"] = component_split[root]
        row["split_component"] = stable_hash("|".join(sorted(components[root])))[:16]


def prepare_evaluator() -> dict:
    admin = read_csv(ADMIN_690)
    gold = read_csv(GOLD_690)
    aprime = read_csv(APRIME_MANIFEST)
    cardinality = read_csv(APRIME_CARDINALITY)
    merge = json.loads(MERGE_AUDIT.read_text(encoding="utf-8"))
    if len(admin) != 690 or len(gold) != 690 or merge.get("admin_rows") != 690:
        raise ValueError("A-prime 690-row cardinality contract changed")
    if merge.get("provenance_counts") != {"human": 0, "judge": 500, "pi": 190}:
        raise ValueError("A-prime provenance counts changed")
    gold_index = {row["rating_id"]: row for row in gold}
    if len(gold_index) != 690 or set(gold_index) != {row["rating_id"] for row in admin}:
        raise ValueError("A-prime gold/admin rating IDs differ")
    frozen_scores: dict[str, dict] = {}
    score_conflicts: list[dict] = []

    def register_score(
        media_sha256: str, demucs_score: str | float, panns_score: str | float,
        source: str, priority: int,
    ) -> None:
        if not media_sha256 or demucs_score in {"", None} or panns_score in {"", None}:
            return
        candidate = {
            "demucs_score": float(demucs_score),
            "panns_score": float(panns_score),
            "score_source": source,
            "priority": priority,
        }
        prior = frozen_scores.get(media_sha256)
        if prior is not None:
            demucs_delta = abs(prior["demucs_score"] - candidate["demucs_score"])
            panns_delta = abs(prior["panns_score"] - candidate["panns_score"])
            if demucs_delta > 5e-4 or panns_delta > 5e-4:
                if prior["priority"] == priority:
                    raise ValueError(
                        f"same-priority frozen detector scores conflict for {media_sha256}"
                    )
                score_conflicts.append(
                    {
                        "media_sha256": media_sha256,
                        "demucs_absolute_delta": demucs_delta,
                        "panns_absolute_delta": panns_delta,
                        "lower_priority_source": (
                            prior["score_source"]
                            if prior["priority"] < priority
                            else candidate["score_source"]
                        ),
                        "selected_source": (
                            candidate["score_source"]
                            if priority > prior["priority"]
                            else prior["score_source"]
                        ),
                    }
                )
            if prior["priority"] > priority:
                return
        frozen_scores[media_sha256] = candidate

    for row in aprime:
        metadata = json.loads(row["metadata_json"])
        register_score(
            str(metadata.get("sha256", "")), row["vocal_energy_ratio"],
            row["panns_vocal"], str(APRIME_MANIFEST.relative_to(ROOT)), 1,
        )
    for row in cardinality:
        register_score(
            row["sha256"], row["demucs_ratio"], row["panns_score"],
            str(APRIME_CARDINALITY.relative_to(ROOT)), 2,
        )
    canonical_score_dir = CANONICAL_ROOT / (
        "orbit-research/adsr_phase2_20260604/paper_prep/w2_contingency_20260711/"
        "activated_20260711/calibration"
    )
    pi_score_paths = sorted(canonical_score_dir.glob("PI_GOLD_SCORES_W*.jsonl"))
    if len(pi_score_paths) != 8:
        raise ValueError(f"expected eight frozen PI-gold score ledgers, found {len(pi_score_paths)}")
    for path in pi_score_paths:
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                register_score(
                    row["audio_sha256"], row["demucs_vocal_energy_ratio"],
                    row["panns_score"], str(path), 3,
                )
    hash_cache: dict[Path, str] = {}
    output = []
    missing_historical_detector_media: set[str] = set()
    for row in admin:
        score_row = frozen_scores.get(row["package_sha256"])
        if score_row is None:
            missing_historical_detector_media.add(row["package_sha256"])
            score_row = {
                "demucs_score": "",
                "panns_score": "",
                "score_source": "exit1_frozen_backend_fill",
            }
        media = resolve_media_path(row["package_media_path"])
        observed_sha = hash_cache.setdefault(media, sha256_file(media))
        if observed_sha != row["package_sha256"]:
            raise ValueError(f"on-disk media hash mismatch for {row['rating_id']}")
        label_text = gold_index[row["rating_id"]]["label_a_voice_presence"].strip().lower()
        if label_text not in {"yes", "no", "unsure"}:
            raise ValueError(f"invalid Label A value: {label_text}")
        rating_source = gold_index[row["rating_id"]]["rating_source"]
        if row["analysis_role"] == "primary" and not rating_source.startswith("pi:"):
            raise ValueError("primary A-prime row lacks PI provenance")
        if row["analysis_role"] == "global_bound" and not re.fullmatch(
            r"judge:[^:]+:validated:[0-9a-f]{64}", rating_source
        ):
            raise ValueError("global A-prime row lacks validated-judge provenance")
        output.append(
            {
                "rating_id": row["rating_id"],
                "media_sha256": row["package_sha256"],
                "clip_path": str(media),
                "prompt_id": row["prompt_id"],
                "set_bucket": row["set_bucket"],
                "analysis_role": row["analysis_role"],
                "rating_source": rating_source,
                "label_a": label_text,
                "label_binary": "" if label_text == "unsure" else int(label_text == "yes"),
                "demucs_score": score_row["demucs_score"],
                "panns_score": score_row["panns_score"],
                "existing_score_source": score_row["score_source"],
                "needs_detector_fill": int(
                    row["package_sha256"] in missing_historical_detector_media
                ),
            }
        )
    _assign_component_split(output, EVALUATOR_TRAIN_FRACTION)
    decided = [row for row in output if row["label_binary"] != ""]
    for split in ("train", "heldout"):
        labels = [int(row["label_binary"]) for row in decided if row["split"] == split]
        if min(Counter(labels).values(), default=0) < 5:
            raise ValueError(f"insufficient class support in {split} split")
    media_rows = {}
    for row in output:
        prior = media_rows.get(row["media_sha256"])
        candidate = {
            "media_sha256": row["media_sha256"],
            "clip_path": row["clip_path"],
            "split": row["split"],
            "needs_detector_fill": row["needs_detector_fill"],
        }
        if prior:
            if (
                prior["split"] != candidate["split"]
                or prior["needs_detector_fill"] != candidate["needs_detector_fill"]
            ):
                raise ValueError("one media hash maps to conflicting split or fill policy")
            if candidate["clip_path"] < prior["clip_path"]:
                media_rows[row["media_sha256"]] = candidate
        else:
            media_rows[row["media_sha256"]] = candidate
    write_csv_once(EVAL_ROWS, output)
    write_csv_once(EVAL_MEDIA, sorted(media_rows.values(), key=lambda row: row["media_sha256"]))
    result = {
        "status": "PASS",
        "nominal_rows": len(output),
        "decided_rows": len(decided),
        "unsure_rows": len(output) - len(decided),
        "unique_media": len(media_rows),
        "prompt_clusters": len({row["prompt_id"] for row in output}),
        "role_counts": dict(Counter(row["analysis_role"] for row in output)),
        "split_counts": dict(Counter(row["split"] for row in decided)),
        "split_class_counts": {
            split: dict(
                Counter(
                    row["label_a"] for row in decided if row["split"] == split
                )
            )
            for split in ("train", "heldout")
        },
        "split_seed": EVALUATOR_SPLIT_SEED,
        "split_method": (
            "SHA-256 deterministic 40/60 split over prompt/media connected components"
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in (
                ADMIN_690, GOLD_690, APRIME_MANIFEST, APRIME_CARDINALITY,
                HUMAN_ADMIN, MERGE_AUDIT,
            )
        },
        "pi_gold_score_ledger_sha256": {
            str(path): sha256_file(path) for path in pi_score_paths
        },
        "existing_score_precedence": (
            "PI-gold W2 calibration ledger, then A-prime cardinality, then A-prime manifest"
        ),
        "resolved_existing_score_conflicts": {
            "count": len(score_conflicts),
            "max_demucs_absolute_delta": max(
                (row["demucs_absolute_delta"] for row in score_conflicts), default=0.0
            ),
            "max_panns_absolute_delta": max(
                (row["panns_absolute_delta"] for row in score_conflicts), default=0.0
            ),
            "examples": score_conflicts[:10],
        },
        "missing_historical_detector_media": len(missing_historical_detector_media),
        "detector_fill_policy": (
            "Score only historically uncovered unique media with the unchanged frozen "
            "W2 Demucs/PANNs backend; preserve every available historical score."
        ),
        "new_human_labels": 0,
    }
    write_json_once(EVAL_PREP_AUDIT, result)
    return result


def _done_score_ids(pattern: str) -> set[str]:
    done = set()
    for path in sorted(EVAL_LEDGER_DIR.glob(pattern)):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                done.add(row["media_sha256"])
    return done


def _whisper_score(model, path: Path) -> dict:
    import librosa

    audio, _ = librosa.load(str(path), sr=16_000, mono=True)
    result = model.transcribe(
        audio,
        task="transcribe",
        fp16=True,
        temperature=0.0,
        beam_size=1,
        condition_on_previous_text=False,
        word_timestamps=False,
        verbose=False,
    )
    segments = []
    for segment in result.get("segments", []):
        text = re.sub(r"\s+", " ", str(segment.get("text", ""))).strip()
        if not re.search(r"\w", text, flags=re.UNICODE):
            continue
        confidence = math.exp(min(0.0, float(segment.get("avg_logprob", -20.0))))
        confidence *= 1.0 - min(1.0, max(0.0, float(segment.get("no_speech_prob", 1.0))))
        segments.append((text, confidence))
    transcript = " ".join(text for text, _ in segments).strip()
    return {
        "transcript_nonempty": int(bool(transcript)),
        "transcript_confidence": max((score for _, score in segments), default=0.0),
        "transcript_chars": len(transcript),
        "transcript_sha256": stable_hash(transcript) if transcript else "",
        "segment_count": len(segments),
    }


def _vocal_class_indices(id2label: dict) -> tuple[list[int], list[str]]:
    include = (
        "speech",
        "singing",
        "singer",
        "choir",
        "vocal",
        "rapping",
        "humming",
        "chant",
        "a capella",
        "human voice",
    )
    excluded = ("speech synthesizer",)
    selected = []
    for raw_index, raw_label in id2label.items():
        index = int(raw_index)
        label = str(raw_label)
        lowered = label.lower()
        if any(term in lowered for term in include) and not any(
            term in lowered for term in excluded
        ):
            selected.append((index, label))
    if not selected:
        raise ValueError("AudioSet model exposes no frozen speech/singing classes")
    selected.sort()
    return [item[0] for item in selected], [item[1] for item in selected]


def _audioset_score(model, processor, path: Path, indices: list[int], labels: list[str]) -> dict:
    import librosa
    import numpy as np
    import torch

    audio, _ = librosa.load(str(path), sr=16_000, mono=True)
    window, hop = 160_000, 80_000
    starts = list(range(0, max(1, len(audio) - window + 1), hop)) or [0]
    if starts[-1] + window < len(audio):
        starts.append(max(0, len(audio) - window))
    chunks = [audio[start : start + window] for start in starts]
    best_score, best_class = -1.0, ""
    for offset in range(0, len(chunks), 8):
        inputs = processor(
            chunks[offset : offset + 8],
            sampling_rate=16_000,
            return_tensors="pt",
            padding=True,
        )
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.inference_mode():
            probabilities = torch.sigmoid(model(**inputs).logits).float().cpu().numpy()
        vocal = probabilities[:, indices]
        flat = int(np.argmax(vocal))
        row_index, class_index = np.unravel_index(flat, vocal.shape)
        score = float(vocal[row_index, class_index])
        if score > best_score:
            best_score = score
            best_class = labels[class_index]
    return {
        "audioset_vocal_score": best_score,
        "audioset_top_vocal_class": best_class,
        "windows": len(chunks),
    }


def _directory_manifest(path: Path) -> tuple[str, list[dict]]:
    rows = []
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        rows.append(
            {
                "path": str(item.relative_to(path)),
                "size": item.stat().st_size,
                "sha256": sha256_file(item),
            }
        )
    digest = stable_hash("\n".join(f"{row['sha256']}  {row['path']}" for row in rows))
    return digest, rows


def score_evaluator(backend: str, worker_index: int, num_workers: int, model_path: str) -> dict:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("each evaluator worker requires exactly one visible GPU")
    all_rows = read_csv(EVAL_MEDIA)
    if backend == "detector_fill":
        all_rows = [row for row in all_rows if int(row["needs_detector_fill"])]
    rows = all_rows[worker_index::num_workers]
    ledger = EVAL_LEDGER_DIR / f"evaluator_{backend}_w{worker_index}.jsonl"
    done = _done_score_ids(f"evaluator_{backend}_w*.jsonl")
    if backend == "whisper":
        import whisper

        model = whisper.load_model(
            "large-v3", device="cuda", download_root="/HOME/paratera_xy/pxy1289/.cache/whisper"
        )
        scorer = lambda path: _whisper_score(model, path)
        backend_id = "openai-whisper-large-v3"
    elif backend == "audioset":
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

        local = Path(model_path).resolve()
        if not local.is_dir():
            raise FileNotFoundError(local)
        processor = AutoFeatureExtractor.from_pretrained(str(local), local_files_only=True)
        model = AutoModelForAudioClassification.from_pretrained(
            str(local), local_files_only=True
        ).to("cuda")
        model.eval()
        indices, labels = _vocal_class_indices(model.config.id2label)
        scorer = lambda path: _audioset_score(model, processor, path, indices, labels)
        backend_id = str(local)
        if worker_index == 0:
            manifest_hash, files = _directory_manifest(local)
            write_json_once(
                EVAL_AUDIOSET_META,
                {
                    "model_path": str(local),
                    "directory_manifest_sha256": manifest_hash,
                    "files": files,
                    "vocal_classes": labels,
                    "class_selection": (
                        "AudioSet labels containing speech/singing/singer/choir/vocal/"
                        "rapping/humming/chant/a capella/human voice; speech synthesizer excluded"
                    ),
                    "acquisition": (
                        "ModelScope was attempted first but did not host the MIT checkpoint; "
                        "downloaded from the explicit Hugging Face mirror/proxy fallback."
                    ),
                },
            )
    elif backend == "detector_fill":
        module = _load_w2_instrument_module()
        instrument = module.LiveDemucsPannsEnsembleInstrument(
            "cuda", AND_DEMUCS_THRESHOLD, AND_PANNS_THRESHOLD, "and"
        )

        def scorer(path: Path) -> dict:
            scored = instrument.score(path)
            return {
                "demucs_score": scored["vocal_energy_ratio"],
                "panns_score": scored["panns_score"],
                "demucs_present": scored["demucs_present"],
                "panns_present": scored["panns_present"],
                "present": scored["present"],
                "near_silent": scored["near_silent"],
            }

        backend_id = "frozen-w2-demucs-panns-and"
    else:
        raise ValueError(f"unsupported evaluator backend: {backend}")
    written = failures = 0
    for row in rows:
        if row["media_sha256"] in done:
            continue
        started = time.time()
        record = {
            "status": "FAIL",
            "backend": backend,
            "backend_id": backend_id,
            "media_sha256": row["media_sha256"],
            "clip_path": row["clip_path"],
            "worker_index": worker_index,
            "num_workers": num_workers,
            "host": socket.gethostname(),
            "gpu_id": visible[0],
        }
        try:
            record.update(scorer(Path(row["clip_path"])))
            record["status"] = "PASS"
            written += 1
        except Exception as exc:  # noqa: BLE001
            record["error"] = repr(exc)
            failures += 1
        record["elapsed_s"] = round(time.time() - started, 4)
        append_jsonl(ledger, record)
    if failures:
        raise RuntimeError(f"{backend} worker {worker_index} recorded {failures} failures")
    return {"backend": backend, "worker": worker_index, "written": written, "failures": 0}


def _load_backend_scores(backend: str) -> dict[str, dict]:
    output = {}
    for path in sorted(EVAL_LEDGER_DIR.glob(f"evaluator_{backend}_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                output[row["media_sha256"]] = row
    return output


def _bootstrap_metrics(
    rows: list[dict], predictions: dict[str, list[int]], replicates: int, seed: int
) -> dict[str, dict[str, list[float]]]:
    import numpy as np

    by_prompt: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_prompt[row["prompt_id"]].append(index)
    prompts = sorted(by_prompt)
    rng = np.random.default_rng(seed)
    draws = {
        name: {metric: [] for metric in ("sensitivity", "specificity", "balanced_accuracy", "mcc")}
        for name in predictions
    }
    truth = [int(row["label_binary"]) for row in rows]
    for _ in range(replicates):
        sampled = rng.choice(prompts, size=len(prompts), replace=True)
        indices = [index for prompt in sampled for index in by_prompt[str(prompt)]]
        sampled_truth = [truth[index] for index in indices]
        if len(set(sampled_truth)) < 2:
            continue
        for name, values in predictions.items():
            metrics = binary_metrics(sampled_truth, [values[index] for index in indices])
            for metric in draws[name]:
                draws[name][metric].append(float(metrics[metric]))
    output = {}
    for name, metrics in draws.items():
        output[name] = {}
        for metric, values in metrics.items():
            output[name][metric] = [
                float(np.quantile(values, 0.025)),
                float(np.quantile(values, 0.975)),
            ]
        output[name]["valid_replicates"] = len(metrics["balanced_accuracy"])
    return output


def _metric_cell(point: float, interval: Sequence[float]) -> str:
    return f"{point:.3f} [{interval[0]:.3f}, {interval[1]:.3f}]"


def finalize_evaluator() -> dict:
    rows = read_csv(EVAL_ROWS)
    whisper = _load_backend_scores("whisper")
    audioset = _load_backend_scores("audioset")
    detector_fill = _load_backend_scores("detector_fill")
    media_count = len({row["media_sha256"] for row in rows})
    if len(whisper) != media_count or len(audioset) != media_count:
        raise ValueError(
            f"evaluator scoring incomplete: media={media_count}, whisper={len(whisper)}, "
            f"audioset={len(audioset)}"
        )
    missing_detector_hashes = {
        row["media_sha256"] for row in rows if int(row["needs_detector_fill"])
    }
    if set(detector_fill) != missing_detector_hashes:
        raise ValueError(
            "detector fill incomplete: "
            f"expected={len(missing_detector_hashes)}, observed={len(detector_fill)}"
        )
    for row in rows:
        if int(row["needs_detector_fill"]):
            score = detector_fill[row["media_sha256"]]
            row["demucs_score"] = score["demucs_score"]
            row["panns_score"] = score["panns_score"]
    whisper_rows = [
        {
            "media_sha256": key,
            "transcript_nonempty": value["transcript_nonempty"],
            "transcript_confidence": value["transcript_confidence"],
            "transcript_chars": value["transcript_chars"],
            "transcript_sha256": value["transcript_sha256"],
            "segment_count": value["segment_count"],
            "backend_id": value["backend_id"],
        }
        for key, value in sorted(whisper.items())
    ]
    audioset_rows = [
        {
            "media_sha256": key,
            "audioset_vocal_score": value["audioset_vocal_score"],
            "audioset_top_vocal_class": value["audioset_top_vocal_class"],
            "windows": value["windows"],
            "backend_id": value["backend_id"],
        }
        for key, value in sorted(audioset.items())
    ]
    if not EVAL_WHISPER_CSV.exists():
        write_csv_once(EVAL_WHISPER_CSV, whisper_rows)
    if not EVAL_AUDIOSET_CSV.exists():
        write_csv_once(EVAL_AUDIOSET_CSV, audioset_rows)
    detector_fill_path = EVAL_TABLE.parent / "EVALUATOR_DETECTOR_FILL_SCORES.csv"
    write_csv_once(
        detector_fill_path,
        [
            {
                "media_sha256": key,
                "demucs_score": value["demucs_score"],
                "panns_score": value["panns_score"],
                "demucs_present": value["demucs_present"],
                "panns_present": value["panns_present"],
                "present": value["present"],
                "near_silent": value["near_silent"],
                "backend_id": value["backend_id"],
            }
            for key, value in sorted(detector_fill.items())
        ],
    )
    decided = [row for row in rows if row["label_binary"] != ""]
    train = [row for row in decided if row["split"] == "train"]
    heldout = [row for row in decided if row["split"] == "heldout"]
    train_truth = [int(row["label_binary"]) for row in train]
    panns_selection = select_threshold(
        train_truth, [float(row["panns_score"]) for row in train]
    )
    whisper_selection = select_threshold(
        train_truth,
        [float(whisper[row["media_sha256"]]["transcript_confidence"]) for row in train],
        [bool(int(whisper[row["media_sha256"]]["transcript_nonempty"])) for row in train],
    )
    audioset_selection = select_threshold(
        train_truth,
        [float(audioset[row["media_sha256"]]["audioset_vocal_score"]) for row in train],
    )
    thresholds = {
        "legacy_demucs": LEGACY_DEMUCS_THRESHOLD,
        "demucs_and_panns": [AND_DEMUCS_THRESHOLD, AND_PANNS_THRESHOLD],
        "panns_only": panns_selection["threshold"],
        "whisper_transcript": whisper_selection["threshold"],
        "audioset_tagger": audioset_selection["threshold"],
    }
    predictions = {
        "legacy_demucs": [int(float(row["demucs_score"]) >= LEGACY_DEMUCS_THRESHOLD) for row in heldout],
        "demucs_and_panns": [
            int(
                float(row["demucs_score"]) >= AND_DEMUCS_THRESHOLD
                and float(row["panns_score"]) >= AND_PANNS_THRESHOLD
            )
            for row in heldout
        ],
        "panns_only": [
            int(float(row["panns_score"]) >= panns_selection["threshold"]) for row in heldout
        ],
        "whisper_transcript": [
            int(
                bool(int(whisper[row["media_sha256"]]["transcript_nonempty"]))
                and float(whisper[row["media_sha256"]]["transcript_confidence"])
                >= whisper_selection["threshold"]
            )
            for row in heldout
        ],
        "audioset_tagger": [
            int(
                float(audioset[row["media_sha256"]]["audioset_vocal_score"])
                >= audioset_selection["threshold"]
            )
            for row in heldout
        ],
    }
    truth = [int(row["label_binary"]) for row in heldout]
    metrics = {name: binary_metrics(truth, values) for name, values in predictions.items()}
    intervals = _bootstrap_metrics(
        heldout, predictions, BOOTSTRAP_REPLICATES, EVALUATOR_BOOTSTRAP_SEED
    )
    historical = json.loads(HISTORICAL_CALIBRATION.read_text(encoding="utf-8"))
    historical_by_family = {row["family"]: row for row in historical["candidates"]}
    names = {
        "legacy_demucs": "Legacy Demucs energy ratio",
        "demucs_and_panns": "Demucs AND PANNs",
        "panns_only": "PANNs only",
        "whisper_transcript": "Whisper transcript",
        "audioset_tagger": "AudioSet tagger",
    }
    threshold_labels = {
        "legacy_demucs": f"Demucs >= {LEGACY_DEMUCS_THRESHOLD}",
        "demucs_and_panns": (
            f"Demucs >= {AND_DEMUCS_THRESHOLD:.10f} AND PANNs >= {AND_PANNS_THRESHOLD:.10f}"
        ),
        "panns_only": f"PANNs >= {panns_selection['threshold']:.8f} (train-selected)",
        "whisper_transcript": (
            f"non-empty AND confidence >= {whisper_selection['threshold']:.8f} (train-selected)"
        ),
        "audioset_tagger": (
            f"speech/singing max >= {audioset_selection['threshold']:.8f} (train-selected)"
        ),
    }
    lines = [
        "# Exit-1 Evaluator Comparison",
        "",
        "The common comparison uses the provenance-enforced 690-row Label-A instrument "
        f"({len(train)} decided train rows; {len(heldout)} decided held-out rows; "
        f"{len(rows) - len(decided)} unsure row excluded from metric denominators). "
        "Prompt clusters and duplicate media are disjoint across the deterministic split. "
        "Only PANNs-only, Whisper, and AudioSet thresholds were selected on train; the two "
        "existing Demucs operationalizations were applied unchanged.",
        f"Historical detector scores were preserved; {len(missing_detector_hashes)} unique "
        "media item(s) without a historical score were evaluated by the unchanged frozen W2 "
        "Demucs/PANNs backend. This supplemental scoring introduced no human labels.",
        "",
        "| Instrument | Frozen operationalization | Sensitivity (95% CI) | Specificity (95% CI) | Balanced accuracy (95% CI) | MCC (95% CI) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for key in names:
        point = metrics[key]
        ci = intervals[key]
        lines.append(
            f"| {names[key]} | {threshold_labels[key]} | "
            f"{_metric_cell(point['sensitivity'], ci['sensitivity'])} | "
            f"{_metric_cell(point['specificity'], ci['specificity'])} | "
            f"{_metric_cell(point['balanced_accuracy'], ci['balanced_accuracy'])} | "
            f"{_metric_cell(point['mcc'], ci['mcc'])} |"
        )
    legacy_hist = historical_by_family["current_demucs"]["heldout_metrics"]
    and_hist = historical_by_family["and"]["heldout_metrics"]
    lines.extend(
        [
            "",
            "## Locked historical restatement",
            "",
            "The earlier 105-row PI-gold held-out record is restated, not re-tuned: legacy "
            f"Demucs sensitivity/specificity/balanced accuracy/MCC = {legacy_hist['sensitivity']:.6f}/"
            f"{legacy_hist['specificity']:.6f}/{legacy_hist['balanced_accuracy']:.6f}/"
            f"{legacy_hist['mcc']:.6f}; Demucs AND PANNs = {and_hist['sensitivity']:.6f}/"
            f"{and_hist['specificity']:.6f}/{and_hist['balanced_accuracy']:.6f}/"
            f"{and_hist['mcc']:.6f}.",
            "",
            "## Inference and uncertainty",
            "",
            "Whisper is the checksum-frozen `large-v3` model. A transcript counts only when "
            "at least one alphanumeric segment is non-empty and the maximum segment "
            "`exp(avg_logprob) * (1 - no_speech_prob)` clears the train-selected floor. "
            "The AudioSet row uses a separate AST-family audio classifier and the maximum "
            "probability across frozen speech/singing-class tags and overlapping windows. "
            f"All intervals are percentile 95% prompt-cluster bootstraps with "
            f"{BOOTSTRAP_REPLICATES:,} replicates and seed `{EVALUATOR_BOOTSTRAP_SEED}`.",
            "",
            "No new human labels were collected. The gold contains 190 `pi:Richard` rows "
            "and 500 rows from the provenance-enforced, disjoint-gold-validated judge instrument.",
        ]
    )
    _write_once(EVAL_TABLE, "\n".join(lines) + "\n")
    result = {
        "status": "COMPLETE",
        "nominal_rows": len(rows),
        "decided_rows": len(decided),
        "train_rows": len(train),
        "heldout_rows": len(heldout),
        "thresholds": thresholds,
        "train_selection": {
            "panns_only": panns_selection,
            "whisper_transcript": whisper_selection,
            "audioset_tagger": audioset_selection,
        },
        "heldout_metrics": metrics,
        "heldout_prompt_cluster_bootstrap_ci95": intervals,
        "bootstrap_seed": EVALUATOR_BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "new_human_labels": 0,
        "historical_detector_media_filled": len(missing_detector_hashes),
        "detector_fill_artifact": str(detector_fill_path.relative_to(ROOT)),
        "historical_restatement": {
            "legacy_demucs": legacy_hist,
            "demucs_and_panns": and_hist,
        },
    }
    write_json_once(EVAL_AUDIT, result)
    return result


def select_attempt(candidates: Sequence[dict]) -> dict:
    if not candidates:
        raise ValueError("selection requires at least one candidate")
    return max(
        candidates,
        key=lambda row: (
            1 - int(row["violation"]),
            float(row["quality_score"]),
            -int(row.get("attempt_index", 0)),
        ),
    )


def _cluster_rate_ci(rows: list[dict], field: str, seed: int) -> tuple[float, float, float]:
    import numpy as np

    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[row["prompt_id"]].append(float(row[field]))
    prompts = sorted(by_prompt)
    point = float(np.mean([value for values in by_prompt.values() for value in values]))
    rng = np.random.default_rng(seed)
    draws = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for index in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(prompts, size=len(prompts), replace=True)
        values = [value for prompt in sampled for value in by_prompt[str(prompt)]]
        draws[index] = float(np.mean(values))
    return point, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def _paired_delta_ci(
    treatment: list[dict], baseline: list[dict], field: str, seed: int
) -> tuple[float, float, float]:
    import numpy as np

    left = {row["prompt_id"]: float(row[field]) for row in treatment}
    right = {row["prompt_id"]: float(row[field]) for row in baseline}
    if set(left) != set(right):
        raise ValueError("paired recipe comparison prompt sets differ")
    prompts = sorted(left)
    differences = {prompt: left[prompt] - right[prompt] for prompt in prompts}
    point = float(np.mean(list(differences.values())))
    rng = np.random.default_rng(seed)
    draws = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for index in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(prompts, size=len(prompts), replace=True)
        draws[index] = float(np.mean([differences[str(prompt)] for prompt in sampled]))
    return point, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def build_recipe_curves() -> dict:
    import numpy as np

    factorial = read_csv(FACTORIAL_SCORES)
    secondary = {}
    for path in sorted(FACTORIAL_SECONDARY.glob("secondary_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                secondary[row["task_id"]] = row
    if len(factorial) != 3072 or len(secondary) != 3072:
        raise ValueError(
            f"factorial/secondary cardinality changed: {len(factorial)}/{len(secondary)}"
        )
    live_raw = [
        row for path in sorted(LIVE_LEDGERS.glob("live_w*.jsonl")) for row in read_jsonl(path)
    ]
    deduplicated = {}
    for row in live_raw:
        key = (row["unit_id"], row["record_type"], str(row.get("slot", "")))
        if key in deduplicated and deduplicated[key] != row:
            raise ValueError(f"conflicting live-confirmation duplicate {key}")
        deduplicated[key] = row
    live_slots = [
        row
        for row in deduplicated.values()
        if row["record_type"] == "slot"
        and row.get("status") == "COMPLETE"
        and row.get("final_common_robust_lcb") is not None
    ]
    x = np.asarray(
        [
            [
                1.0,
                float(row["final_scores"]["semantic_fit"]),
                float(row["final_scores"]["aesthetic_pq"]),
            ]
            for row in live_slots
        ],
        dtype=np.float64,
    )
    y = np.asarray([float(row["final_common_robust_lcb"]) for row in live_slots])
    coefficients, *_ = np.linalg.lstsq(x, y, rcond=None)
    predicted = x @ coefficients
    r2 = 1.0 - float(np.sum((y - predicted) ** 2) / np.sum((y - y.mean()) ** 2))
    floor_source = [
        float(row["final_common_robust_lcb"])
        for row in live_slots
        if row["policy"] == "no_probe_reseed" and int(row["label_b_satisfied"]) == 1
    ]
    if not floor_source:
        raise ValueError("live baseline has no constraint-satisfying quality-floor rows")
    quality_floor = float(np.quantile(floor_source, 0.25))
    prepared = []
    for row in factorial:
        quality = secondary.get(row["task_id"])
        if quality is None:
            raise ValueError(f"missing secondary score {row['task_id']}")
        proxy = float(
            coefficients[0]
            + coefficients[1] * float(quality["clap_prompt_similarity"])
            + coefficients[2] * float(quality["aesthetic_pq"])
        )
        prepared.append(
            {
                **row,
                "attempt_index": int(row["seed_idx"]),
                "violation": int(row["corrected_violation"]),
                "quality_score": proxy,
            }
        )
    by_condition_prompt: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in prepared:
        by_condition_prompt[(row["condition"], row["prompt_id"])].append(row)
    for values in by_condition_prompt.values():
        values.sort(key=lambda row: row["attempt_index"])
    recipes = {
        "plain_baseline+selection": "plain_baseline",
        "positive_text+selection": "positive_text",
        "positive_sampler+selection": "positive_sampler",
    }
    outcomes: dict[tuple[str, int], list[dict]] = {}
    figure_rows = []
    for n in (1, 2, 4, 8):
        for recipe, condition in recipes.items():
            selected_rows = []
            prompts = sorted(
                prompt for cond, prompt in by_condition_prompt if cond == condition
            )
            for prompt in prompts:
                candidates = by_condition_prompt[(condition, prompt)][:n]
                if len(candidates) != n:
                    raise ValueError(f"{condition}/{prompt} lacks N={n} attempts")
                selected = select_attempt(candidates)
                selected_rows.append(
                    {
                        "prompt_id": prompt,
                        "violation": int(selected["violation"]),
                        "cqs_success": int(
                            not int(selected["violation"])
                            and float(selected["quality_score"]) >= quality_floor
                        ),
                    }
                )
            outcomes[(recipe, n)] = selected_rows
            violation = _cluster_rate_ci(
                selected_rows, "violation", RECIPE_BOOTSTRAP_SEED + n
            )
            cqs = _cluster_rate_ci(
                selected_rows, "cqs_success", RECIPE_BOOTSTRAP_SEED + 100 + n
            )
            figure_rows.append(
                {
                    "source": "factorial",
                    "recipe": recipe,
                    "attempts_N": n,
                    "prompt_clusters": len(selected_rows),
                    "units": len(selected_rows),
                    "violation_rate": violation[0],
                    "violation_ci95_low": violation[1],
                    "violation_ci95_high": violation[2],
                    "cqs_style_success": cqs[0],
                    "cqs_ci95_low": cqs[1],
                    "cqs_ci95_high": cqs[2],
                    "quality_floor": quality_floor,
                    "violation_delta_vs_equal_compute_baseline": 0.0 if condition == "plain_baseline" else "",
                    "violation_delta_ci95_low": 0.0 if condition == "plain_baseline" else "",
                    "violation_delta_ci95_high": 0.0 if condition == "plain_baseline" else "",
                    "cqs_delta_vs_equal_compute_baseline": 0.0 if condition == "plain_baseline" else "",
                    "cqs_delta_ci95_low": 0.0 if condition == "plain_baseline" else "",
                    "cqs_delta_ci95_high": 0.0 if condition == "plain_baseline" else "",
                }
            )
        baseline = outcomes[("plain_baseline+selection", n)]
        for recipe in ("positive_text+selection", "positive_sampler+selection"):
            violation_delta = _paired_delta_ci(
                outcomes[(recipe, n)], baseline, "violation", RECIPE_BOOTSTRAP_SEED + 200 + n
            )
            cqs_delta = _paired_delta_ci(
                outcomes[(recipe, n)], baseline, "cqs_success", RECIPE_BOOTSTRAP_SEED + 300 + n
            )
            row = next(
                item
                for item in figure_rows
                if item["source"] == "factorial"
                and item["recipe"] == recipe
                and item["attempts_N"] == n
            )
            row.update(
                {
                    "violation_delta_vs_equal_compute_baseline": violation_delta[0],
                    "violation_delta_ci95_low": violation_delta[1],
                    "violation_delta_ci95_high": violation_delta[2],
                    "cqs_delta_vs_equal_compute_baseline": cqs_delta[0],
                    "cqs_delta_ci95_low": cqs_delta[1],
                    "cqs_delta_ci95_high": cqs_delta[2],
                }
            )
    live_slot_index = {
        (row["unit_id"], int(row["slot"])): row for row in live_slots
    }
    live_selections = [
        row
        for row in deduplicated.values()
        if row["record_type"] == "unit_selection"
        and row.get("status") == "COMPLETE"
        and row.get("requested_vocal") == "0"
        and row["policy"] in {"no_probe_reseed", "always_direction_condition"}
    ]
    live_recipes = {
        "no_probe_reseed": "plain_baseline+selection",
        "always_direction_condition": "positive_sampler+selection",
    }
    for policy, recipe in live_recipes.items():
        selected_rows = []
        for selection in live_selections:
            if selection["policy"] != policy:
                continue
            slot = live_slot_index[(selection["unit_id"], int(selection["selected_slot"]))]
            selected_rows.append(
                {
                    "prompt_id": selection["prompt_id"],
                    "violation": 1 - int(selection["selected_label_b_satisfied"]),
                    "cqs_success": int(
                        int(selection["selected_label_b_satisfied"]) == 1
                        and float(slot["final_common_robust_lcb"]) >= quality_floor
                    ),
                }
            )
        violation = _cluster_rate_ci(
            selected_rows, "violation", RECIPE_BOOTSTRAP_SEED + 402
        )
        cqs = _cluster_rate_ci(
            selected_rows, "cqs_success", RECIPE_BOOTSTRAP_SEED + 502
        )
        figure_rows.append(
            {
                "source": "live_confirmation",
                "recipe": recipe,
                "attempts_N": 2,
                "prompt_clusters": len({row["prompt_id"] for row in selected_rows}),
                "units": len(selected_rows),
                "violation_rate": violation[0],
                "violation_ci95_low": violation[1],
                "violation_ci95_high": violation[2],
                "cqs_style_success": cqs[0],
                "cqs_ci95_low": cqs[1],
                "cqs_ci95_high": cqs[2],
                "quality_floor": quality_floor,
                "violation_delta_vs_equal_compute_baseline": "",
                "violation_delta_ci95_low": "",
                "violation_delta_ci95_high": "",
                "cqs_delta_vs_equal_compute_baseline": "",
                "cqs_delta_ci95_low": "",
                "cqs_delta_ci95_high": "",
            }
        )
    best = max(
        (
            row
            for row in figure_rows
            if row["source"] == "factorial" and row["recipe"] != "plain_baseline+selection"
        ),
        key=lambda row: (
            float(row["cqs_style_success"]),
            -float(row["violation_rate"]),
            -int(row["attempts_N"]),
            row["recipe"],
        ),
    )
    write_csv_once(RECIPE_CSV, figure_rows)
    lines = [
        "# Exit-1 Deployable Recipe Curves",
        "",
        "The frozen factorial contributes 32 prompt clusters with 16 common-random-number "
        "attempts per condition. Selection follows the live worker: promoted-gate "
        "satisfaction first, then quality. The CQS-style quality proxy maps factorial CLAP "
        "semantic fit and Audiobox PQ onto live-confirmation robust LCB; its floor is the "
        "lower quartile of constraint-satisfying `no_probe_reseed` live slots.",
        "",
        "| Source | Recipe | N | Violation rate (95% CI) | CQS-style success (95% CI) | Violation delta vs matched baseline | CQS delta vs matched baseline |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in figure_rows:
        violation_delta = row["violation_delta_vs_equal_compute_baseline"]
        cqs_delta = row["cqs_delta_vs_equal_compute_baseline"]
        violation_delta_text = (
            "NA"
            if violation_delta == ""
            else f"{float(violation_delta):+.3f} [{float(row['violation_delta_ci95_low']):+.3f}, {float(row['violation_delta_ci95_high']):+.3f}]"
        )
        cqs_delta_text = (
            "NA"
            if cqs_delta == ""
            else f"{float(cqs_delta):+.3f} [{float(row['cqs_delta_ci95_low']):+.3f}, {float(row['cqs_delta_ci95_high']):+.3f}]"
        )
        lines.append(
            f"| {row['source']} | `{row['recipe']}` | {row['attempts_N']} | "
            f"{float(row['violation_rate']):.3f} [{float(row['violation_ci95_low']):.3f}, {float(row['violation_ci95_high']):.3f}] | "
            f"{float(row['cqs_style_success']):.3f} [{float(row['cqs_ci95_low']):.3f}, {float(row['cqs_ci95_high']):.3f}] | "
            f"{violation_delta_text} | {cqs_delta_text} |"
        )
    lines.extend(
        [
            "",
            "## Quality proxy and uncertainty",
            "",
            f"Proxy formula: robust-LCB = `{coefficients[0]:.6f} + {coefficients[1]:.6f} * CLAP + "
            f"{coefficients[2]:.6f} * Audiobox_PQ`; in-sample live-slot R2 = `{r2:.6f}`; "
            f"frozen quality floor = `{quality_floor:.6f}`. This is explicitly CQS-style, "
            "not a replacement for the seven-axis robust-LCB evaluator.",
            "",
            f"Intervals use {BOOTSTRAP_REPLICATES:,} prompt-cluster replicates with seed "
            f"`{RECIPE_BOOTSTRAP_SEED}`. Factorial treatment deltas are prompt-paired and "
            "compare with `plain_baseline+selection` at the same N and therefore equal generation compute.",
            "",
            f"Best deployable operating point: `{best['recipe']}` at N={best['attempts_N']} "
            f"({float(best['violation_rate']):.3f} violation; {float(best['cqs_style_success']):.3f} CQS-style success).",
        ]
    )
    _write_once(RECIPE_REPORT, "\n".join(lines) + "\n")
    result = {
        "status": "COMPLETE",
        "factorial_rows": len(factorial),
        "factorial_secondary_rows": len(secondary),
        "live_raw_rows": len(live_raw),
        "live_deduplicated_rows": len(deduplicated),
        "quality_proxy": {
            "intercept": float(coefficients[0]),
            "clap_coefficient": float(coefficients[1]),
            "audiobox_pq_coefficient": float(coefficients[2]),
            "r_squared": r2,
            "floor": quality_floor,
            "floor_rule": (
                "25th percentile of constraint-satisfying no_probe_reseed live slots"
            ),
        },
        "bootstrap_seed": RECIPE_BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "best_operating_point": best,
        "source_sha256": {
            str(FACTORIAL_SCORES.relative_to(ROOT)): sha256_file(FACTORIAL_SCORES),
        },
    }
    write_json_once(RECIPE_AUDIT, result)
    return result


def build_unconditional_tasks(prompt_rows: Sequence[dict], seed_base: int) -> list[dict]:
    tasks = []
    for prompt in prompt_rows:
        replicates = int(prompt["replicates"])
        for replicate in range(replicates):
            index = len(tasks)
            seed = seed_base + index
            clip_id = f"exit1_uncond_{index:03d}"
            tasks.append(
                {
                    "clip_id": clip_id,
                    "manifest_index": index,
                    "prompt_id": prompt["prompt_id"],
                    "stratum": prompt["stratum"],
                    "prompt_text": prompt["prompt_text"],
                    "replicate": replicate,
                    "seed": seed,
                    "output_path": str(
                        Path("analysis_exit1/unconditional_run_20260716/audio")
                        / prompt["prompt_id"]
                        / f"{clip_id}_seed{seed}.flac"
                    ),
                }
            )
    return tasks


def prepare_unconditional() -> dict:
    prompts = read_csv(NEUTRAL_PROMPTS)
    prereg = json.loads(UNCONDITIONAL_PREREG.read_text(encoding="utf-8"))
    if prereg.get("status") != "FROZEN_BEFORE_GENERATION":
        raise ValueError("unconditional preregistration is not frozen")
    if len(prompts) != 16 or Counter(row["stratum"] for row in prompts) != Counter(
        {"empty": 8, "neutral_text": 8}
    ):
        raise ValueError("neutral prompt list must contain eight empty and eight text prompts")
    if any(int(row["replicates"]) != 16 for row in prompts):
        raise ValueError("every frozen neutral prompt must have 16 replicates")
    forbidden = re.compile(r"\b(vocal|voice|sing|singer|choir|rap|speech)\b", re.I)
    if any(forbidden.search(row["prompt_text"]) for row in prompts):
        raise ValueError("neutral prompt list contains a vocal-direction lexeme")
    tasks = build_unconditional_tasks(prompts, UNCONDITIONAL_SEED_BASE)
    if len(tasks) != 256 or int(tasks[-1]["seed"]) != 2_036_000_255:
        raise ValueError("unconditional task/seed cardinality mismatch")
    config_hash = stable_hash(
        sha256_file(NEUTRAL_PROMPTS) + sha256_file(UNCONDITIONAL_PREREG)
    )
    write_csv_once(UNCONDITIONAL_MANIFEST, tasks)
    result = {
        "status": "FROZEN_INPUTS_READY",
        "tasks": len(tasks),
        "prompt_rows": len(prompts),
        "stratum_counts": dict(Counter(row["stratum"] for row in tasks)),
        "seed_min": int(tasks[0]["seed"]),
        "seed_max": int(tasks[-1]["seed"]),
        "config_hash": config_hash,
        "prompt_sha256": sha256_file(NEUTRAL_PROMPTS),
        "preregistration_sha256": sha256_file(UNCONDITIONAL_PREREG),
        "git_hash_before_generation": git_hash(),
        "generation_started": False,
    }
    write_json_once(UNCONDITIONAL_PREP_AUDIT, result)
    return result


def _load_w2_instrument_module():
    scripts = PAPER / "scripts"
    contingency = PAPER / "w2_contingency_20260711"
    for value in (ROOT / "src", scripts, contingency):
        sys.path.insert(0, str(value))
    path = contingency / "w2_instruments.py"
    spec = importlib.util.spec_from_file_location("exit1_w2_instruments", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen W2 instruments")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_unconditional(worker_index: int, num_workers: int) -> dict:
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index outside shard range")
    if num_workers != 8:
        raise ValueError("frozen unconditional run requires eight TP1 replicas")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("each unconditional worker requires exactly one visible GPU")
    import soundfile as sf
    from mprm.common.seeding import seed_everything
    from mprm.data.prompts import Prompt
    from mprm.inference.ace_step import AceStepModel

    prep = json.loads(UNCONDITIONAL_PREP_AUDIT.read_text(encoding="utf-8"))
    tasks = read_csv(UNCONDITIONAL_MANIFEST)[worker_index::num_workers]
    done = set()
    for path in sorted(UNCONDITIONAL_LEDGER_DIR.glob("generation_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                done.add(row["clip_id"])
    ledger = UNCONDITIONAL_LEDGER_DIR / f"generation_w{worker_index}.jsonl"
    model = AceStepModel(device="cuda", dtype="bfloat16")
    module = _load_w2_instrument_module()
    instrument = module.LiveDemucsPannsEnsembleInstrument(
        "cuda", AND_DEMUCS_THRESHOLD, AND_PANNS_THRESHOLD, "and"
    )
    extras = {
        "cfg_type": "apg",
        "guidance_interval": 0.5,
        "use_erg_tag": False,
        "use_erg_lyric": False,
        "use_erg_diffusion": False,
    }
    written = failures = recovered = 0
    for task in tasks:
        if task["clip_id"] in done:
            continue
        started = time.time()
        path = ROOT / task["output_path"]
        record = {
            **task,
            "status": "FAIL",
            "node": socket.gethostname(),
            "gpu_id": visible[0],
            "tp_width": 1,
            "replica_count": num_workers,
            "worker_index": worker_index,
            "config_hash": prep["config_hash"],
            "git_hash": git_hash(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            was_recovered = path.exists()
            if not was_recovered:
                prompt = Prompt(
                    prompt_id=task["prompt_id"],
                    text=task["prompt_text"],
                    lyrics=None,
                    structure_hint=None,
                    duration_target=15.0,
                    metadata={"exit1_role": "unconditional_base_rate"},
                    strata={"prompt_type": task["stratum"]},
                )
                seed = int(task["seed"])
                seed_everything(seed)
                result = model.sample(
                    prompt,
                    seed=seed,
                    cfg_scale=5.0,
                    steps=30,
                    return_trajectory=False,
                    extras=extras,
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                samples = result.waveform.detach().cpu().numpy().T
                sf.write(str(path), samples, result.sample_rate, format="FLAC")
            samples, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
            if len(samples) / sample_rate <= 1.0:
                raise RuntimeError("generated audio is too short")
            scored = instrument.score(path)
            record.update(
                {
                    "status": "PASS",
                    "audio_sha256": sha256_file(path),
                    "sample_rate": sample_rate,
                    "duration_seconds": len(samples) / sample_rate,
                    "demucs_score": scored["vocal_energy_ratio"],
                    "panns_score": scored["panns_score"],
                    "demucs_present": scored["demucs_present"],
                    "panns_present": scored["panns_present"],
                    "present": scored["present"],
                    "near_silent": scored["near_silent"],
                    "instrument_id": scored["instrument_id"],
                    "decision_rule": scored["decision_rule"],
                    "recovered_existing_audio": was_recovered,
                }
            )
            written += 1
            recovered += int(was_recovered)
        except Exception as exc:  # noqa: BLE001
            record["error"] = repr(exc)
            failures += 1
        record["elapsed_s"] = round(time.time() - started, 3)
        append_jsonl(ledger, record)
    if failures:
        raise RuntimeError(f"unconditional worker {worker_index} recorded {failures} failures")
    return {
        "worker": worker_index,
        "written": written,
        "recovered": recovered,
        "failures": 0,
    }


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("invalid Wilson interval counts")
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
    radius /= denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def finalize_unconditional() -> dict:
    manifest = read_csv(UNCONDITIONAL_MANIFEST)
    latest = {}
    raw_rows = 0
    for path in sorted(UNCONDITIONAL_LEDGER_DIR.glob("generation_w*.jsonl")):
        for row in read_jsonl(path):
            raw_rows += 1
            latest[row["clip_id"]] = row
    expected = {row["clip_id"] for row in manifest}
    passed = {key: row for key, row in latest.items() if row.get("status") == "PASS"}
    if set(passed) != expected:
        raise ValueError(
            f"unconditional run incomplete: expected={len(expected)} passed={len(passed)}"
        )
    generation_hashes = {row["git_hash"] for row in passed.values()}
    if len(generation_hashes) != 1:
        raise ValueError(f"unconditional generation used multiple git hashes: {generation_hashes}")
    generation_git_hash = next(iter(generation_hashes))
    scores = []
    checksum_lines = []
    for task in manifest:
        row = passed[task["clip_id"]]
        path = ROOT / task["output_path"]
        observed = sha256_file(path)
        if observed != row["audio_sha256"]:
            raise ValueError(f"unconditional audio checksum mismatch: {task['clip_id']}")
        checksum_lines.append(f"{observed}  {task['output_path']}")
        scores.append(
            {
                **task,
                "audio_sha256": observed,
                "sample_rate": row["sample_rate"],
                "duration_seconds": row["duration_seconds"],
                "demucs_score": row["demucs_score"],
                "panns_score": row["panns_score"],
                "demucs_present": row["demucs_present"],
                "panns_present": row["panns_present"],
                "present": row["present"],
                "near_silent": row["near_silent"],
                "instrument_id": row["instrument_id"],
                "node": row["node"],
                "gpu_id": row["gpu_id"],
            }
        )
    write_csv_once(UNCONDITIONAL_SCORES, scores)
    _write_once(UNCONDITIONAL_SHA, "\n".join(checksum_lines) + "\n")
    summaries = []
    groups = [("overall", "all", scores)]
    for stratum in sorted({row["stratum"] for row in scores}):
        groups.append(("stratum", stratum, [row for row in scores if row["stratum"] == stratum]))
    for prompt_id in sorted({row["prompt_id"] for row in scores}):
        groups.append(("prompt", prompt_id, [row for row in scores if row["prompt_id"] == prompt_id]))
    for group, value, rows in groups:
        count = sum(int(row["present"]) for row in rows)
        low, high = wilson_interval(count, len(rows))
        summaries.append(
            {
                "group": group,
                "value": value,
                "n": len(rows),
                "vocal_present": count,
                "rate": count / len(rows),
                "ci95_low": low,
                "ci95_high": high,
            }
        )
    overall = summaries[0]
    lines = [
        "# Exit-1 Unconditional Base Rate",
        "",
        "Evidence role: PRIOR EVIDENCE",
        "",
        "This analysis estimates vocal presence under the preregistered empty and neutral "
        "prompt distribution. It is PRIOR EVIDENCE for the vocal-bias discussion and is "
        "not causal proof of vocal bias.",
        "",
        f"Overall, the promoted Demucs AND PANNs instrument marked {overall['vocal_present']}/"
        f"{overall['n']} clips as voice-present: {overall['rate']:.4f} "
        f"(Wilson 95% CI [{overall['ci95_low']:.4f}, {overall['ci95_high']:.4f}]).",
        "",
        "| Natural stratum | n | Voice-present | Rate | Wilson 95% CI |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summaries:
        if row["group"] != "stratum":
            continue
        lines.append(
            f"| `{row['value']}` | {row['n']} | {row['vocal_present']} | "
            f"{row['rate']:.4f} | [{row['ci95_low']:.4f}, {row['ci95_high']:.4f}] |"
        )
    lines.extend(
        [
            "",
            "## Frozen execution",
            "",
            "- 256 retained 15-second clips: 128 empty-prompt and 128 neutral-text outputs.",
            f"- Seeds: `{UNCONDITIONAL_SEED_BASE}` through `{UNCONDITIONAL_SEED_BASE + 255}`.",
            "- Placement: `an12`, GPUs 0-7, TP1, eight independent replicas.",
            f"- Instrument: Demucs >= `{AND_DEMUCS_THRESHOLD:.10f}` AND PANNs >= "
            f"`{AND_PANNS_THRESHOLD:.10f}`.",
            "- All audio paths and SHA-256 values are retained in the tracked manifest and checksum file.",
            "",
            "Prompt-level rows remain available in `UNCONDITIONAL_SCORES.csv`; the table "
            "above limits subgroup claims to the two preregistered natural strata.",
        ]
    )
    _write_once(UNCONDITIONAL_REPORT, "\n".join(lines) + "\n")
    prep = json.loads(UNCONDITIONAL_PREP_AUDIT.read_text(encoding="utf-8"))
    run_manifest = {
        "status": "COMPLETE",
        "evidence_role": "PRIOR EVIDENCE",
        "node": "an12",
        "gpu_ids": list(range(8)),
        "tp_width": 1,
        "replica_count": 8,
        "placement_justification": (
            "ACE-Step 3.5B fits on one A800; eight independent TP1 replicas maximize throughput."
        ),
        "command": (
            "CUDA_VISIBLE_DEVICES=<0..7> python analysis_exit1/exit1_analysis.py "
            "run-unconditional --worker-index <0..7> --num-workers 8"
        ),
        "git_hash_before_generation": generation_git_hash,
        "config_hash": prep["config_hash"],
        "seed_base": UNCONDITIONAL_SEED_BASE,
        "seed_max": UNCONDITIONAL_SEED_BASE + 255,
        "artifact_path": str(UNCONDITIONAL_RUN.relative_to(ROOT)),
        "audio_count": len(scores),
        "raw_ledger_rows": raw_rows,
        "deviations": [],
        "instrument": {
            "decision_rule": "and",
            "demucs_threshold": AND_DEMUCS_THRESHOLD,
            "panns_threshold": AND_PANNS_THRESHOLD,
        },
        "overall": overall,
        "strata": [row for row in summaries if row["group"] == "stratum"],
    }
    write_json_once(UNCONDITIONAL_RUN_MANIFEST, run_manifest)
    return run_manifest


def record_tests(exit_code: int, command: str) -> dict:
    if not TEST_RESULTS.is_file():
        raise FileNotFoundError(TEST_RESULTS)
    text = TEST_RESULTS.read_text(encoding="utf-8", errors="replace")
    passed_matches = [int(value) for value in re.findall(r"(\d+) passed", text)]
    failed_matches = [int(value) for value in re.findall(r"(\d+) failed", text)]
    error_matches = [int(value) for value in re.findall(r"(\d+) errors?", text)]
    result = {
        "status": "PASS" if exit_code == 0 and not failed_matches and not error_matches else "FAIL",
        "exit_code": exit_code,
        "command": command,
        "passed": passed_matches[-1] if passed_matches else None,
        "failed": failed_matches[-1] if failed_matches else 0,
        "errors": error_matches[-1] if error_matches else 0,
        "output_sha256": sha256_file(TEST_RESULTS),
        "git_hash": git_hash(),
        "node": socket.gethostname(),
    }
    if result["status"] != "PASS":
        raise RuntimeError(f"test suite did not pass: {result}")
    write_json_once(TEST_SUMMARY, result)
    return result


def write_bundle_report(prereg_commit: str, analysis_commit: str) -> dict:
    required = {
        "EVALUATOR_TABLE_STATUS": [
            EVAL_TABLE,
            EVAL_AUDIT,
            EVAL_PREP_AUDIT,
            EVAL_MEDIA,
            EVAL_WHISPER_CSV,
            EVAL_AUDIOSET_CSV,
            EVAL_AUDIOSET_META,
            EVAL_TABLE.parent / "EVALUATOR_DETECTOR_FILL_SCORES.csv",
        ],
        "RECIPE_CURVES_STATUS": [RECIPE_REPORT, RECIPE_CSV, RECIPE_AUDIT],
        "UNCONDITIONAL_BASE_RATE_STATUS": [
            UNCONDITIONAL_REPORT,
            ROOT / "analysis_exit1/neutral_prompts.csv",
            ROOT / "analysis_exit1/UNCONDITIONAL_PREREGISTRATION.json",
            UNCONDITIONAL_MANIFEST,
            UNCONDITIONAL_SCORES,
            UNCONDITIONAL_SHA,
            UNCONDITIONAL_RUN_MANIFEST,
        ],
        "TEST_SUITE_STATUS": [TEST_RESULTS, TEST_SUMMARY],
    }
    missing = [str(path) for paths in required.values() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Exit-1 evidence paths missing: {missing}")
    test = json.loads(TEST_SUMMARY.read_text(encoding="utf-8"))
    if test.get("status") != "PASS" or test.get("exit_code") != 0:
        raise ValueError("cannot issue bundle report without passing full suite")
    untracked = []
    for paths in required.values():
        for path in paths:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode:
                untracked.append(str(path.relative_to(ROOT)))
    if untracked:
        raise ValueError(f"bundle evidence is not tracked: {untracked}")
    lines = ["# Exit-1 Analysis Bundle Report", ""]
    for status, paths in required.items():
        value = "PASS" if status == "TEST_SUITE_STATUS" else "COMPLETE"
        lines.append(f"{status} = {value}")
        lines.append(
            "evidence: "
            + "; ".join(f"`{path.relative_to(ROOT)}`" for path in paths)
        )
        lines.append("")
    lines.extend(
        [
            "## Commits",
            "",
            f"- Frozen prompt/seed preregistration commit: `{prereg_commit}`.",
            f"- Analysis, retained-audio evidence, and test-results commit: `{analysis_commit}`.",
            "",
            "## Test result",
            "",
            f"- Command: `{test['command']}`.",
            f"- Exit code: `{test['exit_code']}`.",
            f"- Passed: `{test['passed']}`; failed: `{test['failed']}`; errors: `{test['errors']}`.",
            f"- Output SHA-256: `{test['output_sha256']}`.",
            "",
            "## Scope",
            "",
            "This is an Exit-1 analysis bundle. It does not change PLAN/CLAIMS or gate semantics. "
            "The unconditional estimate is labeled PRIOR EVIDENCE and is not causal proof.",
        ]
    )
    _write_once(BUNDLE_REPORT, "\n".join(lines) + "\n")
    return {"status": "COMPLETE", "report": str(BUNDLE_REPORT.relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare-evaluator")
    score = sub.add_parser("score-evaluator")
    score.add_argument(
        "--backend", choices=("whisper", "audioset", "detector_fill"), required=True
    )
    score.add_argument("--worker-index", type=int, required=True)
    score.add_argument("--num-workers", type=int, required=True)
    score.add_argument("--model-path", default="")
    sub.add_parser("finalize-evaluator")
    sub.add_parser("build-recipe-curves")
    sub.add_parser("prepare-unconditional")
    run = sub.add_parser("run-unconditional")
    run.add_argument("--worker-index", type=int, required=True)
    run.add_argument("--num-workers", type=int, required=True)
    tests = sub.add_parser("record-tests")
    tests.add_argument("--exit-code", type=int, required=True)
    tests.add_argument("--test-command", required=True)
    sub.add_parser("finalize-unconditional")
    bundle = sub.add_parser("write-bundle-report")
    bundle.add_argument("--prereg-commit", required=True)
    bundle.add_argument("--analysis-commit", required=True)
    args = parser.parse_args()
    if args.command == "prepare-evaluator":
        result = prepare_evaluator()
    elif args.command == "score-evaluator":
        result = score_evaluator(
            args.backend, args.worker_index, args.num_workers, args.model_path
        )
    elif args.command == "finalize-evaluator":
        result = finalize_evaluator()
    elif args.command == "build-recipe-curves":
        result = build_recipe_curves()
    elif args.command == "prepare-unconditional":
        result = prepare_unconditional()
    elif args.command == "run-unconditional":
        result = run_unconditional(args.worker_index, args.num_workers)
    elif args.command == "finalize-unconditional":
        result = finalize_unconditional()
    elif args.command == "record-tests":
        result = record_tests(args.exit_code, args.test_command)
    elif args.command == "write-bundle-report":
        result = write_bundle_report(args.prereg_commit, args.analysis_commit)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
