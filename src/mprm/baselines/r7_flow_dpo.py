"""R7 — Flow-DPO (offline preference fine-tune).

Preference pairs come from BoN samples ranked by R_lcb; winner = top-quantile, loser =
bottom-quantile. The DPO loss follows arXiv:2501.13918 (Flow-DPO for video) adapted to
audio FM.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import torch

from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt
from mprm.rewards.clap import ClapReward
from mprm.rewards.perturbations import perturbation_set
from mprm.rewards.probes import anti_hacking_probes
from mprm.rewards.robust_lcb import robust_lcb


@dataclass
class PreferencePair:
    prompt_id: str
    z_winner: torch.Tensor
    z_loser: torch.Tensor
    margin: float


class R7FlowDpo(Baseline):
    rung_id = "R7"
    name = "flow_dpo"

    def __init__(self, *args, n_bon: int, beta_dpo: float, beta_robust: float,
                 lambda_probe: dict[str, float], perturbation_names: list[str],
                 sft_steps: int, lora_rank: int = 8, lr: float = 1e-6,
                 min_margin: float = 0.05, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_bon = n_bon
        self.beta_dpo = beta_dpo
        self.beta_robust = beta_robust
        self.lambda_probe = lambda_probe
        self.perturbations = perturbation_set(perturbation_names)
        self.sft_steps = sft_steps
        self.lora_rank = lora_rank
        self.lr = lr
        self.min_margin = min_margin
        self._pairs: list[PreferencePair] = []
        self._clap = next((rm for rm in self.reward_models if isinstance(rm, ClapReward)), None)

    def build_preference_pairs(self, prompts: list[Prompt], *, seed: int) -> list[PreferencePair]:
        self._pairs = []
        for p in prompts:
            samples = []
            base_ref = None
            for i in range(self.n_bon):
                res = self.model.sample(p, seed=seed + i)
                if i == 0:
                    base_ref = res.waveform
                probe = anti_hacking_probes(res.waveform, res.sample_rate, p,
                                             base_reference=base_ref, clap=self._clap)
                lcb = robust_lcb(res.waveform, res.sample_rate, p,
                                  reward_models=self.reward_models,
                                  perturbations=self.perturbations,
                                  probe_scores=probe,
                                  lambda_probe=self.lambda_probe,
                                  beta_robust=self.beta_robust)
                samples.append((res, lcb))
            samples.sort(key=lambda c: c[1].value, reverse=True)
            top = samples[0]
            bot = samples[-1]
            margin = top[1].value - bot[1].value
            if margin < self.min_margin:
                continue
            self._pairs.append(PreferencePair(
                prompt_id=p.prompt_id,
                z_winner=self.model.encode(top[0].waveform),
                z_loser=self.model.encode(bot[0].waveform),
                margin=margin,
            ))
        return self._pairs

    def _trajectory_term(self, z_one: torch.Tensor, prompt: Prompt, tau: float
                           ) -> torch.Tensor:
        z_zero = torch.randn_like(z_one)
        z_tau = (1 - tau) * z_zero + tau * z_one
        v_target = z_one - z_zero
        v_pred = self.model.predict_velocity(z_tau, tau, prompt)
        return torch.nn.functional.mse_loss(v_pred, v_target, reduction="mean")

    def fit(self, prompts: list[Prompt]) -> None:
        if not self._pairs:
            raise RuntimeError("Call build_preference_pairs() first.")
        try:
            from peft import LoraConfig, get_peft_model
        except ImportError as e:
            raise ImportError("peft not installed") from e
        peft_cfg = LoraConfig(r=self.lora_rank, lora_alpha=self.lora_rank * 2)
        backbone = getattr(self.model, "_pipeline", None)
        if backbone is None:
            raise RuntimeError("Model pipeline not loaded.")
        peft_model = get_peft_model(backbone, peft_cfg)
        optim = torch.optim.AdamW(peft_model.parameters(), lr=self.lr)
        prompt_map = {p.prompt_id: p for p in prompts}
        for step in range(self.sft_steps):
            pair = random.choice(self._pairs)
            prompt = prompt_map[pair.prompt_id]
            tau = float(torch.rand(1))
            d_w = self._trajectory_term(pair.z_winner, prompt, tau)
            d_l = self._trajectory_term(pair.z_loser, prompt, tau)
            loss = -torch.nn.functional.logsigmoid(-self.beta_dpo * (d_w - d_l))
            optim.zero_grad()
            loss.backward()
            optim.step()

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        res = self.model.sample(prompt, seed=seed)
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_flow_dpo.wav"
        save_audio(wav_path, res.waveform, res.sample_rate)
        metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=metrics,
            extras={"seed": seed, "n_pairs": len(self._pairs)},
        )
