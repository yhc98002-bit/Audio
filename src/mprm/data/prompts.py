import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class Prompt:
    prompt_id: str
    text: str
    lyrics: str | None
    structure_hint: str | None
    duration_target: float
    metadata: dict = field(default_factory=dict)
    strata: dict = field(default_factory=dict)


def load_prompts(path: str | Path) -> list[Prompt]:
    path = Path(path)
    prompts: list[Prompt] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            prompts.append(Prompt(**raw))
    return prompts


def save_prompts(prompts: Iterable[Prompt], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for p in prompts:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
