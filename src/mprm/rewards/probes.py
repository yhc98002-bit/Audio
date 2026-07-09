"""Anti-hacking probes versioned at v0.1 (METHOD_SPEC §2.3).

Thresholds + activation floors are loaded from `src/mprm/rewards/probes_v01.yaml` at module
import time. Updating the manifest in place is the canonical way to recalibrate Phase A
probe lambdas after the A.aux human-calibration sub-audit.
"""
from __future__ import annotations

from pathlib import Path

import torch
import torchaudio
import yaml

from mprm.data.prompts import Prompt
from mprm.rewards.clap import ClapReward


def _load_manifest() -> dict:
    path = Path(__file__).with_name("probes_v01.yaml")
    if not path.exists():
        return {"version": "v0.1", "probes": {}}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


PROBE_MANIFEST: dict = _load_manifest()
PROBE_VERSION: str = PROBE_MANIFEST.get("version", "v0.1")


def _manifest(name: str, key: str, default):
    return PROBE_MANIFEST.get("probes", {}).get(name, {}).get(key, default)


def silence_fraction(waveform: torch.Tensor, sample_rate: int,
                     window_ms: float | None = None, threshold: float | None = None) -> float:
    window_ms = window_ms if window_ms is not None else _manifest("silence_fraction", "window_ms", 20.0)
    threshold = threshold if threshold is not None else _manifest("silence_fraction", "threshold", 1e-3)
    w = waveform.mean(dim=0) if waveform.dim() == 2 else waveform
    win = max(1, int(window_ms / 1000.0 * sample_rate))
    n_win = w.shape[-1] // win
    if n_win == 0:
        return 1.0
    windows = w[: n_win * win].view(n_win, win)
    return float((windows.abs().max(dim=-1).values < threshold).float().mean())


def autocorr_repetition(waveform: torch.Tensor, sample_rate: int,
                        min_lag_seconds: float | None = None) -> float:
    """Detect short-time repetition by computing the normalized autocorrelation
    at lags >= `min_lag_seconds` and returning its max absolute value.

    STOP-B-8 Phase-1 fix (2026-05-17): the prior implementation used
    `F.conv1d(w, w)` without `padding=n-1`, which makes the output a single
    scalar (kernel_size == input_length) — so `full[n-1]` was out-of-bounds
    for every nontrivial signal, and the function crashed on the first call
    from `anti_hacking_probes`. The bug was latent because the only prior
    end-to-end test (the adapter dev smoke) called `model.sample` directly,
    not the probe path.

    The replacement uses FFT-based circular autocorrelation
    (`irfft(|rfft|²)`, O(n log n)) with explicit `n=n` so odd-length inputs
    reconstruct correctly. Returns the max-magnitude normalized
    autocorrelation over lags >= `min_lag_seconds`.
    """
    min_lag_seconds = (min_lag_seconds if min_lag_seconds is not None
                        else _manifest("autocorr_repetition", "min_lag_seconds", 0.5))
    w = waveform.mean(dim=0) if waveform.dim() == 2 else waveform
    # Cast to float32 in case upstream emits bfloat16 — fft is most robust
    # on float32 and the probe cost is irrelevant.
    w = w.to(torch.float32)
    w = (w - w.mean()) / (w.std() + 1e-8)
    n = w.shape[-1]
    lag = int(min_lag_seconds * sample_rate)
    if n <= lag:
        return 0.0
    # FFT-based circular autocorrelation; explicit n keeps the inverse honest
    # for odd-length signals.
    spec = torch.fft.rfft(w).abs().pow(2)
    full = torch.fft.irfft(spec, n=n).real  # shape (n,)
    norm = float(full[0])  # zero-lag autocorrelation
    if abs(norm) < 1e-8:
        return 0.0
    autocorr = full[lag:] / norm
    return float(autocorr.abs().max())


def off_prompt_distance(waveform: torch.Tensor, sample_rate: int, prompt: Prompt,
                        base_reference: torch.Tensor | None,
                        clap: ClapReward) -> float:
    if base_reference is None:
        return 0.0
    r_x = clap.score(waveform, sample_rate, prompt).value
    r_b = clap.score(base_reference, sample_rate, prompt).value
    return max(0.0, r_b - r_x)


def hf_artifact_score(waveform: torch.Tensor, sample_rate: int,
                      base_reference: torch.Tensor | None = None,
                      hf_cutoff_hz: float | None = None) -> float:
    hf_cutoff_hz = (hf_cutoff_hz if hf_cutoff_hz is not None
                     else _manifest("hf_artifact_score", "hf_cutoff_hz", 18_000.0))
    w = waveform.mean(dim=0) if waveform.dim() == 2 else waveform
    spec = torch.stft(w, n_fft=4096, hop_length=2048, return_complex=True).abs()
    freqs = torch.linspace(0, sample_rate / 2.0, spec.shape[0])
    hf_mask = freqs > hf_cutoff_hz
    hf_energy = float(spec[hf_mask].pow(2).mean()) if hf_mask.any() else 0.0
    if base_reference is not None:
        base_spec = torch.stft(
            base_reference.mean(dim=0) if base_reference.dim() == 2 else base_reference,
            n_fft=4096, hop_length=2048, return_complex=True
        ).abs()
        base_hf = float(base_spec[hf_mask].pow(2).mean()) if hf_mask.any() else 1e-8
        return hf_energy / (base_hf + 1e-8)
    return hf_energy


def anti_hacking_probes(waveform: torch.Tensor, sample_rate: int, prompt: Prompt,
                        base_reference: torch.Tensor | None = None,
                        clap: ClapReward | None = None) -> dict[str, float]:
    return {
        "silence_fraction": silence_fraction(waveform, sample_rate),
        "autocorr_repetition": autocorr_repetition(waveform, sample_rate),
        "off_prompt_distance": (off_prompt_distance(waveform, sample_rate, prompt,
                                                    base_reference, clap)
                                 if clap is not None else 0.0),
        "hf_artifact_score": hf_artifact_score(waveform, sample_rate, base_reference),
    }


def probe_floors() -> dict[str, float]:
    floors: dict[str, float] = {}
    for name, spec in PROBE_MANIFEST.get("probes", {}).items():
        if "activation_floor" in spec:
            floors[name] = float(spec["activation_floor"])
    return floors


def probe_default_lambdas() -> dict[str, float]:
    out: dict[str, float] = {}
    for name, spec in PROBE_MANIFEST.get("probes", {}).items():
        out[name] = float(spec.get("lambda_default", 0.0))
    return out
