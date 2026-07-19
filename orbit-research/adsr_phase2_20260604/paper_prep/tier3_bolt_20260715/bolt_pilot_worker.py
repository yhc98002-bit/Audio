#!/usr/bin/env python3
"""One-GPU, root-tree-owned worker for the frozen BOLT action atlas pilot."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent
for path in (ROOT, ROOT / "src", ROOT / "scripts", OUT):
    sys.path.insert(0, str(path))

from bolt_ace_step import CHECKPOINT_STEPS, AceStepBOLTRunner, prompt_from_dict  # noqa: E402
from bolt_core import SeedNamespace, action_key, append_jsonl, canonical_json_hash, read_jsonl, sha256_file  # noqa: E402
from bolt_scoring import BoltScorer, save_audio_once  # noqa: E402
from bolt_state import load_checkpoint_state, save_checkpoint_state  # noqa: E402


MANIFEST = OUT / "BOLT_PILOT_PROMPT_MANIFEST.jsonl"
RUNTIME = OUT / "BOLT_RUNTIME_FREEZE.json"
FORK_FREEZE = OUT / "BOLT_FORK_FREEZE.json"
GATE0_REPORT = OUT / "BOLT_GATE0_REPORT.md"
ROOT_LEDGER = OUT / "BOLT_ROOT_TRAJECTORY_LEDGER.jsonl"
STATE_LEDGER = OUT / "BOLT_CHECKPOINT_STATE_LEDGER.jsonl"
ACTION_LEDGER = OUT / "BOLT_ACTION_ATLAS_PILOT_LEDGER.jsonl"
ATTEMPT_DIR = OUT / "pilot_attempts"
AUDIO_DIR = OUT / "pilot_audio"
STATE_DIR = OUT / "pilot_states"
SEED_BASE = 2_060_000_000
ACTIONS = ("CONTINUE", "SWITCH_CONDITION", "FORK_LATENT", "RESTART_BASE", "RESTART_CONDITIONED")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def runtime_identity() -> dict[str, str]:
    record = json.loads(RUNTIME.read_text(encoding="utf-8"))
    if record.get("status") != "FROZEN_PARITY_PASS":
        raise RuntimeError("runtime parity has not passed")
    return {
        "model_hash": record["ace_step_source_manifest_sha256"],
        "checkpoint_hash": record["ace_step_checkpoint_manifest_sha256"],
        "scheduler_hash": record["scheduler_sha256"],
    }


def assert_gate0_pass() -> None:
    text = GATE0_REPORT.read_text(encoding="utf-8")
    if "GATE0_STATUS = PASS" not in text:
        raise RuntimeError("pilot launch blocked because Gate 0 has not passed")


def read_manifest() -> list[dict]:
    rows = read_jsonl(MANIFEST)
    if len(rows) != 48 or len({row["prompt_id"] for row in rows}) != 48:
        raise RuntimeError("pilot manifest cardinality mismatch")
    if any(not row["prompt_id"].startswith("dev_") for row in rows):
        raise RuntimeError("held-out prompt leakage in pilot manifest")
    return rows


def unique_rows(path: Path, key_function) -> dict[Any, dict]:
    grouped: dict[Any, list[dict]] = {}
    for row in read_jsonl(path):
        grouped.setdefault(key_function(row), []).append(row)
    duplicates = {key: rows for key, rows in grouped.items() if len(rows) > 1}
    if duplicates:
        raise RuntimeError(f"canonical ledger contains duplicate keys: {list(duplicates)[:3]}")
    return {key: rows[0] for key, rows in grouped.items()}


def root_key(row: dict) -> tuple[str, int]:
    return str(row["prompt_id"]), int(row["root_seed"])


def state_key(row: dict) -> tuple[str, int, int]:
    return str(row["prompt_id"]), int(row["root_seed"]), int(row["checkpoint_step"])


def verify_media(row: dict) -> None:
    path = ROOT / row["output_path"]
    if not path.is_file() or sha256_file(path) != row["output_sha256"]:
        raise RuntimeError(f"completed output missing or checksum mismatch: {path}")


def state_path(prompt_id: str, root_seed: int, checkpoint: int) -> Path:
    return STATE_DIR / prompt_id / f"seed{root_seed}__step{checkpoint:02d}.pt"


def root_audio_path(prompt_id: str, root_seed: int) -> Path:
    return AUDIO_DIR / prompt_id / f"seed{root_seed}" / "ROOT_CONTINUE.flac"


def action_audio_path(prompt_id: str, root_seed: int, checkpoint: int, action: str) -> Path:
    return AUDIO_DIR / prompt_id / f"seed{root_seed}" / f"step{checkpoint:02d}" / f"{action}.flac"


def base_record(prompt_row: dict, root_seed: int, worker: str) -> dict[str, Any]:
    return {
        "prompt_id": prompt_row["prompt_id"],
        "request_direction": prompt_row["request_direction"],
        "requested_vocal": int(prompt_row["requested_vocal"]),
        "stratum": prompt_row["stratum"],
        "design_weight": float(prompt_row["design_weight"]),
        "prompt_slot": int(prompt_row["prompt_slot"]),
        "root_seed": int(root_seed),
        "worker": worker,
        "gpu": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "host": socket.gethostname(),
        "manifest_sha256": sha256_file(MANIFEST),
        "environment_hash": json.loads(RUNTIME.read_text(encoding="utf-8"))["runtime_freeze_sha256"],
    }


def score_generated(
    scorer: BoltScorer,
    *,
    path: Path,
    result,
    prompt,
    requested_vocal: int,
) -> tuple[dict[str, Any], float]:
    started = time.time()
    scores = scorer.score(
        audio_path=path,
        waveform=result.waveform,
        sample_rate=result.sample_rate,
        prompt=prompt,
        requested_vocal=requested_vocal,
    )
    return scores, time.time() - started


def command_run(args: argparse.Namespace) -> int:
    assert_gate0_pass()
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("each BOLT worker requires exactly one visible GPU")
    if not 0 <= args.worker_index < args.num_workers:
        raise ValueError("worker index outside range")
    manifest = [
        row for row in read_manifest()
        if args.prompt_slot_start <= int(row["prompt_slot"]) < args.prompt_slot_end
        and (int(row["prompt_slot"]) - args.prompt_slot_start) % args.num_workers == args.worker_index
    ]
    namespace = SeedNamespace(SEED_BASE)
    eta_record = json.loads(FORK_FREEZE.read_text(encoding="utf-8"))
    if eta_record.get("status") != "FROZEN" or eta_record.get("selected_eta") is None:
        raise RuntimeError("fork eta is not frozen")
    fork_eta = float(eta_record["selected_eta"])
    worker_name = f"{socket.gethostname()}_w{args.worker_index}"
    attempt_ledger = ATTEMPT_DIR / f"{worker_name}.jsonl"
    root_done = unique_rows(ROOT_LEDGER, root_key)
    state_done = unique_rows(STATE_LEDGER, state_key)
    action_done = unique_rows(ACTION_LEDGER, action_key)
    runner = AceStepBOLTRunner(runtime_identity())
    scorer = BoltScorer()
    for prompt_row in manifest:
        prompt = prompt_from_dict(prompt_row["prompt"])
        root_indices = (args.root_index_filter,) if args.root_index_filter is not None else (0, 1)
        for root_index in root_indices:
            root_seed = int(prompt_row["root_seeds"][root_index])
            key = (prompt_row["prompt_id"], root_seed)
            root_record = root_done.get(key)
            try:
                if root_record is None:
                    result = runner.run_full(
                        prompt, seed=root_seed, requested_vocal=int(prompt_row["requested_vocal"]),
                        switched=False, capture_steps=CHECKPOINT_STEPS,
                    )
                    scores, score_seconds = score_generated(
                        scorer, path=root_audio_path(prompt.prompt_id, root_seed), result=result,
                        prompt=prompt, requested_vocal=int(prompt_row["requested_vocal"]),
                    )
                    if result.evpd_probe_tweedie is None:
                        raise RuntimeError("frozen sigma-0.8 EVPD probe state was not captured")
                    probe_started = time.time()
                    probe_waveform = runner.model.decode(
                        result.evpd_probe_tweedie.to(device=runner.device, dtype=runner.dtype)
                    )
                    evpd_probability = scorer.early_evpd_probability(
                        probe_waveform, int(result.sample_rate)
                    )
                    evpd_probe_seconds = time.time() - probe_started
                    root_record = {
                        **base_record(prompt_row, root_seed, worker_name),
                        "record_type": "root_trajectory",
                        "root_id": f"{prompt.prompt_id}__seed{root_seed}",
                        "root_index": root_index,
                        "condition_hash": result.condition_hash,
                        "transformer_forward_calls": result.nfe,
                        "scheduler_steps": result.scheduler_steps,
                        "cumulative_nfe_by_step": result.cumulative_nfe_by_step,
                        "gpu_wall_seconds": result.wall_seconds,
                        "cuda_event_seconds": result.cuda_seconds,
                        "scoring_seconds": score_seconds,
                        "corrected_evpd_probability": evpd_probability,
                        "corrected_evpd_threshold": float(scorer.evpd["threshold"]),
                        "corrected_evpd_decision": int(
                            evpd_probability >= float(scorer.evpd["threshold"])
                        ),
                        "corrected_evpd_probe_sigma": result.evpd_probe_sigma,
                        "corrected_evpd_probe_step": result.evpd_probe_step,
                        "corrected_evpd_probe_nfe": result.evpd_probe_nfe,
                        "corrected_evpd_probe_seconds": evpd_probe_seconds,
                        "corrected_evpd_model_sha256": scorer.evpd_hash,
                        **scores,
                        "output_path": relative(Path(scores["output_path"])),
                        "status": "PASS", "error": "", "timestamp": now(),
                    }
                    append_jsonl(ROOT_LEDGER, root_record)
                    root_done[key] = root_record
                    for checkpoint, state in result.checkpoints.items():
                        path = state_path(prompt.prompt_id, root_seed, checkpoint)
                        metadata = save_checkpoint_state(state, path, allow_existing=True)
                        state_record = {
                            **base_record(prompt_row, root_seed, worker_name),
                            "record_type": "checkpoint_state", "checkpoint_step": checkpoint,
                            "checkpoint_state_id": state.state_id,
                            "state_path": relative(path),
                            "state_file_sha256": metadata["state_file_sha256"],
                            "checkpoint_latent_sha256": metadata["latent_sha256"],
                            "model_output_sha256": metadata["model_output_sha256"],
                            "scheduler_index": metadata["scheduler_index"],
                            "timestep": metadata["timestep"], "sigma": metadata["sigma"],
                            "next_sigma": metadata["next_sigma"], "condition_hash": state.condition_hash,
                            "prefix_nfe": state.nfe_count, "prefix_scheduler_steps": state.scheduler_step_count,
                            "latent_dtype": metadata["latent_dtype"], "latent_shape": metadata["latent_shape"],
                            "status": "PASS", "error": "", "timestamp": now(),
                        }
                        append_jsonl(STATE_LEDGER, state_record)
                        state_done[state_key(state_record)] = state_record
                else:
                    verify_media(root_record)

                states = {}
                for checkpoint in CHECKPOINT_STEPS:
                    state_record = state_done.get((prompt.prompt_id, root_seed, checkpoint))
                    if state_record is None:
                        raise RuntimeError(f"missing checkpoint ledger row at step {checkpoint}")
                    path = ROOT / state_record["state_path"]
                    state, metadata = load_checkpoint_state(path)
                    if metadata["latent_sha256"] != state_record["checkpoint_latent_sha256"]:
                        raise RuntimeError("checkpoint latent hash drift")
                    states[checkpoint] = (state, state_record)

                for checkpoint in CHECKPOINT_STEPS:
                    state, state_record = states[checkpoint]
                    for action in ACTIONS:
                        key_action = (prompt.prompt_id, root_seed, checkpoint, action)
                        existing = action_done.get(key_action)
                        if existing is not None:
                            verify_media(existing)
                            continue
                        action_seed = None
                        condition_after = state.condition_hash
                        result = None
                        score_seconds = 0.0
                        if action == "CONTINUE":
                            scores = {
                                key: value for key, value in root_record.items()
                                if key in {
                                    "output_path", "output_sha256", "sample_rate", "duration_seconds",
                                    "rms", "near_silent", "valid", "promoted_instrument_sha256",
                                    "promoted_instrument_family", "demucs_score", "panns_score",
                                    "promoted_present", "label_b_satisfied",
                                    "calibrated_label_b_violation_probability", "calibration_model_hash",
                                    "common_robust_lcb", "clap_to_original_prompt", "common_quality_floor",
                                    "clap_prompt_floor", "common_quality_floor_pass", "clap_prompt_floor_pass",
                                    "quality_floor_status", "cqs", "gate_policy_hash", "common_scores",
                                }
                            }
                            action_nfe = int(root_record["transformer_forward_calls"]) - int(state_record["prefix_nfe"])
                            scheduler_steps = 30 - checkpoint
                            wall_seconds = 0.0
                            cuda_seconds = 0.0
                        elif action == "SWITCH_CONDITION":
                            result = runner.run_from_state(
                                state, prompt, requested_vocal=int(prompt_row["requested_vocal"]), switched=True,
                            )
                            condition_after = result.condition_hash
                            scores, score_seconds = score_generated(
                                scorer, path=action_audio_path(prompt.prompt_id, root_seed, checkpoint, action),
                                result=result, prompt=prompt, requested_vocal=int(prompt_row["requested_vocal"]),
                            )
                            action_nfe, scheduler_steps = result.nfe, result.scheduler_steps
                            wall_seconds, cuda_seconds = result.wall_seconds, result.cuda_seconds
                        elif action == "FORK_LATENT":
                            action_seed = namespace.fork_seed(int(prompt_row["prompt_slot"]), root_index, checkpoint)
                            result = runner.run_from_state(
                                state, prompt, requested_vocal=int(prompt_row["requested_vocal"]), switched=False,
                                fork_eta=fork_eta, fork_seed=action_seed,
                            )
                            scores, score_seconds = score_generated(
                                scorer, path=action_audio_path(prompt.prompt_id, root_seed, checkpoint, action),
                                result=result, prompt=prompt, requested_vocal=int(prompt_row["requested_vocal"]),
                            )
                            action_nfe, scheduler_steps = result.nfe, result.scheduler_steps
                            wall_seconds, cuda_seconds = result.wall_seconds, result.cuda_seconds
                        elif action in {"RESTART_BASE", "RESTART_CONDITIONED"}:
                            conditioned = action == "RESTART_CONDITIONED"
                            action_seed = namespace.restart_seed(
                                int(prompt_row["prompt_slot"]), root_index, checkpoint, conditioned
                            )
                            result = runner.run_full(
                                prompt, seed=action_seed, requested_vocal=int(prompt_row["requested_vocal"]),
                                switched=conditioned, capture_steps=(),
                            )
                            condition_after = result.condition_hash
                            scores, score_seconds = score_generated(
                                scorer, path=action_audio_path(prompt.prompt_id, root_seed, checkpoint, action),
                                result=result, prompt=prompt, requested_vocal=int(prompt_row["requested_vocal"]),
                            )
                            action_nfe, scheduler_steps = result.nfe, result.scheduler_steps
                            wall_seconds, cuda_seconds = result.wall_seconds, result.cuda_seconds
                        else:
                            raise AssertionError(action)

                        if action == "CONTINUE":
                            output_path = root_record["output_path"]
                        else:
                            output_path = relative(Path(scores["output_path"]))
                        outcome_id = canonical_json_hash(
                            {"prompt_id": prompt.prompt_id, "root_seed": root_seed,
                             "checkpoint_step": checkpoint, "action": action}
                        )[:24]
                        action_record = {
                            **base_record(prompt_row, root_seed, worker_name),
                            "record_type": "action_outcome", "action_outcome_id": outcome_id,
                            "root_index": root_index, "checkpoint_step": checkpoint,
                            "checkpoint_latent_hash": state_record["checkpoint_latent_sha256"],
                            "action": action, "action_seed": action_seed,
                            "condition_before": state.condition_hash, "condition_after": condition_after,
                            "fork_eta": fork_eta if action == "FORK_LATENT" else None,
                            "prefix_nfe": int(state_record["prefix_nfe"]),
                            "action_nfe": int(action_nfe),
                            "total_tree_edge_nfe": int(state_record["prefix_nfe"]) + int(action_nfe),
                            "prefix_scheduler_steps": checkpoint,
                            "action_scheduler_steps": scheduler_steps,
                            "output_path": output_path,
                            **{key: value for key, value in scores.items() if key != "output_path"},
                            "gpu_wall_seconds": wall_seconds, "cuda_event_seconds": cuda_seconds,
                            "scoring_seconds": score_seconds,
                            "status": "PASS", "error": "", "timestamp": now(),
                        }
                        append_jsonl(ACTION_LEDGER, action_record)
                        action_done[key_action] = action_record
            except Exception as exc:  # noqa: BLE001
                failure = {
                    **base_record(prompt_row, root_seed, worker_name),
                    "record_type": "worker_failure", "timestamp": now(), "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                append_jsonl(attempt_ledger, failure)
                raise
            append_jsonl(
                attempt_ledger,
                {**base_record(prompt_row, root_seed, worker_name), "record_type": "root_tree_complete",
                 "timestamp": now(), "status": "PASS", "action_rows": 15},
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-index", type=int, required=True)
    parser.add_argument("--num-workers", type=int, required=True)
    parser.add_argument("--prompt-slot-start", type=int, required=True)
    parser.add_argument("--prompt-slot-end", type=int, required=True)
    parser.add_argument("--root-index-filter", type=int, choices=(0, 1), default=None)
    return parser


if __name__ == "__main__":
    raise SystemExit(command_run(build_parser().parse_args()))
