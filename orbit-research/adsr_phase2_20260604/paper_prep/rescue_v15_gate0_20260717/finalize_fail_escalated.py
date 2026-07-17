#!/usr/bin/env python3
"""Construct the bounded FAIL_ESCALATED Gate-0 evidence bundle.

This file is reporting-only. It never initializes a model or runs inference.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

from v15_gate0_runtime import (
    EXPECTED_DEPENDENCY_SHA256,
    EXPECTED_XL_SHA256,
    MODEL_CACHE_ROOT,
    MODEL_CONFIG_ID,
    MODEL_ID,
    MODELSCOPE_REVISION,
    REPO_ROOT,
    RUN_ROOT,
    RUNTIME_APG_CODE_SHA256,
    RUNTIME_CONFIG_CODE_SHA256,
    RUNTIME_MODEL_CODE_SHA256,
    SOURCE_ARCHIVE_SHA256,
    SOURCE_COMMIT,
    SOURCE_ROOT,
    TASK_DIR,
    TEXT_ENCODER_ID,
    TEXT_ENCODER_WEIGHT_REVISION,
    append_ledger,
    atomic_json,
    atomic_text,
    now_utc,
    sha256_file,
)


DIAGNOSIS_PATH = TASK_DIR / "V15_TERMINAL_DIAGNOSIS.json"
FROZEN_FORK_PATH = TASK_DIR / "V15_FORK_FROZEN.json"
REFERENCE_RECORD = RUN_ROOT / "records/calibration_reference/cal_v15g0_p00_seed2072000017.json"
STATE_16 = RUN_ROOT / "states/cal_v15g0_p00_seed2072000016/step_20.pt"
STATE_17 = RUN_ROOT / "states/cal_v15g0_p00_seed2072000017/step_20.pt"


TERMINAL_STATUSES = {
    "MODEL_PROVENANCE_STATUS": "PASS",
    "ENVIRONMENT_STATUS": "PASS",
    "STATE_CONTRACT_STATUS": "FAIL",
    "RESUME_EQUIVALENCE_STATUS": "FAIL",
    "CONDITION_SWITCH_STATUS": "FAIL",
    "FORK_STATUS": "FAIL",
    "ACTUAL_NFE_STATUS": "PASS",
    "TRUE_ROLLOVER_STATUS": "FAIL",
    "COMPLETION_RESERVE_STATUS": "FAIL",
    "V15_GATE0_STATUS": "FAIL_ESCALATED",
}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f"immutable output exists: {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def diagnose() -> dict:
    if not REFERENCE_RECORD.exists() or not STATE_16.exists() or not STATE_17.exists():
        raise RuntimeError("bounded calibration evidence is incomplete")
    reference = json.loads(REFERENCE_RECORD.read_text(encoding="utf-8"))
    nfe = reference["nfe"]
    if nfe["transformer_forward_calls"] != 50 or nfe["scheduler_euler_updates"] != 50:
        raise RuntimeError("calibration reference does not prove 50-call full cost")
    logs = {
        name: TASK_DIR / "logs" / name
        for name in (
            "calibration_an29_gpu0.log",
            "calibration_an29_gpu0_retry1.log",
            "calibration_an29_gpu0_retry2.log",
        )
    }
    if not all(path.exists() for path in logs.values()):
        raise RuntimeError("bounded diagnostic logs are incomplete")
    diagnosis = {
        "status": "FAIL_ESCALATED",
        "terminal_component": "restartable continuation / fork calibration",
        "effort_cap_applied": True,
        "main_controls_launched": False,
        "constraint_axis_launched": False,
        "tempo_axis_launched": False,
        "policy_training_launched": False,
        "model_identity": f"{MODEL_ID}@{MODELSCOPE_REVISION}",
        "model_is_turbo": False,
        "measured_full_generation_nfe": 50,
        "failure_sequence": [
            {
                "attempt": "initial calibration invocation",
                "result": "stopped before model load",
                "cause": "handler resolved an absent nested checkpoints directory and entered an offline auto-download path",
                "impact": "DNS failed; zero model bytes acquired; zero generation",
                "bounded_action": "one exact-cache/offline environment repair",
            },
            {
                "attempt": "calibration seed 2072000016",
                "result": "uninterrupted 50-NFE reference and step-20 state completed; reporting stopped",
                "cause": "native generate_audio returned a dict containing target_latents while the harness treated it as a tensor",
                "impact": "state retained; no final audio artifact written",
                "bounded_action": "one native-output state-harness repair",
            },
            {
                "attempt": "calibration seed 2072000017",
                "result": "uninterrupted 50-NFE reference, valid audio, and step-20 state completed; first fork continuation stopped before a transformer call",
                "cause": "native continuation requires timesteps as a torch.Tensor; harness supplied the frozen suffix as a list",
                "impact": "no perturbation frozen; no main controls or rollover launched",
                "bounded_action": "stop under B1; no second state-harness repair",
            },
        ],
        "retained_evidence": {
            "reference_record": str(REFERENCE_RECORD),
            "reference_record_sha256": sha256_file(REFERENCE_RECORD),
            "state_seed16": str(STATE_16),
            "state_seed16_sha256": sha256_file(STATE_16),
            "state_seed17": str(STATE_17),
            "state_seed17_sha256": sha256_file(STATE_17),
            "valid_audio_seed17": reference["artifacts"]["wav_path"],
            "valid_audio_seed17_sha256": reference["artifacts"]["wav_sha256"],
            "diagnostic_logs": {
                name: {"path": str(path), "sha256": sha256_file(path)}
                for name, path in logs.items()
            },
        },
        "runtime_source_sync": {
            "source_commit": SOURCE_COMMIT,
            "model_code_sha256": RUNTIME_MODEL_CODE_SHA256,
            "apg_code_sha256": RUNTIME_APG_CODE_SHA256,
            "config_code_sha256": RUNTIME_CONFIG_CODE_SHA256,
            "note": "The official handler synchronized three small runtime code files from the pinned source tree before load. Weight shards were not modified.",
        },
        "genuine_pi_decisions": [
            "Authorize the targeted tensor-timestep continuation fix and a fresh bounded v1.5 Gate-0 dispatch.",
            "Revert the tempo axis to ACE-Step v1 primitives already proven.",
        ],
        "created_utc": now_utc(),
    }
    atomic_json(DIAGNOSIS_PATH, diagnosis)
    atomic_json(
        FROZEN_FORK_PATH,
        {
            "status": "FAIL_ESCALATED",
            "epsilon": None,
            "grid": [1e-5, 3e-5, 1e-4, 3e-4, 1e-3],
            "thresholds_changed": False,
            "reason": "Continuation stopped before the first calibration fork forward call; no perturbation was frozen.",
            "diagnosis": DIAGNOSIS_PATH.name,
        },
    )
    append_ledger(
        {
            "event": "gate0_effort_cap_terminal",
            "status": "FAIL_ESCALATED",
            "terminal_component": diagnosis["terminal_component"],
            "diagnosis_path": str(DIAGNOSIS_PATH),
            "diagnosis_sha256": sha256_file(DIAGNOSIS_PATH),
            "main_controls_launched": False,
        }
    )
    return diagnosis


def finalize() -> dict:
    diagnosis = json.loads(DIAGNOSIS_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_RECORD.read_text(encoding="utf-8"))
    tests = json.loads((TASK_DIR / "V15_TEST_RESULTS.json").read_text(encoding="utf-8"))
    statuses = dict(TERMINAL_STATUSES)
    statuses["TEST_SUITE_STATUS"] = "PASS" if tests.get("pass") else "FAIL"

    write_csv(
        TASK_DIR / "V15_RESUME_EQUIVALENCE.csv",
        ["required_controls", "completed_controls", "status", "reason", "evidence"],
        [{
            "required_controls": 64,
            "completed_controls": 0,
            "status": "FAIL",
            "reason": "bounded calibration continuation failed before a remaining-step forward call; main controls were not launched",
            "evidence": DIAGNOSIS_PATH.name,
        }],
    )
    write_csv(
        TASK_DIR / "V15_CONDITION_SWITCH.csv",
        ["required_controls", "completed_controls", "status", "reason", "evidence"],
        [{
            "required_controls": 64,
            "completed_controls": 0,
            "status": "FAIL",
            "reason": "not launched after the bounded restart/fork prerequisite failed",
            "evidence": DIAGNOSIS_PATH.name,
        }],
    )
    write_csv(
        TASK_DIR / "V15_FORK_CALIBRATION.csv",
        ["seed", "checkpoint_step", "epsilon", "transformer_forward_calls", "status", "reason", "state_path", "state_sha256"],
        [{
            "seed": 2072000017,
            "checkpoint_step": 20,
            "epsilon": "1e-5 (first preregistered candidate; not executed)",
            "transformer_forward_calls": 0,
            "status": "FAIL_ESCALATED",
            "reason": "native continuation rejected list timesteps before the first transformer call",
            "state_path": str(STATE_17),
            "state_sha256": sha256_file(STATE_17),
        }],
    )
    nfe = reference["nfe"]
    write_csv(
        TASK_DIR / "V15_NFE_ACCOUNTING.csv",
        [
            "operation", "seed", "transformer_forward_calls", "scheduler_object_calls",
            "scheduler_euler_updates", "diffusion_gpu_ms", "diffusion_wall_sec",
            "decoder_gpu_ms", "decoder_wall_sec", "prefix_forward_calls",
            "continuation_forward_calls", "valid_audio", "status",
        ],
        [
            {
                "operation": "calibration_uninterrupted_reference",
                "seed": 2072000017,
                "transformer_forward_calls": nfe["transformer_forward_calls"],
                "scheduler_object_calls": nfe["scheduler_object_calls"],
                "scheduler_euler_updates": nfe["scheduler_euler_updates"],
                "diffusion_gpu_ms": nfe["diffusion_gpu_ms"],
                "diffusion_wall_sec": nfe["diffusion_wall_sec"],
                "decoder_gpu_ms": nfe["decoder_gpu_ms"],
                "decoder_wall_sec": nfe["decoder_wall_sec"],
                "prefix_forward_calls": nfe["prefix_forward_calls"],
                "continuation_forward_calls": 0,
                "valid_audio": reference["validity"]["valid"],
                "status": "PASS",
            },
            {
                "operation": "fork_continuation_preflight",
                "seed": 2072000017,
                "transformer_forward_calls": 0,
                "scheduler_object_calls": 0,
                "scheduler_euler_updates": 0,
                "diffusion_gpu_ms": 0,
                "diffusion_wall_sec": 0,
                "decoder_gpu_ms": 0,
                "decoder_wall_sec": 0,
                "prefix_forward_calls": 20,
                "continuation_forward_calls": 0,
                "valid_audio": False,
                "status": "FAIL_ESCALATED",
            },
        ],
    )

    atomic_text(
        TASK_DIR / "V15_MODEL_PROVENANCE.md",
        f"""# ACE-Step v1.5 XL-SFT Model Provenance

