from abc import ABC, abstractmethod
from dataclasses import dataclass

import torch

from mprm.data.prompts import Prompt


@dataclass
class SamplingResult:
    waveform: torch.Tensor
    sample_rate: int
    trajectory: list[torch.Tensor] | None
    seed: int
    cfg_scale: float
    inference_steps: int
    extras: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.extras is None:
            self.extras = {}


class FlowMatchingModel(ABC):
    name: str
    sample_rate: int
    latent_rate_factor: int

    @abstractmethod
    def sample(self, prompt: Prompt, *, seed: int, cfg_scale: float | None = None,
               steps: int | None = None, return_trajectory: bool = False,
               sde_mode: bool = False, eta_schedule: torch.Tensor | None = None,
               extras: dict | None = None,
               ) -> SamplingResult: ...

    @abstractmethod
    def predict_velocity(self, z_tau: torch.Tensor, tau: float, prompt: Prompt) -> torch.Tensor: ...

    @abstractmethod
    def decode(self, z_one: torch.Tensor) -> torch.Tensor: ...

    @abstractmethod
    def encode(self, waveform: torch.Tensor) -> torch.Tensor: ...

    def tweedie_clean(self, z_tau: torch.Tensor, tau: float, prompt: Prompt) -> torch.Tensor:
        """Tweedie clean-target estimate from a noised latent.

        STOP-B-9 (2026-05-22, Codex review D1): the base-class default formula
        `x̂_1 = z_τ + (1 − τ) · v_pred` is the rectified-flow convention
        (τ=1 → data, τ=0 → noise). For ACE-Step the convention is INVERTED
        (σ=0 → data, σ=1 → noise) and the correct formula is
        `x̂_0 = x_σ − σ · v_out` — see `orbit-research/TWEEDIE_DERIVATION_NOTE.md`
        §5 + §8 and the `AceStepModel.tweedie_clean` override in `ace_step.py`.

        Rather than expose the rectified-flow form as a silent default that a
        future ACE-Step caller could accidentally route through (and get a
        wrong reconstruction without any error), this method raises. Subclasses
        MUST override and explicitly declare their convention.
        """
        raise NotImplementedError(
            f"FlowMatchingModel.tweedie_clean is abstract — subclass {type(self).__name__}"
            " must override and declare the σ vs τ convention explicitly. The"
            " rectified-flow base formula `x̂_1 = z_τ + (1−τ)·v` is WRONG for"
            " ACE-Step (which uses σ=0 data, σ=1 noise). See"
            " `orbit-research/TWEEDIE_DERIVATION_NOTE.md` §5 + §8."
        )

    def tweedie_decode(self, z_tau: torch.Tensor, tau: float, prompt: Prompt) -> torch.Tensor:
        z_one_hat = self.tweedie_clean(z_tau, tau, prompt)
        return self.decode(z_one_hat)
