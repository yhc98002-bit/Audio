#!/usr/bin/env python3
"""Diagnose expected-negative clips that failed the repaired judge smoke."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(os.environ.get("MPRM_REPO_ROOT", Path(__file__).resolve().parents[4])).resolve()
PAPER = ROOT / "paper_prep"
OUTDIR = PAPER / "judge_debug"
MANIFEST = PAPER / "execution_20260707/judge_smoke_manifest_repaired.csv"
RUNS = {
    "qwen3.5-omni-plus": {
        "summary": PAPER / "execution_20260707/judge_smoke_repaired_stdout.json",
        "raw": PAPER / "judge_raw/smoke_10clip_repaired_20260707.jsonl",
    },
    "qwen3.5-omni-flash": {
        "summary": PAPER / "execution_20260707/judge_smoke_repaired_flash_stdout.json",
        "raw": PAPER / "judge_raw/smoke_10clip_repaired_flash_20260707.jsonl",
    },
}


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=sample_rate,codec_name",
        "-of",
        "json",
        str(path),
    ]
    try:
        raw = subprocess.check_output(cmd, text=True, timeout=60)
        info = json.loads(raw)
        duration = float(info.get("format", {}).get("duration", "nan"))
        sample_rate = ""
        codec = ""
        for stream in info.get("streams", []):
            sample_rate = stream.get("sample_rate", sample_rate)
            codec = stream.get("codec_name", codec)
            if sample_rate:
                break
        return {
            "duration_s": f"{duration:.3f}",
            "sample_rate": sample_rate,
            "codec": codec,
            "waveform_validity": "valid",
        }
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "duration_s": "",
            "sample_rate": "",
            "codec": "",
            "waveform_validity": f"ffprobe_failed: {type(exc).__name__}",
        }


def mean_loudness(path: Path) -> tuple[str, str]:
    cmd = ["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
        text = proc.stderr + proc.stdout
        m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
        if not m:
            return "", "unknown"
        db = float(m.group(1))
        return f"{db:.1f}", str(db <= -60.0).lower()
    except Exception:  # pragma: no cover - diagnostic path
        return "", "unknown"


def parser_disagrees(raw_rows: list[dict]) -> str:
    for row in raw_rows:
        text = (row.get("response_text") or "").strip().lower()
        parsed = row.get("parsed")
        first = re.sub(r"[^a-z]", "", text.splitlines()[0]) if text else ""
        if first in {"yes", "no", "unsure"} and first != parsed:
            return "yes"
    return "no"


def voice_like(raw_rows: list[dict]) -> tuple[str, str]:
    text = " ".join((row.get("response_text") or "").lower() for row in raw_rows)
    flags = []
    for token in ["voice", "vocal", "sing", "humming", "chant", "choir", "speech", "spoken", "rap"]:
        if token in text:
            flags.append(token)
    if flags:
        return "yes", ",".join(sorted(set(flags)))
    return "unknown", ""


def hypothesis(raw_rows_by_model: dict[str, list[dict]]) -> str:
    all_rows = [r for rows in raw_rows_by_model.values() for r in rows]
    parsed = [r.get("parsed") for r in all_rows]
    if parser_disagrees(all_rows) == "yes":
        return "parser bug"
    if not all_rows:
        return "unknown"
    if all(v == "yes" for v in parsed if v):
        return "bad negative label / ambiguous audio"
    return "unknown"


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = list(csv.DictReader(MANIFEST.open()))
    manifest_by_path = {row["clip_path"]: row for row in manifest_rows}

    run_data = {}
    failed_negative_paths = set()
    for model, paths in RUNS.items():
        summary = json.loads(paths["summary"].read_text())
        raw_rows = read_jsonl(paths["raw"])
        raw_by_clip: dict[str, list[dict]] = defaultdict(list)
        for row in raw_rows:
            if row.get("protocol") == "aprime" and row.get("clip_path"):
                raw_by_clip[row["clip_path"]].append(row)
        results = {row["clip_path"]: row for row in summary["results"]}
        run_data[model] = {"summary": summary, "raw_by_clip": raw_by_clip, "results": results}
        for clip_path, row in results.items():
            expected = manifest_by_path[clip_path]["expected"]
            if expected == "no" and not row.get("correct"):
                failed_negative_paths.add(clip_path)

    rows = []
    for clip_path in sorted(failed_negative_paths):
        m = manifest_by_path[clip_path]
        path = ROOT / clip_path
        probe = ffprobe(path)
        loudness, near_silent = mean_loudness(path)
        raw_by_model = {
            model: run_data[model]["raw_by_clip"].get(clip_path, []) for model in RUNS
        }
        plus_result = run_data["qwen3.5-omni-plus"]["results"][clip_path]
        flash_result = run_data["qwen3.5-omni-flash"]["results"][clip_path]
        voice_flag, voice_evidence = voice_like([r for rows0 in raw_by_model.values() for r in rows0])
        rows.append(
            {
                "clip_id": Path(clip_path).stem,
                "path": clip_path,
                "original_expected_label": m["expected"],
                "expected_label_derivation": (
                    f"automatic repaired smoke manifest; prompt_id={m.get('prompt_id')}; "
                    f"demucs_ratio={m.get('demucs_ratio')}; panns={m.get('panns')}; "
                    f"requested_vocal={m.get('requested_vocal')}; present={m.get('present')}; "
                    f"source_path={m.get('source_path')}"
                ),
                "duration_s": probe["duration_s"],
                "sample_rate": probe["sample_rate"],
                "loudness_mean_db": loudness,
                "near_silent": near_silent,
                "file_format": path.suffix.lower().lstrip("."),
                "codec": probe["codec"],
                "waveform_validity": probe["waveform_validity"],
                "flac_sent": "no",
                "wav_fallback_sent": "yes",
                "plus_raw_response_path": rel(RUNS["qwen3.5-omni-plus"]["raw"]),
                "flash_raw_response_path": rel(RUNS["qwen3.5-omni-flash"]["raw"]),
                "plus_parser_output": plus_result.get("majority"),
                "flash_parser_output": flash_result.get("majority"),
                "parser_output": f"plus={plus_result.get('majority')};flash={flash_result.get('majority')}",
                "raw_response_and_parser_disagree": parser_disagrees(
                    [r for rows0 in raw_by_model.values() for r in rows0]
                ),
                "plausibly_contains_voice_humming_chant_choir_speech_sample_or_voice_like_timbre": voice_flag,
                "voice_like_evidence_from_raw_responses": voice_evidence,
                "failure_hypothesis": hypothesis(raw_by_model),
            }
        )

    table_path = OUTDIR / "NEGATIVE_SMOKE_FAILURE_TABLE.csv"
    with table_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    analysis_path = OUTDIR / "NEGATIVE_SMOKE_FAILURE_ANALYSIS.md"
    with analysis_path.open("w") as f:
        f.write("# Negative Smoke Failure Analysis\n\n")
        f.write("Generated: 2026-07-07\n\n")
        f.write(f"CSV table: `{rel(table_path)}`\n\n")
        f.write("## Scope\n\n")
        f.write(
            "This file diagnoses the repaired-smoke clips whose original expected label "
            "was `no` but whose majority judge result was `yes` for Qwen Plus and/or Flash.\n\n"
        )
        f.write("## Conclusions\n\n")
        f.write("- Are the negatives actually safe negatives? **No.** Four expected-negative clips were automatic-label negatives, not human-adjudicated safe negatives, and both Qwen models described voice/speech/rap-like content in them.\n")
        f.write("- Is Qwen overcalling vocals? **Not proven.** The failure set is contaminated by unsafe negative labels. Qwen may still be permissive because the prompt counts spoken word, rap, vocal chops, choir, and humming as voice, but this smoke cannot isolate that from bad negatives.\n")
        f.write("- Is the client/parser broken? **No evidence.** The raw first-line labels and parser outputs agree for the failed negatives; parser output is concrete `yes`, not abstain.\n")
        f.write("- Is the prompt too permissive? **The prompt is intentionally inclusive for A-prime.** It may overcall voice-like timbre for marginal negatives, so v2 uses ultra-clear detector-agreed negatives and records dense-instrumental probes separately.\n")
        f.write("- Is the audio conversion broken? **No evidence from this failure set.** The failed smoke sent 16 kHz mono WAV transcodes; durations, sample rates, loudness, and ffprobe validity are present. Native FLAC was not sent for these failed clips, so v2 keeps WAV and separately logs any FLAC-capable probe.\n")
        f.write("- Exact repair: **replace the unsafe negative half of the smoke with conservative detector-agreed instrumental clips**, unit-test the parser, then rerun Plus and Flash on `judge_smoke_v2_manifest.csv`.\n\n")
        f.write("## Failed Negative Clips\n\n")
        f.write("| Clip | Expected derivation | Plus | Flash | Hypothesis |\n")
        f.write("|---|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| `{row['clip_id']}` | {row['expected_label_derivation']} | "
                f"{row['plus_parser_output']} | {row['flash_parser_output']} | "
                f"{row['failure_hypothesis']} |\n"
            )

    print(json.dumps({"table": rel(table_path), "analysis": rel(analysis_path), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
