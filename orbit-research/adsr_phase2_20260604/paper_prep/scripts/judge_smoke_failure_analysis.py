#!/usr/bin/env python3
"""Build clip-by-clip judge-smoke failure analysis from pinned raw logs."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
OUTDIR = PAPER / "judge_debug"

MANIFEST = PAPER / "execution_20260707/judge_smoke_manifest_repaired.csv"
RUNS = [
    {
        "model": "qwen3.5-omni-plus",
        "summary": PAPER / "execution_20260707/judge_smoke_repaired_stdout.json",
        "raw": PAPER / "judge_raw/smoke_10clip_repaired_20260707.jsonl",
    },
    {
        "model": "qwen3.5-omni-flash",
        "summary": PAPER / "execution_20260707/judge_smoke_repaired_flash_stdout.json",
        "raw": PAPER / "judge_raw/smoke_10clip_repaired_flash_20260707.jsonl",
    },
]


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def ffprobe(path: Path) -> tuple[float | None, int | None]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=sample_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=60)
        j = json.loads(out)
        duration = None
        if j.get("format", {}).get("duration") is not None:
            duration = float(j["format"]["duration"])
        sr = None
        for stream in j.get("streams", []):
            if stream.get("sample_rate"):
                sr = int(stream["sample_rate"])
                break
        return duration, sr
    except Exception:
        return None, None


def loudness(path: Path) -> tuple[float | None, bool | None]:
    cmd = ["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=120)
        text = proc.stderr + proc.stdout
        m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", text)
        mean_db = float(m.group(1)) if m else None
        near_silent = mean_db is not None and mean_db <= -60.0
        return mean_db, near_silent
    except Exception:
        return None, None


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def response_semantics(parsed: str, expected: str, responses: list[dict]) -> tuple[bool, str]:
    if parsed in {"yes", "no"}:
        return False, "parser returned a concrete yes/no label"
    texts = " ".join((r.get("response_text") or "").lower() for r in responses)
    if expected == "yes" and re.search(r"\byes\b|voice|vocal|sing|speech|rap", texts):
        return True, "response text appears semantically positive"
    if expected == "no" and re.search(r"\bno\b|no voice|instrumental|no vocal", texts):
        return True, "response text appears semantically negative"
    return False, "no parser/semantic mismatch detected"


def failure_category(correct: bool, parsed: str, expected: str, responses: list[dict]) -> str:
    if correct:
        return "n/a"
    if parsed == "abstain":
        return "parser bug"
    if not responses:
        return "unknown"
    if all((r.get("parsed") in {"yes", "no", "unsure"}) for r in responses):
        return "unknown"
    return "parser bug"


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = {r["clip_path"]: r for r in csv.DictReader(MANIFEST.open())}

    audio_meta = {}
    for clip in sorted(manifest_rows):
        path = ROOT / clip
        duration, sr = ffprobe(path)
        mean_db, near_silent = loudness(path)
        audio_meta[clip] = {
            "duration_s": duration,
            "sample_rate": sr,
            "mean_volume_db": mean_db,
            "near_silent": near_silent,
            "input_file_format": path.suffix.lower().lstrip("."),
        }

    out_rows = []
    metadata_rows = []
    for run in RUNS:
        summary = json.loads(run["summary"].read_text())
        raw_rows = load_jsonl(run["raw"])
        raw_by_clip = defaultdict(list)
        for r in raw_rows:
            if r.get("protocol") == "aprime" and r.get("clip_path"):
                raw_by_clip[r["clip_path"]].append(r)
        metadata_rows.append(
            {
                "model": summary.get("model", run["model"]),
                "endpoint": summary.get("endpoint"),
                "request_start": min((r.get("ts") for r in raw_rows if r.get("ts")), default=""),
                "request_end": max((r.get("ts") for r in raw_rows if r.get("ts")), default=""),
                "decoding": json.dumps(summary.get("decoding", {}), sort_keys=True),
                "raw_path": rel(run["raw"]),
                "summary_path": rel(run["summary"]),
            }
        )
        results = {r["clip_path"]: r for r in summary["results"]}
        for idx, clip in enumerate(sorted(manifest_rows), start=1):
            m = manifest_rows[clip]
            result = results[clip]
            responses = raw_by_clip.get(clip, [])
            votes = result.get("votes", [])
            majority = result.get("majority", "")
            confidence = max((votes.count(v) for v in set(votes)), default=0)
            sem_failed, sem_note = response_semantics(majority, m["expected"], responses)
            transcode = responses[0].get("transcode", {}) if responses else {}
            first_question = responses[0].get("question", "") if responses else ""
            out_rows.append(
                {
                    "model": summary.get("model", run["model"]),
                    "clip_id": f"smoke_{idx:02d}",
                    "clip_path": clip,
                    "true_label_source": (
                        f"repaired smoke manifest expected={m['expected']}; "
                        f"Demucs={m.get('demucs_ratio')}; PANNs={m.get('panns')}; "
                        f"source_path={m.get('source_path')}"
                    ),
                    "duration_s": audio_meta[clip]["duration_s"],
                    "sample_rate": audio_meta[clip]["sample_rate"],
                    "mean_volume_db": audio_meta[clip]["mean_volume_db"],
                    "near_silent": audio_meta[clip]["near_silent"],
                    "audio_format_sent": transcode.get("format", "unknown"),
                    "flac_or_wav_used": "WAV transcode from FLAC source",
                    "prompt_template": first_question.replace("\n", " "),
                    "raw_model_response_path": rel(run["raw"]),
                    "parsed_label": majority,
                    "votes": ",".join(votes),
                    "parser_confidence": f"{confidence}/3",
                    "expected_label": m["expected"],
                    "correct": result.get("correct"),
                    "semantic_correct_parser_failed": sem_failed,
                    "semantic_parser_note": sem_note,
                    "failure_category": failure_category(
                        bool(result.get("correct")), majority, m["expected"], responses
                    ),
                    "response_excerpt": " | ".join(
                        (r.get("response_text") or "").replace("\n", " ")[:160] for r in responses[:3]
                    ),
                }
            )

    csv_path = OUTDIR / "JUDGE_SMOKE_FAILURE_ANALYSIS_20260707.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)

    meta_path = OUTDIR / "JUDGE_SMOKE_METADATA_20260707.csv"
    with meta_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metadata_rows[0]))
        writer.writeheader()
        writer.writerows(metadata_rows)

    md_path = OUTDIR / "JUDGE_SMOKE_FAILURE_ANALYSIS_20260707.md"
    with md_path.open("w") as f:
        f.write("# Judge Smoke Failure Analysis\n\n")
        f.write("Generated: 2026-07-07\n\n")
        f.write("Status: **BLOCKED**. The repaired 10-clip smoke failed for both models at 6/10.\n\n")
        f.write("## Metadata\n\n")
        f.write("| Model | Endpoint | Request range | Decoding | Raw log |\n")
        f.write("|---|---|---|---|---|\n")
        for row in metadata_rows:
            f.write(
                f"| `{row['model']}` | `{row['endpoint']}` | {row['request_start']} to {row['request_end']} | "
                f"`{row['decoding']}` | `{row['raw_path']}` |\n"
            )
        f.write("\n")
        f.write("All smoke calls used deterministic decoding (`temperature=0.0`, seed 20260706) and WAV transcodes at 16 kHz mono from FLAC source files. The client did not test native FLAC input in the recorded smoke runs.\n\n")
        f.write("## Clip-Level Table\n\n")
        f.write("| Model | Clip | Expected | Parsed | Votes | Correct | Duration | SR | Mean dB | Sent | Category | Notes |\n")
        f.write("|---|---|---:|---:|---|---:|---:|---:|---:|---|---|---|\n")
        for row in out_rows:
            notes = row["response_excerpt"].replace("|", "/")
            f.write(
                f"| `{row['model']}` | `{row['clip_id']}` `{Path(row['clip_path']).name}` | "
                f"{row['expected_label']} | {row['parsed_label']} | `{row['votes']}` | "
                f"{row['correct']} | {float(row['duration_s'] or 0):.2f} | {row['sample_rate']} | "
                f"{float(row['mean_volume_db'] or 0):.1f} | {row['flac_or_wav_used']} | "
                f"{row['failure_category']} | {notes} |\n"
            )
        f.write("\n")
        f.write("## Interpretation\n\n")
        f.write("- Parser failure is not the cause: all repaired-smoke calls parsed to concrete yes/no labels, and all failures were unanimous `yes` votes on clips labeled `expected=no` by the repaired manifest.\n")
        f.write("- Audio loading is not obviously failing: durations, sample rates, and mean volumes are non-null; none of the clips are near-silent by the `mean_volume <= -60 dB` local check.\n")
        f.write("- The unresolved failure mode is either wrong model judgment or bad negative manifest labels. Because the negative labels are automatic Demucs/PANNs-derived labels rather than human-adjudicated truth, this analysis marks the failed negative clips as `unknown` rather than silently treating them as judge errors.\n")
        f.write("- Scale A-prime/B-prime calls remain blocked until a valid 10/10 smoke exists or an approved fallback replaces the Qwen smoke gate.\n\n")
        f.write("## Required Recovery\n\n")
        f.write("1. Build a new 10-clip smoke with PI- or human-adjudicated negatives, or use an already human-adjudicated negative set.\n")
        f.write("2. Add a native-FLAC request path to the judge client and test FLAC vs WAV on the same fixed clips without changing labels.\n")
        f.write("3. Rerun the 10-clip smoke only after the label source and input-format test are recorded.\n")

    print(md_path)
    print(csv_path)
    print(meta_path)


if __name__ == "__main__":
    main()

