"""R9 — S7 sampler-control rung. STOP-B-8 introduces an M1a-launchable "lite" variant.

Original R9 (per ALGORITHMIC_FORMALIZATION.md §1.6 + CONTROL_DESIGN §5.1):
  Frozen weights + contextual-bandit / BO controller over 4 axes:
  (cfg_scale, sde_eta_mean, step_allocation_late_frac, negative_prompt_strength).
  S7 is the weight-update-necessity falsifier; if R9 ≈ R21 (M-PRM), pivot per
  ALGORITHM_TOURNAMENT.md.

STOP-B-8 reality:
  Three of those four axes (sde_eta_mean, step_allocation_late_frac,
  negative_prompt_strength) are NOT exposed by the public upstream ACE-Step v1
  `__call__` (see `acestep.pipeline_ace_step.ACEStepPipeline.__call__` around
  line 1445). Monkey-patching upstream internals is deferred to STOP-B-9. Until
  then, R9 runs in **r9_lite_public_api** mode over public-API axes only:

  - `cfg_scale`            → upstream `guidance_scale`
  - `omega_scale`          → upstream `omega_scale` (APG strength)
  - `guidance_interval`    → upstream `guidance_interval` (fraction of steps that apply CFG)

**Methodology consequence**: R9-lite is a **WEAKER sampler-control falsifier** for M1a.
A pass on the s7-explain check in lite mode does NOT rule out the stronger 4-axis
sampler-controller from explaining the BoN headroom — the lite controller's search
space is a strict subset of the full one. This is a known M1a-only limitation,
acknowledged in `orbit-research/STOP_B8_BLOCKER_REPORT.md` and surfaced into each
result's `extras["r9_mode"]` and into the M1a gate-decision JSON.
"""
from __future__ import annotations

import random
import warnings
from dataclasses import dataclass

from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt
from mprm.rewards.clap import ClapReward
from mprm.rewards.perturbations import perturbation_set
from mprm.rewards.probes import anti_hacking_probes
from mprm.rewards.robust_lcb import robust_lcb


R9_MODE_LITE = "r9_lite_public_api"
R9_MODE_FULL = "r9_full_4axis"  # blocked; deferred to STOP-B-9


@dataclass
class SamplerScheduleLite:
    """R9-lite schedule over upstream-public axes only (STOP-B-8)."""
    cfg_scale: float
    omega_scale: float
    guidance_interval: float

    def vec(self) -> list[float]:
        return [self.cfg_scale, self.omega_scale, self.guidance_interval]

    def upstream_extras(self) -> dict[str, float]:
        """Build the `extras` dict for `AceStepModel.sample(..., extras=…)`.

        Note: cfg_scale is passed via the dedicated `cfg_scale` kwarg, not via
        extras. Only the non-default upstream knobs go through extras.
        """
        return {
            "omega_scale": float(self.omega_scale),
            "guidance_interval": float(self.guidance_interval),
        }


# Back-compat alias: legacy code referenced `SamplerSchedule`. Keep the alias so
# import sites don't break, but redirect to the lite class.
SamplerSchedule = SamplerScheduleLite