MODEL_PROVENANCE_STATUS = PASS

- Exact model: `{MODEL_ID}` / `{MODEL_CONFIG_ID}`; `is_turbo=false`.
- ModelScope revision: `{MODELSCOPE_REVISION}`.
- Source repository commit: `{SOURCE_COMMIT}`; archive SHA-256 `{SOURCE_ARCHIVE_SHA256}`.
- Four XL-SFT weight shards: exact local/API hashes in `V15_MODEL_CHECKSUMS.tsv`.
- VAE weight SHA-256: `{EXPECTED_DEPENDENCY_SHA256['vae/diffusion_pytorch_model.safetensors']}`.
- Text encoder: `{TEXT_ENCODER_ID}`, weight-file revision `{TEXT_ENCODER_WEIGHT_REVISION}`, SHA-256 `{EXPECTED_DEPENDENCY_SHA256['Qwen3-Embedding-0.6B/model.safetensors']}`. Tokenizer/config hashes are individually frozen in `V15_PROVENANCE.json`.
- Runtime scheduler/model code: source-synced SHA-256 `{RUNTIME_MODEL_CODE_SHA256}`. Acquired ModelScope remote-code SHA-256: `{EXPECTED_XL_SHA256['modeling_acestep_v15_xl_base.py']}`.
- Sampler: 50 steps, CFG 7.0, shift 1.0, inline Euler ODE, ADG off, DCW off, 15 s at 48 kHz.
- Acquisition occurred on the login node through the approved proxy, ModelScope first. The failed compute-node auto-download path acquired zero bytes.

