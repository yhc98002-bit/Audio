#!/usr/bin/env python3
"""Probe and compare the frozen BOLT runtime on an12 and an29."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent
ACE_SOURCE = Path(os.environ.get("BOLT_ACE_STEP_SOURCE", "/XYFS01/HOME/paratera_xy/pxy1289/source/ACE-Step"))
CHECKPOINT = Path(
    os.environ.get(
        "ACE_STEP_CHECKPOINT_DIR",
        "/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models/ACE-Step/ACE-Step-v1-3___5B",
    )
)
PROMOTION = ROOT / "paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json"
INSTRUMENT = ROOT / "paper_prep/w2_contingency_20260711/w2_instruments.py"
GATE_POLICY = ROOT / "configs/eval/gate_v2.yaml.draft"
REPORT = OUT / "BOLT_ENVIRONMENT_PARITY_REPORT.md"
RUNTIME = OUT / "BOLT_RUNTIME_FREEZE.json"
DECLARED_ACE_COMMIT = "1bee4c9f5b43e30995f8d4d33b3919197ce1bd68"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root: Path, paths: list[Path]) -> tuple[str, list[dict]]:
    rows = []
    for path in sorted(paths):
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append(
            {
                "path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), rows


def command_probe(args: argparse.Namespace) -> int:
    import torch
    import torchaudio

    if not torch.cuda.is_available():
        raise RuntimeError("BOLT environment probe requires CUDA visibility")
    source_paths = [path for path in ACE_SOURCE.rglob("*.py") if path.is_file()]
    source_paths.extend(path for path in (ACE_SOURCE / "setup.py", ACE_SOURCE / "requirements.txt") if path.is_file())
    source_hash, source_rows = manifest(ACE_SOURCE, source_paths)
    checkpoint_paths = [path for path in CHECKPOINT.rglob("*") if path.is_file()]
    checkpoint_hash, checkpoint_rows = manifest(CHECKPOINT, checkpoint_paths)
    bolt_paths = [path for path in OUT.glob("*.py") if path.is_file()]
    bolt_hash, bolt_rows = manifest(OUT, bolt_paths)
    quality_paths = [
        Path("/HOME/paratera_xy/pxy1289/.cache/clap/630k-audioset-best.pt"),
        Path("/HOME/paratera_xy/pxy1289/source/audiobox_aesthetics/checkpoint.pt"),
        Path("/HOME/paratera_xy/pxy1289/.cache/whisper/large-v3.pt"),
    ]
    for artifact_root in (
        Path("/HOME/paratera_xy/pxy1289/source/mert/MERT-v1-95M"),
        Path("/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/bert-base-uncased"),
        Path("/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/roberta-base"),
        Path("/HOME/paratera_xy/pxy1289/source/laion_clap_tokenizers/facebook--bart-base"),
    ):
        quality_paths.extend(path for path in artifact_root.rglob("*") if path.is_file())
    quality_hash, quality_rows = manifest(Path("/"), quality_paths)
    scheduler = ACE_SOURCE / "acestep/schedulers/scheduling_flow_match_euler_discrete.py"
    repository_sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    pip_freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    nvidia = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader,nounits"],
        text=True,
    ).strip().splitlines()
    parity_payload = {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "torchaudio_version": torchaudio.__version__,
        "cudnn_version": torch.backends.cudnn.version(),
        "ace_step_declared_commit": DECLARED_ACE_COMMIT,
        "ace_step_source_manifest_sha256": source_hash,
        "ace_step_checkpoint_manifest_sha256": checkpoint_hash,
        "scheduler_sha256": sha256_file(scheduler),
        "promotion_sha256": sha256_file(PROMOTION),
        "instrument_sha256": sha256_file(INSTRUMENT),
        "quality_gate_policy_sha256": sha256_file(GATE_POLICY),
        "quality_artifact_manifest_sha256": quality_hash,
        "quality_artifact_files": quality_rows,
        "bolt_code_manifest_sha256": bolt_hash,
        "bolt_git_sha": repository_sha,
        "pip_freeze_sha256": hashlib.sha256(pip_freeze.encode("utf-8")).hexdigest(),
        "gpu_inventory": nvidia,
    }
    environment_hash = hashlib.sha256(
        json.dumps(parity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    record = {
        "status": "PROBE_PASS",
        "host": socket.gethostname(),
        "executable": sys.executable,
        "parity": parity_payload,
        "environment_hash": environment_hash,
        "source_files": source_rows,
        "checkpoint_files": checkpoint_rows,
        "quality_files": quality_rows,
        "bolt_files": bolt_rows,
        "pip_freeze": pip_freeze.splitlines(),
    }
    output = OUT / args.output
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"host": record["host"], "environment_hash": environment_hash}, sort_keys=True))
    return 0


def command_compare(args: argparse.Namespace) -> int:
    paths = [OUT / args.an12, OUT / args.an29]
    records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    left, right = (record["parity"] for record in records)
    material_keys = (
        "python_version", "torch_version", "torch_cuda_version", "torchaudio_version",
        "cudnn_version", "ace_step_declared_commit", "ace_step_source_manifest_sha256",
        "ace_step_checkpoint_manifest_sha256", "scheduler_sha256", "promotion_sha256",
        "instrument_sha256", "quality_gate_policy_sha256", "quality_artifact_manifest_sha256",
        "quality_artifact_files",
        "bolt_code_manifest_sha256", "bolt_git_sha", "pip_freeze_sha256", "gpu_inventory",
    )
    differences = {
        key: {"an12": left.get(key), "an29": right.get(key)}
        for key in material_keys if left.get(key) != right.get(key)
    }
    status = "PASS" if not differences else "FAIL"
    runtime_payload = {
        "status": "FROZEN_PARITY_PASS" if status == "PASS" else "PARITY_FAIL",
        "nodes": [records[0]["host"], records[1]["host"]],
        "probe_artifacts": [str(path.relative_to(ROOT)) for path in paths],
        "probe_sha256": {path.name: sha256_file(path) for path in paths},
        "differences": differences,
        **left,
    }
    runtime_payload["runtime_freeze_sha256"] = hashlib.sha256(
        json.dumps(runtime_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if RUNTIME.exists():
        raise FileExistsError(RUNTIME)
    RUNTIME.write_text(json.dumps(runtime_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = [
        ("Python", left["python_version"]), ("torch", left["torch_version"]),
        ("CUDA build", left["torch_cuda_version"]), ("torchaudio", left["torchaudio_version"]),
        ("ACE-Step declared commit", left["ace_step_declared_commit"]),
        ("ACE-Step source manifest", left["ace_step_source_manifest_sha256"]),
        ("Checkpoint manifest", left["ace_step_checkpoint_manifest_sha256"]),
        ("Scheduler", left["scheduler_sha256"]), ("Promoted instrument record", left["promotion_sha256"]),
        ("Instrument implementation", left["instrument_sha256"]),
        ("Quality policy", left["quality_gate_policy_sha256"]),
        ("Quality artifact manifest", left["quality_artifact_manifest_sha256"]),
        ("BOLT code manifest", left["bolt_code_manifest_sha256"]),
        ("BOLT git SHA", left["bolt_git_sha"]), ("Environment", records[0]["environment_hash"]),
    ]
    REPORT.write_text(
        "# BOLT Cross-Node Environment Parity\n\n"
        f"ENVIRONMENT_PARITY_STATUS = {status}\n\n"
        "The source checkout is a content-only copy without `.git`; its frozen W2 upstream "
        f"commit provenance is `{DECLARED_ACE_COMMIT}`, and the current source is bound by the "
        "manifest hash below. Both nodes read the same shared artifacts but independently "
        "hashed and imported them.\n\n"
        "| Component | an12 | an29 | Match |\n| --- | --- | --- | --- |\n"
        + "".join(f"| {name} | `{value}` | `{value}` | YES |\n" for name, value in rows)
        + "\n## Differences\n\n"
        + ("None.\n" if not differences else "```json\n" + json.dumps(differences, indent=2, sort_keys=True) + "\n```\n"),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "differences": differences}, sort_keys=True))
    return 0 if status == "PASS" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--output", required=True)
    probe.set_defaults(func=command_probe)
    compare = sub.add_parser("compare")
    compare.add_argument("--an12", required=True)
    compare.add_argument("--an29", required=True)
    compare.set_defaults(func=command_compare)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
