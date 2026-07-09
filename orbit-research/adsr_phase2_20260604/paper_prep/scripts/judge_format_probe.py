#!/usr/bin/env python3
"""Probe native-FLAC vs WAV judge input on fixed smoke clips."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

from judge_client import (
    APRIME_QUESTION,
    ENDPOINT,
    MODEL,
    ROOT,
    audio_part,
    call_omni,
    load_key,
    log_raw,
    parse_presence,
    sha256_file,
    transcode_to_wav_b64,
)


PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
OUT = PAPER / "judge_debug/JUDGE_FORMAT_PROBE_20260707.json"
RUN_NAME = "format_probe_20260707"

CLIPS = [
    {
        "clip_id": "positive_smoke",
        "expected": "yes",
        "clip_path": "orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/A_PRIME_500_JUDGE_SAMPLE/media/aprime_0132_9eb1d0e52752.flac",
    },
    {
        "clip_id": "negative_smoke",
        "expected": "no",
        "clip_path": "orbit-research/adsr_phase2_20260604/paper_prep/storage_triage/A_PRIME_500_JUDGE_SAMPLE/media/aprime_0406_514e4242add9.flac",
    },
]


def flac_b64(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return base64.b64encode(data).decode("ascii"), len(data)


def probe_one(api_key: str, clip: dict, fmt: str) -> dict:
    path = ROOT / clip["clip_path"]
    sha = sha256_file(path)
    if fmt == "flac":
        b64, nbytes = flac_b64(path)
        sr = None
        channels = None
    elif fmt == "wav":
        b64, nbytes = transcode_to_wav_b64(path, 16000, 1)
        sr = 16000
        channels = 1
    else:
        raise ValueError(fmt)
    text, usage, meta = call_omni(
        api_key,
        [audio_part(b64, fmt), {"type": "text", "text": APRIME_QUESTION}],
        max_retries=2,
        timeout=180,
    )
    parsed = parse_presence(text)
    record = {
        "protocol": "format_probe",
        "run": RUN_NAME,
        "clip_id": clip["clip_id"],
        "clip_path": clip["clip_path"],
        "clip_sha256": sha,
        "expected": clip["expected"],
        "input_format": fmt,
        "input_bytes": nbytes,
        "transcode": {"format": fmt, "sr": sr, "channels": channels},
        "question": APRIME_QUESTION,
        "response_text": text,
        "parsed": parsed,
        "correct": parsed == clip["expected"],
        "usage": usage,
        **meta,
    }
    log_raw(RUN_NAME, record)
    return record


def main() -> int:
    api_key = load_key()
    old_model = MODEL
    results = []
    for clip in CLIPS:
        for fmt in ("flac", "wav"):
            results.append(probe_one(api_key, clip, fmt))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "run": RUN_NAME,
        "model": os.environ.get("DASHSCOPE_MODEL", old_model),
        "endpoint": ENDPOINT,
        "results": [
            {
                "clip_id": r["clip_id"],
                "input_format": r["input_format"],
                "parsed": r["parsed"],
                "expected": r["expected"],
                "correct": r["correct"],
                "error": r.get("error"),
                "latency_s": r.get("latency_s"),
            }
            for r in results
        ],
        "raw_log": str(PAPER / "judge_raw" / f"{RUN_NAME}.jsonl"),
    }
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(OUT)
    return 0 if all(r.get("response_text") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

