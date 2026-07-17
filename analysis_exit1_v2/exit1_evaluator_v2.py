#!/usr/bin/env python3
"""Build the amended Exit-1 evaluator comparison from preserved v1 evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import socket
from collections import defaultdict
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "analysis_exit1"
OUT = ROOT / "analysis_exit1_v2"
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"

T6_PROMOTION_REPORT = PAPER / "autochain_20260712/T6_PROMOTION_REPORT.md"
T6_PROMOTION_RESULT = PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json"

V1_EVALUATOR_ROWS = V1 / "EVALUATOR_INPUT_ROWS.csv"
V1_WHISPER_SCORES = V1 / "EVALUATOR_WHISPER_SCORES.csv"
V1_AUDIOSET_SCORES = V1 / "EVALUATOR_AUDIOSET_SCORES.csv"
V1_DETECTOR_FILL = V1 / "EVALUATOR_DETECTOR_FILL_SCORES.csv"
V1_AUDIOSET_METADATA = V1 / "EVALUATOR_AUDIOSET_MODEL_METADATA.json"
V1_PREP_AUDIT = V1 / "EVALUATOR_PREP_AUDIT.json"
V1_COMPARISON_AUDIT = V1 / "EVALUATOR_COMPARISON_AUDIT.json"
V1_COMPARISON_REPORT = V1 / "EVALUATOR_COMPARISON_TABLE.md"

V2_COMPARISON_REPORT = OUT / "EVALUATOR_COMPARISON_TABLE.md"
V2_COMPARISON_AUDIT = OUT / "EVALUATOR_COMPARISON_AUDIT.json"
V2_SUPERSESSION_REPORT = OUT / "EXIT1_V2_SUPERSESSION_REPORT.md"
V2_AUDIOSET_HUMAN_SCORES = OUT / "EVALUATOR_AUDIOSET_HUMAN_VOICE_SCORES.csv"
V2_AUDIOSET_HUMAN_AUDIT = OUT / "EVALUATOR_AUDIOSET_HUMAN_VOICE_AUDIT.json"

LEGACY_DEMUCS_THRESHOLD = 0.1791
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 2026071602
PI_ONLY_NEGATIVE_POWER_FLOOR = 30
METRIC_NAMES = ("sensitivity", "specificity", "balanced_accuracy", "mcc")

# Exact AudioSet labels that satisfy the signed Label-A construct: a sound a
# reasonable listener would perceive as human voice or human vocalization.
HUMAN_VOICE_AUDIOSET_LABELS = frozenset(
    {
        "Speech",
        "Male speech, man speaking",
        "Female speech, woman speaking",
        "Child speech, kid speaking",
        "Conversation",
        "Narration, monologue",
        "Babbling",
        "Shout",
        "Bellow",
        "Whoop",
        "Yell",
        "Battle cry",
        "Children shouting",
        "Screaming",
        "Whispering",
        "Laughter",
        "Baby laughter",
        "Giggle",
        "Snicker",
        "Belly laugh",
        "Chuckle, chortle",
        "Crying, sobbing",
        "Baby cry, infant cry",
        "Whimper",
        "Wail, moan",
        "Sigh",
        "Singing",
        "Choir",
        "Yodeling",
        "Chant",
        "Mantra",
        "Male singing",
        "Female singing",
        "Child singing",
        "Rapping",
        "Humming",
        "Groan",
        "Grunt",
        "Breathing",
        "Wheeze",
        "Snoring",
        "Gasp",
        "Pant",
        "Snort",
        "Cough",
        "Throat clearing",
        "Sneeze",
        "Sniff",
        "Cheering",
        "Chatter",
        "Hubbub, speech noise, speech babble",
        "Children playing",
        "Vocal music",
        "A capella",
    }
)
AUDIOSET_EXCLUSION_REGRESSION_LABELS = frozenset(
    {
        "Speech synthesizer",
        "Synthetic singing",
        "Bird vocalization, bird call, bird song",
        "Whale vocalization",
        "Singing bowl",
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite differing output: {path}")
        return
    path.write_text(content, encoding="utf-8")


def write_json_once(path: Path, value: object) -> None:
    _write_once(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv_once(path: Path, rows: Sequence[dict]) -> None:
    _write_once(path, csv_text(rows))


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
    return {"threshold": best[1], "train_metrics": best[2]}


def parse_canonical_instrument(report_path: Path, result_path: Path) -> dict:
    """Fail closed unless the human-readable report and result JSON agree."""
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("CORRECTED_INSTRUMENT_STATUS") != "PROMOTED":
        raise ValueError("canonical T6 result is not PROMOTED")
    selected = result.get("heldout", {}).get("selected_candidate", {})
    family = selected.get("family")
    demucs_threshold = selected.get("demucs_threshold")
    panns_threshold = selected.get("panns_threshold")
    if family not in {"and", "or", "demucs", "panns", "current_demucs"}:
        raise ValueError(f"unsupported canonical instrument family: {family!r}")
    if not isinstance(demucs_threshold, (int, float)) or not isinstance(
        panns_threshold, (int, float)
    ):
        raise ValueError("canonical instrument thresholds are missing")
    expected_line = f"- Selected family: `{family}`."
    selected_lines = [
        line for line in report_path.read_text(encoding="utf-8").splitlines()
        if "Selected family:" in line
    ]
    if selected_lines != [expected_line]:
        raise ValueError(
            "canonical report/result family mismatch: "
            f"expected {expected_line!r}, observed {selected_lines!r}"
        )
    return {
        "family": family,
        "demucs_threshold": float(demucs_threshold),
        "panns_threshold": float(panns_threshold),
        "report_exact_line": expected_line,
        "report_sha256": sha256_file(report_path),
        "result_sha256": sha256_file(result_path),
    }


def canonical_prediction(
    family: str,
    demucs_score: float,
    panns_score: float,
    demucs_threshold: float,
    panns_threshold: float,
) -> int:
    demucs = demucs_score >= demucs_threshold
    panns = panns_score >= panns_threshold
    if family == "or":
        return int(demucs or panns)
    if family == "and":
        return int(demucs and panns)
    if family in {"demucs", "current_demucs"}:
        return int(demucs)
    if family == "panns":
        return int(panns)
    raise ValueError(f"unsupported canonical instrument family: {family!r}")


def audioset_human_voice_indices(id2label: dict) -> tuple[list[int], list[str]]:
    """Select human voice classes by exact label, never substring matching."""
    available = {str(label) for label in id2label.values()}
    missing = sorted(HUMAN_VOICE_AUDIOSET_LABELS - available)
    if missing:
        raise ValueError(f"AudioSet model is missing frozen human-voice labels: {missing}")
    if HUMAN_VOICE_AUDIOSET_LABELS & AUDIOSET_EXCLUSION_REGRESSION_LABELS:
        raise AssertionError("human-voice whitelist intersects the frozen exclusions")
    selected = sorted(
        (
            (int(raw_index), str(raw_label))
            for raw_index, raw_label in id2label.items()
            if str(raw_label) in HUMAN_VOICE_AUDIOSET_LABELS
        ),
        key=lambda item: item[0],
    )
    if not selected:
        raise ValueError("AudioSet model exposes no frozen human-voice classes")
    return [item[0] for item in selected], [item[1] for item in selected]


def _audioset_human_score(
    model, processor, path: Path, indices: list[int], labels: list[str]
) -> dict:
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
        "audioset_human_voice_score": best_score,
        "audioset_top_human_voice_class": best_class,
        "windows": len(chunks),
    }


def score_audioset_human_voice(model_path: Path, device: str) -> dict:
    """Correct only rows whose old superset maximum was outside the whitelist."""
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    local = model_path.resolve()
    if not local.is_dir():
        raise FileNotFoundError(local)
    old_rows = _index_unique(
        read_csv(V1_AUDIOSET_SCORES), "media_sha256", V1_AUDIOSET_SCORES
    )
    media_rows: dict[str, dict[str, str]] = {}
    for row in read_csv(V1_EVALUATOR_ROWS):
        prior = media_rows.get(row["media_sha256"])
        if prior is None or row["clip_path"] < prior["clip_path"]:
            media_rows[row["media_sha256"]] = row
    config = json.loads((local / "config.json").read_text(encoding="utf-8"))
    indices, labels = audioset_human_voice_indices(config["id2label"])
    affected = sorted(
        media_sha256
        for media_sha256, row in old_rows.items()
        if row["audioset_top_vocal_class"] not in HUMAN_VOICE_AUDIOSET_LABELS
    )
    processor = None
    model = None
    if affected:
        processor = AutoFeatureExtractor.from_pretrained(str(local), local_files_only=True)
        model = AutoModelForAudioClassification.from_pretrained(
            str(local), local_files_only=True
        ).to(device)
        model.eval()
    corrected = []
    for media_sha256, old in sorted(old_rows.items()):
        if media_sha256 in affected:
            assert model is not None and processor is not None
            rescored = _audioset_human_score(
                model,
                processor,
                Path(media_rows[media_sha256]["clip_path"]),
                indices,
                labels,
            )
            source = "rescored_exact_human_voice_whitelist"
        else:
            rescored = {
                "audioset_human_voice_score": float(old["audioset_vocal_score"]),
                "audioset_top_human_voice_class": old["audioset_top_vocal_class"],
                "windows": int(old["windows"]),
            }
            source = "v1_superset_max_is_exact_whitelist_member"
        if rescored["audioset_top_human_voice_class"] not in HUMAN_VOICE_AUDIOSET_LABELS:
            raise ValueError(f"corrected AudioSet result escaped whitelist: {rescored}")
        corrected.append(
            {
                "media_sha256": media_sha256,
                **rescored,
                "score_source": source,
                "old_audioset_vocal_score": old["audioset_vocal_score"],
                "old_audioset_top_vocal_class": old["audioset_top_vocal_class"],
                "was_rescored": int(media_sha256 in affected),
            }
        )
    write_csv_once(V2_AUDIOSET_HUMAN_SCORES, corrected)
    whitelist_sha256 = hashlib.sha256(
        "\n".join(sorted(HUMAN_VOICE_AUDIOSET_LABELS)).encode("utf-8")
    ).hexdigest()
    audit = {
        "status": "COMPLETE",
        "rows": len(corrected),
        "reused_rows": len(corrected) - len(affected),
        "rescored_rows": len(affected),
        "rescored_media_sha256": affected,
        "human_voice_labels": sorted(HUMAN_VOICE_AUDIOSET_LABELS),
        "human_voice_label_count": len(HUMAN_VOICE_AUDIOSET_LABELS),
        "human_voice_whitelist_sha256": whitelist_sha256,
        "exclusion_regression_labels": sorted(AUDIOSET_EXCLUSION_REGRESSION_LABELS),
        "model_path": str(local),
        "model_directory_manifest_sha256": json.loads(
            V1_AUDIOSET_METADATA.read_text(encoding="utf-8")
        )["directory_manifest_sha256"],
        "source_sha256": {
            str(V1_AUDIOSET_SCORES.relative_to(ROOT)): sha256_file(V1_AUDIOSET_SCORES),
            str(V1_EVALUATOR_ROWS.relative_to(ROOT)): sha256_file(V1_EVALUATOR_ROWS),
            str((local / "config.json")): sha256_file(local / "config.json"),
        },
        "output_sha256": sha256_file(V2_AUDIOSET_HUMAN_SCORES),
        "host": socket.gethostname(),
        "device": device,
        "scoring_policy": (
            "reuse v1 score iff its superset maximum is an exact whitelist member; "
            "otherwise rescore that media against the exact whitelist"
        ),
        "new_music_generation": 0,
    }
    write_json_once(V2_AUDIOSET_HUMAN_AUDIT, audit)
    return audit


def bootstrap_metrics(
    rows: list[dict], predictions: dict[str, list[int]], replicates: int, seed: int
) -> dict[str, dict[str, list[float] | int]]:
    import numpy as np

    by_prompt: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_prompt[row["prompt_id"]].append(index)
    prompts = sorted(by_prompt)
    rng = np.random.default_rng(seed)
    draws = {
        name: {metric: [] for metric in METRIC_NAMES}
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
            for metric in METRIC_NAMES:
                draws[name][metric].append(float(metrics[metric]))
    output: dict[str, dict[str, list[float] | int]] = {}
    for name, metrics in draws.items():
        valid = len(metrics["balanced_accuracy"])
        if not valid:
            raise ValueError(f"no valid bootstrap replicates for {name}")
        output[name] = {
            metric: [
                float(np.quantile(values, 0.025)),
                float(np.quantile(values, 0.975)),
            ]
            for metric, values in metrics.items()
        }
        output[name]["valid_replicates"] = valid
    return output


def metric_cell(point: float, interval: Sequence[float], power_limited: bool) -> str:
    marker = " **POWER_LIMITED**" if power_limited else ""
    return f"{point:.3f} [{interval[0]:.3f}, {interval[1]:.3f}]{marker}"


def render_panel_table(
    names: dict[str, str],
    threshold_labels: dict[str, str],
    metrics: dict[str, dict],
    intervals: dict[str, dict],
    power_limited: bool,
) -> list[str]:
    lines = [
        "| Instrument | Frozen operationalization | Sensitivity (95% CI) | "
        "Specificity (95% CI) | Balanced accuracy (95% CI) | MCC (95% CI) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for key in names:
        point = metrics[key]
        ci = intervals[key]
        lines.append(
            f"| {names[key]} | {threshold_labels[key]} | "
            f"{metric_cell(point['sensitivity'], ci['sensitivity'], power_limited)} | "
            f"{metric_cell(point['specificity'], ci['specificity'], power_limited)} | "
            f"{metric_cell(point['balanced_accuracy'], ci['balanced_accuracy'], power_limited)} | "
            f"{metric_cell(point['mcc'], ci['mcc'], power_limited)} |"
        )
    return lines


def _index_unique(rows: list[dict[str, str]], key: str, source: Path) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row[key]
        if value in output:
            raise ValueError(f"duplicate {key}={value!r} in {source}")
        output[value] = row
    return output


def load_v1_evidence() -> tuple[list[dict], dict[str, str]]:
    evidence_paths = (
        V1_EVALUATOR_ROWS,
        V1_WHISPER_SCORES,
        V1_AUDIOSET_SCORES,
        V1_DETECTOR_FILL,
        V1_AUDIOSET_METADATA,
        V1_PREP_AUDIT,
        V1_COMPARISON_AUDIT,
        V1_COMPARISON_REPORT,
    )
    for path in evidence_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    for path in (V2_AUDIOSET_HUMAN_SCORES, V2_AUDIOSET_HUMAN_AUDIT):
        if not path.is_file():
            raise FileNotFoundError(path)
    rows = read_csv(V1_EVALUATOR_ROWS)
    whisper = _index_unique(read_csv(V1_WHISPER_SCORES), "media_sha256", V1_WHISPER_SCORES)
    audioset = _index_unique(
        read_csv(V2_AUDIOSET_HUMAN_SCORES), "media_sha256", V2_AUDIOSET_HUMAN_SCORES
    )
    detector_fill = _index_unique(read_csv(V1_DETECTOR_FILL), "media_sha256", V1_DETECTOR_FILL)
    unique_media = {row["media_sha256"] for row in rows}
    if set(whisper) != unique_media or set(audioset) != unique_media:
        raise ValueError(
            "Whisper/corrected-AudioSet evidence does not cover every unique media hash"
        )
    required_fill = {
        row["media_sha256"] for row in rows if int(row["needs_detector_fill"])
    }
    if set(detector_fill) != required_fill:
        raise ValueError("v1 detector-fill evidence does not match required media hashes")
    for row in rows:
        item = dict(row)
        if int(item["needs_detector_fill"]):
            fill = detector_fill[item["media_sha256"]]
            item["demucs_score"] = fill["demucs_score"]
            item["panns_score"] = fill["panns_score"]
        if not item["demucs_score"] or not item["panns_score"]:
            raise ValueError(f"missing detector score for {item['rating_id']}")
        item["whisper_nonempty"] = whisper[item["media_sha256"]]["transcript_nonempty"]
        item["whisper_score"] = whisper[item["media_sha256"]]["transcript_confidence"]
        item["audioset_score"] = audioset[item["media_sha256"]][
            "audioset_human_voice_score"
        ]
        row.clear()
        row.update(item)
    hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in evidence_paths}
    return rows, hashes


def panel_predictions(rows: list[dict], thresholds: dict) -> dict[str, list[int]]:
    canonical = thresholds["canonical_promoted"]
    return {
        "legacy_demucs": [
            int(float(row["demucs_score"]) >= LEGACY_DEMUCS_THRESHOLD) for row in rows
        ],
        "canonical_promoted": [
            canonical_prediction(
                canonical["family"],
                float(row["demucs_score"]),
                float(row["panns_score"]),
                canonical["demucs_threshold"],
                canonical["panns_threshold"],
            )
            for row in rows
        ],
        "panns_only": [
            int(float(row["panns_score"]) >= thresholds["panns_only"]) for row in rows
        ],
        "whisper_transcript": [
            int(
                bool(int(row["whisper_nonempty"]))
                and float(row["whisper_score"]) >= thresholds["whisper_transcript"]
            )
            for row in rows
        ],
        "audioset_tagger": [
            int(float(row["audioset_score"]) >= thresholds["audioset_tagger"])
            for row in rows
        ],
    }


def evaluate_panel(rows: list[dict], thresholds: dict, seed: int) -> dict:
    predictions = panel_predictions(rows, thresholds)
    truth = [int(row["label_binary"]) for row in rows]
    metrics = {name: binary_metrics(truth, values) for name, values in predictions.items()}
    intervals = bootstrap_metrics(rows, predictions, BOOTSTRAP_REPLICATES, seed)
    return {
        "rows": len(rows),
        "decided_positives": sum(value == 1 for value in truth),
        "decided_negatives": sum(value == 0 for value in truth),
        "prompt_clusters": len({row["prompt_id"] for row in rows}),
        "metrics": metrics,
        "prompt_cluster_bootstrap_ci95": intervals,
    }


def build() -> dict:
    if OUT.resolve() == V1.resolve():
        raise AssertionError("v2 output directory must not equal v1 evidence directory")
    rows, v1_hashes = load_v1_evidence()
    canonical = parse_canonical_instrument(T6_PROMOTION_REPORT, T6_PROMOTION_RESULT)
    audioset_audit = json.loads(V2_AUDIOSET_HUMAN_AUDIT.read_text(encoding="utf-8"))
    if audioset_audit.get("status") != "COMPLETE":
        raise ValueError("corrected AudioSet human-voice audit is not complete")

    decided = [row for row in rows if row["label_binary"] != ""]
    train = [row for row in decided if row["split"] == "train"]
    heldout = [row for row in decided if row["split"] == "heldout"]
    pi_heldout = [row for row in heldout if row["rating_source"].startswith("pi:")]
    train_truth = [int(row["label_binary"]) for row in train]

    panns = select_threshold(train_truth, [float(row["panns_score"]) for row in train])
    whisper = select_threshold(
        train_truth,
        [float(row["whisper_score"]) for row in train],
        [bool(int(row["whisper_nonempty"])) for row in train],
    )
    audioset = select_threshold(
        train_truth, [float(row["audioset_score"]) for row in train]
    )
    thresholds = {
        "legacy_demucs": LEGACY_DEMUCS_THRESHOLD,
        "canonical_promoted": {
            "family": canonical["family"],
            "demucs_threshold": canonical["demucs_threshold"],
            "panns_threshold": canonical["panns_threshold"],
        },
        "panns_only": panns["threshold"],
        "whisper_transcript": whisper["threshold"],
        "audioset_tagger": audioset["threshold"],
    }
    panel_a = evaluate_panel(pi_heldout, thresholds, BOOTSTRAP_SEED)
    panel_b = evaluate_panel(heldout, thresholds, BOOTSTRAP_SEED)
    panel_a_power_limited = panel_a["decided_negatives"] < PI_ONLY_NEGATIVE_POWER_FLOOR

    names = {
        "legacy_demucs": "Legacy Demucs energy ratio",
        "canonical_promoted": "Canonical promoted Demucs OR PANNs",
        "panns_only": "PANNs only",
        "whisper_transcript": "Whisper transcript",
        "audioset_tagger": "AudioSet tagger",
    }
    threshold_labels = {
        "legacy_demucs": f"Demucs >= {LEGACY_DEMUCS_THRESHOLD}",
        "canonical_promoted": (
            f"Demucs >= {canonical['demucs_threshold']:.10f} OR "
            f"PANNs >= {canonical['panns_threshold']:.10f}"
        ),
        "panns_only": f"PANNs >= {panns['threshold']:.8f} (train-selected)",
        "whisper_transcript": (
            f"non-empty AND confidence >= {whisper['threshold']:.8f} (train-selected)"
        ),
        "audioset_tagger": (
            f"exact human-voice whitelist max >= {audioset['threshold']:.8f} "
            "(train-selected)"
        ),
    }
    report_lines = [
        "# Exit-1 Evaluator Comparison v2",
        "",
        "This report supersedes `analysis_exit1/EVALUATOR_COMPARISON_TABLE.md`. The v1 "
        "tree is preserved unchanged and used only as checksum-recorded input evidence.",
        "",
        "## Canonical instrument",
        "",
        "Exact line parsed from `T6_PROMOTION_REPORT.md`:",
        "",
        f"> {canonical['report_exact_line']}",
        "",
        f"`T6_PROMOTION_RESULT.json` SHA-256: `{canonical['result_sha256']}`.",
        "The family and thresholds below were parsed from that JSON; they were not "
        "hard-coded in the Exit-1 evaluator.",
        "",
        "## AudioSet human-voice whitelist",
        "",
        f"The AudioSet comparator uses {audioset_audit['human_voice_label_count']} exact "
        "human-voice/human-vocalization labels. It does not use substring matching. "
        f"Of 679 unique media rows, {audioset_audit['reused_rows']} retained their old "
        "score because the old superset maximum was already an exact whitelist member; "
        f"{audioset_audit['rescored_rows']} were rescored after the old maximum came from "
        "an excluded class.",
        "",
        "Frozen exclusions include `Speech synthesizer`, `Synthetic singing`, "
        "`Bird vocalization, bird call, bird song`, `Whale vocalization`, and "
        "`Singing bowl`. Regression tests name and enforce all five exclusions.",
        "",
        "## Panel A - PI-only held-out gold (primary)",
        "",
        f"**Panel A decided counts: {panel_a['decided_positives']} positive; "
        f"{panel_a['decided_negatives']} negative; {panel_a['rows']} total.**",
    ]
    if panel_a_power_limited:
        report_lines.extend(
            [
                "",
                f"**POWER_LIMITED:** PI-only decided negatives = "
                f"{panel_a['decided_negatives']} < {PI_ONLY_NEGATIVE_POWER_FLOOR}. "
                "Every Panel-A metric is marked accordingly; these estimates must not be "
                "presented as adequately powered specificity evidence.",
            ]
        )
    report_lines.extend(
        [
            "",
            *render_panel_table(
                names,
                threshold_labels,
                panel_a["metrics"],
                panel_a["prompt_cluster_bootstrap_ci95"],
                panel_a_power_limited,
            ),
            "",
            "## Panel B - merged PI plus validated-judge held-out gold (supplemental)",
            "",
            f"**Panel B decided counts: {panel_b['decided_positives']} positive; "
            f"{panel_b['decided_negatives']} negative; {panel_b['rows']} total.**",
            "",
            "Panel B is a precision supplement, not a replacement for Panel A. It includes "
            "validated-judge labels and must retain that instrument qualification.",
            "",
            *render_panel_table(
                names,
                threshold_labels,
                panel_b["metrics"],
                panel_b["prompt_cluster_bootstrap_ci95"],
                False,
            ),
            "",
            "## Threshold fitting and uncertainty",
            "",
            "The canonical promoted rule and legacy Demucs threshold are frozen. PANNs-only, "
            "Whisper, and AudioSet thresholds were selected on the pre-existing 238-row "
            "training split only. Panels A and B use held-out rows only. Intervals are "
            f"percentile 95% prompt-cluster bootstraps with {BOOTSTRAP_REPLICATES:,} "
            f"replicates and seed `{BOOTSTRAP_SEED}`.",
            "",
            "No BOLT output, new human label, or new music generation entered this v2 "
            "analysis. Eight pre-existing clips were re-evaluated by AudioSet solely to "
            "enforce the corrected exact-label human-voice whitelist.",
        ]
    )
    _write_once(V2_COMPARISON_REPORT, "\n".join(report_lines) + "\n")

    audit = {
        "status": "COMPLETE",
        "supersedes": str(V1_COMPARISON_REPORT.relative_to(ROOT)),
        "v1_evidence_preserved": True,
        "v1_input_evidence_sha256": v1_hashes,
        "canonical_instrument": canonical,
        "canonical_result_path": str(T6_PROMOTION_RESULT.relative_to(ROOT)),
        "canonical_report_path": str(T6_PROMOTION_REPORT.relative_to(ROOT)),
        "audioset_human_voice": {
            "scores_path": str(V2_AUDIOSET_HUMAN_SCORES.relative_to(ROOT)),
            "scores_sha256": sha256_file(V2_AUDIOSET_HUMAN_SCORES),
            "audit_path": str(V2_AUDIOSET_HUMAN_AUDIT.relative_to(ROOT)),
            "audit_sha256": sha256_file(V2_AUDIOSET_HUMAN_AUDIT),
            "human_voice_whitelist_sha256": audioset_audit[
                "human_voice_whitelist_sha256"
            ],
            "human_voice_label_count": audioset_audit["human_voice_label_count"],
            "exclusion_regression_labels": audioset_audit[
                "exclusion_regression_labels"
            ],
            "rescored_rows": audioset_audit["rescored_rows"],
            "reused_rows": audioset_audit["reused_rows"],
        },
        "thresholds": thresholds,
        "train_selection": {
            "rows": len(train),
            "panns_only": panns,
            "whisper_transcript": whisper,
            "audioset_tagger": audioset,
        },
        "panel_a_pi_only": {
            **panel_a,
            "power_floor_decided_negatives": PI_ONLY_NEGATIVE_POWER_FLOOR,
            "power_limited": panel_a_power_limited,
        },
        "panel_b_merged_gold_supplement": panel_b,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "new_human_labels": 0,
        "new_model_inference_rows": audioset_audit["rescored_rows"],
        "new_music_generation": 0,
        "generator_source_sha256": sha256_file(Path(__file__)),
    }
    write_json_once(V2_COMPARISON_AUDIT, audit)

    status = "POWER_LIMITED" if panel_a_power_limited else "ADEQUATELY_POWERED"
    supersession_lines = [
        "# Exit-1 v2 Supersession Report",
        "",
        "EXIT1_V2_STATUS = COMPLETE",
        "evidence: `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md`; "
        "`analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`",
        "",
        "V1_EVIDENCE_PRESERVED = YES",
        "evidence: `analysis_exit1/`; "
        "`analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`",
        "",
        f"PANEL_A_POWER_STATUS = {status}",
        "evidence: `analysis_exit1_v2/EVALUATOR_COMPARISON_TABLE.md`; "
        "`analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`",
        "",
        "CANONICAL_INSTRUMENT_PARSE = PASS",
        "evidence: `orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/"
        "T6_PROMOTION_REPORT.md`; `orbit-research/adsr_phase2_20260604/paper_prep/"
        "autochain_20260712/T6_PROMOTION_RESULT.json`; "
        "`analysis_exit1_v2/EVALUATOR_COMPARISON_AUDIT.json`",
        "",
        "## Scope",
        "",
        "This supersession corrects the evaluator-family parse and reporting hierarchy only. "
        "It changes no W2, BOLT, PLAN, CLAIMS, or gate artifact.",
    ]
    _write_once(V2_SUPERSESSION_REPORT, "\n".join(supersession_lines) + "\n")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    score = sub.add_parser("score-audioset-human-voice")
    score.add_argument("--model-path", type=Path, required=True)
    score.add_argument("--device", default="cuda")
    args = parser.parse_args()
    if args.command == "build":
        result = build()
    elif args.command == "score-audioset-human-voice":
        result = score_audioset_human_voice(args.model_path, args.device)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
