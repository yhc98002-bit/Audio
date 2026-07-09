"""D2 — reward harness smoke (DIAGNOSTIC_EXPERIMENT_PLAN §2 D2).

If `--audio` is given, score that file. Otherwise, generate a single base-policy sample
from the configured backbone (default: ACE-Step v1.5) and score it. This exercises the
harness end-to-end without requiring a separately-staged audio asset.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mprm.common.seeding import seed_everything
from mprm.data.audio_io import load_audio, save_audio
from mprm.data.prompts import Prompt


def _generate_test_audio(model_name: str, seed: int, out_dir: Path) -> tuple:
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_everything(seed)
    prompt = Prompt(
        prompt_id="d2_test",
        text="a calm acoustic guitar melody, no vocals",
        lyrics=None,
        structure_hint=None,
        duration_target=20.0,
    )
    if model_name == "ace_step_v15":
        from mprm.inference.ace_step import AceStepModel
        model = AceStepModel(checkpoint="ace-step/ACE-Step-1.5")
    else:
        from mprm.inference.sao import StableAudioOpenModel
        model = StableAudioOpenModel(checkpoint="stabilityai/stable-audio-open-1.0")
    result = model.sample(prompt, seed=seed)
    audio_path = out_dir / "d2_test.wav"
    save_audio(audio_path, result.waveform, result.sample_rate)
    return result.waveform, result.sample_rate, prompt, audio_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", default=None,
                        help="optional path to a test audio file; if omitted, one is generated")
    parser.add_argument("--prompt-text", default="ambient electronic music")
    parser.add_argument("--lyrics", default=None)
    parser.add_argument("--model", choices=["ace_step_v15", "sao_1_0"], default="ace_step_v15")
    parser.add_argument("--out-dir", default="papers/diagnostic/d2")
    args = parser.parse_args()

    if args.audio:
        waveform, sr = load_audio(args.audio)
        prompt = Prompt(
            prompt_id="d2", text=args.prompt_text, lyrics=args.lyrics,
            structure_hint=None, duration_target=float(waveform.shape[-1] / sr),
        )
    else:
        try:
            waveform, sr, prompt, audio_path = _generate_test_audio(
                args.model, seed=42, out_dir=Path(args.out_dir),
            )
            print(f"D2: generated {audio_path}")
        except Exception as e:  # noqa: BLE001
            print(f"D2 FAIL: cannot generate test audio ({e}); pass --audio to skip this step")
            return 1

    rewards_to_test = []
    failures: list[str] = []

    try:
        from mprm.rewards.clap import ClapReward
        rewards_to_test.append(("clap", ClapReward()))
    except Exception as e:  # noqa: BLE001
        failures.append(f"clap: {e}")

    for axis in ("PQ", "PC", "CE", "CU"):
        try:
            from mprm.rewards.audiobox import AudioboxReward
            rewards_to_test.append((f"audiobox_{axis}", AudioboxReward(target_axis=axis)))
        except Exception as e:  # noqa: BLE001
            failures.append(f"audiobox_{axis}: {e}")
            break

    if args.lyrics or (prompt.lyrics is not None):
        try:
            from mprm.rewards.whisper_wer import WhisperWerReward
            rewards_to_test.append(("whisper_wer", WhisperWerReward()))
        except Exception as e:  # noqa: BLE001
            failures.append(f"whisper_wer: {e}")

    try:
        from mprm.rewards.mert import MertReward
        rewards_to_test.append(("mert", MertReward()))
    except Exception as e:  # noqa: BLE001
        failures.append(f"mert: {e}")

    per_axis_scores: dict[str, float] = {}
    for name, model in rewards_to_test:
        try:
            score = model.score(waveform, sr, prompt)
            per_axis_scores[score.axis] = score.value
            print(f"{name}: axis={score.axis} value={score.value:.4f} raw_keys={list(score.raw.keys())}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{name}.score: {type(e).__name__}: {e}")
            print(f"{name}: FAIL {e}")

    # Exercise R_lcb end-to-end on a 2-perturbation subset.
    try:
        from mprm.rewards.perturbations import perturbation_set
        from mprm.rewards.probes import anti_hacking_probes
        from mprm.rewards.robust_lcb import robust_lcb
        clap_for_probe = next((m for _, m in rewards_to_test if isinstance(m, ClapReward)), None)
        probe = anti_hacking_probes(waveform, sr, prompt, clap=clap_for_probe)
        lcb = robust_lcb(waveform, sr, prompt,
                          reward_models=[m for _, m in rewards_to_test],
                          perturbations=perturbation_set(["identity", "crop"]),
                          probe_scores=probe,
                          lambda_probe={"silence_fraction": 0.0,
                                         "autocorr_repetition": 0.0,
                                         "off_prompt_distance": 0.0,
                                         "hf_artifact_score": 0.0},
                          beta_robust=0.5)
        print(f"r_lcb: value={lcb.value:.4f} mean_cells={lcb.mean_cells:.4f} std_cells={lcb.std_cells:.4f}")
    except Exception as e:  # noqa: BLE001
        failures.append(f"robust_lcb: {type(e).__name__}: {e}")

    if failures:
        print("\nD2 FAIL with failures:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nD2 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
