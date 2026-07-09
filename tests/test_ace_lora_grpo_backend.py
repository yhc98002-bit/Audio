from __future__ import annotations

from dataclasses import dataclass

import torch

from mprm.training.ace_lora_grpo import (
    AceLoraGrpoBackend,
    BackendConfig,
    CapturedStep,
    GrpoRollout,
    compute_group_advantages,
)


class _DecodeOut:
    def __init__(self, sample: torch.Tensor):
        self.sample = sample


class _TinyAttention(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.to_q = torch.nn.Linear(2, 2, bias=False)
        self.to_k = torch.nn.Linear(2, 2, bias=False)
        self.to_v = torch.nn.Linear(2, 2, bias=False)
        self.to_out = torch.nn.ModuleList([torch.nn.Linear(2, 2, bias=False)])


class _TinyTransformer(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.attn = _TinyAttention()
        self.frozen_ff = torch.nn.Linear(2, 2, bias=False)

    def forward(self, hidden_states, **kwargs):
        return self.decode(hidden_states, **kwargs)

    def decode(self, hidden_states, **_kwargs):
        # (B, C, H, T) -> (B, T, C)
        x = hidden_states.mean(dim=2).transpose(1, 2)
        y = self.attn.to_q(x) + self.attn.to_v(x)
        y = self.attn.to_out[0](y)
        y = y.transpose(1, 2).unsqueeze(2).expand_as(hidden_states)
        return _DecodeOut(y)


class _TinyPipeline:
    def __init__(self):
        self.ace_step_transformer = _TinyTransformer()
        self.other = torch.nn.Linear(2, 2, bias=False)


@dataclass
class _Prompt:
    prompt_id: str = "p0"


class _TinyAceModel:
    device = "cpu"
    dtype = "float32"

    def __init__(self):
        self._pipeline = _TinyPipeline()

    def _ensure_loaded(self):
        return None

    def _build_condition_cache(self, _prompt):
        return {
            "dtype": torch.float32,
            "encoder_hidden_cond": torch.zeros(1, 1, 2),
            "encoder_mask_cond": torch.ones(1, 1),
            "encoder_hidden_null": torch.zeros(1, 1, 2),
            "encoder_mask_null": torch.ones(1, 1),
        }


def _rollout(prompt_id: str, reward: float) -> GrpoRollout:
    latent = torch.randn(1, 2, 1, 4)
    z0 = torch.zeros_like(latent) + 0.1
    return GrpoRollout(
        prompt_id=prompt_id,
        group_id="g0",
        reward=reward,
        prompt=_Prompt(prompt_id),
        steps=[CapturedStep(latent=latent, sigma=0.7, step_index=0, cfg_active=False)],
        z0=z0,
    )


def test_compute_group_advantages_zero_variance_group():
    adv, info = compute_group_advantages([1.0, 1.0], ["g", "g"])
    assert torch.equal(adv, torch.zeros_like(adv))
    assert info["n_zero_variance_groups"] == 1


def test_lora_insertion_freezes_base_and_trains_adapters(tmp_path):
    backend = AceLoraGrpoBackend(
        _TinyAceModel(),
        BackendConfig(lora_rank=2, learning_rate=1e-3),
        output_dir=tmp_path,
        method_id="unit",
        reward_mode="terminal",
    )
    summary = backend.ensure_lora()
    assert summary["trainable_params"] > 0
    assert summary["base_parameters_frozen"] is True
    assert summary["lora_module_count"] >= 1
    for name, param in backend._pipeline_named_parameters():
        if "lora_" not in name:
            assert not param.requires_grad


def test_update_changes_adapter_not_base_and_checkpoint_resumes(tmp_path):
    backend = AceLoraGrpoBackend(
        _TinyAceModel(),
        BackendConfig(lora_rank=2, learning_rate=1e-2, max_grad_norm=None),
        output_dir=tmp_path,
        method_id="unit",
        reward_mode="terminal",
    )
    backend.ensure_lora()
    rollouts = [_rollout("p0", 0.0), _rollout("p1", 1.0)]
    backend.cache_old_and_ref_logps(rollouts)
    metrics = backend.update(rollouts)
    assert metrics["adapter_updated"] is True
    assert metrics["frozen_parameters"]["unchanged"] is True
    assert metrics["nonzero_grad_tensors"] > 0
    ckpt = backend.save_checkpoint()
    resumed = AceLoraGrpoBackend(
        _TinyAceModel(),
        BackendConfig(lora_rank=2, learning_rate=1e-2, max_grad_norm=None),
        output_dir=tmp_path / "resume",
        method_id="unit",
        reward_mode="terminal",
    )
    resumed.ensure_lora()
    payload = resumed.load_checkpoint(ckpt)
    assert payload["schema_version"] == "ace_step_lora_grpo_checkpoint_v1"
    assert resumed.compare_frozen_snapshot()["unchanged"] is True
