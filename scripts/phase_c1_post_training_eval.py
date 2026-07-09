"""Read-only Phase C1 post-training evaluator.

This script loads completed C1 checkpoints into memory, samples dev prompts, and
scores them with the existing Phase C1 reward stack. It never writes to the
formal C1 training run directory and never calls the GRPO optimizer update path.
"""
from __future__ import annotations

import argparse
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

METHODS = ("r8a", "r8b", "m_fixedwin", "m_section")
SCHEMA_VERSIONS = {
    "phase_c1_post_training_eval_review_v1",
    "phase_c1_post_training_eval_full_review_v1",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML root is not an object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _finite(name: str, value: Any) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise RuntimeError(f"{name} is not finite: {value!r}")
    return out


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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


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
    if data.get("source_split") != "configs/prompts/dev.jsonl":
        raise RuntimeError("formal prompt manifest source_split must be configs/prompts/dev.jsonl")
    if data.get("pi_approved") is not True:
        raise RuntimeError("formal prompt manifest is not PI-approved")
    prompt_ids = data.get("formal_prompt_ids")
    if not isinstance(prompt_ids, list) or not all(isinstance(x, str) for x in prompt_ids):
        raise RuntimeError("formal_prompt_ids must be a list of strings")
    return prompt_ids


def _load_prompts(eval_cfg: dict[str, Any], prompt_ids: list[str]) -> list[Any]:
    rows = _load_prompts_by_id(REPO_ROOT / eval_cfg["scope"]["prompt_source"])
    missing = [pid for pid in prompt_ids if pid not in rows]
    if missing:
        raise RuntimeError(f"prompt IDs missing from dev split: {missing[:8]}")
    return [_prompt_from_row(rows[pid]) for pid in prompt_ids]


def _validate_eval_config(eval_cfg: dict[str, Any], firstwave_cfg: dict[str, Any]) -> None:
    if eval_cfg.get("schema_version") not in SCHEMA_VERSIONS:
        raise RuntimeError(f"schema_version must be one of {sorted(SCHEMA_VERSIONS)}")
    if eval_cfg.get("status") != "review_ready":
        raise RuntimeError("eval config status must be review_ready")
    scope = eval_cfg.get("scope", {})
    if scope.get("split") != "dev" or scope.get("prompt_source") != "configs/prompts/dev.jsonl":
        raise RuntimeError("post-training eval must remain dev split with configs/prompts/dev.jsonl")
    for key in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
        if scope.get(key) is not False:
            raise RuntimeError(f"scope.{key} must be false")
    safety = eval_cfg.get("safety", {})
    if safety.get("read_only_checkpoint_eval") is not True:
        raise RuntimeError("read_only_checkpoint_eval must be true")
    for key in ("no_training", "no_optimizer_step", "no_adapter_update"):
        if safety.get(key) is not True:
            raise RuntimeError(f"safety.{key} must be true")
    if set(eval_cfg.get("methods", {})) != set(METHODS):
        raise RuntimeError(f"eval config must list exactly {METHODS}")
    if eval_cfg["sampler"] != {
        "source": "configs/runs/phase_c1_firstwave.yaml sampler",
        "cfg_type": firstwave_cfg["sampler"]["cfg_type"],
        "use_erg_tag": firstwave_cfg["sampler"]["use_erg_tag"],
        "use_erg_lyric": firstwave_cfg["sampler"]["use_erg_lyric"],
        "use_erg_diffusion": firstwave_cfg["sampler"]["use_erg_diffusion"],
        "guidance_interval": firstwave_cfg["sampler"]["guidance_interval"],
        "guidance_scale": firstwave_cfg["sampler"]["guidance_scale"],
        "terminal_infer_step": firstwave_cfg["sampler"]["terminal_infer_step"],
        "process_infer_step": firstwave_cfg["sampler"]["process_infer_step"],
        "scheduler_shift": firstwave_cfg["sampler"]["scheduler_shift"],
        "duration_target": firstwave_cfg["sampler"]["duration_target"],
    }:
        raise RuntimeError("eval sampler block must mirror firstwave sampler block")
    if eval_cfg["sigma_policy"]["downstream_checkpoints"] != firstwave_cfg["sigma_policy"]["downstream_checkpoints"]:
        raise RuntimeError("eval sigma_policy must mirror firstwave sigma_policy")
    if eval_cfg["process_reward"]["h2_allowed_axis_sigma_pairs"] != firstwave_cfg["process_reward"]["h2_allowed_axis_sigma_pairs"]:
        raise RuntimeError("eval process_reward axes must mirror firstwave process_reward axes")
    for reward_block in ("process_reward", "terminal_reward"):
        if reward_block in eval_cfg:
            eval_reward = {
                k: v for k, v in eval_cfg[reward_block].items()
                if k != "source"
            }
            if eval_reward != firstwave_cfg[reward_block]:
                raise RuntimeError(f"eval {reward_block} block must mirror firstwave {reward_block} block")
    for method, spec in eval_cfg["methods"].items():
        firstwave_spec = firstwave_cfg["methods"][method]
        for key in ("method_id", "display_name", "reward_mode", "role"):
            if spec.get(key) != firstwave_spec.get(key):
                raise RuntimeError(f"{method} {key} must mirror firstwave methods block")
        if firstwave_spec["reward_mode"] == "process" and spec.get("credit_unit") != firstwave_spec.get("credit_unit"):
            raise RuntimeError(f"{method} credit_unit must mirror firstwave methods block")


def _select_prompt_ids(eval_cfg: dict[str, Any], *, mode: str, max_prompts: int | None) -> list[str]:
    if mode == "smoke":
        prompt_ids = list(eval_cfg["evaluation"]["smoke_prompt_ids"])
    else:
        prompt_ids = _load_formal_prompt_ids(REPO_ROOT / eval_cfg["scope"]["formal_prompt_ids_json"])
        prompt_ids = prompt_ids[: int(eval_cfg["evaluation"]["full_n_prompts"])]
    if max_prompts is not None:
        prompt_ids = prompt_ids[: int(max_prompts)]
    if not prompt_ids:
        raise RuntimeError("no prompts selected for eval")
    return prompt_ids


def _validate_method_ready(eval_cfg: dict[str, Any], method: str) -> tuple[Path, dict[str, Any]]:
    spec = eval_cfg["methods"][method]
    if spec.get("eval_enabled_now") is not True:
        raise RuntimeError(f"{method} is not enabled for eval now")
    if spec.get("reward_mode") not in {"process", "terminal"}:
        raise RuntimeError(f"{method} has unsupported reward_mode: {spec.get('reward_mode')}")
    checkpoint = REPO_ROOT / spec["checkpoint_path"]
    result_path = REPO_ROOT / spec["train_results_path"]
    if not checkpoint.exists():
        raise RuntimeError(f"{method} checkpoint missing: {checkpoint}")
    if not result_path.exists():
        raise RuntimeError(f"{method} train_results missing: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("status") != "PASS":
        raise RuntimeError(f"{method} train_results status is not PASS")
    if Path(result.get("checkpoint_path", "")) != Path(spec["checkpoint_path"]):
        raise RuntimeError(f"{method} train_results checkpoint_path mismatch")
    if result.get("method_id") != spec.get("method_id"):
        raise RuntimeError(f"{method} train_results method_id mismatch")
    if result.get("reward_mode") != spec.get("reward_mode"):
        raise RuntimeError(f"{method} train_results reward_mode mismatch")
    for key in (
        "held_out_launched",
        "phase_d_launched",
        "human_eval_launched",
        "reward_definitions_changed",
        "sigma_policy_changed",
        "prompt_splits_changed",
        "credit_unit_definitions_changed",
        "gate_v1_touched_by_runner",
    ):
        if result.get(key) is not False:
            raise RuntimeError(f"{method} train_results {key} must be false")
    return checkpoint, result


def _run_method_eval(
    *,
    eval_cfg: dict[str, Any],
    firstwave_cfg: dict[str, Any],
    method: str,
    prompts: list[Any],
    output_root: Path,
    mode: str,
    dtype: str,
) -> dict[str, Any]:
    import torch
    from mprm.common.seeding import seed_everything
    from mprm.inference.ace_step import AceStepModel
    from mprm.training.ace_lora_grpo import AceLoraGrpoBackend
    from scripts.phase_c1_grpo import (
        _backend_config,
        _load_process_context,
        _load_terminal_context,
        _sample_rollout,
        _sampler_extras,
        _score_process_sample,
        _score_terminal_group,
    )

    checkpoint, train_result = _validate_method_ready(eval_cfg, method)
    source_root = REPO_ROOT / eval_cfg["source_training_run"]["run_root"]
    method_out = output_root / method
    if _is_relative_to(method_out, source_root):
        raise RuntimeError(f"refusing to write eval output inside source run root: {method_out}")
    record_path = method_out / "eval_records.jsonl"
    if record_path.exists():
        raise RuntimeError(f"refusing to append to existing eval records: {record_path}")
    method_out.mkdir(parents=True, exist_ok=False)

    method_spec = firstwave_cfg["methods"][method]
    seed_everything(int(eval_cfg["evaluation"]["seed_base"]))
    before_gpu = _nvidia_snapshot()
    t0 = time.time()
    torch.cuda.reset_peak_memory_stats(torch.device("cuda"))

    model = AceStepModel(dtype=dtype)
    backend = AceLoraGrpoBackend(
        model,
        _backend_config(firstwave_cfg),
        output_dir=method_out / "backend_readonly",
        method_id=method_spec["method_id"],
        reward_mode=method_spec["reward_mode"],
        ledger_path=method_out / "backend_readonly_ledger.jsonl",
    )
    parameter_summary = backend.ensure_lora()
    load_payload = backend.load_checkpoint(checkpoint)
    loaded_adapter_digest = backend.adapter_digest()
    expected_digest = train_result.get("final_adapter_digest")
    if expected_digest and loaded_adapter_digest != expected_digest:
        raise RuntimeError(f"{method} loaded adapter digest mismatch")
    backend.cfg_scale = float(firstwave_cfg["sampler"]["guidance_scale"])
    reward_mode = method_spec["reward_mode"]
    if reward_mode == "terminal":
        reward_ctx = _load_terminal_context(method, firstwave_cfg)
        target_sigmas = None
        sigma_bindings = None
        infer_steps = int(firstwave_cfg["sampler"]["terminal_infer_step"])
        reward_key = "terminal_reward"
    elif reward_mode == "process":
        reward_ctx = _load_process_context(method, firstwave_cfg)
        target_sigmas = reward_ctx["target_sigmas"]
        sigma_bindings = reward_ctx["sigma_bindings"]
        infer_steps = int(firstwave_cfg["sampler"]["process_infer_step"])
        reward_key = "process_reward"
    else:
        raise RuntimeError(f"{method} unsupported reward mode: {reward_mode}")
    sampler_extras = _sampler_extras(firstwave_cfg)
    seed_base = int(eval_cfg["evaluation"]["seed_base"])
    samples_per_prompt = int(eval_cfg["evaluation"].get("samples_per_prompt", 1))
    if samples_per_prompt < 1:
        raise RuntimeError("samples_per_prompt must be >= 1")

    records: list[dict[str, Any]] = []
    for idx, prompt in enumerate(prompts):
        samples: list[dict[str, Any]] = []
        for sample_idx in range(samples_per_prompt):
            seed = seed_base * 100_000 + idx * samples_per_prompt + sample_idx
            with torch.no_grad():
                rollout, meta, res = _sample_rollout(
                    model=model,
                    prompt=prompt,
                    seed=seed,
                    group_id=f"{method}:posttrain:{prompt.prompt_id}",
                    cfg_scale=float(firstwave_cfg["sampler"]["guidance_scale"]),
                    infer_steps=infer_steps,
                    extras=sampler_extras,
                    target_sigmas=target_sigmas,
                    sigma_bindings=sigma_bindings,
                )
            samples.append({"rollout": rollout, "meta": meta, "res": res, "sample_index": sample_idx})

        with torch.no_grad():
            if reward_mode == "terminal":
                reports = _score_terminal_group(ctx=reward_ctx, prompt=prompt, samples=samples)
            else:
                reports = [
                    _score_process_sample(ctx=reward_ctx, prompt=prompt, sample=sample, model=model)
                    for sample in samples
                ]
        if len(reports) != len(samples):
            raise RuntimeError(f"{method} reward report count mismatch")
        for sample, report in zip(samples, reports):
            reward = _finite(reward_key, report[reward_key])
            meta = sample["meta"]
            row = {
                "event": "post_training_eval_sample",
                "mode": mode,
                "method": method,
                "method_id": method_spec["method_id"],
                "reward_mode": reward_mode,
                "prompt_id": prompt.prompt_id,
                "sample_index": sample["sample_index"],
                "seed": meta["seed"],
                "reward": reward,
                reward_key: reward,
                "duration_actual_s": meta.get("duration_actual_s"),
                "sample_rate": meta.get("sample_rate"),
                "selection": meta.get("selection"),
                "reward_report": report,
                "safety": {
                    "read_only_checkpoint_eval": True,
                    "training_launched": False,
                    "optimizer_step_called": False,
                    "held_out_launched": False,
                    "phase_d_launched": False,
                    "human_eval_launched": False,
                },
            }
            records.append(row)
            _append_jsonl(record_path, row)

    torch.cuda.synchronize()
    elapsed = time.time() - t0
    rewards = [float(r[reward_key]) for r in records]
    final_adapter_digest = backend.adapter_digest()
    if final_adapter_digest != loaded_adapter_digest:
        raise RuntimeError(f"{method} adapter digest changed during read-only eval")
    result = {
        "schema_version": "phase_c1_post_training_eval_result_v1",
        "status": "PASS",
        "mode": mode,
        "method": method,
        "method_id": method_spec["method_id"],
        "reward_mode": reward_mode,
        "checkpoint_path": str(checkpoint),
        "train_results_path": eval_cfg["methods"][method]["train_results_path"],
        "checkpoint_step": load_payload.get("step"),
        "n_prompts": len(prompts),
        "prompt_ids": [p.prompt_id for p in prompts],
        "samples_per_prompt": samples_per_prompt,
        "infer_steps": infer_steps,
        "sampler_extras": sampler_extras,
        "seed_base": seed_base,
        "elapsed_seconds": elapsed,
        "gpu_hours_consumed": elapsed / 3600.0,
        "reward_mean": sum(rewards) / len(rewards),
        "reward_min": min(rewards),
        "reward_max": max(rewards),
        f"{reward_key}_mean": sum(rewards) / len(rewards),
        f"{reward_key}_min": min(rewards),
        f"{reward_key}_max": max(rewards),
        "loaded_adapter_digest": loaded_adapter_digest,
        "final_adapter_digest": final_adapter_digest,
        "adapter_unchanged_during_eval": final_adapter_digest == loaded_adapter_digest,
        "base_parameters_frozen": parameter_summary["base_parameters_frozen"],
        "record_path": str(record_path),
        "cuda_max_memory_allocated_mb": int(torch.cuda.max_memory_allocated(torch.device("cuda")) / (1024 * 1024)),
        "nvidia_smi_before": before_gpu,
        "nvidia_smi_after": _nvidia_snapshot(),
        "reward_definitions_changed": False,
        "sigma_policy_changed": False,
        "prompt_splits_changed": False,
        "credit_unit_definitions_changed": False,
        "gate_v1_touched_by_runner": False,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
        "training_launched": False,
        "optimizer_step_called": False,
    }
    _write_json(method_out / "eval_results.json", result)
    lines = [
        f"# Phase C1 Post-Training Eval: {method}",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        f"- status: `{result['status']}`",
        f"- mode: `{mode}`",
        f"- checkpoint: `{checkpoint}`",
        f"- prompts: {len(prompts)}",
        f"- reward mode: `{reward_mode}`",
        f"- {reward_key} mean: {result[f'{reward_key}_mean']:.6g}",
        f"- adapter unchanged during eval: {result['adapter_unchanged_during_eval']}",
        f"- training launched: {result['training_launched']}",
        f"- held_out_launched: {result['held_out_launched']}",
        f"- phase_d_launched: {result['phase_d_launched']}",
        f"- human_eval_launched: {result['human_eval_launched']}",
    ]
    (method_out / "eval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mode", choices=["smoke", "eval"], required=True)
    parser.add_argument("--methods", nargs="+", default=["m_fixedwin", "m_section"])
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--max-prompts", type=int, default=None)
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    args = parser.parse_args()

    eval_cfg = _load_yaml(args.config)
    firstwave_cfg = _load_yaml(REPO_ROOT / eval_cfg["source_training_run"]["training_config"])
    from scripts.phase_c1_grpo import _validate_bundle

    _validate_bundle(firstwave_cfg)
    _validate_eval_config(eval_cfg, firstwave_cfg)
    unknown = [m for m in args.methods if m not in METHODS]
    if unknown:
        raise RuntimeError(f"unknown methods: {unknown}")
    disallowed = [m for m in args.methods if m in eval_cfg["evaluation"]["pending_methods_not_to_eval"]]
    if disallowed:
        raise RuntimeError(f"pending methods must not be evaluated now: {disallowed}")

    prompt_ids = _select_prompt_ids(eval_cfg, mode=args.mode, max_prompts=args.max_prompts)
    prompts = _load_prompts(eval_cfg, prompt_ids)
    output_root = args.output_root or Path(
        eval_cfg["evaluation"]["smoke_output_root"]
        if args.mode == "smoke"
        else eval_cfg["evaluation"]["completed_methods_output_root"]
    )
    output_root = output_root.resolve()
    source_root = (REPO_ROOT / eval_cfg["source_training_run"]["run_root"]).resolve()
    if _is_relative_to(output_root, source_root):
        raise RuntimeError(f"refusing to write eval output inside source run root: {output_root}")
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {}
    for method in args.methods:
        print(f"[phase-c1-post-eval] {args.mode} {method}", flush=True)
        results[method] = _run_method_eval(
            eval_cfg=eval_cfg,
            firstwave_cfg=firstwave_cfg,
            method=method,
            prompts=prompts,
            output_root=output_root,
            mode=args.mode,
            dtype=args.dtype,
        )
    payload = {
        "schema_version": "phase_c1_post_training_eval_bundle_result_v1",
        "status": "PASS",
        "mode": args.mode,
        "methods": list(results),
        "config": str(args.config),
        "output_root": str(output_root),
        "prompt_ids": prompt_ids,
        "results": results,
        "generated_at_utc": _now_utc(),
    }
    _write_json(output_root / "all_eval_results.json", payload)
    print(json.dumps({"status": "PASS", "mode": args.mode, "methods": list(results), "output_root": str(output_root)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
