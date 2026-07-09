from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelConfig:
    name: str
    backbone: str
    sample_rate: int
    duration_seconds: float
    cfg_default: float
    inference_steps: int
    latent_rate_factor: int
    cache_dir: str | None = None


@dataclass
class RewardConfig:
    use_clap: bool = True
    clap_variant: str = "laion-clap-music-630k"
    use_audiobox: bool = True
    audiobox_variant: str = "facebookresearch/audiobox-aesthetics"
    use_whisper: bool = True
    whisper_variant: str = "large-v3"
    use_mert: bool = True
    mert_variant: str = "m-a-p/MERT-v1-95M"
    use_fad: bool = True
    use_demucs: bool = True
    demucs_variant: str = "htdemucs"
    beta_robust: float = 0.5
    lambda_probe: dict[str, float] = field(default_factory=lambda: {
        "silence_fraction": 0.0,
        "autocorr_repetition": 0.0,
        "off_prompt_distance": 0.0,
        "hf_artifact_score": 0.0,
        "broken_section_indicator": 0.0,
    })


@dataclass
class BaselineConfig:
    rung_id: str
    name: str
    description: str
    seed: int
    prompts_path: str
    output_dir: str
    bon_n: int | None = None
    cfg_values: list[float] | None = None
    sft_steps: int | None = None
    rl_steps: int | None = None
    group_size: int | None = None
    t_train: int | None = None
    learning_rate: float | None = None
    lambda_kl: float | None = None
    epsilon_clip: float | None = None
    lora_rank: int = 8
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    project: str
    run_id: str
    split: str
    model: ModelConfig
    reward: RewardConfig
    baseline: BaselineConfig
    run_ledger_path: str = "orbit-research/RUN_LEDGER.jsonl"
    wandb_project: str | None = None


def load_config(path: str | Path) -> Config:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    model = ModelConfig(**raw["model"])
    reward = RewardConfig(**raw.get("reward", {}))
    baseline = BaselineConfig(**raw["baseline"])
    return Config(
        project=raw["project"],
        run_id=raw["run_id"],
        split=raw["split"],
        model=model,
        reward=reward,
        baseline=baseline,
        run_ledger_path=raw.get("run_ledger_path", "orbit-research/RUN_LEDGER.jsonl"),
        wandb_project=raw.get("wandb_project"),
    )


def dump_config(cfg: Config) -> dict[str, Any]:
    return asdict(cfg)