class R9SamplerController(Baseline):
    rung_id = "R9"
    name = "s7_sampler_control"

    def __init__(self, *args, search_budget: int, cfg_range: tuple[float, float],
                 eta_range: tuple[float, float] | None = None,
                 step_alloc_range: tuple[float, float] | None = None,
                 neg_prompt_range: tuple[float, float] | None = None,
                 omega_range: tuple[float, float] = (5.0, 15.0),
                 guidance_interval_range: tuple[float, float] = (0.3, 0.7),
                 inference_steps: int,
                 beta_robust: float, lambda_probe: dict[str, float],
                 perturbation_names: list[str], exploration_eps: float = 0.2,
                 mode: str = R9_MODE_LITE, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_budget = search_budget
        self.cfg_range = cfg_range
        self.omega_range = omega_range
        self.guidance_interval_range = guidance_interval_range
        self.inference_steps = inference_steps
        self.beta_robust = beta_robust
        self.lambda_probe = lambda_probe
        self.perturbations = perturbation_set(perturbation_names)
        self.exploration_eps = exploration_eps
        self.mode = mode
        self._observations: list[tuple[SamplerScheduleLite, float]] = []
        self._clap = next((rm for rm in self.reward_models if isinstance(rm, ClapReward)), None)

        if mode != R9_MODE_LITE:
            raise NotImplementedError(
                f"STOP-B-8: R9 mode {mode!r} is not implemented. Only {R9_MODE_LITE!r} is"
                " supported for M1a (upstream v1 public API exposes only 3 of the 4 original"
                " sampler-control axes). Full R9 deferred to STOP-B-9."
            )

        # Surface the deprecation of the original 4-axis schedule loudly. The
        # constructor still accepts the old ranges so existing configs keep loading,
        # but they have no effect.
        deprecated = []
        if eta_range is not None and eta_range != (0.0, 0.0):
            deprecated.append(f"eta_range={eta_range}")
        if step_alloc_range is not None and step_alloc_range != (0.0, 0.0):
            deprecated.append(f"step_alloc_range={step_alloc_range}")
        if neg_prompt_range is not None and neg_prompt_range != (0.0, 0.0):
            deprecated.append(f"neg_prompt_range={neg_prompt_range}")
        if deprecated:
            warnings.warn(
                "STOP-B-8 R9-lite ignores deprecated 4-axis ranges: " + ", ".join(deprecated)
                + ". Upstream v1 public API does not expose sde-eta /"
                " step-allocation / negative-prompt-strength. M1a runs the"
                " lite (cfg + omega + guidance_interval) sampler-control instead.",
                stacklevel=2,
            )

    @staticmethod
    def _uniform(lo: float, hi: float, rng: random.Random) -> float:
        return rng.uniform(lo, hi)

    @staticmethod
    def _clip(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    def _propose(self, rng: random.Random) -> SamplerScheduleLite:
        if not self._observations or rng.random() < self.exploration_eps:
            return SamplerScheduleLite(
                cfg_scale=self._uniform(*self.cfg_range, rng),
                omega_scale=self._uniform(*self.omega_range, rng),
                guidance_interval=self._uniform(*self.guidance_interval_range, rng),
            )
        best = max(self._observations, key=lambda obs: obs[1])[0]
        return SamplerScheduleLite(
            cfg_scale=self._clip(best.cfg_scale + rng.gauss(0, 0.3), *self.cfg_range),
            omega_scale=self._clip(best.omega_scale + rng.gauss(0, 0.5), *self.omega_range),
            guidance_interval=self._clip(best.guidance_interval + rng.gauss(0, 0.05),
                                          *self.guidance_interval_range),
        )

    def _sample_with_schedule(self, prompt: Prompt, sched: SamplerScheduleLite, seed: int):
        return self.model.sample(
            prompt,
            seed=seed,
            cfg_scale=sched.cfg_scale,
            steps=self.inference_steps,
            extras=sched.upstream_extras(),
        )

    def search(self, prompts: list[Prompt], *, seed: int) -> SamplerScheduleLite:
        rng = random.Random(seed)
        for round_idx in range(self.search_budget):
            prompt = rng.choice(prompts)
            sched = self._propose(rng)
            res = self._sample_with_schedule(prompt, sched, seed + round_idx)
            probe = anti_hacking_probes(res.waveform, res.sample_rate, prompt, clap=self._clap)
            lcb = robust_lcb(res.waveform, res.sample_rate, prompt,
                              reward_models=self.reward_models,
                              perturbations=self.perturbations,
                              probe_scores=probe,
                              lambda_probe=self.lambda_probe,
                              beta_robust=self.beta_robust)
            self._observations.append((sched, lcb.value))
        return max(self._observations, key=lambda obs: obs[1])[0]

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        if not self._observations:
            raise RuntimeError("Call search(prompts, seed=...) before run_on_prompt.")
        best = max(self._observations, key=lambda obs: obs[1])[0]
        res = self._sample_with_schedule(prompt, best, seed)
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_s7.wav"
        save_audio(wav_path, res.waveform, res.sample_rate)
        metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
        sampling_extras = getattr(res, "extras", {}) or {}
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=metrics,
            extras={
                "seed": seed,
                "schedule": best.vec(),
                "schedule_axes": ["cfg_scale", "omega_scale", "guidance_interval"],
                "n_observations": len(self._observations),
                "r9_mode": self.mode,
                "stop_b8_note": (
                    "R9-lite uses public upstream-v1 axes only; this is a WEAKER"
                    " sampler-control falsifier than the original 4-axis design."
                    " See orbit-research/STOP_B8_BLOCKER_REPORT.md."
                ),
                "applied_extras": sampling_extras.get("applied_extras", {}),
                "ignored_extras": sampling_extras.get("ignored_extras", {}),
            },
        )
