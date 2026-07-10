#!/usr/bin/env python3
"""Deterministic OpenAI-compatible audio judge with append-only raw logging."""

from __future__ import annotations

import argparse
import base64
import copy
import csv
import hashlib
import json
import math
import mimetypes
import os
import re
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROMPT = (
    "Listen to the complete audio clip. Does it contain an audible human voice, "
    "including singing, speech, humming, chant, rap, or choir? Answer exactly one "
    "token: yes, no, or unsure. Do not infer from instruments or the text prompt."
)
LABEL_RE = re.compile(r"\b(yes|no|unsure)\b", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_label(response_text: str) -> str | None:
    labels = LABEL_RE.findall(response_text)
    normalized = {label.lower() for label in labels}
    return next(iter(normalized)) if len(normalized) == 1 else None


def content_text(message_content) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        return " ".join(
            str(item.get("text", "")) for item in message_content if isinstance(item, dict)
        )
    return str(message_content)


def majority(labels: list[str | None]) -> str:
    votes = Counter(label for label in labels if label in {"yes", "no"})
    required = len(labels) // 2 + 1
    if votes["yes"] >= required:
        return "yes"
    if votes["no"] >= required:
        return "no"
    return "unsure"


def binary_metrics(rows: list[dict]) -> dict:
    decided = [row for row in rows if row["majority_label"] in {"yes", "no"}]
    tp = sum(row["true_label"] == "yes" and row["majority_label"] == "yes" for row in decided)
    tn = sum(row["true_label"] == "no" and row["majority_label"] == "no" for row in decided)
    fp = sum(row["true_label"] == "no" and row["majority_label"] == "yes" for row in decided)
    fn = sum(row["true_label"] == "yes" and row["majority_label"] == "no" for row in decided)
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {
        "rows": len(rows),
        "decided": len(decided),
        "abstained": len(rows) - len(decided),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": (sensitivity + specificity) / 2,
        "mcc": (tp * tn - fp * fn) / denominator if denominator else math.nan,
        "accuracy": (tp + tn) / len(decided) if decided else math.nan,
        "abstention_rate": (len(rows) - len(decided)) / len(rows) if rows else math.nan,
    }


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def request_one(endpoint: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def canonical_request(payload: dict, audio_hash: str, media_type: str) -> dict:
    request = copy.deepcopy(payload)
    for message in request.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "audio_url":
                item["audio_url"]["url"] = f"sha256:{audio_hash};media_type={media_type}"
    return request


def validate_manifest_rows(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("empty judge manifest")
    clip_ids = [row.get("clip_id") or row.get("rating_id") for row in rows]
    if any(not clip_id for clip_id in clip_ids) or len(set(clip_ids)) != len(clip_ids):
        raise ValueError("manifest clip IDs must be present and unique")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8901")
    parser.add_argument("--model", default="qwen3-omni-judge")
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--calls-per-clip", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--infrastructure-only", action="store_true")
    args = parser.parse_args()
    if args.calls_per_clip < 1:
        raise ValueError("calls-per-clip must be positive")
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    validate_manifest_rows(rows)
    results = []
    for row in rows:
        clip_id = row.get("clip_id") or row.get("rating_id")
        audio_path = Path(row.get("clip_path") or row.get("media_path") or "")
        if not clip_id or not audio_path.is_file():
            raise ValueError(f"invalid manifest row: {row}")
        audio_hash = sha256_file(audio_path)
        media_type = mimetypes.guess_type(audio_path.name)[0] or "audio/flac"
        data_url = f"data:{media_type};base64," + base64.b64encode(audio_path.read_bytes()).decode()
        parsed = []
        for call_index in range(args.calls_per_clip):
            seed = 20260709 + call_index
            payload = {
                "model": args.model,
                "temperature": 0,
                "seed": seed,
                "max_tokens": 8,
                "messages": [
                    {"role": "system", "content": "You are a conservative audio-labeling instrument."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "audio_url", "audio_url": {"url": data_url}},
                            {"type": "text", "text": PROMPT},
                        ],
                    },
                ],
            }
            started = time.time()
            error = None
            response = None
            response_text = ""
            try:
                response = request_one(args.endpoint, payload, args.timeout)
                response_text = content_text(response["choices"][0]["message"]["content"])
                label = parse_label(response_text)
            except Exception as exc:  # noqa: BLE001
                label = None
                error = f"{type(exc).__name__}: {exc}"
            parsed.append(label)
            append_jsonl(
                args.raw_output,
                {
                    "clip_id": clip_id,
                    "audio_path": str(audio_path.resolve()),
                    "audio_sha256": audio_hash,
                    "call_index": call_index,
                    "seed": seed,
                    "model": args.model,
                    "endpoint": args.endpoint,
                    "temperature": 0,
                    "prompt": PROMPT,
                    "request_without_embedded_audio": canonical_request(
                        payload, audio_hash, media_type
                    ),
                    "response": response,
                    "response_text": response_text,
                    "parsed_label": label,
                    "error": error,
                    "runtime_s": time.time() - started,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            if error:
                raise RuntimeError(error)
        results.append(
            {
                "clip_id": clip_id,
                "true_label": row.get("true_label", "").strip().lower(),
                "majority_label": majority(parsed),
                "calls": parsed,
            }
        )
    if args.infrastructure_only:
        total_calls = sum(len(row["calls"]) for row in results)
        parsed_calls = sum(
            label is not None for row in results for label in row["calls"]
        )
        summary = {
            "status": "INFRASTRUCTURE_PASS" if parsed_calls == total_calls else "INFRASTRUCTURE_FAIL",
            "rows": len(results),
            "parsed_calls": parsed_calls,
            "total_calls": total_calls,
        }
    else:
        if any(row["true_label"] not in {"yes", "no"} for row in results):
            raise ValueError("validated run requires yes/no PI truth for every clip")
        summary = {"status": "SCORED", **binary_metrics(results)}
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps({**summary, "results": results}, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] != "INFRASTRUCTURE_FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
