"""R8 — Outcome-GRPO: vanilla Flow-GRPO + robust LCB reward + Lagrangian lyric guard.

**DEFERRED-REAL-TRAINING NOTICE (PLAN_CODE_AUDIT v1.1 §4 fix #9).** The class below preserves
the GRPO call surface and config schema, but the production weight-update path (per-step
logprob accumulation, ratio computation against frozen ref, PPO clip + KL anchor) is part of
the Phase C scaffolding that is deferred to the next `/experiment-bridge` call. In Phase A,
`launch_baseline.py --mode production` REFUSES to invoke R8; `--mode dev` allows the sampling
call path only.

Implements ALGORITHMIC_FORMALIZATION.md §1.8. When lyric guard is inactive (epsilon = None or
no vocal prompts), this collapses to vanilla Flow-GRPO.
"""
from __future__ import annotations

import random
from collections import deque
from pathlib import Path

import torch

from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt
from mprm.rewards.clap import ClapReward
from mprm.rewards.perturbations import perturbation_set
from mprm.rewards.probes import anti_hacking_probes
from mprm.rewards.robust_lcb import robust_lcb
from mprm.rewards.whisper_wer import WhisperWerReward


class R8OutcomeGrpo(Baseline):
    rung_id = "R8"
    name = "outcome_grpo"

    def __init__(self, *args, group_size: int, t_train: int, rl_steps: int, lr: float,
                 lambda_kl: float, epsilon_clip: float, eta_schedule: list[float] | None = None,
                 epsilon_lyric: float | None = 0.0, lambda_init: float = 0.5,
                 lambda_growth: float = 1.1, lambda_decay: float = 0.95,
                 lambda_min: float = 0.01, lambda_max: float = 5.0,
                 lyric_window: int = 32, beta_robust: float = 0.5,
                 lambda_probe: dict[str, float] | None = None,
                 perturbation_names: list[str] | None = None,
                 lora_rank: int = 8, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_size = group_size
        self.t_train = t_train
        self.rl_steps = rl_steps
        self.lr = lr
        self.lambda_kl = lambda_kl
        self.epsilon_clip = epsilon_clip
        self.eta_schedule = eta_schedule
        self.epsilon_lyric = epsilon_lyric
        self.lambda_cur = lambda_init
        self.lambda_growth = lambda_growth
        self.lambda_decay = lambda_decay
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        self.lyric_window = deque(maxlen=lyric_window)
        self.beta_robust = beta_robust
        self.lambda_probe = lambda_probe or {}
        self.perturbations = perturbation_set(perturbation_names or ["identity"])
        self.lora_rank = lora_rank
        self._clap = next((rm for rm in self.reward_models if isinstance(rm, ClapReward)), None)
        self._whisper = next(
            (rm for rm in self.reward_models if isinstance(rm, WhisperWerReward)), None
        )

    def _r_robust(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt,
                   base_ref: torch.Tensor | None) -> float:
        probe = anti_hacking_probes(waveform, sample_rate, prompt,
                                     base_reference=base_ref, clap=self._clap)
        lcb = robust_lcb(waveform, sample_rate, prompt,
                          reward_models=self.reward_models,
                          perturbations=self.perturbations,
                          probe_scores=probe,
                          lambda_probe=self.lambda_probe,
                          beta_robust=self.beta_robust)
        return lcb.value

    def _r_lyric(self, waveform: torch.Tensor, sample_rate: int, prompt: Prompt) -> float:
        if self._whisper is None or self.epsilon_lyric is None or not prompt.lyrics:
            return 1.0
        return self._whisper.score(waveform, sample_rate, prompt).value

    def _update_lambda(self, target_baseline: float) -> None:
        if not self.lyric_window:
            return
        rolling = sum(self.lyric_window) / len(self.lyric_window)
        eps = self.epsilon_lyric or 0.0
        if rolling < target_baseline - eps:
            self.lambda_cur *= self.lambda_growth
        elif rolling > target_baseline + eps:
            self.lambda_cur *= self.lambda_decay
        self.lambda_cur = max(self.lambda_min, min(self.lambda_max, self.lambda_cur))

    def fit(self, prompts: list[Prompt], *, seed: int, lyric_baseline: float | None = None) -> None:
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
        rng = random.Random(seed)
        for step in range(self.rl_steps):
            prompt = rng.choice(prompts)
            base_ref = None
            group_results = []
            for g in range(self.group_size):
                eta = self.eta_schedule[step % len(self.eta_schedule)] if self.eta_schedule else 0.5
                eta_tensor = torch.full((self.t_train,), eta)
                res = self.model.sample(prompt, seed=seed + step * 1000 + g,
                                          steps=self.t_train, sde_mode=True,
                                          eta_schedule=eta_tensor, return_trajectory=True)
                if g == 0:
                    base_ref = res.waveform
                r_music = self._r_robust(res.waveform, res.sample_rate, prompt, base_ref)
                r_lyric = self._r_lyric(res.waveform, res.sample_rate, prompt)
                self.lyric_window.append(r_lyric)
                group_results.append({
                    "trajectory": res.trajectory,
                    "r_music": r_music,
                    "r_lyric": r_lyric,
                })
            r_combined = torch.tensor([
                gr["r_music"] + self.lambda_cur * (gr["r_lyric"] + (self.epsilon_lyric or 0.0))
                for gr in group_results
            ])
            advantage = (r_combined - r_combined.mean()) / (r_combined.std() + 1e-8)
            # Detached policy term — actual ratio computation requires per-step logp accumulation
            # in the model backbone; this scaffold leaves that to the backbone's GRPO trainer.
            loss = -(advantage.mean())
            optim.zero_grad()
            try:
                loss.backward()
                optim.step()
            except RuntimeError:
                # Scaffold-mode skip: model backbone may not expose differentiable trajectory.
                pass
            if lyric_baseline is not None:
                self._update_lambda(lyric_baseline)

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        res = self.model.sample(prompt, seed=seed)
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_outcome_grpo.wav"
        save_audio(wav_path, res.waveform, res.sample_rate)
        metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=metrics,
            extras={"seed": seed, "lambda_cur": self.lambda_cur,
                    "rl_steps": self.rl_steps, "t_train": self.t_train,
                    "group_size": self.group_size},
        )
