#!/usr/bin/env python3
"""Prepare, execute, score, and report the Exit-1 matched neutral control."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import io
import json
import math
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PAPER = ROOT / "orbit-research/adsr_phase2_20260604/paper_prep"
sys.path.insert(0, str(ROOT))

FACTORIAL_DIR = PAPER / "w2_execution_20260712/factorial"
FACTORIAL_PROMPTS = FACTORIAL_DIR / "FACTORIAL_PROMPTS.jsonl"
FACTORIAL_GENERATION_MANIFEST = FACTORIAL_DIR / "FACTORIAL_GENERATION_MANIFEST.csv"
FACTORIAL_POSITIVE_MANIFEST = FACTORIAL_DIR / "FACTORIAL_POSITIVE_CORRECTION_MANIFEST.csv"
FACTORIAL_SCORE_ROWS = (
    PAPER / "autochain_20260712/factorial/FACTORIAL_CORRECTED_SCORE_ROWS.csv"
)
T6_PROMOTION_REPORT = PAPER / "autochain_20260712/T6_PROMOTION_REPORT.md"
T6_PROMOTION_RESULT = PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json"

PROMPTS = OUT / "NEUTRAL_PROMPTS.jsonl"
MANIFEST = OUT / "NEUTRAL_GENERATION_MANIFEST.csv"
PREREGISTRATION = OUT / "NEUTRAL_PREREGISTRATION.json"
PREP_AUDIT = OUT / "NEUTRAL_PREP_AUDIT.json"
FREEZE_SHA256SUMS = OUT / "NEUTRAL_FREEZE_SHA256SUMS"
GENERATION_LEDGER_DIR = OUT / "generation_ledgers"
SCORING_LEDGER_DIR = OUT / "scoring_ledgers"
AUDIO_DIR = OUT / "audio/neutral_matched"
GENERATION_AUDIT = OUT / "NEUTRAL_GENERATION_AUDIT.json"
RUN_MANIFEST = OUT / "NEUTRAL_RUN_MANIFEST.json"
AUDIO_SHA256SUMS = OUT / "NEUTRAL_AUDIO_SHA256SUMS"
SCORING_AUDIT = OUT / "NEUTRAL_SCORING_AUDIT.json"
SCORING_RUN_MANIFEST = OUT / "NEUTRAL_SCORING_RUN_MANIFEST.json"
NEUTRAL_SCORES = OUT / "NEUTRAL_SCORES.csv"
FOUR_CELL_ROWS = OUT / "FOUR_CELL_SCORE_ROWS.csv"
FOUR_CELL_RESULTS_CSV = OUT / "FOUR_CELL_RESULTS.csv"
FOUR_CELL_RESULTS_JSON = OUT / "FOUR_CELL_RESULTS.json"
TEST_RESULTS = OUT / "FULL_TEST_RESULTS.txt"
TEST_SUMMARY = OUT / "FULL_TEST_RESULT_SUMMARY.json"
REPORT = OUT / "NEUTRAL_CONTROL_REPORT.md"

N_PROMPTS = 24
N_SEEDS = 8
SEED_BASE = 2_071_000_000
SEED_MAX = SEED_BASE + (N_PROMPTS - 1) * 1000 + (N_SEEDS - 1)
GUIDANCE_SCALE = 5.0
DURATION_SECONDS = 15.0
INFERENCE_STEPS = 30
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20_260_717
RANDOMIZATION_REPLICATES = 100_000
RANDOMIZATION_SEED = 20_260_718

NEGATIVE_INSERTION = "pure instrumental, no vocals, no singing, no voice"
NEUTRAL_INSERTION = (
    "studio recording, carefully produced, cleanly mixed, balanced acoustics"
)
FORBIDDEN_NEUTRAL_LEXEMES = {
    "vocal",
    "vocals",
    "voice",
    "voices",
    "sing",
    "singing",
    "singer",
    "choir",
    "chant",
    "speech",
    "spoken",
    "rap",
    "lyrics",
}

TOKENIZER_DIR_DEFAULT = (
    Path("/HOME/paratera_xy/pxy1289/.cache/modelscope/hub/models")
    / "ACE-Step/ACE-Step-v1-3___5B/umt5-base"
)
EXPECTED_TOKENIZER_JSON_SHA256 = (
    "20a46ac256746594ed7e1e3ef733b83fbc5a6f0922aa7480eda961743de080ef"
)

FACTORIAL_SOURCE_COMMIT = "69a6d79e52bf44972c4f827c99b147a873dbf69a"
POSITIVE_CORRECTION_COMMIT = "eeb0aa11c090aef294f1d9e94e67970872c2eb48"
T6_PROMOTION_COMMIT = "168d12f1e47f555c85b7b9085da947b5ef261835"
EXPECTED_FACTORIAL_PROMPTS_SHA256 = (
    "1c7e3cb40229e0be4cf25ef466ed872f0acc0f5772f043afe11882b5f115729c"
)
EXPECTED_FACTORIAL_MANIFEST_SHA256 = (
    "11018013cdc9eba4b40686d64900da4694353e49ac4c0813d190411e77b628d2"
)
EXPECTED_POSITIVE_MANIFEST_SHA256 = (
    "440a63bf1ea93353456b9a69d9c5d67e956449b8a1a37fbf90281c2e86f16972"
)
EXPECTED_FACTORIAL_SCORE_ROWS_SHA256 = (
    "cd7d0f08089bf339b45bbd6dad0902d3335c9dfec9fd331b203c7a6962864038"
)

GENERATION_EXTRAS = {
    "cfg_type": "apg",
    "guidance_interval": 0.5,
    "scheduler_type": "euler",
    "use_erg_tag": False,
    "use_erg_lyric": False,
    "use_erg_diffusion": False,
}
GENERATION_CONFIG = {
    "model": "ACE-Step/ACE-Step-v1-3.5B",
    "precision": "bfloat16",
    "duration_seconds": DURATION_SECONDS,
    "inference_steps": INFERENCE_STEPS,
    "scheduler": "Euler",
    "scheduler_shift": 3.0,
    "cfg_type": "apg",
    "guidance_scale": GUIDANCE_SCALE,
    "guidance_interval": 0.5,
    "erg_tag": False,
    "erg_lyric": False,
    "erg_diffusion": False,
    "guidance_rescale": 0.0,
    "omega_scale": 1.0,
    "sample_rate_hz": 48_000,
    "clips_per_process_call": 1,
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


GENERATION_CONFIG_SHA256 = hashlib.sha256(
    canonical_json(GENERATION_CONFIG).encode("utf-8")
).hexdigest()

FROZEN_INPUT_PATHS = (
    Path("analysis_exit1_v2/neutral_control/neutral_control.py"),
    Path("analysis_exit1_v2/neutral_control/NEUTRAL_PROMPTS.jsonl"),
    Path("analysis_exit1_v2/neutral_control/NEUTRAL_GENERATION_MANIFEST.csv"),
    Path("analysis_exit1_v2/neutral_control/NEUTRAL_PREREGISTRATION.json"),
    Path("analysis_exit1_v2/neutral_control/NEUTRAL_PREP_AUDIT.json"),
    Path("analysis_exit1_v2/neutral_control/NEUTRAL_FREEZE_SHA256SUMS"),
    Path("analysis_exit1_v2/exit1_evaluator_v2.py"),
    Path("orbit-research/adsr_phase2_20260604/paper_prep/SEED_REGISTRY.md"),
    Path(
        "orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/"
        "T6_PROMOTION_REPORT.md"
    ),
    Path(
        "orbit-research/adsr_phase2_20260604/paper_prep/autochain_20260712/"
        "T6_PROMOTION_RESULT.json"
    ),
    Path("tests/test_neutral_control.py"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite differing artifact: {path}")
        return
    path.write_text(content, encoding="utf-8")


def write_json_once(path: Path, value: object) -> None:
    _write_once(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl_once(path: Path, rows: Sequence[dict]) -> None:
    content = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows
    )
    _write_once(path, content)


def csv_text(rows: Sequence[dict]) -> str:
    if not rows:
        raise ValueError("refusing to serialize an empty CSV")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_csv_once(path: Path, rows: Sequence[dict]) -> None:
    _write_once(path, csv_text(rows))


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def tokenizer_dir() -> Path:
    checkpoint = os.environ.get("ACE_STEP_CHECKPOINT_DIR")
    if checkpoint:
        candidate = Path(checkpoint) / "umt5-base"
        if candidate.is_dir():
            return candidate
    return Path(os.environ.get("NEUTRAL_CONTROL_TOKENIZER_DIR", TOKENIZER_DIR_DEFAULT))


def load_tokenizer(path: Path):
    # Load the exact tokenizer.json backend used by AutoTokenizer. This avoids
    # importing unrelated transformer generation/scikit-learn/scipy modules in
    # the CPU-only pre-generation freeze while producing identical token IDs.
    from tokenizers import Tokenizer

    if not path.is_dir():
        raise FileNotFoundError(f"frozen tokenizer directory is unavailable: {path}")
    tokenizer_json = path / "tokenizer.json"
    observed_hash = sha256_file(tokenizer_json)
    if observed_hash != EXPECTED_TOKENIZER_JSON_SHA256:
        raise ValueError(
            "frozen tokenizer hash mismatch: "
            f"expected {EXPECTED_TOKENIZER_JSON_SHA256}, observed {observed_hash}"
        )
    return Tokenizer.from_file(str(tokenizer_json)), observed_hash


def token_ids(tokenizer, text: str) -> list[int]:
    if tokenizer.__class__.__module__.startswith("tokenizers"):
        return [int(value) for value in tokenizer.encode(text).ids[:256]]
    encoded = tokenizer(text, truncation=True, max_length=256)
    values = encoded["input_ids"]
    if values and isinstance(values[0], list):
        values = values[0]
    return [int(value) for value in values]


def composed_text(base_text: str, insertion: str) -> str:
    return base_text.rstrip(". ") + ", " + insertion


def actual_conditioning_text(text: str, structure_hint: object) -> str:
    """Mirror AceStepModel.sample's final text-conditioning construction."""
    return f"{text} [structure: {structure_hint}]" if structure_hint else text


