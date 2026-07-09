"""Measure σ_WER per FINAL_REVISION_CRITIC.md #10.

σ_WER = "the per-prompt Whisper-WER measurement noise estimated from 3 repeat-runs
of base ACE-Step on 32-prompt subset". Used as the ε scale in Phase D A2
(lyric-guard tradeoff check), and may be referenced by Phase D ablation cells
under METHOD_SPEC §5.4 ε_lyric.

Approach:
  1. Take 32 stratified VOCAL prompts (non-empty lyrics) from held_out.
  2. For each prompt, use the 3 existing r0_base seed audios from
     runs/r0_base/held_out/seed{0,1,2}/<prompt_id>_seed<N>.wav.
     (No fresh sampling — reuses the 3 repeat-runs already in Phase A.)
  3. WhisperWerReward (with Demucs vocal-stem separation) → 96 WER scores.
  4. Per-prompt σ_seed = std(WER seed 0, 1, 2).
  5. Aggregate σ_WER = mean(per-prompt σ_seed), median, min, max.
  6. Write orbit-research/SIGMA_WER_MEASUREMENT.json.

Cost: ~5-10 GPU-h on single GPU; with 8-GPU parallelism via simple multi-process
distribution on prompt × seed, ~30-50 min wall.

Usage:
    python tools/measure_sigma_wer.py --n-prompts 32 --out orbit-research/SIGMA_WER_MEASUREMENT.json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

import torch
import torchaudio

from mprm.data.prompts import Prompt, load_prompts
from mprm.rewards.whisper_wer import WhisperWerReward


def select_32_stratified_vocal(prompts: list[Prompt], n: int = 32, seed: int = 42) -> list[Prompt]:
    """Pick n vocal prompts (non-empty lyrics) stratified by genre + lyric density."""
    vocal = [p for p in prompts if p.lyrics and len(p.lyrics.strip()) > 5]
    if len(vocal) < n:
        raise RuntimeError(f"Only {len(vocal)} vocal prompts; need {n}")

    # Stratify by genre group (from strata) + by lyric length quartile
    def bucket(p: Prompt) -> tuple:
        genre = p.strata.get("genre_group", "unknown") if isinstance(p.strata, dict) else "unknown"
        l = len(p.lyrics or "")
        if l < 50:
            bucket = "short"
        elif l < 150:
            bucket = "med"
        else:
            bucket = "long"
        return (genre, bucket)

    from collections import defaultdict
    by_bucket = defaultdict(list)
    for p in vocal:
        by_bucket[bucket(p)].append(p)

    rng = random.Random(seed)
    for k in by_bucket:
        rng.shuffle(by_bucket[k])

    # Round-robin sample
    selected: list[Prompt] = []
    bucket_keys = list(by_bucket.keys())
    while len(selected) < n:
        added_this_pass = False
        for k in bucket_keys:
            if by_bucket[k] and len(selected) < n:
                selected.append(by_bucket[k].pop())
                added_this_pass = True
        if not added_this_pass:
            break
    return selected[:n]


def find_seed_audio(prompt_id: str, seed: int, runs_root: Path) -> Path | None:
    """Return Path to runs/r0_base/held_out/seed<N>/<prompt_id>_seed<N>.wav or None."""
    candidates = [
        runs_root / "r0_base" / "held_out" / f"seed{seed}" / f"{prompt_id}_seed{seed}.wav",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", default="configs/prompts/held_out.jsonl")
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--n-prompts", type=int, default=32)
    parser.add_argument("--n-seeds", type=int, default=3)
    parser.add_argument("--out", default="orbit-research/SIGMA_WER_MEASUREMENT.json")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--whisper-model", default="large-v3")
    args = parser.parse_args()

    prompts = load_prompts(args.prompts)
    print(f"Loaded {len(prompts)} held_out prompts")

    selected = select_32_stratified_vocal(prompts, n=args.n_prompts)
    print(f"Selected {len(selected)} vocal prompts (stratified)")
    for p in selected[:5]:
        print(f"  {p.prompt_id} strata={p.strata.get('genre_group','?') if isinstance(p.strata, dict) else '?'} lyric_len={len(p.lyrics)}")

    # Verify audio files exist
    runs_root = Path(args.runs_root)
    missing = []
    for p in selected:
        for s in range(args.n_seeds):
            wav = find_seed_audio(p.prompt_id, s, runs_root)
            if wav is None:
                missing.append((p.prompt_id, s))
    if missing:
        print(f"⚠ Missing {len(missing)} audio files; first few: {missing[:5]}")
        print("  Cannot proceed without all 3 seeds per prompt.")
        return

    # Init Whisper-WER (with Demucs vocal-stem separation)
    print(f"\nLoading WhisperWerReward (Whisper {args.whisper_model} + Demucs)...")
    rewarder = WhisperWerReward(model_size=args.whisper_model, device=args.device, separate_vocals=True)

    # Compute WER per (prompt, seed)
    per_prompt_wers: dict[str, list[float]] = {}
    n_total = len(selected) * args.n_seeds
    n_done = 0
    for p in selected:
        per_prompt_wers[p.prompt_id] = []
        for s in range(args.n_seeds):
            wav_path = find_seed_audio(p.prompt_id, s, runs_root)
            waveform, sr = torchaudio.load(str(wav_path))
            score = rewarder.score(waveform, sr, p)
            wer_value = float(score.value)
            per_prompt_wers[p.prompt_id].append(wer_value)
            n_done += 1
            print(f"  [{n_done:3d}/{n_total}] {p.prompt_id} seed{s}: WER={wer_value:.4f}")

    # Compute σ per prompt (std across seeds) + aggregate
    per_prompt_sigma: dict[str, float] = {}
    for pid, wers in per_prompt_wers.items():
        per_prompt_sigma[pid] = statistics.stdev(wers) if len(wers) >= 2 else 0.0

    sigmas = list(per_prompt_sigma.values())
    out_data = {
        "n_prompts": len(selected),
        "n_seeds": args.n_seeds,
        "whisper_model": args.whisper_model,
        "demucs_separation": True,
        "method": "per-prompt std(WER) across n_seeds repeat-runs of base ACE-Step, on existing held_out r0_base audio",
        "source_audio_provenance": "reused from runs/r0_base/held_out/seed{0,1,2}/ — no fresh sampling",
        "sigma_WER_aggregate": {
            "mean": round(statistics.mean(sigmas), 6),
            "median": round(statistics.median(sigmas), 6),
            "min": round(min(sigmas), 6),
            "max": round(max(sigmas), 6),
            "p25": round(statistics.quantiles(sigmas, n=4)[0], 6) if len(sigmas) >= 4 else None,
            "p75": round(statistics.quantiles(sigmas, n=4)[2], 6) if len(sigmas) >= 4 else None,
        },
        "per_prompt_wer": {pid: [round(w, 6) for w in ws] for pid, ws in per_prompt_wers.items()},
        "per_prompt_sigma": {pid: round(s, 6) for pid, s in per_prompt_sigma.items()},
        "recommended_epsilon": {
            "epsilon_0": 0.0,
            "epsilon_sigma_WER": round(statistics.mean(sigmas), 6),
            "epsilon_2sigma_WER": round(2 * statistics.mean(sigmas), 6),
            "note": "Phase D A2 lyric-guard tradeoff check uses ε ∈ {0, σ_WER} per FINAL_REVISION_CRITIC.md #10. ε=σ_WER means a lyric WER regression within measurement noise is tolerated.",
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(out_data, f, indent=2)
    print(f"\n✅ Wrote {out_path}")
    print(f"   σ_WER mean = {out_data['sigma_WER_aggregate']['mean']:.4f}")
    print(f"   σ_WER median = {out_data['sigma_WER_aggregate']['median']:.4f}")


if __name__ == "__main__":
    main()
