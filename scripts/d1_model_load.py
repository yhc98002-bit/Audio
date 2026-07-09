"""D1 — model checkpoint load + 1-sample smoke (DIAGNOSTIC_EXPERIMENT_PLAN.md §2 D1)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mprm.common.seeding import seed_everything
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["ace_step_v15", "sao_1_0"], required=True)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--out", default="papers/diagnostic/d1")
    args = parser.parse_args()
    seed_everything(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.model == "ace_step_v15":
        from mprm.inference.ace_step import AceStepModel
        checkpoint = args.checkpoint or "ace-step/ACE-Step-1.5"
        model = AceStepModel(checkpoint=checkpoint)
        prompt = Prompt(
            prompt_id="d1_ace_step",
            text="a melodic pop song with female vocals in C major, mid tempo, 60 BPM",
            lyrics="Sing a song of sunshine, dance through gentle rain.",
            structure_hint="verse-chorus-verse",
            duration_target=args.duration,
        )
    else:
        from mprm.inference.sao import StableAudioOpenModel
        checkpoint = args.checkpoint or "stabilityai/stable-audio-open-1.0"
        model = StableAudioOpenModel(checkpoint=checkpoint)
        prompt = Prompt(
            prompt_id="d1_sao",
            text="a calm ambient pad with soft synthesizers, no vocals",
            lyrics=None,
            structure_hint=None,
            duration_target=min(args.duration, 10.0),
        )

    try:
        result = model.sample(prompt, seed=args.seed)
    except Exception as e:  # noqa: BLE001
        print(f"D1 FAIL on {args.model}: {type(e).__name__}: {e}")
        print("Check checkpoint availability + tokenizer + tokenization + license.")
        return 1

    out_path = out_dir / f"d1_{args.model}_seed{args.seed}.wav"
    save_audio(out_path, result.waveform, result.sample_rate)
    rms_db = 20 * (result.waveform.float().abs().mean().clamp(min=1e-12)).log10().item()
    has_nan = bool(result.waveform.isnan().any() or result.waveform.isinf().any())
    print(f"D1 wrote: {out_path} (sr={result.sample_rate}, rms_db={rms_db:.1f}, has_nan={has_nan})")
    if has_nan or rms_db < -40:
        print("D1 FAIL: silent or NaN")
        return 1
    print("D1 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
