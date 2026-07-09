"""Shared ACE-Step LoRA/GRPO backend.

This backend implements the adapter-only training primitive described in
``orbit-research/ACE_STEP_LORA_GRPO_BACKEND_SPEC.md``. Reward computation stays
outside this module; this code consumes detached rewards/advantages and updates
only LoRA adapters on the ACE-Step diffusion transformer.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import torch


DEFAULT_LORA_TARGET_MODULES: tuple[str, ...] = (
    "to_q",
    "to_k",
    "to_v",
    "to_out.0",
    "add_q_proj",
    "add_k_proj",
    "add_v_proj",
    "to_add_out",
)


@dataclass(frozen=True)
class BackendConfig:
    """Runtime knobs for the shared ACE-Step LoRA/GRPO backend."""

    lora_rank: int = 8
    lora_alpha: int | None = None
    lora_dropout: float = 0.0
    learning_rate: float = 1.0e-6
    epsilon_clip: float = 0.2
    lambda_kl: float = 0.05
    ratio_variance: float = 1.0
    ratio_clip_log: float = 5.0
    sigma_floor: float = 1.0e-5
    advantage_eps: float = 1.0e-8
    max_grad_norm: float | None = 1.0
    target_modules: tuple[str, ...] = DEFAULT_LORA_TARGET_MODULES
    estimator_type: str = "flow_matching_surrogate"
    exact_logprob: bool = False
    advantage_gain: float = 1.0
    log_post_update_diagnostics: bool = False
    track_adapter_norm_delta: bool = False


@dataclass
class CapturedStep:
    """One captured flow step used by the surrogate ratio estimator."""

    latent: torch.Tensor
    sigma: float
    step_index: int
    cfg_active: bool = True


@dataclass
class GrpoRollout:
    """Detached rollout record consumed by the GRPO loss."""

    prompt_id: str
    group_id: str
    reward: float
    prompt: Any
    steps: list[CapturedStep]
    z0: torch.Tensor
    old_logp: float | None = None
    ref_logp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_adapter_param(name: str) -> bool:
    return "lora_" in name or ".modules_to_save." in name


def _tensor_digest(tensor: torch.Tensor) -> str:
    data = tensor.detach().float().cpu().contiguous().numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def _stats(values: torch.Tensor) -> dict[str, float]:
    if values.numel() == 0:
        return {"mean": math.nan, "std": math.nan, "min": math.nan, "max": math.nan}
    return {
        "mean": float(values.mean().detach().cpu().item()),
        "std": float(values.std(unbiased=False).detach().cpu().item()),
        "min": float(values.min().detach().cpu().item()),
        "max": float(values.max().detach().cpu().item()),
    }


def compute_group_advantages(
    rewards: torch.Tensor | list[float],
    group_ids: list[str],
    *,
    eps: float = 1.0e-8,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Normalize detached rewards within each rollout group."""

    r = torch.as_tensor(rewards, dtype=torch.float32)
    if r.numel() != len(group_ids):
        raise ValueError(f"rewards/group_ids length mismatch: {r.numel()} != {len(group_ids)}")
    adv = torch.zeros_like(r)
    zero_groups: list[str] = []
    for group_id in sorted(set(group_ids)):
        idx = torch.tensor([i for i, gid in enumerate(group_ids) if gid == group_id])
        vals = r[idx]
        std = vals.std(unbiased=False)
        if vals.numel() < 2 or float(std.item()) <= eps:
            zero_groups.append(group_id)
            continue
        adv[idx] = (vals - vals.mean()) / (std + eps)
    info = {
        "reward": _stats(r),
        "advantage": _stats(adv),
        "zero_variance_groups": zero_groups,
        "n_zero_variance_groups": len(zero_groups),
    }
    return adv, info


