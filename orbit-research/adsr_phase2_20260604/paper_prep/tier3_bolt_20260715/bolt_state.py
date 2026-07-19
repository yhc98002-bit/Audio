#!/usr/bin/env python3
"""Restartable BOLT checkpoint-state contract and condition/fork guards."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import torch


def tensor_sha256(tensor: torch.Tensor) -> str:
    value = tensor.detach().contiguous().cpu()
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(json.dumps(list(value.shape), separators=(",", ":")).encode("ascii"))
    digest.update(value.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_condition_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def assert_condition_changed(before_hash: str, after_hash: str) -> None:
    if not before_hash or not after_hash:
        raise RuntimeError("condition hashes must be present")
    if before_hash == after_hash:
        raise RuntimeError("fatal silent conditioning fallback: before and after hashes are identical")


@dataclasses.dataclass
class CheckpointState:
    state_id: str
    prompt_id: str
    root_seed: int
    completed_steps: int
    scheduler_index: int
    timestep: float
    sigma: float
    next_sigma: float
    latent: torch.Tensor
    model_output: torch.Tensor
    condition_hash: str
    model_hash: str
    checkpoint_hash: str
    scheduler_hash: str
    cpu_rng_state: torch.Tensor
    cuda_rng_state: torch.Tensor | None
    generator_rng_state: torch.Tensor
    nfe_count: int
    scheduler_step_count: int
    extras: dict[str, Any] = dataclasses.field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "prompt_id": self.prompt_id,
            "root_seed": int(self.root_seed),
            "completed_steps": int(self.completed_steps),
            "scheduler_index": int(self.scheduler_index),
            "timestep": float(self.timestep),
            "sigma": float(self.sigma),
            "next_sigma": float(self.next_sigma),
            "condition_hash": self.condition_hash,
            "model_hash": self.model_hash,
            "checkpoint_hash": self.checkpoint_hash,
            "scheduler_hash": self.scheduler_hash,
            "latent_sha256": tensor_sha256(self.latent),
            "model_output_sha256": tensor_sha256(self.model_output),
            "latent_dtype": str(self.latent.dtype),
            "latent_shape": list(self.latent.shape),
            "model_output_dtype": str(self.model_output.dtype),
            "model_output_shape": list(self.model_output.shape),
            "cpu_rng_sha256": tensor_sha256(self.cpu_rng_state),
            "cuda_rng_sha256": tensor_sha256(self.cuda_rng_state) if self.cuda_rng_state is not None else None,
            "generator_rng_sha256": tensor_sha256(self.generator_rng_state),
            "nfe_count": int(self.nfe_count),
            "scheduler_step_count": int(self.scheduler_step_count),
            "extras": self.extras,
        }


def save_checkpoint_state(state: CheckpointState, path: Path, *, allow_existing: bool = False) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = path.with_suffix(path.suffix + ".json")
    if path.exists() or meta_path.exists():
        if not allow_existing:
            raise FileExistsError(f"refusing to overwrite checkpoint state: {path}")
        loaded, metadata = load_checkpoint_state(path)
        if tensor_sha256(loaded.latent) != tensor_sha256(state.latent):
            raise RuntimeError("existing state latent conflicts with attempted resume write")
        return metadata

    metadata = state.metadata()
    payload = {
        "latent": state.latent.detach().contiguous().cpu(),
        "model_output": state.model_output.detach().contiguous().cpu(),
        "cpu_rng_state": state.cpu_rng_state.detach().contiguous().cpu(),
        "cuda_rng_state": (
            state.cuda_rng_state.detach().contiguous().cpu()
            if state.cuda_rng_state is not None else None
        ),
        "generator_rng_state": state.generator_rng_state.detach().contiguous().cpu(),
        "metadata": metadata,
    }
    tmp = path.with_suffix(path.suffix + f".partial.{os.getpid()}")
    tmp_meta = meta_path.with_suffix(meta_path.suffix + f".partial.{os.getpid()}")
    try:
        torch.save(payload, tmp)
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        metadata["state_file_sha256"] = file_sha256(tmp)
        tmp_meta.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with tmp_meta.open("rb") as handle:
            os.fsync(handle.fileno())
        os.rename(tmp, path)
        os.rename(tmp_meta, meta_path)
    finally:
        if tmp.exists():
            tmp.unlink()
        if tmp_meta.exists():
            tmp_meta.unlink()
    return metadata


def load_checkpoint_state(path: Path) -> tuple[CheckpointState, dict[str, Any]]:
    meta_path = path.with_suffix(path.suffix + ".json")
    if not path.is_file() or not meta_path.is_file():
        raise FileNotFoundError(f"checkpoint state or metadata missing for {path}")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if metadata.get("state_file_sha256") != file_sha256(path):
        raise RuntimeError(f"state file checksum mismatch: {path}")
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    for name, key in (("latent", "latent_sha256"), ("model_output", "model_output_sha256")):
        if tensor_sha256(payload[name]) != metadata[key]:
            raise RuntimeError(f"{name} checksum mismatch: {path}")
    if tensor_sha256(payload["cpu_rng_state"]) != metadata["cpu_rng_sha256"]:
        raise RuntimeError(f"CPU RNG checksum mismatch: {path}")
    cuda_state = payload.get("cuda_rng_state")
    if cuda_state is not None and tensor_sha256(cuda_state) != metadata["cuda_rng_sha256"]:
        raise RuntimeError(f"CUDA RNG checksum mismatch: {path}")
    if tensor_sha256(payload["generator_rng_state"]) != metadata["generator_rng_sha256"]:
        raise RuntimeError(f"generator RNG checksum mismatch: {path}")
    state = CheckpointState(
        state_id=metadata["state_id"],
        prompt_id=metadata["prompt_id"],
        root_seed=int(metadata["root_seed"]),
        completed_steps=int(metadata["completed_steps"]),
        scheduler_index=int(metadata["scheduler_index"]),
        timestep=float(metadata["timestep"]),
        sigma=float(metadata["sigma"]),
        next_sigma=float(metadata["next_sigma"]),
        latent=payload["latent"],
        model_output=payload["model_output"],
        condition_hash=metadata["condition_hash"],
        model_hash=metadata["model_hash"],
        checkpoint_hash=metadata["checkpoint_hash"],
        scheduler_hash=metadata["scheduler_hash"],
        cpu_rng_state=payload["cpu_rng_state"],
        cuda_rng_state=cuda_state,
        generator_rng_state=payload["generator_rng_state"],
        nfe_count=int(metadata["nfe_count"]),
        scheduler_step_count=int(metadata["scheduler_step_count"]),
        extras=dict(metadata.get("extras") or {}),
    )
    return state, metadata


def fork_latent(
    latent: torch.Tensor,
    *,
    sigma: float,
    eta: float,
    branch_seed: int,
) -> torch.Tensor:
    if eta <= 0 or sigma < 0:
        raise ValueError("fork eta must be positive and sigma nonnegative")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(branch_seed))
    noise = torch.randn(latent.shape, generator=generator, dtype=torch.float32, device="cpu")
    base = latent.detach().to(device="cpu", dtype=torch.float32)
    forked = base + float(eta) * float(sigma) * noise
    return forked.to(dtype=latent.dtype, device=latent.device)
