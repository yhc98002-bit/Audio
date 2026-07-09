"""D4 — segmentation + Demucs + Whisper smoke (DIAGNOSTIC_EXPERIMENT_PLAN §2 D4).

Required before Phase A because R3 robust-BoN, R6 robust-elite-SFT, R7 Flow-DPO, and R8
Outcome-GRPO all consume Whisper-WER on Demucs vocal stems and MERT section reward.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import torch

from mprm.data.audio_io import load_audio
from mprm.data.prompts import Prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="path to a known-good vocal song wav")
    parser.add_argument("--lyrics", default=None, help="optional reference lyrics for WER check")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    waveform, sr = load_audio(args.audio)
    duration = float(waveform.shape[-1] / sr)
    prompt = Prompt(
        prompt_id="d4_smoke",
        text="d4 smoke test",
        lyrics=args.lyrics,
        structure_hint=None,
        duration_target=duration,
    )

    failures: list[str] = []

    # MERT segmentation reliability proxy
    try:
        from mprm.rewards.mert import MertReward
        mert = MertReward()
        emb = mert.embed(waveform, sr)
        n_windows = emb.shape[0]
        if n_windows < 2:
            failures.append(f"mert: too few windows ({n_windows}); duration {duration:.1f}s")
        else:
            print(f"mert: n_windows={n_windows} (target 2-8 per ~60s)")
    except Exception as e:  # noqa: BLE001
        failures.append(f"mert: {type(e).__name__}: {e}")

    # Demucs vocal-stem extraction
    vocal_stem: torch.Tensor | None = None
    vocal_sr = sr
    try:
        from mprm.rewards.demucs import DemucsVocalStem
        demucs = DemucsVocalStem()
        vocal_stem = demucs.extract_vocal(waveform, sr)
        vocal_sr = int(demucs._model.samplerate) if demucs._model else sr
        rms_db = 20 * (vocal_stem.float().abs().mean().clamp(min=1e-12)).log10().item()
        if rms_db < -50:
            failures.append(f"demucs: vocal stem near-silent (rms_db={rms_db:.1f})")
        else:
            print(f"demucs: vocal stem rms_db={rms_db:.1f}")
    except Exception as e:  # noqa: BLE001
        failures.append(f"demucs: {type(e).__name__}: {e}")

    # Whisper WER on Demucs stem (only if lyrics provided)
    if args.lyrics:
        try:
            from mprm.rewards.whisper_wer import WhisperWerReward
            whisper = WhisperWerReward(language=args.language)
            score = whisper.score(waveform, sr, prompt)
            print(f"whisper_wer: wer={score.raw.get('wer'):.3f} transcript=<{len(score.raw.get('transcript',''))} chars>")
            if score.raw.get("wer", 1.0) >= 1.0:
                failures.append("whisper: WER=1.0 (pure garbage transcript)")
        except Exception as e:  # noqa: BLE001
            failures.append(f"whisper: {type(e).__name__}: {e}")
    else:
        print("whisper: skipped (no --lyrics provided)")

    if failures:
        print("\nD4 FAIL with failures:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nD4 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
