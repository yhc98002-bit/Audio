#!/usr/bin/env python3
"""N2 population retry-map generation worker.

This is a no-intervention ACE-Step retry map: selected held-out prompts x seeds,
Demucs-ratio vocal/instrumental labeling, and kept FLAC outputs. It is sharded,
append-only, and resumable by `(prompt_id, seed_idx)`.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path


REPO = Path(os.environ.get("MPRM_REPO_ROOT", Path(__file__).resolve().parents[4])).resolve()
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from mprm.common.thresholds import VOCAL_PRESENCE_THRESHOLD

NEW_SEED_BASE = 2030000000
THR = VOCAL_PRESENCE_THRESHOLD
BASE_EXTRAS = {
    "cfg_type": "apg",
    "guidance_interval": 0.5,
    "use_erg_tag": False,
    "use_erg_lyric": False,
    "use_erg_diffusion": False,
}


def load_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def stratified_limit(tasks, limit: int):
    """Pick smoke tasks round-robin across violation bins."""
    if not limit or len(tasks) <= limit:
        return tasks
    buckets = defaultdict(list)
    for row, seed_idx in tasks:
        buckets[int(row["baseline_violation_count_8"])].append((row, seed_idx))
    for bucket in buckets.values():
        bucket.sort(key=lambda t: (t[1], int(t[0]["prompt_index"])))
    out = []
    order = sorted(buckets)
    while len(out) < limit and any(buckets.values()):
        for k in order:
            if buckets[k]:
                out.append(buckets[k].pop(0))
                if len(out) == limit:
                    break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--n-seeds", type=int, default=128)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="population_retry_n128")
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=1)
    ap.add_argument("--limit-total-tasks", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.out)
    ledgers = out / "ledgers"
    keep_root = out / "keep" / args.tag
    ledgers.mkdir(parents=True, exist_ok=True)
    keep_root.mkdir(parents=True, exist_ok=True)

    import soundfile as sf
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.batch3_online_harness import GateLabeler
    from scripts.collect_early_tweedie_validation import _prompt_from_row

    rows = list(load_jsonl(Path(args.prompts)))
    tasks = [(row, seed_idx) for row in rows for seed_idx in range(args.n_seeds)]
    tasks = stratified_limit(tasks, args.limit_total_tasks)
    mine = tasks[args.worker_index::args.num_workers]

    done = set()
    for ledger_path in glob.glob(str(ledgers / f"{args.tag}_w*.jsonl")):
        with open(ledger_path) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                done.add((rec.get("prompt_id"), rec.get("seed_idx")))

    ledger_path = ledgers / f"{args.tag}_w{args.worker_index}.jsonl"
    scratch = Path(f"/dev/shm/pop_retry_{args.tag}_{args.worker_index}")
    scratch.mkdir(parents=True, exist_ok=True)

    model = AceStepModel()
    gate = GateLabeler("cuda")
    t0 = time.time()
    n_written = 0
    with ledger_path.open("a") as led:
        for row, seed_idx in mine:
            key = (row["prompt_id"], seed_idx)
            if key in done:
                continue
            seed = NEW_SEED_BASE + int(row["prompt_index"]) * 100000 + seed_idx
            prompt = _prompt_from_row(row)
            requested_vocal = int(row.get("vocal_stratum") == "vocal")
            rec = {
                "prompt_id": row["prompt_id"],
                "prompt_index": row["prompt_index"],
                "source": row.get("source"),
                "condition": "none",
                "requested_vocal": requested_vocal,
                "vocal_stratum": row.get("vocal_stratum"),
                "baseline_violation_count_8": row.get("baseline_violation_count_8"),
                "baseline_clean_count_8": row.get("baseline_clean_count_8"),
                "baseline_present_count_8": row.get("baseline_present_count_8"),
                "selection_bin": row.get("selection_bin"),
                "selection_rank": row.get("selection_rank"),
                "seed_idx": seed_idx,
                "seed": seed,
                "cfg_scale": 5.0,
                "extras": {},
                "worker_index": args.worker_index,
            }
            try:
                seed_everything(seed)
                res = model.sample(
                    prompt,
                    seed=seed,
                    cfg_scale=5.0,
                    steps=30,
                    return_trajectory=False,
                    extras=BASE_EXTRAS,
                )
                ratio, near_silent = gate.ratio(res.waveform, res.sample_rate)
                present = int((ratio >= THR) and not near_silent)
                kd = keep_root / row["prompt_id"]
                kd.mkdir(parents=True, exist_ok=True)
                tmp = scratch / f"{row['prompt_id']}_{seed_idx}.wav"
                flac = kd / f"none_s{seed_idx}_{seed}.flac"
                save_audio(tmp, res.waveform, res.sample_rate)
                data, sr = sf.read(str(tmp))
                sf.write(str(flac), data, sr, format="FLAC")
                tmp.unlink(missing_ok=True)
                rec.update({
                    "ok": True,
                    "sample_rate": res.sample_rate,
                    "vocal_energy_ratio": round(float(ratio), 6),
                    "near_silent": bool(near_silent),
                    "present": present,
                    "type_correct": int(present == requested_vocal),
                    "flac": str(flac.relative_to(out)),
                    "wall_elapsed_s": round(time.time() - t0, 2),
                })
            except Exception as exc:  # noqa: BLE001
                rec.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            led.write(json.dumps(rec, ensure_ascii=False) + "\n")
            led.flush()
            n_written += 1
            if n_written % 25 == 0:
                print(f"w{args.worker_index} {args.tag}: wrote={n_written}", flush=True)
    print(f"POP_RETRY_DONE worker={args.worker_index} tag={args.tag} wrote={n_written}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
