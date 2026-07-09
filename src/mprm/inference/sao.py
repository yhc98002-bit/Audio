"""Stable Audio Open 1.0 wrapper.

Loading goes through `stable-audio-tools` (Stability AI). SAO is the secondary backbone
(audit-only) per FINAL_PROPOSAL.md §4. Full SAO training is the first scope cut.
"""
from __future__ import annotations

import torch

from mprm.data.prompts import Prompt
from mprm.inference.interface import FlowMatchingModel, SamplingResult


class StableAudioOpenModel(FlowMatchingModel):
    name = "stable_audio_open_1_0"
    sample_rate = 44_100
    latent_rate_factor = 64

    def __init__(self, checkpoint: str = "stabilityai/stable-audio-open-1.0",
                 device: str = "cuda", lora_path: str | None = None):
        self.checkpoint = checkpoint
        self.device = device
        self.lora_path = lora_path
        self._pipeline = None

    def _ensure_loaded(self) -> None:
        if self._pipeline is None:
            try:
                from stable_audio_tools import get_pretrained_model
            except ImportError as e:
                raise ImportError(
                    "stable_audio_tools not installed. See "
                    "https://github.com/Stability-AI/stable-audio-tools"
                ) from e
            self._pipeline, _ = get_pretrained_model(self.checkpoint)
            self._pipeline = self._pipeline.to(self.device).eval()

    def sample(self, prompt: Prompt, *, seed: int, cfg_scale: float | None = None,
               steps: int | None = None, return_trajectory: bool = False,
               sde_mode: bool = False, eta_schedule: torch.Tensor | None = None,
               extras: dict | None = None,
               ) -> SamplingResult:
        self._ensure_loaded()
        cfg_scale = cfg_scale if cfg_scale is not None else 7.0
        steps = steps if steps is not None else 25
        generator = torch.Generator(device=self.device).manual_seed(seed)
        from stable_audio_tools.inference.generation import generate_diffusion_cond
        # SAO does not currently expose step-allocation or negative-prompt knobs through
        # this entry; pass-through is a no-op (logged in extras).
        unsupported_extras = dict(extras or {})
        output = generate_diffusion_cond(
            self._pipeline,
            steps=steps,
            cfg_scale=cfg_scale,
            conditioning=[{
                "prompt": prompt.text,
                "seconds_start": 0,
                "seconds_total": prompt.duration_target,
            }],
            generator=generator,
            return_trajectory=return_trajectory,
            sde_mode=sde_mode,
            eta=eta_schedule,
        )
        return SamplingResult(
            waveform=output.audio.cpu(),
            sample_rate=self.sample_rate,
            trajectory=[t.cpu() for t in output.trajectory] if return_trajectory else None,
            seed=seed,
            cfg_scale=cfg_scale,
            inference_steps=steps,
            extras={"applied_extras": {}, "unsupported_extras": unsupported_extras},
        )

    def predict_velocity(self, z_tau: torch.Tensor, tau: float, prompt: Prompt) -> torch.Tensor:
        self._ensure_loaded()
        return self._pipeline.model.predict_velocity(
            z_tau.to(self.device), torch.tensor([tau], device=self.device),
            conditioning=[{"prompt": prompt.text,
                           "seconds_start": 0,
                           "seconds_total": prompt.duration_target}],
        )

    def decode(self, z_one: torch.Tensor) -> torch.Tensor:
        self._ensure_loaded()
        return self._pipeline.pretransform.decode(z_one.to(self.device)).cpu()

    def encode(self, waveform: torch.Tensor) -> torch.Tensor:
        self._ensure_loaded()
        return self._pipeline.pretransform.encode(waveform.to(self.device)).cpu()
