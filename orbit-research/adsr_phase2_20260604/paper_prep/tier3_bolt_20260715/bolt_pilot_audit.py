#!/usr/bin/env python3
"""Strict integrity audit for the frozen 48-prompt BOLT pilot atlas."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import soundfile as sf


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))

from bolt_core import (  # noqa: E402
    ACTIONS,
    CHECKPOINT_STEPS,
    action_key,
    audit_action_rows,
    expected_action_keys,
    read_jsonl,
    sha256_file,
)


MANIFEST = OUT / "BOLT_PILOT_PROMPT_MANIFEST.jsonl"
ROOT_LEDGER = OUT / "BOLT_ROOT_TRAJECTORY_LEDGER.jsonl"
STATE_LEDGER = OUT / "BOLT_CHECKPOINT_STATE_LEDGER.jsonl"
ACTION_LEDGER = OUT / "BOLT_ACTION_ATLAS_PILOT_LEDGER.jsonl"
AUDIT = OUT / "BOLT_ACTION_ATLAS_PILOT_AUDIT.md"
SUMMARY = OUT / "BOLT_ACTION_ATLAS_PILOT_SUMMARY.csv"

REQUIRED_ACTION_FIELDS = {
    "action_outcome_id", "prompt_id", "request_direction", "stratum", "design_weight",
    "root_seed", "checkpoint_step", "checkpoint_latent_hash", "action", "condition_before",
    "condition_after", "prefix_nfe", "action_nfe", "total_tree_edge_nfe", "output_path",
    "output_sha256", "sample_rate", "duration_seconds", "near_silent", "label_b_satisfied",
    "demucs_score", "panns_score", "calibrated_label_b_violation_probability",
    "common_robust_lcb", "clap_to_original_prompt", "quality_floor_status", "cqs",
    "gpu_wall_seconds", "gpu", "worker", "status", "error",
}


def unique_index(rows: list[dict], key_fn, name: str) -> tuple[dict, list]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[key_fn(row)].append(row)
    duplicates = sorted(key for key, group in groups.items() if len(group) != 1)
    return {key: group[0] for key, group in groups.items()}, duplicates


def media_check(rows: list[dict]) -> tuple[list[str], int]:
    errors: list[str] = []
    checked: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("output_path")), str(row.get("output_sha256")))
        if key in checked:
            continue
        checked.add(key)
        path = ROOT / key[0]
        if not path.is_file():
            errors.append(f"missing:{key[0]}")
            continue
        if sha256_file(path) != key[1]:
            errors.append(f"sha256:{key[0]}")
            continue
        try:
            info = sf.info(str(path))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"decode:{key[0]}:{type(exc).__name__}")
            continue
        if info.samplerate <= 0 or info.duration <= 1.0 or info.frames <= 0:
            errors.append(f"invalid:{key[0]}")
    return errors, len(checked)


def write_summary(rows: list[dict]) -> None:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["stratum"]), str(row["action"]))].append(row)
    fields = [
        "stratum", "action", "rows", "cqs_rate", "label_b_satisfaction_rate",
        "quality_floor_pass_rate", "mean_total_tree_edge_nfe", "mean_wall_seconds",
    ]
    with SUMMARY.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for (stratum, action), group in sorted(grouped.items()):
            writer.writerow(
                {
                    "stratum": stratum,
                    "action": action,
                    "rows": len(group),
                    "cqs_rate": sum(int(row["cqs"]) for row in group) / len(group),
                    "label_b_satisfaction_rate": sum(int(row["label_b_satisfied"]) for row in group) / len(group),
                    "quality_floor_pass_rate": sum(row["quality_floor_status"] == "PASS" for row in group) / len(group),
                    "mean_total_tree_edge_nfe": sum(int(row["total_tree_edge_nfe"]) for row in group) / len(group),
                    "mean_wall_seconds": sum(float(row["gpu_wall_seconds"] or 0.0) for row in group) / len(group),
                }
            )


def main() -> int:
    if AUDIT.exists() or SUMMARY.exists():
        raise FileExistsError("pilot audit outputs already exist; never overwrite an experiment audit")
    prompts = read_jsonl(MANIFEST)
    roots = read_jsonl(ROOT_LEDGER)
    states = read_jsonl(STATE_LEDGER)
    actions = read_jsonl(ACTION_LEDGER)
    prompt_ids = {str(row["prompt_id"]) for row in prompts}
    expected_roots = {
        (str(row["prompt_id"]), int(seed)) for row in prompts for seed in row["root_seeds"]
    }
    expected_states = {
        (prompt_id, seed, checkpoint)
        for prompt_id, seed in expected_roots for checkpoint in CHECKPOINT_STEPS
    }
    root_index, root_duplicates = unique_index(
        roots, lambda row: (str(row["prompt_id"]), int(row["root_seed"])), "root"
    )
    state_index, state_duplicates = unique_index(
        states,
        lambda row: (str(row["prompt_id"]), int(row["root_seed"]), int(row["checkpoint_step"])),
        "state",
    )
    action_audit = audit_action_rows(actions, expected_action_keys(prompts))

    errors: list[str] = []
    if len(prompts) != 48 or len(prompt_ids) != 48:
        errors.append("prompt_manifest_cardinality")
    if any(not prompt_id.startswith("dev_") for prompt_id in prompt_ids):
        errors.append("prompt_leakage")
    if set(root_index) != expected_roots or root_duplicates:
        errors.append("root_key_audit")
    if set(state_index) != expected_states or state_duplicates:
        errors.append("checkpoint_key_audit")
    if action_audit["status"] != "PASS":
        errors.append("action_key_audit")
    if any(row.get("status") != "PASS" or row.get("error") not in ("", None) for row in roots + states + actions):
        errors.append("failed_rows")
    missing_fields = [action_key(row) for row in actions if REQUIRED_ACTION_FIELDS - set(row)]
    if missing_fields:
        errors.append("missing_action_fields")
    invalid_numbers = [
        action_key(row) for row in actions
        if not math.isfinite(float(row["demucs_score"]))
        or not math.isfinite(float(row["panns_score"]))
        or int(row["prefix_nfe"]) <= 0
        or int(row["action_nfe"]) <= 0
        or int(row["total_tree_edge_nfe"]) != int(row["prefix_nfe"]) + int(row["action_nfe"])
    ]
    if invalid_numbers:
        errors.append("invalid_scientific_or_accounting_field")

    structural_errors = []
    for row in actions:
        key = (str(row["prompt_id"]), int(row["root_seed"]), int(row["checkpoint_step"]))
        state = state_index.get(key)
        root = root_index.get(key[:2])
        if not state or not root or row["checkpoint_latent_hash"] != state["checkpoint_latent_sha256"]:
            structural_errors.append(action_key(row))
            continue
        action = row["action"]
        if action == "CONTINUE" and row["output_sha256"] != root["output_sha256"]:
            structural_errors.append(action_key(row))
        if action == "SWITCH_CONDITION" and row["condition_before"] == row["condition_after"]:
            structural_errors.append(action_key(row))
        if action in {"CONTINUE", "FORK_LATENT"} and row["condition_before"] != row["condition_after"]:
            structural_errors.append(action_key(row))
        if action == "FORK_LATENT" and row.get("fork_eta") is None:
            structural_errors.append(action_key(row))
    if structural_errors:
        errors.append("state_action_contract")

    media_errors, unique_media = media_check(roots + actions)
    if media_errors:
        errors.append("media_integrity")
    if not errors:
        write_summary(actions)
    status = "PASS" if not errors else "FAIL"
    AUDIT.write_text(
        "# BOLT Pilot Action Atlas Audit\n\n"
        f"PILOT_AUDIT_STATUS = {status}\n\n"
        f"ROOT_TRAJECTORIES = {len(roots)}\n"
        f"CHECKPOINT_STATES = {len(states)}\n"
        f"PILOT_ACTION_OUTCOMES = {len(actions)}\n"
        f"MISSING_ACTION_KEYS = {len(action_audit['missing'])}\n"
        f"DUPLICATE_ACTION_KEYS = {len(action_audit['duplicates'])}\n"
        f"CONFLICTING_ACTION_KEYS = {len(action_audit['conflicts'])}\n"
        f"FAILED_ACTION_ROWS = {len(action_audit['errors'])}\n\n"
        f"Unique decoded media audited: `{unique_media}`. Media errors: `{len(media_errors)}`.\n\n"
        f"Manifest SHA256: `{sha256_file(MANIFEST)}`. Root ledger SHA256: `{sha256_file(ROOT_LEDGER)}`. "
        f"Checkpoint ledger SHA256: `{sha256_file(STATE_LEDGER)}`. Action ledger SHA256: `{sha256_file(ACTION_LEDGER)}`.\n\n"
        "All three deterministic CONTINUE records per root remain in the state/action ledger. "
        "They share one terminal media hash and must be deduplicated in oracle leaf accounting.\n\n"
        "## Errors\n\n" + ("None.\n" if not errors else "\n".join(f"- {item}" for item in errors) + "\n"),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "errors": errors, "counts": [len(roots), len(states), len(actions)]}))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
