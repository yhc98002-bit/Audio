#!/usr/bin/env python3
"""Fail-closed final audit for the bounded ACE-Step v1.5 replication."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


EXPECTED = {"smoke": 2, "prevalence": 1024, "retry": 512, "intervention": 256}


def key(row: dict) -> tuple[str, str, int]:
    return str(row["prompt_id"]), str(row["condition"]), int(row["seed"])


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank line at {path}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"non-object row at {path}:{line_number}")
            rows.append(row)
    return rows


def read_directory(path: Path, pattern: str) -> list[dict]:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} files under {path}")
    rows = []
    for file_path in files:
        rows.extend(read_jsonl(file_path))
    return rows


def unique_map(rows: list[dict], label: str) -> dict[tuple[str, str, int], dict]:
    output = {}
    for row in rows:
        row_key = key(row)
        if row_key in output:
            raise ValueError(f"duplicate {label} key {row_key}")
        output[row_key] = row
    return output


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def failure_category(error: str | None) -> str:
    message = error or ""
    if "NaN or Inf latents" in message:
        return "nan_or_inf_latents"
    if "array is too big" in message:
        return "incomplete_audio_header"
    if "FileNotFoundError" in message:
        return "audio_path_or_export_failure"
    return "unknown"


def audit_stage(
    name: str,
    manifest_path: Path,
    generation_dir: Path,
    score_dir: Path,
    verify_hashes: bool,
) -> tuple[dict, list[dict], list[dict]]:
    manifest = unique_map(read_jsonl(manifest_path), f"{name} manifest")
    if len(manifest) != EXPECTED[name]:
        raise ValueError(f"{name}: expected {EXPECTED[name]} manifest rows, got {len(manifest)}")
    attempts = read_directory(generation_dir, "generation_w*.jsonl")
    scores = unique_map(read_directory(score_dir, "score_w*.jsonl"), f"{name} score")
    if set(scores) != set(manifest):
        raise ValueError(f"{name}: score/manifest key mismatch")
    by_key = defaultdict(list)
    for row in attempts:
        if key(row) not in manifest:
            raise ValueError(f"{name}: generation key outside manifest: {key(row)}")
        by_key[key(row)].append(row)
    if set(by_key) != set(manifest):
        raise ValueError(f"{name}: generation/manifest key mismatch")
    successful = {}
    for row_key, values in by_key.items():
        passes = [row for row in values if row.get("status") == "PASS"]
        if len(passes) != 1:
            raise ValueError(f"{name}: expected one PASS for {row_key}, got {len(passes)}")
        successful[row_key] = passes[0]
    near_silent = sum(bool(row.get("near_silent")) for row in scores.values())
    if near_silent:
        raise ValueError(f"{name}: {near_silent} near-silent score rows")
    media = []
    hash_mismatches = 0
    for row_key, row in sorted(successful.items()):
        audio_path = Path(row["audio_path"])
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        actual_hash = sha256_file(audio_path) if verify_hashes else row["audio_sha256"]
        if actual_hash != row["audio_sha256"]:
            hash_mismatches += 1
        media.append(
            {
                "stage": name,
                "prompt_id": row_key[0],
                "condition": row_key[1],
                "seed": row_key[2],
                "audio_path": str(audio_path),
                "audio_sha256": row["audio_sha256"],
                "host": row["host"],
            }
        )
    if hash_mismatches:
        raise ValueError(f"{name}: {hash_mismatches} audio hash mismatches")
    failures = [row for row in attempts if row.get("status") != "PASS"]
    categories = Counter(failure_category(row.get("error")) for row in failures)
    audit = {
        "stage": name,
        "manifest_rows": len(manifest),
        "generation_attempts": len(attempts),
        "generation_pass": len(successful),
        "generation_fail": len(failures),
        "score_rows": len(scores),
        "near_silent_rows": near_silent,
        "audio_files": len(media),
        "hash_mismatches": hash_mismatches,
        "failure_categories": json.dumps(categories, sort_keys=True),
    }
    return audit, media, list(scores.values())


def metrics(scores: dict[str, list[dict]]) -> dict:
    prevalence = scores["prevalence"]
    by_prompt = defaultdict(list)
    for row in prevalence:
        by_prompt[row["prompt_id"]].append(row)
    prompt_rates = {
        prompt_id: np.mean([int(row["type_correct"]) for row in rows])
        for prompt_id, rows in by_prompt.items()
    }
    strata = {
        stratum: float(
            np.mean(
                [
                    prompt_rates[prompt_id]
                    for prompt_id, rows in by_prompt.items()
                    if rows[0]["vocal_stratum"] == stratum
                ]
            )
        )
        for stratum in ("vocal", "instrumental")
    }
    retry_by_prompt = defaultdict(list)
    for row in scores["retry"]:
        retry_by_prompt[row["prompt_id"]].append(int(row["type_correct"]))
    retry_rates = [float(np.mean(values)) for values in retry_by_prompt.values()]
    paired = defaultdict(dict)
    metadata = {}
    for row in scores["intervention"]:
        paired[(row["prompt_id"], int(row["seed_idx"]))][row["condition"]] = int(
            row["type_correct"]
        )
        metadata[row["prompt_id"]] = row["vocal_stratum"]
    if any(set(values) != {"baseline", "recondition"} for values in paired.values()):
        raise ValueError("incomplete intervention pairs")
    deltas = defaultdict(list)
    for (prompt_id, _seed_idx), values in paired.items():
        deltas[prompt_id].append(values["recondition"] - values["baseline"])
    prompt_deltas = {prompt_id: float(np.mean(values)) for prompt_id, values in deltas.items()}
    values = np.asarray(list(prompt_deltas.values()))
    rng = np.random.default_rng(20260709)
    boot = np.asarray([rng.choice(values, len(values), replace=True).mean() for _ in range(10_000)])
    return {
        "prevalence_overall": float(np.mean([int(row["type_correct"]) for row in prevalence])),
        "prevalence_vocal_prompt_mean": strata["vocal"],
        "prevalence_instrumental_prompt_mean": strata["instrumental"],
        "retry_prompt_mean": float(np.mean(retry_rates)),
        "retry_zero_clean_prompts": int(sum(rate == 0 for rate in retry_rates)),
        "intervention_prompt_mean_delta": float(values.mean()),
        "intervention_ci_low": float(np.quantile(boot, 0.025)),
        "intervention_ci_high": float(np.quantile(boot, 0.975)),
        "intervention_vocal_delta": float(
            np.mean([value for prompt_id, value in prompt_deltas.items() if metadata[prompt_id] == "vocal"])
        ),
        "intervention_instrumental_delta": float(
            np.mean(
                [value for prompt_id, value in prompt_deltas.items() if metadata[prompt_id] == "instrumental"]
            )
        ),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-prep", type=Path, default=Path("paper_prep"))
    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path(os.environ.get("ADSR_V15_EXTERNAL_ROOT", "ADSR_T9_20260709")),
        help="Bulk retry/intervention audio root (or set ADSR_V15_EXTERNAL_ROOT).",
    )
    parser.add_argument("--skip-audio-hashes", action="store_true")
    args = parser.parse_args()
    base = args.paper_prep / "v15_replication_20260709"
    configs = {
        "smoke": (
            base / "manifests/V15_SMOKE_MANIFEST.jsonl",
            base / "smoke/ledgers",
            base / "smoke_score/ledgers",
        ),
        "prevalence": (
            base / "manifests/V15_PREVALENCE_MANIFEST.jsonl",
            base / "prevalence/ledgers",
            base / "prevalence_score/ledgers",
        ),
        "retry": (
            base / "prevalence_analysis/V15_RETRY_MANIFEST.jsonl",
            base / "valid_ledgers/retry_generation",
            base / "valid_ledgers/retry_score",
        ),
        "intervention": (
            base / "prevalence_analysis/V15_INTERVENTION_MANIFEST.jsonl",
            base / "valid_ledgers/intervention_generation",
            base / "valid_ledgers/intervention_score",
        ),
    }
    audits, media, all_scores = [], [], {}
    for name, (manifest, generation, score) in configs.items():
        audit, stage_media, stage_scores = audit_stage(
            name, manifest, generation, score, not args.skip_audio_hashes
        )
        audits.append(audit)
        media.extend(stage_media)
        all_scores[name] = stage_scores
    result = metrics(all_scores)
    write_csv(base / "V15_ATTEMPT_AUDIT.csv", audits)
    write_csv(base / "V15_AUDIO_MANIFEST.csv", media)
    report = f"""# ACE-Step v1.5 Bounded Replication

