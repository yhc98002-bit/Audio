"""Session-scoped feature cache for shared audio intermediates across reward axes.

Per FINAL_REVISION_CRITIC.md #16:
  "Introduce BaseAudioFeatures cache under rewards. Cache waveform hash, sample
  rate, resampling, Demucs vocal stem, mel/STFT features or other shared
  intermediates when safe. CLAP / Audiobox / MERT / Whisper should reuse cached
  feature products where possible. Validation requirement: 32-sample parity test
  comparing pre-cache and post-cache reward outputs. Cache key must include
  waveform hash, sample rate, reward model version, config hash, stem model
  version. If scores change outside tolerance, cache optimization is disabled."

Architecture:
  - Session-scoped (per-audio): create one AudioFeatureCache instance per scoring
    pass (one audio in → all reward axes scored → cache discarded). NOT persistent
    across audios — each audio is its own session.
  - Opt-in: reward modules accept optional `cache: AudioFeatureCache | None = None`.
    If provided, use; else compute fresh. Backward compatible.
  - Cache key composition: waveform_hash + sample_rate + feature_name + version
    + sorted(params). Mis-keyed entries → cache miss; never serve stale.

Initial integration (this commit): Whisper-WER's Demucs vocal-stem extraction.
Other reward modules (CLAP / Audiobox / MERT) have less obvious shared
intermediates with the current single-vocal-axis pipeline; their integration
is deferred to Phase B kickoff if PI validates expected speedup.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable

import torch


class AudioFeatureCache:
    """Session-scoped feature cache. One instance per audio scoring pass."""

    def __init__(self, waveform: torch.Tensor, sample_rate: int,
                 config_hash: str = "default"):
        """Initialize with reference waveform and sample rate.

        Args:
            waveform: the reference audio. Hashed once at construction.
            sample_rate: source sample rate.
            config_hash: optional config-hash (e.g. yaml file SHA) for the
                project config that produced this audio. Mixed into cache keys
                so a config change invalidates cached features automatically.
        """
        self.waveform = waveform
        self.sample_rate = sample_rate
        self.config_hash = config_hash
        self._wave_hash = self._hash_waveform(waveform)
        self._cache: dict[str, Any] = {}
        self._versions: dict[str, str] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _hash_waveform(waveform: torch.Tensor) -> str:
        """Fast hash: SHA256 over float32 bytes. Deterministic and collision-free
        for typical use."""
        h = hashlib.sha256()
        h.update(waveform.detach().cpu().to(torch.float32).numpy().tobytes())
        return h.hexdigest()[:16]

    def _key(self, feature_name: str, version: str, **params: Any) -> str:
        """Compose cache key from waveform_hash + sample_rate + feature_name +
        version + config_hash + sorted(params)."""
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return (f"{self._wave_hash}__sr{self.sample_rate}__{feature_name}"
                f"__v{version}__cfg{self.config_hash}__{param_str}")

    def get_or_compute(self, feature_name: str, version: str,
                       compute_fn: Callable[[], Any], **params: Any) -> Any:
        """Return cached feature or compute + cache it.

        Args:
            feature_name: human-readable identifier (e.g. "demucs_vocal_stem").
            version: feature-source version (e.g. "htdemucs"). MUST change
                when the underlying model/algorithm changes.
            compute_fn: zero-arg callable that returns the feature.
            **params: any additional discriminators (e.g. `target_sr=48000`).
        """
        k = self._key(feature_name, version, **params)
        if k in self._cache:
            self._hits += 1
            return self._cache[k]
        self._misses += 1
        val = compute_fn()
        self._cache[k] = val
        self._versions[feature_name] = version
        return val

    def stats(self) -> dict:
        return {
            "n_features": len(self._cache),
            "feature_names": list(self._versions.keys()),
            "feature_versions": dict(self._versions),
            "wave_hash": self._wave_hash,
            "sample_rate": self.sample_rate,
            "config_hash": self.config_hash,
            "hits": self._hits,
            "misses": self._misses,
        }


def maybe_cache_call(cache: AudioFeatureCache | None, feature_name: str,
                     version: str, compute_fn: Callable[[], Any], **params: Any) -> Any:
    """Convenience helper for reward modules. If cache is None, just call
    compute_fn. If cache is provided, route through get_or_compute."""
    if cache is None:
        return compute_fn()
    return cache.get_or_compute(feature_name, version, compute_fn, **params)
