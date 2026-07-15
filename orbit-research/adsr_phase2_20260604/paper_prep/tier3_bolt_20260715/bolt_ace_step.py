#!/usr/bin/env python3
"""Measured-NFE ACE-Step v1 trajectory capture and continuation for BOLT."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import torch


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
HERE = Path(__file__).resolve().parent
ACE_SOURCE = Path(os.environ.get("BOLT_ACE_STEP_SOURCE", "/XYFS01/HOME/paratera_xy/pxy1289/source/ACE-Step"))
for path in (ROOT, ROOT / "src", ROOT / "scripts", HERE, ACE_SOURCE):
    sys.path.insert(0, str(path))

from bolt_state import (  # noqa: E402
    CheckpointState,
    assert_condition_changed,
    canonical_condition_hash,
    fork_latent,
    tensor_sha256,
)
from mprm.data.prompts import Prompt  # noqa: E402
from mprm.inference.ace_step import AceStepModel  # noqa: E402


INFER_STEPS = 30
GUIDANCE_INTERVAL = 0.5
CFG_SCALE_BASE = 5.0
OMEGA_SCALE = 10.0
CHECKPOINT_STEPS = (6, 12, 18)
POSITIVE_INSTRUMENTAL_TEXT = (
    "instrumental arrangement led by synthesizer, drums, bass, and melodic instruments"
)
VOCAL_STRUCTURE_HINT = "[verse]\n[chorus]\n[verse]\n[chorus]"
FORBIDDEN_INSTRUMENTAL_SWITCH_TERMS = re.compile(
    r"\b(vocal|vocals|voice|voices|sing|singing|singer|lyric|lyrics|speech|choir)\b",
    flags=re.IGNORECASE,
)


def sha256_path_manifest(root: Path) -> str:
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root)}")
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def prompt_from_dict(row: dict[str, Any]) -> Prompt:
    return Prompt(
        prompt_id=str(row["prompt_id"]),
        text=str(row.get("text") or ""),
        lyrics=row.get("lyrics"),
        structure_hint=row.get("structure_hint"),
        duration_target=float(row["duration_target"]),
        metadata=dict(row.get("metadata") or {}),
        strata=dict(row.get("strata") or {}),
    )


def _tempo_description(prompt: Prompt) -> str:
    tempo = str(prompt.strata.get("tempo_bin") or "unspecified tempo").replace("_", " ")
    return tempo


def direction_condition(prompt: Prompt, requested_vocal: int) -> tuple[Prompt, dict[str, float], float]:
    if requested_vocal:
        active = prompt
        if not (active.structure_hint or "").strip():
            active = dataclasses.replace(active, structure_hint=VOCAL_STRUCTURE_HINT)
        return active, {"guidance_scale_text": 5.0, "guidance_scale_lyric": 7.5}, 5.0
    genre = str(prompt.strata.get("genre") or "music")
    structure = str(prompt.strata.get("structural_complexity") or "clear musical form").replace("_", " ")
    text = f"{genre} instrumental music, {_tempo_description(prompt)}, {structure}, {POSITIVE_INSTRUMENTAL_TEXT}"
    if FORBIDDEN_INSTRUMENTAL_SWITCH_TERMS.search(text):
        raise RuntimeError(f"instrumental switch text contains forbidden lexeme: {text}")
    active = dataclasses.replace(prompt, text=text, lyrics=None)
    return active, {}, 7.5


def _hash_cache(cache: dict[str, Any]) -> dict[str, str]:
    return {
        key: tensor_sha256(value)
        for key, value in cache.items()
        if torch.is_tensor(value)
    }


@dataclasses.dataclass
class ConditionBundle:
    prompt: Prompt
    requested_vocal: int
    switched: bool
    cfg_scale: float
    guidance_scale_text: float
    guidance_scale_lyric: float
    cache: dict[str, Any]
    only_text_cache: dict[str, Any] | None
    payload: dict[str, Any]
    condition_hash: str


@dataclasses.dataclass
class RunResult:
    latent: torch.Tensor
    waveform: torch.Tensor
    sample_rate: int
    nfe: int
    scheduler_steps: int
    cumulative_nfe_by_step: dict[int, int]
    wall_seconds: float
    cuda_seconds: float | None
    condition_hash: str
    checkpoints: dict[int, CheckpointState]
    evpd_probe_tweedie: torch.Tensor | None
    evpd_probe_sigma: float | None
    evpd_probe_step: int | None
    evpd_probe_nfe: int | None


class AceStepBOLTRunner:
    def __init__(self, identity: dict[str, str], *, device: str = "cuda", dtype: str = "bfloat16"):
        required = ("model_hash", "checkpoint_hash", "scheduler_hash")
        missing = [key for key in required if not identity.get(key)]
        if missing:
            raise ValueError(f"runtime identity missing {missing}")
        self.identity = dict(identity)
        self.model = AceStepModel(device=device, dtype=dtype)
        self.model._ensure_loaded()
        self.pipeline = self.model._pipeline
        self.device = self.pipeline.device
        self.dtype = self.pipeline.dtype
        self._total_transformer_calls = 0

    @property
    def total_transformer_calls(self) -> int:
        return self._total_transformer_calls

    def build_condition(self, prompt: Prompt, requested_vocal: int, *, switched: bool) -> ConditionBundle:
        if switched:
            active, guidance, cfg_scale = direction_condition(prompt, requested_vocal)
        else:
            active, guidance, cfg_scale = prompt, {}, CFG_SCALE_BASE
        cache = self.model._build_condition_cache(active)
        guidance_text = float(guidance.get("guidance_scale_text", 0.0))
        guidance_lyric = float(guidance.get("guidance_scale_lyric", 0.0))
        only_text_cache = None
        if guidance_text > 1.0 and guidance_lyric > 1.0:
            no_lyric = dataclasses.replace(active, lyrics=None)
            only_text_cache = self.model._build_condition_cache(no_lyric)
        payload = {
            "prompt_id": active.prompt_id,
            "text": active.text,
            "lyrics": active.lyrics or "",
            "structure_hint": active.structure_hint or "",
            "requested_vocal": int(requested_vocal),
            "switched": bool(switched),
            "cfg_scale": cfg_scale,
            "guidance_scale_text": guidance_text,
            "guidance_scale_lyric": guidance_lyric,
            "cfg_type": "cfg",
            "guidance_interval": GUIDANCE_INTERVAL,
            "cache_tensor_sha256": _hash_cache(cache),
            "only_text_cache_tensor_sha256": _hash_cache(only_text_cache or {}),
        }
        condition_hash = canonical_condition_hash(payload)
        return ConditionBundle(
            prompt=active,
            requested_vocal=int(requested_vocal),
            switched=bool(switched),
            cfg_scale=float(cfg_scale),
            guidance_scale_text=guidance_text,
            guidance_scale_lyric=guidance_lyric,
            cache=cache,
            only_text_cache=only_text_cache,
            payload=payload,
            condition_hash=condition_hash,
        )

    def assert_switch(self, base: ConditionBundle, switched: ConditionBundle) -> None:
        if base.prompt.prompt_id != switched.prompt.prompt_id:
            raise RuntimeError("condition switch changed prompt identity")
        assert_condition_changed(base.condition_hash, switched.condition_hash)
        if switched.requested_vocal == 0 and FORBIDDEN_INSTRUMENTAL_SWITCH_TERMS.search(switched.prompt.text):
            raise RuntimeError("instrumental switch contains forbidden vocal/lyric lexeme")

    def _new_scheduler(self):
        from acestep.schedulers.scheduling_flow_match_euler_discrete import FlowMatchEulerDiscreteScheduler
        from diffusers.pipelines.stable_diffusion_3.pipeline_stable_diffusion_3 import retrieve_timesteps

        scheduler = FlowMatchEulerDiscreteScheduler(num_train_timesteps=1000, shift=3.0)
        timesteps, count = retrieve_timesteps(
            scheduler, num_inference_steps=INFER_STEPS, device=self.device, timesteps=None
        )
        if int(count) != INFER_STEPS:
            raise RuntimeError(f"scheduler returned {count} steps, expected {INFER_STEPS}")
        return scheduler, timesteps

    def _decode(self, *, latent: torch.Tensor, timestep: torch.Tensor, hidden: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        self._total_transformer_calls += 1
        return self.pipeline.ace_step_transformer.decode(
            hidden_states=latent,
            attention_mask=torch.ones(
                latent.shape[0], latent.shape[-1], device=self.device, dtype=self.dtype
            ),
            encoder_hidden_states=hidden,
            encoder_hidden_mask=mask,
            output_length=latent.shape[-1],
            timestep=timestep,
        ).sample

    def _velocity(self, latent: torch.Tensor, t: torch.Tensor, step_index: int, condition: ConditionBundle) -> torch.Tensor:
        from acestep.apg_guidance import cfg_double_condition_forward, cfg_forward

        active = int(INFER_STEPS * ((1 - GUIDANCE_INTERVAL) / 2)) <= step_index < int(
            INFER_STEPS * (GUIDANCE_INTERVAL / 2 + 0.5)
        )
        expanded_t = t.expand(latent.shape[0])
        cache = condition.cache
        cond = self._decode(
            latent=latent,
            timestep=expanded_t,
            hidden=cache["encoder_hidden_cond"],
            mask=cache["encoder_mask_cond"],
        )
        if not active or condition.cfg_scale in (0.0, 1.0):
            return cond
        uncond = self._decode(
            latent=latent,
            timestep=expanded_t,
            hidden=cache["encoder_hidden_null"],
            mask=cache["encoder_mask_null"],
        )
        if condition.only_text_cache is not None:
            only_text = self._decode(
                latent=latent,
                timestep=expanded_t,
                hidden=condition.only_text_cache["encoder_hidden_cond"],
                mask=condition.only_text_cache["encoder_mask_cond"],
            )
            return cfg_double_condition_forward(
                cond_output=cond,
                uncond_output=uncond,
                only_text_cond_output=only_text,
                guidance_scale_text=condition.guidance_scale_text,
                guidance_scale_lyric=condition.guidance_scale_lyric,
            )
        return cfg_forward(cond_output=cond, uncond_output=uncond, cfg_strength=condition.cfg_scale)

    def _initial_latent(self, duration: float, generator: torch.Generator) -> torch.Tensor:
        from diffusers.utils.torch_utils import randn_tensor

        frame_length = int(float(duration) * 44100 / 512 / 8)
        return randn_tensor(
            shape=(1, 8, 16, frame_length),
            generator=[generator],
            device=self.device,
            dtype=self.dtype,
        )

    def _run(
        self,
        *,
        prompt: Prompt,
        root_seed: int,
        latent: torch.Tensor,
        generator: torch.Generator,
        start_step: int,
        prefix_nfe: int,
        condition: ConditionBundle,
        capture_steps: Iterable[int],
    ) -> RunResult:
        scheduler, timesteps = self._new_scheduler()
        if start_step:
            scheduler._step_index = int(start_step)
        capture = set(int(value) for value in capture_steps)
        states: dict[int, CheckpointState] = {}
        evpd_probe_tweedie = None
        evpd_probe_sigma = None
        evpd_probe_step = None
        evpd_probe_nfe = None
        before_calls = self._total_transformer_calls
        cumulative: dict[int, int] = {}
        started = time.perf_counter()
        cuda_start = cuda_end = None
        if torch.cuda.is_available():
            cuda_start = torch.cuda.Event(enable_timing=True)
            cuda_end = torch.cuda.Event(enable_timing=True)
            cuda_start.record()
        last_output = torch.zeros_like(latent)
        with torch.no_grad():
            for index in range(start_step, INFER_STEPS):
                t = timesteps[index]
                last_output = self._velocity(latent, t, index, condition)
                current_sigma = float(scheduler.sigmas[index].item())
                if evpd_probe_tweedie is None and current_sigma <= 0.8:
                    # This is the exact frozen W2 probe construction: x0 = x_sigma - sigma*v.
                    evpd_probe_tweedie = (
                        latent.to(torch.float32) - current_sigma * last_output.to(torch.float32)
                    ).detach().cpu()
                    evpd_probe_sigma = current_sigma
                    evpd_probe_step = index + 1
                    evpd_probe_nfe = prefix_nfe + self._total_transformer_calls - before_calls
                latent = scheduler.step(
                    model_output=last_output,
                    timestep=t,
                    sample=latent,
                    return_dict=False,
                    omega=OMEGA_SCALE,
                    generator=generator,
                )[0]
                completed = index + 1
                local_nfe = self._total_transformer_calls - before_calls
                cumulative[completed] = prefix_nfe + local_nfe
                if completed in capture:
                    next_timestep = float(timesteps[completed].item())
                    states[completed] = CheckpointState(
                        state_id=f"{prompt.prompt_id}__seed{root_seed}__step{completed:02d}",
                        prompt_id=prompt.prompt_id,
                        root_seed=int(root_seed),
                        completed_steps=completed,
                        scheduler_index=completed,
                        timestep=next_timestep,
                        sigma=float(scheduler.sigmas[completed].item()),
                        next_sigma=float(scheduler.sigmas[completed + 1].item()),
                        latent=latent.detach().clone().cpu(),
                        model_output=last_output.detach().clone().cpu(),
                        condition_hash=condition.condition_hash,
                        model_hash=self.identity["model_hash"],
                        checkpoint_hash=self.identity["checkpoint_hash"],
                        scheduler_hash=self.identity["scheduler_hash"],
                        cpu_rng_state=torch.get_rng_state(),
                        cuda_rng_state=(torch.cuda.get_rng_state(self.device) if torch.cuda.is_available() else None),
                        generator_rng_state=generator.get_state(),
                        nfe_count=prefix_nfe + local_nfe,
                        scheduler_step_count=completed,
                        extras={
                            "condition_payload": condition.payload,
                            "next_timestep_index": completed,
                            "inference_steps": INFER_STEPS,
                            "guidance_interval": GUIDANCE_INTERVAL,
                            "omega_scale": OMEGA_SCALE,
                        },
                    )
            waveform = self.model.decode(latent)
        if cuda_end is not None and cuda_start is not None:
            cuda_end.record()
            torch.cuda.synchronize(self.device)
            cuda_seconds = float(cuda_start.elapsed_time(cuda_end) / 1000.0)
        else:
            cuda_seconds = None
        return RunResult(
            latent=latent.detach().clone(),
            waveform=waveform,
            sample_rate=self.model.sample_rate,
            nfe=self._total_transformer_calls - before_calls,
            scheduler_steps=INFER_STEPS - start_step,
            cumulative_nfe_by_step=cumulative,
            wall_seconds=time.perf_counter() - started,
            cuda_seconds=cuda_seconds,
            condition_hash=condition.condition_hash,
            checkpoints=states,
            evpd_probe_tweedie=evpd_probe_tweedie,
            evpd_probe_sigma=evpd_probe_sigma,
            evpd_probe_step=evpd_probe_step,
            evpd_probe_nfe=evpd_probe_nfe,
        )

    def run_full(
        self,
        prompt: Prompt,
        *,
        seed: int,
        requested_vocal: int,
        switched: bool = False,
        capture_steps: Iterable[int] = (),
    ) -> RunResult:
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))
        generator = torch.Generator(device=self.device).manual_seed(int(seed))
        condition = self.build_condition(prompt, requested_vocal, switched=switched)
        latent = self._initial_latent(prompt.duration_target, generator)
        return self._run(
            prompt=prompt,
            root_seed=seed,
            latent=latent,
            generator=generator,
            start_step=0,
            prefix_nfe=0,
            condition=condition,
            capture_steps=capture_steps,
        )

    def run_from_state(
        self,
        state: CheckpointState,
        prompt: Prompt,
        *,
        requested_vocal: int,
        switched: bool = False,
        fork_eta: float | None = None,
        fork_seed: int | None = None,
    ) -> RunResult:
        if state.prompt_id != prompt.prompt_id:
            raise RuntimeError("checkpoint prompt identity mismatch")
        for key, expected in (
            ("model_hash", self.identity["model_hash"]),
            ("checkpoint_hash", self.identity["checkpoint_hash"]),
            ("scheduler_hash", self.identity["scheduler_hash"]),
        ):
            if getattr(state, key) != expected:
                raise RuntimeError(f"checkpoint {key} mismatch")
        condition = self.build_condition(prompt, requested_vocal, switched=switched)
        if switched:
            assert_condition_changed(state.condition_hash, condition.condition_hash)
        elif state.condition_hash != condition.condition_hash:
            raise RuntimeError("same-condition resume cache hash mismatch")
        torch.set_rng_state(state.cpu_rng_state)
        if state.cuda_rng_state is not None and torch.cuda.is_available():
            torch.cuda.set_rng_state(state.cuda_rng_state, self.device)
        generator = torch.Generator(device=self.device)
        generator.set_state(state.generator_rng_state)
        latent = state.latent.to(device=self.device, dtype=self.dtype)
        if fork_eta is not None:
            if fork_seed is None:
                raise ValueError("fork seed is required with fork eta")
            latent = fork_latent(
                latent, sigma=state.sigma, eta=float(fork_eta), branch_seed=int(fork_seed)
            )
        return self._run(
            prompt=prompt,
            root_seed=state.root_seed,
            latent=latent,
            generator=generator,
            start_step=state.completed_steps,
            prefix_nfe=state.nfe_count,
            condition=condition,
            capture_steps=(),
        )


def waveform_nrmse(reference: torch.Tensor, candidate: torch.Tensor) -> float:
    if reference.shape != candidate.shape:
        return float("inf")
    ref = reference.to(torch.float64)
    cand = candidate.to(torch.float64)
    numerator = torch.sqrt(torch.mean((ref - cand) ** 2))
    denominator = torch.sqrt(torch.mean(ref**2)).clamp_min(1e-12)
    return float((numerator / denominator).item())


def waveform_validity(waveform: torch.Tensor, sample_rate: int) -> dict[str, Any]:
    if waveform.ndim != 2:
        return {"valid": False, "error": f"expected 2-D waveform, got {tuple(waveform.shape)}"}
    duration = waveform.shape[-1] / float(sample_rate)
    rms = float(waveform.to(torch.float32).square().mean().sqrt().item())
    finite = bool(torch.isfinite(waveform).all().item())
    near_silent = rms < 1e-4
    return {
        "valid": bool(finite and duration > 1.0 and not near_silent),
        "finite": finite,
        "duration_seconds": duration,
        "sample_rate": int(sample_rate),
        "rms": rms,
        "near_silent": near_silent,
    }