def _assert_source_hashes() -> dict[str, str]:
    expected = {
        "factorial_prompts": (FACTORIAL_PROMPTS, EXPECTED_FACTORIAL_PROMPTS_SHA256),
        "factorial_generation_manifest": (
            FACTORIAL_GENERATION_MANIFEST,
            EXPECTED_FACTORIAL_MANIFEST_SHA256,
        ),
        "factorial_positive_manifest": (
            FACTORIAL_POSITIVE_MANIFEST,
            EXPECTED_POSITIVE_MANIFEST_SHA256,
        ),
        "factorial_score_rows": (
            FACTORIAL_SCORE_ROWS,
            EXPECTED_FACTORIAL_SCORE_ROWS_SHA256,
        ),
    }
    observed: dict[str, str] = {}
    for name, (path, expected_hash) in expected.items():
        value = sha256_file(path)
        if value != expected_hash:
            raise ValueError(
                f"canonical source hash mismatch for {name}: expected {expected_hash}, "
                f"observed {value}"
            )
        observed[name] = value
    return observed


def selected_source_prompts(rows: Sequence[dict]) -> list[dict]:
    if len(rows) != 32:
        raise ValueError(f"canonical factorial prompt count changed: {len(rows)} != 32")
    ranked = sorted(rows, key=lambda row: int(row["factorial_prompt_rank"]))
    ranks = [int(row["factorial_prompt_rank"]) for row in ranked]
    if ranks != list(range(32)):
        raise ValueError("canonical factorial ranks are not exactly 0..31")
    selected = ranked[:N_PROMPTS]
    if any(row.get("vocal_stratum") != "instrumental" for row in selected):
        raise ValueError("rank-0..23 selection contains a non-instrumental prompt")
    return selected


def build_frozen_rows(source_rows: Sequence[dict], tokenizer) -> list[dict]:
    neutral_words = set(re.findall(r"[a-z]+", NEUTRAL_INSERTION.lower()))
    leaked = sorted(neutral_words & FORBIDDEN_NEUTRAL_LEXEMES)
    if leaked:
        raise ValueError(f"neutral insertion contains forbidden vocal lexemes: {leaked}")

    negative_insertion_ids = token_ids(tokenizer, NEGATIVE_INSERTION)
    neutral_insertion_ids = token_ids(tokenizer, NEUTRAL_INSERTION)
    if len(negative_insertion_ids) != len(neutral_insertion_ids):
        raise ValueError("standalone neutral and negative insertion token counts differ")

    frozen: list[dict] = []
    for source in selected_source_prompts(source_rows):
        base_text = str(source["text"])
        negative_text = composed_text(base_text, NEGATIVE_INSERTION)
        neutral_text = composed_text(base_text, NEUTRAL_INSERTION)
        negative_conditioning_text = actual_conditioning_text(
            negative_text, source.get("structure_hint")
        )
        neutral_conditioning_text = actual_conditioning_text(
            neutral_text, source.get("structure_hint")
        )
        base_ids = token_ids(tokenizer, base_text)
        negative_ids = token_ids(tokenizer, negative_text)
        neutral_ids = token_ids(tokenizer, neutral_text)
        negative_conditioning_ids = token_ids(tokenizer, negative_conditioning_text)
        neutral_conditioning_ids = token_ids(tokenizer, neutral_conditioning_text)
        if len(negative_ids) != len(neutral_ids):
            raise ValueError(
                f"full-prompt token mismatch for {source['prompt_id']}: "
                f"negative={len(negative_ids)}, neutral={len(neutral_ids)}"
            )
        if len(negative_ids) >= 256:
            raise ValueError(f"prompt reaches tokenizer truncation boundary: {source['prompt_id']}")
        if len(negative_conditioning_ids) != len(neutral_conditioning_ids):
            raise ValueError(
                f"actual conditioning token mismatch for {source['prompt_id']}: "
                f"negative={len(negative_conditioning_ids)}, "
                f"neutral={len(neutral_conditioning_ids)}"
            )
        if len(negative_conditioning_ids) >= 256:
            raise ValueError(
                f"actual conditioning reaches truncation boundary: {source['prompt_id']}"
            )
        frozen.append(
            {
                **source,
                "neutral_control_rank": int(source["factorial_prompt_rank"]),
                "neutral_insertion": NEUTRAL_INSERTION,
                "negative_reference_insertion": NEGATIVE_INSERTION,
                "neutral_full_text": neutral_text,
                "negative_reference_full_text": negative_text,
                "base_token_count_including_eos": len(base_ids),
                "negative_full_token_count_including_eos": len(negative_ids),
                "neutral_full_token_count_including_eos": len(neutral_ids),
                "negative_append_token_delta": len(negative_ids) - len(base_ids),
                "neutral_append_token_delta": len(neutral_ids) - len(base_ids),
                "negative_insertion_token_count_including_eos": len(
                    negative_insertion_ids
                ),
                "neutral_insertion_token_count_including_eos": len(neutral_insertion_ids),
                "negative_full_token_ids_sha256": sha256_text(canonical_json(negative_ids)),
                "neutral_full_token_ids_sha256": sha256_text(canonical_json(neutral_ids)),
                "negative_conditioning_token_count_including_eos": len(
                    negative_conditioning_ids
                ),
                "neutral_conditioning_token_count_including_eos": len(
                    neutral_conditioning_ids
                ),
                "negative_conditioning_token_ids_sha256": sha256_text(
                    canonical_json(negative_conditioning_ids)
                ),
                "neutral_conditioning_token_ids_sha256": sha256_text(
                    canonical_json(neutral_conditioning_ids)
                ),
                "neutral_full_text_sha256": sha256_text(neutral_text),
                "selection_assumption": (
                    "task specifies 24 while canonical factorial contains 32; freeze "
                    "pre-existing historical-N2-risk ranks 0-23 without using factorial-"
                    "condition outcomes in the 24-of-32 selection rule, before neutral-"
                    "control generation"
                ),
            }
        )
    return frozen


def build_generation_manifest(prompt_rows: Sequence[dict]) -> list[dict]:
    rows: list[dict] = []
    seeds: set[int] = set()
    for prompt in prompt_rows:
        rank = int(prompt["neutral_control_rank"])
        for seed_idx in range(N_SEEDS):
            seed = SEED_BASE + rank * 1000 + seed_idx
            seeds.add(seed)
            output = AUDIO_DIR / prompt["prompt_id"] / (
                f"neutral_matched_s{seed_idx:02d}_{seed}.flac"
            )
            rows.append(
                {
                    "task_id": f"neutral_control_{rank:02d}_{seed_idx:02d}",
                    "prompt_rank": rank,
                    "prompt_id": prompt["prompt_id"],
                    "condition": "neutral_matched",
                    "seed_idx": seed_idx,
                    "seed": seed,
                    "cfg_scale": GUIDANCE_SCALE,
                    "duration_seconds": DURATION_SECONDS,
                    "inference_steps": INFERENCE_STEPS,
                    "neutral_insertion": NEUTRAL_INSERTION,
                    "neutral_full_text_sha256": prompt["neutral_full_text_sha256"],
                    "generation_config_sha256": GENERATION_CONFIG_SHA256,
                    "output_path": str(output.relative_to(ROOT)),
                }
            )
    if len(rows) != N_PROMPTS * N_SEEDS:
        raise AssertionError("neutral generation cardinality mismatch")
    if len(seeds) != len(rows) or min(seeds) != SEED_BASE or max(seeds) != SEED_MAX:
        raise AssertionError("neutral seed range or uniqueness mismatch")
    return rows