Evidence: `V15_PROVENANCE.json`, `V15_MODEL_CHECKSUMS.tsv`, `V15_TERMINAL_DIAGNOSIS.json`.
""",
    )
    runtime = reference["runtime"]
    atomic_text(
        TASK_DIR / "V15_ENVIRONMENT_REPORT.md",
        f"""# ACE-Step v1.5 Gate-0 Environment

ENVIRONMENT_STATUS = PASS

- Node: `{runtime['node']}`; physical placement command selected an29 GPU 0; TP1; one replica for bounded calibration.
- GPU: `{runtime['gpu']['name']}`, capability `{runtime['gpu']['capability']}`, memory `{runtime['gpu']['total_memory']}` bytes.
- Python: `{runtime['python']}`.
- torch: `{runtime['torch']}`; CUDA runtime `{runtime['torch_cuda']}`; cuDNN `{runtime['cudnn']}`.
- transformers: `{runtime['packages']['transformers']}`; torchaudio: `{runtime['packages']['torchaudio']}`; diffusers: `{runtime['packages']['diffusers']}`.
- Dtype: `{reference['model_identity']['dtype']}`; attention: `{reference['model_identity']['attention']}`.
- Source: `{SOURCE_ROOT}`; exact runtime code hashes are in `V15_TERMINAL_DIAGNOSIS.json`.

