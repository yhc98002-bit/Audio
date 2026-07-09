"""Smoke tests for the shared ACE-Step LoRA/GRPO backend.

This script is deliberately smoke-only. It never launches formal Phase C,
held-out, Phase D, or human evaluation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
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


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _load_prompts(prompt_source: Path, prompt_ids: list[str]):
    from scripts.phase_c_m_fixedwin_prm import _load_prompts_by_id, _prompt_from_row

    rows = _load_prompts_by_id(prompt_source)
    missing = [pid for pid in prompt_ids if pid not in rows]
    if missing:
        raise RuntimeError(f"missing prompt IDs in {prompt_source}: {missing}")
    return [_prompt_from_row(rows[pid]) for pid in prompt_ids]


def _nvidia_snapshot() -> list[dict[str, Any]]:
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    rows = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        rows.append(
            {
                "index": int(parts[0]),
                "memory_used_mb": int(parts[1]),
                "memory_total_mb": int(parts[2]),
                "utilization_gpu_percent": int(parts[3]),
            }
        )
    return rows


def _sampler_extras_from_phase_c(cfg: dict[str, Any]) -> dict[str, Any]:
    sampler = cfg["sampler"]
    return {
        "cfg_type": sampler["cfg_type"],
        "use_erg_tag": sampler["use_erg_tag"],
        "use_erg_lyric": sampler["use_erg_lyric"],
        "use_erg_diffusion": sampler["use_erg_diffusion"],
        "guidance_interval": sampler["guidance_interval"],
    }


def _select_steps_from_result(
    res: Any,
    *,
    target_sigmas: list[float] | None,
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
    steps = [
        CapturedStep(
            latent=traj[k].to(torch.float32),
            sigma=float(sigmas[k]),
            step_index=int(k),
            cfg_active=bool(cfg_flags[k]) if k < len(cfg_flags) else True,
        )
        for k in indices
    ]
    return steps, {
        "selection_policy": "configured_sigmas" if target_sigmas else "all_captured_steps",
        "target_sigmas": target_sigmas,
        "selected_step_indices": [s.step_index for s in steps],
        "selected_sigmas": [s.sigma for s in steps],
    }


def _sample_rollout(
    *,
    model: Any,
    prompt: Any,
    seed: int,
    reward: float,
    group_id: str,
    cfg_scale: float,
    steps: int,
    extras: dict[str, Any],
    target_sigmas: list[float] | None,
) -> tuple[GrpoRollout, dict[str, Any], Any]:
    res = model.sample(
        prompt,
        seed=seed,
        cfg_scale=cfg_scale,
        steps=steps,
        return_trajectory=True,
        extras=extras,
    )
    selected, selection_info = _select_steps_from_result(res, target_sigmas=target_sigmas)
    with torch.no_grad():
        z0 = model.encode(res.waveform)
    rollout = GrpoRollout(
        prompt_id=prompt.prompt_id,
        group_id=group_id,
        reward=reward,
        prompt=prompt,
        steps=selected,
        z0=z0.detach().cpu().float(),
        metadata={
            "seed": seed,
            "duration_actual_s": float(res.waveform.shape[-1]) / float(res.sample_rate),
            "selection": selection_info,
        },
    )
    return rollout, rollout.metadata, res


def _fixture_terminal_reward(waveform: torch.Tensor) -> float:
    # Smoke-only finite terminal scalar. Formal reward definitions stay outside
    # the backend and are not modified by this fixture.
    w = waveform.detach().float()
    return float(w.pow(2).mean().sqrt().cpu().item())


def _process_reward_from_phase_c(
    *,
    cfg: dict[str, Any],
    prompt: Any,
    res: Any,
    model: Any,
    reward_stack: dict[str, Any],
    credit_unit: Any,
    target_sigmas: list[float],
) -> tuple[float, dict[str, Any]]:
    from scripts.phase_c_m_fixedwin_prm import (
        _cvar_lower_tail,
        _pick_sigma_index,
        _score_segment_vectors,
    )

    traj = res.trajectory or []
    traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
    traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
    if not traj or not traj_sigmas or not traj_vs:
        raise RuntimeError("trajectory capture missing for process reward")
    intermediates: dict[float, Any] = {}
    for sigma in target_sigmas:
        k = _pick_sigma_index(sigma, traj_sigmas)
        z0_hat = traj[k].to(torch.float32) - float(traj_sigmas[k]) * traj_vs[k].to(torch.float32)
        intermediates[float(sigma)] = model.decode(z0_hat)
    seg_out = credit_unit.segment(res.waveform, res.sample_rate, prompt, seed=0)
    if not seg_out.applicable or len(seg_out.segments) < 2:
        raise RuntimeError(f"credit unit produced {len(seg_out.segments)} applicable segments")
    rows, deltas = _score_segment_vectors(
        cfg=cfg,
        prompt=prompt,
        final_audio=res.waveform,
        intermediates=intermediates,
        sample_rate=res.sample_rate,
        reward_stack=reward_stack,
        segments=seg_out.segments,
    )
    if not deltas:
        raise RuntimeError("no finite process reward deltas")
    delta_tensor = torch.tensor(deltas, dtype=torch.float32)
    cvar = _cvar_lower_tail(
        delta_tensor,
        alpha=float(cfg["reward_policy"]["cvar"]["alpha"]),
        beta=float(cfg["reward_policy"]["cvar"]["beta"]),
    )
    return float(cvar.detach().cpu().item()), {
        "n_segments": len(seg_out.segments),
        "segments": [
            {"start_s": s.start_s, "end_s": s.end_s, "label": s.label}
            for s in seg_out.segments
        ],
        "n_reward_deltas": len(deltas),
        "reward_rows": rows,
        "process_scalar": float(cvar.detach().cpu().item()),
    }


def _backend_config(rank: int, lr: float) -> BackendConfig:
    return BackendConfig(
        lora_rank=rank,
        learning_rate=lr,
        epsilon_clip=0.2,
        lambda_kl=0.05,
        ratio_variance=1.0,
        ratio_clip_log=5.0,
        sigma_floor=1.0e-5,
        max_grad_norm=1.0,
    )


def smoke_lora(args: argparse.Namespace) -> dict[str, Any]:
    from mprm.inference.ace_step import AceStepModel

    out_dir = Path(args.output_root) / "lora_insertion"
    model = AceStepModel(dtype=args.dtype)
    backend = AceLoraGrpoBackend(
        model,
        _backend_config(args.lora_rank, args.lr),
        output_dir=out_dir,
        method_id="lora_insertion_smoke",
        reward_mode="none",
    )
    summary = backend.ensure_lora()
    result = {
        "schema_version": "ace_lora_grpo_smoke_v1",
        "smoke": "lora_insertion",
        "status": "PASS",
        "summary": summary,
        "nvidia_smi": _nvidia_snapshot(),
        "formal_phase_c_launched": False,
    }
    _write_json(out_dir / "smoke_results.json", result)
    return result


def _run_update_smoke(
    *,
    args: argparse.Namespace,
    smoke_name: str,
    method_id: str,
    reward_mode: str,
    phase_c_config: Path | None = None,
    terminal: bool = False,
    section: bool = False,
) -> dict[str, Any]:
    from mprm.inference.ace_step import AceStepModel
    from scripts.phase_c_m_fixedwin_prm import (
        _load_credit_unit_for_config,
        _load_reward_stack_for_config,
    )

    t0 = time.time()
    out_dir = Path(args.output_root) / smoke_name
    out_dir.mkdir(parents=True, exist_ok=True)
    model = AceStepModel(dtype=args.dtype)
    backend = AceLoraGrpoBackend(
        model,
        _backend_config(args.lora_rank, args.lr),
        output_dir=out_dir,
        method_id=method_id,
        reward_mode=reward_mode,
    )
    summary = backend.ensure_lora()
    backend.cfg_scale = 5.0

    if phase_c_config is not None:
        cfg = _load_yaml(phase_c_config)
        prompts = _load_prompts(REPO_ROOT / cfg["scope"]["prompt_source"], args.prompt_ids)
        sampler_extras = _sampler_extras_from_phase_c(cfg)
        cfg_scale = float(cfg["sampler"]["guidance_scale"])
        infer_steps = int(args.infer_steps or cfg["sampler"]["infer_step"])
        target_sigmas = [float(x["target"]) for x in cfg["sigma_policy"]["downstream_checkpoints"]]
        reward_stack = _load_reward_stack_for_config(cfg)
        credit_unit = _load_credit_unit_for_config(cfg)
    else:
        prompts = _load_prompts(REPO_ROOT / "configs/prompts/dev.jsonl", args.prompt_ids)
        sampler_extras = {
            "cfg_type": "cfg",
            "use_erg_tag": False,
            "use_erg_lyric": False,
            "use_erg_diffusion": False,
            "guidance_interval": 0.5,
        }
        cfg_scale = 5.0
        infer_steps = int(args.infer_steps or 5)
        target_sigmas = None
        reward_stack = {}
        credit_unit = None

    backend.cfg_scale = cfg_scale
    rollouts: list[GrpoRollout] = []
    rollout_reports: list[dict[str, Any]] = []
    for idx, prompt in enumerate(prompts):
        seed = args.seed_base + idx
        placeholder_reward = 0.0
        rollout, meta, res = _sample_rollout(
            model=model,
            prompt=prompt,
            seed=seed,
            reward=placeholder_reward,
            group_id="backend_smoke_group",
            cfg_scale=cfg_scale,
            steps=infer_steps,
            extras=sampler_extras,
            target_sigmas=target_sigmas,
        )
        if terminal:
            reward = _fixture_terminal_reward(res.waveform)
            reward_report = {
                "reward_source": "smoke_fixture_terminal_rms",
                "terminal_reward": reward,
                "formal_reward_claim": False,
            }
        else:
            assert phase_c_config is not None and credit_unit is not None
            reward, reward_report = _process_reward_from_phase_c(
                cfg=cfg,
                prompt=prompt,
                res=res,
                model=model,
                reward_stack=reward_stack,
                credit_unit=credit_unit,
                target_sigmas=target_sigmas or [],
            )
            reward_report["reward_source"] = "phase_c_h2_allowed_process_reward_stack"
        rollout.reward = reward
        rollouts.append(rollout)
        rollout_reports.append({"prompt_id": prompt.prompt_id, **meta, **reward_report})

    old_ref = backend.cache_old_and_ref_logps(rollouts)
    update_metrics = backend.update(rollouts)
    ckpt = backend.save_checkpoint()
    resume_payload = backend.load_checkpoint(ckpt)
    elapsed = time.time() - t0
    result = {
        "schema_version": "ace_lora_grpo_smoke_v1",
        "smoke": smoke_name,
        "status": "PASS",
        "method_id": method_id,
        "reward_mode": reward_mode,
        "elapsed_seconds": elapsed,
        "gpu_hours_consumed": elapsed / 3600.0,
        "parameter_summary": summary,
        "rollouts": rollout_reports,
        "old_ref_logps": old_ref,
        "update_metrics": update_metrics,
        "checkpoint_path": str(ckpt),
        "checkpoint_resume_ok": resume_payload.get("schema_version") == "ace_step_lora_grpo_checkpoint_v1",
        "nvidia_smi": _nvidia_snapshot(),
        "formal_phase_c_launched": False,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
        "section_diagnostic": section,
    }
    _write_json(out_dir / "smoke_results.json", result)
    return result


def smoke_old_new(args: argparse.Namespace) -> dict[str, Any]:
    return _run_update_smoke(
        args=args,
        smoke_name="old_new_policy_forward",
        method_id="old_new_policy_forward_smoke",
        reward_mode="terminal",
        terminal=True,
    )


def smoke_r8a(args: argparse.Namespace) -> dict[str, Any]:
    return _run_update_smoke(
        args=args,
        smoke_name="r8a_terminal_grpo",
        method_id="R8a",
        reward_mode="terminal",
        terminal=True,
    )


def smoke_m_fixedwin(args: argparse.Namespace) -> dict[str, Any]:
    return _run_update_smoke(
        args=args,
        smoke_name="m_fixedwin_process_grpo",
        method_id="M-FixedWin-PRM",
        reward_mode="process",
        phase_c_config=Path("configs/runs/phase_c_m_fixedwin_firstwave.yaml"),
    )


def smoke_m_section(args: argparse.Namespace) -> dict[str, Any]:
    return _run_update_smoke(
        args=args,
        smoke_name="m_section_process_grpo",
        method_id="M-Section-PRM",
        reward_mode="process",
        phase_c_config=Path("configs/runs/phase_c_m_section_diagnostic.yaml"),
        section=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--smoke",
        choices=["lora", "old_new", "r8a", "m_fixedwin", "m_section", "all"],
        required=True,
    )
    parser.add_argument("--output-root", default="runs/ace_lora_grpo_backend_smoke")
    parser.add_argument("--prompt-ids", nargs="+", default=["dev_0000", "dev_0001"])
    parser.add_argument("--seed-base", type=int, default=20260524)
    parser.add_argument("--lora-rank", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1.0e-4)
    parser.add_argument("--infer-steps", type=int, default=None)
    parser.add_argument("--dtype", default="bfloat16")
    args = parser.parse_args()

    if len(args.prompt_ids) < 1:
        raise SystemExit("--prompt-ids must not be empty")
    if args.smoke in {"r8a", "m_fixedwin", "m_section", "all"} and len(args.prompt_ids) < 2:
        raise SystemExit("R8a/M-PRM smokes require at least 2 prompts")
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for ACE-Step backend GPU smoke tests")

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    dispatch = {
        "lora": smoke_lora,
        "old_new": smoke_old_new,
        "r8a": smoke_r8a,
        "m_fixedwin": smoke_m_fixedwin,
        "m_section": smoke_m_section,
    }
    if args.smoke == "all":
        results = {}
        for name in ["lora", "old_new", "r8a", "m_fixedwin", "m_section"]:
            print(f"[ace-lora-grpo-smoke] running {name}", flush=True)
            results[name] = dispatch[name](args)
        _write_json(Path(args.output_root) / "all_smoke_results.json", results)
    else:
        result = dispatch[args.smoke](args)
        print(json.dumps({"smoke": args.smoke, "status": result["status"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