def _parse_canonical_instrument() -> dict:
    from analysis_exit1_v2.exit1_evaluator_v2 import parse_canonical_instrument

    parsed = parse_canonical_instrument(T6_PROMOTION_REPORT, T6_PROMOTION_RESULT)
    if parsed["family"] != "or":
        raise ValueError("neutral control is frozen for the promoted OR family")
    if parsed["report_exact_line"] != "- Selected family: `or`.":
        raise ValueError("Dispatch A exact selected-family line changed")
    return parsed


def canonical_prediction(instrument: dict, demucs_score: float, panns_score: float) -> int:
    from analysis_exit1_v2.exit1_evaluator_v2 import canonical_prediction as predict

    return predict(
        instrument["family"],
        float(demucs_score),
        float(panns_score),
        float(instrument["demucs_threshold"]),
        float(instrument["panns_threshold"]),
    )


def prepare() -> dict:
    if AUDIO_DIR.exists() and any(AUDIO_DIR.rglob("*")):
        raise RuntimeError("prepare must run before generation; neutral audio already exists")
    if GENERATION_LEDGER_DIR.exists() and any(GENERATION_LEDGER_DIR.glob("*.jsonl")):
        raise RuntimeError("prepare must run before generation ledgers exist")
    source_hashes = _assert_source_hashes()
    instrument = _parse_canonical_instrument()
    tok_dir = tokenizer_dir()
    tokenizer, tokenizer_hash = load_tokenizer(tok_dir)
    prompt_rows = build_frozen_rows(read_jsonl(FACTORIAL_PROMPTS), tokenizer)
    manifest_rows = build_generation_manifest(prompt_rows)

    if not all(
        row["negative_full_token_count_including_eos"]
        == row["neutral_full_token_count_including_eos"]
        for row in prompt_rows
    ):
        raise AssertionError("per-prompt full token match failed")
    if not all(
        row["negative_append_token_delta"] == row["neutral_append_token_delta"]
        for row in prompt_rows
    ):
        raise AssertionError("per-prompt append token delta match failed")
    if not all(
        row["negative_conditioning_token_count_including_eos"]
        == row["neutral_conditioning_token_count_including_eos"]
        for row in prompt_rows
    ):
        raise AssertionError("actual ACE-Step conditioning token match failed")

    preregistration = {
        "status": "FROZEN_BEFORE_GENERATION",
        "objective": (
            "distinguish negative-wording semantics from insertion length/specificity "
            "using one preregistered, vocally inert by design, token-matched neutral condition"
        ),
        "created_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
        "prompt_selection": {
            "canonical_count": 32,
            "requested_count": N_PROMPTS,
            "selected_factorial_ranks": list(range(N_PROMPTS)),
            "rule": (
                "first 24 under the already preregistered ascending historical-N2-clean-rate "
                "risk rank"
            ),
            "assumption": (
                "No separate 24-row canonical artifact exists. The task's cardinality "
                "is implemented as ranks 0-23 using the pre-existing historical-N2-risk "
                "rank without using factorial-condition outcomes in the 24-of-32 selection "
                "rule, and is frozen before neutral-control generation. The subset is "
                "historically N2-outcome-ranked and inference does not automatically "
                "generalize to all 32 factorial prompts."
            ),
        },
        "neutral_insertion": NEUTRAL_INSERTION,
        "negative_reference_insertion": NEGATIVE_INSERTION,
        "token_contract": {
            "tokenizer_dir": str(tok_dir),
            "tokenizer_json_sha256": tokenizer_hash,
            "audit_backend": (
                "tokenizers.Tokenizer.from_file on the exact tokenizer.json loaded by "
                "ACE-Step AutoTokenizer"
            ),
            "max_length": 256,
            "match": (
                "standalone insertion token count and composed full-prompt token count, "
                "including EOS, must equal the negative-reference condition for every "
                "prompt; equality is rechecked after AceStepModel appends structure_hint"
            ),
        },
        "seed_contract": {
            "base": SEED_BASE,
            "maximum": SEED_MAX,
            "formula": "2071000000 + prompt_rank*1000 + seed_idx",
            "seed_indices": list(range(N_SEEDS)),
            "relationship_to_legacy_cells": (
                "new independent seeds; paired inference is by prompt, not by random noise"
            ),
        },
        "generation": GENERATION_CONFIG,
        "generation_config_sha256": GENERATION_CONFIG_SHA256,
        "legacy_cell_sampling": {
            "conditions": ["plain_baseline", "negative_text", "positive_text"],
            "seed_indices": list(range(N_SEEDS)),
            "rows_per_cell": N_PROMPTS * N_SEEDS,
            "positive_source": "corrected positive-v2 primary rows only",
        },
        "analysis": {
            "endpoint": "promoted OR hard vocal-presence violation",
            "cell_order": ["plain", "neutral-matched", "negative", "positive"],
            "cell_ci": "two-sided 95% percentile bootstrap resampling 24 prompt clusters",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "confound_delta": "neutral-matched violation minus negative violation",
            "confound_pairing": "mean within prompt, then paired prompt-cluster bootstrap",
            "randomization_test": (
                "two-sided prompt-level sign-flip Monte Carlo with deterministic seed"
            ),
            "randomization_replicates": RANDOMIZATION_REPLICATES,
            "randomization_seed": RANDOMIZATION_SEED,
            "semantic_assumption": (
                "The frozen studio/recording descriptor is vocally inert by design and passes "
                "a forbidden-vocal-lexeme screen. Token equality does not establish generic "
                "semantic-specificity equivalence for every possible neutral insertion."
            ),
            "positive_cell_context": (
                "corrected positive-v2 removes the source negative vocal/lyrics clause before "
                "adding positive instrumental descriptors; it is contextual, not a pure "
                "same-base insertion control"
            ),
        },
        "canonical_instrument": instrument,
        "canonical_sources": source_hashes,
        "source_commits": {
            "factorial_freeze": FACTORIAL_SOURCE_COMMIT,
            "positive_correction": POSITIVE_CORRECTION_COMMIT,
            "t6_promotion": T6_PROMOTION_COMMIT,
        },
        "plan_or_claim_status_changed": False,
    }
    prep_audit = {
        "status": "PASS",
        "prompts": len(prompt_rows),
        "manifest_rows": len(manifest_rows),
        "unique_prompt_ids": len({row["prompt_id"] for row in prompt_rows}),
        "unique_seeds": len({int(row["seed"]) for row in manifest_rows}),
        "seed_min": min(int(row["seed"]) for row in manifest_rows),
        "seed_max": max(int(row["seed"]) for row in manifest_rows),
        "all_full_prompt_token_counts_match": True,
        "all_append_token_deltas_match": True,
        "all_actual_conditioning_token_counts_match": True,
        "neutral_forbidden_lexeme_hits": [],
        "tokenizer_json_sha256": tokenizer_hash,
        "source_hashes": source_hashes,
        "canonical_instrument_result_sha256": instrument["result_sha256"],
        "canonical_instrument_report_exact_line": instrument["report_exact_line"],
        "audio_files_before_freeze": 0,
        "generation_ledger_rows_before_freeze": 0,
        "selection_assumption_recorded": True,
    }
    write_jsonl_once(PROMPTS, prompt_rows)
    write_csv_once(MANIFEST, manifest_rows)
    write_json_once(PREREGISTRATION, preregistration)
    write_json_once(PREP_AUDIT, prep_audit)
    return prep_audit


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate_freeze_commit(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("freeze commit must be a full lowercase 40-character SHA")
    subprocess.run(["git", "cat-file", "-e", f"{value}^{{commit}}"], cwd=ROOT, check=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", value, "HEAD"], cwd=ROOT, check=True)
    current_head = git_head()
    if current_head != value:
        raise RuntimeError(
            "generation, scoring, and their audits require HEAD to equal the frozen-input "
            f"commit exactly: HEAD={current_head}, freeze={value}"
        )
    tracked_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if tracked_status.strip():
        raise RuntimeError("tracked worktree must be clean before generation or scoring")
    for relative_path in FROZEN_INPUT_PATHS:
        local_path = ROOT / relative_path
        if not local_path.is_file():
            raise FileNotFoundError(f"frozen input is missing locally: {relative_path}")
        frozen_blob = subprocess.run(
            ["git", "show", f"{value}:{relative_path.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        local_blob = local_path.read_bytes()
        if frozen_blob != local_blob:
            raise RuntimeError(
                f"local frozen input differs from freeze commit {value}: {relative_path}"
            )
    return value


def _latest_passes(directory: Path, prefix: str) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for path in sorted(directory.glob(f"{prefix}*.jsonl")):
        for row in read_jsonl(path):
            latest[str(row.get("task_id"))] = row
    return {key: row for key, row in latest.items() if row.get("status") == "PASS"}


def read_audio_checksums(path: Path = AUDIO_SHA256SUMS) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        if relative in checksums:
            raise ValueError(f"duplicate audio checksum path: {relative}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid audio checksum digest: {digest}")
        checksums[relative] = digest
    return checksums


def decoded_hash(samples: np.ndarray, sample_rate: int) -> str:
    canonical = np.ascontiguousarray(samples.T, dtype="<f4")
    header = np.asarray((sample_rate, *canonical.shape), dtype="<i8")
    digest = hashlib.sha256(header.tobytes())
    digest.update(canonical.tobytes())
    return digest.hexdigest()


def generate(worker_index: int, num_workers: int, freeze_commit: str, limit: int) -> int:
    validate_freeze_commit(freeze_commit)
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index is outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("each generator requires exactly one CUDA_VISIBLE_DEVICES entry")
    if not PROMPTS.is_file() or not MANIFEST.is_file():
        raise FileNotFoundError("frozen prompt list and manifest are required")
    if sha256_file(PREP_AUDIT) == "":
        raise AssertionError("unreachable empty prep hash")

    import soundfile as sf
    import torch

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts"))
    from mprm.common.seeding import seed_everything
    from mprm.data.audio_io import save_audio
    from mprm.inference.ace_step import AceStepModel
    from scripts.collect_early_tweedie_validation import _prompt_from_row

    prompt_rows = {row["prompt_id"]: row for row in read_jsonl(PROMPTS)}
    tasks = read_csv(MANIFEST)[worker_index::num_workers]
    if limit:
        tasks = tasks[:limit]
    done = _latest_passes(GENERATION_LEDGER_DIR, "generation_w")
    ledger = GENERATION_LEDGER_DIR / f"generation_w{worker_index}.jsonl"
    model = AceStepModel(device="cuda", dtype="bfloat16")
    current_commit = git_head()
    written = 0
    for task in tasks:
        prior = done.get(task["task_id"])
        output = ROOT / task["output_path"]
        if prior:
            if not output.is_file() or sha256_file(output) != prior.get("waveform_sha256"):
                raise RuntimeError(f"passed ledger/output mismatch for {task['task_id']}")
            continue
        if output.exists():
            raise FileExistsError(f"refusing to overwrite unledgered output: {output}")
        started = time.time()
        record = {
            **task,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(
                timespec="seconds"
            ),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "cuda_visible_devices": visible[0],
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "python_version": sys.version.split()[0],
            "freeze_commit": freeze_commit,
            "generation_git_commit": current_commit,
            "generation_config_sha256": GENERATION_CONFIG_SHA256,
            "status": "FAIL",
            "error": "",
        }
        scratch: Path | None = None
        try:
            source = prompt_rows[task["prompt_id"]]
            prompt = _prompt_from_row(source)
            prompt = dataclasses.replace(
                prompt,
                text=source["neutral_full_text"],
                lyrics=None,
                duration_target=DURATION_SECONDS,
            )
            seed = int(task["seed"])
            seed_everything(seed)
            result = model.sample(
                prompt,
                seed=seed,
                cfg_scale=GUIDANCE_SCALE,
                steps=INFERENCE_STEPS,
                return_trajectory=False,
                extras=GENERATION_EXTRAS,
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                prefix=f"neutral_{worker_index}_", suffix=".wav", dir="/dev/shm", delete=False
            )
            scratch = Path(handle.name)
            handle.close()
            save_audio(scratch, result.waveform, result.sample_rate)
            samples, sample_rate = sf.read(str(scratch), always_2d=True, dtype="float32")
            sf.write(str(output), samples, sample_rate, format="FLAC")
            decoded, decoded_sr = sf.read(str(output), always_2d=True, dtype="float32")
            rms = float(np.sqrt(np.mean(np.square(decoded, dtype=np.float64))))
            duration = len(decoded) / decoded_sr
            if duration <= 5 or rms <= 1e-7:
                raise RuntimeError(f"invalid output duration={duration:.6f}, rms={rms:.8g}")
            record.update(
                {
                    "status": "PASS",
                    "sample_rate": int(decoded_sr),
                    "duration_s": round(duration, 6),
                    "rms": rms,
                    "near_silent": bool(20 * math.log10(max(rms, 1e-12)) < -60),
                    "waveform_sha256": sha256_file(output),
                    "decoded_audio_sha256": decoded_hash(decoded, decoded_sr),
                    "output_bytes": output.stat().st_size,
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if scratch is not None and scratch.exists():
                scratch.unlink()
        record["elapsed_s"] = round(time.time() - started, 6)
        append_jsonl(ledger, record)
        print(json.dumps(record, sort_keys=True), flush=True)
        written += 1
        if record["status"] != "PASS":
            return 1
    return 0 if written or all(task["task_id"] in done for task in tasks) else 1


def audit_generation(
    freeze_commit: str,
    launch_command: str,
    node: str,
    gpu_ids: str,
    placement_justification: str,
    log_paths: str,
) -> dict:
    validate_freeze_commit(freeze_commit)
    tasks = read_csv(MANIFEST)
    latest = _latest_passes(GENERATION_LEDGER_DIR, "generation_w")
    missing: list[str] = []
    invalid: list[str] = []
    checksum_lines: list[str] = []
    for task in tasks:
        row = latest.get(task["task_id"])
        if not row:
            missing.append(task["task_id"])
            continue
        output = ROOT / task["output_path"]
        if not output.is_file() or output.stat().st_size <= 0:
            invalid.append(task["task_id"])
            continue
        observed = sha256_file(output)
        if observed != row.get("waveform_sha256"):
            invalid.append(task["task_id"])
            continue
        checksum_lines.append(f"{observed}  {task['output_path']}")
    hosts = sorted({str(row["host"]) for row in latest.values()})
    observed_freezes = sorted({str(row["freeze_commit"]) for row in latest.values()})
    observed_git_commits = sorted(
        {str(row["generation_git_commit"]) for row in latest.values()}
    )
    observed_config_hashes = sorted(
        {str(row["generation_config_sha256"]) for row in latest.values()}
    )
    observed_gpu_ids = sorted(
        {str(row["cuda_visible_devices"]) for row in latest.values()}, key=int
    )
    observed_num_workers = sorted({int(row["num_workers"]) for row in latest.values()})
    observed_worker_indices = sorted({int(row["worker_index"]) for row in latest.values()})
    declared_gpu_ids = sorted({value for value in gpu_ids.split(",") if value}, key=int)
    declared_log_paths = [Path(value) for value in log_paths.split(",") if value]
    required_log_root = Path("analysis_exit1_v2/neutral_control/logs")
    valid_logs = bool(declared_log_paths) and all(
        path.is_relative_to(required_log_root) and (ROOT / path).is_file()
        for path in declared_log_paths
    )
    status = (
        "PASS"
        if len(tasks) == 192
        and len(latest) == 192
        and set(latest) == {task["task_id"] for task in tasks}
        and not missing
        and not invalid
        and hosts == [node]
        and observed_freezes == [freeze_commit]
        and observed_git_commits == [freeze_commit]
        and observed_config_hashes == [GENERATION_CONFIG_SHA256]
        and observed_gpu_ids == declared_gpu_ids
        and observed_num_workers == [len(declared_gpu_ids)]
        and observed_worker_indices == list(range(len(declared_gpu_ids)))
        and bool(launch_command.strip())
        and bool(placement_justification.strip())
        and valid_logs
        else "FAIL"
    )
    audit = {
        "status": status,
        "manifest_rows": len(tasks),
        "successful_latest_rows": len(latest),
        "retained_audio_files": len(checksum_lines),
        "missing_count": len(missing),
        "invalid_count": len(invalid),
        "missing_examples": missing[:20],
        "invalid_examples": invalid[:20],
        "hosts": hosts,
        "freeze_commits": observed_freezes,
        "generation_git_commits": observed_git_commits,
        "observed_gpu_ids": observed_gpu_ids,
        "observed_num_workers": observed_num_workers,
        "observed_worker_indices": observed_worker_indices,
        "log_paths": [path.as_posix() for path in declared_log_paths],
        "logs_valid": valid_logs,
        "generation_config_sha256": GENERATION_CONFIG_SHA256,
        "total_audio_bytes": sum(
            (ROOT / task["output_path"]).stat().st_size
            for task in tasks
            if (ROOT / task["output_path"]).is_file()
        ),
    }
    if status != "PASS":
        raise RuntimeError(f"generation audit failed: {audit}")
    _write_once(AUDIO_SHA256SUMS, "\n".join(sorted(checksum_lines)) + "\n")
    write_json_once(GENERATION_AUDIT, audit)
    run = {
        "status": "COMPLETE",
        "node": node,
        "gpu_ids": observed_gpu_ids,
        "tensor_parallel_width": 1,
        "replica_count": len(observed_gpu_ids),
        "placement_justification": placement_justification,
        "command": launch_command,
        "git_hash": freeze_commit,
        "config_hash": GENERATION_CONFIG_SHA256,
        "seed_base": SEED_BASE,
        "seed_max": SEED_MAX,
        "seed_formula": "2071000000 + prompt_rank*1000 + seed_idx",
        "artifact_path": str(AUDIO_DIR.relative_to(ROOT)),
        "manifest_path": str(MANIFEST.relative_to(ROOT)),
        "ledger_path": str(GENERATION_LEDGER_DIR.relative_to(ROOT)),
        "log_paths": [path.as_posix() for path in declared_log_paths],
        "audio_checksums_path": str(AUDIO_SHA256SUMS.relative_to(ROOT)),
        "prompt_count": N_PROMPTS,
        "seeds_per_prompt": N_SEEDS,
        "clip_count": N_PROMPTS * N_SEEDS,
        "configuration": GENERATION_CONFIG,
        "deviations": [
            (
                "Canonical factorial contains 32 prompts; task-required 24 implemented "
                "as preregistered ranks 0-23."
            ),
            (
                "Neutral uses a registered independent seed range; legacy-cell comparison "
                "is prompt-paired rather than same-noise paired."
            ),
        ],
        "ledger_hosts": hosts,
        "started_at": min(row["timestamp"] for row in latest.values()),
        "completed_at": max(row["timestamp"] for row in latest.values()),
    }
    write_json_once(RUN_MANIFEST, run)
    return audit


def _seed_scoring(identity: str) -> None:
    import torch

    seed = int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:4], "big")
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def score(worker_index: int, num_workers: int, freeze_commit: str, limit: int) -> int:
    validate_freeze_commit(freeze_commit)
    if not 0 <= worker_index < num_workers:
        raise ValueError("worker index is outside shard range")
    visible = [value for value in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if value]
    if len(visible) != 1:
        raise RuntimeError("each scorer requires exactly one CUDA_VISIBLE_DEVICES entry")
    instrument = _parse_canonical_instrument()
    if not GENERATION_AUDIT.is_file() or not AUDIO_SHA256SUMS.is_file():
        raise FileNotFoundError("passing generation audit and audio checksums are required")
    generation_audit = json.loads(GENERATION_AUDIT.read_text(encoding="utf-8"))
    if generation_audit.get("status") != "PASS":
        raise RuntimeError("generation audit is not PASS")
    generation_passes = _latest_passes(GENERATION_LEDGER_DIR, "generation_w")
    audio_checksums = read_audio_checksums()

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(PAPER / "scripts"))
    sys.path.insert(0, str(PAPER / "w2_contingency_20260711"))
    import torch

    from w2_instruments import CurrentDemucsInstrument, LivePannsInstrument

    tasks = read_csv(MANIFEST)[worker_index::num_workers]
    if limit:
        tasks = tasks[:limit]
    done = _latest_passes(SCORING_LEDGER_DIR, "scoring_w")
    ledger = SCORING_LEDGER_DIR / f"scoring_w{worker_index}.jsonl"
    demucs = CurrentDemucsInstrument(
        device="cuda", threshold=float(instrument["demucs_threshold"])
    )
    panns = LivePannsInstrument(
        device="cuda", threshold=float(instrument["panns_threshold"])
    )
    current_commit = git_head()
    scoring_config_sha256 = sha256_text(canonical_json(instrument))
    written = 0
    for task in tasks:
        if task["task_id"] in done:
            continue
        started = time.time()
        output = ROOT / task["output_path"]
        record = {
            **task,
            "timestamp": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(
                timespec="seconds"
            ),
            "host": socket.gethostname(),
            "worker_index": worker_index,
            "num_workers": num_workers,
            "cuda_visible_devices": visible[0],
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "freeze_commit": freeze_commit,
            "scoring_git_commit": current_commit,
            "scoring_config_sha256": scoring_config_sha256,
            "instrument_family": instrument["family"],
            "instrument_report_exact_line": instrument["report_exact_line"],
            "instrument_report_sha256": instrument["report_sha256"],
            "instrument_result_sha256": instrument["result_sha256"],
            "status": "FAIL",
            "error": "",
        }
        try:
            if not output.is_file():
                raise FileNotFoundError(output)
            generation_row = generation_passes.get(task["task_id"])
            if not generation_row:
                raise ValueError(f"missing passing generation row for {task['task_id']}")
            observed_audio_hash = sha256_file(output)
            if not (
                observed_audio_hash == generation_row.get("waveform_sha256")
                == audio_checksums.get(task["output_path"])
            ):
                raise ValueError(f"generation/audio checksum mismatch for {task['task_id']}")
            _seed_scoring(task["task_id"] + "|demucs")
            d = demucs.score(output)
            _seed_scoring(task["task_id"] + "|panns")
            p = panns.score(output)
            violation = canonical_prediction(
                instrument, float(d["vocal_energy_ratio"]), float(p["panns_score"])
            )
            record.update(
                {
                    "status": "PASS",
                    "demucs_score": float(d["vocal_energy_ratio"]),
                    "panns_score": float(p["panns_score"]),
                    "panns_top_vocal_class": p["panns_top_vocal_class"],
                    "near_silent": bool(d["near_silent"]),
                    "canonical_violation": int(violation),
                    "canonical_rule": "demucs>=parsed_threshold OR panns>=parsed_threshold",
                    "audio_sha256": observed_audio_hash,
                    "generation_audio_sha256": generation_row["waveform_sha256"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"
        record["elapsed_s"] = round(time.time() - started, 6)
        append_jsonl(ledger, record)
        print(json.dumps(record, sort_keys=True), flush=True)
        written += 1
        if record["status"] != "PASS":
            return 1
    return 0 if written or all(task["task_id"] in done for task in tasks) else 1


def audit_scoring(
    freeze_commit: str,
    launch_command: str,
    node: str,
    gpu_ids: str,
    placement_justification: str,
    log_paths: str,
) -> dict:
    validate_freeze_commit(freeze_commit)
    tasks = read_csv(MANIFEST)
    latest = _latest_passes(SCORING_LEDGER_DIR, "scoring_w")
    instrument = _parse_canonical_instrument()
    scoring_config_sha256 = sha256_text(canonical_json(instrument))
    declared_gpu_ids = sorted({value for value in gpu_ids.split(",") if value}, key=int)
    declared_log_paths = [Path(value) for value in log_paths.split(",") if value]
    required_log_root = Path("analysis_exit1_v2/neutral_control/logs")
    valid_logs = bool(declared_log_paths) and all(
        path.is_relative_to(required_log_root) and (ROOT / path).is_file()
        for path in declared_log_paths
    )
    hosts = sorted({str(row["host"]) for row in latest.values()})
    observed_gpu_ids = sorted(
        {str(row["cuda_visible_devices"]) for row in latest.values()}, key=int
    )
    observed_num_workers = sorted({int(row["num_workers"]) for row in latest.values()})
    observed_worker_indices = sorted({int(row["worker_index"]) for row in latest.values()})
    observed_commits = sorted({str(row["scoring_git_commit"]) for row in latest.values()})
    observed_configs = sorted(
        {str(row["scoring_config_sha256"]) for row in latest.values()}
    )
    observed_result_hashes = sorted(
        {str(row["instrument_result_sha256"]) for row in latest.values()}
    )
    status = (
        "PASS"
        if len(tasks) == 192
        and len(latest) == 192
        and set(latest) == {task["task_id"] for task in tasks}
        and hosts == [node]
        and observed_gpu_ids == declared_gpu_ids
        and observed_num_workers == [len(declared_gpu_ids)]
        and observed_worker_indices == list(range(len(declared_gpu_ids)))
        and observed_commits == [freeze_commit]
        and observed_configs == [scoring_config_sha256]
        and observed_result_hashes == [instrument["result_sha256"]]
        and bool(launch_command.strip())
        and bool(placement_justification.strip())
        and valid_logs
        else "FAIL"
    )
    audit = {
        "status": status,
        "scored_rows": len(latest),
        "task_identity_match": set(latest) == {task["task_id"] for task in tasks},
        "node": node,
        "ledger_hosts": hosts,
        "gpu_ids": observed_gpu_ids,
        "tensor_parallel_width": 1,
        "replica_count": len(observed_gpu_ids),
        "observed_num_workers": observed_num_workers,
        "observed_worker_indices": observed_worker_indices,
        "placement_justification": placement_justification,
        "command": launch_command,
        "git_hash": freeze_commit,
        "config_hash": scoring_config_sha256,
        "instrument": instrument,
        "ledger_path": str(SCORING_LEDGER_DIR.relative_to(ROOT)),
        "log_paths": [path.as_posix() for path in declared_log_paths],
        "logs_valid": valid_logs,
        "artifact_path": str(AUDIO_DIR.relative_to(ROOT)),
    }
    if status != "PASS":
        raise RuntimeError(f"scoring run audit failed: {audit}")
    write_json_once(SCORING_RUN_MANIFEST, audit)
    return audit


def prompt_cluster_ci(
    rows: Sequence[dict], value_key: str, replicates: int, seed: int
) -> tuple[float, float, float]:
    by_prompt: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_prompt[str(row["prompt_id"])].append(float(row[value_key]))
    prompt_ids = sorted(by_prompt)
    if len(prompt_ids) != N_PROMPTS:
        raise ValueError(f"expected {N_PROMPTS} prompt clusters, found {len(prompt_ids)}")
    prompt_means = np.asarray(
        [float(np.mean(by_prompt[prompt_id])) for prompt_id in prompt_ids], dtype=float
    )
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(prompt_means), size=(replicates, len(prompt_means)))
    estimates = np.mean(prompt_means[indices], axis=1)
    return (
        float(np.mean(prompt_means)),
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
    )


def paired_prompt_delta(
    rows: Sequence[dict],
    left_condition: str,
    right_condition: str,
    replicates: int,
    seed: int,
) -> dict:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["prompt_id"]), str(row["condition"]))].append(
            float(row["violation"])
        )
    prompt_ids = sorted({prompt_id for prompt_id, _condition in grouped})
    if len(prompt_ids) != N_PROMPTS:
        raise ValueError("paired delta prompt cardinality mismatch")
    deltas = np.asarray(
        [
            np.mean(grouped[(prompt_id, left_condition)])
            - np.mean(grouped[(prompt_id, right_condition)])
            for prompt_id in prompt_ids
        ],
        dtype=float,
    )
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(deltas), size=(replicates, len(deltas)))
    estimates = np.mean(deltas[indices], axis=1)
    observed = float(np.mean(deltas))
    random_rng = np.random.default_rng(RANDOMIZATION_SEED)
    signs = random_rng.choice(
        np.asarray([-1.0, 1.0]), size=(RANDOMIZATION_REPLICATES, len(deltas))
    )
    null_estimates = np.mean(signs * deltas, axis=1)
    p_value = float(
        (1 + np.sum(np.abs(null_estimates) >= abs(observed)))
        / (RANDOMIZATION_REPLICATES + 1)
    )
    return {
        "orientation": f"{left_condition} minus {right_condition}",
        "estimate": observed,
        "ci95": [
            float(np.quantile(estimates, 0.025)),
            float(np.quantile(estimates, 0.975)),
        ],
        "prompt_clusters": len(deltas),
        "prompt_differences": deltas.tolist(),
        "bootstrap_replicates": replicates,
        "bootstrap_seed": seed,
        "randomization_replicates": RANDOMIZATION_REPLICATES,
        "randomization_seed": RANDOMIZATION_SEED,
        "two_sided_sign_flip_p": p_value,
        "pairing": "prompt-paired, seed-independent",
    }


def _legacy_condition_name(value: str) -> str:
    mapping = {
        "plain_baseline": "plain",
        "negative_text": "negative",
        "positive_text": "positive",
    }
    if value not in mapping:
        raise ValueError(f"unexpected legacy condition: {value}")
    return mapping[value]


def analyze() -> dict:
    if not SCORING_RUN_MANIFEST.is_file():
        raise FileNotFoundError("passing scoring run manifest is required")
    scoring_run = json.loads(SCORING_RUN_MANIFEST.read_text(encoding="utf-8"))
    if scoring_run.get("status") != "PASS":
        raise RuntimeError("scoring run manifest is not PASS")
    instrument = _parse_canonical_instrument()
    source_hashes = _assert_source_hashes()
    prompts = read_jsonl(PROMPTS)
    prompt_ids = {row["prompt_id"] for row in prompts}
    prompt_rank = {row["prompt_id"]: int(row["neutral_control_rank"]) for row in prompts}
    score_latest = _latest_passes(SCORING_LEDGER_DIR, "scoring_w")
    generation_latest = _latest_passes(GENERATION_LEDGER_DIR, "generation_w")
    audio_checksums = read_audio_checksums()
    tasks = {row["task_id"]: row for row in read_csv(MANIFEST)}
    if len(score_latest) != 192 or set(score_latest) != set(tasks):
        raise ValueError(
            f"neutral scoring incomplete: {len(score_latest)}/192 passed task identities"
        )

    neutral_rows: list[dict] = []
    for task_id in sorted(tasks):
        task = tasks[task_id]
        score_row = score_latest[task_id]
        generation_row = generation_latest.get(task_id)
        if not generation_row:
            raise ValueError(f"missing passing generation provenance for {task_id}")
        output = ROOT / task["output_path"]
        if not output.is_file():
            raise FileNotFoundError(output)
        observed_audio_hash = sha256_file(output)
        if not (
            observed_audio_hash == generation_row.get("waveform_sha256")
            == score_row.get("audio_sha256")
            == score_row.get("generation_audio_sha256")
            == audio_checksums.get(task["output_path"])
        ):
            raise ValueError(f"score/generation/audio checksum mismatch for {task_id}")
        violation = canonical_prediction(
            instrument, float(score_row["demucs_score"]), float(score_row["panns_score"])
        )
        neutral_rows.append(
            {
                "task_id": task_id,
                "prompt_rank": int(task["prompt_rank"]),
                "prompt_id": task["prompt_id"],
                "condition": "neutral-matched",
                "seed_idx": int(task["seed_idx"]),
                "seed": int(task["seed"]),
                "output_path": task["output_path"],
                "demucs_score": float(score_row["demucs_score"]),
                "panns_score": float(score_row["panns_score"]),
                "near_silent": int(bool(score_row["near_silent"])),
                "violation": int(violation),
                "source_role": "NEW_NEUTRAL_MATCHED_GENERATION",
            }
        )

    legacy_rows: list[dict] = []
    seen_legacy: set[tuple[str, str, int]] = set()
    for row in read_csv(FACTORIAL_SCORE_ROWS):
        if row["prompt_id"] not in prompt_ids:
            continue
        if row["condition"] not in {"plain_baseline", "negative_text", "positive_text"}:
            continue
        seed_idx = int(row["seed_idx"])
        if seed_idx not in range(N_SEEDS):
            continue
        condition = _legacy_condition_name(row["condition"])
        key = (row["prompt_id"], condition, seed_idx)
        if key in seen_legacy:
            raise ValueError(f"duplicate canonical legacy row: {key}")
        seen_legacy.add(key)
        if condition == "positive" and row["implementation_role"] != "CORRECTED_POSITIVE_ONLY_PRIMARY":
            raise ValueError("positive cell is not the canonical corrected positive-v2 cohort")
        if condition != "positive" and row["implementation_role"] != "ORIGINAL_UNAFFECTED_PRIMARY":
            raise ValueError(f"unexpected implementation role for {condition}")
        violation = canonical_prediction(
            instrument, float(row["demucs_score"]), float(row["panns_score"])
        )
        legacy_rows.append(
            {
                "task_id": row["task_id"],
                "prompt_rank": prompt_rank[row["prompt_id"]],
                "prompt_id": row["prompt_id"],
                "condition": condition,
                "seed_idx": seed_idx,
                "seed": int(row["seed"]),
                "output_path": row["output_path"],
                "demucs_score": float(row["demucs_score"]),
                "panns_score": float(row["panns_score"]),
                "near_silent": int(row["near_silent"]),
                "violation": int(violation),
                "source_role": row["implementation_role"],
            }
        )
    if len(legacy_rows) != 3 * N_PROMPTS * N_SEEDS:
        raise ValueError(f"legacy four-cell source cardinality mismatch: {len(legacy_rows)}")

    all_rows = sorted(
        [*legacy_rows, *neutral_rows],
        key=lambda row: (
            ["plain", "neutral-matched", "negative", "positive"].index(row["condition"]),
            int(row["prompt_rank"]),
            int(row["seed_idx"]),
        ),
    )
    counts = Counter(row["condition"] for row in all_rows)
    if counts != {
        "plain": 192,
        "neutral-matched": 192,
        "negative": 192,
        "positive": 192,
    }:
        raise ValueError(f"four-cell count mismatch: {counts}")

    summaries: list[dict] = []
    for offset, condition in enumerate(["plain", "neutral-matched", "negative", "positive"]):
        group = [row for row in all_rows if row["condition"] == condition]
        estimate, lower, upper = prompt_cluster_ci(
            group, "violation", BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED + offset
        )
        summaries.append(
            {
                "condition": condition,
                "observations": len(group),
                "prompt_clusters": len({row["prompt_id"] for row in group}),
                "seeds_per_prompt": N_SEEDS,
                "violation_rate": estimate,
                "ci95_lower": lower,
                "ci95_upper": upper,
                "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                "bootstrap_seed": BOOTSTRAP_SEED + offset,
            }
        )
    delta = paired_prompt_delta(
        all_rows,
        "neutral-matched",
        "negative",
        BOOTSTRAP_REPLICATES,
        BOOTSTRAP_SEED + 10,
    )
    lower, upper = delta["ci95"]
    if upper < 0:
        verdict = "REJECT_TOKEN_MATCHED_NEUTRAL_AS_SOLE_DRIVER_WITHIN_RISK_SUBSET"
        interpretation = (
            "Under the preregistered neutral-inertness assumption, neutral-matched has a "
            "lower promoted-OR violation rate than negative in the selected risk-ranked "
            "subset; the prompt-paired 95% CI excludes zero in the preregistered direction."
        )
    elif lower > 0:
        verdict = "NEUTRAL_EXCEEDS_NEGATIVE"
        interpretation = (
            "Neutral-matched has a higher violation rate than negative; this does not "
            "support the proposed negative-wording mechanism within the selected subset."
        )
    else:
        verdict = "INCONCLUSIVE_MATCHED_LENGTH_CONFOUND_TEST"
        interpretation = (
            "The prompt-paired 95% CI includes zero, so this cell does not rule out the "
            "matched-length/neutral-descriptor explanation within the selected subset."
        )

    score_audit = {
        "status": "PASS",
        "neutral_score_rows": len(neutral_rows),
        "unique_neutral_task_ids": len({row["task_id"] for row in neutral_rows}),
        "four_cell_rows": len(all_rows),
        "condition_counts": dict(counts),
        "canonical_instrument": instrument,
        "canonical_rule": "demucs_score >= parsed threshold OR panns_score >= parsed threshold",
        "near_silent_not_used_to_suppress_demucs": True,
        "all_score_rows_link_to_generation_and_retained_audio_sha256": True,
        "source_hashes": source_hashes,
    }
    result = {
        "status": "COMPLETE",
        "endpoint": "promoted OR hard vocal-presence violation",
        "condition_results": summaries,
        "neutral_minus_negative": delta,
        "confound_test_verdict": verdict,
        "confound_test_interpretation": interpretation,
        "instrument": instrument,
        "prompt_selection_assumption": (
            "historical-N2-risk ranks 0-23 selected because task requests 24 from a "
            "32-prompt factorial; subset inference only"
        ),
        "neutral_semantic_assumption": (
            "one frozen studio descriptor is vocally inert by design and lexical screen; "
            "generic semantic-specificity equivalence is unverified"
        ),
        "positive_cell_context": (
            "canonical corrected positive-v2 removes source negative clauses before adding "
            "positive descriptors"
        ),
        "legacy_seed_indices": list(range(N_SEEDS)),
        "neutral_seed_range": [SEED_BASE, SEED_MAX],
        "plan_or_claim_status_changed": False,
    }
    write_csv_once(NEUTRAL_SCORES, neutral_rows)
    write_csv_once(FOUR_CELL_ROWS, all_rows)
    write_csv_once(FOUR_CELL_RESULTS_CSV, summaries)
    write_json_once(SCORING_AUDIT, score_audit)
    write_json_once(FOUR_CELL_RESULTS_JSON, result)
    return result


def record_tests(log_path: Path, exit_code: int, command: str) -> dict:
    if not log_path.is_file():
        raise FileNotFoundError(log_path)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(r"(\d+) passed", text)
    failed = re.findall(r"(\d+) failed", text)
    errors = re.findall(r"(\d+) error", text)
    passed = int(matches[-1]) if matches else 0
    status = "PASS" if exit_code == 0 and passed > 0 and not failed and not errors else "FAIL"
    summary = {
        "status": status,
        "command": command,
        "exit_code": exit_code,
        "passed": passed,
        "failed": int(failed[-1]) if failed else 0,
        "errors": int(errors[-1]) if errors else 0,
        "node": socket.gethostname(),
        "git_hash": git_head(),
        "python": sys.version.split()[0],
        "log_path": str(log_path.relative_to(ROOT)),
        "log_sha256": sha256_file(log_path),
        "recorded_at": dt.datetime.now(dt.timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
    }
    if status != "PASS":
        raise RuntimeError(f"full test suite did not pass: {summary}")
    write_json_once(TEST_SUMMARY, summary)
    return summary


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )


def render_report(freeze_commit: str, generation_commit: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", freeze_commit):
        raise ValueError("freeze commit must be a full SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", generation_commit):
        raise ValueError("generation commit must be a full SHA")
    if freeze_commit == generation_commit or not _is_ancestor(freeze_commit, generation_commit):
        raise ValueError("freeze commit must be a strict ancestor of generation commit")
    head = git_head()
    if not _is_ancestor(generation_commit, head):
        raise ValueError("generation commit must be an ancestor of the report tree")
    generation_audit = json.loads(GENERATION_AUDIT.read_text(encoding="utf-8"))
    scoring_audit = json.loads(SCORING_AUDIT.read_text(encoding="utf-8"))
    scoring_run = json.loads(SCORING_RUN_MANIFEST.read_text(encoding="utf-8"))
    results = json.loads(FOUR_CELL_RESULTS_JSON.read_text(encoding="utf-8"))
    tests = json.loads(TEST_SUMMARY.read_text(encoding="utf-8"))
    run = json.loads(RUN_MANIFEST.read_text(encoding="utf-8"))
    prep = json.loads(PREP_AUDIT.read_text(encoding="utf-8"))
    if not all(
        value == "PASS"
        for value in [
            prep["status"],
            generation_audit["status"],
            scoring_audit["status"],
            scoring_run["status"],
            tests["status"],
        ]
    ):
        raise RuntimeError("cannot render COMPLETE report from a non-PASS audit")
    if results["status"] != "COMPLETE":
        raise RuntimeError("four-cell results are incomplete")

    lines = [
        "# Exit-1 Neutral-Control Report",
        "",
        "`NEUTRAL_CONTROL_STATUS = COMPLETE`",
        "",
        "The matched neutral-control cell is complete: 24 prompts × 8 newly registered "
        "seeds produced 192 retained clips, all clips passed integrity checks, all clips "
        "were scored with the mechanically parsed promoted OR instrument, and the four-cell "
        "prompt-cluster analysis completed. This report changes neither PLAN nor CLAIMS.",
        "",
        "## Frozen design and ordering evidence",
        "",
        f"- Frozen-input commit: `{freeze_commit}`.",
        f"- Generation/scoring evidence commit: `{generation_commit}`.",
        "- Git ancestry check: `PASS` (the frozen-input commit is a strict ancestor of the "
        "generation/scoring evidence commit).",
        "- Canonical factorial mismatch assumption: the source has 32 prompts; the task "
        "requires 24, so pre-existing historical-N2-risk ranks 0–23 were frozen before "
        "neutral generation. Factorial-condition outcomes were not used in the 24-of-32 "
        "selection rule. This is a risk-ranked subset, so the result does not automatically "
        "generalize to ranks 24–31.",
        f"- Neutral insertion: `{NEUTRAL_INSERTION}`.",
        f"- Negative reference insertion: `{NEGATIVE_INSERTION}`.",
        "- Per-prompt tokenizer audit: all 24 neutral full prompts exactly match their "
        "negative-reference full-prompt token counts; all append deltas and actual "
        "post-structure-hint ACE-Step conditioning counts match.",
        "- Semantic scope: the single frozen studio/recording descriptor is vocally inert "
        "by design and passes the forbidden-vocal-lexeme screen. Exact token equality does "
        "not prove generic semantic-specificity equivalence for every possible neutral text.",
        f"- Tokenizer JSON SHA-256: `{prep['tokenizer_json_sha256']}`.",
        f"- New seed range: `{SEED_BASE}` through `{SEED_MAX}`; formula "
        "`2071000000 + prompt_rank*1000 + seed_idx`.",
        "- Legacy cells use frozen seed indices 0–7. Neutral seeds are independent, so the "
        "paired confound test is paired by prompt cluster, not by identical diffusion noise.",
        "",
        "## Promoted OR instrument",
        "",
        "Dispatch A's fail-closed parser read the canonical JSON and verified the exact report line:",
        "",
        "```text",
        results["instrument"]["report_exact_line"],
        "```",
        "",
        f"- `T6_PROMOTION_RESULT.json` SHA-256: `{results['instrument']['result_sha256']}`.",
        f"- `T6_PROMOTION_REPORT.md` SHA-256: `{results['instrument']['report_sha256']}`.",
        f"- Parsed Demucs threshold: `{results['instrument']['demucs_threshold']}`.",
        f"- Parsed PANNs threshold: `{results['instrument']['panns_threshold']}`.",
        "- Endpoint: hard vocal-presence violation = "
        "`demucs_score >= parsed threshold OR panns_score >= parsed threshold`. The "
        "near-silent flag does not suppress the canonical Demucs component.",
        "",
        "## Four-cell comparison",
        "",
        "Each cell has 192 observations in 24 prompt clusters. Intervals are two-sided "
        "95% percentile intervals from 10,000 deterministic prompt-cluster bootstrap draws.",
        "The positive row is the canonical corrected positive-v2 cohort: its source "
        "negative vocal/lyrics clause was removed before positive instrumental descriptors "
        "were added. It is therefore contextual/descriptive, not a pure same-base insertion cell.",
        "",
        "| cell | observations | prompt clusters | promoted-OR violation rate | 95% prompt-cluster CI |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in results["condition_results"]:
        lines.append(
            f"| {row['condition']} | {row['observations']} | {row['prompt_clusters']} | "
            f"{row['violation_rate']:.6f} | "
            f"[{row['ci95_lower']:.6f}, {row['ci95_upper']:.6f}] |"
        )
    delta = results["neutral_minus_negative"]
    lines.extend(
        [
            "",
            "## Paired neutral-vs-negative confound test",
            "",
            "The preregistered orientation is neutral-matched minus negative. Within each "
            "prompt, each condition is first averaged across its eight independent seeds; "
            "the 24 prompt differences are then bootstrapped as paired clusters.",
            "",
            f"- Delta: `{delta['estimate']:.6f}`.",
            f"- 95% prompt-paired bootstrap CI: "
            f"`[{delta['ci95'][0]:.6f}, {delta['ci95'][1]:.6f}]`.",
            f"- Two-sided prompt-level sign-flip p-value: "
            f"`{delta['two_sided_sign_flip_p']:.6g}` "
            f"({delta['randomization_replicates']:,} Monte Carlo draws).",
            f"- Confound-test verdict: `{results['confound_test_verdict']}`.",
            f"- Interpretation: {results['confound_test_interpretation']}",
            "- Scope qualifier: the verdict is conditional on the preregistered neutral-"
            "inertness assumption and applies to this risk-ranked 24/32 subset.",
            "",
            "This is a completed control experiment, not a PLAN/CLAIMS amendment. The "
            "reported outcome is not upgraded beyond the evidence in this cell.",
            "",
            "## Generation and retained evidence",
            "",
            f"- Placement: `{run['node']}`, GPUs `{','.join(run['gpu_ids'])}`, TP"
            f"`{run['tensor_parallel_width']}`, `{run['replica_count']}` independent replicas.",
            f"- Placement justification: {run['placement_justification']}",
            f"- Exact launch command: `{run['command']}`.",
            f"- Generation config SHA-256: `{run['config_hash']}`.",
            f"- Retained audio: `{generation_audit['retained_audio_files']}` FLAC files, "
            f"`{generation_audit['total_audio_bytes']}` bytes under `{run['artifact_path']}`.",
            f"- Audio checksum manifest: `{AUDIO_SHA256SUMS.relative_to(ROOT)}` "
            f"(SHA-256 `{sha256_file(AUDIO_SHA256SUMS)}`).",
            f"- Generation audit: `{GENERATION_AUDIT.relative_to(ROOT)}` "
            f"(SHA-256 `{sha256_file(GENERATION_AUDIT)}`).",
            f"- Scoring audit: `{SCORING_AUDIT.relative_to(ROOT)}` "
            f"(SHA-256 `{sha256_file(SCORING_AUDIT)}`).",
            f"- Scoring placement: `{scoring_run['node']}`, GPUs "
            f"`{','.join(scoring_run['gpu_ids'])}`, TP`1`, "
            f"`{scoring_run['replica_count']}` independent replicas.",
            f"- Exact scoring command: `{scoring_run['command']}`.",
            f"- Scoring config SHA-256: `{scoring_run['config_hash']}`; run manifest "
            f"`{SCORING_RUN_MANIFEST.relative_to(ROOT)}`.",
            f"- Four-cell rows: `{FOUR_CELL_ROWS.relative_to(ROOT)}` "
            f"(SHA-256 `{sha256_file(FOUR_CELL_ROWS)}`).",
            "",
            "## Tests",
            "",
            "`TEST_SUITE_STATUS = PASS`",
            "",
            f"- Command: `{tests['command']}`.",
            f"- Result: `{tests['passed']} passed`, exit code `{tests['exit_code']}`.",
            f"- Tested git hash: `{tests['git_hash']}` on `{tests['node']}` with Python "
            f"`{tests['python']}`.",
            f"- Raw output: `{tests['log_path']}` (SHA-256 `{tests['log_sha256']}`).",
            f"- Summary: `{TEST_SUMMARY.relative_to(ROOT)}`.",
            "",
            "## Scope",
            "",
            "`PLAN_CLAIMS_CHANGED = NO`",
            "",
            "No checkpoint, pre-existing generated data, canonical factorial artifact, "
            "PLAN file, or CLAIMS file was modified.",
        ]
    )
    _write_once(REPORT, "\n".join(lines) + "\n")
    return {
        "status": "COMPLETE",
        "report": str(REPORT),
        "freeze_commit": freeze_commit,
        "generation_commit": generation_commit,
        "test_status": tests["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")

    generate_parser = sub.add_parser("generate")
    generate_parser.add_argument("--worker-index", type=int, required=True)
    generate_parser.add_argument("--num-workers", type=int, required=True)
    generate_parser.add_argument("--freeze-commit", required=True)
    generate_parser.add_argument("--limit", type=int, default=0)

    audit_parser = sub.add_parser("audit-generation")
    audit_parser.add_argument("--freeze-commit", required=True)
    audit_parser.add_argument("--launch-command", required=True)
    audit_parser.add_argument("--node", required=True)
    audit_parser.add_argument("--gpu-ids", required=True)
    audit_parser.add_argument("--placement-justification", required=True)
    audit_parser.add_argument("--log-paths", required=True)

    score_parser = sub.add_parser("score")
    score_parser.add_argument("--worker-index", type=int, required=True)
    score_parser.add_argument("--num-workers", type=int, required=True)
    score_parser.add_argument("--freeze-commit", required=True)
    score_parser.add_argument("--limit", type=int, default=0)
    score_audit_parser = sub.add_parser("audit-scoring")
    score_audit_parser.add_argument("--freeze-commit", required=True)
    score_audit_parser.add_argument("--launch-command", required=True)
    score_audit_parser.add_argument("--node", required=True)
    score_audit_parser.add_argument("--gpu-ids", required=True)
    score_audit_parser.add_argument("--placement-justification", required=True)
    score_audit_parser.add_argument("--log-paths", required=True)
    sub.add_parser("analyze")

    tests_parser = sub.add_parser("record-tests")
    tests_parser.add_argument("--log-path", type=Path, required=True)
    tests_parser.add_argument("--exit-code", type=int, required=True)
    tests_parser.add_argument("--test-command", required=True)

    report_parser = sub.add_parser("render-report")
    report_parser.add_argument("--freeze-commit", required=True)
    report_parser.add_argument("--generation-commit", required=True)
    args = parser.parse_args()

    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, sort_keys=True))
        return 0
    if args.command == "generate":
        return generate(args.worker_index, args.num_workers, args.freeze_commit, args.limit)
    if args.command == "audit-generation":
        result = audit_generation(
            args.freeze_commit,
            args.launch_command,
            args.node,
            args.gpu_ids,
            args.placement_justification,
            args.log_paths,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "score":
        return score(args.worker_index, args.num_workers, args.freeze_commit, args.limit)
    if args.command == "audit-scoring":
        result = audit_scoring(
            args.freeze_commit,
            args.launch_command,
            args.node,
            args.gpu_ids,
            args.placement_justification,
            args.log_paths,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "analyze":
        print(json.dumps(analyze(), indent=2, sort_keys=True))
        return 0
    if args.command == "record-tests":
        print(
            json.dumps(
                record_tests(args.log_path, args.exit_code, args.test_command),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "render-report":
        print(
            json.dumps(
                render_report(args.freeze_commit, args.generation_commit),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
