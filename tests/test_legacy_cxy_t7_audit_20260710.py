from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import wave
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "paper_prep/scripts/audit_legacy_cxy_t7_20260710.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_legacy_cxy_t7_20260710", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_wav(path: Path) -> str:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8_000)
        handle.writeframes(b"\0\0" * 16_000)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_recomputes_metrics_and_rejects_embedded_audio(tmp_path):
    module = load_module()
    manifest = tmp_path / "manifest.csv"
    raw = tmp_path / "raw.jsonl"
    summary = tmp_path / "summary.json"
    clips = []
    for clip_id, truth in (("positive", "yes"), ("negative", "no")):
        audio = tmp_path / f"{clip_id}.wav"
        digest = write_wav(audio)
        clips.append((clip_id, truth, audio, digest))
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["clip_id", "clip_path", "true_label", "provenance"])
        writer.writeheader()
        for clip_id, truth, audio, _digest in clips:
            writer.writerow({"clip_id": clip_id, "clip_path": audio, "true_label": truth, "provenance": "test"})
    raw_rows = []
    results = []
    for clip_id, truth, audio, digest in clips:
        calls = [truth, truth, truth]
        results.append({"clip_id": clip_id, "true_label": truth, "majority_label": truth, "calls": calls})
        for index, label in enumerate(calls):
            raw_rows.append({
                "clip_id": clip_id,
                "call_index": index,
                "parsed_label": label,
                "error": None,
                "audio_sha256": digest,
                "request_without_embedded_audio": {"audio": f"sha256:{digest}"},
            })
    raw.write_text("".join(json.dumps(row) + "\n" for row in raw_rows), encoding="utf-8")
    summary.write_text(json.dumps({
        "rows": 2,
        "decided": 2,
        "abstained": 0,
        "sensitivity": 1.0,
        "specificity": 1.0,
        "balanced_accuracy": 1.0,
        "mcc": 1.0,
        "abstention_rate": 0.0,
        "results": results,
    }), encoding="utf-8")
    result = module.audit(manifest, raw, summary, 3)
    assert result["balanced_accuracy"] == 1.0
    assert result["calls"] == 6

    raw_rows[0]["request_without_embedded_audio"] = {"audio": "data:audio/wav;base64,AAAA"}
    raw.write_text("".join(json.dumps(row) + "\n" for row in raw_rows), encoding="utf-8")
    try:
        module.audit(manifest, raw, summary, 3)
    except ValueError as exc:
        assert "embedded audio" in str(exc)
    else:
        raise AssertionError("embedded audio should fail the audit")
