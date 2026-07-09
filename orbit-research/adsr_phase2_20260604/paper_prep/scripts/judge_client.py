#!/usr/bin/env python3
"""ADSR judge client — qwen3.5-omni-plus via DashScope (OpenAI-compatible).

Implements ADSR_Publication_ToDo_Guide.md §3:
  A' (presence): "does this clip contain human singing/voice" — 3 calls/clip,
      majority vote, abstains logged.
  B' (quality A/B): pair judged in BOTH orders, 3 questions per call,
      fixed decoding, ties/refusals logged.
  smoke: 10 known clips (5 vocal / 5 instrumental), require 10/10 presence.

Runs on the login node only (compute nodes have no internet). Raw
request/response records are appended as JSONL under paper_prep/judge_raw/
— that pinned log is the citable artifact (model string, endpoint, date,
decoding settings all recorded per record).

Key loading order: $DASHSCOPE_API_KEY, then <script_dir>/.dashscope_key.
The key must never be committed to any release tree (guide §1 C1).
"""

import argparse
import base64
import concurrent.futures as cf
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = os.environ.get("DASHSCOPE_MODEL", "qwen3.5-omni-plus")
ROOT = Path("/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion")
JUDGE_RAW = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep/judge_raw"

import requests

_log_lock = threading.Lock()


def load_key():
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not key:
        keyfile = Path(__file__).resolve().parent / ".dashscope_key"
        if keyfile.exists():
            key = keyfile.read_text().strip()
    if not key:
        sys.exit("No DASHSCOPE_API_KEY in env and no .dashscope_key file")
    return key


