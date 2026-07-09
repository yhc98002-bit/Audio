#!/usr/bin/env python3
"""Emit a compact JSON report for the SA3 execution environment."""

from __future__ import annotations

import importlib
import json
import socket
import sys
import time


MODULES = [
    "torch",
    "torchaudio",
    "transformers",
    "safetensors",
    "stable_audio_3",
    "stable_audio_tools",
]


def main() -> None:
    info: dict[str, object] = {
        "host": socket.gethostname(),
        "python": sys.version,
        "module_imports": {},
    }
    imports: dict[str, object] = {}
    for name in MODULES:
        started = time.time()
        try:
            module = importlib.import_module(name)
            imports[name] = {
                "status": "ok",
                "version": getattr(module, "__version__", "imported_no_version"),
                "seconds": round(time.time() - started, 3),
            }
        except Exception as exc:  # pragma: no cover - diagnostic script.
            imports[name] = {
                "status": "fail",
                "error": repr(exc),
                "seconds": round(time.time() - started, 3),
            }
    info["module_imports"] = imports
    try:
        import torch

        info["cuda_available"] = torch.cuda.is_available()
        info["cuda_device_count"] = torch.cuda.device_count()
        if torch.cuda.is_available():
            info["gpu0"] = torch.cuda.get_device_name(0)
    except Exception as exc:  # pragma: no cover - diagnostic script.
        info["cuda_error"] = repr(exc)
    print(json.dumps(info, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
