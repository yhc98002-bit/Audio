from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_sha(value: str, name: str) -> str:
    normalized = value.strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{name} must be a 64-character lowercase hexadecimal SHA256")
    return normalized


def _git_sha(repo_root: Path) -> str | None:
    override = os.environ.get("MPRM_GIT_SHA")
    if override:
        value = override.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{7,40}", value):
            raise ValueError("MPRM_GIT_SHA must be a 7-40 character hexadecimal commit SHA")
        return value
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _model_weight_path(model_cfg: Any) -> Path | None:
    explicit = os.environ.get("MPRM_MODEL_WEIGHTS")
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None

    roots: list[Path] = []
    checkpoint_dir = os.environ.get("ACE_STEP_CHECKPOINT_DIR")
    if checkpoint_dir:
        roots.append(Path(checkpoint_dir).expanduser())
    cache_dir = getattr(model_cfg, "cache_dir", None)
    if cache_dir:
        roots.append(Path(cache_dir).expanduser())

    candidates = (
        Path("ace_step_transformer/diffusion_pytorch_model.safetensors"),
        Path("diffusion_pytorch_model.safetensors"),
        Path("model.safetensors"),
    )
    for root in roots:
        if root.is_file():
            return root
        for relative in candidates:
            path = root / relative
            if path.is_file():
                return path
    return None


def collect_run_provenance(
    config_path: str | Path,
    model_cfg: Any,
    repo_root: str | Path,
) -> dict[str, str | None]:
    """Hash the exact config, code revision, and primary model weights once."""
    config_path = Path(config_path)
    model_override = os.environ.get("MPRM_MODEL_SHA256")
    if model_override:
        model_sha = _validated_sha(model_override, "MPRM_MODEL_SHA256")
    else:
        weight_path = _model_weight_path(model_cfg)
        model_sha = sha256_file(weight_path) if weight_path is not None else None
    return {
        "config_hash": sha256_file(config_path),
        "git_sha": _git_sha(Path(repo_root)),
        "model_sha": model_sha,
    }