def sha256_file(path, blocksize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(blocksize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def transcode_to_wav_b64(path, sr, channels):
    """FLAC/anything -> WAV (given sr/channels) -> base64 string."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmpname = tmp.name
    try:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", str(path),
            "-ar", str(sr), "-ac", str(channels),
            "-c:a", "pcm_s16le", tmpname,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        data = Path(tmpname).read_bytes()
        return base64.b64encode(data).decode("ascii"), len(data)
    finally:
        Path(tmpname).unlink(missing_ok=True)


def audio_part(b64, fmt="wav"):
    return {
        "type": "input_audio",
        "input_audio": {"data": f"data:audio/{fmt};base64,{b64}", "format": fmt},
    }


def call_omni(api_key, content_parts, max_retries=6, timeout=300):
    """One streaming chat call, temperature 0. Returns (text, usage, meta)."""
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content_parts}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "modalities": ["text"],
        "temperature": 0.0,
        "seed": 20260706,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_err = None
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=body,
                                 stream=True, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {resp.status_code}: {resp.text[:500]}"
                time.sleep(min(2 ** attempt * 2, 60))
                continue
            if resp.status_code != 200:
                return None, None, {
                    "error": f"HTTP {resp.status_code}: {resp.text[:2000]}",
                    "attempt": attempt, "latency_s": round(time.time() - t0, 2),
                }
            text_parts, usage = [], None
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8", "replace")
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                for ch in chunk.get("choices", []):
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        text_parts.append(delta["content"])
            return "".join(text_parts), usage, {
                "attempt": attempt, "latency_s": round(time.time() - t0, 2),
            }
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = repr(e)
            time.sleep(min(2 ** attempt * 2, 60))
    return None, None, {"error": f"retries exhausted: {last_err}",
                        "attempt": max_retries, "latency_s": None}


def log_raw(run_name, record):
    JUDGE_RAW.mkdir(parents=True, exist_ok=True)
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    record.setdefault("model", MODEL)
    record.setdefault("endpoint", ENDPOINT)
    record.setdefault("decoding", {"temperature": 0.0, "seed": 20260706,
                                   "stream": True, "modalities": ["text"]})
    path = JUDGE_RAW / f"{run_name}.jsonl"
    with _log_lock:
        with open(path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


APRIME_QUESTION = (
    "Listen to the audio clip carefully.\n"
    "Question: does this clip contain any human singing or human voice "
    "(including spoken word, rap, humming, vocal chops, or choir)?\n"
    "Answer on the FIRST line with exactly one word: yes, no, or unsure.\n"
    "On the SECOND line give a one-sentence reason."
)


def parse_presence(text):
    if not text:
        return "abstain"
    first = text.strip().splitlines()[0].strip().lower()
    first = re.sub(r"[^a-z]", "", first)
    if first in ("yes", "no", "unsure"):
        return first
    low = text.strip().lower()
    for tok in ("yes", "no", "unsure"):
        if low.startswith(tok):
            return tok
    return "abstain"


def judge_presence_clip(api_key, clip_path, run_name, n_calls=3,
                        sr=16000, channels=1, extra_meta=None):
    """A' protocol for one clip. Returns dict with per-call and majority."""
    clip_path = Path(clip_path)
    sha = sha256_file(clip_path)
    b64, nbytes = transcode_to_wav_b64(clip_path, sr, channels)
    votes = []
    for i in range(n_calls):
        text, usage, meta = call_omni(
            api_key, [audio_part(b64), {"type": "text", "text": APRIME_QUESTION}])
        parsed = parse_presence(text)
        votes.append(parsed)
        rec = {
            "protocol": "aprime", "run": run_name, "call_index": i,
            "clip_path": str(clip_path), "clip_sha256": sha,
            "transcode": {"sr": sr, "channels": channels, "format": "wav",
                          "wav_bytes": nbytes},
            "question": APRIME_QUESTION, "response_text": text,
            "parsed": parsed, "usage": usage, **meta,
        }
        if extra_meta:
            rec["clip_meta"] = extra_meta
        log_raw(run_name, rec)
    counts = {v: votes.count(v) for v in set(votes)}
    yes, no = votes.count("yes"), votes.count("no")
    if yes > n_calls // 2:
        majority = "yes"
    elif no > n_calls // 2:
        majority = "no"
    else:
        majority = "abstain"
    return {"clip_path": str(clip_path), "clip_sha256": sha, "votes": votes,
            "vote_counts": counts, "majority": majority}


BPRIME_QUESTION_TMPL = (
    "You will hear two music clips, Clip A then Clip B.{req_line}\n"
    "Answer three questions. Reply with EXACTLY three lines:\n"
    "Q1: A, B, or tie   (which clip do you prefer overall?)\n"
    "Q2: A, B, or tie   (which clip matches the request better?)\n"
    "Q3: A, B, or tie   (which clip has fewer audio flaws, e.g. artifacts, "
    "glitches, muddiness, clipping?)\n"
    "Format each line as 'Q1: <answer>' etc. After the three lines, add one "
    "short sentence of justification."
)


def parse_ab(text):
    out = {"q1": "refusal", "q2": "refusal", "q3": "refusal"}
    if not text:
        return out
    for q in ("q1", "q2", "q3"):
        m = re.search(rf"{q}\s*[::]\s*(a|b|tie)\b", text, re.IGNORECASE)
        if m:
            out[q] = m.group(1).lower()
    return out


def judge_pair(api_key, path_a, path_b, pair_id, run_name, order_tag,
               request_text=None, sr=24000, channels=1):
    """One B' call: two clips, three questions."""
    sha_a, sha_b = sha256_file(path_a), sha256_file(path_b)
    b64a, na = transcode_to_wav_b64(path_a, sr, channels)
    b64b, nb = transcode_to_wav_b64(path_b, sr, channels)
    req_line = (f"\nThe generation request was: \"{request_text}\""
                if request_text else "")
    question = BPRIME_QUESTION_TMPL.format(req_line=req_line)
    parts = [
        {"type": "text", "text": "Clip A:"}, audio_part(b64a),
        {"type": "text", "text": "Clip B:"}, audio_part(b64b),
        {"type": "text", "text": question},
    ]
    text, usage, meta = call_omni(api_key, parts)
    parsed = parse_ab(text)
    log_raw(run_name, {
        "protocol": "bprime", "run": run_name, "pair_id": pair_id,
        "order": order_tag, "clip_a": str(path_a), "clip_b": str(path_b),
        "sha_a": sha_a, "sha_b": sha_b,
        "transcode": {"sr": sr, "channels": channels, "format": "wav",
                      "wav_bytes": [na, nb]},
        "question": question, "response_text": text, "parsed": parsed,
        "usage": usage, **meta,
    })
    return {"pair_id": pair_id, "order": order_tag, "parsed": parsed,
            "raw_ok": text is not None}


def cmd_smoke(args):
    """§3a smoke: 10 clips, expect 10/10 presence + sane rationale."""
    api_key = load_key()
    rows = list(csv.DictReader(open(args.manifest)))
    results, failures = [], []
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(judge_presence_clip, api_key, r["clip_path"],
                          args.run_name, 3, 16000, 1,
                          {"expected": r["expected"]}): r for r in rows}
        for fut in cf.as_completed(futs):
            r = futs[fut]
            res = fut.result()
            res["expected"] = r["expected"]
            res["correct"] = res["majority"] == r["expected"]
            results.append(res)
            if not res["correct"]:
                failures.append(res)
    n_ok = sum(r["correct"] for r in results)
    verdict = "PASS" if n_ok == len(results) else "FAIL"
    summary = {"protocol": "aprime_smoke", "run": args.run_name,
               "n_clips": len(results), "n_correct": n_ok,
               "verdict": verdict, "results": results}
    log_raw(args.run_name, summary)
    print(json.dumps(summary, indent=2))
    sys.exit(0 if verdict == "PASS" else 1)


def cmd_aprime(args):
    api_key = load_key()
    rows = list(csv.DictReader(open(args.manifest)))
    if args.limit:
        rows = rows[: args.limit]
    done = set()
    out_path = Path(args.out)
    if out_path.exists():
        for line in open(out_path):
            try:
                done.add(json.loads(line)["clip_path"])
            except (json.JSONDecodeError, KeyError):
                pass
    todo = [r for r in rows if r[args.path_col] not in done]
    print(f"A': {len(rows)} rows, {len(done)} already done, {len(todo)} to judge",
          file=sys.stderr)
    lock = threading.Lock()
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(judge_presence_clip, api_key, r[args.path_col],
                          args.run_name, 3, 16000, 1,
                          {k: r[k] for k in r if k != args.path_col}): r
                for r in todo}
        for fut in cf.as_completed(futs):
            res = fut.result()
            with lock:
                with open(out_path, "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")