The initial wrong cache resolution stopped before model load. The repaired offline initializer loaded the exact local non-Turbo XL-SFT, VAE, and Qwen encoder without compute-node acquisition.
""",
    )
    atomic_text(
        TASK_DIR / "V15_STATE_CONTRACT.md",
        f"""# V15 Checkpoint-State Contract

STATE_CONTRACT_STATUS = FAIL

Two diagnostic step-20 states were retained. They include latent, scheduler/timestep/sigma state, native decoder cache, model-output state, APG momentum, conditioning payload, prompt/root seed, Python/NumPy/torch RNG state, dtype/shape, and model/runtime hashes.

The seed-17 state file is `{STATE_17}` with SHA-256 `{sha256_file(STATE_17)}`. Its latent and cache hashes were recorded at capture. Separate-process continuation was invoked, but the native API rejected the list-valued timestep suffix before any transformer forward call. Therefore restartability, exact continuation, and 64/64 equivalence are not established.

No threshold was relaxed and no failed state was overwritten.
""",
    )
    atomic_text(
        TASK_DIR / "V15_TRUE_ROLLOVER_REPORT.md",
        """# V15 True Global Rollover

TRUE_ROLLOVER_STATUS = FAIL
COMPLETION_RESERVE_STATUS = FAIL

The full-generation cost was directly measured as 50 transformer calls, so the specified demonstration budget would be 100 calls. The restart/fork prerequisite failed under the bounded effort cap before main controls; consequently no real global-pool rollover demonstration was launched. Unit and synthetic controller-integration tests pass, but they are not substituted for the required model-backed demonstration.

