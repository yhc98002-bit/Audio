#!/usr/bin/env python3
"""Inspect whether the installed transformers build can load T5Gemma."""

from __future__ import annotations

import importlib
import json

import transformers


def probe_attr(name: str) -> dict[str, str]:
    try:
        value = getattr(transformers, name)
        return {"status": "ok", "repr": repr(value)}
    except Exception as exc:  # pragma: no cover - diagnostic script.
        return {"status": "fail", "error": repr(exc)}


def probe_module(name: str) -> dict[str, object]:
    try:
        module = importlib.import_module(name)
        return {
            "status": "ok",
            "t5gemma_names": [x for x in dir(module) if "T5Gemma" in x],
        }
    except Exception as exc:  # pragma: no cover - diagnostic script.
        return {"status": "fail", "error": repr(exc)}


def main() -> None:
    result = {
        "transformers_version": transformers.__version__,
        "attrs": {
            name: probe_attr(name)
            for name in ["T5GemmaEncoderModel", "AutoTokenizer", "AutoConfig"]
        },
        "modules": {
            name: probe_module(name)
            for name in [
                "transformers.models.t5gemma",
                "transformers.models.t5gemma.modeling_t5gemma",
                "transformers.models.t5gemma.configuration_t5gemma",
            ]
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
