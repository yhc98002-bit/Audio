from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import torch

from mprm.data.prompts import Prompt


@dataclass
class RewardScore:
    axis: str
    value: float
    raw: dict[str, Any] = field(default_factory=dict)


class RewardModel(ABC):
    axis: str
    version: str

    @abstractmethod
    def score(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt) -> RewardScore: ...

    def score_batch(self, waveforms: list[torch.Tensor], sample_rate: int,
                    prompts: list[Prompt]) -> list[RewardScore]:
        return [self.score(w, sample_rate, p) for w, p in zip(waveforms, prompts)]