def cmd_bprime(args):
    api_key = load_key()
    rows = list(csv.DictReader(open(args.manifest)))
    if args.limit:
        rows = rows[: args.limit]
    done = set()
    out_path = Path(args.out)
    if out_path.exists():
        for line in open(out_path):
            try:
                j = json.loads(line)
                done.add((j["pair_id"], j["order"]))
            except (json.JSONDecodeError, KeyError):
                pass
    jobs = []
    for r in rows:
        for order in ("ab", "ba"):
            if (r["pair_id"], order) in done:
                continue
            a, b = ((r["path_a"], r["path_b"]) if order == "ab"
                    else (r["path_b"], r["path_a"]))
            jobs.append((r["pair_id"], order, a, b, r.get("request_text")))
    print(f"B': {len(rows)} pairs, {len(jobs)} calls to make", file=sys.stderr)
    lock = threading.Lock()
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(judge_pair, api_key, a, b, pid, args.run_name,
                          order, req, args.sr, args.channels)
                for pid, order, a, b, req in jobs]
        for fut in cf.as_completed(futs):
            res = fut.result()
            with lock:
                with open(out_path, "a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("smoke", help="10-clip judge smoke (§3a)")
    ps.add_argument("--manifest", required=True,
                    help="CSV with clip_path,expected columns")
    ps.add_argument("--run-name", default="smoke_10clip")
    ps.add_argument("--concurrency", type=int, default=4)
    ps.set_defaults(func=cmd_smoke)

    pa = sub.add_parser("aprime", help="A' presence judging over a manifest")
    pa.add_argument("--manifest", required=True)
    pa.add_argument("--path-col", default="clip_path")
    pa.add_argument("--out", required=True, help="results JSONL (resumable)")
    pa.add_argument("--run-name", required=True)
    pa.add_argument("--concurrency", type=int, default=6)
    pa.add_argument("--limit", type=int, default=0)
    pa.set_defaults(func=cmd_aprime)

    pb = sub.add_parser("bprime", help="B' pairwise A/B judging")
    pb.add_argument("--manifest", required=True,
                    help="CSV with pair_id,path_a,path_b[,request_text]")
    pb.add_argument("--out", required=True)
    pb.add_argument("--run-name", required=True)
    pb.add_argument("--concurrency", type=int, default=4)
    pb.add_argument("--sr", type=int, default=24000)
    pb.add_argument("--channels", type=int, default=1)
    pb.add_argument("--limit", type=int, default=0)
    pb.set_defaults(func=cmd_bprime)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
