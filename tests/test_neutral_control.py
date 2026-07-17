from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "analysis_exit1_v2/neutral_control/neutral_control.py"
SPEC = importlib.util.spec_from_file_location("neutral_control", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeTokenizer:
    """Context-free tokenizer sufficient for manifest-contract unit tests."""

    def __call__(self, text: str, **_kwargs) -> dict[str, list[int]]:
        pieces = text.replace(",", " ,").replace(".", " .").split()
        return {"input_ids": [sum(map(ord, piece)) % 10_000 for piece in pieces] + [1]}


def source_prompts() -> list[dict]:
    return [
        {
            "factorial_prompt_rank": rank,
            "prompt_id": f"held_out_{rank:04d}",
            "text": f"Synthetic instrumental request {rank}.",
            "lyrics": None,
            "vocal_stratum": "instrumental",
        }
        for rank in range(32)
    ]


def test_selected_source_prompts_freezes_ranks_zero_through_23() -> None:
    selected = MODULE.selected_source_prompts(list(reversed(source_prompts())))
    assert [row["factorial_prompt_rank"] for row in selected] == list(range(24))


def test_selected_source_prompts_rejects_changed_canonical_count() -> None:
    with pytest.raises(ValueError, match="count changed"):
        MODULE.selected_source_prompts(source_prompts()[:-1])


def test_frozen_rows_match_negative_and_neutral_full_token_counts() -> None:
    rows = MODULE.build_frozen_rows(source_prompts(), FakeTokenizer())
    assert len(rows) == 24
    assert all(
        row["negative_full_token_count_including_eos"]
        == row["neutral_full_token_count_including_eos"]
        for row in rows
    )
    assert all(
        row["negative_append_token_delta"] == row["neutral_append_token_delta"]
        for row in rows
    )
    assert all(
        row["negative_conditioning_token_count_including_eos"]
        == row["neutral_conditioning_token_count_including_eos"]
        for row in rows
    )


def test_generation_manifest_cardinality_and_registered_seed_formula() -> None:
    rows = MODULE.build_frozen_rows(source_prompts(), FakeTokenizer())
    manifest = MODULE.build_generation_manifest(rows)
    assert len(manifest) == 192
    assert len({row["seed"] for row in manifest}) == 192
    assert min(row["seed"] for row in manifest) == 2_071_000_000
    assert max(row["seed"] for row in manifest) == 2_071_023_007
    assert {row["cfg_scale"] for row in manifest} == {5.0}
    assert {row["generation_config_sha256"] for row in manifest} == {
        MODULE.GENERATION_CONFIG_SHA256
    }


def test_neutral_insertion_contains_no_forbidden_vocal_lexeme() -> None:
    words = set(MODULE.re.findall(r"[a-z]+", MODULE.NEUTRAL_INSERTION.lower()))
    assert not words & MODULE.FORBIDDEN_NEUTRAL_LEXEMES


def test_prompt_cluster_ci_resamples_prompt_means() -> None:
    rows = []
    for prompt in range(24):
        for seed_idx in range(8):
            rows.append(
                {
                    "prompt_id": f"p{prompt:02d}",
                    "violation": int(prompt >= 12),
                    "seed_idx": seed_idx,
                }
            )
    point, lower, upper = MODULE.prompt_cluster_ci(rows, "violation", 1000, 9)
    assert point == 0.5
    assert lower < point < upper


def test_paired_prompt_delta_averages_seeds_within_prompt() -> None:
    rows = []
    for prompt in range(24):
        for seed_idx in range(8):
            rows.extend(
                [
                    {
                        "prompt_id": f"p{prompt:02d}",
                        "condition": "neutral-matched",
                        "violation": 0,
                        "seed_idx": seed_idx,
                    },
                    {
                        "prompt_id": f"p{prompt:02d}",
                        "condition": "negative",
                        "violation": 1,
                        "seed_idx": seed_idx,
                    },
                ]
            )
    result = MODULE.paired_prompt_delta(
        rows, "neutral-matched", "negative", replicates=1000, seed=10
    )
    assert result["estimate"] == -1.0
    assert result["ci95"] == [-1.0, -1.0]
    assert result["pairing"] == "prompt-paired, seed-independent"


def test_frozen_artifacts_if_present_have_exact_contract() -> None:
    prompt_path = ROOT / "analysis_exit1_v2/neutral_control/NEUTRAL_PROMPTS.jsonl"
    manifest_path = ROOT / "analysis_exit1_v2/neutral_control/NEUTRAL_GENERATION_MANIFEST.csv"
    if not prompt_path.exists() or not manifest_path.exists():
        pytest.skip("pre-generation freeze artifacts have not been materialized yet")
    prompts = [json.loads(line) for line in prompt_path.read_text().splitlines() if line]
    manifest = MODULE.read_csv(manifest_path)
    assert len(prompts) == 24
    assert len(manifest) == 192
    assert [row["neutral_control_rank"] for row in prompts] == list(range(24))
    assert all(
        row["negative_full_token_count_including_eos"]
        == row["neutral_full_token_count_including_eos"]
        for row in prompts
    )
    assert all(
        row["negative_conditioning_token_count_including_eos"]
        == row["neutral_conditioning_token_count_including_eos"]
        for row in prompts
    )
    assert {int(row["seed"]) for row in manifest} == {
        MODULE.SEED_BASE + rank * 1000 + seed_idx
        for rank in range(24)
        for seed_idx in range(8)
    }
