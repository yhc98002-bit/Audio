from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt
from mprm.rewards.clap import ClapReward
from mprm.rewards.perturbations import perturbation_set
from mprm.rewards.probes import anti_hacking_probes
from mprm.rewards.robust_lcb import robust_lcb


class R3RobustBoN(Baseline):
    rung_id = "R3"
    name = "robust_bon"

    def __init__(self, *args, n: int, beta_robust: float, lambda_probe: dict[str, float],
                 perturbation_names: list[str], cfg_scale: float | None = None,
                 inference_steps: int | None = None, base_reference_for_probes: bool = True,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.n = n
        self.beta_robust = beta_robust
        self.lambda_probe = lambda_probe
        self.perturbations = perturbation_set(perturbation_names)
        self.cfg_scale = cfg_scale
        self.inference_steps = inference_steps
        self.base_reference_for_probes = base_reference_for_probes
        self._clap_for_probe: ClapReward | None = None
        for rm in self.reward_models:
            if isinstance(rm, ClapReward):
                self._clap_for_probe = rm

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        candidates = []
        base_ref = None
        for i in range(self.n):
            res = self.model.sample(prompt, seed=seed + i,
                                     cfg_scale=self.cfg_scale, steps=self.inference_steps)
            if i == 0 and self.base_reference_for_probes:
                base_ref = res.waveform
            probe = anti_hacking_probes(res.waveform, res.sample_rate, prompt,
                                         base_reference=base_ref, clap=self._clap_for_probe)
            lcb = robust_lcb(res.waveform, res.sample_rate, prompt,
                              reward_models=self.reward_models,
                              perturbations=self.perturbations,
                              probe_scores=probe,
                              lambda_probe=self.lambda_probe,
                              beta_robust=self.beta_robust)
            candidates.append((res, lcb, probe))
        best = max(candidates, key=lambda c: c[1].value)
        best_res, best_lcb, best_probe = best
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_robust_bon{self.n}.wav"
        save_audio(wav_path, best_res.waveform, best_res.sample_rate)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics={
                "r_lcb": best_lcb.value,
                "mean_cells": best_lcb.mean_cells,
                "std_cells": best_lcb.std_cells,
                "probe_penalty": best_lcb.probe_penalty,
                **best_lcb.per_axis,
            },
            extras={"seed": seed, "n": self.n, "probe_scores": best_probe,
                    "candidates_lcb": [c[1].value for c in candidates]},
        )
