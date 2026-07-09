"""Isolated two-GPU rollout-parallel smoke for Phase C1 methods.

This is a smoke-only controller/worker harness. It does not modify the Phase C1
runner or configs. The controller owns the single logical LoRA adapter and
optimizer on logical cuda:0; the worker on logical cuda:1 reloads the
controller's adapter checkpoint before rollout generation and never performs an
optimizer step.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import torch
import torch.multiprocessing as mp

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from mprm.training.ace_lora_grpo import (  # noqa: E402
    AceLoraGrpoBackend,
    GrpoRollout,
)
from scripts.phase_c1_grpo import (  # noqa: E402
    _append_jsonl,
    _backend_config,
    _check_update_metrics,
    _finite,
    _load_prompts,
    _load_process_context,
    _load_terminal_context,
    _load_yaml,
    _nvidia_snapshot,
    _rollout_seed,
    _sample_rollout,
    _sampler_extras,
    _score_terminal_group,
    _score_process_sample,
    _validate_bundle,
    _write_json,
)


METHOD = "r8a"
EXPECTED_PHYSICAL_GPUS = ("5", "6")
ARCHITECTURE_ID = "controller_worker_rollout_parallel_shared_adapter_v1"


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _visible_devices() -> list[str]:
    raw = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _assert_visible_physical_gpus(expected: tuple[str, ...] | None = None) -> None:
    expected = expected or EXPECTED_PHYSICAL_GPUS
    visible = _visible_devices()
    if tuple(visible) != expected:
        raise RuntimeError(
            "This smoke must be launched with exactly "
            f"CUDA_VISIBLE_DEVICES={','.join(expected)}; got {os.environ.get('CUDA_VISIBLE_DEVICES')!r}"
        )
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    if torch.cuda.device_count() != len(expected):
        raise RuntimeError(
            f"Expected {len(expected)} visible CUDA devices, got {torch.cuda.device_count()}"
        )


def _gpu_uuid_by_index() -> dict[str, str]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,uuid",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return {}
    mapping: dict[str, str] = {}
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2:
            mapping[parts[0]] = parts[1]
    return mapping


def _compute_apps_by_index() -> dict[str, list[dict[str, Any]]]:
    uuid_to_index = {uuid: idx for idx, uuid in _gpu_uuid_by_index().items()}
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return {}
    rows: dict[str, list[dict[str, Any]]] = {}
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        idx = uuid_to_index.get(parts[0])
        if idx is None:
            continue
        rows.setdefault(idx, []).append(
            {
                "gpu_uuid": parts[0],
                "pid": int(parts[1]),
                "process_name": parts[2],
                "used_memory_mb": int(parts[3].replace(" MiB", "")),
            }
        )
    return rows


def _assert_target_gpus_idle() -> None:
    apps = _compute_apps_by_index()
    busy = {idx: apps.get(idx, []) for idx in EXPECTED_PHYSICAL_GPUS if apps.get(idx)}
    if busy:
        raise RuntimeError(
            f"physical GPUs {','.join(EXPECTED_PHYSICAL_GPUS)} are not idle before launch: {busy}"
        )


def _make_backend(
    *,
    model: Any,
    cfg: dict[str, Any],
    output_dir: Path,
    ledger_name: str,
) -> AceLoraGrpoBackend:
    method_spec = cfg["methods"][METHOD]
    backend = AceLoraGrpoBackend(
        model,
        _backend_config(cfg),
        output_dir=output_dir,
        method_id=method_spec["method_id"],
        reward_mode=method_spec["reward_mode"],
        ledger_path=output_dir / ledger_name,
    )
    backend.cfg_scale = float(cfg["sampler"]["guidance_scale"])
    return backend


def _sample_members(
    *,
    model: Any,
    prompt: Any,
    group_id: str,
    members: list[int],
    seeds_by_member: dict[int, int],
    cfg_scale: float,
    infer_steps: int,
    sampler_extras: dict[str, Any],
    target_sigmas: list[float] | None,
    sigma_bindings: dict[float, Any] | None,
    logical_device: str,
    producer: str,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for member in members:
        rollout, meta, res = _sample_rollout(
            model=model,
            prompt=prompt,
            seed=int(seeds_by_member[member]),
            group_id=group_id,
            cfg_scale=cfg_scale,
            infer_steps=infer_steps,
            extras=sampler_extras,
            target_sigmas=target_sigmas,
            sigma_bindings=sigma_bindings,
        )
        meta = dict(meta)
        meta.update(
            {
                "member_index": int(member),
                "rollout_logical_device": logical_device,
                "rollout_producer": producer,
            }
        )
        rollout.metadata = dict(rollout.metadata)
        rollout.metadata.update(meta)
        samples.append(
            {
                "member": int(member),
                "rollout": rollout,
                "meta": meta,
                "res": SimpleNamespace(
                    waveform=res.waveform.detach().cpu().float(),
                    sample_rate=int(res.sample_rate),
                    trajectory=[
                        t.detach().cpu().float()
                        for t in (getattr(res, "trajectory", None) or [])
                    ],
                    extras={
                        **(getattr(res, "extras", None) or {}),
                        "trajectory_model_outputs": [
                            t.detach().cpu().float()
                            for t in (
                                (getattr(res, "extras", None) or {}).get(
                                    "trajectory_model_outputs", []
                                )
                            )
                        ],
                    },
                ),
            }
        )
    return samples


def _move_process_res_to_device(res: Any, device: str) -> Any:
    extras = dict(getattr(res, "extras", None) or {})
    extras["trajectory_model_outputs"] = [
        t.to(device) if hasattr(t, "to") else t
        for t in extras.get("trajectory_model_outputs", [])
    ]
    return SimpleNamespace(
        waveform=res.waveform.to(device) if hasattr(res.waveform, "to") else res.waveform,
        sample_rate=res.sample_rate,
        trajectory=[
            t.to(device) if hasattr(t, "to") else t
            for t in (getattr(res, "trajectory", None) or [])
        ],
        extras=extras,
    )


def _worker_main(
    command_q: mp.Queue,
    result_q: mp.Queue,
    *,
    method: str,
    expected_physical_gpus: tuple[str, str],
    config_path: str,
    output_dir: str,
    dtype: str,
    worker_device: str,
) -> None:
    try:
        global METHOD, EXPECTED_PHYSICAL_GPUS
        METHOD = method
        EXPECTED_PHYSICAL_GPUS = tuple(str(x) for x in expected_physical_gpus)
        _assert_visible_physical_gpus()
        cfg = _load_yaml(Path(config_path))
        _validate_bundle(cfg)
        method_spec = cfg["methods"][METHOD]

        from mprm.common.seeding import seed_everything
        from mprm.inference.ace_step import AceStepModel

        seed_everything(int(cfg["backend"]["init_seed"]) + 1)
        worker_dir = Path(output_dir) / f"worker_gpu{EXPECTED_PHYSICAL_GPUS[1]}"
        model = AceStepModel(dtype=dtype, device=worker_device)
        backend = _make_backend(
            model=model,
            cfg=cfg,
            output_dir=worker_dir,
            ledger_name="worker_backend_ledger.jsonl",
        )
        parameter_summary = backend.ensure_lora()
        startup_digest = backend.adapter_digest()
        result_q.put(
            {
                "ok": True,
                "event": "worker_ready",
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "device": worker_device,
                "parameter_summary": parameter_summary,
                "startup_adapter_digest": startup_digest,
            }
        )

        while True:
            cmd = command_q.get()
            if cmd.get("op") == "stop":
                result_q.put({"ok": True, "event": "worker_stopped", "pid": os.getpid()})
                return
            if cmd.get("op") != "sample_batch":
                raise RuntimeError(f"unknown worker op: {cmd.get('op')!r}")

            backend.load_checkpoint(cmd["checkpoint_path"])
            loaded_digest = backend.adapter_digest()
            expected_digest = str(cmd["adapter_digest"])
            if loaded_digest != expected_digest:
                raise RuntimeError(
                    "worker adapter digest mismatch after sync: "
                    f"{loaded_digest} != {expected_digest}"
                )
            started = time.time()
            samples = _sample_members(
                model=model,
                prompt=cmd["prompt"],
                group_id=str(cmd["group_id"]),
                members=[int(x) for x in cmd["members"]],
                seeds_by_member={int(k): int(v) for k, v in cmd["seeds_by_member"].items()},
                cfg_scale=float(cmd["cfg_scale"]),
                infer_steps=int(cmd["infer_steps"]),
                sampler_extras=dict(cmd["sampler_extras"]),
                target_sigmas=cmd.get("target_sigmas"),
                sigma_bindings=cmd.get("sigma_bindings"),
                logical_device=worker_device,
                producer=f"worker_gpu{EXPECTED_PHYSICAL_GPUS[1]}",
            )
            result_q.put(
                {
                    "ok": True,
                    "event": "sample_batch_done",
                    "step": int(cmd["step"]),
                    "prompt_id": cmd["prompt"].prompt_id,
                    "members": [int(s["member"]) for s in samples],
                    "adapter_digest_after_load": loaded_digest,
                    "elapsed_seconds": time.time() - started,
                    "samples": samples,
                }
            )
    except BaseException as exc:  # noqa: BLE001
        result_q.put(
            {
                "ok": False,
                "event": "worker_error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "pid": os.getpid(),
            }
        )


def _get_worker_message(result_q: mp.Queue, *, timeout_s: float) -> dict[str, Any]:
    try:
        msg = result_q.get(timeout=timeout_s)
    except queue.Empty as exc:
        raise RuntimeError(f"worker timed out after {timeout_s} seconds") from exc
    if not msg.get("ok"):
        raise RuntimeError(
            f"worker failed: {msg.get('error_type')}: {msg.get('error')}\n"
            f"{msg.get('traceback', '')}"
        )
    return msg


def _write_summary(path: Path, result: dict[str, Any]) -> None:
    last = result.get("last_update_metrics") or {}
    lines = [
        f"# Phase C1 Two-GPU {result['method']} Smoke Summary",
        "",
        f"- status: {result['status']}",
        f"- architecture: {result['architecture_id']}",
        f"- physical GPUs: {result['physical_gpus_requested']}",
        f"- CUDA_VISIBLE_DEVICES: {result['cuda_visible_devices']}",
        f"- method: {result['method']} ({result['method_id']})",
        f"- prompts: {result['prompts']}",
        f"- steps completed: {result['steps_completed']}",
        f"- group size: {result['group_size']} ({result['group_size_source']})",
        f"- rollout split: {result['rollout_split_policy']}",
        f"- elapsed seconds: {result['elapsed_seconds']:.3f}",
        f"- two-GPU smoke GPU-hours: {result['gpu_hours_consumed']:.6f}",
        f"- adapter updated: {result['adapter_updated']}",
        f"- base parameters frozen: {result['base_parameters_frozen']}",
        f"- checkpoint resume ok: {result['checkpoint_resume_ok']}",
        f"- final adapter digest: {result['final_adapter_digest']}",
        f"- loss: {last.get('loss')}",
        f"- approx_kl_old: {last.get('approx_kl_old')}",
        f"- approx_kl_ref: {last.get('approx_kl_ref')}",
        f"- grad_norm: {last.get('grad_norm')}",
        "",
        "This is a feasibility smoke only, not a formal Phase C result.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_two_gpu_smoke(args: argparse.Namespace) -> dict[str, Any]:
    _assert_visible_physical_gpus()
    _assert_target_gpus_idle()
    cfg_path = (REPO_ROOT / args.config).resolve()
    cfg = _load_yaml(cfg_path)
    _validate_bundle(cfg)

    method_spec = cfg["methods"][METHOD]
    reward_mode = method_spec["reward_mode"]
    prompt_ids = args.prompt_ids or list(cfg["smoke"]["prompt_ids"])
    if not (2 <= len(prompt_ids) <= 4):
        raise RuntimeError("Researcher requested 2-4 dev prompts for this smoke")
    prompts = _load_prompts(cfg, prompt_ids=prompt_ids)

    group_size = int(cfg["firstwave"]["group_size"])
    if group_size % 2 != 0:
        raise RuntimeError(f"group_size must split evenly across two GPUs, got {group_size}")
    steps = int(args.steps)
    if steps < 1 or steps > 2:
        raise RuntimeError("--steps must be 1 or 2 for this smoke")

    output_dir = Path(args.output_root).resolve() / METHOD
    if output_dir.exists():
        raise RuntimeError(f"refusing to write into existing output dir: {output_dir}")
    output_dir.mkdir(parents=True)
    log_path = output_dir / "two_gpu_smoke_log.jsonl"

    from mprm.common.seeding import seed_everything
    from mprm.inference.ace_step import AceStepModel

    seed_everything(int(cfg["backend"]["init_seed"]))
    t0 = time.time()
    before_gpu = _nvidia_snapshot()

    sampler = cfg["sampler"]
    cfg_scale = float(sampler["guidance_scale"])
    infer_steps = int(
        sampler["terminal_infer_step"] if reward_mode == "terminal"
        else sampler["process_infer_step"]
    )
    sampler_extras = _sampler_extras(cfg)
    max_kl = float(cfg["firstwave"]["max_kl_vs_ref"])
    min_reward_std = float(cfg["firstwave"]["reward_collapse"]["min_group_reward_std"])

    controller_model = AceStepModel(dtype=args.dtype, device="cuda:0")
    controller_backend = _make_backend(
        model=controller_model,
        cfg=cfg,
        output_dir=output_dir,
        ledger_name="controller_backend_ledger.jsonl",
    )
    parameter_summary = controller_backend.ensure_lora()
    initial_adapter_digest = controller_backend.adapter_digest()
    if reward_mode == "terminal":
        reward_ctx = _load_terminal_context(METHOD, cfg)
        target_sigmas = None
        sigma_bindings = None
    else:
        reward_ctx = _load_process_context(METHOD, cfg)
        target_sigmas = reward_ctx["target_sigmas"]
        sigma_bindings = reward_ctx["sigma_bindings"]

    ctx = mp.get_context("spawn")
    command_q: mp.Queue = ctx.Queue()
    result_q: mp.Queue = ctx.Queue()
    worker = ctx.Process(
        target=_worker_main,
        kwargs={
            "command_q": command_q,
            "result_q": result_q,
            "method": METHOD,
            "expected_physical_gpus": EXPECTED_PHYSICAL_GPUS,
            "config_path": str(cfg_path),
            "output_dir": str(output_dir),
            "dtype": args.dtype,
            "worker_device": "cuda:1",
        },
    )
    worker.start()
    worker_ready = _get_worker_message(result_q, timeout_s=args.worker_timeout_s)
    _append_jsonl(
        log_path,
        {
            "event": "worker_ready",
            "timestamp": _now_utc(),
            "worker": worker_ready,
            "architecture_id": ARCHITECTURE_ID,
        },
    )

    checkpoint_path: Path | None = None
    checkpoint_resume_ok = False
    completed = 0
    gpu_h_by_step: list[float] = []
    last_metrics: dict[str, Any] | None = None
    worker_batches: list[dict[str, Any]] = []
    controller_members = [m for m in range(group_size) if m % 2 == 0]
    worker_members = [m for m in range(group_size) if m % 2 == 1]

    try:
        for step in range(steps):
            step_start = time.time()
            sync_checkpoint = controller_backend.save_checkpoint(
                output_dir / f"sync_adapter_step_{step:06d}.pt"
            )
            sync_payload = controller_backend.load_checkpoint(sync_checkpoint)
            if sync_payload.get("schema_version") != "ace_step_lora_grpo_checkpoint_v1":
                raise RuntimeError("controller sync checkpoint resume failed")
            sync_digest = controller_backend.adapter_digest()
            all_rollouts: list[GrpoRollout] = []
            all_reward_reports: list[dict[str, Any]] = []
            reward_stds: list[float] = []
            prompt_ids_for_step: list[str] = []
            rollout_split_reports: list[dict[str, Any]] = []

            for prompt_index, prompt in enumerate(prompts):
                prompt_ids_for_step.append(prompt.prompt_id)
                group_id = f"{method_spec['method_id']}:two_gpu_step{step}:{prompt.prompt_id}"
                seeds_by_member = {
                    member: (
                        _rollout_seed(int(cfg["firstwave"]["seeds"][0]), step, member)
                        + 100 * (prompt_index + 1)
                    )
                    for member in range(group_size)
                }
                command_q.put(
                    {
                        "op": "sample_batch",
                        "step": step,
                        "prompt": prompt,
                        "group_id": group_id,
                        "members": worker_members,
                        "seeds_by_member": seeds_by_member,
                        "cfg_scale": cfg_scale,
                        "infer_steps": infer_steps,
                        "sampler_extras": sampler_extras,
                        "target_sigmas": target_sigmas,
                        "sigma_bindings": sigma_bindings,
                        "checkpoint_path": str(sync_checkpoint),
                        "adapter_digest": sync_digest,
                    }
                )

                controller_started = time.time()
                controller_samples = _sample_members(
                    model=controller_model,
                    prompt=prompt,
                    group_id=group_id,
                    members=controller_members,
                    seeds_by_member=seeds_by_member,
                    cfg_scale=cfg_scale,
                    infer_steps=infer_steps,
                    sampler_extras=sampler_extras,
                    target_sigmas=target_sigmas,
                    sigma_bindings=sigma_bindings,
                    logical_device="cuda:0",
                    producer=f"controller_gpu{EXPECTED_PHYSICAL_GPUS[0]}",
                )
                controller_elapsed = time.time() - controller_started
                worker_msg = _get_worker_message(result_q, timeout_s=args.worker_timeout_s)
                if worker_msg.get("event") != "sample_batch_done":
                    raise RuntimeError(f"unexpected worker event: {worker_msg.get('event')}")
                worker_batches.append(
                    {
                        "step": worker_msg["step"],
                        "prompt_id": worker_msg["prompt_id"],
                        "members": worker_msg["members"],
                        "elapsed_seconds": worker_msg["elapsed_seconds"],
                        "adapter_digest_after_load": worker_msg["adapter_digest_after_load"],
                    }
                )
                samples = list(controller_samples) + list(worker_msg["samples"])
                samples.sort(key=lambda s: int(s["member"]))
                if [int(s["member"]) for s in samples] != list(range(group_size)):
                    raise RuntimeError("combined samples do not cover one full GRPO group")

                if reward_mode == "terminal":
                    reward_reports = _score_terminal_group(
                        ctx=reward_ctx,
                        prompt=prompt,
                        samples=samples,
                    )
                else:
                    for sample in samples:
                        sample["res"] = _move_process_res_to_device(sample["res"], "cuda:0")
                    reward_reports = [
                        _score_process_sample(
                            ctx=reward_ctx,
                            prompt=prompt,
                            sample=s,
                            model=controller_model,
                        )
                        for s in samples
                    ]
                rollouts = [s["rollout"] for s in samples]
                rewards = torch.tensor([float(r.reward) for r in rollouts], dtype=torch.float32)
                if not bool(torch.isfinite(rewards).all().item()):
                    raise RuntimeError("reward tensor contains NaN/Inf")
                reward_std = float(rewards.std(unbiased=False).item())
                reward_stds.append(reward_std)
                all_rollouts.extend(rollouts)
                all_reward_reports.extend(reward_reports)
                rollout_split_reports.append(
                    {
                        "prompt_id": prompt.prompt_id,
                        "group_id": group_id,
                        "controller_members": controller_members,
                        "worker_members": worker_members,
                        "worker_adapter_digest_after_load": worker_msg["adapter_digest_after_load"],
                        "controller_adapter_digest_at_sync": sync_digest,
                        "controller_elapsed_seconds": controller_elapsed,
                        "worker_elapsed_seconds": worker_msg["elapsed_seconds"],
                        "reward_std": reward_std,
                    }
                )

            if not all_rollouts:
                raise RuntimeError("no rollouts generated for update")
            reward_std_min = min(reward_stds) if reward_stds else 0.0
            old_ref = controller_backend.cache_old_and_ref_logps(all_rollouts)
            update_metrics = controller_backend.update(all_rollouts)
            _check_update_metrics(update_metrics, max_kl_vs_ref=max_kl)
            if reward_std_min <= min_reward_std:
                raise RuntimeError(
                    f"reward collapse: group reward std {reward_std_min} <= {min_reward_std}"
                )
            if update_metrics["advantage_info"]["n_zero_variance_groups"] > 0:
                raise RuntimeError("reward collapse: zero-variance GRPO group")

            completed += 1
            step_elapsed = time.time() - step_start
            gpu_h_by_step.append((step_elapsed * 2.0) / 3600.0)
            checkpoint_path = controller_backend.save_checkpoint(
                output_dir / f"checkpoint_step_{completed:06d}.pt"
            )
            payload = controller_backend.load_checkpoint(checkpoint_path)
            checkpoint_resume_ok = (
                payload.get("schema_version") == "ace_step_lora_grpo_checkpoint_v1"
            )
            if not checkpoint_resume_ok:
                raise RuntimeError("checkpoint resume check failed")
            last_metrics = update_metrics
            _append_jsonl(
                log_path,
                {
                    "event": "optimizer_step",
                    "timestamp": _now_utc(),
                    "mode": "two_gpu_smoke",
                    "architecture_id": ARCHITECTURE_ID,
                    "method": METHOD,
                    "method_id": method_spec["method_id"],
                    "step": step,
                    "prompt_ids": prompt_ids_for_step,
                    "group_size": group_size,
                    "group_size_source": "configs/runs/phase_c1_firstwave.yaml:firstwave.group_size",
                    "infer_steps": infer_steps,
                    "elapsed_seconds": step_elapsed,
                    "gpu_hours_consumed": (step_elapsed * 2.0) / 3600.0,
                    "reward_std_min": reward_std_min,
                    "rollout_split_reports": rollout_split_reports,
                    "reward_reports": all_reward_reports,
                    "old_ref_logps": old_ref,
                    "update_metrics": update_metrics,
                    "sync_checkpoint_path": str(sync_checkpoint),
                    "checkpoint_path": str(checkpoint_path),
                    "checkpoint_resume_ok": checkpoint_resume_ok,
                    "semantics": {
                        "single_logical_adapter": True,
                        "controller_owns_optimizer": True,
                        "worker_optimizer_steps": 0,
                        "full_group_aggregation_before_update": True,
                        "old_ref_new_logps_on_controller_after_aggregation": True,
                        "worker_synced_from_controller_checkpoint_before_rollout": True,
                    },
                    "safety": {
                        "formal_phase_c1_training": False,
                        "held_out_launched": False,
                        "phase_d_launched": False,
                        "human_eval_launched": False,
                    },
                },
            )
    finally:
        if worker.is_alive():
            command_q.put({"op": "stop"})
            try:
                stop_msg = _get_worker_message(result_q, timeout_s=120.0)
                _append_jsonl(log_path, {"event": "worker_stop", "timestamp": _now_utc(), "worker": stop_msg})
            except Exception as exc:  # noqa: BLE001
                _append_jsonl(
                    log_path,
                    {
                        "event": "worker_stop_failed",
                        "timestamp": _now_utc(),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
            worker.join(timeout=120.0)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=30.0)

    torch.cuda.synchronize(torch.device("cuda:0"))
    elapsed = time.time() - t0
    final_adapter_digest = controller_backend.adapter_digest()
    result = {
        "schema_version": "phase_c1_two_gpu_rollout_parallel_smoke_v1",
        "status": "PASS",
        "architecture_id": ARCHITECTURE_ID,
        "method": METHOD,
        "method_id": method_spec["method_id"],
        "display_name": method_spec["display_name"],
        "reward_mode": reward_mode,
        "output_dir": str(output_dir),
        "host": socket.gethostname(),
        "controller_pid": os.getpid(),
        "physical_gpus_requested": [int(x) for x in EXPECTED_PHYSICAL_GPUS],
        "cuda_visible_devices": _visible_devices(),
        "logical_devices": {"controller": "cuda:0", "worker": "cuda:1"},
        "elapsed_seconds": elapsed,
        "wall_clock_hours": elapsed / 3600.0,
        "gpu_hours_consumed": (elapsed * 2.0) / 3600.0,
        "steps_completed": completed,
        "group_size": group_size,
        "group_size_source": "firstwave.group_size",
        "infer_steps": infer_steps,
        "prompts": [p.prompt_id for p in prompts],
        "sampler_extras": sampler_extras,
        "rollout_split_policy": (
            f"even members on controller GPU{EXPECTED_PHYSICAL_GPUS[0]}; "
            f"odd members on worker GPU{EXPECTED_PHYSICAL_GPUS[1]}"
        ),
        "worker_batches": worker_batches,
        "parameter_summary": parameter_summary,
        "initial_adapter_digest": initial_adapter_digest,
        "final_adapter_digest": final_adapter_digest,
        "adapter_updated": initial_adapter_digest != final_adapter_digest,
        "base_parameters_frozen": parameter_summary["base_parameters_frozen"],
        "last_update_metrics": last_metrics,
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        "checkpoint_resume_ok": checkpoint_resume_ok,
        "log_path": str(log_path),
        "log_written": log_path.exists() and log_path.stat().st_size > 0,
        "cuda_max_memory_allocated_mb_controller": int(
            torch.cuda.max_memory_allocated(torch.device("cuda:0")) / (1024 * 1024)
        ),
        "nvidia_smi_before": before_gpu,
        "nvidia_smi_after": _nvidia_snapshot(),
        "gpu_hours_by_step": gpu_h_by_step,
        "scientific_equivalence_checks": {
            "single_logical_adapter": True,
            "controller_owns_only_optimizer_update": True,
            "worker_rollout_replica_synced_by_adapter_checkpoint": True,
            "worker_digest_verified_before_each_rollout_batch": True,
            "full_grpo_group_size_preserved": True,
            "full_group_rewards_aggregated_before_advantage_update": True,
            "old_ref_new_logps_computed_on_controller_after_aggregation": True,
            "frozen_base_parameters_checked_by_backend": bool(
                last_metrics and last_metrics.get("frozen_parameters", {}).get("unchanged")
            ),
            "adapter_updated_by_controller": initial_adapter_digest != final_adapter_digest,
            "checkpoint_save_resume_checked": checkpoint_resume_ok,
        },
        "reward_definitions_changed": False,
        "sigma_policy_changed": False,
        "prompt_splits_changed": False,
        "credit_unit_definitions_changed": False,
        "gate_v1_touched_by_runner": False,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
        "no_formal_result_claim": True,
    }
    _write_json(output_dir / "two_gpu_smoke_results.json", result)
    _write_summary(output_dir / "two_gpu_smoke_summary.md", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("r8a", "r8b", "m_fixedwin", "m_section"), default="r8a")
    parser.add_argument("--config", default="configs/runs/phase_c1_firstwave.yaml")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--prompt-ids", nargs="+", default=None)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--worker-timeout-s", type=float, default=7200.0)
    parser.add_argument("--expected-physical-gpus", nargs=2, default=["5", "6"])
    args = parser.parse_args()

    global METHOD, EXPECTED_PHYSICAL_GPUS
    METHOD = args.method
    EXPECTED_PHYSICAL_GPUS = tuple(str(x) for x in args.expected_physical_gpus)
    result = run_two_gpu_smoke(args)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output_dir": result["output_dir"],
                "steps_completed": result["steps_completed"],
                "gpu_hours_consumed": result["gpu_hours_consumed"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[phase-c1-two-gpu-smoke] FAIL: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise
