#!/usr/bin/env python3
"""Build the hash-disjoint T7 negative-gold staged-reveal rater bundle."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import math
import os
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
sys.path.insert(0, str(PAPER / "scripts"))
from build_rater_bundles_20260711 import (  # noqa: E402
    CHOIR_RULE,
    LABEL_A_WORDING,
    make_zip,
    render_html,
)


SELECTION_SEED = 20260713
BUNDLE_ID = "t7_judge_gold_negatives"
N_ROWS = 40
FAR_BELOW_RATIO = 0.5
PROMOTION = PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json"
SPINE_ROOT = PAPER / "w2_execution_20260712/spine_reconstruction_torch251_recovery"
SPINE_MANIFEST = SPINE_ROOT / "SPINE_RECONSTRUCTION_MANIFEST.csv"
SPINE_SCORES = SPINE_ROOT / "scoring_ledgers"
CALIBRATION_SELECTION = PAPER / "w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_MANIFEST.csv"
JUDGE_GOLD = PAPER / "autochain_20260712/judge_aprime/JUDGE_LABEL_A_GOLD_SPLIT.csv"
T6_ADMIN = PAPER / "rater_admin_keys_20260712/t6_calibration_torch251_recovery/T6_CALIBRATION_ADMIN.csv"
T6_RATINGS = PAPER / "autochain_20260712/T6_OFFICIAL_RATINGS.csv"

OUT = PAPER / "t7_judge_gold_20260713"
SAMPLING_FRAME = OUT / "T7_SAMPLING_FRAME.csv"
SELECTION = OUT / "T7_SELECTION_MANIFEST.csv"
SELECTION_AUDIT = OUT / "T7_SELECTION_AUDIT.json"
REPORT = OUT / "T7_JUDGE_GOLD_NEGATIVES_REPORT.md"
ADMIN_DIR = PAPER / "rater_admin_keys_20260712" / BUNDLE_ID
ADMIN = ADMIN_DIR / "T7_JUDGE_GOLD_NEGATIVES_ADMIN.csv"
BUNDLE_ROOT = PAPER / "rater_bundles_20260712"
BUNDLE_DIR = BUNDLE_ROOT / BUNDLE_ID
ZIP_PATH = BUNDLE_ROOT / f"{BUNDLE_ID}.zip"
SHA_PATH = BUNDLE_ROOT / "SHA256SUMS"


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
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str, purpose: str) -> str:
    return hashlib.sha256(f"{SELECTION_SEED}|{purpose}|{value}".encode()).hexdigest()


def nonce_key(nonce: str, value: str, purpose: str) -> str:
    return hmac.new(
        nonce.encode(), f"{SELECTION_SEED}|{purpose}|{value}".encode(), hashlib.sha256
    ).hexdigest()


def latest_scores() -> dict[str, dict]:
    rows = {}
    for path in sorted(SPINE_SCORES.glob("scoring_w*.jsonl")):
        for row in read_jsonl(path):
            if row.get("status") == "PASS":
                rows[row["task_id"]] = row
    if len(rows) != 4_096:
        raise ValueError(f"spine score cardinality changed: {len(rows)}")
    return rows


def excluded_hashes() -> dict[str, set[str]]:
    calibration = {
        row["media_sha256"] for row in read_csv(CALIBRATION_SELECTION) if row["media_sha256"]
    }
    judge = {row["media_sha256"] for row in read_csv(JUDGE_GOLD) if row["media_sha256"]}
    if not calibration or not judge:
        raise ValueError("exclusion hash sets are empty")
    return {"detector_selection_promotion": calibration, "existing_judge_gold": judge}


def negative_yield_basis() -> dict:
    promotion = json.loads(PROMOTION.read_text(encoding="utf-8"))
    candidate = promotion["heldout"]["selected_candidate"]
    ratings = {row["rating_id"]: row for row in read_csv(T6_RATINGS)}
    absent = []
    for row in read_csv(T6_ADMIN):
        if row["role"] not in {"train", "heldout", "transport"}:
            continue
        present = (
            float(row["demucs_score"]) >= float(candidate["demucs_threshold"])
            or float(row["panns_score"]) >= float(candidate["panns_threshold"])
        )
        if not present:
            absent.append(ratings[row["rating_id"]]["label_a_voice_presence"])
    decided = [label for label in absent if label in {"yes", "no"}]
    successes = sum(label == "no" for label in decided)
    if not decided:
        raise ValueError("no T6 predicted-absent yield basis")
    z = 1.959963984540054
    p = successes / len(decided)
    denominator = 1 + z * z / len(decided)
    lower = (
        p
        + z * z / (2 * len(decided))
        - z * math.sqrt(p * (1 - p) / len(decided) + z * z / (4 * len(decided) ** 2))
    ) / denominator
    return {
        "t6_predicted_absent_decided": len(decided),
        "t6_predicted_absent_human_no": successes,
        "observed_negative_yield": p,
        "wilson_95_lower": lower,
        "t7_point_expected_negatives": N_ROWS * p,
        "t7_conservative_expected_negatives": N_ROWS * lower,
    }


def build_frame() -> tuple[list[dict], dict]:
    promotion = json.loads(PROMOTION.read_text(encoding="utf-8"))
    if promotion["CORRECTED_INSTRUMENT_STATUS"] != "PROMOTED":
        raise ValueError("T7 requires the mechanically promoted candidate")
    candidate = promotion["heldout"]["selected_candidate"]
    if candidate["family"] != "or":
        raise ValueError("T7 implementation is frozen for the promoted OR family")
    admin = {row["task_id"]: row for row in read_csv(SPINE_MANIFEST)}
    scores = latest_scores()
    exclusions = excluded_hashes()
    exclusion_union = set().union(*exclusions.values())
    eligible = []
    excluded_counts = Counter()
    for task_id, task in admin.items():
        score = scores[task_id]
        demucs = float(score["recomputed_demucs_score"])
        panns = float(score["panns_score"])
        ratio = max(
            demucs / float(candidate["demucs_threshold"]),
            panns / float(candidate["panns_threshold"]),
        )
        if int(task["requested_vocal"]) != 0 or ratio >= FAR_BELOW_RATIO:
            continue
        path = Path(task["target_audio_path"])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = sha256(path)
        if digest in exclusion_union:
            for source, values in exclusions.items():
                excluded_counts[source] += int(digest in values)
            continue
        eligible.append(
            {
                "canonical_clip_id": task_id,
                "record_id": task["record_id"],
                "prompt_id": task["prompt_id"],
                "candidate_index": int(task["candidate_index"]),
                "candidate_seed": int(task["candidate_seed"]),
                "media_path": str(path),
                "media_sha256": digest,
                "request_mode": "instrumental",
                "requested_vocal": 0,
                "demucs_score": demucs,
                "panns_score": panns,
                "promoted_present": 0,
                "score_to_threshold_ratio": ratio,
                "source_family": "spine",
                "eligibility_rule": "instrumental_and_promoted_OR_score_ratio_below_0p5",
            }
        )
    if len({row["media_sha256"] for row in eligible}) != len(eligible):
        raise ValueError("eligible frame has duplicate media hashes")
    by_prompt: dict[str, list[dict]] = {}
    for row in eligible:
        by_prompt.setdefault(row["prompt_id"], []).append(row)
    representatives = []
    for prompt_id, rows in by_prompt.items():
        representatives.append(
            min(rows, key=lambda row: (row["score_to_threshold_ratio"], row["canonical_clip_id"]))
        )
    representatives.sort(key=lambda row: stable_key(row["prompt_id"], "t7_prompt_sample"))
    if len(representatives) < N_ROWS:
        raise ValueError(f"T7 frame has only {len(representatives)} eligible prompts")
    probability = N_ROWS / len(representatives)
    frame = [
        {
            **row,
            "prompt_representative": 1,
            "prompt_frame_count": len(representatives),
            "inclusion_probability": probability,
            "sampling_rank": rank,
            "selected": int(rank <= N_ROWS),
        }
        for rank, row in enumerate(representatives, start=1)
    ]
    selected = frame[:N_ROWS]
    for row in selected:
        row["topup_order"] = int(row["sampling_rank"])
    if len({row["prompt_id"] for row in selected}) != N_ROWS:
        raise AssertionError("T7 selected prompts are not unique")
    write_csv(SAMPLING_FRAME, frame)
    write_csv(SELECTION, selected)
    audit = {
        "status": "PASS",
        "spine_rows": len(admin),
        "far_below_eligible_clips_after_exclusion": len(eligible),
        "eligible_prompt_representatives": len(representatives),
        "selected_rows": len(selected),
        "selected_unique_prompts": len({row["prompt_id"] for row in selected}),
        "selected_unique_hashes": len({row["media_sha256"] for row in selected}),
        "request_mode_counts": dict(Counter(row["request_mode"] for row in selected)),
        "exclusion_set_sizes": {key: len(value) for key, value in exclusions.items()},
        "excluded_eligible_counts": dict(excluded_counts),
        "selected_overlap_detector_selection_promotion": len(
            {row["media_sha256"] for row in selected} & exclusions["detector_selection_promotion"]
        ),
        "selected_overlap_existing_judge_gold": len(
            {row["media_sha256"] for row in selected} & exclusions["existing_judge_gold"]
        ),
        "uniform_prompt_inclusion_probability": probability,
        "selection_seed": SELECTION_SEED,
        "topup_order_rule": "ascending frozen sampling_rank; consume until 23 additional decided human negatives",
        "far_below_ratio": FAR_BELOW_RATIO,
        "promoted_candidate": candidate,
        "negative_yield_basis": negative_yield_basis(),
    }
    SELECTION_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return selected, audit


def _link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _update_sha_manifest() -> None:
    absolute = str(ZIP_PATH.resolve())
    line = f"{sha256(ZIP_PATH)}  {absolute}"
    existing = SHA_PATH.read_text(encoding="utf-8").splitlines() if SHA_PATH.is_file() else []
    kept = [row for row in existing if row.strip() and not row.endswith("  " + absolute)]
    SHA_PATH.write_text("\n".join(kept + [line]) + "\n", encoding="utf-8")


def build_bundle(nonce: str) -> dict:
    if not nonce:
        raise ValueError("ADSR_BLINDING_NONCE is required")
    if BUNDLE_DIR.exists() or ZIP_PATH.exists() or ADMIN.exists():
        raise FileExistsError("T7 output already exists; refusing to overwrite")
    selected, audit = build_frame()
    BUNDLE_DIR.mkdir(parents=True)
    (BUNDLE_DIR / "media").mkdir()
    shuffled = sorted(
        selected, key=lambda row: nonce_key(nonce, row["canonical_clip_id"], "t7_shuffle")
    )
    public = []
    admin_rows = []
    for reveal_sequence, row in enumerate(shuffled, start=1):
        rating_id = "t7_" + nonce_key(
            nonce, row["canonical_clip_id"], "t7_rating_id"
        )[:20]
        source = Path(row["media_path"])
        destination = BUNDLE_DIR / "media" / f"audio_{rating_id}{source.suffix.lower()}"
        _link(source, destination)
        public.append(
            {
                "rating_id": rating_id,
                "media": f"media/{destination.name}",
                "request_mode": row["request_mode"],
            }
        )
        admin_rows.append(
            {
                "rating_id": rating_id,
                "canonical_clip_id": row["canonical_clip_id"],
                "record_id": row["record_id"],
                "prompt_id": row["prompt_id"],
                "media_path": row["media_path"],
                "media_sha256": row["media_sha256"],
                "request_mode": row["request_mode"],
                "requested_vocal": row["requested_vocal"],
                "demucs_score": row["demucs_score"],
                "panns_score": row["panns_score"],
                "promoted_present": row["promoted_present"],
                "score_to_threshold_ratio": row["score_to_threshold_ratio"],
                "source_family": row["source_family"],
                "eligibility_rule": row["eligibility_rule"],
                "inclusion_probability": row["inclusion_probability"],
                "selection_seed": SELECTION_SEED,
                "topup_order": row["topup_order"],
                "reveal_sequence": reveal_sequence,
                "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
                "rating_source_required": "pi:Richard",
            }
        )
    payload = {
        "bundle_id": BUNDLE_ID,
        "title": "T7 judge-gold negative top-up",
        "mode": "decisive_staged",
        "wording_html": f"<p><strong>Label A:</strong> {LABEL_A_WORDING}</p><p>{CHOIR_RULE}</p>",
        "rows": public,
    }
    html = render_html("T7 judge-gold negative top-up", payload)
    html = html.replace(
        'return /^(pi:[A-Za-z][A-Za-z0-9 ._-]{0,63}|human:CXY)$/.test(v)',
        'return v==="pi:Richard"',
    ).replace(
        "Enter one approved source once: <code>pi:&lt;name&gt;</code> or <code>human:CXY</code>.",
        "This bundle accepts only <code>pi:Richard</code>.",
    ).replace(
        "Use pi:&lt;name&gt; or human:CXY exactly.", "Use pi:Richard exactly."
    )
    if 'return v==="pi:Richard"' not in html:
        raise AssertionError("T7 rating-source restriction was not applied")
    (BUNDLE_DIR / "index.html").write_text(html, encoding="utf-8")
    (BUNDLE_DIR / "README").write_text(
        "T7: 40 blinded, hash-disjoint predicted-no-voice clips for judge-gold top-up.\n"
        "Rate Label A blind, reveal the instrumental request, then rate Label B; use pi:Richard exactly.\n"
        "Open index.html locally; export responses_Richard.json and its CSV backup when complete.\n",
        encoding="utf-8",
    )
    write_csv(ADMIN, admin_rows)
    make_zip(BUNDLE_DIR, ZIP_PATH)
    _update_sha_manifest()
    result = {
        **audit,
        "bundle_rows": len(public),
        "admin_rows": len(admin_rows),
        "media_files": len(list((BUNDLE_DIR / "media").iterdir())),
        "zip_path": str(ZIP_PATH),
        "zip_sha256": sha256(ZIP_PATH),
        "source_restricted_to": "pi:Richard",
    }
    return result


def audit_bundle() -> dict:
    import soundfile as sf

    visible = sorted(path.name for path in BUNDLE_DIR.iterdir())
    if visible != ["README", "index.html", "media"]:
        raise ValueError(f"unexpected T7 bundle files: {visible}")
    html = (BUNDLE_DIR / "index.html").read_text(encoding="utf-8")
    forbidden = ["expected_label", '"bucket"', '"arm"', '"set_name"']
    leaked = [token for token in forbidden if token in html.lower()]
    rows = read_csv(ADMIN)
    media = list((BUNDLE_DIR / "media").iterdir())
    if leaked or len(rows) != N_ROWS or len(media) != N_ROWS:
        raise ValueError(f"T7 leak/cardinality audit failed: leaked={leaked}")
    if "Reveal request" not in html or "label_a_amended" not in html:
        raise ValueError("T7 staged reveal controls missing")
    if 'return v==="pi:Richard"' not in html:
        raise ValueError("T7 rating source is not restricted")
    if len((BUNDLE_DIR / "README").read_text(encoding="utf-8").splitlines()) != 3:
        raise ValueError("T7 README must have exactly three lines")
    for row in rows:
        source = Path(row["media_path"])
        bundled = BUNDLE_DIR / "media" / f"audio_{row['rating_id']}{source.suffix.lower()}"
        if not bundled.is_file() or sha256(bundled) != row["media_sha256"]:
            raise ValueError(f"T7 media checksum mismatch: {row['rating_id']}")
        info = sf.info(str(bundled))
        if not info.samplerate or info.frames / info.samplerate <= 1:
            raise ValueError(f"T7 media decode/duration failure: {row['rating_id']}")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        names = archive.namelist()
    if len(names) != N_ROWS + 2:
        raise ValueError(f"T7 zip member count changed: {len(names)}")
    if sha256(ZIP_PATH) not in SHA_PATH.read_text(encoding="utf-8"):
        raise ValueError("T7 ZIP checksum is absent from SHA256SUMS")
    return {
        "status": "PASS",
        "rows": len(rows),
        "media": len(media),
        "leak_test": "PASS",
        "staged_reveal": "PASS",
        "source_restriction": "PASS",
        "zip_members": len(names),
        "zip_sha256": sha256(ZIP_PATH),
    }


def write_report(build: dict, audit: dict) -> None:
    basis = build["negative_yield_basis"]
    REPORT.write_text(
        "# T7 Judge-Gold Negative Package\n\n"
        "`T7_PACKAGE_STATUS = READY`\n\n"
        f"- Presentations: {build['bundle_rows']} blinded, unique clips from {build['selected_unique_prompts']} unique prompts.\n"
        "- Request mode: 40 instrumental. Label A is completed blind; the request and matching Label-B rule are revealed afterward.\n"
        f"- Sampling frame: {build['eligible_prompt_representatives']} far-below-threshold predicted-no-voice prompt representatives.\n"
        f"- Uniform prompt-level inclusion probability: {build['uniform_prompt_inclusion_probability']:.8f}.\n"
        "- Count-only top-up order: ascending frozen sampling rank; consume rows until 23 additional decided human negatives are reached.\n"
        f"- Detector-selection/promotion hash overlap: {build['selected_overlap_detector_selection_promotion']}.\n"
        f"- Existing judge-gold hash overlap: {build['selected_overlap_existing_judge_gold']}.\n"
        f"- Yield basis: {basis['t6_predicted_absent_human_no']}/{basis['t6_predicted_absent_decided']} prior T6 predicted-absent clips were human `no`.\n"
        f"- Conservative expected T7 negatives from the Wilson 95% lower bound: {basis['t7_conservative_expected_negatives']:.2f}/40; point expectation {basis['t7_point_expected_negatives']:.2f}/40.\n"
        "- Frozen target: at least 23 decided negatives; oversampling is expected to clear it with margin.\n"
        f"- Bundle audit: `{audit['status']}`; leak/staged-reveal/source checks all PASS.\n"
        f"- ZIP: `{ZIP_PATH}`.\n"
        f"- ZIP SHA-256: `{audit['zip_sha256']}`.\n\n"
        "## Start\n\n"
        f"Open `{BUNDLE_DIR / 'index.html'}` in a browser, enter `pi:Richard`, and complete all 40 rows.\n",
        encoding="utf-8",
    )


def run(nonce: str) -> dict:
    build = build_bundle(nonce)
    audit = audit_bundle()
    write_report(build, audit)
    return {
        "T7_PACKAGE_STATUS": "READY",
        "bundle_dir": str(BUNDLE_DIR),
        "zip_path": str(ZIP_PATH),
        "zip_sha256": audit["zip_sha256"],
        "selection_audit": str(SELECTION_AUDIT),
        "admin": str(ADMIN),
        "report": str(REPORT),
        "expected_negatives_point": build["negative_yield_basis"]["t7_point_expected_negatives"],
        "expected_negatives_conservative": build["negative_yield_basis"]["t7_conservative_expected_negatives"],
    }


if __name__ == "__main__":
    print(json.dumps(run(os.environ.get("ADSR_BLINDING_NONCE", "")), indent=2, sort_keys=True))
