#!/usr/bin/env python3
"""Execute and audit BOLT Gate 0 in resumable phases."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import socket
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "src", ROOT / "scripts", OUT):
    sys.path.insert(0, str(path))

from bolt_ace_step import (  # noqa: E402
    CHECKPOINT_STEPS,
    AceStepBOLTRunner,
    prompt_from_dict,
    waveform_nrmse,
    waveform_validity,
)
from bolt_core import (  # noqa: E402
    BudgetManager,
    append_jsonl,
    canonical_json_hash,
    demonstrate_true_rollover,
    read_jsonl,
    select_best_scored,
    sha256_file,
    shared_prefix_program_cost,
)
from bolt_scoring import BoltScorer, save_audio_once  # noqa: E402
from bolt_state import load_checkpoint_state, save_checkpoint_state, tensor_sha256  # noqa: E402


MANIFEST = OUT / "BOLT_GATE0_TEST_MANIFEST.jsonl"
RUNTIME = OUT / "BOLT_RUNTIME_FREEZE.json"
GATE0_LEDGER = OUT / "BOLT_GATE0_LEDGER.jsonl"
LEDGER_DIR = OUT / "gate0_ledgers"
STATE_DIR = OUT / "gate0_states"
AUDIO_DIR = OUT / "gate0_audio"
SCORE_DIR = OUT / "gate0_scores"
RESUME_CSV = OUT / "BOLT_RESUME_EQUIVALENCE.csv"
SWITCH_CSV = OUT / "BOLT_CONDITION_SWITCH.csv"
FORK_CSV = OUT / "BOLT_FORK_CALIBRATION.csv"
NFE_CSV = OUT / "BOLT_NFE_ACCOUNTING.csv"
REPORT = OUT / "BOLT_GATE0_REPORT.md"
FORK_REPORT = OUT / "BOLT_FORK_CALIBRATION_REPORT.md"
FORK_FREEZE = OUT / "BOLT_FORK_FREEZE.json"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def read_runtime() -> dict[str, str]:
    record = json.loads(RUNTIME.read_text(encoding="utf-8"))
    if record.get("status") != "FROZEN_PARITY_PASS":
        raise RuntimeError("BOLT runtime is not frozen after environment parity")
    return {
        "model_hash": record["ace_step_source_manifest_sha256"],
        "checkpoint_hash": record["ace_step_checkpoint_manifest_sha256"],
        "scheduler_hash": record["scheduler_sha256"],
    }


def manifest_rows() -> list[dict]:
    rows = read_jsonl(MANIFEST)
    if len(rows) != 8 or any(len(row.get("root_seeds", [])) != 2 for row in rows):
        raise RuntimeError("Gate-0 manifest must contain 8 prompts and two roots each")
    if any(not row["prompt_id"].startswith("dev_") for row in rows):
        raise RuntimeError("Gate-0 prompt leakage")
    return rows


def root_tasks() -> list[dict]:
    tasks = []
    for prompt_row in manifest_rows():
        for root_index, seed in enumerate(prompt_row["root_seeds"]):
            tasks.append({**prompt_row, "root_index": root_index, "root_seed": int(seed)})
    return tasks


def state_path(task: dict, checkpoint: int) -> Path:
    return STATE_DIR / task["prompt_id"] / f"seed{task['root_seed']}__step{checkpoint:02d}.pt"


def audio_path(phase: str, task: dict, checkpoint: int | None = None, eta: float | None = None) -> Path:
    suffix = ""
    if checkpoint is not None:
        suffix += f"__step{checkpoint:02d}"
    if eta is not None:
        suffix += f"__eta{eta:.3f}".replace(".", "p")
    return AUDIO_DIR / phase / task["prompt_id"] / f"seed{task['root_seed']}{suffix}.flac"


def load_phase_rows(phase: str) -> list[dict]:
    rows = []
    for path in sorted(LEDGER_DIR.glob(f"{phase}_w*.jsonl")):
        rows.extend(read_jsonl(path))
    latest: dict[str, dict] = {}
    for row in rows:
        key = str(row["unit_id"])
        prior = latest.get(key)
        if prior and prior.get("status") == "PASS" and row.get("status") == "PASS":
            comparable = (prior.get("output_sha256"), prior.get("condition_after"), prior.get("nfe"))
            current = (row.get("output_sha256"), row.get("condition_after"), row.get("nfe"))
            if comparable != current:
                raise RuntimeError(f"conflicting successful Gate-0 rows for {key}")
        latest[key] = row
    return list(latest.values())


def prior_passes(ledger: Path) -> set[str]:
    return {str(row["unit_id"]) for row in read_jsonl(ledger) if row.get("status") == "PASS"}


def append_gate0_record(record: dict) -> None:
    append_jsonl(GATE0_LEDGER, record)


def command_root(args: argparse.Namespace) -> int:
    tasks = root_tasks()[args.worker_index :: args.num_workers]
    ledger = LEDGER_DIR / f"root_w{args.worker_index}.jsonl"
    done = prior_passes(ledger)
    runner = AceStepBOLTRunner(read_runtime())
    for task in tasks:
        unit_id = f"root::{task['prompt_id']}::{task['root_seed']}"
        if unit_id in done:
            continue
        started = time.time()
        record = {
            "timestamp": now(), "phase": "root", "unit_id": unit_id,
            "prompt_id": task["prompt_id"], "root_seed": task["root_seed"],
            "root_index": task["root_index"], "worker": args.worker_index,
            "gpu": os.environ.get("CUDA_VISIBLE_DEVICES"), "host": socket.gethostname(),
            "status": "FAIL", "error": "",
        }
        try:
            prompt = prompt_from_dict(task["prompt"])
            result = runner.run_full(
                prompt, seed=task["root_seed"], requested_vocal=int(task["requested_vocal"]),
                switched=False, capture_steps=CHECKPOINT_STEPS,
            )
            saved = save_audio_once(audio_path("root", task), result.waveform, result.sample_rate)
            states = {}
            for checkpoint, state in result.checkpoints.items():
                metadata = save_checkpoint_state(state, state_path(task, checkpoint), allow_existing=True)
                states[str(checkpoint)] = {
                    "path": repo_relative(state_path(task, checkpoint)),
                    "state_file_sha256": metadata["state_file_sha256"],
                    "latent_sha256": metadata["latent_sha256"],
                    "model_output_sha256": metadata["model_output_sha256"],
                    "prefix_nfe": state.nfe_count,
                    "prefix_scheduler_steps": state.scheduler_step_count,
                }
            record.update(
                {
                    **saved,
                    "output_path": repo_relative(Path(saved["output_path"])),
                    "condition_after": result.condition_hash,
                    "condition_before": result.condition_hash,
                    "nfe": result.nfe,
                    "scheduler_steps": result.scheduler_steps,
                    "cumulative_nfe_by_step": result.cumulative_nfe_by_step,
                    "wall_seconds": result.wall_seconds,
                    "cuda_seconds": result.cuda_seconds,
                    "checkpoint_states": states,
                    "status": "PASS",
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_seconds"] = time.time() - started
        append_jsonl(ledger, record)
        append_gate0_record(record)
        if record["status"] != "PASS":
            raise RuntimeError(record["error"])
    return 0


def continuation_tasks() -> list[dict]:
    return [
        {**task, "checkpoint_step": checkpoint}
        for task in root_tasks() for checkpoint in CHECKPOINT_STEPS
    ]


def command_continue(args: argparse.Namespace) -> int:
    phase = args.phase
    if phase not in {"resume", "switch"}:
        raise ValueError(phase)
    tasks = continuation_tasks()[args.worker_index :: args.num_workers]
    ledger = LEDGER_DIR / f"{phase}_w{args.worker_index}.jsonl"
    done = prior_passes(ledger)
    runner = AceStepBOLTRunner(read_runtime())
    for task in tasks:
        checkpoint = int(task["checkpoint_step"])
        unit_id = f"{phase}::{task['prompt_id']}::{task['root_seed']}::{checkpoint}"
        if unit_id in done:
            continue
        record = {
            "timestamp": now(), "phase": phase, "unit_id": unit_id,
            "prompt_id": task["prompt_id"], "root_seed": task["root_seed"],
            "root_index": task["root_index"], "checkpoint_step": checkpoint,
            "worker": args.worker_index, "gpu": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "host": socket.gethostname(), "status": "FAIL", "error": "",
        }
        try:
            state, metadata = load_checkpoint_state(state_path(task, checkpoint))
            prompt = prompt_from_dict(task["prompt"])
            result = runner.run_from_state(
                state, prompt, requested_vocal=int(task["requested_vocal"]),
                switched=phase == "switch",
            )
            saved = save_audio_once(audio_path(phase, task, checkpoint), result.waveform, result.sample_rate)
            record.update(
                {
                    **saved,
                    "output_path": repo_relative(Path(saved["output_path"])),
                    "state_path": repo_relative(state_path(task, checkpoint)),
                    "state_file_sha256": metadata["state_file_sha256"],
                    "latent_save_load_hash_exact": tensor_sha256(state.latent) == metadata["latent_sha256"],
                    "condition_before": state.condition_hash,
                    "condition_after": result.condition_hash,
                    "condition_hash_changed": state.condition_hash != result.condition_hash,
                    "prefix_nfe": state.nfe_count,
                    "nfe": result.nfe,
                    "total_tree_edge_nfe": state.nfe_count + result.nfe,
                    "scheduler_steps": result.scheduler_steps,
                    "wall_seconds": result.wall_seconds,
                    "cuda_seconds": result.cuda_seconds,
                    "status": "PASS",
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        append_jsonl(ledger, record)
        append_gate0_record(record)
        if record["status"] != "PASS":
            raise RuntimeError(record["error"])
    return 0


def fork_tasks() -> list[dict]:
    return [{**task, "checkpoint_step": 12} for task in root_tasks() if task["root_index"] == 0]


def command_fork(args: argparse.Namespace) -> int:
    phase = f"fork_eta_{args.eta:.3f}".replace(".", "p")
    tasks = fork_tasks()[args.worker_index :: args.num_workers]
    ledger = LEDGER_DIR / f"{phase}_w{args.worker_index}.jsonl"
    done = prior_passes(ledger)
    runner = AceStepBOLTRunner(read_runtime())
    for task in tasks:
        checkpoint = 12
        branch_seed = int(args.seed_base + 9_500_000 + int(task["gate0_prompt_index"]) * 100 + round(args.eta * 1000))
        unit_id = f"{phase}::{task['prompt_id']}::{task['root_seed']}::{checkpoint}"
        if unit_id in done:
            continue
        record = {
            "timestamp": now(), "phase": phase, "unit_id": unit_id,
            "prompt_id": task["prompt_id"], "root_seed": task["root_seed"],
            "checkpoint_step": checkpoint, "fork_eta": float(args.eta),
            "branch_seed": branch_seed, "worker": args.worker_index,
            "gpu": os.environ.get("CUDA_VISIBLE_DEVICES"), "host": socket.gethostname(),
            "status": "FAIL", "error": "",
        }
        try:
            state, metadata = load_checkpoint_state(state_path(task, checkpoint))
            prompt = prompt_from_dict(task["prompt"])
            result = runner.run_from_state(
                state, prompt, requested_vocal=int(task["requested_vocal"]), switched=False,
                fork_eta=float(args.eta), fork_seed=branch_seed,
            )
            saved = save_audio_once(audio_path("fork", task, checkpoint, args.eta), result.waveform, result.sample_rate)
            record.update(
                {
                    **saved,
                    "output_path": repo_relative(Path(saved["output_path"])),
                    "state_path": repo_relative(state_path(task, checkpoint)),
                    "state_file_sha256": metadata["state_file_sha256"],
                    "condition_before": state.condition_hash,
                    "condition_after": result.condition_hash,
                    "prefix_nfe": state.nfe_count,
                    "nfe": result.nfe,
                    "total_tree_edge_nfe": state.nfe_count + result.nfe,
                    "scheduler_steps": result.scheduler_steps,
                    "wall_seconds": result.wall_seconds,
                    "cuda_seconds": result.cuda_seconds,
                    "status": "PASS",
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        append_jsonl(ledger, record)
        append_gate0_record(record)
        if record["status"] != "PASS":
            raise RuntimeError(record["error"])
    return 0


def _task_index() -> dict[tuple[str, int], dict]:
    return {(row["prompt_id"], int(row["root_seed"])): row for row in root_tasks()}


def command_score(args: argparse.Namespace) -> int:
    phase = args.phase
    generated = load_phase_rows(phase)
    if not generated:
        raise RuntimeError(f"no generation rows for phase {phase}")
    generated = sorted(generated, key=lambda row: row["unit_id"])[args.worker_index :: args.num_workers]
    ledger = SCORE_DIR / f"{phase}_score_w{args.worker_index}.jsonl"
    done = prior_passes(ledger)
    scorer = BoltScorer()
    tasks = _task_index()
    root_by_key = {(row["prompt_id"], int(row["root_seed"])): row for row in load_phase_rows("root")}
    for generated_row in generated:
        unit_id = generated_row["unit_id"]
        if unit_id in done:
            continue
        record = {"timestamp": now(), "phase": phase, "unit_id": unit_id, "status": "FAIL", "error": ""}
        try:
            import soundfile as sf
            import torch

            key = (generated_row["prompt_id"], int(generated_row["root_seed"]))
            task = tasks[key]
            prompt = prompt_from_dict(task["prompt"])
            path = ROOT / generated_row["output_path"]
            samples, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
            waveform = torch.from_numpy(samples.T.copy())
            scores = scorer.score(
                audio_path=path, waveform=waveform, sample_rate=int(sample_rate), prompt=prompt,
                requested_vocal=int(task["requested_vocal"]),
            )
            record.update(generated_row)
            record.update(scores)
            record["output_path"] = generated_row["output_path"]
            if phase != "root":
                reference_row = root_by_key[key]
                reference_path = ROOT / reference_row["output_path"]
                reference_samples, reference_sr = sf.read(
                    str(reference_path), always_2d=True, dtype="float32"
                )
                reference = torch.from_numpy(reference_samples.T.copy())
                record["waveform_nrmse_vs_deterministic"] = waveform_nrmse(reference, waveform)
                record["audio_audio_clap_cosine"] = scorer.audio_audio_cosine(
                    reference, waveform, int(reference_sr)
                )
                record["reference_output_sha256"] = reference_row["output_sha256"]
            record["status"] = "PASS"
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        append_jsonl(ledger, record)
        append_gate0_record(record)
        if record["status"] != "PASS":
            raise RuntimeError(record["error"])
    return 0


def load_scores(phase: str) -> list[dict]:
    rows = []
    for path in sorted(SCORE_DIR.glob(f"{phase}_score_w*.jsonl")):
        rows.extend(read_jsonl(path))
    latest = {row["unit_id"]: row for row in rows}
    return list(latest.values())


def write_csv_once(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(path)
    if not rows:
        raise ValueError(f"empty CSV {path}")
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def command_audit(_args: argparse.Namespace) -> int:
    root_generation = load_phase_rows("root")
    root_scores = load_scores("root")
    resume_generation = load_phase_rows("resume")
    resume_scores = load_scores("resume")
    switch_generation = load_phase_rows("switch")
    switch_scores = load_scores("switch")
    root_score_index = {(row["prompt_id"], int(row["root_seed"])): row for row in root_scores}
    expected_resume = 8 * 2 * 3
    resume_rows = []
    for row in sorted(resume_scores, key=lambda value: value["unit_id"]):
        reference = root_score_index[(row["prompt_id"], int(row["root_seed"]))]
        no_label_flip = row["label_b_satisfied"] == reference["label_b_satisfied"]
        no_quality_flip = row["quality_floor_status"] == reference["quality_floor_status"]
        pass_row = (
            row.get("status") == "PASS"
            and row.get("latent_save_load_hash_exact") is True
            and float(row["waveform_nrmse_vs_deterministic"]) <= 1e-6
            and float(row["audio_audio_clap_cosine"]) >= 0.999999
            and no_label_flip and no_quality_flip
            and int(row["sample_rate"]) == int(reference["sample_rate"])
            and abs(float(row["duration_seconds"]) - float(reference["duration_seconds"])) <= 1e-9
        )
        resume_rows.append(
            {
                "unit_id": row["unit_id"], "prompt_id": row["prompt_id"],
                "root_seed": row["root_seed"], "checkpoint_step": row["checkpoint_step"],
                "latent_save_load_hash_exact": row["latent_save_load_hash_exact"],
                "waveform_nrmse": row["waveform_nrmse_vs_deterministic"],
                "audio_audio_clap_cosine": row["audio_audio_clap_cosine"],
                "label_b_flip": int(not no_label_flip), "quality_floor_flip": int(not no_quality_flip),
                "sample_rate_match": int(row["sample_rate"] == reference["sample_rate"]),
                "duration_match": int(abs(float(row["duration_seconds"]) - float(reference["duration_seconds"])) <= 1e-9),
                "status": "PASS" if pass_row else "FAIL",
            }
        )
    resume_status = len(resume_rows) == expected_resume and all(row["status"] == "PASS" for row in resume_rows)

    switch_rows = []
    for row in sorted(switch_scores, key=lambda value: value["unit_id"]):
        valid = bool(row.get("valid")) and not bool(row.get("near_silent"))
        changed = bool(row.get("condition_hash_changed"))
        pass_row = row.get("status") == "PASS" and valid and changed
        switch_rows.append(
            {
                "unit_id": row["unit_id"], "prompt_id": row["prompt_id"],
                "root_seed": row["root_seed"], "checkpoint_step": row["checkpoint_step"],
                "condition_before": row["condition_before"], "condition_after": row["condition_after"],
                "condition_hash_changed": changed, "prefix_nfe": row["prefix_nfe"],
                "continuation_nfe": row["nfe"], "valid": valid,
                "label_b_satisfied": row["label_b_satisfied"],
                "common_robust_lcb": row["common_robust_lcb"],
                "clap_to_original_prompt": row["clap_to_original_prompt"],
                "status": "PASS" if pass_row else "FAIL",
            }
        )
    switch_status = len(switch_rows) == expected_resume and all(row["status"] == "PASS" for row in switch_rows)

    fork_rows = []
    eta_summary = []
    for eta in (0.025, 0.05, 0.10):
        phase = f"fork_eta_{eta:.3f}".replace(".", "p")
        rows = load_scores(phase)
        for row in rows:
            nonidentical = row["output_sha256"] != row["reference_output_sha256"]
            fork_rows.append(
                {
                    "unit_id": row["unit_id"], "prompt_id": row["prompt_id"],
                    "root_seed": row["root_seed"], "checkpoint_step": row["checkpoint_step"],
                    "eta": eta, "branch_seed": row["branch_seed"],
                    "nonidentical_waveform_hash": int(nonidentical),
                    "audio_audio_clap_cosine": row["audio_audio_clap_cosine"],
                    "near_silent": row["near_silent"], "valid": row["valid"],
                    "status": row["status"],
                }
            )
        valid = len(rows) == 8 and all(row.get("status") == "PASS" and row.get("valid") and not row.get("near_silent") for row in rows)
        nonidentical_share = float(np.mean([row["output_sha256"] != row["reference_output_sha256"] for row in rows])) if rows else 0.0
        mean_cosine = float(np.mean([float(row["audio_audio_clap_cosine"]) for row in rows])) if rows else math.nan
        eta_pass = bool(valid and nonidentical_share >= 0.90 and mean_cosine >= 0.80 and mean_cosine < 0.999)
        eta_summary.append(
            {"eta": eta, "rows": len(rows), "nonidentical_share": nonidentical_share,
             "mean_audio_audio_clap_cosine": mean_cosine, "status": "PASS" if eta_pass else "FAIL"}
        )
    passing_eta = [row for row in eta_summary if row["status"] == "PASS"]
    selected_eta = min((row["eta"] for row in passing_eta), default=None)
    fork_status = selected_eta is not None

    root_nfes = {int(row["nfe"]) for row in root_generation if row.get("status") == "PASS"}
    standard_nfe = next(iter(root_nfes)) if len(root_nfes) == 1 else 0
    nfe_rows = []
    for phase, rows in (
        ("root", root_generation), ("resume", resume_generation), ("switch", switch_generation),
    ):
        for row in rows:
            prefix = int(row.get("prefix_nfe", 0))
            action = int(row.get("nfe", 0))
            nfe_rows.append(
                {
                    "phase": phase, "unit_id": row["unit_id"], "prompt_id": row["prompt_id"],
                    "root_seed": row["root_seed"], "checkpoint_step": row.get("checkpoint_step", 0),
                    "prefix_nfe": prefix, "action_nfe": action,
                    "total_program_nfe": shared_prefix_program_cost(prefix, [action]),
                    "scheduler_steps": row.get("scheduler_steps"),
                    "wall_seconds": row.get("wall_seconds"), "cuda_seconds": row.get("cuda_seconds"),
                    "status": row["status"],
                }
            )
    actual_nfe_status = bool(
        standard_nfe > 0 and len(root_generation) == 16
        and all(row["status"] == "PASS" and int(row["nfe"]) > 0 for row in root_generation)
        and len(resume_generation) == 48 and len(switch_generation) == 48
        and all(int(row["prefix_nfe"]) + int(row["nfe"]) == standard_nfe for row in resume_generation)
    )
    prefix12 = {
        int(row["checkpoint_states"]["12"]["prefix_nfe"])
        for row in root_generation if row.get("status") == "PASS"
    }
    rollover = demonstrate_true_rollover(standard_nfe, next(iter(prefix12))) if standard_nfe and len(prefix12) == 1 else {"status": "FAIL"}
    true_rollover_status = rollover["status"] == "PASS"
    reserve = BudgetManager(2 * standard_nfe, standard_nfe) if standard_nfe else None
    completion_reserve_status = bool(reserve and not reserve.feasible(standard_nfe + 1) and reserve.feasible(standard_nfe, guarantees_completion=True))
    zero_row = select_best_scored([{"score": None, "id": "missing"}, {"score": 0.0, "id": "zero"}], "score")
    zero_status = zero_row["id"] == "zero"
    environment_text = (OUT / "BOLT_ENVIRONMENT_PARITY_REPORT.md").read_text(encoding="utf-8")
    environment_status = "ENVIRONMENT_PARITY_STATUS = PASS" in environment_text
    gate0 = all(
        (environment_status, resume_status, switch_status, fork_status, actual_nfe_status,
         true_rollover_status, completion_reserve_status, zero_status)
    )

    for path, rows in ((RESUME_CSV, resume_rows), (SWITCH_CSV, switch_rows), (FORK_CSV, fork_rows), (NFE_CSV, nfe_rows)):
        write_csv_once(path, rows)
    FORK_FREEZE.write_text(
        json.dumps({"status": "FROZEN", "selected_eta": selected_eta, "calibration": eta_summary}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    FORK_REPORT.write_text(
        "# BOLT Fork Calibration\n\n"
        f"`FORK_STATUS = {'PASS' if fork_status else 'FAIL'}`\n\n"
        f"Selected eta: `{selected_eta}`. The smallest passing eta is frozen for the pilot.\n\n"
        "| eta | rows | nonidentical share | mean CLAP audio-audio cosine | status |\n"
        "| ---: | ---: | ---: | ---: | --- |\n"
        + "".join(
            f"| {row['eta']:.3f} | {row['rows']} | {row['nonidentical_share']:.6f} | {row['mean_audio_audio_clap_cosine']:.9f} | {row['status']} |\n"
            for row in eta_summary
        ), encoding="utf-8",
    )
    REPORT.write_text(
        "# BOLT Gate 0 Report\n\n"
        f"GATE0_STATUS = {'PASS' if gate0 else 'FAIL'}\n"
        f"ENVIRONMENT_PARITY_STATUS = {'PASS' if environment_status else 'FAIL'}\n"
        f"RESUME_EQUIVALENCE_STATUS = {'PASS' if resume_status else 'FAIL'}\n"
        f"CONDITION_SWITCH_STATUS = {'PASS' if switch_status else 'FAIL'}\n"
        f"FORK_STATUS = {'PASS' if fork_status else 'FAIL'}\n"
        f"ACTUAL_NFE_STATUS = {'PASS' if actual_nfe_status else 'FAIL'}\n"
        f"TRUE_ROLLOVER_STATUS = {'PASS' if true_rollover_status else 'FAIL'}\n"
        f"COMPLETION_RESERVE_STATUS = {'PASS' if completion_reserve_status else 'FAIL'}\n"
        f"ZERO_SCORE_SELECTION_STATUS = {'PASS' if zero_status else 'FAIL'}\n\n"
        f"Measured standard-generation NFE: `{standard_nfe}`; pilot budget NFE: `{2 * standard_nfe}`.\n\n"
        f"Resume controls: `{sum(row['status'] == 'PASS' for row in resume_rows)}/{expected_resume}`; "
        f"Label-B flips: `{sum(int(row['label_b_flip']) for row in resume_rows)}`; "
        f"quality-floor flips: `{sum(int(row['quality_floor_flip']) for row in resume_rows)}`.\n\n"
        f"True-rollover trace: `{json.dumps(rollover, sort_keys=True)}`. Scheduler-step equivalent trace is 60 -> 48 -> 36 -> complete 30.\n\n"
        f"Fork eta: `{selected_eta}`. Detailed evidence: `{repo_relative(FORK_CSV)}` and `{repo_relative(FORK_REPORT)}`.\n",
        encoding="utf-8",
    )
    summary = {
        "timestamp": now(), "phase": "gate0_audit", "status": "PASS" if gate0 else "FAIL",
        "gate0_status": "PASS" if gate0 else "FAIL", "standard_generation_nfe": standard_nfe,
        "budget_nfe": 2 * standard_nfe, "selected_fork_eta": selected_eta,
        "manifest_sha256": sha256_file(MANIFEST), "report_sha256": sha256_file(REPORT),
    }
    append_gate0_record(summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if gate0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("root", command_root),):
        child = sub.add_parser(name)
        child.add_argument("--worker-index", type=int, required=True)
        child.add_argument("--num-workers", type=int, required=True)
        child.set_defaults(func=func)
    continuation = sub.add_parser("continue")
    continuation.add_argument("--phase", choices=("resume", "switch"), required=True)
    continuation.add_argument("--worker-index", type=int, required=True)
    continuation.add_argument("--num-workers", type=int, required=True)
    continuation.set_defaults(func=command_continue)
    fork = sub.add_parser("fork")
    fork.add_argument("--eta", type=float, choices=(0.025, 0.05, 0.10), required=True)
    fork.add_argument("--seed-base", type=int, required=True)
    fork.add_argument("--worker-index", type=int, required=True)
    fork.add_argument("--num-workers", type=int, required=True)
    fork.set_defaults(func=command_fork)
    score = sub.add_parser("score")
    score.add_argument("--phase", required=True)
    score.add_argument("--worker-index", type=int, required=True)
    score.add_argument("--num-workers", type=int, required=True)
    score.set_defaults(func=command_score)
    audit = sub.add_parser("audit")
    audit.set_defaults(func=command_audit)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command != "audit":
        visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
        if len(visible) != 1:
            raise RuntimeError("each Gate-0 GPU worker requires exactly one visible GPU")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
