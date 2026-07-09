#!/usr/bin/env python
"""P0.4 transcript pass — Whisper over EN-vocal early WAVs at σ∈{0.9,0.8,0.7}.

Reuses the production WhisperWerReward (Demucs vocal-stem separation + whisper large-v3 + the
exact WER normalization), so transcript-level early-lyric values are directly comparable to the
stored early `lyric_intelligibility` scores. Sharded across GPUs via --worker-index/--num-workers.
Resumable (skips keys already in the worker's output file).

Usage: CUDA_VISIBLE_DEVICES=g python scripts/phase0_whisper_pass.py --worker-index g --num-workers 8
Output: orbit-research/adsr_phase2_20260604/phase0/whisper_early/transcripts_w{g}.jsonl
"""
from __future__ import annotations
import argparse, glob, json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
MERGED = REPO / "runs/adsr_recollect_20260604_full01_merged"
OUT = REPO / "orbit-research/adsr_phase2_20260604/phase0/whisper_early"
SIGMAS = ["0.9", "0.8", "0.7"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-index", type=int, default=0)
    ap.add_argument("--num-workers", type=int, default=8)
    args = ap.parse_args()

    from mprm.data.audio_io import load_audio
    from mprm.rewards.whisper_wer import WhisperWerReward
    from scripts.collect_early_tweedie_validation import (_load_manifest, _load_prompt_rows,
                                                          _prompt_from_row)

    recs = []
    for f in sorted(glob.glob(str(MERGED / "shard0*" / "candidate_records.jsonl"))):
        for l in open(f):
            r = json.loads(l)
            if r.get("vocal_stratum") == "vocal" and r.get("language") == "en":
                recs.append(r)
    recs.sort(key=lambda r: (r["prompt_id"], r["candidate_index"]))
    master = _load_manifest(REPO / "orbit-research/EARLY_TWEEDIE_VALIDATION_512_PROMPTS.json")
    need = {r["prompt_id"] for r in recs}
    rows_by_id = _load_prompt_rows([m for m in master if m["prompt_id"] in need])
    prompts = {}
    for r in recs:
        pid = r["prompt_id"]
        if pid not in prompts:
            prompts[pid] = _prompt_from_row(rows_by_id[(str(r["prompt_source"]), pid)])

    tasks = []
    for r in recs:
        for sk in SIGMAS:
            ap_ = r.get(f"early_{sk}_audio_path")
            if ap_:
                tasks.append((r["prompt_id"], int(r["candidate_index"]), sk, ap_,
                              r.get(f"early_{sk}_lyric_intelligibility")))
    mine = tasks[args.worker_index::args.num_workers]
    OUT.mkdir(parents=True, exist_ok=True)
    out_f = OUT / f"transcripts_w{args.worker_index}.jsonl"
    done = set()
    if out_f.exists():
        for l in open(out_f):
            try:
                d = json.loads(l); done.add((d["prompt_id"], d["candidate_index"], d["sigma"]))
            except Exception:
                pass
    todo = [t for t in mine if (t[0], t[1], t[2]) not in done]
    print(f"worker {args.worker_index}/{args.num_workers}: {len(todo)} todo "
          f"({len(mine)-len(todo)} done)", flush=True)
    rm = WhisperWerReward(device="cuda")
    n = 0; t0 = time.time()
    with out_f.open("a") as fh:
        for pid, ci, sk, ap_, stored in todo:
            try:
                wav, sr = load_audio(REPO / ap_)
                sc = rm.score(wav, sr, prompts[pid])
                fh.write(json.dumps({"prompt_id": pid, "candidate_index": ci, "sigma": sk,
                                     "value": sc.value, "wer": sc.raw.get("wer"),
                                     "transcript": sc.raw.get("transcript"),
                                     "n_hyp": sc.raw.get("n_hyp"),
                                     "stored_early_value": stored}) + "\n")
            except Exception as e:
                fh.write(json.dumps({"prompt_id": pid, "candidate_index": ci, "sigma": sk,
                                     "error": f"{type(e).__name__}: {e}"}) + "\n")
            fh.flush(); n += 1
            if n % 50 == 0:
                rate = n / max(time.time() - t0, 1)
                print(f"w{args.worker_index}: {n}/{len(todo)} ({rate:.2f}/s)", flush=True)
    print(f"WORKER_DONE w{args.worker_index} n={n}", flush=True)


if __name__ == "__main__":
    main()
