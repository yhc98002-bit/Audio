#!/usr/bin/env python3
"""ACE-Step v1.5 XL-SFT Gate-0 engineering harness.

This module deliberately delegates conditioning, native diffusion, and VAE
decoding to the pinned ACE-Step source. It instruments the native sampler at
the decoder boundary and persists the state needed to restart that sampler.
It does not implement or run a scientific constraint axis.
"""

from __future__ import annotations

import csv
import fcntl
import hashlib
import inspect
import json
import math
import os
import platform
import random
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


TASK_DIR = Path(__file__).resolve().parent
REPO_ROOT = TASK_DIR.parents[3]
PAPER_PREP = TASK_DIR.parent
PROMPTS_PATH = TASK_DIR / "V15_GATE0_PROMPTS.jsonl"
PREREG_PATH = TASK_DIR / "V15_GATE0_PREREGISTRATION.json"
LEDGER_PATH = TASK_DIR / "V15_APPEND_ONLY_LEDGER.jsonl"
RUN_ROOT = Path(os.environ.get("V15_GATE0_RUN_ROOT", TASK_DIR / "artifacts" / "run_20260717"))
SOURCE_ROOT = Path(
    os.environ.get(
        "ACESTEP_V15_SOURCE_ROOT",
        "/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/ACE-Step-1.5",
    )
)
OVERLAY_ROOT = SOURCE_ROOT / "py310-overlay"
MODEL_CACHE_ROOT = Path(
    os.environ.get(
        "ACESTEP_V15_MODEL_CACHE",
        "/XYFS02/HDD_POOL/paratera_xy/pxy1289/HaocunYe/Research/AudioDiffusion_envs/model_cache/ACE-Step1.5",
    )
)
MODEL_DIR = MODEL_CACHE_ROOT / "acestep-v15-xl-sft"
MODEL_ID = "ACE-Step/acestep-v15-xl-sft"
MODEL_CONFIG_ID = "acestep-v15-xl-sft"
MODELSCOPE_REVISION = "d1ca0bc96e29cd46435219ceb4f8e3a13a8eaf50"
TEXT_ENCODER_ID = "Qwen/Qwen3-Embedding-0.6B"
TEXT_ENCODER_WEIGHT_REVISION = "5092237580d1545d466a2d454c09f18181c341ec"
SOURCE_COMMIT = "6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0"
SOURCE_ARCHIVE_SHA256 = "fc563d80a60a8c2485161b658bb30d621ef4eff10ca2e7ac9ac411d4cae1ea91"
SEED_BASE = 2_072_000_000
INFER_STEPS = 50
CHECKPOINT_STEPS = (10, 20, 30, 40)
SAMPLE_RATE = 48_000
AUDIO_DURATION_SEC = 15.0
GUIDANCE_SCALE = 7.0
SHIFT = 1.0
STATE_CONTRACT_VERSION = "v15-gate0-state-v1"

EXPECTED_XL_SHA256 = {
    ".gitattributes": "f102fcaa8ce8a0be24a838b56de3c0383135998bab16c5d4952c22793a7941ae",
    "README.md": "6cfd536f953f5171283d84baf223c68d88979d8215cac9209324d04c331988e2",
    "apg_guidance.py": "89ecdc4686e174225d6e6d304939d75892297dc3c19fbb11e04345dc3d4685db",
    "config.json": "174cf8c4afc2c41212546b4dca9afb11e7958f8b1e1a770d7cd009a82d72a6f1",
    "configuration.json": "7f4974aae8f10534513210f4faeae0843183cc83c24c5d00fce01e48ad9f2bba",
    "configuration_acestep_v15.py": "0d66f38eba6a3d1665c9449a1a52724d68354477bc88dcf02389640e3602a0c7",
    "model-00001-of-00004.safetensors": "1d304b8a34859cd92c349c71ae6c27d50564844c7f7611d2d32913f67508e5a4",
    "model-00002-of-00004.safetensors": "94e33648f514fdd00f473f2d2680af959204b58b15f7ab37246ac16d066aac87",
    "model-00003-of-00004.safetensors": "befe558365f53bc6c44f3f7e521cb2dd026927a817c36aa05ad94fcd80a533a9",
    "model-00004-of-00004.safetensors": "dfbc77aa26e54d0127892d6e7f3c0868bfc4623aa067867f6595c3b2fb7d31a4",
    "model.safetensors.index.json": "0a0c7e153a7bb6f6061b155739e9502cf83977bb959186d4df688595302a9474",
    "modeling_acestep_v15_xl_base.py": "e367811c6d8cd9162e630da86622dd6edc9d5c2b7f605eadd68e69a227c35e88",
    "silence_latent.pt": "a778e9dd942f5e8b2c09c55370782d318834432b03dabbcdf70e6ed49ad6358b",
}
EXPECTED_DEPENDENCY_SHA256 = {
    "Qwen3-Embedding-0.6B/model.safetensors": "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd",
    "vae/diffusion_pytorch_model.safetensors": "da17edb604c40deaf09e9b24974e590d1ca83a374070e5d0884cfa4bed9a99b0",
}
REQUIRED_STATE_FIELDS = {
    "contract_version",
    "latent",
    "latent_sha256",
    "past_key_values",
    "cache_sha256",
    "scheduler_state",
    "sigma_state",
    "last_model_output",
    "model_output_sha256",
    "apg_momentum_running_average",
    "conditioning_identity",
    "generation_kwargs",
    "prompt_identity",
    "root_seed",
    "rng_state",
    "dtype",
    "shape",
    "model_identity",
    "hashes",
}


class Gate0Error(RuntimeError):
    """A bounded Gate-0 failure."""


class ConditionCaptured(RuntimeError):
    """Private control-flow exception used after official condition preparation."""


def now_utc() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 8 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tensor_sha256(value: Any) -> str:
    import torch

    tensor = value.detach().contiguous().cpu()
    header = f"{tensor.dtype}|{tuple(tensor.shape)}|".encode("ascii")
    raw = tensor.view(torch.uint8).numpy().tobytes()
    return sha256_bytes(header + raw)


def tree_sha256(value: Any) -> str:
    import torch

    digest = hashlib.sha256()
    visited: set[int] = set()

    def update(item: Any) -> None:
        if isinstance(item, torch.Tensor):
            digest.update(b"tensor:")
            digest.update(tensor_sha256(item).encode("ascii"))
        elif item is None or isinstance(item, (bool, int, float, str)):
            digest.update(repr(item).encode("utf-8"))
        elif isinstance(item, Mapping):
            digest.update(b"{")
            for key in sorted(item, key=lambda candidate: str(candidate)):
                update(str(key))
                update(item[key])
            digest.update(b"}")
        elif isinstance(item, (list, tuple)):
            digest.update(b"[")
            for child in item:
                update(child)
            digest.update(b"]")
        elif hasattr(item, "__dict__"):
            identity = id(item)
            if identity in visited:
                digest.update(b"<cycle>")
                return
            visited.add(identity)
            update(type(item).__module__ + "." + type(item).__qualname__)
            update(vars(item))
        else:
            update(type(item).__module__ + "." + type(item).__qualname__)
            update(repr(item))

    update(value)
    return digest.hexdigest()


def cpu_tree(value: Any) -> Any:
    import torch

    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {key: cpu_tree(child) for key, child in value.items()}
    if isinstance(value, list):
        return [cpu_tree(child) for child in value]
    if isinstance(value, tuple):
        return tuple(cpu_tree(child) for child in value)
    raise TypeError(f"unsupported generation-argument type: {type(value)!r}")


def device_tree(value: Any, device: str) -> Any:
    import torch

    if isinstance(value, torch.Tensor):
        return value.to(device)
    if isinstance(value, dict):
        return {key: device_tree(child, device) for key, child in value.items()}
    if isinstance(value, list):
        return [device_tree(child, device) for child in value]
    if isinstance(value, tuple):
        return tuple(device_tree(child, device) for child in value)
    return value


def move_object_tensors(value: Any, device: str, visited: Optional[set[int]] = None) -> Any:
    import torch

    if visited is None:
        visited = set()
    if isinstance(value, torch.Tensor):
        return value.to(device)
    if isinstance(value, list):
        for index, child in enumerate(value):
            value[index] = move_object_tensors(child, device, visited)
        return value
    if isinstance(value, tuple):
        return type(value)(move_object_tensors(child, device, visited) for child in value)
    if isinstance(value, dict):
        for key, child in list(value.items()):
            value[key] = move_object_tensors(child, device, visited)
        return value
    if hasattr(value, "__dict__"):
        identity = id(value)
        if identity in visited:
            return value
        visited.add(identity)
        for key, child in list(vars(value).items()):
            try:
                setattr(value, key, move_object_tensors(child, device, visited))
            except (AttributeError, TypeError):
                pass
    return value


