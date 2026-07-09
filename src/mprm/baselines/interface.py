from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch

from mprm.data.prompts import Prompt
from mprm.inference.interface import FlowMatchingModel
from mprm.rewards.interface import RewardModel


@dataclass
class BaselineResult:
    rung_id: str
    run_id: str
    prompt_id: str
    waveform_path: str | None
    metrics: dict[str, float]
    extras: dict[str, Any] = field(default_factory=dict)


class Baseline(ABC):
    rung_id: str
    name: str

    def __init__(self, model: FlowMatchingModel, reward_models: list[RewardModel],
                 output_dir: str | Path):
        self.model = model
        self.reward_models = reward_models
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult: ...

    def run_on_set(self, prompts: list[Prompt], *, seed: int) -> list[BaselineResult]:
        return [self.run_on_prompt(p, seed=seed) for p in prompts]

    def score_all_axes(self, waveform: torch.Tensor, sr: int, prompt: Prompt) -> dict[str, float]:
        return {rm.axis: rm.score(waveform, sr, prompt).value for rm in self.reward_models}
