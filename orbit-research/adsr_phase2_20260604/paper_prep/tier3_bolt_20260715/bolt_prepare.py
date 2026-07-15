#!/usr/bin/env python3
"""Freeze BOLT seed, quality-floor, Gate-0, and pilot sampling artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
from bolt_core import SeedNamespace, canonical_json_hash, sha256_file  # noqa: E402


PROMOTION = ROOT / "paper_prep/autochain_20260712/T6_PROMOTION_RESULT.json"
EVPD_MANIFEST = ROOT / (
    "paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/"
    "CORRECTED_EVPD_TRAINING_MANIFEST.csv"
)
EVPD_MODEL = ROOT / (
    "paper_prep/w2_execution_20260712/evpd_liveconfirm_torch251_recovery/"
    "corrected_evpd_sigma08.joblib"
)
TRAJECTORY = ROOT / "orbit-research/trajectory_candidate_dataset.jsonl"
RAW_DETECTOR = ROOT / "orbit-research/adsr_phase2_20260604/vocal_presence_raw.jsonl"
DEV_PROMPTS = ROOT / "configs/prompts/dev.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def promoted_candidate() -> dict:
    record = json.loads(PROMOTION.read_text(encoding="utf-8"))
    if record.get("CORRECTED_INSTRUMENT_STATUS") != "PROMOTED":
        raise RuntimeError("BOLT requires the mechanically promoted W2 instrument")
    candidate = record.get("selected_candidate") or record["heldout"]["selected_candidate"]
    if candidate.get("family") != "or":
        raise RuntimeError("BOLT is frozen to the promoted OR-family instrument")
    return candidate


def is_present(demucs: float, panns: float, near_silent: bool, candidate: dict) -> bool:
    return (not near_silent) and (
        demucs >= float(candidate["demucs_threshold"])
        or panns >= float(candidate["panns_threshold"])
    )


def collision_scan(base: int) -> dict:
    lower, upper = base, base + 10_000_000
    candidates: set[Path] = {ROOT / "paper_prep/SEED_REGISTRY.md", ROOT / "orbit-research/RUN_LEDGER.jsonl"}
    for directory in (ROOT / "paper_prep", ROOT / "orbit-research"):
        for path in directory.rglob("*"):
            if not path.is_file() or OUT in path.parents:
                continue
            name = path.name.lower()
            if "manifest" in name or "seed" in name and "registry" in name:
                candidates.add(path)
    number = re.compile(rb"(?<!\d)(\d{9,10})(?!\d)")
    collisions: list[dict] = []
    scanned = 0
    for path in sorted(candidates):
        try:
            if path.stat().st_size > 256 * 1024 * 1024:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        scanned += 1
        for match in number.finditer(data):
            value = int(match.group(1))
            if lower <= value < upper:
                line = data.count(b"\n", 0, match.start()) + 1
                collisions.append(
                    {"path": str(path.relative_to(ROOT)), "line": line, "seed": value}
                )
    return {
        "candidate_base": base,
        "candidate_end_exclusive": upper,
        "files_scanned": scanned,
        "collisions": collisions,
        "collision_count": len(collisions),
        "status": "PASS" if not collisions else "FAIL",
    }


def choose_namespace(start: int) -> dict:
    if start % 10_000_000:
        raise ValueError("namespace base must be 10-million aligned")
    attempts = []
    for base in range(start, 2_140_000_000, 10_000_000):
        audit = collision_scan(base)
        attempts.append(audit)
        if audit["status"] == "PASS":
            return {"selected_base": base, "attempts": attempts, "status": "PASS"}
    raise RuntimeError("no unused seed namespace found in the bounded scan")


def command_collision(args: argparse.Namespace) -> int:
    path = OUT / "BOLT_SEED_COLLISION_AUDIT.json"
    if path.exists():
        raise FileExistsError(path)
    result = choose_namespace(args.start)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


def build_joined_rows() -> list[dict]:
    trajectory = {row["candidate_uid"]: row for row in read_jsonl(TRAJECTORY)}
    if len(trajectory) != 4096:
        raise RuntimeError(f"expected 4096 trajectory rows, found {len(trajectory)}")
    detector = {
        (str(row["prompt_id"]), int(row["candidate_index"])): row
        for row in read_jsonl(RAW_DETECTOR) if row.get("ok")
    }
    candidate = promoted_candidate()
    joined = []
    for manifest_index, row in enumerate(read_csv(EVPD_MANIFEST)):
        uid = row["task_id"]
        source = trajectory.get(uid)
        if source is None:
            raise RuntimeError(f"trajectory row missing for {uid}")
        prior = detector[(row["prompt_id"], int(row["candidate_index"]))]
        demucs = float(row["demucs_score"])
        panns = float(row["panns_score"])
        requested = int(row["requested_vocal"])
        present = is_present(demucs, panns, bool(prior.get("near_silent")), candidate)
        satisfied = present if requested else not present
        joined.append(
            {
                "source_row": manifest_index + 2,
                "task_id": uid,
                "prompt_id": row["prompt_id"],
                "candidate_index": int(row["candidate_index"]),
                "prompt_split": row["prompt_split"],
                "requested_vocal": requested,
                "demucs_score": demucs,
                "panns_score": panns,
                "near_silent": bool(prior.get("near_silent")),
                "promoted_present": int(present),
                "label_b_satisfied": int(satisfied),
                "common_robust_lcb": float(source["final_common_robust_lcb"]),
                "clap_to_original_prompt": float(source["final_semantic_fit"]),
                "analysis_split": source["analysis_split"],
                "mel_0p8_path": prior["mel_paths"]["0.8"],
            }
        )
    if len(joined) != 4096:
        raise RuntimeError("joined development/held-out spine is incomplete")
    return joined


def command_quality_floors(_args: argparse.Namespace) -> int:
    output = OUT / "BOLT_QUALITY_FLOORS.json"
    source_rows_output = OUT / "BOLT_QUALITY_FLOOR_SOURCE_ROWS.jsonl"
    if output.exists() or source_rows_output.exists():
        raise FileExistsError("quality-floor artifacts already exist; refusing overwrite")
    if (OUT / "BOLT_ACTION_ATLAS_PILOT_LEDGER.jsonl").exists():
        raise RuntimeError("refusing to derive floors after a BOLT pilot ledger exists")
    joined = build_joined_rows()
    eligible = [
        row for row in joined
        if row["prompt_split"] in {"train", "val"}
        and row["prompt_id"].startswith("dev_")
        and row["label_b_satisfied"] == 1
        and math.isfinite(row["common_robust_lcb"])
        and math.isfinite(row["clap_to_original_prompt"])
    ]
    directions = {}
    for requested, name in ((0, "instrumental_request"), (1, "vocal_request")):
        rows = [row for row in eligible if row["requested_vocal"] == requested]
        if len(rows) < 30:
            raise RuntimeError(f"too few eligible rows for {name}: {len(rows)}")
        directions[name] = {
            "requested_vocal": requested,
            "eligible_rows": len(rows),
            "unique_prompts": len({row["prompt_id"] for row in rows}),
            "common_robust_lcb_floor": float(
                np.quantile([row["common_robust_lcb"] for row in rows], 0.10, method="linear")
            ),
            "clap_to_original_prompt_floor": float(
                np.quantile([row["clap_to_original_prompt"] for row in rows], 0.10, method="linear")
            ),
            "source_task_ids": [row["task_id"] for row in rows],
            "source_manifest_rows": [row["source_row"] for row in rows],
        }
    source_artifacts = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in (PROMOTION, EVPD_MANIFEST, TRAJECTORY, RAW_DETECTOR)
    }
    payload = {
        "schema": "bolt_quality_floors_v1",
        "status": "FROZEN_BEFORE_BOLT_OUTPUT",
        "source_population": "pre-existing ACE-Step v1 development baseline outputs",
        "prompt_split": ["train", "val"],
        "held_out_excluded": True,
        "inclusion_criteria": [
            "prompt_id starts with dev_",
            "prompt_split is train or val",
            "promoted W2 Label-B instrument says satisfied",
            "finite final_common_robust_lcb",
            "finite final_semantic_fit against original prompt",
        ],
        "quantile": {"probability": 0.10, "numpy_method": "linear"},
        "directions": directions,
        "source_artifact_sha256": source_artifacts,
        "no_bolt_pilot_output_influenced_floors": True,
    }
    payload["floor_definition_sha256"] = canonical_json_hash(payload)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(source_rows_output, eligible)
    print(json.dumps({"floors": directions, "definition_sha256": payload["floor_definition_sha256"]}))
    return 0


def mel_summary(mel: np.ndarray) -> np.ndarray:
    value = np.asarray(mel, dtype=np.float32)
    return np.concatenate(
        [
            value.mean(1), value.std(1), value.max(1),
            np.percentile(value, 25, axis=1), np.percentile(value, 75, axis=1),
        ]
    )


def risk_frame() -> list[dict]:
    import joblib

    joined = build_joined_rows()
    model_record = joblib.load(EVPD_MODEL)
    if model_record.get("target") != "corrected Label-B constraint violation":
        raise RuntimeError("corrected EVPD model target mismatch")
    prompts = {row["prompt_id"]: row for row in read_jsonl(DEV_PROMPTS)}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in joined:
        if row["prompt_split"] not in {"train", "val"} or not row["prompt_id"].startswith("dev_"):
            continue
        feature = mel_summary(np.load(ROOT / row["mel_0p8_path"]))
        probability = float(
            model_record["model"].predict_proba(
                model_record["scaler"].transform(feature.reshape(1, -1))
            )[0, 1]
        )
        enriched = dict(row)
        enriched["corrected_evpd_violation_probability"] = probability
        enriched["candidate_violation"] = 1 - row["label_b_satisfied"]
        grouped[row["prompt_id"]].append(enriched)
    frame = []
    for prompt_id, candidates in sorted(grouped.items()):
        prompt = prompts[prompt_id]
        requested = int(candidates[0]["requested_vocal"])
        promoted_rate = float(np.mean([row["candidate_violation"] for row in candidates]))
        evpd_rate = float(np.mean([row["corrected_evpd_violation_probability"] for row in candidates]))
        frame.append(
            {
                "prompt_id": prompt_id,
                "requested_vocal": requested,
                "prompt_split": candidates[0]["prompt_split"],
                "candidate_rows": len(candidates),
                "promoted_violation_rate": promoted_rate,
                "corrected_evpd_mean_risk": evpd_rate,
                "risk_score": 0.5 * promoted_rate + 0.5 * evpd_rate,
                "genre": prompt.get("strata", {}).get("genre", "unknown"),
                "tempo_bin": prompt.get("strata", {}).get("tempo_bin", "unknown"),
                "prompt_specificity": prompt.get("strata", {}).get("prompt_specificity", "unknown"),
                "structure_complexity": prompt.get("strata", {}).get("structural_complexity", "unknown"),
                "language": prompt.get("strata", {}).get("language", "unknown"),
                "prompt": prompt,
            }
        )
    if len(frame) != 256:
        raise RuntimeError(f"expected 256 development prompts, found {len(frame)}")
    return frame


def command_gate0_manifest(args: argparse.Namespace) -> int:
    output = OUT / "BOLT_GATE0_TEST_MANIFEST.jsonl"
    if output.exists():
        raise FileExistsError(output)
    frame = risk_frame()
    rng = random.Random(args.selection_seed)
    chosen = []
    for requested in (0, 1):
        pool = [row for row in frame if row["requested_vocal"] == requested]
        chosen.extend(rng.sample(pool, 4))
    namespace = SeedNamespace(args.seed_base)
    rows = []
    for prompt_index, row in enumerate(sorted(chosen, key=lambda value: value["prompt_id"])):
        prompt = row["prompt"]
        rows.append(
            {
                "gate0_prompt_index": prompt_index,
                "prompt_id": row["prompt_id"],
                "requested_vocal": row["requested_vocal"],
                "prompt_split": row["prompt_split"],
                "risk_score_preexisting": row["risk_score"],
                "root_seeds": [
                    namespace._check(args.seed_base + 9_000_000 + prompt_index * 1000 + root_index)
                    for root_index in (0, 1)
                ],
                "prompt": prompt,
            }
        )
    write_jsonl(output, rows)
    print(json.dumps({"rows": len(rows), "prompt_ids": [row["prompt_id"] for row in rows]}))
    return 0


def assign_instrumental_risk_strata(rows: list[dict]) -> None:
    instrumental = sorted(
        (row for row in rows if row["requested_vocal"] == 0),
        key=lambda row: (row["risk_score"], canonical_json_hash(row["prompt_id"])),
    )
    n = len(instrumental)
    for rank, row in enumerate(instrumental):
        third = min(2, (rank * 3) // n)
        row["pilot_stratum"] = ("low_risk_instrumental", "medium_risk_instrumental", "high_risk_instrumental")[third]
    for row in rows:
        if row["requested_vocal"] == 1:
            row["pilot_stratum"] = "vocal_request"


def genre_allocations(pool: list[dict], slots: int = 12) -> dict[str, int]:
    """Proportional genre allocation with one mandatory seat per available genre."""
    counts = Counter(str(row["genre"]) for row in pool)
    if len(counts) > slots:
        raise RuntimeError(f"cannot represent {len(counts)} genres in {slots} slots")
    allocation = {genre: 1 for genre in counts}
    while sum(allocation.values()) < slots:
        eligible = [genre for genre in counts if allocation[genre] < counts[genre]]
        if not eligible:
            raise RuntimeError("genre allocation exhausted before filling pilot stratum")
        chosen = max(
            eligible,
            key=lambda genre: (
                counts[genre] / (2 * allocation[genre] + 1),
                canonical_json_hash(genre),
            ),
        )
        allocation[chosen] += 1
    return allocation


def command_pilot_manifest(args: argparse.Namespace) -> int:
    frame_csv = OUT / "BOLT_PILOT_PROMPT_FRAME.csv"
    manifest = OUT / "BOLT_PILOT_PROMPT_MANIFEST.jsonl"
    audit = OUT / "BOLT_PILOT_SAMPLING_AUDIT.md"
    if any(path.exists() for path in (frame_csv, manifest, audit)):
        raise FileExistsError("pilot sampling artifacts already exist")
    gate0_ids = {row["prompt_id"] for row in read_jsonl(OUT / "BOLT_GATE0_TEST_MANIFEST.jsonl")}
    frame = risk_frame()
    assign_instrumental_risk_strata(frame)
    for row in frame:
        row["gate0_excluded"] = int(row["prompt_id"] in gate0_ids)
    eligible = [row for row in frame if not row["gate0_excluded"]]
    rng = random.Random(args.selection_seed)
    selected = []
    frame_counts = Counter(row["pilot_stratum"] for row in eligible)
    allocation_by_stratum: dict[str, dict[str, int]] = {}
    genre_frame_counts: dict[tuple[str, str], int] = {}
    for stratum in (
        "high_risk_instrumental", "medium_risk_instrumental",
        "low_risk_instrumental", "vocal_request",
    ):
        pool = [row for row in eligible if row["pilot_stratum"] == stratum]
        if len(pool) < 12:
            raise RuntimeError(f"too few prompts in {stratum}: {len(pool)}")
        allocation = genre_allocations(pool, 12)
        allocation_by_stratum[stratum] = allocation
        for genre, count in Counter(str(row["genre"]) for row in pool).items():
            genre_frame_counts[(stratum, genre)] = count
            genre_pool = [row for row in pool if str(row["genre"]) == genre]
            selected.extend(rng.sample(genre_pool, allocation[genre]))
    selected = sorted(selected, key=lambda row: (
        ("high_risk_instrumental", "medium_risk_instrumental", "low_risk_instrumental", "vocal_request").index(row["pilot_stratum"]),
        row["prompt_id"],
    ))
    namespace = SeedNamespace(args.seed_base)
    manifest_rows = []
    for slot, row in enumerate(selected):
        genre = str(row["genre"])
        allocation = allocation_by_stratum[row["pilot_stratum"]][genre]
        genre_frame_size = genre_frame_counts[(row["pilot_stratum"], genre)]
        probability = allocation / genre_frame_size
        manifest_rows.append(
            {
                "prompt_slot": slot,
                "prompt_id": row["prompt_id"],
                "request_direction": "vocal" if row["requested_vocal"] else "instrumental",
                "requested_vocal": row["requested_vocal"],
                "stratum": row["pilot_stratum"],
                "risk_score_preexisting": row["risk_score"],
                "promoted_violation_rate": row["promoted_violation_rate"],
                "corrected_evpd_mean_risk": row["corrected_evpd_mean_risk"],
                "sampling_frame_size": frame_counts[row["pilot_stratum"]],
                "genre_frame_size": genre_frame_size,
                "genre_allocation": allocation,
                "inclusion_probability": probability,
                "design_weight": 1.0 / probability,
                "root_seeds": [namespace.root_seed(slot, index) for index in (0, 1)],
                "prompt": row["prompt"],
                "balance": {
                    key: row[key] for key in (
                        "genre", "tempo_bin", "prompt_specificity", "structure_complexity", "language"
                    )
                },
            }
        )
    frame_rows = []
    for row in frame:
        cell = (row["pilot_stratum"], str(row["genre"]))
        design = (
            {
                "genre_frame_size": genre_frame_counts[cell],
                "genre_allocation": allocation_by_stratum[row["pilot_stratum"]][str(row["genre"])],
                "inclusion_probability": (
                    allocation_by_stratum[row["pilot_stratum"]][str(row["genre"])]
                    / genre_frame_counts[cell]
                ),
            }
            if not row["gate0_excluded"] else
            {"genre_frame_size": "", "genre_allocation": "", "inclusion_probability": ""}
        )
        base_frame_row = {
            key: row[key] for key in (
                "prompt_id", "requested_vocal", "prompt_split", "promoted_violation_rate",
                "corrected_evpd_mean_risk", "risk_score", "genre", "tempo_bin",
                "prompt_specificity", "structure_complexity", "language", "pilot_stratum",
                "gate0_excluded",
            )
        }
        frame_rows.append({**base_frame_row, **design})
    write_csv(frame_csv, frame_rows)
    write_jsonl(manifest, manifest_rows)
    selected_counts = Counter(row["stratum"] for row in manifest_rows)
    balance_lines = []
    for stratum in selected_counts:
        subset = [row for row in manifest_rows if row["stratum"] == stratum]
        balance_lines.append(
            f"- {stratum}: genres={dict(Counter(x['balance']['genre'] for x in subset))}; "
            f"tempo={dict(Counter(x['balance']['tempo_bin'] for x in subset))}; "
            f"specificity={dict(Counter(x['balance']['prompt_specificity'] for x in subset))}; "
            f"structure={dict(Counter(x['balance']['structure_complexity'] for x in subset))}; "
            f"language={dict(Counter(x['balance']['language'] for x in subset))}"
        )
    audit.write_text(
        "# BOLT Pilot Sampling Audit\n\n"
        "`PILOT_SAMPLING_STATUS = FROZEN`\n\n"
        f"Selection seed: `{args.selection_seed}`. Gate-0 prompt IDs were excluded. "
        "All source prompt IDs begin with `dev_`; no held-out/test prompt is eligible.\n\n"
        "Risk is frozen as `0.5 * promoted-instrument candidate violation rate + "
        "0.5 * mean corrected-EVPD violation probability` over the eight pre-existing "
        "spine candidates. Instrumental prompts are rank-tertiled before sampling.\n\n"
        "Each stratum allocates 12 seats across genres with one mandatory seat per "
        "available genre and deterministic Webster proportional priorities for the "
        "remaining seats. Within each `(risk stratum, genre)` cell, selection is "
        "fixed-seed simple random sampling. Every row therefore has exact inclusion "
        "probability `cell allocation / eligible cell size` and inverse-probability "
        "design weight. Tempo, specificity, structure, and language are audited as "
        "secondary realized-balance dimensions.\n\n"
        f"Frozen genre allocations: `{json.dumps(allocation_by_stratum, sort_keys=True)}`.\n\n"
        f"Frame SHA256: `{sha256_file(frame_csv)}`. Manifest SHA256: `{sha256_file(manifest)}`.\n\n"
        "## Realized balance\n\n" + "\n".join(balance_lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(manifest_rows), "counts": selected_counts, "manifest_sha256": sha256_file(manifest)}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collision = sub.add_parser("collision-scan")
    collision.add_argument("--start", type=int, default=2_040_000_000)
    collision.set_defaults(func=command_collision)
    floors = sub.add_parser("quality-floors")
    floors.set_defaults(func=command_quality_floors)
    gate0 = sub.add_parser("gate0-manifest")
    gate0.add_argument("--seed-base", type=int, required=True)
    gate0.add_argument("--selection-seed", type=int, default=2026071501)
    gate0.set_defaults(func=command_gate0_manifest)
    pilot = sub.add_parser("pilot-manifest")
    pilot.add_argument("--seed-base", type=int, required=True)
    pilot.add_argument("--selection-seed", type=int, default=2026071502)
    pilot.set_defaults(func=command_pilot_manifest)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