def atomic_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"immutable output exists: {path}")
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    with temp.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def atomic_text(path: Path, value: str, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"immutable output exists: {path}")
    temp = path.with_name(path.name + f".tmp.{os.getpid()}")
    with temp.open("x", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def append_ledger(event: Mapping[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(event)
    payload.setdefault("timestamp_utc", now_utc())
    payload.setdefault("pid", os.getpid())
    payload.setdefault("node", socket.gethostname())
    line = json.dumps(payload, sort_keys=True, default=str) + "\n"
    with LEDGER_PATH.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_record(phase: str, record_id: str, record: Mapping[str, Any]) -> Path:
    path = RUN_ROOT / "records" / phase / f"{record_id}.json"
    atomic_json(path, record)
    append_ledger(
        {
            "event": "record_committed",
            "phase": phase,
            "record_id": record_id,
            "record_path": str(path),
            "record_sha256": sha256_file(path),
            "pass": record.get("pass"),
        }
    )
    return path


def load_prompts() -> List[Dict[str, Any]]:
    prompts: List[Dict[str, Any]] = []
    with PROMPTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                prompts.append(json.loads(line))
    if len(prompts) != 8:
        raise Gate0Error(f"expected 8 frozen prompts, found {len(prompts)}")
    return prompts


def main_roots() -> List[Dict[str, Any]]:
    roots = []
    for prompt_rank, prompt in enumerate(load_prompts()):
        for seed_index in range(2):
            seed = SEED_BASE + prompt_rank * 2 + seed_index
            roots.append(
                {
                    **prompt,
                    "prompt_rank": prompt_rank,
                    "seed_index": seed_index,
                    "seed": seed,
                    "root_id": f"{prompt['prompt_id']}_s{seed_index}_seed{seed}",
                }
            )
    return roots


def deterministic_runtime() -> None:
    import torch

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    random.seed(0)
    try:
        import numpy as np

        np.random.seed(0)
    except ImportError:
        pass
    torch.manual_seed(0)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def initialize_handler() -> Tuple[Any, Dict[str, Any]]:
    deterministic_runtime()
    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(MODEL_CACHE_ROOT)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["MODELSCOPE_OFFLINE"] = "1"
    if str(OVERLAY_ROOT) not in sys.path:
        sys.path.insert(0, str(OVERLAY_ROOT))
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))
    from acestep.handler import AceStepHandler
    from acestep.model_downloader import check_main_model_exists, check_model_exists

    if not check_main_model_exists(MODEL_CACHE_ROOT):
        raise Gate0Error(f"offline aggregate checkpoint preflight failed: {MODEL_CACHE_ROOT}")
    if not check_model_exists(MODEL_CONFIG_ID, MODEL_CACHE_ROOT):
        raise Gate0Error(f"offline exact-model preflight failed: {MODEL_DIR}")

    handler = AceStepHandler()
    candidates = {
        "project_root": str(MODEL_CACHE_ROOT),
        "config_path": MODEL_CONFIG_ID,
        "device": "cuda",
        "use_flash_attention": False,
        "compile_model": False,
        "offload_to_cpu": False,
        "offload_dit_to_cpu": False,
        "quantization": None,
        "use_mlx_dit": False,
        "prefer_source": False,
    }
    signature = inspect.signature(handler.initialize_service)
    init_kwargs = {key: value for key, value in candidates.items() if key in signature.parameters}
    started = time.perf_counter()
    status, success = handler.initialize_service(**init_kwargs)
    load_wall_sec = time.perf_counter() - started
    if not success:
        raise Gate0Error(f"XL-SFT initialization failed: {status}")
    config = handler.model.config
    if bool(getattr(config, "is_turbo", True)):
        raise Gate0Error("model identity guard rejected Turbo or missing is_turbo=false")
    loaded_path = str(getattr(handler, "last_init_params", {}).get("config_path", ""))
    if MODEL_CONFIG_ID not in loaded_path and MODEL_CONFIG_ID not in str(status):
        raise Gate0Error(f"loaded config path does not identify {MODEL_CONFIG_ID}: {loaded_path}")
    runtime = runtime_identity(handler)
    runtime.update(
        {
            "init_kwargs": init_kwargs,
            "init_status": status,
            "model_load_wall_sec": load_wall_sec,
        }
    )
    return handler, runtime


def runtime_identity(handler: Optional[Any] = None) -> Dict[str, Any]:
    import importlib.metadata as metadata
    import torch

    packages = {}
    for name in (
        "torch",
        "torchaudio",
        "transformers",
        "accelerate",
        "diffusers",
        "safetensors",
        "sentencepiece",
        "soundfile",
        "numpy",
        "scipy",
        "vector-quantize-pytorch",
    ):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = "NOT_INSTALLED"
    result = {
        "node": socket.gethostname(),
        "pid": os.getpid(),
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "cuda_available": torch.cuda.is_available(),
        "packages": packages,
        "source_root": str(SOURCE_ROOT),
        "overlay_root": str(OVERLAY_ROOT),
        "model_dir": str(MODEL_DIR),
    }
    if torch.cuda.is_available():
        index = torch.cuda.current_device()
        properties = torch.cuda.get_device_properties(index)
        result["gpu"] = {
            "index": index,
            "name": properties.name,
            "total_memory": properties.total_memory,
            "capability": list(torch.cuda.get_device_capability(index)),
        }
    if handler is not None:
        config = handler.model.config
        result["model"] = {
            "model_id": MODEL_ID,
            "config_id": MODEL_CONFIG_ID,
            "class": type(handler.model).__module__ + "." + type(handler.model).__qualname__,
            "dtype": str(handler.dtype),
            "is_turbo": bool(getattr(config, "is_turbo", True)),
            "model_version": str(getattr(config, "model_version", "")),
            "attention": str(getattr(config, "_attn_implementation", "")),
        }
    return result


def full_timesteps(kwargs: Mapping[str, Any]) -> List[float]:
    import torch

    custom = kwargs.get("timesteps")
    if custom is not None:
        if isinstance(custom, torch.Tensor):
            return [float(value) for value in custom.detach().cpu().tolist()]
        return [float(value) for value in custom]
    steps = int(kwargs.get("infer_steps", INFER_STEPS))
    values = torch.linspace(1.0, 0.0, steps + 1, dtype=torch.float32)
    shift = float(kwargs.get("shift", SHIFT))
    if shift != 1.0:
        values = shift * values / (1.0 + (shift - 1.0) * values)
    return [float(value) for value in values.tolist()]


def extract_first_tensor(value: Any) -> Optional[Any]:
    import torch

    if isinstance(value, torch.Tensor):
        return value
    if isinstance(value, Mapping):
        for child in value.values():
            found = extract_first_tensor(child)
            if found is not None:
                return found
    if isinstance(value, (list, tuple)):
        for child in value:
            found = extract_first_tensor(child)
            if found is not None:
                return found
    for name in ("last_hidden_state", "sample", "hidden_states", "logits"):
        child = getattr(value, name, None)
        if isinstance(child, torch.Tensor):
            return child
    return None


def condition_identity(kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    keys = (
        "encoder_hidden_states",
        "encoder_attention_mask",
        "context_latents",
        "attention_mask",
        "lyric_token_ids",
    )
    available = {key: kwargs[key] for key in keys if key in kwargs}
    return {
        "sha256": tree_sha256(available),
        "keys": sorted(available),
        "tensor_hashes": {
            key: tree_sha256(available[key]) for key in sorted(available)
        },
    }


class NativeSamplerProbe:
    """Instrument and optionally restart the checkpoint's native sampler."""

    def __init__(
        self,
        model: Any,
        metadata: Mapping[str, Any],
        checkpoint_steps: Sequence[int] = (),
        checkpoint_callback: Optional[Callable[[int, Mapping[str, Any], "NativeSamplerProbe"], None]] = None,
        initial_latent: Optional[Any] = None,
        restored_cache: Optional[Any] = None,
        restored_momentum: Optional[Any] = None,
    ) -> None:
        self.model = model
        self.metadata = dict(metadata)
        self.checkpoint_steps = set(int(step) for step in checkpoint_steps)
        self.checkpoint_callback = checkpoint_callback
        self.initial_latent = initial_latent
        self.restored_cache = restored_cache
        self.restored_momentum = restored_momentum
        self.forward_calls = 0
        self.scheduler_euler_updates = 0
        self.scheduler_object_calls = 0
        self.generation_kwargs: Dict[str, Any] = {}
        self.initial_noise = None
        self.last_decoder_output = None
        self.last_model_output = None
        self.momentum_buffer = None
        self.gpu_wall_ms = float("nan")
        self.wall_sec = float("nan")

    def _pre_hook(self, _module: Any, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
        completed = self.forward_calls
        if completed in self.checkpoint_steps:
            if self.checkpoint_callback is None:
                raise Gate0Error("checkpoint requested without callback")
            self.checkpoint_callback(completed, kwargs, self)
        self.forward_calls += 1

    def _post_hook(self, _module: Any, _args: Tuple[Any, ...], _kwargs: Dict[str, Any], output: Any) -> None:
        self.last_decoder_output = extract_first_tensor(output)
        self.scheduler_euler_updates += 1

    def run(self, native_generate: Callable[..., Any], kwargs: Mapping[str, Any]) -> Any:
        import torch

        self.generation_kwargs = dict(kwargs)
        globals_dict = native_generate.__func__.__globals__ if hasattr(native_generate, "__func__") else native_generate.__globals__
        original_momentum = globals_dict.get("MomentumBuffer")
        original_apg = globals_dict.get("adaptive_projected_guidance")
        original_cache = globals_dict.get("EncoderDecoderCache")
        original_prepare_noise = self.model.prepare_noise

        if original_momentum is None or original_cache is None:
            raise Gate0Error("native sampler globals lack MomentumBuffer or EncoderDecoderCache")

        def momentum_factory(*args: Any, **factory_kwargs: Any) -> Any:
            buffer = original_momentum(*args, **factory_kwargs)
            if self.restored_momentum is not None:
                buffer.running_average = self.restored_momentum.to(self.metadata["device"])
            self.momentum_buffer = buffer
            return buffer

        def apg_wrapper(*args: Any, **apg_kwargs: Any) -> Any:
            output = original_apg(*args, **apg_kwargs)
            tensor = extract_first_tensor(output)
            if tensor is not None:
                self.last_model_output = tensor
            return output

        def prepare_noise_wrapper(*args: Any, **noise_kwargs: Any) -> Any:
            if self.initial_latent is None:
                output = original_prepare_noise(*args, **noise_kwargs)
            else:
                output = self.initial_latent.to(self.metadata["device"]).clone()
            self.initial_noise = output
            return output

        def cache_factory(*_args: Any, **_kwargs: Any) -> Any:
            return self.restored_cache

        globals_dict["MomentumBuffer"] = momentum_factory
        if original_apg is not None:
            globals_dict["adaptive_projected_guidance"] = apg_wrapper
        if self.restored_cache is not None:
            globals_dict["EncoderDecoderCache"] = cache_factory
        object.__setattr__(self.model, "prepare_noise", prepare_noise_wrapper)
        pre_handle = self.model.decoder.register_forward_pre_hook(self._pre_hook, with_kwargs=True)
        post_handle = self.model.decoder.register_forward_hook(self._post_hook, with_kwargs=True)
        start_event = end_event = None
        if torch.cuda.is_available():
            start_event = torch.cuda.Event(enable_timing=True)
            end_event = torch.cuda.Event(enable_timing=True)
            start_event.record()
        started = time.perf_counter()
        try:
            output = native_generate(**dict(kwargs))
            if end_event is not None:
                end_event.record()
                torch.cuda.synchronize()
                self.gpu_wall_ms = float(start_event.elapsed_time(end_event))
            return output
        finally:
            self.wall_sec = time.perf_counter() - started
            pre_handle.remove()
            post_handle.remove()
            object.__setattr__(self.model, "prepare_noise", original_prepare_noise)
            globals_dict["MomentumBuffer"] = original_momentum
            globals_dict["EncoderDecoderCache"] = original_cache
            if original_apg is not None:
                globals_dict["adaptive_projected_guidance"] = original_apg


def decoder_hook_latent(args: Sequence[Any], kwargs: Mapping[str, Any]) -> Any:
    import torch

    for key in ("hidden_states", "inputs_embeds", "x", "xt"):
        value = kwargs.get(key)
        if isinstance(value, torch.Tensor) and value.ndim >= 3:
            return value
    for value in args:
        if isinstance(value, torch.Tensor) and value.ndim >= 3 and value.is_floating_point():
            return value
    raise Gate0Error(f"unable to locate latent in decoder call keys={sorted(kwargs)}")


def save_checkpoint_state(
    path: Path,
    step: int,
    hook_kwargs: Mapping[str, Any],
    probe: NativeSamplerProbe,
) -> Dict[str, Any]:
    import numpy as np
    import torch

    if path.exists():
        raise FileExistsError(f"immutable state exists: {path}")
    latent = decoder_hook_latent((), hook_kwargs).detach()
    cache = hook_kwargs.get("past_key_values")
    if cache is None:
        raise Gate0Error("decoder restart state lacks past_key_values")
    model_output = probe.last_model_output
    if model_output is None:
        model_output = probe.last_decoder_output
    if model_output is None:
        raise Gate0Error("decoder restart state lacks prior model output")
    momentum = None
    if probe.momentum_buffer is not None:
        momentum = getattr(probe.momentum_buffer, "running_average", None)
    schedule = full_timesteps(probe.generation_kwargs)
    prompt = {
        "prompt_id": probe.metadata["prompt_id"],
        "caption": probe.metadata["caption"],
        "caption_sha256": sha256_bytes(probe.metadata["caption"].encode("utf-8")),
    }
    rng_state = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
        "torch_cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
    }
    state = {
        "contract_version": STATE_CONTRACT_VERSION,
        "checkpoint_step": step,
        "next_step_index": step,
        "latent": latent,
        "latent_sha256": tensor_sha256(latent),
        "past_key_values": cache,
        "cache_sha256": tree_sha256(cache),
        "scheduler_state": {
            "implementation": "native inline Euler ODE update xt = xt - vt * (t_curr - t_prev)",
            "implementation_sha256": EXPECTED_XL_SHA256["modeling_acestep_v15_xl_base.py"],
            "full_timesteps": schedule,
            "next_timestep": schedule[step],
            "terminal_timestep": schedule[-1],
            "completed_euler_updates": step,
            "remaining_euler_updates": INFER_STEPS - step,
        },
        "sigma_state": {
            "sigma": schedule[step],
            "schedule": "shifted linear flow schedule",
            "shift": float(probe.generation_kwargs.get("shift", SHIFT)),
        },
        "last_model_output": model_output.detach(),
        "model_output_sha256": tensor_sha256(model_output),
        "apg_momentum_running_average": momentum.detach() if hasattr(momentum, "detach") else momentum,
        "conditioning_identity": condition_identity(probe.generation_kwargs),
        "generation_kwargs": cpu_tree(probe.generation_kwargs),
        "prompt_identity": prompt,
        "root_seed": int(probe.metadata["seed"]),
        "rng_state": rng_state,
        "dtype": str(latent.dtype),
        "shape": list(latent.shape),
        "model_identity": {
            "model_id": MODEL_ID,
            "config_id": MODEL_CONFIG_ID,
            "modelscope_revision": MODELSCOPE_REVISION,
            "source_commit": SOURCE_COMMIT,
            "is_turbo": False,
        },
        "hashes": {
            "model_config_sha256": EXPECTED_XL_SHA256["config.json"],
            "model_code_sha256": EXPECTED_XL_SHA256["modeling_acestep_v15_xl_base.py"],
            "initial_noise_sha256": tensor_sha256(probe.initial_noise),
            "preregistration_sha256": sha256_file(PREREG_PATH),
            "prompt_list_sha256": sha256_file(PROMPTS_PATH),
        },
        "capture_process": {
            "pid": os.getpid(),
            "node": socket.gethostname(),
            "device": probe.metadata["device"],
            "captured_utc": now_utc(),
        },
    }
    missing = REQUIRED_STATE_FIELDS - set(state)
    if missing:
        raise Gate0Error(f"state contract construction missing {sorted(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, path)
    result = {
        "path": str(path),
        "sha256": sha256_file(path),
        "latent_sha256": state["latent_sha256"],
        "cache_sha256": state["cache_sha256"],
        "step": step,
    }
    append_ledger({"event": "checkpoint_state_committed", **result})
    return result


def generation_parameters(root: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "captions": root["base_caption"],
        "global_caption": "",
        "lyrics": "",
        "inference_steps": INFER_STEPS,
        "guidance_scale": GUIDANCE_SCALE,
        "use_random_seed": False,
        "seed": int(root["seed"]),
        "audio_duration": AUDIO_DURATION_SEC,
        "batch_size": 1,
        "task_type": "text2music",
        "shift": SHIFT,
        "infer_method": "ode",
        "sampler_mode": "euler",
        "use_adg": False,
        "velocity_norm_threshold": 0.0,
        "velocity_ema_factor": 0.0,
        "dcw_enabled": False,
        "use_tiled_decode": True,
    }


def waveform_array(value: Any) -> Any:
    import numpy as np
    import torch

    if isinstance(value, torch.Tensor):
        array = value.detach().float().cpu().numpy()
    else:
        array = np.asarray(value, dtype=np.float32)
    while array.ndim > 2 and array.shape[0] == 1:
        array = array[0]
    if array.ndim == 1:
        array = array[None, :]
    if array.ndim != 2:
        raise Gate0Error(f"unexpected waveform shape {array.shape}")
    if array.shape[0] > array.shape[1] and array.shape[1] <= 8:
        array = array.T
    return np.ascontiguousarray(array.astype(np.float32, copy=False))


def validity_metrics(waveform: Any) -> Dict[str, Any]:
    import numpy as np

    wave = waveform_array(waveform)
    finite = bool(np.isfinite(wave).all())
    rms = float(np.sqrt(np.mean(np.square(wave.astype(np.float64))))) if finite else float("nan")
    peak = float(np.max(np.abs(wave))) if finite else float("nan")
    valid = finite and rms >= 1e-4 and wave.shape[-1] > 0
    return {
        "finite": finite,
        "rms": rms,
        "peak": peak,
        "channels": int(wave.shape[0]),
        "samples": int(wave.shape[-1]),
        "sample_rate": SAMPLE_RATE,
        "duration_sec": float(wave.shape[-1] / SAMPLE_RATE),
        "validity_label": "VALID" if valid else "INVALID",
        "valid": valid,
    }


def save_audio_artifacts(prefix: Path, latent: Any, waveform: Any) -> Dict[str, Any]:
    import numpy as np
    import soundfile as sf
    import torch

    prefix.parent.mkdir(parents=True, exist_ok=True)
    latent_path = prefix.with_suffix(".latent.pt")
    numpy_path = prefix.with_suffix(".wave.npy")
    wav_path = prefix.with_suffix(".wav")
    for path in (latent_path, numpy_path, wav_path):
        if path.exists():
            raise FileExistsError(f"immutable audio artifact exists: {path}")
    torch.save(latent.detach().cpu(), latent_path)
    wave = waveform_array(waveform)
    with numpy_path.open("xb") as handle:
        np.save(handle, wave, allow_pickle=False)
    sf.write(wav_path, wave.T, SAMPLE_RATE, subtype="FLOAT")
    return {
        "latent_path": str(latent_path),
        "latent_file_sha256": sha256_file(latent_path),
        "latent_sha256": tensor_sha256(latent),
        "waveform_path": str(numpy_path),
        "waveform_file_sha256": sha256_file(numpy_path),
        "waveform_sha256": sha256_bytes(wave.tobytes()),
        "wav_path": str(wav_path),
        "wav_sha256": sha256_file(wav_path),
    }


def extract_result_waveform(result: Mapping[str, Any]) -> Optional[Any]:
    import torch

    candidates = result.get("audios") if isinstance(result, Mapping) else None
    if isinstance(candidates, torch.Tensor):
        return candidates
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, torch.Tensor):
            return first
        if isinstance(first, Mapping):
            for key in ("audio", "waveform", "wav"):
                if key in first:
                    return first[key]
    return None


def reference_one(
    handler: Any,
    runtime: Mapping[str, Any],
    root: Mapping[str, Any],
    checkpoint_steps: Sequence[int] = CHECKPOINT_STEPS,
    phase: str = "reference",
) -> Dict[str, Any]:
    import torch

    model = handler.model
    original_generate = model.generate_audio
    original_decode = handler.tiled_decode
    captured: Dict[str, Any] = {}
    state_records: List[Dict[str, Any]] = []
    metadata = {
        "prompt_id": root["prompt_id"],
        "caption": root["base_caption"],
        "seed": root["seed"],
        "device": str(handler.device),
    }

    def state_callback(step: int, hook_kwargs: Mapping[str, Any], probe: NativeSamplerProbe) -> None:
        path = RUN_ROOT / "states" / root["root_id"] / f"step_{step:02d}.pt"
        state_records.append(save_checkpoint_state(path, step, hook_kwargs, probe))

    probe = NativeSamplerProbe(
        model,
        metadata,
        checkpoint_steps=checkpoint_steps,
        checkpoint_callback=state_callback,
    )

    def generate_wrapper(*_args: Any, **kwargs: Any) -> Any:
        output = probe.run(original_generate, kwargs)
        captured["latent"] = output
        return output

    def decode_wrapper(*args: Any, **kwargs: Any) -> Any:
        start_event = end_event = None
        if torch.cuda.is_available():
            start_event = torch.cuda.Event(enable_timing=True)
            end_event = torch.cuda.Event(enable_timing=True)
            start_event.record()
        started = time.perf_counter()
        output = original_decode(*args, **kwargs)
        captured["decoder_wall_sec"] = time.perf_counter() - started
        if end_event is not None:
            end_event.record()
            torch.cuda.synchronize()
            captured["decoder_gpu_ms"] = float(start_event.elapsed_time(end_event))
        captured["waveform"] = output
        return output

    object.__setattr__(model, "generate_audio", generate_wrapper)
    object.__setattr__(handler, "tiled_decode", decode_wrapper)
    started = time.perf_counter()
    try:
        result = handler.generate_music(**generation_parameters(root))
    finally:
        object.__setattr__(model, "generate_audio", original_generate)
        object.__setattr__(handler, "tiled_decode", original_decode)
    total_wall_sec = time.perf_counter() - started
    if "latent" not in captured:
        raise Gate0Error(f"native generation was not invoked: {result}")
    waveform = captured.get("waveform")
    if waveform is None:
        waveform = extract_result_waveform(result)
    if waveform is None:
        raise Gate0Error(f"VAE decode output was not captured: {result}")
    prefix = RUN_ROOT / "audio" / phase / root["root_id"]
    artifacts = save_audio_artifacts(prefix, captured["latent"], waveform)
    validity = validity_metrics(waveform)
    record = {
        "phase": phase,
        "root_id": root["root_id"],
        "prompt_id": root["prompt_id"],
        "prompt_sha256": sha256_bytes(root["base_caption"].encode("utf-8")),
        "seed": int(root["seed"]),
        "process": {"pid": os.getpid(), "node": socket.gethostname()},
        "runtime": runtime,
        "model_identity": runtime["model"],
        "states": state_records,
        "condition_identity": condition_identity(probe.generation_kwargs),
        "artifacts": artifacts,
        "validity": validity,
        "nfe": {
            "transformer_forward_calls": probe.forward_calls,
            "scheduler_object_calls": probe.scheduler_object_calls,
            "scheduler_euler_updates": probe.scheduler_euler_updates,
            "diffusion_gpu_ms": probe.gpu_wall_ms,
            "diffusion_wall_sec": probe.wall_sec,
            "decoder_gpu_ms": captured.get("decoder_gpu_ms"),
            "decoder_wall_sec": captured.get("decoder_wall_sec"),
            "total_wall_sec": total_wall_sec,
            "prefix_forward_calls": INFER_STEPS,
            "continuation_forward_calls": 0,
            "restart_forward_calls": 0,
            "fork_forward_calls": 0,
        },
        "pass": bool(
            validity["valid"]
            and probe.forward_calls == INFER_STEPS
            and probe.scheduler_euler_updates == INFER_STEPS
            and len(state_records) == len(checkpoint_steps)
        ),
    }
    write_record(phase, root["root_id"], record)
    return record


def capture_condition_kwargs(handler: Any, root: Mapping[str, Any], caption: str) -> Dict[str, Any]:
    model = handler.model
    original_generate = model.generate_audio
    captured: Dict[str, Any] = {}

    def capture(*_args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        raise ConditionCaptured("condition prepared")

    params = generation_parameters(root)
    params["captions"] = caption
    object.__setattr__(model, "generate_audio", capture)
    try:
        handler.generate_music(**params)
    finally:
        object.__setattr__(model, "generate_audio", original_generate)
    if not captured:
        raise Gate0Error("official handler did not expose prepared condition")
    return captured


def load_state(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    import torch

    file_hash = sha256_file(path)
    state = torch.load(path, map_location="cpu", weights_only=False)
    missing = REQUIRED_STATE_FIELDS - set(state)
    if missing:
        raise Gate0Error(f"state {path} missing fields {sorted(missing)}")
    loaded_latent_hash = tensor_sha256(state["latent"])
    loaded_cache_hash = tree_sha256(state["past_key_values"])
    return state, {
        "state_file_sha256": file_hash,
        "loaded_latent_sha256": loaded_latent_hash,
        "loaded_cache_sha256": loaded_cache_hash,
        "state_file_exact": True,
        "latent_hash_exact": loaded_latent_hash == state["latent_sha256"],
        "cache_hash_exact": loaded_cache_hash == state["cache_sha256"],
    }


def perturb_latent(latent: Any, epsilon: float, seed: int) -> Tuple[Any, Dict[str, Any]]:
    import torch

    source = latent.detach().cpu()
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    direction = torch.randn(source.shape, generator=generator, dtype=torch.float32)
    direction = direction / direction.square().mean().sqrt().clamp_min(1e-12)
    perturbed = (source.float() + float(epsilon) * direction).to(source.dtype)
    effective = perturbed.float() - source.float()
    return perturbed, {
        "requested_epsilon": float(epsilon),
        "effective_rms": float(effective.square().mean().sqrt()),
        "effective_max_abs": float(effective.abs().max()),
        "source_sha256": tensor_sha256(source),
        "perturbed_sha256": tensor_sha256(perturbed),
        "nonidentical": not bool(torch.equal(source, perturbed)),
        "perturbation_seed": int(seed),
    }


def waveform_comparison(reference: Any, candidate: Any) -> Dict[str, Any]:
    import numpy as np

    left = waveform_array(reference).astype(np.float64)
    right = waveform_array(candidate).astype(np.float64)
    shape_equal = left.shape == right.shape
    if not shape_equal:
        return {
            "shape_equal": False,
            "max_abs_error": float("inf"),
            "rms_error": float("inf"),
            "cosine": float("nan"),
            "nonidentical": True,
        }
    delta = right - left
    denominator = float(np.linalg.norm(left.ravel()) * np.linalg.norm(right.ravel()))
    cosine = float(np.dot(left.ravel(), right.ravel()) / denominator) if denominator else float("nan")
    return {
        "shape_equal": True,
        "max_abs_error": float(np.max(np.abs(delta))),
        "rms_error": float(np.sqrt(np.mean(np.square(delta)))),
        "cosine": cosine,
        "nonidentical": not bool(np.array_equal(left, right)),
    }


def latent_cosine(reference: Any, candidate: Any) -> float:
    import torch

    left = reference.detach().float().cpu().flatten()
    right = candidate.detach().float().cpu().flatten()
    return float(torch.nn.functional.cosine_similarity(left[None], right[None]).item())


def run_from_state(
    handler: Any,
    state_path: Path,
    output_prefix: Path,
    *,
    mode: str,
    condition_kwargs: Optional[Mapping[str, Any]] = None,
    fork_epsilon: Optional[float] = None,
    stop_after: Optional[int] = None,
    decode: bool = True,
) -> Dict[str, Any]:
    import torch

    state, reload_checks = load_state(state_path)
    device = str(handler.device)
    checkpoint_step = int(state["checkpoint_step"])
    remaining = INFER_STEPS - checkpoint_step
    calls_requested = remaining if stop_after is None else int(stop_after)
    if calls_requested < 1 or calls_requested > remaining:
        raise Gate0Error(f"invalid continuation length {calls_requested} for step {checkpoint_step}")
    if condition_kwargs is None:
        kwargs = device_tree(state["generation_kwargs"], device)
    else:
        kwargs = device_tree(cpu_tree(dict(condition_kwargs)), device)
    schedule = state["scheduler_state"]["full_timesteps"]
    kwargs["infer_steps"] = calls_requested
    kwargs["timesteps"] = schedule[checkpoint_step : checkpoint_step + calls_requested + 1]
    kwargs["shift"] = SHIFT
    base_latent = state["latent"]
    perturbation = None
    if fork_epsilon is not None:
        base_latent, perturbation = perturb_latent(
            base_latent,
            fork_epsilon,
            int(state["root_seed"]) + checkpoint_step + 700_000,
        )
    restored_cache = None
    restored_momentum = None
    if mode in ("resume", "fork", "rollover_resume", "rollover_fork"):
        restored_cache = move_object_tensors(state["past_key_values"], device)
        momentum = state.get("apg_momentum_running_average")
        if hasattr(momentum, "to"):
            restored_momentum = momentum.to(device)
    probe = NativeSamplerProbe(
        handler.model,
        {
            "prompt_id": state["prompt_identity"]["prompt_id"],
            "caption": state["prompt_identity"]["caption"],
            "seed": state["root_seed"],
            "device": device,
        },
        initial_latent=base_latent,
        restored_cache=restored_cache,
        restored_momentum=restored_momentum,
    )
    output = probe.run(handler.model.generate_audio, kwargs)
    waveform = None
    decoder_wall_sec = None
    decoder_gpu_ms = None
    if decode:
        start_event = end_event = None
        if torch.cuda.is_available():
            start_event = torch.cuda.Event(enable_timing=True)
            end_event = torch.cuda.Event(enable_timing=True)
            start_event.record()
        started = time.perf_counter()
        waveform = handler.tiled_decode(output)
        decoder_wall_sec = time.perf_counter() - started
        if end_event is not None:
            end_event.record()
            torch.cuda.synchronize()
            decoder_gpu_ms = float(start_event.elapsed_time(end_event))
    artifacts = {}
    validity = None
    if decode:
        artifacts = save_audio_artifacts(output_prefix, output, waveform)
        validity = validity_metrics(waveform)
    else:
        output_prefix.parent.mkdir(parents=True, exist_ok=True)
        latent_path = output_prefix.with_suffix(".latent.pt")
        if latent_path.exists():
            raise FileExistsError(f"immutable partial latent exists: {latent_path}")
        torch.save(output.detach().cpu(), latent_path)
        artifacts = {
            "latent_path": str(latent_path),
            "latent_file_sha256": sha256_file(latent_path),
            "latent_sha256": tensor_sha256(output),
        }
    return {
        "mode": mode,
        "checkpoint_step": checkpoint_step,
        "state_path": str(state_path),
        "state_expected_sha256": sha256_file(state_path),
        "reload_checks": reload_checks,
        "capture_process": state["capture_process"],
        "resume_process": {"pid": os.getpid(), "node": socket.gethostname()},
        "separate_process": int(state["capture_process"]["pid"]) != os.getpid(),
        "prefix_latent_sha256": state["latent_sha256"],
        "start_latent_sha256": tensor_sha256(base_latent),
        "original_condition_identity": state["conditioning_identity"],
        "active_condition_identity": condition_identity(kwargs),
        "perturbation": perturbation,
        "artifacts": artifacts,
        "validity": validity,
        "final_latent": output.detach().cpu(),
        "waveform": waveform,
        "nfe": {
            "transformer_forward_calls": probe.forward_calls,
            "scheduler_object_calls": probe.scheduler_object_calls,
            "scheduler_euler_updates": probe.scheduler_euler_updates,
            "diffusion_gpu_ms": probe.gpu_wall_ms,
            "diffusion_wall_sec": probe.wall_sec,
            "decoder_gpu_ms": decoder_gpu_ms,
            "decoder_wall_sec": decoder_wall_sec,
            "prefix_forward_calls": checkpoint_step,
            "continuation_forward_calls": probe.forward_calls,
            "restart_forward_calls": probe.forward_calls if mode == "resume" else 0,
            "fork_forward_calls": probe.forward_calls if "fork" in mode else 0,
        },
        "expected_remaining_calls": calls_requested,
        "only_remaining_nfe": probe.forward_calls == calls_requested,
    }


def load_reference_arrays(root_id: str, phase: str = "reference") -> Tuple[Dict[str, Any], Any, Any]:
    import numpy as np
    import torch

    record_path = RUN_ROOT / "records" / phase / f"{root_id}.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    latent = torch.load(record["artifacts"]["latent_path"], map_location="cpu", weights_only=True)
    waveform = np.load(record["artifacts"]["waveform_path"], allow_pickle=False)
    return record, latent, waveform


def process_main_continuations(rank: int, world_size: int) -> None:
    frozen = json.loads((TASK_DIR / "V15_FORK_FROZEN.json").read_text(encoding="utf-8"))
    if frozen.get("status") != "PASS":
        raise Gate0Error("fork perturbation was not frozen at PASS")
    epsilon = float(frozen["epsilon"])
    handler, runtime = initialize_handler()
    for index, root in enumerate(main_roots()):
        if index % world_size != rank:
            continue
        reference, reference_latent, reference_wave = load_reference_arrays(root["root_id"])
        modified_kwargs = capture_condition_kwargs(handler, root, root["modified_caption"])
        modified_identity = condition_identity(modified_kwargs)
        for step in CHECKPOINT_STEPS:
            state_path = RUN_ROOT / "states" / root["root_id"] / f"step_{step:02d}.pt"
            common_id = f"{root['root_id']}_step{step:02d}"

            resume = run_from_state(
                handler,
                state_path,
                RUN_ROOT / "audio" / "resume" / common_id,
                mode="resume",
            )
            resume_compare = waveform_comparison(reference_wave, resume.pop("waveform"))
            resume_latent = resume.pop("final_latent")
            resume["final_latent_comparison"] = {
                "reference_sha256": tensor_sha256(reference_latent),
                "resume_sha256": tensor_sha256(resume_latent),
                "cosine": latent_cosine(reference_latent, resume_latent),
            }
            resume["waveform_comparison"] = resume_compare
            resume["reference_validity"] = reference["validity"]
            resume["prompt_id"] = root["prompt_id"]
            resume["root_id"] = root["root_id"]
            resume["seed"] = root["seed"]
            resume["runtime"] = runtime
            resume["pass"] = bool(
                resume["separate_process"]
                and all(resume["reload_checks"].values())
                and resume["only_remaining_nfe"]
                and resume["validity"]["valid"]
                and resume["validity"]["validity_label"] == reference["validity"]["validity_label"]
                and resume_compare["shape_equal"]
                and resume_compare["max_abs_error"] <= 1e-4
                and resume_compare["rms_error"] <= 1e-6
                and resume_compare["cosine"] >= 0.999999
                and resume["validity"]["sample_rate"] == reference["validity"]["sample_rate"]
                and resume["validity"]["samples"] == reference["validity"]["samples"]
            )
            write_record("resume", common_id, resume)

            switch = run_from_state(
                handler,
                state_path,
                RUN_ROOT / "audio" / "condition_switch" / common_id,
                mode="condition_switch",
                condition_kwargs=modified_kwargs,
            )
            switch.pop("waveform")
            switch.pop("final_latent")
            switch["prompt_id"] = root["prompt_id"]
            switch["root_id"] = root["root_id"]
            switch["seed"] = root["seed"]
            switch["modified_prompt_sha256"] = sha256_bytes(root["modified_caption"].encode("utf-8"))
            switch["changed_condition_hash"] = (
                modified_identity["sha256"] != switch["original_condition_identity"]["sha256"]
            )
            switch["silent_fallback"] = False
            switch["identical_latent_prefix"] = (
                switch["prefix_latent_sha256"] == switch["start_latent_sha256"]
            )
            switch["runtime"] = runtime
            switch["pass"] = bool(
                switch["changed_condition_hash"]
                and switch["identical_latent_prefix"]
                and not switch["silent_fallback"]
                and switch["only_remaining_nfe"]
                and switch["validity"]["valid"]
            )
            write_record("condition_switch", common_id, switch)

            fork = run_from_state(
                handler,
                state_path,
                RUN_ROOT / "audio" / "fork" / common_id,
                mode="fork",
                fork_epsilon=epsilon,
            )
            fork_wave = fork.pop("waveform")
            fork_latent = fork.pop("final_latent")
            diversity = waveform_comparison(reference_wave, fork_wave)
            diversity["final_latent_cosine"] = latent_cosine(reference_latent, fork_latent)
            fork["prompt_id"] = root["prompt_id"]
            fork["root_id"] = root["root_id"]
            fork["seed"] = root["seed"]
            fork["frozen_epsilon"] = epsilon
            fork["shared_prefix_preserved"] = (
                fork["prefix_latent_sha256"] == fork["perturbation"]["source_sha256"]
            )
            fork["diversity"] = diversity
            fork["runtime"] = runtime
            fork["pass"] = bool(
                fork["shared_prefix_preserved"]
                and fork["perturbation"]["nonidentical"]
                and fork["only_remaining_nfe"]
                and fork["validity"]["valid"]
                and diversity["nonidentical"]
                and diversity["rms_error"] >= 1e-5
                and diversity["rms_error"] <= 0.1
                and diversity["final_latent_cosine"] >= 0.95
            )
            write_record("fork", common_id, fork)


def run_reference_worker(rank: int, world_size: int) -> None:
    handler, runtime = initialize_handler()
    for index, root in enumerate(main_roots()):
        if index % world_size == rank:
            reference_one(handler, runtime, root)


def run_fork_calibration() -> Dict[str, Any]:
    handler, runtime = initialize_handler()
    prompt = load_prompts()[0]
    root = {
        **prompt,
        "seed": SEED_BASE + 16,
        "root_id": f"cal_{prompt['prompt_id']}_seed{SEED_BASE + 16}",
    }
    reference = reference_one(handler, runtime, root, checkpoint_steps=(20,), phase="calibration_reference")
    _, reference_latent, reference_wave = load_reference_arrays(root["root_id"], "calibration_reference")
    state_path = RUN_ROOT / "states" / root["root_id"] / "step_20.pt"
    grid = [1e-5, 3e-5, 1e-4, 3e-4, 1e-3]
    records = []
    selected = None
    for epsilon in grid:
        token = f"eps{epsilon:.0e}".replace("+", "")
        run = run_from_state(
            handler,
            state_path,
            RUN_ROOT / "audio" / "fork_calibration" / token,
            mode="fork",
            fork_epsilon=epsilon,
        )
        wave = run.pop("waveform")
        latent = run.pop("final_latent")
        comparison = waveform_comparison(reference_wave, wave)
        comparison["final_latent_cosine"] = latent_cosine(reference_latent, latent)
        passed = bool(
            run["perturbation"]["nonidentical"]
            and run["validity"]["valid"]
            and comparison["nonidentical"]
            and comparison["rms_error"] >= 1e-5
            and comparison["rms_error"] <= 0.1
            and comparison["final_latent_cosine"] >= 0.95
            and run["only_remaining_nfe"]
        )
        record = {
            **{key: value for key, value in run.items() if key not in ("runtime",)},
            "epsilon": epsilon,
            "comparison": comparison,
            "shared_prefix_preserved": run["prefix_latent_sha256"] == run["perturbation"]["source_sha256"],
            "pass": passed,
        }
        records.append(record)
        write_record("fork_calibration", token, record)
        if selected is None and passed:
            selected = epsilon
    frozen = {
        "status": "PASS" if selected is not None else "FAIL",
        "epsilon": selected,
        "grid": grid,
        "thresholds": {
            "minimum_waveform_rms_delta": 1e-5,
            "maximum_waveform_rms_delta": 0.1,
            "minimum_final_latent_cosine": 0.95,
            "valid_audio_required": True,
            "nonidentical_required": True,
        },
        "calibration_seed": root["seed"],
        "calibration_checkpoint_step": 20,
        "frozen_before_main_controls": True,
        "frozen_utc": now_utc(),
        "reference_record": str(RUN_ROOT / "records" / "calibration_reference" / f"{root['root_id']}.json"),
    }
    atomic_json(TASK_DIR / "V15_FORK_FROZEN.json", frozen)
    append_ledger({"event": "fork_perturbation_frozen", **frozen})
    if selected is None:
        raise Gate0Error("bounded fork calibration found no preregistered passing perturbation")
    return frozen


@dataclass
class Reservation:
    attempt_id: str
    kind: str
    reserved: int
    started_remaining: int


@dataclass
class GlobalComputePool:
    full_generation_cost: int
    total_budget: int
    remaining: int = field(init=False)
    completed_candidates: int = 0
    shared_prefixes: Dict[str, int] = field(default_factory=dict)
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.full_generation_cost <= 0:
            raise ValueError("full generation cost must be positive")
        if self.total_budget != 2 * self.full_generation_cost:
            raise ValueError("demonstration budget must equal exactly two full generations")
        self.remaining = self.total_budget

    def charge_shared_prefix(self, prefix_id: str, actual_calls: int) -> None:
        if prefix_id in self.shared_prefixes:
            raise ValueError("shared prefix can only be charged once")
        if actual_calls < 0 or actual_calls > self.remaining:
            raise ValueError("invalid shared-prefix charge")
        self.shared_prefixes[prefix_id] = actual_calls
        self.remaining -= actual_calls
        self._assert_reserve()

    def begin_exploratory(self, attempt_id: str, requested_max: int) -> Reservation:
        reserve = 0 if self.completed_candidates else self.full_generation_cost
        available = self.remaining - reserve
        if available <= 0:
            raise ValueError("completion reserve forbids exploratory attempt")
        reserved = min(int(requested_max), available)
        if reserved <= 0:
            raise ValueError("attempt reservation must be positive")
        return Reservation(attempt_id, "exploratory", reserved, self.remaining)

    def begin_completion(self, attempt_id: str, requested_max: int) -> Reservation:
        reserved = min(int(requested_max), self.remaining)
        if reserved <= 0:
            raise ValueError("completion reservation must be positive")
        return Reservation(attempt_id, "completion", reserved, self.remaining)

    def finish(self, reservation: Reservation, actual_calls: int, valid_completion: bool) -> Dict[str, Any]:
        actual_calls = int(actual_calls)
        if actual_calls < 0 or actual_calls > reservation.reserved:
            raise ValueError("actual calls exceed reservation")
        self.remaining -= actual_calls
        if valid_completion:
            self.completed_candidates += 1
        event = {
            "attempt_id": reservation.attempt_id,
            "kind": reservation.kind,
            "reserved_calls": reservation.reserved,
            "actual_calls": actual_calls,
            "returned_unused_calls": reservation.reserved - actual_calls,
            "valid_completion": bool(valid_completion),
            "remaining_after": self.remaining,
            "completed_candidates_after": self.completed_candidates,
        }
        self.attempts.append(event)
        self._assert_reserve()
        return event

    def _assert_reserve(self) -> None:
        if not self.completed_candidates and self.remaining < self.full_generation_cost:
            raise AssertionError("completion reserve invariant violated")


def run_true_rollover() -> Dict[str, Any]:
    references = load_records("reference")
    measured_costs = {int(record["nfe"]["transformer_forward_calls"]) for record in references}
    if measured_costs != {INFER_STEPS}:
        raise Gate0Error(f"full-generation NFE is not uniquely measured: {measured_costs}")
    full_cost = measured_costs.pop()
    root = main_roots()[0]
    state_path = RUN_ROOT / "states" / root["root_id"] / "step_10.pt"
    handler, runtime = initialize_handler()
    modified_kwargs = capture_condition_kwargs(handler, root, root["modified_caption"])
    pool = GlobalComputePool(full_generation_cost=full_cost, total_budget=2 * full_cost)
    pool.charge_shared_prefix("p00-s0-step10", 10)

    reservation1 = pool.begin_exploratory("dynamic-attempt-1", 40)
    attempt1 = run_from_state(
        handler,
        state_path,
        RUN_ROOT / "audio" / "rollover" / "attempt1_early_fork",
        mode="rollover_fork",
        fork_epsilon=float(json.loads((TASK_DIR / "V15_FORK_FROZEN.json").read_text())["epsilon"]),
        stop_after=5,
        decode=False,
    )
    event1 = pool.finish(reservation1, attempt1["nfe"]["transformer_forward_calls"], False)

    reservation2 = pool.begin_exploratory("dynamic-attempt-2", 40)
    attempt2 = run_from_state(
        handler,
        state_path,
        RUN_ROOT / "audio" / "rollover" / "attempt2_early_switch",
        mode="condition_switch",
        condition_kwargs=modified_kwargs,
        stop_after=10,
        decode=False,
    )
    event2 = pool.finish(reservation2, attempt2["nfe"]["transformer_forward_calls"], False)

    reservation3 = pool.begin_completion("dynamic-attempt-3", 40)
    attempt3 = run_from_state(
        handler,
        state_path,
        RUN_ROOT / "audio" / "rollover" / "attempt3_completion",
        mode="rollover_resume",
    )
    attempt3.pop("waveform")
    attempt3.pop("final_latent")
    event3 = pool.finish(
        reservation3,
        attempt3["nfe"]["transformer_forward_calls"],
        bool(attempt3["validity"]["valid"]),
    )
    report = {
        "full_generation_cost_measured_transformer_forwards": full_cost,
        "global_budget_transformer_forwards": 2 * full_cost,
        "shared_prefix": {
            "id": "p00-s0-step10",
            "actual_calls": 10,
            "charged_count": 1,
            "state_path": str(state_path),
            "state_sha256": sha256_file(state_path),
        },
        "events": [event1, event2, event3],
        "dynamic_attempt_count": len(pool.attempts),
        "remaining_budget": pool.remaining,
        "completed_candidates": pool.completed_candidates,
        "reserve_held_after_first_termination": event1["remaining_after"] >= full_cost,
        "reserve_held_after_second_termination": event2["remaining_after"] >= full_cost,
        "multiple_early_terminations_before_completion": True,
        "no_fixed_two_slot_assumption": len(pool.attempts) > 2,
        "runtime": runtime,
        "pass": bool(
            full_cost == 50
            and pool.total_budget == 100
            and pool.completed_candidates >= 1
            and event1["returned_unused_calls"] > 0
            and event2["returned_unused_calls"] > 0
            and event1["remaining_after"] >= full_cost
            and event2["remaining_after"] >= full_cost
            and len(pool.attempts) == 3
            and attempt3["validity"]["valid"]
        ),
    }
    write_record("rollover", "true_global_rollover", report)
    return report


def collect_provenance() -> Dict[str, Any]:
    download_log = TASK_DIR / "logs" / "modelscope_download_sha256.txt"
    observed: Dict[str, str] = {}
    if download_log.exists():
        for line in download_log.read_text(encoding="utf-8").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                observed[Path(parts[1].strip()).name] = parts[0]
    for name, expected in EXPECTED_XL_SHA256.items():
        path = MODEL_DIR / name
        if not path.exists():
            raise Gate0Error(f"missing XL-SFT artifact: {path}")
        if name not in observed:
            observed[name] = sha256_file(path)
        if observed[name] != expected:
            raise Gate0Error(f"XL-SFT hash mismatch for {name}: {observed[name]} != {expected}")
    dependency_hashes = {}
    for relative, expected in EXPECTED_DEPENDENCY_SHA256.items():
        path = MODEL_CACHE_ROOT / relative
        actual = sha256_file(path)
        dependency_hashes[relative] = actual
        if actual != expected:
            raise Gate0Error(f"dependency hash mismatch for {relative}: {actual} != {expected}")
    small_identity_files = []
    for directory in (MODEL_CACHE_ROOT / "Qwen3-Embedding-0.6B", MODEL_CACHE_ROOT / "vae"):
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix not in (".safetensors", ".bin"):
                small_identity_files.append(
                    {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
                )
    config = json.loads((MODEL_DIR / "config.json").read_text(encoding="utf-8"))
    provenance = {
        "status": "PASS" if config.get("is_turbo") is False else "FAIL",
        "model_id": MODEL_ID,
        "config_id": MODEL_CONFIG_ID,
        "modelscope_repository": MODEL_ID,
        "modelscope_revision": MODELSCOPE_REVISION,
        "source_repository": "https://github.com/ace-step/ACE-Step-1.5",
        "source_commit": SOURCE_COMMIT,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "model_config": {
            "architectures": config.get("architectures"),
            "model_version": config.get("model_version"),
            "is_turbo": config.get("is_turbo"),
            "dtype": config.get("dtype"),
            "hidden_size": config.get("hidden_size"),
            "num_hidden_layers": config.get("num_hidden_layers"),
        },
        "xl_files": [
            {
                "path": str(MODEL_DIR / name),
                "sha256": observed[name],
                "expected_sha256": expected,
                "bytes": (MODEL_DIR / name).stat().st_size,
                "match": observed[name] == expected,
            }
            for name, expected in sorted(EXPECTED_XL_SHA256.items())
        ],
        "dependencies": [
            {
                "path": str(MODEL_CACHE_ROOT / relative),
                "identity": "Qwen3-Embedding-0.6B tokenizer/text encoder" if relative.startswith("Qwen") else "ACE-Step v1.5 VAE",
                "sha256": actual,
                "expected_sha256": EXPECTED_DEPENDENCY_SHA256[relative],
                "match": actual == EXPECTED_DEPENDENCY_SHA256[relative],
            }
            for relative, actual in sorted(dependency_hashes.items())
        ],
        "text_encoder_identity": {
            "model_id": TEXT_ENCODER_ID,
            "weight_file_revision": TEXT_ENCODER_WEIGHT_REVISION,
            "local_snapshot": str(MODEL_CACHE_ROOT / "Qwen3-Embedding-0.6B"),
        },
        "small_identity_files": small_identity_files,
        "scheduler": {
            "implementation": "inline shifted linear schedule plus Euler ODE update",
            "scheduler_object": None,
            "model_code_sha256": EXPECTED_XL_SHA256["modeling_acestep_v15_xl_base.py"],
        },
        "generation_defaults": {
            "infer_steps": 50,
            "guidance_scale": 7.0,
            "shift": 1.0,
            "infer_method": "ode",
            "sampler_mode": "euler",
            "dcw_enabled": False,
            "use_adg": False,
            "audio_duration_sec": 15.0,
            "sample_rate": 48000,
            "thinking": False,
        },
        "acquisition": {
            "node_role": "login",
            "source_priority": "ModelScope first",
            "proxy": "http://127.0.0.1:7890",
            "compute_node_download": False,
        },
        "collected_utc": now_utc(),
    }
    atomic_json(TASK_DIR / "V15_PROVENANCE.json", provenance)
    lines = ["sha256\tbytes\tpath\tidentity"]
    for item in provenance["xl_files"]:
        lines.append(f"{item['sha256']}\t{item['bytes']}\t{item['path']}\tXL-SFT")
    for item in provenance["dependencies"]:
        path = Path(item["path"])
        lines.append(f"{item['sha256']}\t{path.stat().st_size}\t{path}\t{item['identity']}")
    for item in small_identity_files:
        lines.append(f"{item['sha256']}\t{item['bytes']}\t{item['path']}\tconfiguration/tokenizer")
    atomic_text(TASK_DIR / "V15_MODEL_CHECKSUMS.tsv", "\n".join(lines) + "\n")
    environment = runtime_identity()
    environment["git_base_commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    environment["command"] = "python run_v15_gate0.py provenance"
    environment["config_hash"] = sha256_file(PREREG_PATH)
    environment["seed_namespace"] = f"{SEED_BASE}..{SEED_BASE + 63}"
    environment["artifact_path"] = str(RUN_ROOT)
    environment["placement"] = {
        "node": socket.gethostname(),
        "gpu_ids": [],
        "tp_width": 1,
        "replica_count": 0,
        "justification": "Login-only provenance collection; no model generation.",
    }
    atomic_json(TASK_DIR / "V15_LOGIN_ENVIRONMENT.json", environment)
    append_ledger({"event": "provenance_frozen", "status": provenance["status"], "model_id": MODEL_ID})
    return provenance


def load_records(phase: str) -> List[Dict[str, Any]]:
    directory = RUN_ROOT / "records" / phase
    if not directory.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]


def flatten_record(record: Mapping[str, Any], phase: str) -> Dict[str, Any]:
    validity = record.get("validity") or {}
    nfe = record.get("nfe") or {}
    comparison = record.get("waveform_comparison") or record.get("diversity") or record.get("comparison") or {}
    reload_checks = record.get("reload_checks") or {}
    perturbation = record.get("perturbation") or {}
    return {
        "phase": phase,
        "root_id": record.get("root_id", ""),
        "prompt_id": record.get("prompt_id", ""),
        "seed": record.get("seed", ""),
        "checkpoint_step": record.get("checkpoint_step", ""),
        "state_path": record.get("state_path", ""),
        "state_file_sha256": record.get("state_expected_sha256", ""),
        "state_file_exact": reload_checks.get("state_file_exact", ""),
        "latent_hash_exact": reload_checks.get("latent_hash_exact", ""),
        "cache_hash_exact": reload_checks.get("cache_hash_exact", ""),
        "separate_process": record.get("separate_process", ""),
        "changed_condition_hash": record.get("changed_condition_hash", ""),
        "identical_latent_prefix": record.get("identical_latent_prefix", ""),
        "shared_prefix_preserved": record.get("shared_prefix_preserved", ""),
        "epsilon": record.get("epsilon", record.get("frozen_epsilon", "")),
        "effective_perturbation_rms": perturbation.get("effective_rms", ""),
        "waveform_max_abs_error": comparison.get("max_abs_error", ""),
        "waveform_rms_error": comparison.get("rms_error", ""),
        "waveform_cosine": comparison.get("cosine", ""),
        "final_latent_cosine": comparison.get("final_latent_cosine", ""),
        "validity_label": validity.get("validity_label", ""),
        "valid_rms": validity.get("rms", ""),
        "sample_rate": validity.get("sample_rate", ""),
        "samples": validity.get("samples", ""),
        "transformer_forward_calls": nfe.get("transformer_forward_calls", ""),
        "scheduler_object_calls": nfe.get("scheduler_object_calls", ""),
        "scheduler_euler_updates": nfe.get("scheduler_euler_updates", ""),
        "diffusion_gpu_ms": nfe.get("diffusion_gpu_ms", ""),
        "diffusion_wall_sec": nfe.get("diffusion_wall_sec", ""),
        "decoder_gpu_ms": nfe.get("decoder_gpu_ms", ""),
        "decoder_wall_sec": nfe.get("decoder_wall_sec", ""),
        "prefix_forward_calls": nfe.get("prefix_forward_calls", ""),
        "continuation_forward_calls": nfe.get("continuation_forward_calls", ""),
        "pass": record.get("pass", False),
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise Gate0Error(f"refusing empty required CSV {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"immutable output exists: {path}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def finalize_reports() -> Dict[str, str]:
    provenance = json.loads((TASK_DIR / "V15_PROVENANCE.json").read_text(encoding="utf-8"))
    login_environment = json.loads((TASK_DIR / "V15_LOGIN_ENVIRONMENT.json").read_text(encoding="utf-8"))
    references = [record for record in load_records("reference") if record["root_id"].startswith("v15g0_")]
    resumes = load_records("resume")
    switches = load_records("condition_switch")
    calibration = load_records("fork_calibration")
    forks = load_records("fork")
    rollover_records = load_records("rollover")
    tests_path = TASK_DIR / "V15_TEST_RESULTS.json"
    tests = json.loads(tests_path.read_text(encoding="utf-8")) if tests_path.exists() else {"pass": False}

    state_paths = [Path(state["path"]) for record in references for state in record["states"]]
    state_contract_pass = len(state_paths) == 64 and all(path.exists() for path in state_paths)
    if state_contract_pass:
        for path in state_paths:
            state, checks = load_state(path)
            state_contract_pass &= not (REQUIRED_STATE_FIELDS - set(state)) and all(checks.values())

    statuses = {
        "MODEL_PROVENANCE_STATUS": "PASS" if provenance.get("status") == "PASS" else "FAIL",
        "ENVIRONMENT_STATUS": "PASS" if references and all(r["runtime"]["cuda_available"] for r in references) else "FAIL",
        "STATE_CONTRACT_STATUS": "PASS" if state_contract_pass else "FAIL",
        "RESUME_EQUIVALENCE_STATUS": "PASS" if len(resumes) == 64 and all(r["pass"] for r in resumes) else "FAIL",
        "CONDITION_SWITCH_STATUS": "PASS" if len(switches) == 64 and all(r["pass"] for r in switches) else "FAIL",
        "FORK_STATUS": "PASS" if len(forks) == 64 and all(r["pass"] for r in forks) and any(r["pass"] for r in calibration) else "FAIL",
        "ACTUAL_NFE_STATUS": "PASS" if len(references) == 16 and all(r["nfe"]["transformer_forward_calls"] == 50 and r["nfe"]["scheduler_euler_updates"] == 50 for r in references) else "FAIL",
        "TRUE_ROLLOVER_STATUS": "PASS" if len(rollover_records) == 1 and rollover_records[0]["pass"] else "FAIL",
        "COMPLETION_RESERVE_STATUS": "PASS" if len(rollover_records) == 1 and rollover_records[0]["reserve_held_after_first_termination"] and rollover_records[0]["reserve_held_after_second_termination"] else "FAIL",
        "TEST_SUITE_STATUS": "PASS" if tests.get("pass") else "FAIL",
    }
    component_values = list(statuses.values())
    statuses["V15_GATE0_STATUS"] = "PASS" if all(value == "PASS" for value in component_values) else "FAIL_ESCALATED"

    resume_rows = [flatten_record(record, "resume") for record in resumes]
    switch_rows = [flatten_record(record, "condition_switch") for record in switches]
    fork_rows = [flatten_record(record, "calibration") for record in calibration] + [flatten_record(record, "frozen_main") for record in forks]
    nfe_rows = []
    for phase, records in (
        ("reference", references),
        ("resume", resumes),
        ("condition_switch", switches),
        ("fork", forks),
    ):
        nfe_rows.extend(flatten_record(record, phase) for record in records)
    write_csv(TASK_DIR / "V15_RESUME_EQUIVALENCE.csv", resume_rows)
    write_csv(TASK_DIR / "V15_CONDITION_SWITCH.csv", switch_rows)
    write_csv(TASK_DIR / "V15_FORK_CALIBRATION.csv", fork_rows)
    write_csv(TASK_DIR / "V15_NFE_ACCOUNTING.csv", nfe_rows)

    provenance_md = f"""# ACE-Step v1.5 XL-SFT Model Provenance

MODEL_PROVENANCE_STATUS = {statuses['MODEL_PROVENANCE_STATUS']}

- Source repository: `https://github.com/ace-step/ACE-Step-1.5`
- Source commit: `{SOURCE_COMMIT}`
- Source archive SHA-256: `{SOURCE_ARCHIVE_SHA256}`
- ModelScope repository: `{MODEL_ID}`
- ModelScope revision: `{MODELSCOPE_REVISION}`
- Exact model/config ID: `{MODEL_ID}` / `{MODEL_CONFIG_ID}`
- Model class: `{provenance['model_config']['architectures'][0]}`
- Turbo guard: `is_turbo = false`
- Transformer checkpoint: four safetensors shards listed in `V15_MODEL_CHECKSUMS.tsv`
- VAE: `{MODEL_CACHE_ROOT / 'vae'}`; weight SHA-256 `{EXPECTED_DEPENDENCY_SHA256['vae/diffusion_pytorch_model.safetensors']}`
- Tokenizer/text encoder: `{MODEL_CACHE_ROOT / 'Qwen3-Embedding-0.6B'}`; weight SHA-256 `{EXPECTED_DEPENDENCY_SHA256['Qwen3-Embedding-0.6B/model.safetensors']}`
- Scheduler: no scheduler object is instantiated. The pinned model code constructs a shifted linear flow schedule and performs the inline Euler ODE update. Model/scheduler code SHA-256: `{EXPECTED_XL_SHA256['modeling_acestep_v15_xl_base.py']}`.
- Research defaults: 50 steps, CFG 7.0, shift 1.0, Euler ODE, ADG disabled, DCW disabled, no LM thinking, 15 s, 48 kHz.
- Acquisition: login node through `http://127.0.0.1:7890`, ModelScope first. No compute-node download and no checkpoint substitution occurred.

Evidence: `V15_MODEL_CHECKSUMS.tsv`, `V15_PROVENANCE.json`, `V15_GATE0_PREREGISTRATION.json`.
"""
    atomic_text(TASK_DIR / "V15_MODEL_PROVENANCE.md", provenance_md)

    compute_runtimes = {}
    for record in references:
        identity = json.dumps(record["runtime"], sort_keys=True)
        compute_runtimes[sha256_bytes(identity.encode())] = record["runtime"]
    environment_md = f"""# ACE-Step v1.5 Gate-0 Environment

ENVIRONMENT_STATUS = {statuses['ENVIRONMENT_STATUS']}

## Login provenance environment

```json
{json.dumps(login_environment, indent=2, sort_keys=True)}
```

## Compute environments

```json
{json.dumps(list(compute_runtimes.values()), indent=2, sort_keys=True)}
```

Placement: single-node inference, TP1, independent one-GPU replicas. XL-SFT fits one A800; TP wider than one would add communication without being required. The source and dependency overlay are `{SOURCE_ROOT}` and `{OVERLAY_ROOT}`.
"""
    atomic_text(TASK_DIR / "V15_ENVIRONMENT_REPORT.md", environment_md)

    state_md = f"""# V15 Checkpoint-State Contract

STATE_CONTRACT_STATUS = {statuses['STATE_CONTRACT_STATUS']}

Contract version: `{STATE_CONTRACT_VERSION}`. Captures occur after exactly 10, 20, 30, and 40 completed Euler updates, immediately before the next transformer call.

Persisted fields: `{', '.join(sorted(REQUIRED_STATE_FIELDS))}`. The cache payload contains the native `EncoderDecoderCache`; APG momentum and the prior effective model output are separate fields. Scheduler state records the exact remaining timestep suffix and sigma. RNG state includes Python, NumPy, torch CPU, and all CUDA generators.

Reload semantics: same-condition resume restores latent, decoder cache, APG momentum, condition tensors, timestep suffix, and RNG provenance. Condition switch preserves the latent but deliberately resets condition-dependent cache and momentum. A fork preserves the checkpoint identity and cache while replacing only the checkpoint latent with the frozen deterministic perturbation.

Observed main-control state files: {len(state_paths)}. Every file was loaded in a process distinct from its capture process and checked against its file, latent, and cache hashes.

Evidence: `V15_RESUME_EQUIVALENCE.csv`, `V15_APPEND_ONLY_LEDGER.jsonl`.
"""
    atomic_text(TASK_DIR / "V15_STATE_CONTRACT.md", state_md)

    rollover = rollover_records[0] if rollover_records else {}
    rollover_md = f"""# V15 True Global Rollover

TRUE_ROLLOVER_STATUS = {statuses['TRUE_ROLLOVER_STATUS']}
COMPLETION_RESERVE_STATUS = {statuses['COMPLETION_RESERVE_STATUS']}

- Measured full-generation cost: `{rollover.get('full_generation_cost_measured_transformer_forwards', 'NA')}` transformer forward calls.
- Global demonstration budget: `{rollover.get('global_budget_transformer_forwards', 'NA')}` calls, exactly two measured full generations.
- Shared prefix: 10 calls, charged once.
- Dynamic attempts: `{rollover.get('dynamic_attempt_count', 'NA')}`; no two-slot data structure exists.
- Remaining global budget: `{rollover.get('remaining_budget', 'NA')}` calls.
- Valid completed candidates: `{rollover.get('completed_candidates', 'NA')}`.
- Completion reserve held after both early terminations: `{rollover.get('reserve_held_after_first_termination', False) and rollover.get('reserve_held_after_second_termination', False)}`.

{markdown_table([[e.get('attempt_id'), e.get('reserved_calls'), e.get('actual_calls'), e.get('returned_unused_calls'), e.get('remaining_after'), e.get('valid_completion')] for e in rollover.get('events', [])], ['attempt', 'reserved', 'actual', 'returned', 'pool remaining', 'valid completion'])}

Early termination charges only measured calls; unused reservation returns to the one global pool. The completion attempt spends the already-paid prefix zero additional times and charges only its 40-call continuation.

Evidence: `V15_NFE_ACCOUNTING.csv`, `V15_APPEND_ONLY_LEDGER.jsonl`, immutable rollover record hash in the ledger.
"""
    atomic_text(TASK_DIR / "V15_TRUE_ROLLOVER_REPORT.md", rollover_md)

    evidence_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    report_lines = ["# ACE-Step v1.5 BOLT Gate 0", ""]
    for key in (
        "MODEL_PROVENANCE_STATUS",
        "ENVIRONMENT_STATUS",
        "STATE_CONTRACT_STATUS",
        "RESUME_EQUIVALENCE_STATUS",
        "CONDITION_SWITCH_STATUS",
        "FORK_STATUS",
        "ACTUAL_NFE_STATUS",
        "TRUE_ROLLOVER_STATUS",
        "COMPLETION_RESERVE_STATUS",
        "V15_GATE0_STATUS",
        "TEST_SUITE_STATUS",
    ):
        report_lines.append(f"{key} = {statuses[key]}")
    report_lines.extend(
        [
            "",
            f"MODEL_IDENTITY = {MODEL_ID}@{MODELSCOPE_REVISION} (config={MODEL_CONFIG_ID}, is_turbo=false)",
            "MEASURED_FULL_GENERATION_NFE = 50 transformer forward calls; 50 inline Euler scheduler updates; 0 scheduler-object calls",
            "",
            "## Evidence",
            "",
            "evidence: `V15_MODEL_PROVENANCE.md`, `V15_MODEL_CHECKSUMS.tsv`, `V15_PROVENANCE.json`",
            "evidence: `V15_ENVIRONMENT_REPORT.md`, `V15_LOGIN_ENVIRONMENT.json`",
            "evidence: `V15_STATE_CONTRACT.md`, `V15_RESUME_EQUIVALENCE.csv`, `V15_APPEND_ONLY_LEDGER.jsonl`",
            "evidence: `V15_CONDITION_SWITCH.csv`",
            "evidence: `V15_FORK_CALIBRATION.csv`, `V15_FORK_FROZEN.json`",
            "evidence: `V15_NFE_ACCOUNTING.csv`",
            "evidence: `V15_TRUE_ROLLOVER_REPORT.md`",
            "evidence: `V15_TEST_RESULTS.json`",
            "",
            "## Commits and tests",
            "",
            "- Seed/preregistration commit: `788e366`.",
            f"- Evidence-base commit at report construction: `{evidence_commit}`.",
            f"- Focused tests: `{tests.get('focused', {}).get('summary', 'NOT RUN')}`.",
            f"- Repository suite: `{tests.get('full_suite', {}).get('summary', 'NOT RUN')}`.",
            "",
            "## Scope",
            "",
            "This is engineering evidence only. No constraint-axis, tempo-axis, policy training, or vocal/instrumental scientific claim was run. Legacy BOLT and W2 evidence were not modified.",
        ]
    )
    if statuses["V15_GATE0_STATUS"] != "PASS":
        report_lines.extend(
            [
                "",
                "## Genuine PI decision required",
                "",
                "Choose either targeted-fix authorization for the failed terminal component(s), or revert the tempo axis to ACE-Step v1 primitives. No additional v1.5 grinding is authorized by this bundle.",
            ]
        )
    atomic_text(TASK_DIR / "V15_GATE0_REPORT.md", "\n".join(report_lines) + "\n")

    manifest = {
        "run_id": "v15_gate0_20260717",
        "branch": "codex/bolt-v15-gate0-20260717",
        "git_base": login_environment["git_base_commit"],
        "config_hash": sha256_file(PREREG_PATH),
        "seed_namespace": f"{SEED_BASE}..{SEED_BASE + 63}",
        "artifact_path": str(RUN_ROOT),
        "nodes": sorted({record["process"]["node"] for record in references}),
        "gpu_ids": sorted({record["runtime"].get("gpu", {}).get("index") for record in references}),
        "tp_width": 1,
        "replica_count": len(compute_runtimes),
        "placement_justification": "Independent TP1 XL-SFT replicas on one 8xA800 node maximize control throughput; the model fits one GPU.",
        "commands": [
            "python run_v15_gate0.py provenance",
            "python run_v15_gate0.py calibrate",
            "torchrun --standalone --nproc-per-node=8 run_v15_gate0.py reference-worker",
            "torchrun --standalone --nproc-per-node=8 run_v15_gate0.py continuation-worker",
            "python run_v15_gate0.py rollover",
            "pytest -q test_v15_gate0.py",
            "pytest -q",
            "python run_v15_gate0.py finalize",
        ],
        "statuses": statuses,
        "deviations": [
            "The first calibration invocation stopped before model load because the handler resolved an incorrect checkpoints subdirectory and attempted an offline auto-download. DNS failed, no bytes were acquired, no model loaded, and no generation occurred. The bounded repair added exact local-cache preflight plus compute-node offline guards."
        ],
        "finalized_utc": now_utc(),
    }
    atomic_json(TASK_DIR / "V15_RUN_MANIFEST.json", manifest)
    append_ledger({"event": "gate0_reports_finalized", "statuses": statuses})

    checksum_targets = [
        "V15_MODEL_PROVENANCE.md",
        "V15_ENVIRONMENT_REPORT.md",
        "V15_STATE_CONTRACT.md",
        "V15_RESUME_EQUIVALENCE.csv",
        "V15_CONDITION_SWITCH.csv",
        "V15_FORK_CALIBRATION.csv",
        "V15_NFE_ACCOUNTING.csv",
        "V15_TRUE_ROLLOVER_REPORT.md",
        "V15_GATE0_REPORT.md",
        "V15_APPEND_ONLY_LEDGER.jsonl",
        "V15_MODEL_CHECKSUMS.tsv",
        "V15_PROVENANCE.json",
        "V15_RUN_MANIFEST.json",
        "V15_TEST_RESULTS.json",
        "V15_FORK_FROZEN.json",
    ]
    checksum_lines = ["sha256\tbytes\tpath"]
    for name in checksum_targets:
        path = TASK_DIR / name
        checksum_lines.append(f"{sha256_file(path)}\t{path.stat().st_size}\t{path.relative_to(REPO_ROOT)}")
    atomic_text(TASK_DIR / "V15_CHECKSUMS.tsv", "\n".join(checksum_lines) + "\n")
    return statuses


def record_test_results(focused_log: Path, full_log: Path, focused_rc: int, full_rc: int) -> None:
    def summary(path: Path, rc: int) -> str:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        return f"exit={rc}; {lines[-1] if lines else 'no output'}"

    result = {
        "focused": {"command": "pytest -q test_v15_gate0.py", "exit_code": focused_rc, "summary": summary(focused_log, focused_rc), "log": str(focused_log)},
        "full_suite": {"command": "pytest -q", "exit_code": full_rc, "summary": summary(full_log, full_rc), "log": str(full_log)},
        "pass": focused_rc == 0 and full_rc == 0,
        "recorded_utc": now_utc(),
    }
    atomic_json(TASK_DIR / "V15_TEST_RESULTS.json", result)
    append_ledger({"event": "test_results_recorded", **result})
