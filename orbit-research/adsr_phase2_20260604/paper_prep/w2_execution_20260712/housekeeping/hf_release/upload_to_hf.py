#!/usr/bin/env python3
"""Upload the reviewed ADSR staging package; intentionally requires --execute."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("dry guard: pass --execute only after the post-gate human release decision")
    token = os.environ.get("HF_TOKEN", "")
    repo_id = os.environ.get("HF_REPO_ID", "")
    if not token or not repo_id:
        raise SystemExit("HF_TOKEN and HF_REPO_ID must be supplied as environment variables")
    manifest = HERE / "UPLOAD_MANIFEST.csv"
    if not manifest.is_file():
        raise SystemExit("UPLOAD_MANIFEST.csv is missing; build and review it first")
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(HERE),
        ignore_patterns=["upload_to_hf.py", "__pycache__/*"],
        commit_message="Stage reviewed ADSR evidence package",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
