import json
import os
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunEntry:
    run_id: str
    rung_id: str
    stage: str
    event: str
    timestamp: str
    host: str
    pid: int
    config_hash: str | None = None
    git_sha: str | None = None
    model_sha: str | None = None
    split: str | None = None
    seed: int | None = None
    gpu_count: int | None = None
    elapsed_seconds: float | None = None
    gpu_hours: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None


class RunLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._provenance: dict[str, dict[str, str | None]] = {}

    def append(self, entry: RunEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def start(self, run_id: str, rung_id: str, stage: str, config_hash: str | None = None,
              git_sha: str | None = None, model_sha: str | None = None,
              split: str | None = None, seed: int | None = None,
              gpu_count: int | None = None) -> RunEntry:
        self._provenance[run_id] = {
            "config_hash": config_hash,
            "git_sha": git_sha,
            "model_sha": model_sha,
        }
        entry = RunEntry(
            run_id=run_id,
            rung_id=rung_id,
            stage=stage,
            event="start",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            host=socket.gethostname(),
            pid=os.getpid(),
            config_hash=config_hash,
            git_sha=git_sha,
            model_sha=model_sha,
            split=split,
            seed=seed,
            gpu_count=gpu_count,
        )
        self.append(entry)
        return entry

    def final(self, run_id: str, rung_id: str, stage: str, metrics: dict[str, Any],
              notes: str | None = None, split: str | None = None, seed: int | None = None,
              gpu_count: int | None = None, elapsed_seconds: float | None = None,
              config_hash: str | None = None, git_sha: str | None = None,
              model_sha: str | None = None) -> RunEntry:
        provenance = self._provenance.get(run_id, {})
        gpu_hours = None
        if elapsed_seconds is not None and gpu_count is not None and gpu_count > 0:
            gpu_hours = (elapsed_seconds / 3600.0) * gpu_count
        entry = RunEntry(
            run_id=run_id,
            rung_id=rung_id,
            stage=stage,
            event="final",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            host=socket.gethostname(),
            pid=os.getpid(),
            config_hash=config_hash if config_hash is not None else provenance.get("config_hash"),
            git_sha=git_sha if git_sha is not None else provenance.get("git_sha"),
            model_sha=model_sha if model_sha is not None else provenance.get("model_sha"),
            split=split,
            seed=seed,
            gpu_count=gpu_count,
            elapsed_seconds=elapsed_seconds,
            gpu_hours=gpu_hours,
            metrics=metrics,
            notes=notes,
        )
        self.append(entry)
        return entry

    def fail(self, run_id: str, rung_id: str, stage: str, error: str,
             config_hash: str | None = None, git_sha: str | None = None,
             model_sha: str | None = None) -> RunEntry:
        provenance = self._provenance.get(run_id, {})
        entry = RunEntry(
            run_id=run_id,
            rung_id=rung_id,
            stage=stage,
            event="fail",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            host=socket.gethostname(),
            pid=os.getpid(),
            config_hash=config_hash if config_hash is not None else provenance.get("config_hash"),
            git_sha=git_sha if git_sha is not None else provenance.get("git_sha"),
            model_sha=model_sha if model_sha is not None else provenance.get("model_sha"),
            notes=error,
        )
        self.append(entry)
        return entry
