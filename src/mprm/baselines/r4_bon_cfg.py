from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


class R4BoNCfg(Baseline):
    rung_id = "R4"
    name = "bon_plus_cfg"

    def __init__(self, *args, n: int, cfg_values: list[float], primary_axis: str,
                 inference_steps: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.n = n
        self.cfg_values = cfg_values
        self.primary_axis = primary_axis
        self.inference_steps = inference_steps

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        candidates = []
        for cfg in self.cfg_values:
            for i in range(self.n):
                res = self.model.sample(prompt, seed=seed + i,
                                         cfg_scale=cfg, steps=self.inference_steps)
                metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
                candidates.append((res, metrics, cfg))
        best_res, best_metrics, best_cfg = max(
            candidates, key=lambda c: c[1].get(self.primary_axis, float("-inf"))
        )
        wav_path = self.output_dir / (
            f"{prompt.prompt_id}_seed{seed}_bon{self.n}_cfg{best_cfg}.wav"
        )
        save_audio(wav_path, best_res.waveform, best_res.sample_rate)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=best_metrics,
            extras={"seed": seed, "n": self.n, "best_cfg": best_cfg,
                    "n_total_candidates": len(candidates)},
        )
