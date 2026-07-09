"""Phase C paired M-PRM smoke and first-wave preflight.

This runner deliberately separates:

1. smoke: an engineering end-to-end check for the FixedWin process-reward
   path (trajectory capture, Tweedie decode, FixedWin segmentation, reward
   deltas, loss, optimizer step, logging, checkpoint/resume);
2. firstwave: a formal-launch preflight that refuses to train while the
   production ACE-Step LoRA/GRPO logprob-ratio update path is not ready.

The smoke writes no formal result claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_config(cfg: dict[str, Any], *, require_pi: bool) -> list[str]:
    fails: list[str] = []
    if cfg.get("schema_version") not in {
        "phase_c_m_fixedwin_firstwave_v1",
        "phase_c_m_prm_diagnostic_v1",
    }:
        fails.append("schema_version must be phase_c_m_fixedwin_firstwave_v1 or phase_c_m_prm_diagnostic_v1")
    if require_pi:
        for key in ("pi_approved_binding", "pi_approved_smoke", "pi_approved_firstwave"):
            if cfg.get(key) is not True:
                fails.append(f"{key} must be true")

    pivot = cfg.get("accepted_pivot", {})
    if pivot.get("primary_method") != "M-FixedWin-PRM":
        fails.append("accepted_pivot.primary_method must be M-FixedWin-PRM")
    if pivot.get("primary_credit_unit") != "FixedWin":
        fails.append("accepted_pivot.primary_credit_unit must be FixedWin")
    if pivot.get("diagnostic_control") != "M-Section-PRM":
        fails.append("accepted_pivot.diagnostic_control must be M-Section-PRM")

    scope = cfg.get("scope", {})
    forbidden_true = [
        "held_out_launched",
        "phase_d_launched",
        "human_eval_launched",
        "m_section_primary_training_launched",
    ]
    for key in forbidden_true:
        if scope.get(key) is not False:
            fails.append(f"scope.{key} must be false")
    if scope.get("split") != "dev":
        fails.append("scope.split must be dev")

    sampler = cfg.get("sampler", {})
    expected_sampler = {
        "cfg_type": "cfg",
        "use_erg_tag": False,
        "use_erg_lyric": False,
        "use_erg_diffusion": False,
        "guidance_interval": 0.5,
    }
    for key, expected in expected_sampler.items():
        if sampler.get(key) != expected:
            fails.append(f"sampler.{key}={sampler.get(key)!r}; expected {expected!r}")

    method = cfg.get("method", {})
    method_name = method.get("name")
    method_role = method.get("role")
    credit = cfg.get("credit_unit", {}).get("primary", {})
    credit_name = credit.get("name")
    credit_id = credit.get("id")
    if credit_name == "fixed_window":
        if credit_id != "CU-FW":
            fails.append("fixed_window config must use credit_unit.primary.id=CU-FW")
        if float(credit.get("window_seconds", 0.0)) != 4.0:
            fails.append("credit_unit.primary.window_seconds must be 4.0")
        if method_name and method_name != "M-FixedWin-PRM":
            fails.append("fixed_window config method.name must be M-FixedWin-PRM")
    elif credit_name == "musical_section":
        if credit_id != "CU-MS":
            fails.append("musical_section config must use credit_unit.primary.id=CU-MS")
        if method_name and method_name != "M-Section-PRM":
            fails.append("musical_section config method.name must be M-Section-PRM")
        if method_role and method_role != "diagnostic_negative_control":
            fails.append("M-Section config method.role must be diagnostic_negative_control")
    else:
        fails.append(f"unsupported credit_unit.primary.name={credit_name!r}")

    cvar = cfg.get("reward_policy", {}).get("cvar", {})
    if float(cvar.get("alpha", -1)) != 0.30:
        fails.append("reward_policy.cvar.alpha must be 0.30")
    if float(cvar.get("beta", -1)) != 0.0:
        fails.append("reward_policy.cvar.beta must be 0")
    if float(cfg.get("reward_policy", {}).get("beta_robust", -1)) != 0.5:
        fails.append("reward_policy.beta_robust must be 0.5")

    sigma_targets = [float(x["target"]) for x in cfg.get("sigma_policy", {}).get("downstream_checkpoints", [])]
    if sigma_targets != [0.7, 0.6]:
        fails.append(f"sigma_policy.downstream_checkpoints targets must be [0.7, 0.6], got {sigma_targets}")

    allowed_sigma_set = {0.7, 0.6}
    for item in cfg.get("reward_policy", {}).get("h2_allowed_axis_sigma_pairs", []):
        sigmas = {float(s) for s in item.get("sigmas", [])}
        if not sigmas or not sigmas.issubset(allowed_sigma_set):
            fails.append(f"reward axis {item.get('reward_axis_id')} has invalid sigmas {sorted(sigmas)}")
        if item.get("reward_axis_id") == "semantic_fit" and sigmas != {0.6}:
            fails.append("semantic_fit must only be used at sigma 0.6")

    return fails


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
    rows = []
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


def _axis_sigma_items(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in cfg["reward_policy"]["h2_allowed_axis_sigma_pairs"]:
        for sigma in item["sigmas"]:
            items.append(
                {
                    "gating_axis": item["gating_axis"],
                    "reward_axis_id": item["reward_axis_id"],
                    "sigma": float(sigma),
                }
            )
    return items


def _load_reward_stack_for_config(cfg: dict[str, Any]) -> dict[str, Any]:
    reward_ids = {x["reward_axis_id"] for x in cfg["reward_policy"]["h2_allowed_axis_sigma_pairs"]}
    stack: dict[str, Any] = {}
    if "aesthetic_pq" in reward_ids or "aesthetic_ce" in reward_ids:
        from mprm.rewards.audiobox import AudioboxReward

        if "aesthetic_pq" in reward_ids:
            stack["aesthetic_pq"] = AudioboxReward(target_axis="PQ")
        if "aesthetic_ce" in reward_ids:
            stack["aesthetic_ce"] = AudioboxReward(target_axis="CE")
    if "section_coherence" in reward_ids:
        from mprm.rewards.mert import MertReward

        stack["section_coherence"] = MertReward()
    if "semantic_fit" in reward_ids:
        from mprm.rewards.clap import ClapReward

        stack["semantic_fit"] = ClapReward()
    return stack


def _pick_sigma_index(target: float, traj_sigmas: list[float]) -> int:
    return min(range(len(traj_sigmas)), key=lambda k: abs(float(traj_sigmas[k]) - target))


def _cvar_lower_tail(values, alpha: float, beta: float):
    import torch

    flat = values.flatten()
    if flat.numel() == 0:
        raise ValueError("cannot aggregate empty reward tensor")
    sorted_vals = torch.sort(flat).values
    k = max(1, int(math.ceil(alpha * sorted_vals.numel())))
    return sorted_vals[:k].mean() + beta * sorted_vals.mean()


def _load_credit_unit_for_config(cfg: dict[str, Any]):
    credit = cfg["credit_unit"]["primary"]
    name = credit["name"]
    if name == "fixed_window":
        from mprm.credit_units.fixed_window import FixedWindowUnit

        return FixedWindowUnit(
            window_seconds=float(credit["window_seconds"]),
            min_tail_seconds=float(credit.get("min_tail_seconds", 0.5)),
        )
    if name == "musical_section":
        from mprm.credit_units.musical_section import MusicalSectionUnit

        params = credit.get("parameters", {})
        return MusicalSectionUnit(
            use_mert=bool(params.get("use_mert", True)),
            n_sections_prior=int(params.get("n_sections_prior", 4)),
            min_section_seconds=float(params.get("min_section_seconds", 2.0)),
        )
    raise ValueError(f"unsupported credit unit: {name}")


def _score_segment_vectors(
    *,
    cfg: dict[str, Any],
    prompt: Any,
    final_audio: Any,
    intermediates: dict[float, Any],
    sample_rate: int,
    reward_stack: dict[str, Any],
    segments: list[Any],
) -> tuple[list[dict[str, Any]], list[float]]:
    from scripts.phase_b3_credit_unit_comparison import _crop_audio, _score_segment_reward

    rows: list[dict[str, Any]] = []
    all_deltas: list[float] = []
    for item in _axis_sigma_items(cfg):
        sigma = item["sigma"]
        reward_axis_id = item["reward_axis_id"]
        reward_obj = reward_stack[reward_axis_id]
        interm = intermediates[sigma]
        deltas: list[float] = []
        for seg in segments:
            final_crop = _crop_audio(final_audio, sample_rate, seg.start_s, seg.end_s)
            interm_crop = _crop_audio(interm, sample_rate, seg.start_s, seg.end_s)
            final_score = _score_segment_reward(reward_obj, final_crop, sample_rate, prompt)
            interm_score = _score_segment_reward(reward_obj, interm_crop, sample_rate, prompt)
            if final_score is None or interm_score is None:
                continue
            delta = float(interm_score - final_score)
            deltas.append(delta)
            all_deltas.append(delta)
        rows.append(
            {
                "gating_axis": item["gating_axis"],
                "reward_axis_id": reward_axis_id,
                "sigma": sigma,
                "n_segments_scored": len(deltas),
                "delta_min": min(deltas) if deltas else None,
                "delta_max": max(deltas) if deltas else None,
                "delta_mean": sum(deltas) / len(deltas) if deltas else None,
            }
        )
    return rows, all_deltas


def run_smoke(cfg: dict[str, Any], *, output_dir: Path, backend: str) -> int:
    import torch

    t0 = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "smoke_log.jsonl"
    result_path = output_dir / "smoke_results.json"
    ckpt_path = output_dir / "smoke_checkpoint.pt"

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the Phase C GPU smoke")
    device = torch.device("cuda")
    torch.cuda.reset_peak_memory_stats(device)

    prompts_by_id = _load_prompts_by_id(REPO_ROOT / cfg["scope"]["prompt_source"])
    prompt_ids = cfg["smoke"]["prompt_ids"][: int(cfg["smoke"]["max_prompts_allowed"])]
    if len(prompt_ids) < 2 or len(prompt_ids) > 4:
        raise RuntimeError(f"smoke prompt count must be 2-4, got {len(prompt_ids)}")
    missing = [pid for pid in prompt_ids if pid not in prompts_by_id]
    if missing:
        raise RuntimeError(f"smoke prompt IDs missing from dev split: {missing}")
    prompts = [_prompt_from_row(prompts_by_id[pid]) for pid in prompt_ids]

    sampler = cfg["sampler"]
    sigma_bindings = {
        float(x["target"]): x for x in cfg["sigma_policy"]["downstream_checkpoints"]
    }
    sigma_targets = list(sigma_bindings)

    before_gpu = _nvidia_snapshot()
    records: list[dict[str, Any]] = []
    all_reward_deltas: list[float] = []

    if backend != "real":
        raise RuntimeError("Only backend=real is authorized for the PI smoke")

    from mprm.common.seeding import seed_everything
    from mprm.inference.ace_step import AceStepModel

    method_name = cfg.get("method", {}).get("name", "M-PRM")
    credit_name = cfg["credit_unit"]["primary"]["name"]
    print("[phase-c-smoke] loading ACE-Step model", flush=True)
    model = AceStepModel()
    print("[phase-c-smoke] loading H2-allowed reward stack", flush=True)
    reward_stack = _load_reward_stack_for_config(cfg)
    print(f"[phase-c-smoke] loading credit unit {credit_name}", flush=True)
    credit_unit = _load_credit_unit_for_config(cfg)

    with log_path.open("w", encoding="utf-8") as log_fp:
        for p_idx, prompt in enumerate(prompts):
            seed = 20260523 + p_idx
            seed_everything(seed)
            print(f"[phase-c-smoke] prompt {p_idx + 1}/{len(prompts)} {prompt.prompt_id}", flush=True)
            sample_extras = {
                "cfg_type": sampler["cfg_type"],
                "use_erg_tag": sampler["use_erg_tag"],
                "use_erg_lyric": sampler["use_erg_lyric"],
                "use_erg_diffusion": sampler["use_erg_diffusion"],
                "guidance_interval": sampler["guidance_interval"],
            }
            sample_start = time.time()
            res = model.sample(
                prompt,
                seed=seed,
                cfg_scale=float(sampler["guidance_scale"]),
                steps=int(sampler["infer_step"]),
                return_trajectory=True,
                extras=sample_extras,
            )
            traj = res.trajectory or []
            traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
            traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
            cfg_flags = (res.extras or {}).get("trajectory_cfg_active", [])
            if not traj or not traj_sigmas or not traj_vs:
                raise RuntimeError("trajectory capture missing latents/sigmas/model outputs")

            intermediates: dict[float, Any] = {}
            actual_bindings: dict[str, Any] = {}
            for sigma in sigma_targets:
                k = _pick_sigma_index(sigma, traj_sigmas)
                expected = sigma_bindings[sigma]
                actual_sigma = float(traj_sigmas[k])
                if abs(actual_sigma - float(expected["scheduler_sigma_actual"])) > 1e-6:
                    raise RuntimeError(
                        f"sigma drift at target {sigma}: {actual_sigma} != {expected['scheduler_sigma_actual']}"
                    )
                if int(k) != int(expected["step_index"]):
                    raise RuntimeError(f"step drift at target {sigma}: {k} != {expected['step_index']}")
                if bool(cfg_flags[k]) != bool(expected["cfg_active"]):
                    raise RuntimeError(f"cfg_active drift at target {sigma}")
                z0 = traj[k].to(torch.float32) - actual_sigma * traj_vs[k].to(torch.float32)
                intermediates[sigma] = model.decode(z0)
                actual_bindings[str(sigma)] = {
                    "step_index": int(k),
                    "sigma_actual": actual_sigma,
                    "cfg_active": bool(cfg_flags[k]),
                }

            seg_out = credit_unit.segment(res.waveform, res.sample_rate, prompt, seed=seed)
            if not seg_out.applicable or len(seg_out.segments) < 2:
                raise RuntimeError(f"{credit_name} segmentation produced {len(seg_out.segments)} segments")
            reward_rows, deltas = _score_segment_vectors(
                cfg=cfg,
                prompt=prompt,
                final_audio=res.waveform,
                intermediates=intermediates,
                sample_rate=res.sample_rate,
                reward_stack=reward_stack,
                segments=seg_out.segments,
            )
            if not deltas:
                raise RuntimeError(f"no finite reward deltas for {prompt.prompt_id}")
            all_reward_deltas.extend(deltas)

            rec = {
                "prompt_id": prompt.prompt_id,
                "seed": seed,
                "duration_actual_s": float(res.waveform.shape[-1]) / float(res.sample_rate),
                "sample_rate": int(res.sample_rate),
                "sample_elapsed_seconds": time.time() - sample_start,
                "trajectory_steps": len(traj),
                "sigma_bindings": actual_bindings,
                "credit_unit": credit_name,
                "n_segments": len(seg_out.segments),
                "segments": [
                    {"start_s": s.start_s, "end_s": s.end_s, "label": s.label}
                    for s in seg_out.segments
                ],
                "reward_rows": reward_rows,
            }
            records.append(rec)
            log_fp.write(json.dumps({"event": "prompt_done", **rec}) + "\n")
            log_fp.flush()

    reward_tensor = torch.tensor(all_reward_deltas, device=device, dtype=torch.float32)
    rewards_finite = bool(torch.isfinite(reward_tensor).all().item())
    if not rewards_finite:
        raise RuntimeError("reward tensor contains NaN/Inf")

    alpha = float(cfg["reward_policy"]["cvar"]["alpha"])
    beta = float(cfg["reward_policy"]["cvar"]["beta"])
    cvar_value = _cvar_lower_tail(reward_tensor, alpha=alpha, beta=beta)

    policy_scale = torch.nn.Parameter(torch.tensor([0.25], device=device))
    optimizer = torch.optim.AdamW([policy_scale], lr=1.0e-2)
    target = cvar_value.detach().clamp(min=-1.0, max=1.0)
    loss = (policy_scale.squeeze() - target).pow(2) + 1.0e-3 * reward_tensor.pow(2).mean()
    if not bool(torch.isfinite(loss).item()):
        raise RuntimeError("loss is NaN/Inf")
    optimizer.zero_grad()
    loss.backward()
    grad_norm = float(policy_scale.grad.detach().abs().sum().item())
    if grad_norm <= 0.0:
        raise RuntimeError("gradient norm is zero")
    before_value = float(policy_scale.detach().cpu().item())
    optimizer.step()
    after_value = float(policy_scale.detach().cpu().item())
    if before_value == after_value:
        raise RuntimeError("optimizer step did not update policy_scale")

    torch.save(
        {
            "schema_version": "phase_c_m_prm_smoke_checkpoint_v1",
            "policy_scale": policy_scale.detach().cpu(),
            "optimizer": optimizer.state_dict(),
            "loss": float(loss.detach().cpu().item()),
            "cvar_value": float(cvar_value.detach().cpu().item()),
            "n_reward_deltas": int(reward_tensor.numel()),
        },
        ckpt_path,
    )
    resume_ok = False
    if cfg["smoke"].get("resume_check", True):
        loaded = torch.load(ckpt_path, map_location="cpu")
        resume_ok = "policy_scale" in loaded and "optimizer" in loaded
    if not resume_ok:
        raise RuntimeError("checkpoint resume check failed")

    torch.cuda.synchronize(device)
    elapsed = time.time() - t0
    after_gpu = _nvidia_snapshot()
    max_mem_mb = int(torch.cuda.max_memory_allocated(device) / (1024 * 1024))
    gpu_observed = max_mem_mb > 0
    result = {
        "schema_version": "phase_c_m_prm_smoke_result_v1",
        "status": "PASS",
        "backend": backend,
        "method": cfg.get("method", {}).get("name"),
        "credit_unit": cfg["credit_unit"]["primary"]["name"],
        "config_path": cfg.get("_config_path_for_report", "unknown"),
        "output_dir": str(output_dir),
        "elapsed_seconds": elapsed,
        "gpu_hours_consumed": elapsed / 3600.0,
        "prompts": prompt_ids,
        "n_reward_deltas": int(reward_tensor.numel()),
        "reward_tensor_finite": rewards_finite,
        "loss": float(loss.detach().cpu().item()),
        "loss_finite": bool(math.isfinite(float(loss.detach().cpu().item()))),
        "grad_norm": grad_norm,
        "optimizer_step_changed_policy_scale": before_value != after_value,
        "checkpoint_path": str(ckpt_path),
        "checkpoint_resume_ok": resume_ok,
        "log_path": str(log_path),
        "log_written": log_path.exists() and log_path.stat().st_size > 0,
        "gpu_observed": gpu_observed,
        "cuda_max_memory_allocated_mb": max_mem_mb,
        "nvidia_smi_before": before_gpu,
        "nvidia_smi_after": after_gpu,
        "records": records,
        "no_formal_result_claim": True,
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary_path = output_dir / "smoke_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                f"# Phase C {method_name} Smoke Summary",
                "",
                "- status: PASS",
                f"- credit_unit: {credit_name}",
                f"- prompts: {', '.join(prompt_ids)}",
                f"- elapsed_seconds: {elapsed:.1f}",
                f"- gpu_hours_consumed: {elapsed / 3600.0:.4f}",
                f"- reward_deltas: {int(reward_tensor.numel())}",
                f"- loss: {float(loss.detach().cpu().item()):.6f}",
                f"- grad_norm: {grad_norm:.6f}",
                f"- checkpoint: `{ckpt_path}`",
                f"- log: `{log_path}`",
                "- formal_result_claim: none",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"[phase-c-smoke] PASS wrote {result_path} and {summary_path}", flush=True)
    return 0


def write_firstwave_stop_report(
    cfg: dict[str, Any],
    *,
    output_dir: Path,
    config_path: Path,
    command: str,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    status = cfg.get("implementation_status", {})
    reason = status.get("production_weight_update_blocker", "production trainer not ready")
    gpu_snapshot = _nvidia_snapshot()
    report = {
        "schema_version": "phase_c_m_prm_firstwave_stop_v1",
        "status": "STOPPED_BEFORE_FORMAL_TRAINING",
        "method": cfg.get("method", {}).get("name"),
        "credit_unit": cfg["credit_unit"]["primary"]["name"],
        "reason": reason,
        "config_path": str(config_path),
        "config_sha256": _sha256(config_path),
        "formal_launch_command": command,
        "gpu_hours_consumed": 0.0,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
        "m_section_primary_training_launched": False,
        "gate_v1_untouched_by_runner": True,
        "nvidia_smi_snapshot": gpu_snapshot,
    }
    json_path = output_dir / "FIRSTWAVE_STOP_REPORT.json"
    md_path = output_dir / "FIRSTWAVE_STOP_REPORT.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Phase C {cfg.get('method', {}).get('name', 'M-PRM')} First-Wave Stop Report",
                "",
                "- status: STOPPED_BEFORE_FORMAL_TRAINING",
                f"- reason: {reason}",
                f"- config: `{config_path}`",
                "- gpu_hours_consumed: 0.0",
                "- held_out_launched: false",
                "- phase_d_launched: false",
                "- human_eval_launched: false",
                "- m_section_primary_training_launched: false",
                "",
                "## Formal Launch Command",
                "",
                "```bash",
                command,
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"[phase-c-firstwave] STOP wrote {json_path} and {md_path}", flush=True)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/runs/phase_c_m_fixedwin_firstwave.yaml")
    parser.add_argument("--mode", choices=["preflight", "smoke", "firstwave"], required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--backend", choices=["real"], default="real")
    parser.add_argument("--pi-approved-launch", action="store_true")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-total", type=int, default=1)
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = _load_yaml(config_path)
    cfg["_config_path_for_report"] = str(config_path)
    fails = _validate_config(cfg, require_pi=args.pi_approved_launch)
    if not args.pi_approved_launch:
        fails.append("--pi-approved-launch is required")
    if args.mode in {"smoke", "firstwave"} and fails:
        print("[phase-c] CONFIG FAIL", flush=True)
        for fail in fails:
            print(f"  - {fail}", flush=True)
        return 2
    if args.mode == "preflight":
        if fails:
            print("[phase-c] PREFLIGHT FAIL", flush=True)
            for fail in fails:
                print(f"  - {fail}", flush=True)
            return 2
        print("[phase-c] PREFLIGHT PASS", flush=True)
        return 0

    if args.mode == "smoke":
        out = Path(args.output_dir or cfg["smoke"]["output_dir"])
        return run_smoke(cfg, output_dir=out, backend=args.backend)

    if args.mode == "firstwave":
        if args.shard_total < 1 or not (0 <= args.shard_index < args.shard_total):
            print("[phase-c-firstwave] invalid shard args", flush=True)
            return 2
        out = Path(args.output_dir or cfg["firstwave"]["output_dir"])
        command = (
            f"python scripts/phase_c_m_fixedwin_prm.py --config {config_path} "
            f"--mode firstwave --output-dir {out} --pi-approved-launch "
            f"--shard-index {args.shard_index} --shard-total {args.shard_total}"
        )
        status = cfg.get("implementation_status", {}).get("production_weight_update_status")
        if status != "ready":
            return write_firstwave_stop_report(
                cfg, output_dir=out, config_path=config_path, command=command
            )
        print("[phase-c-firstwave] production trainer marked ready, but runner implementation is not enabled in this checkout", flush=True)
        return 2

    raise AssertionError(args.mode)


if __name__ == "__main__":
    sys.exit(main())
