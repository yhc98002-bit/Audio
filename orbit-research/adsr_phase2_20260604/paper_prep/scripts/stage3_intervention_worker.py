#!/usr/bin/env python3
"""Stage 3 intervention-decomposition generation worker.

This is a publication-prep worker for ADSR_Publication_ToDo_Guide.md §2/N1.
It is sharded, append-only, and resumable by `(prompt_id, condition, seed_idx)`.
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import os
import sys
import time
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

VOCAL_CONDITIONS = ("vocal_guidance", "vocal_hints", "vocal_both")
INSTR_CONDITIONS = ("instr_text", "instr_sampler", "instr_both")
COND_IDX = {
    "vocal_guidance": 1,
    "vocal_hints": 2,
    "vocal_both": 3,
    "instr_text": 4,
    "instr_sampler": 5,
    "instr_both": 6,
}


def load_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def default_hint(prompt):
    if (prompt.structure_hint or "").strip():
        return prompt
    return dataclasses.replace(prompt, structure_hint="[verse]\n[chorus]\n[verse]\n[chorus]")


def apply_condition(prompt, condition: str):
    extras = {}
    cfg = 5.0
    if condition in ("vocal_guidance", "vocal_both"):
        extras.update({"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5})
    if condition in ("vocal_hints", "vocal_both"):
        prompt = default_hint(prompt)
    if condition in ("instr_text", "instr_both"):
        anti = ", pure instrumental, no vocals, no singing, no voice"
        if condition == "instr_both":
            anti = (", pure instrumental backing track, absolutely no vocals, no singing, "
                    "no voice, no choir, no rap, no spoken word, no humming, no vocal chops")
        prompt = dataclasses.replace(prompt, text=prompt.text.rstrip(". ") + anti, lyrics=None)
    if condition in ("instr_sampler", "instr_both"):
        cfg = 7.5
    return prompt, extras, cfg


def build_tasks(vocal_prompts: Path, instr_prompts: Path, n_seeds: int):
    tasks = []
    for row in load_jsonl(vocal_prompts):
        for condition in VOCAL_CONDITIONS:
            for seed_idx in range(n_seeds):
                tasks.append((row, condition, seed_idx))
    for row in load_jsonl(instr_prompts):
        for condition in INSTR_CONDITIONS:
            for seed_idx in range(n_seeds):
                tasks.append((row, condition, seed_idx))
    return tasks


def stratified_limit(tasks, limit: int):
    """Pick a smoke subset round-robin across conditions and prompt ids."""
    if not limit or len(tasks) <= limit:
        return tasks
    buckets = {cond: [] for cond in COND_IDX}
    for task in tasks:
        row, condition, seed_idx = task
        buckets[condition].append(task)
    for cond in buckets:
        buckets[cond].sort(key=lambda t: (t[2], int(t[0]["prompt_index"])))
    out = []
    order = list(VOCAL_CONDITIONS) + list(INSTR_CONDITIONS)
    while len(out) < limit and any(buckets.values()):
        for cond in order:
            if buckets[cond]:
                out.append(buckets[cond].pop(0))
                if len(out) == limit:
                    break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vocal-prompts", required=True)
    ap.add_argument("--instr-prompts", required=True)
    ap.add_argument("--n-seeds", type=int, default=64)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="stage3_intervention")
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

    tasks = build_tasks(Path(args.vocal_prompts), Path(args.instr_prompts), args.n_seeds)
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
                done.add((rec.get("prompt_id"), rec.get("condition"), rec.get("seed_idx")))

    ledger_path = ledgers / f"{args.tag}_w{args.worker_index}.jsonl"
    scratch = Path(f"/dev/shm/stage3_{args.tag}_{args.worker_index}")
    scratch.mkdir(parents=True, exist_ok=True)

    model = AceStepModel()
    gate = GateLabeler("cuda")
    t0 = time.time()
    n_written = 0
    with ledger_path.open("a") as led:
        for row, condition, seed_idx in mine:
            key = (row["prompt_id"], condition, seed_idx)
            if key in done:
                continue
            cond_i = COND_IDX[condition]
            seed = NEW_SEED_BASE + int(row["prompt_index"]) * 100000 + cond_i * 1000 + seed_idx
            prompt = _prompt_from_row(row)
            prompt, extras, cfg = apply_condition(prompt, condition)
            requested_vocal = int(row.get("vocal_stratum") == "vocal")
            rec = {
                "prompt_id": row["prompt_id"],
                "prompt_index": row["prompt_index"],
                "source": row.get("source"),
                "condition": condition,
                "condition_index": cond_i,
                "requested_vocal": requested_vocal,
                "seed_idx": seed_idx,
                "seed": seed,
                "cfg_scale": cfg,
                "extras": extras,
                "worker_index": args.worker_index,
            }
            try:
                seed_everything(seed)
                res = model.sample(
                    prompt,
                    seed=seed,
                    cfg_scale=cfg,
                    steps=30,
                    return_trajectory=False,
                    extras={**BASE_EXTRAS, **extras},
                )
                ratio, near_silent = gate.ratio(res.waveform, res.sample_rate)
                present = int((ratio >= THR) and not near_silent)
                kd = keep_root / condition / row["prompt_id"]
                kd.mkdir(parents=True, exist_ok=True)
                tmp = scratch / f"{row['prompt_id']}_{condition}_{seed_idx}.wav"
                flac = kd / f"{condition}_s{seed_idx}_{seed}.flac"
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
            if n_written % 10 == 0:
                print(f"w{args.worker_index} {args.tag}: wrote={n_written}", flush=True)
    print(f"STAGE3_DONE worker={args.worker_index} tag={args.tag} wrote={n_written}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