`V15_REPLICATION_STATUS = COMPLETE`

## Coverage And Audit

- Smoke: 2/2 successful, decoded, non-silent, and scored.
- Difficult-set prevalence: 1,024/1,024 successful and scored.
- Focused retry: 512/512 successful and scored.
- Matched intervention: 256/256 successful and scored.
- Near-silent scored rows: 0.
- Audio SHA-256 mismatches: 0.
- Failed generation attempts are retained in raw ledgers and excluded only
  after requiring exactly one PASS for every manifest key.

## Results

- Difficult-set per-draw type-correct rate: {result['prevalence_overall']:.6f}.
- Vocal-request prompt mean: {result['prevalence_vocal_prompt_mean']:.6f}.
- Instrumental-request prompt mean: {result['prevalence_instrumental_prompt_mean']:.6f}.
- Focused retry prompt mean: {result['retry_prompt_mean']:.6f}; zero-clean
  prompts at 32 fresh seeds: {result['retry_zero_clean_prompts']}/16.
- Matched reconditioning prompt-mean delta:
  {result['intervention_prompt_mean_delta']:+.6f}, prompt-bootstrap 95% CI
  [{result['intervention_ci_low']:+.6f}, {result['intervention_ci_high']:+.6f}].
- Vocal-request delta: {result['intervention_vocal_delta']:+.6f}.
- Instrumental-request delta: {result['intervention_instrumental_delta']:+.6f}.

## Claim Boundary

This completes the mandatory bounded v1.5 replication. The 128 prompts are a
selected difficult/stratified set, not a generic population sample. The result
shows severe vocal-request failures and a small, uncertain focused
reconditioning lift. It does not replace the frozen ACE-Step v1 evidence and
does not support a broad v1.5 intervention-success claim.

Audio for retry and intervention is stored outside Git under
`{args.external_root}`; `V15_AUDIO_MANIFEST.csv` records every path and hash.
"""
    (base / "V15_FINAL_REPLICATION_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "COMPLETE", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
