from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


class R1CfgSweep(Baseline):
    rung_id = "R1"
    name = "cfg_sweep"

    def __init__(self, *args, cfg_values: list[float], inference_steps: int | None = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.cfg_values = cfg_values
        self.inference_steps = inference_steps

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        per_cfg: dict[float, dict[str, float]] = {}
        per_cfg_path: dict[float, str] = {}
        best_cfg = None
        best_value = float("-inf")
        for w in self.cfg_values:
            res = self.model.sample(prompt, seed=seed, cfg_scale=w, steps=self.inference_steps)
            wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}_cfg{w}.wav"
            save_audio(wav_path, res.waveform, res.sample_rate)
            per_cfg_path[w] = str(wav_path)
            metrics = self.score_all_axes(res.waveform, res.sample_rate, prompt)
            per_cfg[w] = metrics
            primary = metrics.get("aesthetic_pq", next(iter(metrics.values())))
            if primary > best_value:
                best_value = primary
                best_cfg = w
        canonical = best_cfg if best_cfg is not None else self.cfg_values[0]
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=per_cfg_path[canonical],
            metrics=per_cfg[canonical],
            extras={"seed": seed, "per_cfg": per_cfg, "per_cfg_path": per_cfg_path,
                    "best_cfg": best_cfg},
        )
