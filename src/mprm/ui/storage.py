"""Append-only annotation storage for human evaluation (Block D.hum)."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Annotation:
    pair_id: str
    rater_id: str
    timestamp: str
    axis_preferences: dict[str, str]
    worst_section_label_a: str | None = None
    worst_section_label_b: str | None = None
    section_local_preferences: dict[str, str] = field(default_factory=dict)
    notes: str | None = None


class AnnotationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, annotation: Annotation) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(annotation), ensure_ascii=False) + "\n")

    def load_all(self) -> list[Annotation]:
        if not self.path.exists():
            return []
        out: list[Annotation] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                out.append(Annotation(**json.loads(line)))
        return out

    @staticmethod
    def now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