Evidence: `V15_NFE_ACCOUNTING.csv`, `V15_TEST_RESULTS.json`, `V15_TERMINAL_DIAGNOSIS.json`.
""",
    )

    current_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    lines = ["# ACE-Step v1.5 BOLT Gate 0", ""]
    order = [
        "MODEL_PROVENANCE_STATUS", "ENVIRONMENT_STATUS", "STATE_CONTRACT_STATUS",
        "RESUME_EQUIVALENCE_STATUS", "CONDITION_SWITCH_STATUS", "FORK_STATUS",
        "ACTUAL_NFE_STATUS", "TRUE_ROLLOVER_STATUS", "COMPLETION_RESERVE_STATUS",
        "V15_GATE0_STATUS", "TEST_SUITE_STATUS",
    ]
    lines.extend(f"{key} = {statuses[key]}" for key in order)
    lines.extend(
        [
            "",
            f"MODEL_IDENTITY = {MODEL_ID}@{MODELSCOPE_REVISION} (config={MODEL_CONFIG_ID}, is_turbo=false)",
            "MEASURED_FULL_GENERATION_NFE = 50 transformer forward calls; 50 inline Euler updates; 0 scheduler-object calls",
            "",
            "## Evidence",
            "",
            "evidence: `V15_MODEL_PROVENANCE.md`, `V15_MODEL_CHECKSUMS.tsv`, `V15_PROVENANCE.json`",
            "evidence: `V15_ENVIRONMENT_REPORT.md`, `V15_LOGIN_ENVIRONMENT.json`",
            "evidence: `V15_STATE_CONTRACT.md`, `V15_RESUME_EQUIVALENCE.csv`, `V15_TERMINAL_DIAGNOSIS.json`",
            "evidence: `V15_CONDITION_SWITCH.csv`, `V15_FORK_CALIBRATION.csv`, `V15_FORK_FROZEN.json`",
            "evidence: `V15_NFE_ACCOUNTING.csv`, `V15_TRUE_ROLLOVER_REPORT.md`",
            "evidence: `V15_TEST_RESULTS.json`, `V15_APPEND_ONLY_LEDGER.jsonl`, `V15_CHECKSUMS.tsv`",
            "",
            "## Commits and tests",
            "",
            "- Seed/preregistration commit: `788e366`.",
            "- Harness commit: `6465750`.",
            "- Provenance commit: `f6883b1`.",
            "- Offline-cache repair commit: `5e0a994`.",
            "- Native-output repair commit: `abe628b`.",
            f"- Evidence-base commit at construction: `{current_commit}`.",
            f"- Focused tests: `{tests['focused']['summary']}`.",
            f"- Repository suite: `{tests['full_suite']['summary']}`.",
            "",
            "## Bounded terminal diagnosis",
            "",
            "The second bounded state-harness attempt failed before the first continuation transformer call because native `generate_audio` requires the timestep suffix as a tensor, while the harness supplied a list. Per B1, no second repair, 64-control run, rollover run, or scientific axis was launched.",
            "",
            "## Genuine PI decisions",
            "",
            "1. Authorize the targeted tensor-timestep continuation fix and a fresh bounded v1.5 Gate-0 dispatch.",
            "2. Revert the tempo axis to ACE-Step v1 primitives already proven.",
            "",
            "No constraint-axis experiment, tempo experiment, policy training, or vocal/instrumental scientific claim was run. Legacy BOLT and W2 evidence were not modified.",
        ]
    )
    atomic_text(TASK_DIR / "V15_GATE0_REPORT.md", "\n".join(lines) + "\n")

    manifest = {
        "run_id": "v15_gate0_20260717",
        "branch": "codex/bolt-v15-gate0-20260717",
        "model_identity": f"{MODEL_ID}@{MODELSCOPE_REVISION}",
        "node": "an29",
        "gpu_ids": [0],
        "tp_width": 1,
        "replica_count": 1,
        "placement_justification": "Bounded calibration only; XL-SFT fits one A800 at TP1.",
        "config_hash": sha256_file(TASK_DIR / "V15_GATE0_PREREGISTRATION.json"),
        "seed_namespace": "2072000000..2072000063",
        "seeds_used": [2072000016, 2072000017],
        "artifact_path": str(RUN_ROOT),
        "measured_full_generation_nfe": 50,
        "statuses": statuses,
        "deviations": diagnosis["failure_sequence"],
        "commands": [
            "python run_v15_gate0.py provenance",
            "CUDA_VISIBLE_DEVICES=0 python run_v15_gate0.py calibrate (bounded attempts; terminally stopped)",
            "pytest -q test_v15_gate0.py",
            "pytest -q",
            "python finalize_fail_escalated.py finalize",
        ],
        "finalized_utc": now_utc(),
    }
    atomic_json(TASK_DIR / "V15_RUN_MANIFEST.json", manifest)
    append_ledger({"event": "fail_escalated_bundle_finalized", "statuses": statuses})

    checksum_names = [
        "V15_MODEL_PROVENANCE.md", "V15_ENVIRONMENT_REPORT.md", "V15_STATE_CONTRACT.md",
        "V15_RESUME_EQUIVALENCE.csv", "V15_CONDITION_SWITCH.csv", "V15_FORK_CALIBRATION.csv",
        "V15_NFE_ACCOUNTING.csv", "V15_TRUE_ROLLOVER_REPORT.md", "V15_GATE0_REPORT.md",
        "V15_APPEND_ONLY_LEDGER.jsonl", "V15_MODEL_CHECKSUMS.tsv", "V15_PROVENANCE.json",
        "V15_RUN_MANIFEST.json", "V15_TEST_RESULTS.json", "V15_FORK_FROZEN.json",
        "V15_TERMINAL_DIAGNOSIS.json",
    ]
    checksum_lines = ["sha256\tbytes\tpath"]
    for name in checksum_names:
        path = TASK_DIR / name
        checksum_lines.append(
            f"{sha256_file(path)}\t{path.stat().st_size}\t{path.relative_to(REPO_ROOT)}"
        )
    atomic_text(TASK_DIR / "V15_CHECKSUMS.tsv", "\n".join(checksum_lines) + "\n")
    return statuses


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("diagnose", "finalize"))
    args = parser.parse_args()
    result = diagnose() if args.phase == "diagnose" else finalize()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

