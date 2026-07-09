import json
import statistics
from dataclasses import asdict
from pathlib import Path

from mprm.baselines.interface import BaselineResult


def parse_baseline_results(path: str | Path) -> list[BaselineResult]:
    path = Path(path)
    results = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            results.append(BaselineResult(**raw))
    return results


def save_baseline_results(results: list[BaselineResult], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def summarize_baseline(results: list[BaselineResult]) -> dict[str, dict[str, float]]:
    summary: dict[str, list[float]] = {}
    for r in results:
        for axis, value in r.metrics.items():
            summary.setdefault(axis, []).append(value)
    out: dict[str, dict[str, float]] = {}
    for axis, values in summary.items():
        mean = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        out[axis] = {"mean": mean, "std": std, "n": len(values), "min": min(values), "max": max(values)}
    return out