class AceLoraGrpoBackend:
    """Adapter-only GRPO backend for ACE-Step.

    The wrapped model must be an ``AceStepModel``-like object exposing
    ``_ensure_loaded()``, ``_pipeline``, ``device``, ``dtype``, and
    ``_build_condition_cache(prompt)``.
    """

    backend_id = "ace_step_lora_grpo_v1"

    def __init__(
        self,
        model: Any,
        config: BackendConfig | None = None,
        *,
        output_dir: str | Path,
        method_id: str,
        reward_mode: str,
        ledger_path: str | Path | None = None,
    ):
        self.model = model
        self.config = config or BackendConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.method_id = method_id
        self.reward_mode = reward_mode
        self.ledger_path = Path(ledger_path) if ledger_path is not None else (
            self.output_dir / "run_ledger.jsonl"
        )
        self.policy = None
        self.optimizer: torch.optim.Optimizer | None = None
        self._base_snapshot: dict[str, str] = {}
        self._step = 0
        self._last_metrics: dict[str, Any] = {}

    # ------------------------------------------------------------------ setup

    def ensure_lora(self) -> dict[str, Any]:
        """Load ACE-Step, insert LoRA into intended transformer modules, freeze base."""

        self.model._ensure_loaded()
        pipeline = self.model._pipeline
        transformer = pipeline.ace_step_transformer

        for _name, param in self._pipeline_named_parameters():
            param.requires_grad_(False)

        from peft import LoraConfig, get_peft_model

        alpha = self.config.lora_alpha or self.config.lora_rank * 2
        peft_cfg = LoraConfig(
            r=self.config.lora_rank,
            lora_alpha=alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=list(self.config.target_modules),
            bias="none",
        )
        self.policy = get_peft_model(transformer, peft_cfg)
        pipeline.ace_step_transformer = self.policy

        trainable = [(n, p) for n, p in self._pipeline_named_parameters() if p.requires_grad]
        if not trainable:
            raise RuntimeError("LoRA insertion produced no trainable parameters")
        bad_trainable = [n for n, _p in trainable if not _is_adapter_param(n)]
        if bad_trainable:
            raise RuntimeError(f"non-adapter parameters are trainable: {bad_trainable[:8]}")

        self.optimizer = torch.optim.AdamW(
            [p for _n, p in trainable],
            lr=self.config.learning_rate,
        )
        self._base_snapshot = self.snapshot_frozen_parameters(max_tensors=8)
        summary = self.parameter_summary()
        self.write_ledger_event("lora_inserted", metrics=summary)
        return summary

    def parameter_summary(self) -> dict[str, Any]:
        self.model._ensure_loaded()
        trainable_params = 0
        frozen_params = 0
        trainable_tensors = 0
        frozen_tensors = 0
        adapter_tensors = 0
        lora_module_prefixes: set[str] = set()
        for name, param in self._pipeline_named_parameters():
            n = int(param.numel())
            if param.requires_grad:
                trainable_params += n
                trainable_tensors += 1
            else:
                frozen_params += n
                frozen_tensors += 1
            if _is_adapter_param(name):
                adapter_tensors += 1
                parts = name.split(".")
                if "lora_A" in parts:
                    lora_module_prefixes.add(".".join(parts[: parts.index("lora_A")]))
                elif "lora_B" in parts:
                    lora_module_prefixes.add(".".join(parts[: parts.index("lora_B")]))
        return {
            "backend_id": self.backend_id,
            "method_id": self.method_id,
            "reward_mode": self.reward_mode,
            "target_modules": list(self.config.target_modules),
            "lora_rank": self.config.lora_rank,
            "trainable_params": trainable_params,
            "frozen_params": frozen_params,
            "trainable_tensors": trainable_tensors,
            "frozen_tensors": frozen_tensors,
            "adapter_tensors": adapter_tensors,
            "lora_module_count": len(lora_module_prefixes),
            "lora_module_prefixes_sample": sorted(lora_module_prefixes)[:20],
            "base_parameters_frozen": self.base_parameters_frozen(),
        }

    def base_parameters_frozen(self) -> bool:
        self.model._ensure_loaded()
        for name, param in self._pipeline_named_parameters():
            if not _is_adapter_param(name) and param.requires_grad:
                return False
        return True

    def snapshot_frozen_parameters(self, max_tensors: int = 8) -> dict[str, str]:
        self.model._ensure_loaded()
        out: dict[str, str] = {}
        for name, param in self._pipeline_named_parameters():
            if _is_adapter_param(name):
                continue
            out[name] = _tensor_digest(param)
            if len(out) >= max_tensors:
                break
        return out

    def compare_frozen_snapshot(self, snapshot: dict[str, str] | None = None) -> dict[str, Any]:
        snapshot = snapshot or self._base_snapshot
        current = dict(self._pipeline_named_parameters())
        changed = []
        for name, digest in snapshot.items():
            if name not in current:
                changed.append(name)
                continue
            if _tensor_digest(current[name]) != digest:
                changed.append(name)
        return {"checked": len(snapshot), "changed": changed, "unchanged": not changed}

    def adapter_digest(self) -> str:
        self.model._ensure_loaded()
        h = hashlib.sha256()
        n_tensors = 0
        for name, param in sorted(self._pipeline_named_parameters()):
            if not _is_adapter_param(name):
                continue
            h.update(name.encode("utf-8"))
            h.update(param.detach().float().cpu().contiguous().numpy().tobytes())
            n_tensors += 1
        h.update(str(n_tensors).encode("ascii"))
        return h.hexdigest()

    def adapter_l2_norm(self) -> float:
        self.model._ensure_loaded()
        total = 0.0
        for name, param in self._pipeline_named_parameters():
            if not _is_adapter_param(name):
                continue
            norm = float(param.detach().float().cpu().norm().item())
            total += norm * norm
        return math.sqrt(total)

    def _pipeline_named_parameters(self) -> list[tuple[str, torch.nn.Parameter]]:
        """Return named parameters even when ACEStepPipeline is not an nn.Module."""

        pipeline = self.model._pipeline
        out: list[tuple[str, torch.nn.Parameter]] = []
        seen: set[int] = set()
        if hasattr(pipeline, "named_parameters"):
            for name, param in pipeline.named_parameters():
                out.append((name, param))
                seen.add(id(param))
        for attr, value in vars(pipeline).items():
            if not isinstance(value, torch.nn.Module):
                continue
            for name, param in value.named_parameters():
                if id(param) in seen:
                    continue
                out.append((f"{attr}.{name}", param))
                seen.add(id(param))
        return out

    # -------------------------------------------------------------- estimator

    def _device_and_dtype(self) -> tuple[torch.device, torch.dtype]:
        device = torch.device(getattr(self.model, "device", "cuda"))
        dtype_str = getattr(self.model, "dtype", "bfloat16")
        if dtype_str == "bfloat16":
            dtype = torch.bfloat16
        elif dtype_str == "float16":
            dtype = torch.float16
        else:
            dtype = torch.float32
        return device, dtype

    @staticmethod
    def _align_z0(z0: torch.Tensor, latent: torch.Tensor) -> tuple[torch.Tensor, int]:
        if z0.dim() == 3:
            z0 = z0.unsqueeze(0)
        if latent.dim() == 3:
            latent = latent.unsqueeze(0)
        mismatch = int(z0.shape[-1] - latent.shape[-1])
        if z0.shape[-1] > latent.shape[-1]:
            z0 = z0[..., : latent.shape[-1]]
        elif z0.shape[-1] < latent.shape[-1]:
            z0 = torch.nn.functional.pad(z0, (0, latent.shape[-1] - z0.shape[-1]))
        return z0, mismatch

    def _condition_cache(self, prompt: Any) -> dict[str, Any]:
        with torch.no_grad():
            return self.model._build_condition_cache(prompt)

    def _velocity(
        self,
        step: CapturedStep,
        prompt: Any,
        *,
        condition_cache: dict[str, Any] | None = None,
    ) -> torch.Tensor:
        device, dtype = self._device_and_dtype()
        cache = condition_cache or self._condition_cache(prompt)
        z = step.latent.to(device=device, dtype=dtype)
        if z.dim() == 3:
            z = z.unsqueeze(0)
        bsz, _channels, _height, frame_length = z.shape
        timestep = torch.full(
            (bsz,),
            float(step.sigma) * 1000.0,
            device=device,
            dtype=torch.float32,
        )
        attention_mask = torch.ones(bsz, frame_length, device=device, dtype=dtype)
        transformer = self.model._pipeline.ace_step_transformer
        v_cond = transformer.decode(
            hidden_states=z,
            attention_mask=attention_mask,
            encoder_hidden_states=cache["encoder_hidden_cond"],
            encoder_hidden_mask=cache["encoder_mask_cond"],
            output_length=frame_length,
            timestep=timestep,
        ).sample
        if step.cfg_active:
            v_uncond = transformer.decode(
                hidden_states=z,
                attention_mask=attention_mask,
                encoder_hidden_states=cache["encoder_hidden_null"],
                encoder_hidden_mask=cache["encoder_mask_null"],
                output_length=frame_length,
                timestep=timestep,
            ).sample
            cfg_scale = float(getattr(self, "cfg_scale", 5.0))
            v_out = v_uncond + cfg_scale * (v_cond - v_uncond)
        else:
            v_out = v_cond
        return v_out.float()

    def _adapter_disabled(self):
        if self.policy is not None and hasattr(self.policy, "disable_adapter"):
            return self.policy.disable_adapter()
        return contextlib.nullcontext()

    def rollout_logp(
        self,
        rollout: GrpoRollout,
        *,
        reference: bool = False,
        grad: bool = True,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        if self.policy is None:
            raise RuntimeError("ensure_lora() must be called before rollout_logp()")
        cache = self._condition_cache(rollout.prompt)
        logps: list[torch.Tensor] = []
        align_mismatches: list[int] = []
        ctx1 = self._adapter_disabled() if reference else contextlib.nullcontext()
        ctx2 = contextlib.nullcontext() if grad else torch.no_grad()
        with ctx1:
            with ctx2:
                for step in rollout.steps:
                    latent = step.latent.float()
                    if latent.dim() == 3:
                        latent = latent.unsqueeze(0)
                    z0, mismatch = self._align_z0(rollout.z0.float(), latent)
                    align_mismatches.append(mismatch)
                    target = (latent - z0) / max(float(step.sigma), self.config.sigma_floor)
                    v = self._velocity(step, rollout.prompt, condition_cache=cache)
                    target = target.to(v.device, dtype=v.dtype)
                    mse = (v - target).pow(2).mean()
                    logps.append(-mse / (2.0 * self.config.ratio_variance))
        if not logps:
            raise ValueError(f"rollout {rollout.prompt_id} has no selected steps")
        total = torch.stack(logps).sum()
        info = {
            "selected_step_indices": [int(s.step_index) for s in rollout.steps],
            "selected_sigmas": [float(s.sigma) for s in rollout.steps],
            "z0_latent_frame_mismatches": align_mismatches,
            "n_selected_steps": len(logps),
        }
        return total, info

    def cache_old_and_ref_logps(self, rollouts: list[GrpoRollout]) -> list[dict[str, Any]]:
        infos: list[dict[str, Any]] = []
        for rollout in rollouts:
            old_logp, old_info = self.rollout_logp(rollout, reference=False, grad=False)
            ref_logp, ref_info = self.rollout_logp(rollout, reference=True, grad=False)
            rollout.old_logp = float(old_logp.detach().cpu().item())
            rollout.ref_logp = float(ref_logp.detach().cpu().item())
            infos.append({
                "prompt_id": rollout.prompt_id,
                "old_logp": rollout.old_logp,
                "ref_logp": rollout.ref_logp,
                "old_info": old_info,
                "ref_info": ref_info,
            })
        return infos

    # ------------------------------------------------------------------ update

    def update(self, rollouts: list[GrpoRollout]) -> dict[str, Any]:
        if self.optimizer is None:
            raise RuntimeError("ensure_lora() must be called before update()")
        if not rollouts:
            raise ValueError("cannot update on empty rollout list")
        if any(r.old_logp is None or r.ref_logp is None for r in rollouts):
            self.cache_old_and_ref_logps(rollouts)

        rewards = torch.tensor([float(r.reward) for r in rollouts], dtype=torch.float32)
        group_ids = [r.group_id for r in rollouts]
        advantages, adv_info = compute_group_advantages(
            rewards,
            group_ids,
            eps=self.config.advantage_eps,
        )
        advantage_gain = float(self.config.advantage_gain)
        advantages = advantages * advantage_gain
        adv_info["advantage_gain"] = advantage_gain
        adv_info["advantage_after_gain"] = _stats(advantages)
        device, _dtype = self._device_and_dtype()
        advantages = advantages.to(device)

        old_logps = torch.tensor([float(r.old_logp) for r in rollouts], device=device)
        ref_logps = torch.tensor([float(r.ref_logp) for r in rollouts], device=device)
        before_digest = self.adapter_digest()
        before_adapter_l2 = self.adapter_l2_norm() if self.config.track_adapter_norm_delta else None
        self.optimizer.zero_grad(set_to_none=True)

        new_logps_detached: list[torch.Tensor] = []
        log_ratios_detached: list[torch.Tensor] = []
        ratios_detached: list[torch.Tensor] = []
        per_loss_detached: list[torch.Tensor] = []
        per_rollout_info: list[dict[str, Any]] = []
        n_rollouts = float(len(rollouts))
        for idx, rollout in enumerate(rollouts):
            logp, info = self.rollout_logp(rollout, reference=False, grad=True)
            old_logp_i = old_logps[idx]
            ref_logp_i = ref_logps[idx]
            adv_i = advantages[idx]
            log_ratio_i = logp - old_logp_i
            log_ratio_clamped_i = torch.clamp(
                log_ratio_i,
                min=-self.config.ratio_clip_log,
                max=self.config.ratio_clip_log,
            )
            ratio_i = torch.exp(log_ratio_clamped_i)
            unclipped_i = ratio_i * adv_i
            clipped_ratio_i = torch.clamp(
                ratio_i,
                min=1.0 - self.config.epsilon_clip,
                max=1.0 + self.config.epsilon_clip,
            )
            clipped_i = clipped_ratio_i * adv_i
            policy_loss_i = -torch.minimum(unclipped_i, clipped_i) / n_rollouts
            kl_ref_i = (logp - ref_logp_i) / n_rollouts
            loss_i = policy_loss_i + self.config.lambda_kl * kl_ref_i
            finite_tensors_i = [loss_i, ratio_i, logp, log_ratio_i, kl_ref_i]
            if not all(bool(torch.isfinite(t).all().detach().cpu().item()) for t in finite_tensors_i):
                raise RuntimeError("nonfinite loss/logp/ratio/KL detected before optimizer step")
            loss_i.backward()
            new_logps_detached.append(logp.detach())
            log_ratios_detached.append(log_ratio_i.detach())
            ratios_detached.append(ratio_i.detach())
            per_loss_detached.append(loss_i.detach())
            per_rollout_info.append({"prompt_id": rollout.prompt_id, **info})
        new_logp = torch.stack(new_logps_detached)
        log_ratio = new_logp - old_logps
        ratio = torch.stack(ratios_detached)
        unclipped = ratio * advantages
        clipped_ratio = torch.clamp(
            ratio,
            min=1.0 - self.config.epsilon_clip,
            max=1.0 + self.config.epsilon_clip,
        )
        clipped = clipped_ratio * advantages
        policy_loss = -torch.minimum(unclipped, clipped).mean()
        approx_kl_old = (old_logps - new_logp).mean()
        approx_kl_ref = (new_logp - ref_logps).mean()
        loss = policy_loss + self.config.lambda_kl * approx_kl_ref
        finite_tensors = [loss, ratio, new_logp, log_ratio, approx_kl_old, approx_kl_ref]
        if not all(bool(torch.isfinite(t).all().detach().cpu().item()) for t in finite_tensors):
            raise RuntimeError("nonfinite loss/logp/ratio/KL detected before optimizer step")

        grad_sq = 0.0
        nonzero_grad_tensors = 0
        for name, param in self._pipeline_named_parameters():
            if not param.requires_grad or param.grad is None:
                continue
            g = param.grad.detach()
            g_norm = float(g.float().norm().cpu().item())
            if g_norm > 0.0:
                nonzero_grad_tensors += 1
            grad_sq += g_norm * g_norm
            if not torch.isfinite(g).all():
                raise RuntimeError(f"nonfinite gradient in {name}")
        grad_norm = math.sqrt(grad_sq)
        if grad_norm <= 0.0:
            raise RuntimeError("adapter gradient norm is zero")
        if self.config.max_grad_norm is not None:
            torch.nn.utils.clip_grad_norm_(
                [p for _n, p in self._pipeline_named_parameters() if p.requires_grad],
                self.config.max_grad_norm,
            )
        self.optimizer.step()
        after_adapter_l2 = self.adapter_l2_norm() if self.config.track_adapter_norm_delta else None
        after_digest = self.adapter_digest()
        if before_digest == after_digest:
            raise RuntimeError("optimizer step did not change adapter digest")
        frozen_cmp = self.compare_frozen_snapshot()
        if not frozen_cmp["unchanged"]:
            raise RuntimeError(f"frozen parameter snapshot changed: {frozen_cmp['changed'][:3]}")

        post_update: dict[str, Any] | None = None
        if self.config.log_post_update_diagnostics:
            post_logps: list[torch.Tensor] = []
            for rollout in rollouts:
                post_logp, _info = self.rollout_logp(rollout, reference=False, grad=False)
                post_logps.append(post_logp.detach())
            post_new_logp = torch.stack(post_logps)
            post_log_ratio = post_new_logp - old_logps
            post_log_ratio_clamped = torch.clamp(
                post_log_ratio,
                min=-self.config.ratio_clip_log,
                max=self.config.ratio_clip_log,
            )
            post_ratio = torch.exp(post_log_ratio_clamped)
            post_kl_old = (old_logps - post_new_logp).mean()
            post_kl_ref = (post_new_logp - ref_logps).mean()
            finite_post = [post_ratio, post_new_logp, post_log_ratio, post_kl_old, post_kl_ref]
            if not all(bool(torch.isfinite(t).all().detach().cpu().item()) for t in finite_post):
                raise RuntimeError("nonfinite post-update logp/ratio/KL diagnostic")
            post_update = {
                "approx_kl_old": float(post_kl_old.detach().cpu().item()),
                "approx_kl_ref": float(post_kl_ref.detach().cpu().item()),
                "ratio": _stats(post_ratio.detach().cpu()),
                "log_ratio": _stats(post_log_ratio.detach().cpu()),
                "clip_fraction": float(
                    ((post_ratio < 1.0 - self.config.epsilon_clip) |
                     (post_ratio > 1.0 + self.config.epsilon_clip)).float().mean().detach().cpu().item()
                ),
            }

        self._step += 1
        metrics = {
            "backend_id": self.backend_id,
            "method_id": self.method_id,
            "reward_mode": self.reward_mode,
            "estimator_type": self.config.estimator_type,
            "exact_logprob": self.config.exact_logprob,
            "ratio_variance": self.config.ratio_variance,
            "sigma_floor": self.config.sigma_floor,
            "advantage_gain": advantage_gain,
            "loss": float(loss.detach().cpu().item()),
            "policy_loss": float(policy_loss.detach().cpu().item()),
            "approx_kl_old": float(approx_kl_old.detach().cpu().item()),
            "approx_kl_ref": float(approx_kl_ref.detach().cpu().item()),
            "ratio": _stats(ratio.detach().cpu()),
            "log_ratio": _stats(log_ratio.detach().cpu()),
            "clip_fraction": float(
                ((ratio < 1.0 - self.config.epsilon_clip) |
                 (ratio > 1.0 + self.config.epsilon_clip)).float().mean().detach().cpu().item()
            ),
            "grad_norm": grad_norm,
            "nonzero_grad_tensors": nonzero_grad_tensors,
            "adapter_updated": before_digest != after_digest,
            "frozen_parameters": frozen_cmp,
            "advantage_info": adv_info,
            "per_rollout": per_rollout_info,
        }
        if self.config.track_adapter_norm_delta:
            metrics["adapter_norm"] = {
                "before_l2": before_adapter_l2,
                "after_l2": after_adapter_l2,
                "delta_l2": (
                    None if before_adapter_l2 is None or after_adapter_l2 is None
                    else after_adapter_l2 - before_adapter_l2
                ),
            }
        if post_update is not None:
            metrics["post_update"] = post_update
        self._last_metrics = metrics
        self.write_ledger_event("optimizer_step", metrics=metrics)
        return metrics

    # -------------------------------------------------------------- checkpoint

    def _adapter_state_dict(self) -> dict[str, torch.Tensor]:
        return {
            name: param.detach().cpu()
            for name, param in self._pipeline_named_parameters()
            if _is_adapter_param(name)
        }

    def save_checkpoint(self, path: str | Path | None = None) -> Path:
        if self.optimizer is None:
            raise RuntimeError("cannot save checkpoint before ensure_lora()")
        out = Path(path) if path is not None else self.output_dir / "backend_checkpoint.pt"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "ace_step_lora_grpo_checkpoint_v1",
            "backend_id": self.backend_id,
            "method_id": self.method_id,
            "reward_mode": self.reward_mode,
            "step": self._step,
            "adapter_state": self._adapter_state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "backend_config": asdict(self.config),
            "parameter_summary": self.parameter_summary(),
            "last_metrics": self._last_metrics,
            "safety": {
                "formal_phase_c_launched": False,
                "held_out_launched": False,
                "phase_d_launched": False,
                "human_eval_launched": False,
            },
        }
        torch.save(payload, out)
        self.write_ledger_event("checkpoint_saved", metrics={"checkpoint_path": str(out)})
        return out

    def load_checkpoint(self, path: str | Path) -> dict[str, Any]:
        if self.optimizer is None:
            raise RuntimeError("ensure_lora() must be called before load_checkpoint()")
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("schema_version") != "ace_step_lora_grpo_checkpoint_v1":
            raise ValueError(f"unsupported checkpoint schema: {payload.get('schema_version')}")
        cfg = payload.get("backend_config", {})
        if tuple(cfg.get("target_modules", ())) != tuple(self.config.target_modules):
            raise ValueError("checkpoint target_modules do not match backend config")
        if int(cfg.get("lora_rank", -1)) != int(self.config.lora_rank):
            raise ValueError("checkpoint lora_rank does not match backend config")
        params = dict(self._pipeline_named_parameters())
        for name, value in payload["adapter_state"].items():
            if name not in params:
                raise KeyError(f"adapter parameter missing in model: {name}")
            params[name].data.copy_(value.to(params[name].device, dtype=params[name].dtype))
        self.optimizer.load_state_dict(payload["optimizer"])
        self._step = int(payload.get("step", 0))
        self._last_metrics = dict(payload.get("last_metrics") or {})
        self.write_ledger_event("checkpoint_resumed", metrics={"checkpoint_path": str(path)})
        return payload

    # ---------------------------------------------------------------- ledger

    def write_ledger_event(self, event: str, *, metrics: dict[str, Any] | None = None) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": _now_utc(),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "event": event,
            "backend_id": self.backend_id,
            "method_id": self.method_id,
            "reward_mode": self.reward_mode,
            "estimator_type": self.config.estimator_type,
            "exact_logprob": self.config.exact_logprob,
            "metrics": metrics or {},
            "safety": {
                "formal_phase_c_launched": False,
                "held_out_launched": False,
                "phase_d_launched": False,
                "human_eval_launched": False,
            },
        }
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")


__all__ = [
    "AceLoraGrpoBackend",
    "BackendConfig",
    "CapturedStep",
    "GrpoRollout",
    "compute_group_advantages",
]
