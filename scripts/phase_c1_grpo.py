"""Phase C0 backend validation and bounded Phase C1 first-wave runner.

This runner is dev-only. It does not launch held-out, Phase D, human
evaluation, or new ablations. Reward computation stays outside the shared
ACE-Step LoRA/GRPO backend; the backend consumes detached scalar rewards.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

import torch
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from mprm.training.ace_lora_grpo import (  # noqa: E402
    AceLoraGrpoBackend,
    BackendConfig,
    CapturedStep,
    GrpoRollout,
)

METHODS = ("r8a", "r8b", "m_fixedwin", "m_section")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML root is not an object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True, default=str) + "\n",
                    encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")


def _nvidia_snapshot() -> list[dict[str, Any]]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 5:
            continue
        rows.append(
            {
                "index": int(parts[0]),
                "name": parts[1],
                "memory_used_mb": int(parts[2]),
                "memory_total_mb": int(parts[3]),
                "utilization_gpu_percent": int(parts[4]),
            }
        )
    return rows


def _finite(name: str, value: float) -> float:
    v = float(value)
    if not math.isfinite(v):
        raise RuntimeError(f"{name} is not finite: {value!r}")
    return v


def _load_prompts_by_id(jsonl_path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            out[row["prompt_id"]] = row
    return out


def _prompt_from_row(row: dict[str, Any]):
    from mprm.data.prompts import Prompt

    return Prompt(
        prompt_id=row["prompt_id"],
        text=row.get("text", ""),
        lyrics=row.get("lyrics"),
        structure_hint=row.get("structure_hint"),
        duration_target=float(row.get("duration_target", 30.0)),
        metadata=row.get("metadata", {}),
        strata=row.get("strata", {}),
    )


def _load_formal_prompt_ids(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"formal prompt manifest must be an object: {path}")
    if data.get("source_split") != "configs/prompts/dev.jsonl":
        raise RuntimeError("formal prompt manifest source_split is not dev")
    if data.get("pi_approved") is not True:
        raise RuntimeError("formal prompt manifest is not PI-approved")
    prompt_ids = data.get("formal_prompt_ids")
    if not isinstance(prompt_ids, list) or not all(isinstance(x, str) for x in prompt_ids):
        raise RuntimeError("formal_prompt_ids must be a list of strings")
    if int(data.get("n_formal_prompts", -1)) != len(prompt_ids):
        raise RuntimeError("n_formal_prompts does not match formal_prompt_ids")
    return prompt_ids


def _validate_bundle(cfg: dict[str, Any]) -> None:
    if cfg.get("schema_version") != "phase_c1_firstwave_bundle_v1":
        raise RuntimeError("schema_version must be phase_c1_firstwave_bundle_v1")
    scope = cfg.get("scope", {})
    if scope.get("split") != "dev":
        raise RuntimeError("Phase C1 bundle must be dev split only")
    if scope.get("prompt_source") != "configs/prompts/dev.jsonl":
        raise RuntimeError("Phase C1 bundle prompt_source must be configs/prompts/dev.jsonl")
    for key in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
        if scope.get(key) is not False:
            raise RuntimeError(f"scope.{key} must be false")
    backend = cfg.get("backend", {})
    if backend.get("estimator_type") != "flow_matching_surrogate":
        raise RuntimeError("backend.estimator_type must remain flow_matching_surrogate")
    if backend.get("exact_logprob") is not False:
        raise RuntimeError("backend.exact_logprob must be false")
    if [float(x["target"]) for x in cfg["sigma_policy"]["downstream_checkpoints"]] != [0.7, 0.6]:
        raise RuntimeError("sigma_policy targets must remain [0.7, 0.6]")
    if set(cfg.get("methods", {})) != set(METHODS):
        raise RuntimeError(f"methods must be exactly {METHODS}")
    safety = cfg.get("safety", {})
    forbidden = safety.get("forbidden_launches", {})
    if forbidden.get("held_out") or forbidden.get("phase_d") or forbidden.get("human_eval"):
        raise RuntimeError("forbidden launch flags must remain false")


def _load_prompts(cfg: dict[str, Any], *, prompt_ids: list[str]) -> list[Any]:
    rows = _load_prompts_by_id(REPO_ROOT / cfg["scope"]["prompt_source"])
    missing = [pid for pid in prompt_ids if pid not in rows]
    if missing:
        raise RuntimeError(f"prompt IDs missing from dev split: {missing[:8]}")
    return [_prompt_from_row(rows[pid]) for pid in prompt_ids]


def _prompt_schedule(prompts: list[Any], *, seed: int, steps: int) -> list[Any]:
    rng = random.Random(seed)
    out: list[Any] = []
    while len(out) < steps:
        epoch = list(prompts)
        rng.shuffle(epoch)
        out.extend(epoch)
    return out[:steps]


def _sampler_extras(cfg: dict[str, Any]) -> dict[str, Any]:
    sampler = cfg["sampler"]
    return {
        "cfg_type": sampler["cfg_type"],
        "use_erg_tag": sampler["use_erg_tag"],
        "use_erg_lyric": sampler["use_erg_lyric"],
        "use_erg_diffusion": sampler["use_erg_diffusion"],
        "guidance_interval": sampler["guidance_interval"],
    }


def _backend_config(cfg: dict[str, Any]) -> BackendConfig:
    b = cfg["backend"]
    return BackendConfig(
        lora_rank=int(b["lora_rank"]),
        learning_rate=float(b["learning_rate"]),
        epsilon_clip=float(b["epsilon_clip"]),
        lambda_kl=float(b["lambda_kl"]),
        ratio_variance=float(b["ratio_variance"]),
        ratio_clip_log=float(b["ratio_clip_log"]),
        sigma_floor=float(b["sigma_floor"]),
        max_grad_norm=float(b["max_grad_norm"]) if b.get("max_grad_norm") is not None else None,
        estimator_type=str(b["estimator_type"]),
        exact_logprob=bool(b["exact_logprob"]),
        advantage_gain=float(b.get("advantage_gain", 1.0)),
        log_post_update_diagnostics=bool(b.get("log_post_update_diagnostics", False)),
        track_adapter_norm_delta=bool(b.get("track_adapter_norm_delta", False)),
    )


def _select_steps_from_result(
    res: Any,
    *,
    target_sigmas: list[float] | None,
    sigma_bindings: dict[float, dict[str, Any]] | None,
) -> tuple[list[CapturedStep], dict[str, Any]]:
    traj = res.trajectory or []
    sigmas = (res.extras or {}).get("trajectory_sigmas", [])
    cfg_flags = (res.extras or {}).get("trajectory_cfg_active", [])
    if not traj or not sigmas:
        raise RuntimeError("trajectory capture missing latents/sigmas")
    if target_sigmas:
        indices = [
            min(range(len(sigmas)), key=lambda k: abs(float(sigmas[k]) - float(target)))
            for target in target_sigmas
        ]
    else:
        indices = list(range(len(traj)))

    selected: list[CapturedStep] = []
    for k in indices:
        sigma = float(sigmas[k])
        cfg_active = bool(cfg_flags[k]) if k < len(cfg_flags) else True
        if sigma_bindings:
            expected = sigma_bindings[min(sigma_bindings, key=lambda x: abs(x - sigma))]
            if int(k) != int(expected["step_index"]):
                raise RuntimeError(f"sigma step drift: selected {k}, expected {expected['step_index']}")
            if abs(sigma - float(expected["scheduler_sigma_actual"])) > 1.0e-6:
                raise RuntimeError(
                    f"sigma drift: selected {sigma}, expected {expected['scheduler_sigma_actual']}"
                )
            if cfg_active != bool(expected["cfg_active"]):
                raise RuntimeError("cfg_active drift for selected sigma")
        selected.append(
            CapturedStep(
                latent=traj[k].to(torch.float32),
                sigma=sigma,
                step_index=int(k),
                cfg_active=cfg_active,
            )
        )
    return selected, {
        "selection_policy": "configured_sigmas" if target_sigmas else "all_captured_steps",
        "target_sigmas": target_sigmas,
        "selected_step_indices": [s.step_index for s in selected],
        "selected_sigmas": [s.sigma for s in selected],
        "selected_cfg_active": [s.cfg_active for s in selected],
    }


def _sample_rollout(
    *,
    model: Any,
    prompt: Any,
    seed: int,
    group_id: str,
    cfg_scale: float,
    infer_steps: int,
    extras: dict[str, Any],
    target_sigmas: list[float] | None,
    sigma_bindings: dict[float, dict[str, Any]] | None,
) -> tuple[GrpoRollout, dict[str, Any], Any]:
    res = model.sample(
        prompt,
        seed=seed,
        cfg_scale=cfg_scale,
        steps=infer_steps,
        return_trajectory=True,
        extras=extras,
    )
    selected, selection_info = _select_steps_from_result(
        res,
        target_sigmas=target_sigmas,
        sigma_bindings=sigma_bindings,
    )
    with torch.no_grad():
        z0 = model.encode(res.waveform)
    rollout = GrpoRollout(
        prompt_id=prompt.prompt_id,
        group_id=group_id,
        reward=0.0,
        prompt=prompt,
        steps=selected,
        z0=z0.detach().cpu().float(),
        metadata={
            "seed": seed,
            "duration_actual_s": float(res.waveform.shape[-1]) / float(res.sample_rate),
            "sample_rate": int(res.sample_rate),
            "selection": selection_info,
        },
    )
    return rollout, rollout.metadata, res


def _load_terminal_context(method: str, cfg: dict[str, Any]) -> dict[str, Any]:
    from mprm.common.config import load_config
    from mprm.rewards.perturbations import perturbation_set
    from scripts.launch_baseline import _build_reward_models

    tcfg = cfg["terminal_reward"][method]
    baseline_cfg = load_config(REPO_ROOT / tcfg["baseline_config"])
    if baseline_cfg.baseline.rung_id != cfg["methods"][method]["method_id"]:
        raise RuntimeError(f"{method} baseline rung_id mismatch")
    if float(baseline_cfg.reward.beta_robust) != float(cfg["terminal_reward"]["beta_robust"]):
        raise RuntimeError(f"{method} beta_robust mismatch")
    if dict(baseline_cfg.reward.lambda_probe) != dict(cfg["terminal_reward"]["lambda_probe"]):
        raise RuntimeError(f"{method} lambda_probe mismatch")
    extras = baseline_cfg.baseline.extras
    if list(extras.get("perturbations", [])) != list(cfg["terminal_reward"]["perturbations"]):
        raise RuntimeError(f"{method} perturbation set mismatch")
    if method == "r8a":
        if extras.get("epsilon_lyric") is not None or extras.get("use_curriculum") is not False:
            raise RuntimeError("R8a must keep lyric guard and curriculum off")
    if method == "r8b":
        if extras.get("epsilon_lyric") is None or extras.get("use_curriculum") is not True:
            raise RuntimeError("R8b must keep lyric guard and curriculum on/configured")

    reward_models = _build_reward_models(baseline_cfg.reward)
    return {
        "baseline_config": baseline_cfg,
        "reward_models": reward_models,
        "perturbations": perturbation_set(extras.get("perturbations", ["identity"])),
        "lambda_probe": dict(baseline_cfg.reward.lambda_probe),
        "beta_robust": float(baseline_cfg.reward.beta_robust),
        "clap": next((rm for rm in reward_models if getattr(rm, "axis", None) == "semantic_fit"), None),
        "whisper": next(
            (rm for rm in reward_models if getattr(rm, "axis", None) == "lyric_intelligibility"),
            None,
        ),
        "guarded": method == "r8b",
        "epsilon_lyric": extras.get("epsilon_lyric"),
        "lambda_cur": float(extras.get("lambda_init", 0.5)),
        "lyric_window": deque(maxlen=int(extras.get("lyric_window", 32))),
        "source": tcfg["baseline_config"],
    }


def _score_terminal_group(
    *,
    ctx: dict[str, Any],
    prompt: Any,
    samples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from mprm.rewards.probes import anti_hacking_probes
    from mprm.rewards.robust_lcb import robust_lcb

    if not samples:
        raise RuntimeError("cannot score empty terminal group")
    base_ref = samples[0]["res"].waveform
    reports: list[dict[str, Any]] = []
    for sample in samples:
        res = sample["res"]
        probe = anti_hacking_probes(
            res.waveform,
            res.sample_rate,
            prompt,
            base_reference=base_ref,
            clap=ctx["clap"],
        )
        lcb = robust_lcb(
            res.waveform,
            res.sample_rate,
            prompt,
            reward_models=ctx["reward_models"],
            perturbations=ctx["perturbations"],
            probe_scores=probe,
            lambda_probe=ctx["lambda_probe"],
            beta_robust=ctx["beta_robust"],
        )
        r_music = _finite("terminal robust_lcb", lcb.value)
        r_lyric = 1.0
        if ctx["guarded"] and prompt.lyrics and ctx["whisper"] is not None:
            r_lyric = _finite(
                "terminal lyric reward",
                ctx["whisper"].score(res.waveform, res.sample_rate, prompt).value,
            )
            ctx["lyric_window"].append(r_lyric)
        if ctx["guarded"]:
            eps = float(ctx["epsilon_lyric"] or 0.0)
            reward = r_music + float(ctx["lambda_cur"]) * (r_lyric + eps)
            reward_source = "terminal_robust_lcb_plus_existing_lyric_guard"
        else:
            eps = None
            reward = r_music
            reward_source = "terminal_robust_lcb"
        reward = _finite("terminal combined reward", reward)
        sample["rollout"].reward = reward
        reports.append(
            {
                "prompt_id": prompt.prompt_id,
                "seed": sample["meta"]["seed"],
                "reward_source": reward_source,
                "terminal_reward": reward,
                "r_music_robust_lcb": r_music,
                "r_lyric": r_lyric,
                "lambda_cur": float(ctx["lambda_cur"]),
                "epsilon_lyric": eps,
                "mean_cells": _finite("mean_cells", lcb.mean_cells),
                "std_cells": _finite("std_cells", lcb.std_cells),
                "probe_penalty": _finite("probe_penalty", lcb.probe_penalty),
                "probe_scores": {k: _finite(k, v) for k, v in probe.items()},
                "per_axis": {k: _finite(k, v) for k, v in lcb.per_axis.items()},
                **sample["meta"],
            }
        )
    return reports


def _load_process_context(method: str, cfg: dict[str, Any]) -> dict[str, Any]:
    from scripts.phase_c_m_fixedwin_prm import (
        _load_credit_unit_for_config,
        _load_reward_stack_for_config,
        _validate_config,
    )

    phase_c_path = REPO_ROOT / cfg["methods"][method]["phase_c_config"]
    phase_c_cfg = _load_yaml(phase_c_path)
    phase_c_cfg["_config_path_for_report"] = str(phase_c_path)
    fails = _validate_config(phase_c_cfg, require_pi=True)
    if fails:
        raise RuntimeError(f"{method} Phase C config validation failed: {fails}")
    expected_credit = cfg["methods"][method]["credit_unit"]
    actual_credit = phase_c_cfg["credit_unit"]["primary"]["name"]
    if actual_credit != expected_credit:
        raise RuntimeError(f"{method} credit unit mismatch: {actual_credit} != {expected_credit}")
    if phase_c_cfg["scope"]["prompt_source"] != cfg["scope"]["prompt_source"]:
        raise RuntimeError(f"{method} prompt source mismatch")
    if [float(x["target"]) for x in phase_c_cfg["sigma_policy"]["downstream_checkpoints"]] != [0.7, 0.6]:
        raise RuntimeError(f"{method} sigma policy mismatch")
    return {
        "cfg": phase_c_cfg,
        "reward_stack": _load_reward_stack_for_config(phase_c_cfg),
        "credit_unit": _load_credit_unit_for_config(phase_c_cfg),
        "target_sigmas": [
            float(x["target"]) for x in phase_c_cfg["sigma_policy"]["downstream_checkpoints"]
        ],
        "sigma_bindings": {
            float(x["target"]): x for x in phase_c_cfg["sigma_policy"]["downstream_checkpoints"]
        },
        "source": str(phase_c_path),
    }


def _score_process_sample(
    *,
    ctx: dict[str, Any],
    prompt: Any,
    sample: dict[str, Any],
    model: Any,
) -> dict[str, Any]:
    from scripts.ace_lora_grpo_backend_smoke import _process_reward_from_phase_c

    reward, report = _process_reward_from_phase_c(
        cfg=ctx["cfg"],
        prompt=prompt,
        res=sample["res"],
        model=model,
        reward_stack=ctx["reward_stack"],
        credit_unit=ctx["credit_unit"],
        target_sigmas=ctx["target_sigmas"],
    )
    reward = _finite("process reward", reward)
    sample["rollout"].reward = reward
    return {
        "prompt_id": prompt.prompt_id,
        "seed": sample["meta"]["seed"],
        "reward_source": "phase_c_h2_allowed_process_reward_stack",
        "process_reward": reward,
        **sample["meta"],
        **report,
    }


def _rollout_seed(base_seed: int, step: int, member: int) -> int:
    return int(base_seed) * 10_000_000 + int(step) * 10_000 + int(member)


def _check_update_metrics(metrics: dict[str, Any], *, max_kl_vs_ref: float) -> None:
    for key in ("loss", "policy_loss", "approx_kl_old", "approx_kl_ref", "grad_norm"):
        _finite(key, metrics[key])
    if not metrics.get("adapter_updated"):
        raise RuntimeError("adapter parameters did not update")
    if not metrics.get("frozen_parameters", {}).get("unchanged"):
        raise RuntimeError("frozen/base parameter checksum changed")
    if int(metrics.get("nonzero_grad_tensors", 0)) <= 0:
        raise RuntimeError("adapter gradients were zero")
    if abs(float(metrics["approx_kl_ref"])) > float(max_kl_vs_ref):
        raise RuntimeError(
            f"KL/divergence abort: approx_kl_ref={metrics['approx_kl_ref']} "
            f"> max_kl_vs_ref={max_kl_vs_ref}"
        )
    for stat_name in ("ratio", "log_ratio"):
        stats = metrics[stat_name]
        for key in ("mean", "std", "min", "max"):
            _finite(f"{stat_name}.{key}", stats[key])


def _run_updates(
    *,
    cfg: dict[str, Any],
    method: str,
    output_dir: Path,
    prompts: list[Any],
    steps: int,
    group_size: int,
    mode: str,
    dtype: str,
) -> dict[str, Any]:
    from mprm.common.seeding import seed_everything
    from mprm.inference.ace_step import AceStepModel

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for Phase C0/C1 GPU runs")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"{mode}_log.jsonl"
    if log_path.exists():
        raise RuntimeError(f"refusing to append to existing log: {log_path}")

    method_spec = cfg["methods"][method]
    reward_mode = method_spec["reward_mode"]
    method_id = method_spec["method_id"]
    sampler = cfg["sampler"]
    cfg_scale = float(sampler["guidance_scale"])
    infer_steps = int(
        sampler["terminal_infer_step"] if reward_mode == "terminal"
        else sampler["process_infer_step"]
    )
    sampler_extras = _sampler_extras(cfg)
    max_kl = float(cfg["firstwave"]["max_kl_vs_ref"])
    min_reward_std = float(cfg["firstwave"]["reward_collapse"]["min_group_reward_std"])
    seed_everything(int(cfg["backend"]["init_seed"]))

    t0 = time.time()
    before_gpu = _nvidia_snapshot()
    model = AceStepModel(dtype=dtype)
    backend = AceLoraGrpoBackend(
        model,
        _backend_config(cfg),
        output_dir=output_dir,
        method_id=method_id,
        reward_mode=reward_mode,
        ledger_path=output_dir / "backend_run_ledger.jsonl",
    )
    parameter_summary = backend.ensure_lora()
    backend.cfg_scale = cfg_scale
    initial_adapter_digest = backend.adapter_digest()

    if reward_mode == "terminal":
        reward_ctx = _load_terminal_context(method, cfg)
        target_sigmas = None
        sigma_bindings = None
    else:
        reward_ctx = _load_process_context(method, cfg)
        target_sigmas = reward_ctx["target_sigmas"]
        sigma_bindings = reward_ctx["sigma_bindings"]

    if mode == "smoke":
        if steps != 1:
            raise RuntimeError("smoke mode must run exactly one optimizer update")
        schedule = [None]
    else:
        schedule = _prompt_schedule(
            prompts,
            seed=int(cfg["firstwave"]["seeds"][0]),
            steps=steps,
        )
    checkpoint_path = None
    checkpoint_resume_ok = False
    completed = 0
    gpu_h_by_step: list[float] = []
    last_metrics: dict[str, Any] | None = None

    for step, scheduled_prompt in enumerate(schedule):
        step_start = time.time()
        step_prompts = prompts if mode == "smoke" else [scheduled_prompt]
        all_rollouts: list[GrpoRollout] = []
        all_reward_reports: list[dict[str, Any]] = []
        prompt_ids_for_step: list[str] = []
        reward_stds: list[float] = []

        for prompt in step_prompts:
            if prompt is None:
                raise RuntimeError("internal prompt schedule error")
            prompt_ids_for_step.append(prompt.prompt_id)
            group_id = f"{method_id}:step{step}:{prompt.prompt_id}"
            samples: list[dict[str, Any]] = []
            rollouts: list[GrpoRollout] = []
            for member in range(group_size):
                seed = _rollout_seed(int(cfg["firstwave"]["seeds"][0]), step, member)
                # Keep smoke seeds distinct across prompts while preserving the
                # one-update, group-normalized GRPO shape.
                if mode == "smoke":
                    seed += 100 * len(prompt_ids_for_step)
                rollout, meta, res = _sample_rollout(
                    model=model,
                    prompt=prompt,
                    seed=seed,
                    group_id=group_id,
                    cfg_scale=cfg_scale,
                    infer_steps=infer_steps,
                    extras=sampler_extras,
                    target_sigmas=target_sigmas,
                    sigma_bindings=sigma_bindings,
                )
                sample = {"rollout": rollout, "meta": meta, "res": res}
                samples.append(sample)
                rollouts.append(rollout)
            if reward_mode == "terminal":
                reward_reports = _score_terminal_group(
                    ctx=reward_ctx,
                    prompt=prompt,
                    samples=samples,
                )
            else:
                reward_reports = [
                    _score_process_sample(ctx=reward_ctx, prompt=prompt, sample=s, model=model)
                    for s in samples
                ]

            rewards = torch.tensor([float(r.reward) for r in rollouts], dtype=torch.float32)
            if not bool(torch.isfinite(rewards).all().item()):
                raise RuntimeError("reward tensor contains NaN/Inf")
            reward_stds.append(float(rewards.std(unbiased=False).item()))
            all_rollouts.extend(rollouts)
            all_reward_reports.extend(reward_reports)

        rollouts = all_rollouts
        reward_reports = all_reward_reports
        if not rollouts:
            raise RuntimeError("no rollouts generated for update")
        reward_std = min(reward_stds) if reward_stds else 0.0

        old_ref = backend.cache_old_and_ref_logps(rollouts)
        update_metrics = backend.update(rollouts)
        _check_update_metrics(update_metrics, max_kl_vs_ref=max_kl)
        if mode == "train" and reward_std <= min_reward_std:
            raise RuntimeError(f"reward collapse: group reward std {reward_std} <= {min_reward_std}")
        if mode == "train" and update_metrics["advantage_info"]["n_zero_variance_groups"] > 0:
            raise RuntimeError("reward collapse: zero-variance GRPO group")

        completed += 1
        step_elapsed = time.time() - step_start
        gpu_h_by_step.append(step_elapsed / 3600.0)
        row = {
            "event": "optimizer_step",
            "mode": mode,
            "method": method,
            "method_id": method_id,
            "step": step,
            "prompt_ids": prompt_ids_for_step,
            "group_size": group_size,
            "infer_steps": infer_steps,
            "elapsed_seconds": step_elapsed,
            "gpu_hours_consumed": step_elapsed / 3600.0,
            "reward_std": reward_std,
            "reward_reports": reward_reports,
            "old_ref_logps": old_ref,
            "update_metrics": update_metrics,
            "safety": {
                "formal_phase_c1_training": mode == "train",
                "held_out_launched": False,
                "phase_d_launched": False,
                "human_eval_launched": False,
            },
        }
        _append_jsonl(log_path, row)
        last_metrics = update_metrics

        should_checkpoint = mode == "smoke" or (
            mode == "train"
            and (completed % int(cfg["firstwave"]["checkpoint_every_steps"]) == 0
                 or completed == steps)
        )
        if should_checkpoint:
            checkpoint_path = backend.save_checkpoint(
                output_dir / f"checkpoint_step_{completed:06d}.pt"
            )
            payload = backend.load_checkpoint(checkpoint_path)
            checkpoint_resume_ok = (
                payload.get("schema_version") == "ace_step_lora_grpo_checkpoint_v1"
            )
            if not checkpoint_resume_ok:
                raise RuntimeError("checkpoint resume check failed")
            _append_jsonl(
                log_path,
                {
                    "event": "checkpoint_saved_and_resumed",
                    "step": step,
                    "checkpoint_path": str(checkpoint_path),
                    "checkpoint_resume_ok": checkpoint_resume_ok,
                },
            )

    torch.cuda.synchronize()
    elapsed = time.time() - t0
    max_mem_mb = int(torch.cuda.max_memory_allocated(torch.device("cuda")) / (1024 * 1024))
    result = {
        "schema_version": "phase_c1_grpo_result_v1",
        "status": "PASS",
        "mode": mode,
        "method": method,
        "method_id": method_id,
        "display_name": method_spec["display_name"],
        "reward_mode": reward_mode,
        "output_dir": str(output_dir),
        "elapsed_seconds": elapsed,
        "gpu_hours_consumed": elapsed / 3600.0,
        "steps_completed": completed,
        "group_size": group_size,
        "infer_steps": infer_steps,
        "prompts": [p.prompt_id for p in prompts],
        "sampler_extras": sampler_extras,
        "parameter_summary": parameter_summary,
        "initial_adapter_digest": initial_adapter_digest,
        "final_adapter_digest": backend.adapter_digest(),
        "adapter_updated": (
            last_metrics.get("adapter_updated") if last_metrics is not None else False
        ),
        "base_parameters_frozen": parameter_summary["base_parameters_frozen"],
        "last_update_metrics": last_metrics,
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        "checkpoint_resume_ok": checkpoint_resume_ok,
        "log_path": str(log_path),
        "log_written": log_path.exists() and log_path.stat().st_size > 0,
        "cuda_max_memory_allocated_mb": max_mem_mb,
        "nvidia_smi_before": before_gpu,
        "nvidia_smi_after": _nvidia_snapshot(),
        "gpu_hours_by_step": gpu_h_by_step,
        "reward_definitions_changed": False,
        "sigma_policy_changed": False,
        "prompt_splits_changed": False,
        "credit_unit_definitions_changed": False,
        "gate_v1_touched_by_runner": False,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
        "no_formal_result_claim": mode == "smoke",
    }
    _write_json(output_dir / f"{mode}_results.json", result)
    return result


def run_smoke(args: argparse.Namespace, cfg: dict[str, Any], method: str) -> dict[str, Any]:
    prompt_ids = args.prompt_ids or list(cfg["smoke"]["prompt_ids"])
    if len(prompt_ids) < 1 or len(prompt_ids) > int(cfg["smoke"]["max_prompts_allowed"]):
        raise RuntimeError("smoke prompt count must be between 1 and max_prompts_allowed")
    prompts = _load_prompts(cfg, prompt_ids=prompt_ids)
    out_dir = Path(args.output_root) / method
    return _run_updates(
        cfg=cfg,
        method=method,
        output_dir=out_dir,
        prompts=prompts,
        steps=int(cfg["smoke"]["steps"]),
        group_size=int(cfg["smoke"]["group_size"]),
        mode="smoke",
        dtype=args.dtype,
    )


def run_train(args: argparse.Namespace, cfg: dict[str, Any], method: str) -> dict[str, Any]:
    if not args.pi_approved_launch:
        raise RuntimeError("--pi-approved-launch is required for train mode")
    formal_ids = _load_formal_prompt_ids(REPO_ROOT / cfg["scope"]["formal_prompt_ids_json"])
    if len(formal_ids) != int(cfg["scope"]["n_prompts"]):
        raise RuntimeError("formal prompt count mismatch")
    prompts = _load_prompts(cfg, prompt_ids=formal_ids)
    out_dir = Path(args.output_root) / method
    return _run_updates(
        cfg=cfg,
        method=method,
        output_dir=out_dir,
        prompts=prompts,
        steps=int(cfg["firstwave"]["rl_steps"]),
        group_size=int(cfg["firstwave"]["group_size"]),
        mode="train",
        dtype=args.dtype,
    )


def run_eta(args: argparse.Namespace, cfg: dict[str, Any]) -> dict[str, Any]:
    smoke_root = Path(args.smoke_root or args.output_root)
    formal_steps = int(cfg["firstwave"]["rl_steps"])
    formal_group = int(cfg["firstwave"]["group_size"])
    rows: dict[str, Any] = {}
    total = 0.0
    for method in METHODS:
        path = smoke_root / method / "smoke_results.json"
        if not path.exists():
            raise RuntimeError(f"missing smoke result for ETA: {path}")
        smoke = json.loads(path.read_text(encoding="utf-8"))
        if smoke.get("status") != "PASS":
            raise RuntimeError(f"smoke did not pass for {method}: {path}")
        smoke_steps = int(smoke["steps_completed"])
        smoke_group = int(smoke["group_size"])
        smoke_prompt_count = max(1, len(smoke.get("prompts", [])))
        smoke_rollouts_per_update = max(1, smoke_group * smoke_prompt_count)
        step_gpu_hours = smoke.get("gpu_hours_by_step") or [smoke["gpu_hours_consumed"]]
        smoke_update_gpu_h = float(sum(float(x) for x in step_gpu_hours)) / max(1, len(step_gpu_hours))
        projected = (
            smoke_update_gpu_h
            * (formal_steps / max(1, smoke_steps))
            * (formal_group / smoke_rollouts_per_update)
        )
        total += projected
        rows[method] = {
            "smoke_gpu_h": float(smoke["gpu_hours_consumed"]),
            "smoke_update_gpu_h": smoke_update_gpu_h,
            "smoke_steps": smoke_steps,
            "smoke_group_size": smoke_group,
            "smoke_prompt_count": smoke_prompt_count,
            "smoke_rollouts_per_update": smoke_rollouts_per_update,
            "formal_steps": formal_steps,
            "formal_group_size": formal_group,
            "projected_gpu_h": projected,
            "single_gpu_eta_minutes": projected * 60.0,
            "single_gpu_eta_gt_30_min": projected > 0.5,
        }
    cap = float(cfg["safety"]["hard_cap_gpu_h"])
    report = {
        "schema_version": "phase_c1_eta_v1",
        "status": "PASS" if total <= cap else "STOP_GPU_H_CAP",
        "smoke_root": str(smoke_root),
        "estimate_policy": "linear_from_measured_smoke_update_time_excluding_one_time_startup",
        "parallelism_policy": cfg["launch_policy"]["parallelism_policy"],
        "methods": rows,
        "projected_total_gpu_h": total,
        "hard_cap_gpu_h": cap,
        "within_hard_cap": total <= cap,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
    }
    _write_json(Path(args.output_root) / "phase_c1_eta.json", report)
    if total > cap:
        raise RuntimeError(f"projected total GPU-h {total:.3f} exceeds cap {cap:.3f}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/runs/phase_c1_firstwave.yaml")
    parser.add_argument("--mode", choices=["preflight", "smoke", "eta", "train"], required=True)
    parser.add_argument("--method", choices=[*METHODS, "all"], default="all")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--smoke-root", default=None)
    parser.add_argument("--prompt-ids", nargs="+", default=None)
    parser.add_argument("--pi-approved-launch", action="store_true")
    parser.add_argument("--dtype", default="bfloat16")
    args = parser.parse_args()

    cfg = _load_yaml(REPO_ROOT / args.config)
    _validate_bundle(cfg)
    if args.output_root is None:
        args.output_root = (
            cfg["smoke"]["output_root"] if args.mode == "smoke"
            else cfg["firstwave"]["output_root"]
        )

    if args.mode == "preflight":
        print("[phase-c1] PREFLIGHT PASS")
        return 0

    if args.mode == "eta":
        report = run_eta(args, cfg)
        print(json.dumps({"status": report["status"], "gpu_h": report["projected_total_gpu_h"]}))
        return 0

    methods = list(METHODS) if args.method == "all" else [args.method]
    results: dict[str, Any] = {}
    for method in methods:
        print(f"[phase-c1] {args.mode} {method}", flush=True)
        if args.mode == "smoke":
            results[method] = run_smoke(args, cfg, method)
        elif args.mode == "train":
            results[method] = run_train(args, cfg, method)
        else:
            raise AssertionError(args.mode)
    if len(results) > 1:
        _write_json(Path(args.output_root) / f"all_{args.mode}_results.json", results)
    print(json.dumps({"mode": args.mode, "methods": list(results), "status": "PASS"}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[phase-c1] FAIL: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise
