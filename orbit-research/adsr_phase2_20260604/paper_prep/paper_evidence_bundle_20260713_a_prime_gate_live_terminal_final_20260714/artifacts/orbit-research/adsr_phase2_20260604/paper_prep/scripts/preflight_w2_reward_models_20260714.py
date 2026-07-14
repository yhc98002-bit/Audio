#!/usr/bin/env python3
"""Fail closed unless the W2 live reward stack can resolve fully offline."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ENV_PATHS = {
    "LAION_CLAP_BERT_DIR": "directory",
    "LAION_CLAP_ROBERTA_DIR": "directory",
    "LAION_CLAP_BART_DIR": "directory",
    "MERT_LOCAL_PATH": "directory",
    "AUDIOBOX_AES_CKPT": "file",
}


def validate_paths(home: Path | None = None) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for variable, kind in ENV_PATHS.items():
        raw = os.environ.get(variable, "")
        if not raw:
            raise RuntimeError(f"required offline path variable is unset: {variable}")
        path = Path(raw).expanduser().resolve()
        valid = path.is_dir() if kind == "directory" else path.is_file()
        if not valid:
            raise RuntimeError(f"required offline {kind} is missing: {variable}={path}")
        resolved[variable] = str(path)
    home = home or Path.home()
    whisper = home / ".cache" / "whisper" / "large-v3.pt"
    clap = home / ".cache" / "clap" / "630k-audioset-best.pt"
    for label, path in {"WHISPER_LARGE_V3": whisper, "CLAP_630K_AUDIOSET": clap}.items():
        if not path.is_file():
            raise RuntimeError(f"required offline checkpoint is missing: {label}={path}")
        resolved[label] = str(path.resolve())
    return resolved


def validate_imports(paths: dict[str, str]) -> dict[str, str]:
    from mprm.compat import laion_clap_local_tokenizers as clap_shim
    from mprm.rewards.mert import MertReward
    from transformers import BartTokenizer, Wav2Vec2FeatureExtractor

    bart_resolved = clap_shim._resolve("facebook/bart-base")
    if bart_resolved != paths["LAION_CLAP_BART_DIR"]:
        raise RuntimeError(f"BART shim did not resolve locally: {bart_resolved}")
    BartTokenizer.from_pretrained("facebook/bart-base", local_files_only=True)
    mert_target = MertReward()._resolve_load_target()
    if Path(mert_target).resolve() != Path(paths["MERT_LOCAL_PATH"]):
        raise RuntimeError(f"MERT did not resolve locally: {mert_target}")
    Wav2Vec2FeatureExtractor.from_pretrained(mert_target, local_files_only=True)
    import laion_clap  # noqa: F401

    return {"bart_target": bart_resolved, "mert_target": mert_target}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths-only", action="store_true")
    args = parser.parse_args()
    paths = validate_paths()
    imports = {} if args.paths_only else validate_imports(paths)
    print(
        json.dumps(
            {
                "status": "PASS_OFFLINE_REWARD_PREFLIGHT",
                "offline_flags": {
                    "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
                    "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
                },
                "paths": paths,
                "imports": imports,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
