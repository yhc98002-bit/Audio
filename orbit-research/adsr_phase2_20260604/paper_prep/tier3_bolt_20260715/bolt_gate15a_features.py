#!/usr/bin/env python3
"""Audit persisted BOLT states and extract hash-scoped preview features."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import socket
import time
from pathlib import Path
from typing import Any

import torch


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent

from bolt_ace_step import AceStepBOLTRunner, prompt_from_dict, waveform_validity  # noqa: E402
from bolt_core import (  # noqa: E402
    CHECKPOINT_STEPS,
    append_jsonl,
    canonical_json_hash,
    read_jsonl,
    sha256_file,
)
from bolt_pilot_worker import runtime_identity  # noqa: E402
from bolt_scoring import BoltScorer  # noqa: E402
from bolt_state import load_checkpoint_state, tensor_sha256  # noqa: E402


PROMPT_MANIFEST = OUT / "BOLT_PILOT_PROMPT_MANIFEST.jsonl"
STATE_LEDGER = OUT / "BOLT_CHECKPOINT_STATE_LEDGER.jsonl"
RUNTIME = OUT / "BOLT_RUNTIME_FREEZE.json"
STATE_AUDIT_CSV = OUT / "BOLT_GATE15A_STATE_AUDIT.csv"
STATE_AUDIT_REPORT = OUT / "BOLT_GATE15A_STATE_AUDIT.md"
FEATURE_SHARDS = OUT / "gate15a_feature_shards"
FEATURE_SMOKE = OUT / "gate15a_feature_smoke"
PREVIEW_DIR = OUT / "gate15a_previews"
FEATURE_LEDGER = OUT / "BOLT_GATE15A_STATE_FEATURES.jsonl"
FEATURE_REPORT = OUT / "BOLT_GATE15A_FEATURE_AUDIT.md"
EXPECTED_STATES = 48 * 2 * len(CHECKPOINT_STEPS)
FEATURE_SCHEMA = "bolt_gate15a_state_features_v1"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def state_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return str(row["prompt_id"]), int(row["root_seed"]), int(row["checkpoint_step"])


def load_prompts() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = read_jsonl(PROMPT_MANIFEST)
    if len(rows) != 48 or len({str(row["prompt_id"]) for row in rows}) != 48:
        raise RuntimeError("Gate 1.5A prompt-manifest cardinality mismatch")
    if any(not str(row["prompt_id"]).startswith("dev_") for row in rows):
        raise RuntimeError("non-development prompt in Gate 1.5A manifest")
    return rows, {str(row["prompt_id"]): row for row in rows}


def expected_keys(prompts: list[dict[str, Any]]) -> set[tuple[str, int, int]]:
    return {
        (str(row["prompt_id"]), int(seed), int(checkpoint))
        for row in prompts
        for seed in row["root_seeds"]
        for checkpoint in CHECKPOINT_STEPS
    }


def unique_state_rows(prompts: list[dict[str, Any]]) -> dict[tuple[str, int, int], dict[str, Any]]:
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    for row in read_jsonl(STATE_LEDGER):
        grouped.setdefault(state_key(row), []).append(row)
    duplicates = {key: values for key, values in grouped.items() if len(values) != 1}
    if duplicates:
        raise RuntimeError(f"duplicate checkpoint-state ledger keys: {list(duplicates)[:3]}")
    rows = {key: values[0] for key, values in grouped.items()}
    expected = expected_keys(prompts)
    if set(rows) != expected:
        missing = sorted(expected - set(rows))
        extra = sorted(set(rows) - expected)
        raise RuntimeError(f"checkpoint-state key mismatch: missing={missing[:3]} extra={extra[:3]}")
    return rows


def root_index(prompt_row: dict[str, Any], seed: int) -> int:
    seeds = [int(value) for value in prompt_row["root_seeds"]]
    if int(seed) not in seeds:
        raise RuntimeError(f"root seed {seed} is absent from prompt {prompt_row['prompt_id']}")
    return seeds.index(int(seed))


def verify_state(
    row: dict[str, Any], prompt_row: dict[str, Any]
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    path = ROOT / str(row["state_path"])
    state, metadata = load_checkpoint_state(path)
    checks = {
        "state_path": relative(path),
        "state_file_sha256": sha256_file(path),
        "latent_sha256": tensor_sha256(state.latent),
        "model_output_sha256": tensor_sha256(state.model_output),
        "prompt_id": state.prompt_id,
        "root_seed": int(state.root_seed),
        "checkpoint_step": int(state.completed_steps),
    }
    expected = {
        "state_file_sha256": str(row["state_file_sha256"]),
        "latent_sha256": str(row["checkpoint_latent_sha256"]),
        "model_output_sha256": str(row["model_output_sha256"]),
        "prompt_id": str(row["prompt_id"]),
        "root_seed": int(row["root_seed"]),
        "checkpoint_step": int(row["checkpoint_step"]),
    }
    for name, value in expected.items():
        if checks[name] != value:
            raise RuntimeError(f"state contract mismatch for {path}: {name}={checks[name]} != {value}")
    if metadata.get("state_file_sha256") != row["state_file_sha256"]:
        raise RuntimeError(f"sidecar/ledger file hash mismatch: {path}")
    if int(row["checkpoint_step"]) not in CHECKPOINT_STEPS:
        raise RuntimeError(f"unexpected checkpoint step: {row['checkpoint_step']}")
    index = root_index(prompt_row, int(row["root_seed"]))
    return state, metadata, {**checks, "root_index": index}


def write_csv_once(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(path)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def command_audit(_: argparse.Namespace) -> int:
    if STATE_AUDIT_CSV.exists() or STATE_AUDIT_REPORT.exists():
        raise FileExistsError("Gate 1.5A state audit outputs already exist")
    prompts, prompt_index = load_prompts()
    rows = unique_state_rows(prompts)
    actual_pt = set((OUT / "pilot_states").rglob("*.pt"))
    ledger_pt = {ROOT / str(row["state_path"]) for row in rows.values()}
    if actual_pt != ledger_pt:
        missing = sorted(str(path) for path in ledger_pt - actual_pt)
        extra = sorted(str(path) for path in actual_pt - ledger_pt)
        raise RuntimeError(f"checkpoint tensor inventory mismatch: missing={missing[:3]} extra={extra[:3]}")
    audit_rows = []
    for key in sorted(rows):
        row = rows[key]
        _, metadata, checks = verify_state(row, prompt_index[key[0]])
        audit_rows.append(
            {
                **checks,
                "sidecar_path": relative((ROOT / str(row["state_path"])).with_suffix(".pt.json")),
                "sidecar_sha256": sha256_file((ROOT / str(row["state_path"])).with_suffix(".pt.json")),
                "condition_hash": metadata["condition_hash"],
                "status": "PASS",
            }
        )
    if len(audit_rows) != EXPECTED_STATES:
        raise RuntimeError(f"state audit produced {len(audit_rows)}, expected {EXPECTED_STATES}")
    write_csv_once(STATE_AUDIT_CSV, audit_rows)
    STATE_AUDIT_REPORT.write_text(
        "# BOLT Gate 1.5A Persisted-State Audit\n\n"
        "STATE_AUDIT_STATUS = PASS\n"
        f"EXPECTED_STATES = {EXPECTED_STATES}\n"
        f"PRESENT_STATES = {len(audit_rows)}\n"
        "MISSING_STATES = 0\nDUPLICATE_STATES = 0\nHASH_ERRORS = 0\n\n"
        "Every canonical checkpoint tensor was loaded through `load_checkpoint_state`; file, "
        "latent, model-output, CPU RNG, CUDA RNG, and generator RNG hashes matched its sidecar. "
        "The `.pt` inventory exactly matched the checkpoint-state ledger, with no proxy "
        "substitution. Per-state evidence is in `BOLT_GATE15A_STATE_AUDIT.csv`.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "states": len(audit_rows)}, sort_keys=True))
    return 0


def preview_path(row: dict[str, Any], preview_root: Path = PREVIEW_DIR) -> Path:
    return preview_root / str(row["prompt_id"]) / (
        f"seed{int(row['root_seed'])}__step{int(row['checkpoint_step']):02d}.flac"
    )


def selected_feature_payload(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "feature_schema",
        "state_id",
        "prompt_id",
        "root_seed",
        "root_index",
        "checkpoint_step",
        "prefix_nfe",
        "remaining_budget_nfe",
        "request_direction",
        "requested_vocal",
        "risk_score_preexisting",
        "promoted_violation_rate_preexisting",
        "corrected_evpd_mean_risk_preexisting",
        "genre",
        "tempo_bin",
        "prompt_specificity",
        "structure_complexity",
        "language",
        "preview_demucs_score",
        "preview_panns_score",
        "preview_promoted_present",
        "preview_calibrated_violation_probability",
        "preview_clap_to_prompt",
        "preview_common_robust_lcb",
        "preview_output_sha256",
        "state_file_sha256",
        "latent_sha256",
        "promoted_instrument_sha256",
        "calibration_model_hash",
        "scoring_protocol_version",
    )
    return {key: row[key] for key in keys}


def feature_record(
    *,
    state_row: dict[str, Any],
    prompt_row: dict[str, Any],
    state: Any,
    checks: dict[str, Any],
    score: dict[str, Any],
    decode_seconds: float,
    score_seconds: float,
) -> dict[str, Any]:
    clap = score.get("clap_to_original_prompt")
    required_finite = {
        "preview_demucs_score": score.get("demucs_score"),
        "preview_panns_score": score.get("panns_score"),
        "preview_calibrated_violation_probability": score.get(
            "calibrated_label_b_violation_probability"
        ),
        "preview_clap_to_prompt": clap,
    }
    for name, value in required_finite.items():
        if value is None or not math.isfinite(float(value)):
            raise RuntimeError(f"nonfinite required state feature {name} for {state.state_id}: {value}")
    balance = prompt_row["balance"]
    record = {
        "feature_schema": FEATURE_SCHEMA,
        "state_id": state.state_id,
        "prompt_id": str(state_row["prompt_id"]),
        "root_seed": int(state_row["root_seed"]),
        "root_index": int(checks["root_index"]),
        "checkpoint_step": int(state_row["checkpoint_step"]),
        "checkpoint_fraction": float(int(state_row["checkpoint_step"]) / 30.0),
        "prefix_nfe": int(state_row["prefix_nfe"]),
        "remaining_budget_nfe": int(90 - int(state_row["prefix_nfe"])),
        "remaining_budget_fraction": float((90 - int(state_row["prefix_nfe"])) / 90.0),
        "request_direction": str(prompt_row["request_direction"]),
        "requested_vocal": int(prompt_row["requested_vocal"]),
        "stratum": str(prompt_row["stratum"]),
        "design_weight": float(prompt_row["design_weight"]),
        "risk_score_preexisting": float(prompt_row["risk_score_preexisting"]),
        "promoted_violation_rate_preexisting": float(prompt_row["promoted_violation_rate"]),
        "corrected_evpd_mean_risk_preexisting": float(prompt_row["corrected_evpd_mean_risk"]),
        "genre": str(balance["genre"]),
        "tempo_bin": str(balance["tempo"] if "tempo" in balance else balance["tempo_bin"]),
        "prompt_specificity": str(balance["prompt_specificity"]),
        "structure_complexity": str(balance["structure_complexity"]),
        "language": str(balance["language"]),
        "preview_demucs_score": float(score["demucs_score"]),
        "preview_panns_score": float(score["panns_score"]),
        "preview_promoted_present": int(score["promoted_present"]),
        "preview_calibrated_violation_probability": float(
            score["calibrated_label_b_violation_probability"]
        ),
        "preview_clap_to_prompt": float(clap),
        "preview_common_robust_lcb": (
            None if score.get("common_robust_lcb") is None else float(score["common_robust_lcb"])
        ),
        "preview_valid": bool(score["valid"]),
        "preview_near_silent": bool(score["near_silent"]),
        "preview_duration_seconds": float(score["duration_seconds"]),
        "preview_sample_rate": int(score["sample_rate"]),
        "preview_rms": float(score["rms"]),
        "preview_output_path": relative(Path(score["output_path"])),
        "preview_output_sha256": str(score["output_sha256"]),
        "state_path": str(state_row["state_path"]),
        "state_file_sha256": str(checks["state_file_sha256"]),
        "latent_sha256": str(checks["latent_sha256"]),
        "promoted_instrument_sha256": str(score["promoted_instrument_sha256"]),
        "calibration_model_hash": str(score["calibration_model_hash"]),
        "gate_policy_hash": str(score["gate_policy_hash"]),
        "scoring_protocol_version": str(score["scoring_protocol_version"]),
        "decode_wall_seconds": float(decode_seconds),
        "scoring_wall_seconds": float(score_seconds),
        "host": socket.gethostname(),
        "gpu": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "timestamp": now(),
        "status": "PASS",
        "error": "",
    }
    record["state_feature_hash"] = canonical_json_hash(selected_feature_payload(record))
    return record


def command_extract(args: argparse.Namespace) -> int:
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1 or not torch.cuda.is_available():
        raise RuntimeError("Gate 1.5A feature worker requires exactly one visible CUDA GPU")
    if not 0 <= args.worker_index < args.num_workers:
        raise ValueError("worker index outside range")
    prompts, prompt_index = load_prompts()
    state_rows = unique_state_rows(prompts)
    selected = [
        state_rows[key]
        for key in sorted(state_rows)
        if int(prompt_index[key[0]]["prompt_slot"]) % args.num_workers == args.worker_index
    ]
    if args.max_states is not None:
        selected = selected[: args.max_states]
    preview_root = Path(args.preview_root) if args.preview_root else PREVIEW_DIR
    if not preview_root.is_absolute():
        preview_root = ROOT / preview_root
    shard = Path(args.output_shard) if args.output_shard else (
        FEATURE_SHARDS / f"worker_{args.worker_index:02d}_of_{args.num_workers:02d}.jsonl"
    )
    if not shard.is_absolute():
        shard = ROOT / shard
    existing_rows = read_jsonl(shard)
    existing: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in existing_rows:
        key = state_key(row)
        if key in existing:
            raise RuntimeError(f"duplicate feature key already in shard {shard}: {key}")
        existing[key] = row
    runner = AceStepBOLTRunner(runtime_identity())
    scorer = BoltScorer()
    completed = 0
    recovered = 0
    for state_row in selected:
        key = state_key(state_row)
        previous = existing.get(key)
        if previous is not None:
            preview = ROOT / previous["preview_output_path"]
            if not preview.is_file() or sha256_file(preview) != previous["preview_output_sha256"]:
                raise RuntimeError(f"existing feature row references invalid preview: {key}")
            recovered += 1
            continue
        prompt_row = prompt_index[key[0]]
        state, _, checks = verify_state(state_row, prompt_row)
        seed = int(canonical_json_hash({"state_id": state.state_id})[:16], 16) % (2**31)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        decode_started = time.perf_counter()
        with torch.no_grad():
            waveform = runner.model.decode(
                state.latent.to(device=runner.device, dtype=runner.dtype)
            )
        torch.cuda.synchronize(runner.device)
        decode_seconds = time.perf_counter() - decode_started
        validity = waveform_validity(waveform, runner.model.sample_rate)
        if not validity["valid"]:
            raise RuntimeError(f"decoded checkpoint preview is invalid: {state.state_id}: {validity}")
        score_started = time.perf_counter()
        score = scorer.score(
            audio_path=preview_path(state_row, preview_root),
            waveform=waveform,
            sample_rate=runner.model.sample_rate,
            prompt=prompt_from_dict(prompt_row["prompt"]),
            requested_vocal=int(prompt_row["requested_vocal"]),
        )
        score_seconds = time.perf_counter() - score_started
        row = feature_record(
            state_row=state_row,
            prompt_row=prompt_row,
            state=state,
            checks=checks,
            score=score,
            decode_seconds=decode_seconds,
            score_seconds=score_seconds,
        )
        append_jsonl(shard, row)
        existing[key] = row
        completed += 1
        print(json.dumps({"state_id": state.state_id, "status": "PASS"}, sort_keys=True), flush=True)
    print(
        json.dumps(
            {
                "worker": args.worker_index,
                "num_workers": args.num_workers,
                "new": completed,
                "recovered": recovered,
                "shard": str(shard),
            },
            sort_keys=True,
        )
    )
    return 0


def command_merge(args: argparse.Namespace) -> int:
    if FEATURE_LEDGER.exists() or FEATURE_REPORT.exists():
        raise FileExistsError("canonical Gate 1.5A feature outputs already exist")
    prompts, _ = load_prompts()
    expected = expected_keys(prompts)
    grouped: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    shards = [FEATURE_SHARDS / f"worker_{index:02d}_of_{args.num_workers:02d}.jsonl" for index in range(args.num_workers)]
    missing_shards = [str(path) for path in shards if not path.is_file()]
    if missing_shards:
        raise RuntimeError(f"missing feature shards: {missing_shards}")
    for shard in shards:
        for row in read_jsonl(shard):
            grouped.setdefault(state_key(row), []).append(row)
    duplicates = {key: rows for key, rows in grouped.items() if len(rows) != 1}
    missing = expected - set(grouped)
    extra = set(grouped) - expected
    errors = [rows[0] for rows in grouped.values() if rows[0].get("status") != "PASS"]
    if duplicates or missing or extra or errors:
        raise RuntimeError(
            f"feature merge blocked: duplicates={len(duplicates)} missing={len(missing)} "
            f"extra={len(extra)} errors={len(errors)}"
        )
    rows = [grouped[key][0] for key in sorted(grouped)]
    instrument_hashes = {row["promoted_instrument_sha256"] for row in rows}
    calibration_hashes = {row["calibration_model_hash"] for row in rows}
    protocol_versions = {row["scoring_protocol_version"] for row in rows}
    for row in rows:
        preview = ROOT / row["preview_output_path"]
        if not preview.is_file() or sha256_file(preview) != row["preview_output_sha256"]:
            raise RuntimeError(f"preview checksum mismatch during merge: {preview}")
        if canonical_json_hash(selected_feature_payload(row)) != row["state_feature_hash"]:
            raise RuntimeError(f"state-feature hash mismatch: {row['state_id']}")
    with FEATURE_LEDGER.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    FEATURE_REPORT.write_text(
        "# BOLT Gate 1.5A State-Feature Audit\n\n"
        "STATE_FEATURE_STATUS = PASS\n"
        f"EXPECTED_STATE_FEATURES = {EXPECTED_STATES}\n"
        f"STATE_FEATURES = {len(rows)}\n"
        "MISSING_STATE_FEATURES = 0\nDUPLICATE_STATE_FEATURES = 0\n"
        "FEATURE_ERRORS = 0\nINVALID_PREVIEWS = 0\n\n"
        f"Promoted-instrument hashes: `{sorted(instrument_hashes)}`. Calibration hashes: "
        f"`{sorted(calibration_hashes)}`. Scoring protocols: `{sorted(protocol_versions)}`.\n\n"
        "Every feature row is bound to the persisted state-file and latent hashes and to a "
        "decoded-preview SHA-256. The feature extractor did not import or read the action-outcome "
        "ledger. Preview common-quality values are retained for audit but excluded from both "
        "cross-fitted policy models.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "features": len(rows)}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.set_defaults(func=command_audit)
    extract = sub.add_parser("extract")
    extract.add_argument("--worker-index", type=int, required=True)
    extract.add_argument("--num-workers", type=int, required=True)
    extract.add_argument("--max-states", type=int)
    extract.add_argument("--output-shard")
    extract.add_argument("--preview-root")
    extract.set_defaults(func=command_extract)
    merge = sub.add_parser("merge")
    merge.add_argument("--num-workers", type=int, required=True)
    merge.set_defaults(func=command_merge)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
