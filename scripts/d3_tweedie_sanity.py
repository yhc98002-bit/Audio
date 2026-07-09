"""D3 — Tweedie-clean reconstruction sanity (DIAGNOSTIC_EXPERIMENT_PLAN.md §2 D3).

For each prompt: sample with trajectory capture, then for K target σ checkpoints,
decode `â_k = D(TweedieClean(x_σ_k, σ_k))` and compare against `a_final` via
log-spectral distance + aesthetic-axis Spearman trend.

STOP-B-9 / audit-Round-4 update (2026-05-21):
- Uses `scheduler.sigmas[k]` (shift=3.0 applied) from the captured trajectory.
  NOT a raw uniform τ value (the prior implementation was algebraically wrong
  for ACE-Step — see `TWEEDIE_DERIVATION_NOTE.md` §3, §5, §8).
- `--candidate-formula` switches between the ACE-Step-paper Tweedie form and
  the rectified-flow Tweedie form. For the ACE-Step model, only one of these
  matches the source; the test is whether the paper form materially
  out-reconstructs the rectified-flow baseline.

σ TARGET VALUES (audit-Codex 2026-05-22): the default `--target-sigmas`
`0.5,0.3,0.1` are **magic-number placeholders pending Stage 0 calibration
sweep** (audit-Round-4 ADD 2026-05-21, cost-gated at 20 GPU-h). They come
from the theoretical-rectified-flow late regime (R2 #25) and are NOT
empirically calibrated against per-axis reliability data. Phase B.1
(64×3 calibration) will re-derive the optimal Stage-1 σ set.

CAPTURED-v REQUIREMENT (audit-Codex 2026-05-22 check [C]): the d3 sanity
REQUIRES the captured velocity (`trajectory_model_outputs[k]`) at each
checkpoint. Recomputing via `predict_velocity` is NOT a valid fallback —
it would mask trajectory-capture regressions. The script hard-fails if
captured v is missing.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

import torch

from mprm.common.seeding import seed_everything
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


# ----------------------------------------------------------- helpers


def log_spectral_distance(a: torch.Tensor, b: torch.Tensor) -> float:
    """LSD between two waveforms (mono-folded for the metric)."""
    a = a.mean(dim=0) if a.dim() == 2 else a
    b = b.mean(dim=0) if b.dim() == 2 else b
    if a.shape[-1] > b.shape[-1]:
        a = a[..., : b.shape[-1]]
    elif b.shape[-1] > a.shape[-1]:
        b = b[..., : a.shape[-1]]
    A = (
        torch.stft(a, n_fft=2048, hop_length=512, return_complex=True)
        .abs()
        .clamp_min(1e-8)
        .log()
    )
    B = (
        torch.stft(b, n_fft=2048, hop_length=512, return_complex=True)
        .abs()
        .clamp_min(1e-8)
        .log()
    )
    return float((A - B).pow(2).mean().sqrt())


def spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        return float("nan")

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        ranks = [0.0] * len(v)
        for r, idx in enumerate(order):
            ranks[idx] = float(r)
        return ranks

    rx, ry = rank(x), rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = (sum((a - mx) ** 2 for a in rx)) ** 0.5
    dy = (sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / (dx * dy + 1e-12)


def _read_derivation_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    import re

    text = path.read_text(encoding="utf-8")
    m = re.search(r"^STATUS:\s*(RESOLVED|AMBIGUOUS|TBD)\s*$", text, re.MULTILINE)
    return m.group(1) if m else "UNKNOWN"


def _pick_checkpoints_for_sigmas(
    target_sigmas: list[float], traj_sigmas: list[float]
) -> list[int]:
    """For each desired σ value, find the closest captured trajectory step.

    STOP-B-9 contract: `traj_sigmas[k]` is the shift-applied σ at step `k`
    (pulled from `scheduler.sigmas[step_index]`), NOT a raw uniform τ. We map
    a user-facing "I want σ ≈ 0.5" request to the nearest captured step.
    """
    indices = []
    for target in target_sigmas:
        best_k = min(range(len(traj_sigmas)), key=lambda k: abs(traj_sigmas[k] - target))
        indices.append(best_k)
    return indices


# ----------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["ace_step_v15", "sao_1_0"], default="ace_step_v15")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-prompts", type=int, default=16)
    parser.add_argument(
        "--out", default="papers/diagnostic/d3",
        help="Output directory (cleaned per --candidate-formula).",
    )
    parser.add_argument(
        "--mode",
        choices=["dev", "production"],
        default="production",
        help="production mode REQUIRES D3a derivation note STATUS=RESOLVED",
    )
    parser.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="Skip the D3a derivation-note gate (smoke / candidate-test only)",
    )
    parser.add_argument(
        "--candidate-formula",
        choices=["ace_step_paper", "rectified_flow"],
        default=None,
        help="Test a named candidate from TWEEDIE_DERIVATION_NOTE.md §6. "
             "ace_step_paper: x̂_0 = x_σ − σ·v (σ=0 data, σ=1 noise). "
             "rectified_flow: x̂_1 = z_τ + (1−τ)·v (the wrong-default baseline).",
    )
    parser.add_argument(
        "--derivation-note",
        default="orbit-research/TWEEDIE_DERIVATION_NOTE.md",
    )
    parser.add_argument(
        "--target-sigmas",
        default="0.5,0.3,0.1",
        help=("Comma-separated σ targets (ACE-Step convention: σ=0 data, σ=1 noise). "
              "Default = 0.5, 0.3, 0.1 — these are **magic-number placeholders** "
              "from R2 #25 (theoretical-rectified-flow late regime); pending the "
              "Stage 0 sigma calibration sweep (audit-Round-4 ADD 2026-05-21, "
              "cost-gated at 20 GPU-h) they are NOT empirically calibrated. "
              "Use 0.7,0.5,0.3,0.1 for K=4 escalation, or pass other values to "
              "explore. See TWEEDIE_DERIVATION_NOTE §9 + gate_v2.yaml.draft."),
    )
    parser.add_argument(
        "--cfg-type",
        default="cfg",
        help=("ACE-Step cfg_type to pass via extras. 'cfg' is the simplest CFG path "
              "and matches predict_velocity's mixing; 'apg' is upstream's default "
              "but is harder to replicate exactly. Defaults to 'cfg' so the "
              "trajectory v_out matches what predict_velocity would produce."),
    )
    parser.add_argument(
        "--cfg-scale", type=float, default=5.0,
        help="Guidance scale (matches AceStepModel.sample default).",
    )
    parser.add_argument(
        "--duration", type=float, default=20.0,
        help="Audio duration in seconds for each generated sample.",
    )
    parser.add_argument(
        "--infer-step", type=int, default=50,
        help="Number of inference steps (matches AceStepModel.sample default).",
    )
    parser.add_argument(
        "--no-aesthetic", action="store_true",
        help="Skip the aesthetic reward Spearman (LSD-only diagnostic).",
    )
    args = parser.parse_args()
    seed_everything(args.seed)
    out_dir = Path(args.out)
    if args.candidate_formula is not None:
        out_dir = out_dir / args.candidate_formula
    out_dir.mkdir(parents=True, exist_ok=True)

    target_sigmas = [float(x) for x in args.target_sigmas.split(",") if x.strip()]
    if not target_sigmas:
        print("D3 FAIL: --target-sigmas parsed to empty list.")
        return 1

    # STOP-B-4 D3a gate (production mode requires RESOLVED).
    note_path = Path(args.derivation_note)
    status = _read_derivation_status(note_path)
    if (
        not args.allow_unresolved
        and args.candidate_formula is None
        and args.mode == "production"
    ):
        if status != "RESOLVED":
            print(f"D3 BLOCK: D3a derivation note at {note_path} is STATUS={status}.")
            print("  Production D3 reconstruction sanity is gated on RESOLVED (per STOP-B-4).")
            print("  Run `python scripts/d3a_tweedie_derivation.py` and complete the derivation,")
            print("  or pass --allow-unresolved (dev) or --candidate-formula <name> (ambiguous).")
            return 2
    if args.candidate_formula is not None:
        print(f"D3: candidate-formula mode = {args.candidate_formula}")
        print(f"    (derivation note STATUS = {status})")
    elif status == "RESOLVED":
        print(f"D3: derivation note STATUS = RESOLVED — D3a gate satisfied.")

    print(f"D3: target σ values = {target_sigmas}")
    print(f"D3: cfg_type = {args.cfg_type}, cfg_scale = {args.cfg_scale}, "
          f"duration = {args.duration}s, infer_step = {args.infer_step}, "
          f"n_prompts = {args.n_prompts}")

    if args.model == "ace_step_v15":
        from mprm.inference.ace_step import AceStepModel

        model = AceStepModel(checkpoint=args.checkpoint or "ace-step/ACE-Step-1.5")
    else:
        from mprm.inference.sao import StableAudioOpenModel

        model = StableAudioOpenModel(checkpoint=args.checkpoint or "stabilityai/stable-audio-open-1.0")

    aesthetic = None
    if not args.no_aesthetic:
        try:
            from mprm.rewards.audiobox import AudioboxReward

            aesthetic = AudioboxReward(target_axis="PQ")
        except Exception as e:  # noqa: BLE001
            print(f"D3 WARN: cannot load aesthetic reward ({e}); falling back to LSD-only.")
            aesthetic = None

    aesthetic_intermediate: dict[float, list[float]] = {s: [] for s in target_sigmas}
    aesthetic_final: list[float] = []
    lsd_means: dict[float, list[float]] = {s: [] for s in target_sigmas}
    actual_sigmas: dict[float, list[float]] = {s: [] for s in target_sigmas}

    for i in range(args.n_prompts):
        prompt = Prompt(
            prompt_id=f"d3_{i:02d}",
            text="a calm acoustic guitar melody with no vocals",
            lyrics=None,
            structure_hint=None,
            duration_target=float(args.duration),
        )
        try:
            res = model.sample(
                prompt,
                seed=args.seed + i,
                cfg_scale=args.cfg_scale,
                steps=args.infer_step,
                return_trajectory=True,
                extras={"cfg_type": args.cfg_type},
            )
        except Exception as e:  # noqa: BLE001
            print(f"D3 FAIL sampling prompt {i}: {type(e).__name__}: {e}")
            return 1

        traj = res.trajectory
        traj_sigmas = res.extras.get("trajectory_sigmas", []) if res.extras else []
        traj_vs = res.extras.get("trajectory_model_outputs", []) if res.extras else []

        if traj is None or not traj_sigmas:
            print(
                f"D3 FAIL prompt {i}: model did not return trajectory or sigmas "
                f"(trajectory={None if traj is None else len(traj)}, "
                f"sigmas={len(traj_sigmas)}). "
                f"Adapter must set extras['trajectory_sigmas'] + "
                f"extras['trajectory_model_outputs'] per STOP-B-9 contract."
            )
            return 1

        final_audio = res.waveform
        if aesthetic is not None:
            aesthetic_final.append(
                aesthetic.score(final_audio, res.sample_rate, prompt).value
            )

        # Map target σ values to captured step indices.
        step_indices = _pick_checkpoints_for_sigmas(target_sigmas, traj_sigmas)
        for target_sigma, k in zip(target_sigmas, step_indices):
            sigma_actual = float(traj_sigmas[k])
            z_at_step = traj[k]
            v_at_step = traj_vs[k] if k < len(traj_vs) else None
            actual_sigmas[target_sigma].append(sigma_actual)

            # Codex review [C] (2026-05-22): captured v_out MUST be present.
            # A silent fallback to predict_velocity could mask a trajectory-capture
            # bug (e.g. _SchedulerStepCapture not populating model_outputs) by
            # recomputing v independently — which would still produce a sane LSD
            # comparison but would not be testing what we think we're testing
            # (the captured-v Tweedie formula). Hard-fail instead.
            if v_at_step is None:
                print(
                    f"D3 FAIL prompt {i}, σ={sigma_actual:.4f}: captured v_out is "
                    f"None at trajectory step {k}. The d3 sanity REQUIRES the "
                    f"captured velocity (trajectory_model_outputs[k]) to be present "
                    f"so the Tweedie formula is tested under the exact velocity the "
                    f"sampler used. Recomputing via predict_velocity is NOT a "
                    f"valid fallback for this test (would mask trajectory-capture "
                    f"regressions). Check _SchedulerStepCapture / "
                    f"sample(return_trajectory=True) plumbing."
                )
                return 1

            try:
                if args.candidate_formula == "rectified_flow":
                    # Rectified-flow form: x̂_1 = z_τ + (1 − τ) · v, with τ = 1 − σ
                    # (i.e. τ=1 → data, τ=0 → noise; opposite of ACE-Step).
                    # IMPORTANT: this is the WRONG-DEFAULT baseline we test against.
                    tau_rf = 1.0 - sigma_actual
                    z0_hat = z_at_step.to(torch.float32) + (1.0 - tau_rf) * v_at_step.to(torch.float32)
                    ahat = model.decode(z0_hat)
                else:
                    # Default + 'ace_step_paper': x̂_0 = x_σ - σ · v_out.
                    # Use captured v (Codex [C]: hard requirement, not optional shortcut).
                    ahat = model.tweedie_decode(
                        z_at_step,
                        sigma_actual,
                        prompt,
                        cfg_scale=args.cfg_scale,
                        v_out=v_at_step,
                    )
            except Exception as e:  # noqa: BLE001
                print(f"D3 FAIL tweedie at prompt {i}, σ={sigma_actual:.4f}: "
                      f"{type(e).__name__}: {e}")
                return 1

            if aesthetic is not None:
                aesthetic_intermediate[target_sigma].append(
                    aesthetic.score(ahat, res.sample_rate, prompt).value
                )
            lsd_means[target_sigma].append(log_spectral_distance(ahat, final_audio))
            if i == 0:
                save_audio(
                    out_dir / f"d3_sigma{sigma_actual:.3f}.wav",
                    ahat,
                    res.sample_rate,
                )
        if i == 0:
            save_audio(out_dir / "d3_final.wav", final_audio, res.sample_rate)

    # ------------------------------------------------- reporting

    label = args.candidate_formula or "default"
    print(f"\nD3 results [{label}] over {args.n_prompts} prompts:")
    if aesthetic_final:
        print(f"  aesthetic@final: mean={statistics.mean(aesthetic_final):.3f}")
    print("  σ_target | σ_actual(med) | LSD_mean | aesthetic_Spearman")
    print("  ---------+---------------+----------+-------------------")
    for target_sigma in target_sigmas:
        sigma_actual_med = (
            statistics.median(actual_sigmas[target_sigma])
            if actual_sigmas[target_sigma]
            else float("nan")
        )
        lsd_mean = (
            statistics.mean(lsd_means[target_sigma])
            if lsd_means[target_sigma]
            else float("nan")
        )
        if aesthetic_final and aesthetic_intermediate[target_sigma]:
            rho = spearman(aesthetic_intermediate[target_sigma], aesthetic_final)
            rho_str = f"{rho:+.3f}"
        else:
            rho = float("nan")
            rho_str = "  n/a"
        print(
            f"   {target_sigma:.2f}    |    {sigma_actual_med:.3f}     | "
            f"  {lsd_mean:.3f}  |      {rho_str}"
        )

    # PASS / FAIL heuristics. With only K=3 σ values the trend test is weak;
    # we use absolute LSD trend + (if available) any positive Spearman at the
    # smallest σ as the minimal-pass criterion.
    sorted_sigmas = sorted(target_sigmas)
    monotonic_lsd = True
    for k1, k2 in zip(sorted_sigmas, sorted_sigmas[1:]):
        # sorted_sigmas is ascending (e.g. [0.1, 0.3, 0.5]). σ↑ means further
        # from data, so LSD-to-final should also ↑. So lsd[k2] ≥ lsd[k1] - slack.
        if not (
            statistics.mean(lsd_means[k2])
            >= statistics.mean(lsd_means[k1]) - 0.05  # allow 0.05 slack
        ):
            monotonic_lsd = False
            break

    has_positive_trend = False
    if aesthetic_final:
        for s in sorted_sigmas[: max(1, len(sorted_sigmas) // 2)]:
            # any positive spearman at small σ (closer to data) is encouraging
            if (
                aesthetic_intermediate.get(s)
                and spearman(aesthetic_intermediate[s], aesthetic_final) > 0
            ):
                has_positive_trend = True
                break

    print()
    if not monotonic_lsd:
        print("D3 WARN: LSD not monotonic-improving toward smaller σ; check formula / σ order.")
    if aesthetic_final and not has_positive_trend:
        print("D3 WARN: no positive aesthetic Spearman at late checkpoints.")

    if monotonic_lsd or has_positive_trend:
        print(f"D3 PASS [{label}] (monotonic LSD OR positive late Spearman).")
        return 0
    print(f"D3 FAIL [{label}].")
    return 1


if __name__ == "__main__":
    sys.exit(main())
