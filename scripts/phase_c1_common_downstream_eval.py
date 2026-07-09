"""Read-only Phase C1 common downstream evaluator.

This runner samples Base plus C1 checkpoints with one shared sampler and scores
all generated audio with one gate_v2.draft robust-LCB metric policy. It does not
train, update adapters, overwrite checkpoints, activate gate_v2, or touch gate_v1.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

SCHEMA_VERSION = "phase_c1_common_downstream_eval_review_v1"
METHODS = ("base", "r8a", "r8b", "m_fixedwin", "m_section")


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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _finite(name: str, value: Any) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise RuntimeError(f"{name} is not finite: {value!r}")
    return out


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


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


def _select_prompt_ids(cfg: dict[str, Any], *, mode: str, max_prompts: int | None) -> list[str]:
    if mode == "smoke":
        prompt_ids = list(cfg["evaluation"]["smoke_prompt_ids"])
    else:
        prompt_ids = _load_formal_prompt_ids(REPO_ROOT / cfg["scope"]["formal_prompt_ids_json"])
        prompt_ids = prompt_ids[: int(cfg["evaluation"]["full_n_prompts"])]
    if max_prompts is not None:
        prompt_ids = prompt_ids[: int(max_prompts)]
    if not prompt_ids:
        raise RuntimeError("no prompts selected")
    return prompt_ids


def _load_prompts(cfg: dict[str, Any], prompt_ids: list[str]) -> list[Any]:
    rows = _load_prompts_by_id(REPO_ROOT / cfg["scope"]["prompt_source"])
    missing = [pid for pid in prompt_ids if pid not in rows]
    if missing:
        raise RuntimeError(f"prompt IDs missing from dev split: {missing[:8]}")
    return [_prompt_from_row(rows[pid]) for pid in prompt_ids]


def _validate_common_config(cfg: dict[str, Any], firstwave: dict[str, Any]) -> tuple[dict[str, Any], str]:
    from scripts.launch_baseline import load_gate_eval_policy

    if cfg.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"schema_version must be {SCHEMA_VERSION}")
    if cfg.get("status") != "review_ready":
        raise RuntimeError("config status must be review_ready")
    scope = cfg.get("scope", {})
    if scope.get("split") != "dev" or scope.get("prompt_source") != "configs/prompts/dev.jsonl":
        raise RuntimeError("common eval must stay on dev split")
    for key in ("held_out_launched", "phase_d_launched", "human_eval_launched"):
        if scope.get(key) is not False:
            raise RuntimeError(f"scope.{key} must be false")
    safety = cfg.get("safety", {})
    for key in ("read_only_checkpoint_eval", "no_training", "no_optimizer_step", "no_adapter_update"):
        if safety.get(key) is not True:
            raise RuntimeError(f"safety.{key} must be true")
    for group in ("forbidden_launches", "forbidden_changes"):
        for key, value in safety.get(group, {}).items():
            if value is not False:
                raise RuntimeError(f"safety.{group}.{key} must be false")

    sampler = cfg["common_sampler"]
    expected_sampler = {
        "source": "configs/runs/phase_c1_firstwave.yaml sampler",
        "choice": "formal_phase_b_c_30_step_binding",
        "rationale": sampler["rationale"],
        "cfg_type": firstwave["sampler"]["cfg_type"],
        "use_erg_tag": firstwave["sampler"]["use_erg_tag"],
        "use_erg_lyric": firstwave["sampler"]["use_erg_lyric"],
        "use_erg_diffusion": firstwave["sampler"]["use_erg_diffusion"],
        "guidance_interval": firstwave["sampler"]["guidance_interval"],
        "guidance_scale": firstwave["sampler"]["guidance_scale"],
        "infer_step": firstwave["sampler"]["process_infer_step"],
        "scheduler_shift": firstwave["sampler"]["scheduler_shift"],
        "duration_target": firstwave["sampler"]["duration_target"],
    }
    if sampler != expected_sampler:
        raise RuntimeError("common_sampler must mirror firstwave 30-step sampler binding")

    metric = cfg["common_metric_policy"]
    policy_path = REPO_ROOT / metric["source"]
    if policy_path.name != "gate_v2.yaml.draft" or not policy_path.exists():
        raise RuntimeError("common eval may only read configs/eval/gate_v2.yaml.draft")
    policy, policy_hash = load_gate_eval_policy(policy_path)
    if policy.get("name") != metric["expected_name"] or str(policy.get("version")) != str(metric["expected_version"]):
        raise RuntimeError("gate_v2 draft policy name/version mismatch")
    if policy_hash != metric["expected_policy_hash"]:
        raise RuntimeError("gate_v2 draft policy hash mismatch")
    for key in ("beta_robust", "lambda_probe", "perturbations", "reward_axes"):
        if policy[key] != metric[key]:
            raise RuntimeError(f"common metric policy {key} does not match gate_v2 draft")
    if (REPO_ROOT / "configs/eval/gate_v2.yaml").exists():
        raise RuntimeError("configs/eval/gate_v2.yaml exists; draft appears activated")

    first_methods = firstwave["methods"]
    for method in ("r8a", "r8b", "m_fixedwin", "m_section"):
        spec = cfg["checkpoint_requests"][method]
        first_spec = first_methods[method]
        for key in ("method_id", "display_name", "reward_mode"):
            if spec.get(key) != first_spec.get(key):
                raise RuntimeError(f"{method} {key} must mirror firstwave config")
        if method.startswith("m_") and spec.get("credit_unit") != first_spec.get("credit_unit"):
            raise RuntimeError(f"{method} credit_unit must mirror firstwave config")
        train_results = REPO_ROOT / spec["train_results_path"]
        if not train_results.exists():
            raise RuntimeError(f"{method} train_results missing: {train_results}")
        tr = json.loads(train_results.read_text(encoding="utf-8"))
        if tr.get("status") != "PASS":
            raise RuntimeError(f"{method} train_results status is not PASS")
        for ckpt_label, ckpt in spec["checkpoints"].items():
            path = REPO_ROOT / ckpt["checkpoint_path"]
            if not path.exists():
                raise RuntimeError(f"{method} {ckpt_label} checkpoint missing: {path}")
            if ckpt_label == "step250_nearest200" and int(ckpt["actual_step"]) != 200:
                raise RuntimeError("step250 nearest checkpoint must be explicitly labeled actual_step=200")
    return policy, policy_hash


def _sampler_extras(firstwave: dict[str, Any]) -> dict[str, Any]:
    sampler = firstwave["sampler"]
    return {
        "cfg_type": sampler["cfg_type"],
        "use_erg_tag": sampler["use_erg_tag"],
        "use_erg_lyric": sampler["use_erg_lyric"],
        "use_erg_diffusion": sampler["use_erg_diffusion"],
        "guidance_interval": sampler["guidance_interval"],
    }


def _reward_cfg_from_common(cfg: dict[str, Any]) -> SimpleNamespace:
    variants = cfg["reward_model_variants"]
    return SimpleNamespace(
        use_clap=True,
        clap_variant=variants["clap_variant"],
        use_audiobox=True,
        audiobox_variant=variants["audiobox_variant"],
        use_whisper=True,
        whisper_variant=variants["whisper_variant"],
        use_mert=True,
        mert_variant=variants["mert_variant"],
    )


def _build_common_reward_context(cfg: dict[str, Any], policy: dict[str, Any], policy_hash: str) -> dict[str, Any]:
    from mprm.rewards.clap import ClapReward
    from mprm.rewards.perturbations import perturbation_set
    from mprm.rewards.probes import probe_floors
    from scripts.launch_baseline import _assert_reward_axes_match_policy, _build_reward_models

    reward_models = _build_reward_models(_reward_cfg_from_common(cfg))
    _assert_reward_axes_match_policy(reward_models, policy)
    return {
        "policy": policy,
        "policy_hash": policy_hash,
        "reward_models": reward_models,
        "perturbations": perturbation_set(list(policy["perturbations"])),
        "lambda_probe": dict(policy["lambda_probe"]),
        "beta_robust": float(policy["beta_robust"]),
        "probe_floors": probe_floors(),
        "clap": next((rm for rm in reward_models if isinstance(rm, ClapReward)), None),
    }


def _build_process_contexts(firstwave: dict[str, Any]) -> dict[str, Any]:
    from scripts.phase_c1_grpo import _load_process_context

    return {
        "fixedwin_process": _load_process_context("m_fixedwin", firstwave),
        "section_process": _load_process_context("m_section", firstwave),
    }


def _target_sigmas(firstwave: dict[str, Any]) -> tuple[list[float], dict[float, dict[str, Any]]]:
    bindings = {
        float(x["target"]): x for x in firstwave["sigma_policy"]["downstream_checkpoints"]
    }
    return list(bindings), bindings


def _select_targets(
    cfg: dict[str, Any],
    *,
    mode: str,
    methods: list[str] | None,
    checkpoint_set: str,
    checkpoint_labels: list[str] | None,
) -> list[dict[str, Any]]:
    if methods is None:
        methods = list(cfg["evaluation"]["smoke_methods"] if mode == "smoke" else METHODS)
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        raise RuntimeError(f"unknown methods: {unknown}")
    if checkpoint_labels is None:
        if mode == "smoke":
            checkpoint_labels = list(cfg["evaluation"]["smoke_checkpoint_labels"])
        else:
            checkpoint_labels = list(cfg["evaluation"]["checkpoint_sets"][checkpoint_set])
    targets: list[dict[str, Any]] = []
    for method in methods:
        spec = cfg["checkpoint_requests"][method]
        if method == "base":
            targets.append(
                {
                    "target_id": "base__base",
                    "method": "base",
                    "method_id": spec["method_id"],
                    "display_name": spec["display_name"],
                    "reward_mode": "reference",
                    "checkpoint_label": "base",
                    "requested_step": None,
                    "actual_step": None,
                    "checkpoint_path": None,
                    "selection_reason": "unadapted reference model",
                }
            )
            continue
        for label in checkpoint_labels:
            if label not in spec["checkpoints"]:
                raise RuntimeError(f"{method} has no checkpoint label {label}")
            ckpt = spec["checkpoints"][label]
            targets.append(
                {
                    "target_id": f"{method}__{label}",
                    "method": method,
                    "method_id": spec["method_id"],
                    "display_name": spec["display_name"],
                    "reward_mode": spec["reward_mode"],
                    "credit_unit": spec.get("credit_unit"),
                    "checkpoint_label": label,
                    "requested_step": ckpt.get("requested_step"),
                    "actual_step": ckpt.get("actual_step"),
                    "checkpoint_path": ckpt.get("checkpoint_path"),
                    "selection_reason": ckpt.get("selection_reason", "exact requested checkpoint"),
                    "train_results_path": spec.get("train_results_path"),
                }
            )
    return targets


def _score_common(
    *,
    ctx: dict[str, Any],
    prompt: Any,
    waveform: Any,
    sample_rate: int,
    base_reference: Any,
) -> dict[str, Any]:
    from mprm.rewards.probes import anti_hacking_probes
    from mprm.rewards.robust_lcb import robust_lcb

    probe = anti_hacking_probes(
        waveform,
        sample_rate,
        prompt,
        base_reference=base_reference,
        clap=ctx["clap"],
    )
    lcb = robust_lcb(
        waveform,
        sample_rate,
        prompt,
        reward_models=ctx["reward_models"],
        perturbations=ctx["perturbations"],
        probe_scores=probe,
        lambda_probe=ctx["lambda_probe"],
        probe_floors=ctx["probe_floors"],
        beta_robust=ctx["beta_robust"],
    )
    return {
        "common_robust_lcb": _finite("common_robust_lcb", lcb.value),
        "mean_cells": _finite("mean_cells", lcb.mean_cells),
        "std_cells": _finite("std_cells", lcb.std_cells),
        "probe_penalty": _finite("probe_penalty", lcb.probe_penalty),
        "probe_scores": {k: _finite(k, v) for k, v in probe.items()},
        "per_axis": {k: _finite(k, v) for k, v in lcb.per_axis.items()},
        "per_perturbation": {
            p: {axis: _finite(f"{p}.{axis}", value) for axis, value in axis_values.items()}
            for p, axis_values in lcb.per_perturbation.items()
        },
    }


def _seed_for(seed_base: int, prompt_index: int, sample_index: int = 0) -> int:
    return int(seed_base) * 100_000 + int(prompt_index) * 10 + int(sample_index)


def _make_model_and_backend(
    *,
    firstwave: dict[str, Any],
    target: dict[str, Any],
    output_root: Path,
    dtype: str,
):
    import torch
    from mprm.inference.ace_step import AceStepModel
    from mprm.training.ace_lora_grpo import AceLoraGrpoBackend
    from scripts.phase_c1_grpo import _backend_config

    model = AceStepModel(dtype=dtype)
    if target["method"] == "base":
        with torch.no_grad():
            model._ensure_loaded()
        return model, None, None, None

    backend = AceLoraGrpoBackend(
        model,
        _backend_config(firstwave),
        output_dir=output_root / "backend_readonly" / target["target_id"],
        method_id=target["method_id"],
        reward_mode=target["reward_mode"],
        ledger_path=output_root / "backend_readonly" / f"{target['target_id']}_ledger.jsonl",
    )
    parameter_summary = backend.ensure_lora()
    backend.cfg_scale = float(firstwave["sampler"]["guidance_scale"])
    load_payload = backend.load_checkpoint(REPO_ROOT / target["checkpoint_path"])
    loaded_digest = backend.adapter_digest()
    train_results = None
    if target.get("train_results_path"):
        train_results = json.loads((REPO_ROOT / target["train_results_path"]).read_text(encoding="utf-8"))
        if int(target.get("actual_step") or -1) == 1000:
            expected_digest = train_results.get("final_adapter_digest")
            if expected_digest and loaded_digest != expected_digest:
                raise RuntimeError(f"{target['target_id']} final adapter digest mismatch")
    return model, backend, parameter_summary, {"payload": load_payload, "digest": loaded_digest, "train_results": train_results}


def _sample_target(
    *,
    model: Any,
    prompt: Any,
    seed: int,
    target: dict[str, Any],
    firstwave: dict[str, Any],
    target_sigmas: list[float],
    sigma_bindings: dict[float, dict[str, Any]],
) -> tuple[dict[str, Any], Any]:
    from scripts.phase_c1_grpo import _sample_rollout

    rollout, meta, res = _sample_rollout(
        model=model,
        prompt=prompt,
        seed=seed,
        group_id=f"{target['target_id']}:{prompt.prompt_id}",
        cfg_scale=float(firstwave["sampler"]["guidance_scale"]),
        infer_steps=int(firstwave["sampler"]["process_infer_step"]),
        extras=_sampler_extras(firstwave),
        target_sigmas=target_sigmas,
        sigma_bindings=sigma_bindings,
    )
    return {"rollout": rollout, "meta": meta, "res": res, "sample_index": 0}, res


def _score_process_objectives(
    *,
    process_contexts: dict[str, Any],
    prompt: Any,
    sample: dict[str, Any],
    model: Any,
) -> dict[str, Any]:
    from scripts.phase_c1_grpo import _score_process_sample

    out: dict[str, Any] = {}
    for objective_name, ctx in process_contexts.items():
        report = _score_process_sample(ctx=ctx, prompt=prompt, sample=sample, model=model)
        out[objective_name] = {
            "process_reward": _finite(f"{objective_name}.process_reward", report["process_reward"]),
            "n_segments": int(report.get("n_segments", 0)),
            "n_reward_deltas": int(report.get("n_reward_deltas", 0)),
            "process_scalar": _finite(f"{objective_name}.process_scalar", report.get("process_scalar", report["process_reward"])),
            "reward_rows": report.get("reward_rows", []),
        }
    return out


def _stats(values: list[float]) -> dict[str, float | int | None]:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if not vals:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None, "median": None}
    return {
        "n": len(vals),
        "mean": sum(vals) / len(vals),
        "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
        "min": min(vals),
        "max": max(vals),
        "median": statistics.median(vals),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row_key(row: dict[str, Any]) -> tuple[str, str, int]:
    return (str(row["target_id"]), str(row["prompt_id"]), int(row.get("sample_index", 0)))


def _write_aggregate_outputs(
    *,
    output_root: Path,
    records: list[dict[str, Any]],
    result: dict[str, Any],
    per_prompt_already_written: bool = False,
) -> None:
    per_prompt_path = output_root / "per_prompt_common_eval.jsonl"
    if per_prompt_path.exists():
        if not per_prompt_already_written:
            raise RuntimeError(f"refusing to overwrite existing merged JSONL: {per_prompt_path}")
        existing_rows = _rows_from_jsonl(per_prompt_path)
        existing_keys = sorted(_row_key(row) for row in existing_rows)
        record_keys = sorted(_row_key(row) for row in records)
        if existing_keys != record_keys:
            raise RuntimeError(
                f"existing streamed JSONL does not match in-memory records: {per_prompt_path}"
            )
    else:
        for row in records:
            _append_jsonl(per_prompt_path, row)

    summary_rows, delta_vs_base, pair_rows, best = _summarize(records)
    summary_fields = [
        "target_id", "method", "method_id", "checkpoint_label", "requested_step",
        "actual_step", "n_prompts", "common_robust_lcb_mean",
        "common_robust_lcb_std", "common_robust_lcb_min",
        "common_robust_lcb_max", "common_robust_lcb_median", "mean_cells_mean",
        "std_cells_mean", "probe_penalty_mean",
    ]
    axis_fields = sorted({k for row in summary_rows for k in row if k.endswith("_mean") and k not in summary_fields})
    _write_csv(output_root / "method_by_checkpoint_summary.csv", summary_rows, summary_fields + axis_fields)

    delta_fields = [
        "target_id", "method", "method_id", "checkpoint_label", "requested_step",
        "actual_step", "n_paired", "delta_common_robust_lcb_mean",
        "delta_common_robust_lcb_std", "delta_common_robust_lcb_min",
        "delta_common_robust_lcb_max", "delta_common_robust_lcb_median",
    ]
    delta_axis_fields = sorted({k for row in delta_vs_base for k in row if k.startswith("delta_") and k.endswith("_mean") and k not in delta_fields})
    _write_csv(output_root / "paired_delta_vs_base.csv", delta_vs_base, delta_fields + delta_axis_fields)
    _write_csv(
        output_root / "paired_delta_method_vs_method.csv",
        pair_rows,
        [
            "checkpoint_label", "left_target_id", "right_target_id", "left_method",
            "right_method", "n_paired",
            "delta_common_robust_lcb_mean_left_minus_right",
            "delta_common_robust_lcb_std", "delta_common_robust_lcb_min",
            "delta_common_robust_lcb_max", "delta_common_robust_lcb_median",
        ],
    )
    result["summary"] = summary_rows
    result["paired_delta_vs_base"] = delta_vs_base
    result["paired_delta_method_vs_method"] = pair_rows
    result["best_checkpoint_by_method"] = best
    result["output_files"] = {
        "per_prompt_common_eval": str(per_prompt_path),
        "method_by_checkpoint_summary": str(output_root / "method_by_checkpoint_summary.csv"),
        "paired_delta_vs_base": str(output_root / "paired_delta_vs_base.csv"),
        "paired_delta_method_vs_method": str(output_root / "paired_delta_method_vs_method.csv"),
    }
    _write_json(output_root / "common_eval_results.json", result)


def _summarize(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        by_target.setdefault(row["target_id"], []).append(row)

    axis_names = sorted({axis for r in records for axis in r.get("per_axis", {})})
    summary_rows: list[dict[str, Any]] = []
    for target_id, rows in sorted(by_target.items()):
        first = rows[0]
        lcb_stats = _stats([r["common_robust_lcb"] for r in rows])
        item = {
            "target_id": target_id,
            "method": first["method"],
            "method_id": first["method_id"],
            "checkpoint_label": first["checkpoint_label"],
            "requested_step": first.get("requested_step"),
            "actual_step": first.get("actual_step"),
            "n_prompts": lcb_stats["n"],
            "common_robust_lcb_mean": lcb_stats["mean"],
            "common_robust_lcb_std": lcb_stats["std"],
            "common_robust_lcb_min": lcb_stats["min"],
            "common_robust_lcb_max": lcb_stats["max"],
            "common_robust_lcb_median": lcb_stats["median"],
            "mean_cells_mean": _stats([r["mean_cells"] for r in rows])["mean"],
            "std_cells_mean": _stats([r["std_cells"] for r in rows])["mean"],
            "probe_penalty_mean": _stats([r["probe_penalty"] for r in rows])["mean"],
        }
        for axis in axis_names:
            item[f"{axis}_mean"] = _stats([r["per_axis"].get(axis, math.nan) for r in rows])["mean"]
        for proc_key in ("fixedwin_process", "section_process"):
            vals = [
                r.get("process_objectives", {}).get(proc_key, {}).get("process_reward", math.nan)
                for r in rows
            ]
            item[f"{proc_key}_mean"] = _stats(vals)["mean"]
        summary_rows.append(item)

    base_by_prompt = {
        r["prompt_id"]: r for r in records if r["method"] == "base" and r["checkpoint_label"] == "base"
    }
    delta_vs_base: list[dict[str, Any]] = []
    for target_id, rows in sorted(by_target.items()):
        first = rows[0]
        if first["method"] == "base":
            continue
        deltas: list[float] = []
        axis_deltas: dict[str, list[float]] = {axis: [] for axis in axis_names}
        for row in rows:
            base = base_by_prompt.get(row["prompt_id"])
            if base is None:
                continue
            deltas.append(float(row["common_robust_lcb"]) - float(base["common_robust_lcb"]))
            for axis in axis_names:
                if axis in row.get("per_axis", {}) and axis in base.get("per_axis", {}):
                    axis_deltas[axis].append(float(row["per_axis"][axis]) - float(base["per_axis"][axis]))
        ds = _stats(deltas)
        item = {
            "target_id": target_id,
            "method": first["method"],
            "method_id": first["method_id"],
            "checkpoint_label": first["checkpoint_label"],
            "requested_step": first.get("requested_step"),
            "actual_step": first.get("actual_step"),
            "n_paired": ds["n"],
            "delta_common_robust_lcb_mean": ds["mean"],
            "delta_common_robust_lcb_std": ds["std"],
            "delta_common_robust_lcb_min": ds["min"],
            "delta_common_robust_lcb_max": ds["max"],
            "delta_common_robust_lcb_median": ds["median"],
        }
        for axis in axis_names:
            item[f"delta_{axis}_mean"] = _stats(axis_deltas[axis])["mean"]
        delta_vs_base.append(item)

    non_base = [r for r in records if r["method"] != "base"]
    pair_rows: list[dict[str, Any]] = []
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in non_base:
        groups.setdefault(row["checkpoint_label"], {}).setdefault(row["target_id"], []).append(row)
    for checkpoint_label, targets in sorted(groups.items()):
        for left_id, right_id in itertools.combinations(sorted(targets), 2):
            left = {r["prompt_id"]: r for r in targets[left_id]}
            right = {r["prompt_id"]: r for r in targets[right_id]}
            shared = sorted(set(left) & set(right))
            deltas = [
                float(left[pid]["common_robust_lcb"]) - float(right[pid]["common_robust_lcb"])
                for pid in shared
            ]
            ds = _stats(deltas)
            pair_rows.append(
                {
                    "checkpoint_label": checkpoint_label,
                    "left_target_id": left_id,
                    "right_target_id": right_id,
                    "left_method": targets[left_id][0]["method"],
                    "right_method": targets[right_id][0]["method"],
                    "n_paired": ds["n"],
                    "delta_common_robust_lcb_mean_left_minus_right": ds["mean"],
                    "delta_common_robust_lcb_std": ds["std"],
                    "delta_common_robust_lcb_min": ds["min"],
                    "delta_common_robust_lcb_max": ds["max"],
                    "delta_common_robust_lcb_median": ds["median"],
                }
            )

    best: dict[str, Any] = {}
    for method in ("r8a", "r8b", "m_fixedwin", "m_section"):
        rows = [r for r in summary_rows if r["method"] == method]
        if rows:
            best[method] = max(rows, key=lambda x: float(x["common_robust_lcb_mean"]))
    return summary_rows, delta_vs_base, pair_rows, best


def _run_eval(
    *,
    cfg: dict[str, Any],
    firstwave: dict[str, Any],
    policy: dict[str, Any],
    policy_hash: str,
    targets: list[dict[str, Any]],
    prompts: list[Any],
    output_root: Path,
    mode: str,
    dtype: str,
    process_objectives: bool,
) -> dict[str, Any]:
    import torch
    from mprm.common.seeding import seed_everything

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for common downstream eval")
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    source_root = (REPO_ROOT / cfg["source_training_run"]["run_root"]).resolve()
    if _is_relative_to(output_root, source_root):
        raise RuntimeError(f"refusing to write inside source training run root: {output_root}")

    common_ctx = _build_common_reward_context(cfg, policy, policy_hash)
    process_methods = set(cfg["process_objective_audit"]["applies_to_methods"])
    needs_process_contexts = process_objectives and any(t["method"] in process_methods for t in targets)
    proc_contexts = _build_process_contexts(firstwave) if needs_process_contexts else {}
    target_sigmas, sigma_bindings = _target_sigmas(firstwave)
    seed_base = int(cfg["evaluation"]["seed_base"])
    seed_everything(seed_base)
    before_gpu = _nvidia_snapshot()
    t0 = time.time()
    torch.cuda.reset_peak_memory_stats(torch.device("cuda"))

    per_prompt_path = output_root / "per_prompt_common_eval.jsonl"
    records: list[dict[str, Any]] = []
    base_refs: dict[str, Any] = {}
    base_scores: dict[str, dict[str, Any]] = {}
    target_results: dict[str, Any] = {}

    # Always evaluate Base first when present so paired probe references are fixed.
    ordered_targets = sorted(targets, key=lambda t: 0 if t["method"] == "base" else 1)
    for target_index, target in enumerate(ordered_targets):
        print(f"[common-eval] target {target_index + 1}/{len(ordered_targets)} {target['target_id']}", flush=True)
        target_start = time.time()
        model, backend, parameter_summary, load_info = _make_model_and_backend(
            firstwave=firstwave,
            target=target,
            output_root=output_root,
            dtype=dtype,
        )
        loaded_digest = load_info["digest"] if load_info else None
        final_digest = None
        prompt_count = 0
        for prompt_index, prompt in enumerate(prompts):
            seed = _seed_for(seed_base, prompt_index)
            with torch.no_grad():
                sample, res = _sample_target(
                    model=model,
                    prompt=prompt,
                    seed=seed,
                    target=target,
                    firstwave=firstwave,
                    target_sigmas=target_sigmas,
                    sigma_bindings=sigma_bindings,
                )
            if target["method"] == "base":
                base_refs[prompt.prompt_id] = res.waveform
                base_reference = res.waveform
            else:
                if prompt.prompt_id not in base_refs:
                    raise RuntimeError(f"Base reference missing for {prompt.prompt_id}")
                base_reference = base_refs[prompt.prompt_id]
            with torch.no_grad():
                common = _score_common(
                    ctx=common_ctx,
                    prompt=prompt,
                    waveform=res.waveform,
                    sample_rate=res.sample_rate,
                    base_reference=base_reference,
                )
                proc = {}
                if (
                    process_objectives
                    and target["method"] in set(cfg["process_objective_audit"]["applies_to_methods"])
                ):
                    proc = _score_process_objectives(
                        process_contexts=proc_contexts,
                        prompt=prompt,
                        sample=sample,
                        model=model,
                    )
            row = {
                "event": "phase_c1_common_downstream_eval_sample",
                "mode": mode,
                "target_id": target["target_id"],
                "method": target["method"],
                "method_id": target["method_id"],
                "display_name": target["display_name"],
                "reward_mode": target["reward_mode"],
                "credit_unit": target.get("credit_unit"),
                "checkpoint_label": target["checkpoint_label"],
                "requested_step": target.get("requested_step"),
                "actual_step": target.get("actual_step"),
                "checkpoint_path": target.get("checkpoint_path"),
                "selection_reason": target.get("selection_reason"),
                "prompt_id": prompt.prompt_id,
                "sample_index": 0,
                "seed": seed,
                "duration_actual_s": sample["meta"].get("duration_actual_s"),
                "sample_rate": sample["meta"].get("sample_rate"),
                "selection": sample["meta"].get("selection"),
                "gate_eval_policy": {
                    "name": policy["name"],
                    "version": policy["version"],
                    "hash": policy_hash,
                    "source": cfg["common_metric_policy"]["source"],
                    "draft_read_only": True,
                },
                "sampler": cfg["common_sampler"],
                "process_objectives": proc,
                "safety": {
                    "read_only_checkpoint_eval": True,
                    "training_launched": False,
                    "optimizer_step_called": False,
                    "held_out_launched": False,
                    "phase_d_launched": False,
                    "human_eval_launched": False,
                    "gate_v1_touched_by_runner": False,
                    "gate_v2_activated": False,
                    "reward_definitions_changed": False,
                    "sigma_policy_changed": False,
                    "prompt_splits_changed": False,
                    "credit_unit_definitions_changed": False,
                },
                **common,
            }
            if target["method"] == "base":
                base_scores[prompt.prompt_id] = row
            records.append(row)
            _append_jsonl(per_prompt_path, row)
            prompt_count += 1
            print(
                f"[common-eval] {target['target_id']} {prompt_count}/{len(prompts)} "
                f"{prompt.prompt_id} lcb={row['common_robust_lcb']:.6g}",
                flush=True,
            )
        if backend is not None:
            final_digest = backend.adapter_digest()
            if final_digest != loaded_digest:
                raise RuntimeError(f"{target['target_id']} adapter digest changed during eval")
        target_results[target["target_id"]] = {
            "target": target,
            "elapsed_seconds": time.time() - target_start,
            "loaded_adapter_digest": loaded_digest,
            "final_adapter_digest": final_digest,
            "adapter_unchanged_during_eval": (final_digest == loaded_digest) if loaded_digest else None,
            "parameter_summary": parameter_summary,
        }
        del backend
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    elapsed = time.time() - t0
    result = {
        "schema_version": "phase_c1_common_downstream_eval_result_v1",
        "status": "PASS",
        "mode": mode,
        "config": str(REPO_ROOT / args_config_placeholder()),
        "output_root": str(output_root),
        "generated_at_utc": _now_utc(),
        "n_prompts": len(prompts),
        "prompt_ids": [p.prompt_id for p in prompts],
        "targets": targets,
        "target_results": target_results,
        "gate_eval_policy": {
            "source": cfg["common_metric_policy"]["source"],
            "name": policy["name"],
            "version": policy["version"],
            "hash": policy_hash,
            "draft_read_only": True,
        },
        "sampler": cfg["common_sampler"],
        "elapsed_seconds": elapsed,
        "gpu_hours_consumed": elapsed / 3600.0,
        "cuda_max_memory_allocated_mb": int(torch.cuda.max_memory_allocated(torch.device("cuda")) / (1024 * 1024)),
        "nvidia_smi_before": before_gpu,
        "nvidia_smi_after": _nvidia_snapshot(),
        "boundary_flags": {
            "training_launched": False,
            "optimizer_step_called": False,
            "checkpoint_overwritten": False,
            "held_out_launched": False,
            "phase_d_launched": False,
            "human_eval_launched": False,
            "gate_v1_touched_by_runner": False,
            "gate_v2_activated": False,
            "reward_definitions_changed": False,
            "sigma_policy_changed": False,
            "prompt_splits_changed": False,
            "credit_unit_definitions_changed": False,
        },
    }
    _write_aggregate_outputs(
        output_root=output_root,
        records=records,
        result=result,
        per_prompt_already_written=True,
    )
    return result


def _rows_from_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _validate_row_only_recovery(
    *,
    root: Path,
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
    policy_hash: str,
    mode: str,
) -> None:
    if not rows:
        raise RuntimeError(f"row-only recovery root has no rows: {root}")
    expected_prompt_ids = set(_select_prompt_ids(cfg, mode=mode, max_prompts=None))
    seen_keys: set[tuple[str, str, int]] = set()
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = _row_key(row)
        if key in seen_keys:
            raise RuntimeError(f"duplicate row in recovery root {root}: {key}")
        seen_keys.add(key)
        if row.get("gate_eval_policy", {}).get("hash") != policy_hash:
            raise RuntimeError(f"row-only recovery policy hash mismatch: {root}")
        if row.get("sampler") != cfg["common_sampler"]:
            raise RuntimeError(f"row-only recovery sampler mismatch: {root}")
        if row.get("prompt_id") not in expected_prompt_ids:
            raise RuntimeError(f"row-only recovery unexpected prompt_id in {root}: {row.get('prompt_id')}")
        safety = row.get("safety", {})
        for boundary_key in (
            "training_launched",
            "optimizer_step_called",
            "checkpoint_overwritten",
            "held_out_launched",
            "phase_d_launched",
            "human_eval_launched",
            "gate_v1_touched_by_runner",
            "gate_v2_activated",
            "reward_definitions_changed",
            "sigma_policy_changed",
            "prompt_splits_changed",
            "credit_unit_definitions_changed",
        ):
            if safety.get(boundary_key) not in (False, None):
                raise RuntimeError(f"row-only recovery violates boundary {boundary_key}: {root}")
        by_target.setdefault(str(row["target_id"]), []).append(row)
    if "base__base" not in by_target:
        raise RuntimeError(f"row-only recovery root is missing Base rows: {root}")
    for target_id, target_rows in by_target.items():
        prompt_ids = {str(row["prompt_id"]) for row in target_rows}
        if prompt_ids != expected_prompt_ids:
            missing = sorted(expected_prompt_ids - prompt_ids)[:8]
            extra = sorted(prompt_ids - expected_prompt_ids)[:8]
            raise RuntimeError(
                f"row-only recovery target has incomplete prompts in {root}: "
                f"{target_id} missing={missing} extra={extra}"
            )
        if len(target_rows) != len(expected_prompt_ids):
            raise RuntimeError(
                f"row-only recovery target has duplicate prompt rows in {root}: {target_id}"
            )


def _merge_roots(
    *,
    cfg: dict[str, Any],
    policy: dict[str, Any],
    policy_hash: str,
    roots: list[Path],
    output_root: Path,
    mode: str,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    source_root = (REPO_ROOT / cfg["source_training_run"]["run_root"]).resolve()
    if _is_relative_to(output_root, source_root):
        raise RuntimeError(f"refusing to write inside source training run root: {output_root}")

    records_by_key: dict[tuple[str, str, int], dict[str, Any]] = {}
    shard_results: list[dict[str, Any]] = []
    row_only_recovered_roots: list[str] = []
    for root in roots:
        result_path = root / "common_eval_results.json"
        rows_path = root / "per_prompt_common_eval.jsonl"
        if not rows_path.exists():
            raise RuntimeError(f"merge root missing required JSONL: {root}")
        rows = _rows_from_jsonl(rows_path)
        if result_path.exists():
            shard = json.loads(result_path.read_text(encoding="utf-8"))
            if shard.get("status") != "PASS":
                raise RuntimeError(f"merge root status is not PASS: {root}")
            shard_policy = shard.get("gate_eval_policy", {})
            if shard_policy.get("hash") != policy_hash:
                raise RuntimeError(f"merge root gate policy hash mismatch: {root}")
        else:
            _validate_row_only_recovery(
                root=root,
                rows=rows,
                cfg=cfg,
                policy_hash=policy_hash,
                mode=mode,
            )
            row_only_recovered_roots.append(str(root))
            shard = {
                "status": "ROW_ONLY_RECOVERED",
                "output_root": str(root),
                "n_rows": len(rows),
                "gpu_hours_consumed": None,
                "elapsed_seconds": None,
                "recovery_reason": (
                    "streamed per_prompt_common_eval.jsonl completed but the shard "
                    "exited before common_eval_results.json was written"
                ),
            }
        shard_results.append(shard)
        for row in rows:
            key = (row["target_id"], row["prompt_id"], int(row.get("sample_index", 0)))
            if key in records_by_key:
                existing = records_by_key[key]
                if row["method"] == "base":
                    # Parallel shards intentionally duplicate Base references.
                    # Keep the first deterministic Base row.
                    continue
                raise RuntimeError(f"duplicate non-Base row while merging: {key}")
            records_by_key[key] = row
    records = sorted(
        records_by_key.values(),
        key=lambda r: (
            0 if r["method"] == "base" else 1,
            str(r["checkpoint_label"]),
            str(r["method"]),
            str(r["prompt_id"]),
            int(r.get("sample_index", 0)),
        ),
    )
    prompt_ids = sorted({r["prompt_id"] for r in records})
    target_ids = sorted({r["target_id"] for r in records})
    boundary = {
        "training_launched": False,
        "optimizer_step_called": False,
        "checkpoint_overwritten": False,
        "held_out_launched": False,
        "phase_d_launched": False,
        "human_eval_launched": False,
        "gate_v1_touched_by_runner": False,
        "gate_v2_activated": False,
        "reward_definitions_changed": False,
        "sigma_policy_changed": False,
        "prompt_splits_changed": False,
        "credit_unit_definitions_changed": False,
    }
    for row in records:
        safety = row.get("safety", {})
        for key in boundary:
            if safety.get(key) not in (False, None):
                raise RuntimeError(f"merged row violates boundary {key}: {row['target_id']} {row['prompt_id']}")
    known_gpu_hours = [
        float(shard["gpu_hours_consumed"])
        for shard in shard_results
        if isinstance(shard.get("gpu_hours_consumed"), (int, float))
    ]
    known_elapsed_seconds = [
        float(shard["elapsed_seconds"])
        for shard in shard_results
        if isinstance(shard.get("elapsed_seconds"), (int, float))
    ]
    missing_gpu_hour_roots = [
        str(shard.get("output_root"))
        for shard in shard_results
        if not isinstance(shard.get("gpu_hours_consumed"), (int, float))
    ]
    result = {
        "schema_version": "phase_c1_common_downstream_eval_result_v1",
        "status": "PASS",
        "mode": mode,
        "merge_only": True,
        "config": str(REPO_ROOT / args_config_placeholder()),
        "output_root": str(output_root),
        "generated_at_utc": _now_utc(),
        "n_prompts": len(prompt_ids),
        "prompt_ids": prompt_ids,
        "targets": [{"target_id": tid} for tid in target_ids],
        "merged_from_roots": [str(root) for root in roots],
        "row_only_recovery_used": bool(row_only_recovered_roots),
        "row_only_recovered_roots": row_only_recovered_roots,
        "shard_gpu_hours_consumed": sum(known_gpu_hours) if not missing_gpu_hour_roots else None,
        "known_shard_gpu_hours_consumed": sum(known_gpu_hours),
        "missing_shard_gpu_hour_roots": missing_gpu_hour_roots,
        "shard_elapsed_seconds": sum(known_elapsed_seconds) if not missing_gpu_hour_roots else None,
        "known_shard_elapsed_seconds": sum(known_elapsed_seconds),
        "gate_eval_policy": {
            "source": cfg["common_metric_policy"]["source"],
            "name": policy["name"],
            "version": policy["version"],
            "hash": policy_hash,
            "draft_read_only": True,
        },
        "sampler": cfg["common_sampler"],
        "boundary_flags": boundary,
    }
    _write_aggregate_outputs(output_root=output_root, records=records, result=result)
    return result


_CONFIG_PATH_FOR_RESULT = ""


def args_config_placeholder() -> str:
    return _CONFIG_PATH_FOR_RESULT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mode", choices=["smoke", "eval"], required=True)
    parser.add_argument("--checkpoint-set", choices=["step1000", "sweep"], default="step1000")
    parser.add_argument("--checkpoint-labels", nargs="+", default=None)
    parser.add_argument("--methods", nargs="+", default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--max-prompts", type=int, default=None)
    parser.add_argument("--dtype", choices=["bfloat16", "float16", "float32"], default="bfloat16")
    parser.add_argument("--skip-process-objectives", action="store_true")
    parser.add_argument("--merge-roots", nargs="+", type=Path, default=None)
    args = parser.parse_args()

    global _CONFIG_PATH_FOR_RESULT
    _CONFIG_PATH_FOR_RESULT = str(args.config)

    cfg = _load_yaml(args.config)
    firstwave = _load_yaml(REPO_ROOT / cfg["source_training_run"]["training_config"])
    from scripts.phase_c1_grpo import _validate_bundle

    _validate_bundle(firstwave)
    policy, policy_hash = _validate_common_config(cfg, firstwave)
    if args.merge_roots:
        output_root = args.output_root
        if output_root is None:
            raise RuntimeError("--output-root is required with --merge-roots")
        result = _merge_roots(
            cfg=cfg,
            policy=policy,
            policy_hash=policy_hash,
            roots=[p.resolve() for p in args.merge_roots],
            output_root=output_root.resolve(),
            mode=args.mode,
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "mode": result["mode"],
                    "merge_only": True,
                    "n_prompts": result["n_prompts"],
                    "n_targets": len(result["targets"]),
                    "output_root": result["output_root"],
                    "shard_gpu_hours_consumed": result["shard_gpu_hours_consumed"],
                }
            )
        )
        return 0
    prompt_ids = _select_prompt_ids(cfg, mode=args.mode, max_prompts=args.max_prompts)
    prompts = _load_prompts(cfg, prompt_ids)
    targets = _select_targets(
        cfg,
        mode=args.mode,
        methods=args.methods,
        checkpoint_set=args.checkpoint_set,
        checkpoint_labels=args.checkpoint_labels,
    )
    output_root = args.output_root or Path(
        cfg["evaluation"]["smoke_output_root"] if args.mode == "smoke" else cfg["evaluation"]["full_output_root"]
    )
    output_root = output_root.resolve()
    result = _run_eval(
        cfg=cfg,
        firstwave=firstwave,
        policy=policy,
        policy_hash=policy_hash,
        targets=targets,
        prompts=prompts,
        output_root=output_root,
        mode=args.mode,
        dtype=args.dtype,
        process_objectives=not args.skip_process_objectives,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "mode": result["mode"],
                "n_prompts": result["n_prompts"],
                "n_targets": len(result["targets"]),
                "output_root": result["output_root"],
                "gpu_hours_consumed": result["gpu_hours_consumed"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
