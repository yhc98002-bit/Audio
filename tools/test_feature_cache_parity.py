"""Feature-cache parity test per FINAL_REVISION_CRITIC.md #16.

Compares Whisper-WER (and any other cache-integrated axis) outputs on 32 audio
samples with vs without AudioFeatureCache enabled. Tolerance: |Δ| ≤ 1e-6 per
reward axis (exact float match expected since cache returns the same tensor
object; any larger diff indicates a bug).

If parity FAILS → cache must be disabled. Per critique #16:
  "if scores change outside tolerance, cache optimization is disabled."

Usage:
    python tools/test_feature_cache_parity.py --n-samples 32 --device cuda:0
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import torch
import torchaudio

from mprm.data.prompts import load_prompts
from mprm.rewards.feature_cache import AudioFeatureCache
from mprm.rewards.whisper_wer import WhisperWerReward


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", default="configs/prompts/held_out.jsonl")
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--n-samples", type=int, default=32)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="orbit-research/FEATURE_CACHE_PARITY_TEST.json")
    args = parser.parse_args()

    prompts = load_prompts(args.prompts)
    vocal = [p for p in prompts if p.lyrics and len(p.lyrics.strip()) > 5]
    if len(vocal) < args.n_samples:
        print(f"Only {len(vocal)} vocal prompts; need {args.n_samples}.")
        return 2

    # Pick first n_samples vocal prompts
    selected = vocal[: args.n_samples]
    print(f"Selected {len(selected)} vocal prompts for parity test")

    # Pre-load 1 seed of audio per prompt from runs/r0_base/held_out/seed0/
    audios: list[tuple] = []
    runs_root = Path(args.runs_root)
    for p in selected:
        wav_path = runs_root / "r0_base" / "held_out" / "seed0" / f"{p.prompt_id}_seed0.wav"
        if not wav_path.exists():
            print(f"  ⚠ missing {wav_path}; skipping")
            continue
        waveform, sr = torchaudio.load(str(wav_path))
        audios.append((p, waveform, sr))
    print(f"Loaded {len(audios)} audio files")

    print(f"\nInitializing WhisperWerReward (device={args.device})...")
    rewarder = WhisperWerReward(model_size="large-v3", device=args.device, separate_vocals=True)

    # Pre-warm so timing comparison is fair
    print("Warm-up score on first audio...")
    p, w, sr = audios[0]
    _ = rewarder.score(w, sr, p)

    # Run no-cache
    print("\nNo-cache run...")
    t0 = time.time()
    no_cache_scores: list[float] = []
    for i, (p, w, sr) in enumerate(audios):
        s = rewarder.score(w, sr, p)
        no_cache_scores.append(s.value)
        if i % 8 == 0:
            print(f"  [{i+1}/{len(audios)}] {p.prompt_id}: value={s.value:.6f}")
    t_nocache = time.time() - t0
    print(f"No-cache total: {t_nocache:.1f}s, mean per-sample: {t_nocache/len(audios):.2f}s")

    # Run with cache. Note: cache is session-scoped, so create one per audio.
    # For Whisper-WER alone, cache benefit comes from caching demucs_vocal_stem
    # across multiple score() calls on the same audio — which for a single
    # axis does NOT happen. The expected per-axis speedup is 0 for single-axis
    # use; the win is across multiple axes scoring the same audio.
    #
    # So this parity test is primarily checking CORRECTNESS (no score drift),
    # not speed. Speed benefit emerges in Phase B/C/D when all 4 reward axes
    # are scored on each audio.
    print("\nWith-cache run...")
    t0 = time.time()
    cache_scores: list[float] = []
    for i, (p, w, sr) in enumerate(audios):
        cache = AudioFeatureCache(waveform=w, sample_rate=sr)
        # Score twice in succession on same audio to test cache hit
        s1 = rewarder.score(w, sr, p, cache=cache)
        s2 = rewarder.score(w, sr, p, cache=cache)
        if abs(s1.value - s2.value) > args.tolerance:
            print(f"  ⚠ self-inconsistency: {s1.value} vs {s2.value} (Δ={abs(s1.value-s2.value):.2e})")
        cache_scores.append(s1.value)
        cs = cache.stats()
        if i == 0:
            print(f"  cache stats sample 0: hits={cs['hits']} misses={cs['misses']} features={cs['feature_names']}")
        if i % 8 == 0:
            print(f"  [{i+1}/{len(audios)}] {p.prompt_id}: value={s1.value:.6f} (cache hits={cs['hits']})")
    t_cache = time.time() - t0
    print(f"With-cache total: {t_cache:.1f}s, mean per-sample (×2 scores): {t_cache/(2*len(audios)):.2f}s")

    # Parity check
    print("\n=== Parity check ===")
    deltas = [abs(a - b) for a, b in zip(no_cache_scores, cache_scores)]
    max_delta = max(deltas)
    n_violations = sum(1 for d in deltas if d > args.tolerance)
    print(f"  max |Δ| = {max_delta:.2e} (tolerance {args.tolerance:.2e})")
    print(f"  violations: {n_violations}/{len(deltas)}")

    parity_passed = n_violations == 0
    out_data = {
        "test_name": "feature_cache_parity_v1",
        "axis": "whisper_wer (lyric_intelligibility)",
        "n_samples": len(audios),
        "tolerance": args.tolerance,
        "max_abs_delta": float(max_delta),
        "n_violations": n_violations,
        "parity_passed": parity_passed,
        "no_cache_mean_score": round(statistics.mean(no_cache_scores), 6),
        "cache_mean_score": round(statistics.mean(cache_scores), 6),
        "no_cache_wall_time_s": round(t_nocache, 1),
        "with_cache_wall_time_s": round(t_cache, 1),
        "note": "Cache speedup is expected to emerge in Phase B/C/D when all 4 reward axes are scored on each audio. Single-axis run has no inherent speedup (cache miss on every call). Parity (correctness) is the primary check here.",
        "per_sample_deltas": [round(d, 8) for d in deltas],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out_data, f, indent=2)

    if parity_passed:
        print(f"\n✅ Parity PASS — cache safe to enable. Output: {args.out}")
        return 0
    else:
        print(f"\n❌ Parity FAIL — DO NOT enable cache. Investigate. Output: {args.out}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
