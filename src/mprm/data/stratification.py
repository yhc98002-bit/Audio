from collections import Counter
from typing import Iterable

from mprm.data.prompts import Prompt

REQUIRED_STRATA = {
    "genre",
    "tempo_bin",
    "vocal_vs_instrumental",
    "lyric_density",
    "structural_complexity",
    "language",
    "prompt_specificity",
    "length_bin",
}


def validate_strata(prompts: Iterable[Prompt]) -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    for p in prompts:
        missing = REQUIRED_STRATA - set(p.strata.keys())
        if missing:
            issues.setdefault(p.prompt_id, []).append(f"missing strata: {sorted(missing)}")
    return issues


def stratify(prompts: list[Prompt]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = {k: Counter() for k in REQUIRED_STRATA}
    for p in prompts:
        for k in REQUIRED_STRATA:
            counts[k][p.strata.get(k, "<missing>")] += 1
    return {k: dict(v) for k, v in counts.items()}
