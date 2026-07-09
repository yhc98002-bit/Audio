from mprm.baselines.interface import Baseline, BaselineResult
from mprm.data.audio_io import save_audio
from mprm.data.prompts import Prompt


class R0BaseSampling(Baseline):
    rung_id = "R0"
    name = "base_sampling"

    def __init__(self, *args, cfg_scale: float | None = None, inference_steps: int | None = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.cfg_scale = cfg_scale
        self.inference_steps = inference_steps

    def run_on_prompt(self, prompt: Prompt, *, seed: int) -> BaselineResult:
        result = self.model.sample(prompt, seed=seed, cfg_scale=self.cfg_scale,
                                    steps=self.inference_steps)
        wav_path = self.output_dir / f"{prompt.prompt_id}_seed{seed}.wav"
        save_audio(wav_path, result.waveform, result.sample_rate)
        metrics = self.score_all_axes(result.waveform, result.sample_rate, prompt)
        return BaselineResult(
            rung_id=self.rung_id,
            run_id=f"{self.rung_id}-{prompt.prompt_id}-seed{seed}",
            prompt_id=prompt.prompt_id,
            waveform_path=str(wav_path),
            metrics=metrics,
            extras={"seed": seed, "cfg_scale": result.cfg_scale,
                    "inference_steps": result.inference_steps},
        )
