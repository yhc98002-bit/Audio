#!/usr/bin/env python3
"""Score SA3 prevalence outputs with the ADSR Demucs vocal-ratio detector."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import time
from pathlib import Path

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

THR = VOCAL_PRESENCE_THRESHOLD

_MODEL = None


def get_model(device: str):
    global _MODEL
    if _MODEL is None:
        import torch
        from demucs.pretrained import get_model

        torch.set_num_threads(int(os.environ.get("ADSR_THREADS", "4")))
        model = get_model("htdemucs").eval()
        if device != "cpu":
            model = model.to(device)
        _MODEL = model
    return _MODEL


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def existing_keys(path: Path) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    if not path.exists():
        return keys
    for row in read_jsonl(path):
        if row.get("ok"):
            keys.add((row["prompt_id"], int(row["seed_idx"])))
    return keys


def score_one(path: Path, device: str) -> dict:
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    from demucs.apply import apply_model

    model = get_model(device)
    model_sr = int(getattr(model, "samplerate", 44100))
    wav, sr = sf.read(str(path))
    stereo = wav.T if wav.ndim == 2 else np.stack([wav, wav])
    x = torch.tensor(stereo, dtype=torch.float32).unsqueeze(0)
    if sr != model_sr:
        x = torchaudio.functional.resample(x, sr, model_sr)
    input_rms = float(torch.sqrt((x**2).mean()).item())
    near_silent = input_rms < 1e-3
    with torch.inference_mode():
        out = apply_model(model, x, device=device, split=True, overlap=0.1)[0]
    idx = {source: i for i, source in enumerate(model.sources)}
    energy = {source: float((out[idx[source]] ** 2).mean().item()) for source in model.sources}
    total = sum(energy.values()) + 1e-12
    ratio = energy["vocals"] / total
    return {
        "vocal_energy_ratio": ratio,
        "input_rms": input_rms,
        "near_silent": near_silent,
        "present": int((ratio >= THR) and not near_silent),
        "stem_energy": {k: v / total for k, v in energy.items()},
        "model_sr": model_sr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prevalence-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    ledger_path = args.prevalence_dir / "SA3_PREVALENCE_LEDGER.jsonl"
    score_path = args.prevalence_dir / "SA3_PREVALENCE_DEMUCS_LEDGER.jsonl"
    rows = [
        row
        for row in read_jsonl(ledger_path)
        if row.get("status") == "PASS" and row.get("output_path")
    ]
    # Deduplicate generated rows by prompt/seed; keep first PASS row.
    dedup: dict[tuple[str, int], dict] = {}
    for row in rows:
        dedup.setdefault((row["prompt_id"], int(row["seed_idx"])), row)
    shard_rows = [
        row
        for row in sorted(dedup.values(), key=lambda r: int(r["row_index"]))
        if int(row["row_index"]) % args.num_shards == args.shard_index
    ]
    if args.max_rows > 0:
        shard_rows = shard_rows[: args.max_rows]
    done = existing_keys(score_path)
    for row in shard_rows:
        key = (row["prompt_id"], int(row["seed_idx"]))
        if key in done:
            continue
        started = time.time()
        out = {
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "prompt_id": row["prompt_id"],
            "prompt_index": row["prompt_index"],
            "row_index": row["row_index"],
            "seed_idx": row["seed_idx"],
            "seed": row["seed"],
            "vocal_stratum": row.get("vocal_stratum", ""),
            "stratum": row.get("stratum", ""),
            "threshold": THR,
            "audio_path": row["output_path"],
            "ok": False,
            "error": "",
        }
        try:
            scored = score_one(Path(row["output_path"]), args.device)
            requested_vocal = 1 if row.get("vocal_stratum") == "vocal" else 0
            out.update(scored)
            out["type_correct"] = int(int(scored["present"]) == requested_vocal)
            out["ok"] = True
        except Exception as exc:  # noqa: BLE001 - exact traceback class belongs in ledger.
            out["error"] = f"{type(exc).__name__}: {exc}"
        out["elapsed_s"] = time.time() - started
        with score_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(out, sort_keys=True) + "\n")
        print(json.dumps(out, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
