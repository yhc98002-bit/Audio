"""Stable Audio 3 Medium adapter with same-trajectory preview capture.

This module targets the dedicated ``stable-audio-3`` package. It is separate
from :mod:`mprm.inference.sao`, which remains the Stable Audio Open 1.0 adapter.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import torch

from mprm.data.prompts import Prompt
from mprm.inference.interface import FlowMatchingModel, SamplingResult


def normalize_capture_steps(capture_steps: Iterable[int] | None, total_steps: int) -> tuple[int, ...]:
    """Validate and normalize zero-based sampler callback indices."""
    if total_steps <= 0:
        raise ValueError("total_steps must be positive")
    values = range(total_steps) if capture_steps is None else capture_steps
    normalized = tuple(sorted({int(step) for step in values}))
    invalid = [step for step in normalized if step < 0 or step >= total_steps]
    if invalid:
        raise ValueError(f"capture steps outside [0, {total_steps - 1}]: {invalid}")
    return normalized


class SameTrajectoryCapture:
    """Collect clean-latent estimates emitted by one SA3 sampler trajectory."""

    def __init__(self, capture_steps: Iterable[int] | None, total_steps: int):
        self.capture_steps = normalize_capture_steps(capture_steps, total_steps)
        self._capture_set = set(self.capture_steps)
        self.latents: dict[int, torch.Tensor] = {}
        self.metadata: dict[int, dict[str, float | int]] = {}

    @staticmethod
    def _scalar(value: Any) -> float:
        if isinstance(value, torch.Tensor):
            value = value.detach().reshape(-1)[0].cpu().item()
        return float(value)

    def __call__(self, callback_info: dict[str, Any]) -> None:
        step = int(callback_info["i"])
        if step not in self._capture_set:
            return
        denoised = callback_info["denoised"]
        if not isinstance(denoised, torch.Tensor):
            raise TypeError("SA3 callback 'denoised' must be a torch.Tensor")
        self.latents[step] = denoised.detach().to("cpu", copy=True)
        self.metadata[step] = {
            "step_index": step,
            "t": self._scalar(callback_info["t"]),
            "sigma": self._scalar(callback_info["sigma"]),
        }

    def assert_complete(self) -> None:
        missing = sorted(self._capture_set.difference(self.latents))
        if missing:
            raise RuntimeError(f"SA3 callback omitted requested steps: {missing}")


class StableAudio3MediumModel(FlowMatchingModel):
    """Local Stable Audio 3 Medium inference with decoded denoising previews."""

    name = "stable_audio_3_medium"
    sample_rate = 44_100
    latent_rate_factor = 2_048

    def __init__(
        self,
        checkpoint_dir: str | Path,
        *,
        device: str = "cuda",
        dtype: str = "bfloat16",
    ) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.device = device
        self.dtype = dtype
        self._pipeline = None

    @staticmethod
    def _patch_local_paths(model_config: dict, checkpoint_dir: Path) -> None:
        for cond in model_config["model"]["conditioning"]["configs"]:
            if cond.get("id") == "prompt" and cond.get("type") == "t5gemma":
                cfg = cond["config"]
                cfg["model_path"] = str(checkpoint_dir / "t5gemma-b-b-ul2")
                cfg.pop("repo_id", None)
                cfg.pop("subfolder", None)

    def _ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        try:
            from stable_audio_3.loading_utils import load_diffusion_cond
            from stable_audio_3.model import StableAudioModel
        except ImportError as exc:
            raise ImportError(
                "Stable Audio 3 requires the dedicated stable-audio-3 package"
            ) from exc

        config_path = self.checkpoint_dir / "model_config.json"
        weights_path = self.checkpoint_dir / "model.safetensors"
        with config_path.open("r", encoding="utf-8") as handle:
            model_config = json.load(handle)
        self._patch_local_paths(model_config, self.checkpoint_dir)
        model_half = self.dtype == "float16"
        model = load_diffusion_cond(
            model_config,
            str(weights_path),
            device=self.device,
            model_half=model_half,
        )
        if self.dtype == "bfloat16":
            model = model.to(torch.bfloat16)
        elif self.dtype == "float32":
            model = model.to(torch.float32)
        self._pipeline = StableAudioModel(model, model_config, self.device, model_half=model_half)
        self.sample_rate = int(model.sample_rate)
        self.latent_rate_factor = int(model.pretransform.downsampling_ratio)

    def _decode_latent(self, latent: torch.Tensor, *, chunked: bool = True) -> torch.Tensor:
        self._ensure_loaded()
        pretransform = self._pipeline.model.pretransform
        dtype = next(pretransform.parameters()).dtype
        decoded = pretransform.decode(
            latent.to(device=self.device, dtype=dtype),
            chunked=chunked,
        )
        return decoded.detach().to(torch.float32).clamp(-1, 1).cpu()

    def sample(
        self,
        prompt: Prompt,
        *,
        seed: int,
        cfg_scale: float | None = None,
        steps: int | None = None,
        return_trajectory: bool = False,
        sde_mode: bool = False,
        eta_schedule: torch.Tensor | None = None,
        extras: dict | None = None,
    ) -> SamplingResult:
        self._ensure_loaded()
        if sde_mode or eta_schedule is not None:
            raise ValueError("SA3 ping-pong sampling does not accept sde_mode or eta_schedule")
        options = dict(extras or {})
        steps = 4 if steps is None else int(steps)
        cfg_scale = 1.0 if cfg_scale is None else float(cfg_scale)
        duration = float(options.pop("duration_s", prompt.duration_target))
        capture_steps = options.pop("capture_steps", None)
        sampler_type = str(options.pop("sampler_type", "pingpong"))
        chunked_decode = bool(options.pop("chunked_decode", True))
        negative_prompt = options.pop("negative_prompt", None)
        if options:
            raise ValueError(f"unsupported SA3 sampling extras: {sorted(options)}")

        capture = SameTrajectoryCapture(capture_steps, steps) if return_trajectory else None
        audio = self._pipeline.generate(
            prompt=prompt.text,
            negative_prompt=negative_prompt,
            duration=duration,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            batch_size=1,
            sample_size=int(self._pipeline.model_config["sample_size"]),
            sampler_type=sampler_type,
            chunked_decode=chunked_decode,
            disable_tqdm=True,
            callback=capture,
        )
        trajectory = None
        capture_metadata: list[dict[str, float | int]] = []
        if capture is not None:
            capture.assert_complete()
            trajectory = []
            max_frames = int(round(duration * self.sample_rate))
            for step in capture.capture_steps:
                decoded = self._decode_latent(capture.latents[step], chunked=chunked_decode)
                trajectory.append(decoded[..., :max_frames])
                capture_metadata.append(capture.metadata[step])

        return SamplingResult(
            waveform=audio.detach().to(torch.float32).clamp(-1, 1).cpu(),
            sample_rate=self.sample_rate,
            trajectory=trajectory,
            seed=seed,
            cfg_scale=cfg_scale,
            inference_steps=steps,
            extras={
                "backbone": self.name,
                "checkpoint_dir": str(self.checkpoint_dir),
                "sampler_type": sampler_type,
                "same_trajectory_capture": return_trajectory,
                "capture_metadata": capture_metadata,
            },
        )

    def predict_velocity(self, z_tau: torch.Tensor, tau: float, prompt: Prompt) -> torch.Tensor:
        raise NotImplementedError("SA3 velocity prediction requires encoded conditioning")

    def decode(self, z_one: torch.Tensor) -> torch.Tensor:
        return self._decode_latent(z_one)

    def encode(self, waveform: torch.Tensor) -> torch.Tensor:
        self._ensure_loaded()
        pretransform = self._pipeline.model.pretransform
        dtype = next(pretransform.parameters()).dtype
        encoded = pretransform.encode(waveform.to(device=self.device, dtype=dtype))
        return encoded.detach().cpu()
