"""R6 — Robust Elite SFT (former S6 Stages 0–3).

Stage 0: headroom-curriculum prompt distribution.
Stage 1: BoN under curriculum.
Stage 2: robust LCB elite selection.
Stage 3: weighted SFT on robust elites.

Implements ALGORITHMIC_FORMALIZATION.md §1.5.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

import torch

from mprm.baselines.interface import Baseline, BaselineResult
from mprm.baselines.r5_sft_on_best import EliteSample
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt
from mprm.rewards.clap import ClapReward
from mprm.rewards.perturbations import perturbation_set
from mprm.rewards.probes import anti_hacking_probes
from mprm.rewards.robust_lcb import robust_lcb


@dataclass
class PromptStats:
    prompt_id: str
    bon_spread: float
    base_failure_rate: float
    evaluator_disagreement: float
    raw_weight: float


def capped_floor_weight(stats: PromptStats, n: int, w_min_factor: float = 0.5,
                         w_max_factor: float = 5.0) -> float:
    w_min = w_min_factor / n
    w_max = w_max_factor / n
    return max(w_min, min(stats.raw_weight, w_max))


class R6RobustEliteSft(Baseline):
    rung_id = "R6"
    name = "robust_elite_sft"

    def __init__(self, *args, n_bon: int, beta_robust: float, lambda_probe: dict[str, float],
                 perturbation_names: list[str], elite_quantile: float = 0.25,
                 sft_steps: int = 1000, lora_rank: int = 8, lr: float = 1e-5,
                 evaluator_disagreement_axis_pair: tuple[str, str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_bon = n_bon
        self.beta_robust = beta_robust
        self.lambda_probe = lambda_probe
        self.perturbations = perturbation_set(perturbation_names)
        self.elite_quantile = elite_quantile
        self.sft_steps = sft_steps
        self.lora_rank = lora_rank
        self.lr = lr
        self.evaluator_disagreement_axis_pair = evaluator_disagreement_axis_pair
        self._clap = next((rm for rm in self.reward_models if isinstance(rm, ClapReward)), None)
        self._stats: dict[str, PromptStats] = {}
        self._elites: dict[str, list[EliteSample]] = {}
        self._curriculum: dict[str, float] = {}

    def stage0_curriculum(self, prompts: list[Prompt], *, seed: int) -> dict[str, float]:
        for p in prompts:
            samples = [self.model.sample(p, seed=seed + i) for i in range(min(self.n_bon, 4))]
            metrics_list = [self.score_all_axes(s.waveform, s.sample_rate, p) for s in samples]
            spread = self._spread(metrics_list)
            failure_rate = self._failure_rate(metrics_list)
            disagreement = self._disagreement(metrics_list)
            raw = max(spread * (failure_rate + 1e-3) * (disagreement + 1e-3), 1e-6)
            self._stats[p.prompt_id] = PromptStats(
                prompt_id=p.prompt_id, bon_spread=spread, base_failure_rate=failure_rate,
                evaluator_disagreement=disagreement, raw_weight=raw,
            )
        n = len(prompts)
        weights = {pid: capped_floor_weight(s, n) for pid, s in self._stats.items()}
        total = sum(weights.values()) or 1.0
        self._curriculum = {pid: w / total for pid, w in weights.items()}
        return self._curriculum

    @staticmethod
    def _spread(metrics_list: list[dict[str, float]]) -> float:
        if not metrics_list:
            return 0.0
        primary = list(metrics_list[0].keys())[0]
        values = [m.get(primary, 0.0) for m in metrics_list]
        return float(statistics.pstdev(values)) if len(values) > 1 else 0.0

    @staticmethod
    def _failure_rate(metrics_list: list[dict[str, float]], threshold: float = 0.3) -> float:
        primary = list(metrics_list[0].keys())[0] if metrics_list else None
        if primary is None:
            return 0.0
        below = sum(1 for m in metrics_list if m.get(primary, 0.0) < threshold)
        return below / len(metrics_list)

    def _disagreement(self, metrics_list: list[dict[str, float]]) -> float:
        if not self.evaluator_disagreement_axis_pair:
            return 0.0
        a1, a2 = self.evaluator_disagreement_axis_pair
        deltas = [abs(m.get(a1, 0.0) - m.get(a2, 0.0)) for m in metrics_list]
        return float(statistics.mean(deltas)) if deltas else 0.0

    def stage1_2_bon_robust_elite(self, prompts: list[Prompt], *, seed: int) -> None:
        for p in prompts:
            candidates = []
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
                candidates.append((res, lcb))
            candidates.sort(key=lambda c: c[1].value, reverse=True)
            k = max(1, math.ceil(self.elite_quantile * len(candidates)))
            top = candidates[:k]
            self._elites[p.prompt_id] = [
                EliteSample(prompt_id=p.prompt_id,
                             z_one=self.model.encode(res.waveform),
                             metrics={"r_lcb": lcb.value, **lcb.per_axis})
                for (res, lcb) in top
            ]

    def stage3_weighted_sft(self, prompts: list[Prompt]) -> None:
        try:
            from peft import LoraConfig, get_peft_model
        except ImportError as e:
            raise ImportError("peft not installed; required for LoRA fine-tuning") from e
        peft_cfg = LoraConfig(r=self.lora_rank, lora_alpha=self.lora_rank * 2)
        backbone = getattr(self.model, "_pipeline", None)
        if backbone is None:
            raise RuntimeError("Model pipeline not loaded.")
        peft_model = get_peft_model(backbone, peft_cfg)
        optim = torch.optim.AdamW(peft_model.parameters(), lr=self.lr)
        prompt_map = {p.prompt_id: p for p in prompts}
        for step in range(self.sft_steps):
            pid = self._sample_curriculum()
            prompt = prompt_map[pid]
            elites = self._elites[pid]
            r_lcb_vec = torch.tensor([e.metrics["r_lcb"] for e in elites])
            elite_weights = torch.softmax(r_lcb_vec, dim=0)
            idx = int(torch.multinomial(elite_weights, num_samples=1))
            elite = elites[idx]
            tau = float(torch.rand(1))
            z_zero = torch.randn_like(elite.z_one)
            z_tau = (1 - tau) * z_zero + tau * elite.z_one
            v_target = elite.z_one - z_zero
            v_pred = self.model.predict_velocity(z_tau, tau, prompt)
            loss = torch.nn.functional.mse_loss(v_pred, v_target) * elite_weights[idx]
            optim.zero_grad()
            loss.backward()
            optim.step()

    def _sample_curriculum(self) -> str:
        keys = list(self._curriculum.keys())
        probs = torch.tensor([self._curriculum[k] for k in keys])
        idx = int(torch.multinomial(probs, num_samples=1))
        return keys[idx]

    def fit(self, prompts: list[Prompt], *, seed: int) -> None:
        self.stage0_curriculum(prompts, seed=seed)
        self.stage1_2_bon_robust_elite(prompts, seed=seed)
        self.stage3_weighted_sft(prompts)

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        res = self.model.sample(prompt, seed=seed)
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_robust_elite_sft.wav"
        save_audio(wav_path, res.waveform, res.sample_rate)
        metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=metrics,
            extras={"seed": seed,
                    "n_elites_per_prompt": {pid: len(es) for pid, es in self._elites.items()},
                    "curriculum_top10": dict(sorted(self._curriculum.items(),
                                                     key=lambda kv: kv[1], reverse=True)[:10])},
        )
