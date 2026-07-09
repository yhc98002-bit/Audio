"""R5 — SFT on best-of-N: offline amortization of BoN gain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch

from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt
from mprm.inference.interface import FlowMatchingModel
from mprm.rewards.interface import RewardModel


@dataclass
class EliteSample:
    prompt_id: str
    z_one: torch.Tensor
    metrics: dict[str, float]


class R5SftOnBest(Baseline):
    rung_id = "R5"
    name = "sft_on_best"

    def __init__(self, *args, n: int, primary_axis: str, sft_steps: int,
                 lora_rank: int = 8, lr: float = 1e-5, **kwargs):
        super().__init__(*args, **kwargs)
        self.n = n
        self.primary_axis = primary_axis
        self.sft_steps = sft_steps
        self.lora_rank = lora_rank
        self.lr = lr
        self._elites: dict[str, EliteSample] = {}

    def collect_elites(self, prompts: list[Prompt], *, seed: int) -> dict[str, EliteSample]:
        self._elites = {}
        for p in prompts:
            best: tuple[FlowMatchingModel, float] | None = None
            best_res = None
            best_metrics: dict[str, float] = {}
            for i in range(self.n):
                res = self.model.sample(p, seed=seed + i)
                metrics = self.score_all_axes(res.waveform, res.sample_rate, p)
                axis_value = metrics.get(self.primary_axis, float("-inf"))
                if best is None or axis_value > best[1]:
                    best = (None, axis_value)
                    best_res = res
                    best_metrics = metrics
            assert best_res is not None
            z_one = self.model.encode(best_res.waveform)
            self._elites[p.prompt_id] = EliteSample(
                prompt_id=p.prompt_id, z_one=z_one, metrics=best_metrics
            )
        return self._elites

    def _fm_loss_for_elite(self, elite: EliteSample, prompt: Prompt,
                            tau: float) -> torch.Tensor:
        z_one = elite.z_one
        z_zero = torch.randn_like(z_one)
        z_tau = (1 - tau) * z_zero + tau * z_one
        v_target = z_one - z_zero
        v_pred = self.model.predict_velocity(z_tau, tau, prompt)
        return torch.nn.functional.mse_loss(v_pred, v_target)

    def fit(self, prompts: list[Prompt]) -> None:
        if not self._elites:
            raise RuntimeError("Call collect_elites(prompts, seed=...) before fit().")
        try:
            from peft import LoraConfig, get_peft_model
        except ImportError as e:
            raise ImportError("peft not installed; required for LoRA fine-tuning") from e
        peft_cfg = LoraConfig(r=self.lora_rank, lora_alpha=self.lora_rank * 2)
        backbone = getattr(self.model, "_pipeline", None)
        if backbone is None:
            raise RuntimeError("Model pipeline not loaded; call model._ensure_loaded() first.")
        peft_model = get_peft_model(backbone, peft_cfg)
        optim = torch.optim.AdamW(peft_model.parameters(), lr=self.lr)
        import random as _rand
        for step in range(self.sft_steps):
            p = _rand.choice(prompts)
            elite = self._elites[p.prompt_id]
            tau = float(torch.rand(1))
            loss = self._fm_loss_for_elite(elite, p, tau)
            optim.zero_grad()
            loss.backward()
            optim.step()

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        res = self.model.sample(prompt, seed=seed)
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_sft.wav"
        save_audio(wav_path, res.waveform, res.sample_rate)
        metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=metrics,
            extras={"seed": seed, "sft_steps": self.sft_steps,
                    "n_elites": len(self._elites)},
        )

    def save_adapter(self, path: str | Path) -> None:
        backbone = getattr(self.model, "_pipeline", None)
        if backbone is None:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if hasattr(backbone, "save_pretrained"):
            backbone.save_pretrained(str(path))
