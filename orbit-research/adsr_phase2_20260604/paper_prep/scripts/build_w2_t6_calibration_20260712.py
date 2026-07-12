#!/usr/bin/env python3
"""Select and build the nonce-blinded t6 W2 calibration bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import math
import os
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT / "paper_prep/scripts"))
from build_rater_bundles_20260711 import (  # noqa: E402
    CHOIR_RULE,
    LABEL_A_WORDING,
    make_zip,
    render_html,
)

PAPER = ROOT / "paper_prep"
OUT = PAPER / "w2_execution_20260712/calibration"
SELECTION_MANIFEST = OUT / "W2_CALIBRATION_SELECTION_MANIFEST.csv"
SELECTION_AUDIT = OUT / "W2_CALIBRATION_SELECTION_AUDIT.json"
SAMPLING_FRAME = OUT / "W2_CALIBRATION_SAMPLING_FRAME.csv"
ADMIN_DIR = PAPER / "rater_admin_keys_20260712/t6_calibration"
ADMIN_MANIFEST = ADMIN_DIR / "T6_CALIBRATION_ADMIN.csv"
BUNDLE_ROOT = PAPER / "rater_bundles_20260712"
BUNDLE_DIR = BUNDLE_ROOT / "t6_calibration"
ZIP_PATH = BUNDLE_ROOT / "t6_calibration.zip"
SHA_PATH = BUNDLE_ROOT / "SHA256SUMS"
SPINE_MANIFEST = PAPER / "w2_execution_20260712/spine_reconstruction/SPINE_RECONSTRUCTION_MANIFEST.csv"
SPINE_SCORE_DIR = PAPER / "w2_execution_20260712/spine_reconstruction/scoring_ledgers"
RETAINED = PAPER / "w2_contingency_20260711/W2_RETAINED_AUDIO_MANIFEST.jsonl"
EXISTING_SCORES = PAPER / "w2_contingency_20260711/activated_20260711/full_corrected/W2_CORRECTED_MERGED.jsonl"
BATCH3_MANIFEST = PAPER / "w2_execution_20260712/analysis/BATCH3_1342_RESCORING_MANIFEST.csv"
BATCH3_SCORE_DIR = PAPER / "w2_execution_20260712/analysis/batch3_scoring_ledgers"
APPENDIX_ADMIN = PAPER / "rater_admin_keys_20260711/t1_decisive/DECISIVE_PACKET_ADMIN.csv"
SELECTION_SEED = 20260712
CORE_TRAIN = 60
CORE_HELDOUT = 100
ANCHOR = 40
TRANSPORT = 20
REPEATS = 20
RESERVE = 200
CANDIDATE_DEMUCS_THRESHOLD = 0.038639528676867485
CANDIDATE_PANNS_THRESHOLD = 0.03181814216077328


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    known = set(fieldnames)
    for row in rows[1:]:
        for field in row:
            if field not in known:
                known.add(field)
                fieldnames.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str, purpose: str) -> str:
    return hashlib.sha256(f"{SELECTION_SEED}|{purpose}|{value}".encode()).hexdigest()


def nonce_digest(nonce: str, value: str, purpose: str) -> str:
    return hmac.new(nonce.encode(), f"{SELECTION_SEED}|{purpose}|{value}".encode(), hashlib.sha256).hexdigest()


def latest_scores(directory: Path, pattern: str, key: str) -> dict[str, dict]:
    rows = {}
    for path in sorted(directory.glob(pattern)):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[str(row[key])] = row
    return rows


def joint_score(demucs: float, panns: float) -> float:
    return min(demucs / CANDIDATE_DEMUCS_THRESHOLD, panns / CANDIDATE_PANNS_THRESHOLD)


def score_band(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value < high:
        return "boundary"
    return "high"


def _add_strata(rows: list[dict], low: float, high: float) -> list[dict]:
    output = []
    for row in rows:
        corrected = int(
            float(row["demucs_score"]) >= CANDIDATE_DEMUCS_THRESHOLD
            and float(row["panns_score"]) >= CANDIDATE_PANNS_THRESHOLD
        )
        old = int(row["old_present"])
        request = int(row["requested_vocal"])
        value = joint_score(float(row["demucs_score"]), float(row["panns_score"]))
        band = score_band(value, low, high)
        disagreement = int(old != corrected)
        corrected_violation = int(corrected != request)
        old_violation = int(old != request)
        stratum = "|".join(
            [
                "vocal" if request else "instrumental",
                band,
                f"old{old}",
                f"corrected{corrected}",
                f"disagree{disagreement}",
                row["source_family"],
            ]
        )
        output.append(
            {
                **row,
                "joint_corrected_score": value,
                "corrected_score_band": band,
                "old_present": old,
                "corrected_present": corrected,
                "old_corrected_disagreement": disagreement,
                "old_violation": old_violation,
                "candidate_violation": corrected_violation,
                "calibration_stratum": stratum,
            }
        )
    return output


def spine_frame() -> list[dict]:
    admin = {row["task_id"]: row for row in read_csv(SPINE_MANIFEST)}
    scores = latest_scores(SPINE_SCORE_DIR, "scoring_w*.jsonl", "task_id")
    if len(admin) != 4096 or len(scores) != 4096:
        raise ValueError(f"spine is incomplete: admin={len(admin)}, scores={len(scores)}")
    rows = []
    for task_id, task in admin.items():
        score = scores[task_id]
        path = Path(task["target_audio_path"])
        media = path if path.is_absolute() else ROOT / path
        if not media.is_file():
            raise FileNotFoundError(media)
        rows.append(
            {
                "canonical_clip_id": task_id,
                "prompt_id": task["prompt_id"],
                "media_path": str(media),
                "media_sha256": "",
                "requested_vocal": int(task["requested_vocal"]),
                "demucs_score": float(score["recomputed_demucs_score"]),
                "panns_score": float(score["panns_score"]),
                "old_present": int(score["recomputed_old_present_0p1791"]),
                "source_family": "spine",
                "source_record_id": task["record_id"],
            }
        )
    values = np.asarray([joint_score(row["demucs_score"], row["panns_score"]) for row in rows])
    low, high = (float(value) for value in np.quantile(values, [1 / 3, 2 / 3]))
    return _add_strata(rows, low, high)


def transport_frame(spine: list[dict]) -> list[dict]:
    values = [float(row["joint_corrected_score"]) for row in spine]
    low, high = (float(value) for value in np.quantile(values, [1 / 3, 2 / 3]))
    retained = {row["record_id"]: row for row in read_jsonl(RETAINED)}
    rows = []
    for score in read_jsonl(EXISTING_SCORES):
        if score.get("status") != "PASS":
            continue
        admin = retained.get(score["record_id"])
        if not admin or admin["cohort"] not in {"n2_population_retry", "stage3_intervention"}:
            continue
        path = Path(admin["audio_path"])
        if not path.is_file():
            continue
        family = "N2" if admin["cohort"] == "n2_population_retry" else "Stage3"
        rows.append(
            {
                "canonical_clip_id": score["record_id"],
                "prompt_id": admin["prompt_id"],
                "media_path": str(path),
                "media_sha256": "",
                "requested_vocal": int(admin["requested_vocal"]),
                "demucs_score": float(score["vocal_energy_ratio"]),
                "panns_score": float(score["panns_score"]),
                "old_present": int(score["old_present"]),
                "source_family": family,
                "source_record_id": score["record_id"],
            }
        )
    batch3_admin = {row["record_id"]: row for row in read_csv(BATCH3_MANIFEST)}
    batch3_scores = latest_scores(BATCH3_SCORE_DIR, "batch3_w*.jsonl", "record_id")
    if len(batch3_scores) != 1342:
        raise ValueError(f"Batch-3 transport frame incomplete: {len(batch3_scores)}/1342")
    for record_id, score in batch3_scores.items():
        admin = batch3_admin[record_id]
        path = ROOT / admin["audio_path"]
        rows.append(
            {
                "canonical_clip_id": record_id,
                "prompt_id": admin["prompt_id"],
                "media_path": str(path),
                "media_sha256": admin["audio_sha256"],
                "requested_vocal": int(admin["requested_vocal"]),
                "demucs_score": float(score["demucs_score"]),
                "panns_score": float(score["panns_score"]),
                "old_present": int(score["old_present"]),
                "source_family": "Batch3_keep",
                "source_record_id": record_id,
            }
        )
    return _add_strata(rows, low, high)


def stratified_pick(pool: list[dict], positive_n: int, negative_n: int, purpose: str) -> list[dict]:
    selected = []
    for target, count in ((1, positive_n), (0, negative_n)):
        eligible = [row for row in pool if int(row["candidate_violation"]) == target]
        by_stratum: dict[str, list[dict]] = defaultdict(list)
        for row in eligible:
            by_stratum[row["calibration_stratum"]].append(row)
        for stratum in by_stratum:
            by_stratum[stratum].sort(key=lambda row: stable_key(row["canonical_clip_id"], purpose))
        order = sorted(by_stratum, key=lambda value: stable_key(value, purpose + "|stratum"))
        cursor = 0
        picked = []
        while len(picked) < count and any(by_stratum.values()):
            stratum = order[cursor % len(order)]
            if by_stratum[stratum]:
                picked.append(by_stratum[stratum].pop(0))
            cursor += 1
            if cursor > len(eligible) * max(len(order), 1) * 2:
                break
        if len(picked) != count:
            raise ValueError(f"cannot select {count} target={target} rows for {purpose}")
        selected.extend(picked)
    return selected


def _assign_probabilities(selected: list[dict], frame: list[dict], role: str) -> list[dict]:
    selected_counts = Counter(row["calibration_stratum"] for row in selected)
    eligible_counts = Counter(row["calibration_stratum"] for row in frame)
    output = []
    for row in selected:
        probability = selected_counts[row["calibration_stratum"]] / eligible_counts[row["calibration_stratum"]]
        output.append(
            {
                **row,
                "role": role,
                "selection_stage_probability": probability,
                "final_inclusion_probability": probability,
                "inclusion_probability": probability,
            }
        )
    return output


def _write_sampling_frame(frame: list[dict], selection: list[dict]) -> dict:
    eligible = Counter(row["calibration_stratum"] for row in frame)
    selected_by_role = {
        role: Counter(
            row["calibration_stratum"]
            for row in selection
            if row["role"] == role
        )
        for role in ("train", "heldout", "transport", "reserve")
    }
    rows = []
    for request, band, old, corrected, disagreement, family in product(
        ("vocal", "instrumental"),
        ("low", "boundary", "high"),
        (0, 1),
        (0, 1),
        (0, 1),
        ("spine", "N2", "Stage3", "Batch3_keep"),
    ):
        stratum = "|".join(
            [request, band, f"old{old}", f"corrected{corrected}", f"disagree{disagreement}", family]
        )
        rows.append(
            {
                "request_type": request,
                "corrected_score_band": band,
                "old_detector_status": old,
                "corrected_status": corrected,
                "old_corrected_disagreement": disagreement,
                "source_family": family,
                "calibration_stratum": stratum,
                "frame_eligible_count": eligible[stratum],
                "selected_train_count": selected_by_role["train"][stratum],
                "selected_heldout_count": selected_by_role["heldout"][stratum],
                "selected_transport_count": selected_by_role["transport"][stratum],
                "selected_reserve_count": selected_by_role["reserve"][stratum],
            }
        )
    write_csv(SAMPLING_FRAME, rows)
    return {
        "cross_product_cells": len(rows),
        "empty_cross_product_cells": sum(row["frame_eligible_count"] == 0 for row in rows),
        "frame_rows": sum(row["frame_eligible_count"] for row in rows),
    }


def select_calibration() -> dict:
    spine = spine_frame()
    ordered = sorted(spine, key=lambda row: stable_key(row["canonical_clip_id"], "anchor"))
    anchor = ordered[:ANCHOR]
    anchor_ids = {row["canonical_clip_id"] for row in anchor}
    anchor_positive = sum(row["candidate_violation"] for row in anchor)
    target_positive = max(0, min(60, 40 - anchor_positive))
    target_negative = 60 - target_positive
    remaining = [row for row in spine if row["canonical_clip_id"] not in anchor_ids]
    targeted_heldout = stratified_pick(remaining, target_positive, target_negative, "heldout_targeted")
    heldout_ids = anchor_ids | {row["canonical_clip_id"] for row in targeted_heldout}
    heldout = [
        {
            **row,
            "role": "heldout",
            "selection_component": "simple_random_anchor",
            "selection_stage_probability": ANCHOR / 4096,
            "final_inclusion_probability": ANCHOR / 4096,
            "inclusion_probability": ANCHOR / 4096,
        }
        for row in anchor
    ]
    heldout.extend(
        {
            **row,
            "selection_component": "targeted_heldout",
        }
        for row in _assign_probabilities(targeted_heldout, remaining, "heldout")
    )
    train_pool = [row for row in spine if row["canonical_clip_id"] not in heldout_ids]
    train_selected = stratified_pick(train_pool, 30, 30, "train")
    train = [
        {**row, "selection_component": "targeted_train"}
        for row in _assign_probabilities(train_selected, train_pool, "train")
    ]
    used = heldout_ids | {row["canonical_clip_id"] for row in train_selected}
    reserve_pool = [row for row in spine if row["canonical_clip_id"] not in used]
    reserve = stratified_pick(reserve_pool, RESERVE // 2, RESERVE // 2, "reserve")
    reserve = [
        {**row, "selection_component": "class_count_only_reserve", "reserve_order": index + 1}
        for index, row in enumerate(
            sorted(_assign_probabilities(reserve, reserve_pool, "reserve"), key=lambda row: stable_key(row["canonical_clip_id"], "reserve_order"))
        )
    ]

    transport_pool = transport_frame(spine)
    quotas = {"N2": 7, "Stage3": 7, "Batch3_keep": 6}
    transport = []
    for family, count in quotas.items():
        eligible = [row for row in transport_pool if row["source_family"] == family]
        ranked = sorted(
            eligible,
            key=lambda row: (
                -int(row["old_corrected_disagreement"]),
                abs(math.log(max(float(row["joint_corrected_score"]), 1e-12))),
                stable_key(row["canonical_clip_id"], "transport"),
            ),
        )
        chosen = []
        seen_media = set()
        for row in ranked:
            media_identity = row.get("media_sha256") or row["media_path"]
            if media_identity in seen_media:
                continue
            seen_media.add(media_identity)
            chosen.append(row)
            if len(chosen) == count:
                break
        if len(chosen) != count:
            raise ValueError(f"transport family {family} has only {len(chosen)} rows")
        selected_counts = Counter(row["calibration_stratum"] for row in chosen)
        eligible_counts = Counter(row["calibration_stratum"] for row in eligible)
        for row in chosen:
            transport.append(
                {
                    **row,
                    "role": "transport",
                    "selection_component": "boundary_disagreement_transport",
                    "selection_stage_probability": selected_counts[row["calibration_stratum"]] / eligible_counts[row["calibration_stratum"]],
                    "final_inclusion_probability": selected_counts[row["calibration_stratum"]] / eligible_counts[row["calibration_stratum"]],
                    "inclusion_probability": selected_counts[row["calibration_stratum"]] / eligible_counts[row["calibration_stratum"]],
                }
            )

    repeat_parents = stratified_pick(heldout, 10, 10, "repeat_parents")
    repeats = [
        {
            **row,
            "canonical_clip_id": f"{row['canonical_clip_id']}__hidden_repeat",
            "role": "repeat",
            "selection_component": "hidden_intrarater_repeat",
            "repeat_parent_clip_id": row["canonical_clip_id"],
        }
        for row in repeat_parents
    ]
    unique = train + heldout + transport
    if len(unique) != 180 or len(repeats) != 20:
        raise AssertionError(f"calibration cardinality mismatch: unique={len(unique)}, repeats={len(repeats)}")
    selection = unique + repeats + reserve
    for row in selection:
        row["calibration_analysis_weight_multiplier"] = 0 if row["role"] == "repeat" else 1
    media_hash_cache: dict[str, str] = {}
    for row in selection:
        media_path = str(row["media_path"])
        if media_path not in media_hash_cache:
            path = Path(media_path)
            if not path.is_absolute():
                path = ROOT / path
            media_hash_cache[media_path] = sha256_file(path)
        row["media_sha256"] = media_hash_cache[media_path]
    unique_hashes = [row["media_sha256"] for row in unique]
    if len(set(unique_hashes)) != len(unique_hashes):
        raise ValueError("the 180 unique calibration rows contain duplicate media")
    write_csv(SELECTION_MANIFEST, selection)
    frame_audit = _write_sampling_frame(spine + transport_pool, selection)
    audit = {
        "status": "PASS",
        "unique_calibration_rows": len(unique),
        "train_rows": len(train),
        "heldout_rows": len(heldout),
        "simple_random_anchor_rows": len(anchor),
        "transport_rows": len(transport),
        "hidden_repeats": len(repeats),
        "reserve_rows": len(reserve),
        "heldout_candidate_violation_composition": dict(Counter(row["candidate_violation"] for row in heldout)),
        "transport_source_counts": dict(Counter(row["source_family"] for row in transport)),
        "spine_score_band_counts": dict(Counter(row["corrected_score_band"] for row in spine)),
        "inclusion_probabilities_present": all(float(row["inclusion_probability"]) > 0 for row in selection),
        "selection_stage_probabilities_present": all(float(row["selection_stage_probability"]) > 0 for row in selection),
        "final_inclusion_probabilities_present": all(float(row["final_inclusion_probability"]) > 0 for row in selection),
        "hidden_repeat_calibration_weight_zero": all(
            int(row["calibration_analysis_weight_multiplier"]) == 0
            for row in repeats
        ),
        **frame_audit,
    }
    SELECTION_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def _link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def resolve_appendix_media(source: dict[str, str], root: Path = ROOT) -> Path:
    expected = source.get("sha256", "")
    tried = []
    for field in ("source_path", "package_media_path"):
        value = source.get(field, "")
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        tried.append(str(path))
        if path.is_file() and (not expected or sha256_file(path) == expected):
            return path
    raise FileNotFoundError(f"no checksum-valid appendix media; tried={tried}")


def _appendix_row() -> dict:
    rows = read_csv(APPENDIX_ADMIN)
    source = next(row for row in rows if row["rating_id"] == "decisive_04_a5f338f1ce29")
    path = resolve_appendix_media(source)
    return {
        "canonical_clip_id": source["rating_id"],
        "prompt_id": source["prompt_id"],
        "media_path": str(path),
        "media_sha256": sha256_file(path),
        "requested_vocal": int(source["requested_vocal"]),
        "demucs_score": "",
        "panns_score": "",
        "old_present": "",
        "corrected_present": "",
        "old_corrected_disagreement": "",
        "candidate_violation": "",
        "joint_corrected_score": "",
        "corrected_score_band": "",
        "calibration_stratum": "appendix_pending_adjudication",
        "source_family": "decisive_appendix",
        "source_record_id": source["source_id"],
        "role": "appendix",
        "selection_component": "pending_adjudication_appendix_excluded_from_all_metrics",
        "inclusion_probability": 1.0,
        "repeat_parent_clip_id": "",
        "reserve_order": "",
    }


def build_bundle(nonce: str) -> dict:
    if not nonce:
        raise ValueError("ADSR_BLINDING_NONCE is required")
    if BUNDLE_DIR.exists() or ZIP_PATH.exists() or ADMIN_MANIFEST.exists():
        raise FileExistsError("t6 output already exists; refusing to overwrite")
    selection = read_csv(SELECTION_MANIFEST)
    main = [row for row in selection if row["role"] in {"train", "heldout", "transport", "repeat"}]
    if len(main) != 200:
        raise ValueError(f"expected 200 calibration presentations, found {len(main)}")
    appendix = _appendix_row()
    rows = main + [appendix]
    shuffled = sorted(rows, key=lambda row: nonce_digest(nonce, row["canonical_clip_id"], "shuffle"))
    BUNDLE_DIR.mkdir(parents=True)
    (BUNDLE_DIR / "media").mkdir()
    public = []
    admin = []
    id_map = {}
    for reveal_sequence, row in enumerate(shuffled, start=1):
        rating_id = "r_" + nonce_digest(nonce, row["canonical_clip_id"], "rating_id")[:20]
        id_map[row["canonical_clip_id"]] = rating_id
        source = Path(row["media_path"])
        if not source.is_absolute():
            source = ROOT / source
        suffix = source.suffix.lower()
        destination = BUNDLE_DIR / "media" / f"audio_{rating_id}{suffix}"
        _link(source, destination)
        request_mode = "vocal" if row["requested_vocal"] == "1" else "instrumental"
        public.append(
            {
                "rating_id": rating_id,
                "media": f"media/{destination.name}",
                "request_mode": request_mode,
            }
        )
        admin.append(
            {
                "rating_id": rating_id,
                "canonical_clip_id": row["canonical_clip_id"],
                "role": row["role"],
                "repeat_parent_rating_id": "",
                "repeat_parent_clip_id": row.get("repeat_parent_clip_id", ""),
                "media_path": str(source),
                "media_sha256": sha256_file(destination),
                "request_mode": request_mode,
                "requested_vocal": row["requested_vocal"],
                "demucs_score": row["demucs_score"],
                "panns_score": row["panns_score"],
                "old_present": row["old_present"],
                "corrected_present": row["corrected_present"],
                "candidate_violation": row["candidate_violation"],
                "calibration_stratum": row["calibration_stratum"],
                "source_family": row["source_family"],
                "selection_component": row["selection_component"],
                "inclusion_probability": row["inclusion_probability"],
                "reserve_order": row.get("reserve_order", ""),
                "shuffle_seed": SELECTION_SEED,
                "reveal_sequence": reveal_sequence,
                "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
            }
        )
    for row in admin:
        parent_clip = row["repeat_parent_clip_id"]
        if parent_clip:
            row["repeat_parent_rating_id"] = id_map[parent_clip]
    payload = {
        "bundle_id": "t6_calibration",
        "title": "W2 corrected-instrument calibration",
        "mode": "decisive_staged",
        "wording_html": f"<p><strong>Label A:</strong> {LABEL_A_WORDING}</p><p>{CHOIR_RULE}</p>",
        "rows": public,
    }
    html = render_html("W2 corrected-instrument calibration", payload)
    html = html.replace(
        'return /^(pi:[A-Za-z][A-Za-z0-9 ._-]{0,63}|human:CXY)$/.test(v)',
        'return v==="pi:Richard"',
    ).replace(
        "Enter one approved source once: <code>pi:&lt;name&gt;</code> or <code>human:CXY</code>.",
        "This bundle accepts only <code>pi:Richard</code>.",
    ).replace(
        "Use pi:&lt;name&gt; or human:CXY exactly.",
        "Use pi:Richard exactly.",
    )
    if 'return v==="pi:Richard"' not in html:
        raise AssertionError("t6 source restriction was not applied")
    (BUNDLE_DIR / "index.html").write_text(html, encoding="utf-8")
    (BUNDLE_DIR / "README").write_text(
        "t6_calibration: 200 blinded calibration presentations plus one excluded adjudication appendix.\n"
        "Complete Label A blind, reveal the request, then complete Label B; use pi:Richard exactly.\n"
        "Do not start until W2_AMENDMENT_20260712.md carries both PI signatures.\n",
        encoding="utf-8",
    )
    write_csv(ADMIN_MANIFEST, admin)
    make_zip(BUNDLE_DIR, ZIP_PATH)
    SHA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHA_PATH.write_text(f"{sha256_file(ZIP_PATH)}  {ZIP_PATH.resolve()}\n", encoding="utf-8")
    return {
        "bundle_rows": len(public),
        "calibration_presentations": len(main),
        "appendix_presentations": 1,
        "media_files": len(list((BUNDLE_DIR / "media").iterdir())),
        "zip_sha256": sha256_file(ZIP_PATH),
        "admin_rows": len(admin),
        "source_restricted_to": "pi:Richard",
    }


def audit_bundle() -> dict:
    import soundfile as sf

    visible = sorted(path.name for path in BUNDLE_DIR.iterdir())
    if visible != ["README", "index.html", "media"]:
        raise ValueError(f"bundle contains unexpected files: {visible}")
    html = (BUNDLE_DIR / "index.html").read_text(encoding="utf-8")
    forbidden = ["expected_label", '"bucket"', '"arm"', '"set_name"']
    leaked = [token for token in forbidden if token in html.lower()]
    admin = read_csv(ADMIN_MANIFEST)
    if leaked or len(admin) != 201 or len(list((BUNDLE_DIR / "media").iterdir())) != 201:
        raise ValueError(f"t6 bundle audit failed: leaked={leaked}, admin={len(admin)}")
    if "Reveal request" not in html or "label_a_amended" not in html:
        raise ValueError("t6 staged reveal controls are missing")
    if 'return v==="pi:Richard"' not in html:
        raise ValueError("t6 rating source is not restricted")
    if sha256_file(ZIP_PATH) not in SHA_PATH.read_text(encoding="utf-8"):
        raise ValueError("t6 zip checksum file is stale")
    durations = []
    sample_rates = Counter()
    for row in admin:
        suffix = Path(row["media_path"]).suffix.lower()
        media = BUNDLE_DIR / "media" / f"audio_{row['rating_id']}{suffix}"
        if not media.is_file() or sha256_file(media) != row["media_sha256"]:
            raise ValueError(f"t6 media checksum mismatch: {row['rating_id']}")
        info = sf.info(str(media))
        duration = info.frames / info.samplerate if info.samplerate else 0
        if duration <= 1:
            raise ValueError(f"t6 media is too short or undecodable: {row['rating_id']}")
        durations.append(duration)
        sample_rates[int(info.samplerate)] += 1
    return {
        "status": "PASS",
        "bundle_rows": 201,
        "calibration_rows": 200,
        "appendix_rows": 1,
        "media_rows": 201,
        "leak_test": "PASS",
        "staged_reveal": "PASS",
        "source_enum": "pi:Richard_only",
        "checksum_valid_media": len(durations),
        "decoded_media": len(durations),
        "minimum_duration_s": min(durations),
        "sample_rate_counts": dict(sample_rates),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("select")
    sub.add_parser("build")
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.command == "select":
        result = select_calibration()
    elif args.command == "build":
        result = build_bundle(os.environ.get("ADSR_BLINDING_NONCE", ""))
    else:
        result = audit_bundle()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
