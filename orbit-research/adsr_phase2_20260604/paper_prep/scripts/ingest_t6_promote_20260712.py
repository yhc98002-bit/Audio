#!/usr/bin/env python3
"""Ingest the t6 PI ratings, gate on reliability, then run frozen W2 promotion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
OUT = PAPER / "autochain_20260712"
RATINGS = PAPER / "pi_ratings_20260712/t6_calibration_torch251_recovery.json"
ADMIN = PAPER / "rater_admin_keys_20260712/t6_calibration_torch251_recovery/T6_CALIBRATION_ADMIN.csv"
SELECTION = PAPER / "w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_MANIFEST.csv"
BUNDLE_HTML = PAPER / "rater_bundles_20260712/t6_calibration_torch251_recovery/index.html"
BUNDLE_REPORT = PAPER / "w2_execution_20260712/calibration_torch251_recovery/T6_CALIBRATION_PACK_REPORT.md"
AMENDMENT = PAPER / "W2_AMENDMENT_20260712.md"
PROMOTION_SCRIPT = PAPER / "scripts/w2_promotion_pipeline_20260712.py"

INGEST_AUDIT = OUT / "T6_INGEST_AUDIT.json"
OFFICIAL_RATINGS = OUT / "T6_OFFICIAL_RATINGS.csv"
RELIABILITY_JSON = OUT / "T6_RELIABILITY_RESULT.json"
RELIABILITY_REPORT = OUT / "T6_RELIABILITY_REPORT.md"
TRAIN_SELECTION = OUT / "T6_TRAIN_SELECTION.json"
PROMOTION_RESULT = OUT / "T6_PROMOTION_RESULT.json"
PROMOTION_REPORT = OUT / "T6_PROMOTION_REPORT.md"
HELDOUT_EXPOSURE = OUT / "T6_HELDOUT_EXPOSURE_RECORD.json"
ESCALATION = OUT / "T6_PROMOTION_ESCALATION.md"

EXPECTED_BUNDLE = "t6_calibration_torch251_recovery"
EXPECTED_SOURCE = "pi:Richard"
REQUIRED_FIELDS = (
    "rating_id",
    "rating_source",
    "label_a_voice_presence",
    "perceived_vocal_type",
    "vocal_extent",
    "request_mode",
    "label_b_constraint",
    "reveal_sequence",
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROMOTION = load_module(PROMOTION_SCRIPT, "w2_promotion_pipeline_20260712_autochain")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _kappa(left: list[str], right: list[str]) -> dict:
    if len(left) != len(right) or not left:
        raise ValueError("kappa inputs must be non-empty and aligned")
    labels = sorted(set(left) | set(right))
    count_left = Counter(left)
    count_right = Counter(right)
    n = len(left)
    observed = sum(a == b for a, b in zip(left, right)) / n
    expected = sum((count_left[label] / n) * (count_right[label] / n) for label in labels)
    value = (observed - expected) / (1 - expected) if expected < 1 else (1.0 if observed == 1 else math.nan)
    return {
        "rows": n,
        "exact_agreement_count": sum(a == b for a, b in zip(left, right)),
        "exact_agreement": observed,
        "cohen_kappa": value,
        "parent_counts": dict(count_left),
        "repeat_counts": dict(count_right),
    }


def validate_export() -> tuple[dict, list[dict], list[dict], dict]:
    payload = json.loads(RATINGS.read_text(encoding="utf-8"))
    if payload.get("bundle_id") != EXPECTED_BUNDLE:
        raise ValueError("unexpected t6 bundle ID")
    if payload.get("rating_source") != EXPECTED_SOURCE:
        raise ValueError("t6 top-level provenance is not pi:Richard")
    ratings = payload.get("responses")
    if not isinstance(ratings, list) or len(ratings) != 201:
        raise ValueError("t6 export must contain exactly 201 responses")
    admin = read_csv(ADMIN)
    if len(admin) != 201:
        raise ValueError("t6 admin must contain exactly 201 rows")
    rating_ids = [str(row.get("rating_id", "")) for row in ratings]
    admin_ids = [row["rating_id"] for row in admin]
    if len(set(rating_ids)) != 201 or set(rating_ids) != set(admin_ids):
        raise ValueError("t6 export/admin ID sets do not match exactly")
    admin_by_id = {row["rating_id"]: row for row in admin}

    blanks = Counter()
    for row in ratings:
        for field in REQUIRED_FIELDS:
            if str(row.get(field, "")).strip() == "":
                blanks[field] += 1
        if row.get("rating_source") != EXPECTED_SOURCE:
            raise ValueError(f"invalid t6 row provenance: {row.get('rating_id')}")
        if row.get("label_a_voice_presence") not in {"yes", "no", "unsure"}:
            raise ValueError(f"invalid Label-A value: {row.get('rating_id')}")
        if row.get("label_b_constraint") not in {"satisfied", "violated", "unsure"}:
            raise ValueError(f"invalid Label-B value: {row.get('rating_id')}")
        admin_row = admin_by_id[row["rating_id"]]
        if row.get("request_mode") != admin_row["request_mode"]:
            raise ValueError(f"request mode disagrees with keys-side admin: {row['rating_id']}")
    if blanks:
        raise ValueError(f"blank required t6 answer fields: {dict(blanks)}")

    reveal = [int(row["reveal_sequence"]) for row in ratings]
    if len(set(reveal)) != 201 or min(reveal) < 1:
        raise ValueError("t6 reveal sequences must be unique positive integers")
    html = BUNDLE_HTML.read_text(encoding="utf-8")
    required_invariants = (
        "reveal_enabled:labelAComplete(response)&&!revealed",
        "label_b_enabled:revealed",
        "label_a_enabled:!revealed||Boolean(response.label_a_editing)",
        "response.label_a_amended=true",
    )
    if any(token not in html for token in required_invariants):
        raise ValueError("t6 staged-reveal UI invariants are missing")
    if "Staged Label-A, request reveal, then Label-B flow: PASS" not in BUNDLE_REPORT.read_text(encoding="utf-8"):
        raise ValueError("t6 package staged-reveal audit is absent")

    audit = {
        "status": "PASS",
        "bundle_id": EXPECTED_BUNDLE,
        "rows": len(ratings),
        "exact_id_set_match": True,
        "unique_ids": len(set(rating_ids)),
        "rating_source": EXPECTED_SOURCE,
        "required_answer_blanks": 0,
        "optional_confidence_missing": sum(
            str(row.get("confidence_1_to_5", "")).strip() == "" for row in ratings
        ),
        "optional_notes_missing": sum(str(row.get("notes", "")).strip() == "" for row in ratings),
        "request_mode_matches_admin": True,
        "reveal_sequences_unique_positive": True,
        "staged_reveal_verification": "PASS_UI_INVARIANT_PLUS_REVEAL_SEQUENCE",
        "staged_reveal_export_limitation": "Label-A/B answer timestamps are not exported; order is verified from fail-closed UI invariants plus per-row reveal_sequence",
        "input_sha256": sha256_file(RATINGS),
        "admin_sha256": sha256_file(ADMIN),
        "role_counts": dict(Counter(row["role"] for row in admin)),
    }
    return payload, ratings, admin, audit


def score_reliability(ratings: list[dict], admin: list[dict]) -> dict:
    by_rating = {row["rating_id"]: row for row in ratings}
    repeats = [row for row in admin if row["role"] == "repeat"]
    if len(repeats) != 20:
        raise ValueError(f"expected 20 hidden repeats, found {len(repeats)}")
    parent_rows = []
    repeat_rows = []
    details = []
    for repeat in repeats:
        parent = by_rating.get(repeat["repeat_parent_rating_id"])
        child = by_rating.get(repeat["rating_id"])
        if parent is None or child is None:
            raise ValueError(f"missing hidden-repeat pair for {repeat['rating_id']}")
        parent_rows.append(parent)
        repeat_rows.append(child)
        details.append(
            {
                "parent_rating_id": repeat["repeat_parent_rating_id"],
                "repeat_rating_id": repeat["rating_id"],
                "label_a_parent": parent["label_a_voice_presence"],
                "label_a_repeat": child["label_a_voice_presence"],
                "label_b_parent": parent["label_b_constraint"],
                "label_b_repeat": child["label_b_constraint"],
                "label_a_exact": parent["label_a_voice_presence"] == child["label_a_voice_presence"],
                "label_b_exact": parent["label_b_constraint"] == child["label_b_constraint"],
                "satisfied_violated_reversal": {
                    parent["label_b_constraint"], child["label_b_constraint"]
                }
                == {"satisfied", "violated"},
            }
        )
    label_a = _kappa(
        [row["label_a_voice_presence"] for row in parent_rows],
        [row["label_a_voice_presence"] for row in repeat_rows],
    )
    label_b = _kappa(
        [row["label_b_constraint"] for row in parent_rows],
        [row["label_b_constraint"] for row in repeat_rows],
    )
    reversals = sum(row["satisfied_violated_reversal"] for row in details)
    passed = label_b["exact_agreement"] >= 0.85 and reversals <= 2
    return {
        "RELIABILITY_STATUS": "PASS" if passed else "FAIL_ESCALATED",
        "label_a": label_a,
        "label_b": label_b,
        "satisfied_violated_reversals": reversals,
        "minimum_label_b_exact_agreement": 0.85,
        "maximum_satisfied_violated_reversals": 2,
        "reliability_scored_before_training_labels_exposed": True,
        "details": details,
    }


def write_reliability_report(audit: dict, result: dict) -> None:
    RELIABILITY_REPORT.write_text(
        "# T6 Reliability Report\n\n"
        f"`RELIABILITY_STATUS = {result['RELIABILITY_STATUS']}`\n\n"
        f"- Export/admin exact ID match: 201/201.\n"
        f"- Provenance: `{EXPECTED_SOURCE}`.\n"
        f"- Required answer blanks: {audit['required_answer_blanks']}.\n"
        f"- Optional confidence annotations missing: {audit['optional_confidence_missing']}/201.\n"
        f"- Staged reveal: `{audit['staged_reveal_verification']}`.\n"
        "- Export limitation: the UI does not export Label-A/B answer timestamps; order is\n"
        "  verified through the fail-closed UI state machine and each row's reveal event.\n\n"
        "| Construct | Exact | Agreement | Cohen's kappa |\n"
        "|---|---:|---:|---:|\n"
        f"| Label A | {result['label_a']['exact_agreement_count']}/20 | "
        f"{result['label_a']['exact_agreement']:.6f} | {result['label_a']['cohen_kappa']:.6f} |\n"
        f"| Label B | {result['label_b']['exact_agreement_count']}/20 | "
        f"{result['label_b']['exact_agreement']:.6f} | {result['label_b']['cohen_kappa']:.6f} |\n\n"
        f"Satisfied-to-violated or violated-to-satisfied reversals: "
        f"{result['satisfied_violated_reversals']}/20.\n\n"
        "Reliability was computed and written before train or held-out labels were\n"
        "joined to instrument scores.\n",
        encoding="utf-8",
    )


def _add_prompt_ids(rows: list[dict]) -> None:
    selection = read_csv(SELECTION)
    prompt_by_clip = {}
    for row in selection:
        prompt_by_clip.setdefault(row["canonical_clip_id"], row["prompt_id"])
    for row in rows:
        row["prompt_id"] = prompt_by_clip.get(row["canonical_clip_id"], "appendix")


def _unweighted_metrics(rows: list[dict], selected: dict) -> tuple[dict, dict]:
    copied = [{**row, "design_weight": 1.0} for row in rows]
    predicted = PROMOTION.predictions(
        copied,
        selected["family"],
        selected["demucs_threshold"],
        selected["panns_threshold"],
    )
    metrics = PROMOTION.weighted_metrics(copied, predicted)
    intervals = PROMOTION.stratified_bootstrap_lcbs(
        copied,
        selected["family"],
        selected["demucs_threshold"],
        selected["panns_threshold"],
        replicates=10_000,
        seed=20260713,
    )
    return metrics, intervals


def transport_audit(rows: list[dict], selected: dict, heldout_ba: float) -> dict:
    transport = [row for row in rows if row["role"] == "transport"]
    if len(transport) != 20:
        raise ValueError("transport audit requires exactly 20 rows")

    def evaluate(group: list[dict]) -> dict:
        predicted = PROMOTION.predictions(
            group,
            selected["family"],
            selected["demucs_threshold"],
            selected["panns_threshold"],
        )
        metrics = PROMOTION.weighted_metrics(group, predicted)
        delta = metrics["balanced_accuracy"] - heldout_ba
        return {
            "metrics": metrics,
            "delta_balanced_accuracy_vs_heldout": delta,
            "absolute_delta_gt_0p10": bool(abs(delta) > 0.10),
            "source_specific_correction_flag": bool(abs(delta) > 0.10),
        }

    overall = evaluate(transport)
    by_source = {}
    for source in ("N2", "Stage3", "Batch3_keep"):
        group = [row for row in transport if row["source_family"] == source]
        try:
            by_source[source] = evaluate(group)
        except (ValueError, ZeroDivisionError):
            by_source[source] = {
                "rows": len(group),
                "status": "NOT_ESTIMABLE_BOTH_CLASSES_NOT_PRESENT",
                "source_specific_correction_flag": True,
            }
    return {
        "rows": len(transport),
        "overall": overall,
        "by_source": by_source,
        "any_source_specific_correction_flag": bool(
            overall["source_specific_correction_flag"]
            or any(value.get("source_specific_correction_flag", False) for value in by_source.values())
        ),
        "rule": "absolute balanced-accuracy delta > 0.10 versus held-out",
    }


def run_promotion(ratings: list[dict], admin: list[dict], reliability_result: dict) -> dict:
    rows = PROMOTION.join_rows(admin, ratings)
    _add_prompt_ids(rows)
    train = [row for row in rows if row["role"] == "train"]
    heldout = [row for row in rows if row["role"] == "heldout"]
    selection = PROMOTION.select_candidate(train)
    write_json(TRAIN_SELECTION, selection)

    exposure_identity = {
        "ratings_sha256": sha256_file(RATINGS),
        "admin_sha256": sha256_file(ADMIN),
        "heldout_rating_ids_sha256": hashlib.sha256(
            "\n".join(sorted(row["rating_id"] for row in heldout)).encode()
        ).hexdigest(),
        "heldout_rows": len(heldout),
        "evaluation_count": 1,
        "status": "EXPOSED_ONCE",
    }
    if HELDOUT_EXPOSURE.exists():
        prior = json.loads(HELDOUT_EXPOSURE.read_text(encoding="utf-8"))
        if prior != exposure_identity or not PROMOTION_RESULT.exists():
            raise ValueError("held-out exposure record conflicts with current inputs")
        return json.loads(PROMOTION_RESULT.read_text(encoding="utf-8"))
    write_json(HELDOUT_EXPOSURE, exposure_identity)

    heldout_result = PROMOTION.evaluate_heldout(
        heldout,
        selection,
        reliability_result,
        bootstrap_replicates=10_000,
        bootstrap_seed=20260712,
    )
    if heldout_result["mechanical_promotion_gate"] == "NOT_RUN_TOPUP_REQUIRED":
        status = "BLOCKED_CLASS_COUNT_TOPUP_REQUIRED"
        transport = {"status": "BLOCKED_UNTIL_TOPUP"}
        unweighted = {"status": "BLOCKED_UNTIL_TOPUP"}
    else:
        selected = selection["selected_candidate"]
        unweighted_metrics, unweighted_intervals = _unweighted_metrics(heldout, selected)
        unweighted = {"metrics": unweighted_metrics, "bootstrap": unweighted_intervals}
        transport = transport_audit(
            rows, selected, heldout_result["heldout_metrics"]["balanced_accuracy"]
        )
        status = (
            "PROMOTED"
            if heldout_result["mechanical_promotion_gate"] == "PASS"
            else "SENSITIVITY_ONLY"
        )
    output = {
        "CORRECTED_INSTRUMENT_STATUS": status,
        "amendment_signature_status": (
            "SIGNED_BY_BOTH_PIS"
            if PROMOTION._amendment_has_two_signatures(AMENDMENT)
            else "DRAFTED_AWAITING_SIGNATURE"
        ),
        "plan_or_claim_status_changed": False,
        "ratings_sha256": sha256_file(RATINGS),
        "admin_sha256": sha256_file(ADMIN),
        "reliability": reliability_result,
        "train_selection": selection,
        "heldout": heldout_result,
        "unweighted_sanity": unweighted,
        "transport": transport,
        "topup_applied": False,
        "topup_note": (
            "no top-up needed"
            if heldout_result["mechanical_promotion_gate"] != "NOT_RUN_TOPUP_REQUIRED"
            else "frozen reserve ratings are required in committed order"
        ),
        "adoption_status": "BLOCKED_UNTIL_BOTH_W2_SIGNATURES",
    }
    write_json(PROMOTION_RESULT, output)
    return output


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "NA" if not math.isfinite(number) else f"{number:.6f}"


def write_promotion_report(result: dict) -> None:
    heldout = result["heldout"]
    selected = result["train_selection"]["selected_candidate"]
    lines = [
        "# T6 Corrected-Instrument Promotion Report",
        "",
        f"`CORRECTED_INSTRUMENT_STATUS = {result['CORRECTED_INSTRUMENT_STATUS']}`",
        "",
        f"- Selected family: `{selected['family']}`.",
        f"- Demucs threshold: `{selected['demucs_threshold']}`.",
        f"- PANNs threshold: `{selected['panns_threshold']}`.",
        f"- Candidate count searched on train only: {result['train_selection']['candidate_count']}.",
        f"- Amendment signatures: `{result['amendment_signature_status']}`.",
        "- PLAN/CLAIMS changed: `false`.",
        "",
    ]
    if heldout["mechanical_promotion_gate"] == "NOT_RUN_TOPUP_REQUIRED":
        lines.extend(
            [
                "## Class-Count Top-Up",
                "",
                f"- Decided positives: {heldout['heldout_decided_positive_rows']}.",
                f"- Decided negatives: {heldout['heldout_decided_negative_rows']}.",
                f"- Positive top-up needed: {heldout['topup_needed_positive']}.",
                f"- Negative top-up needed: {heldout['topup_needed_negative']}.",
                "- Promotion metrics remain unexposed until the frozen reserve is rated.",
            ]
        )
    else:
        metrics = heldout["heldout_metrics"]
        bootstrap = heldout["bootstrap"]["metrics"]
        sanity = result["unweighted_sanity"]
        lines.extend(
            [
                "## Held-Out Evaluation",
                "",
                f"Held-out labels were exposed once after reliability and train selection. "
                f"Decided positives: {metrics['positive_rows']}; decided negatives: "
                f"{metrics['negative_rows']}; abstentions: {metrics['abstention_rows']}.",
                "",
                "| Metric | Design-weighted point | One-sided 95% LCB | Unweighted point | Unweighted LCB | Required point / LCB |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for metric, minimum in PROMOTION.METRIC_MINIMUMS.items():
            lines.append(
                f"| `{metric}` | {_fmt(metrics[metric])} | "
                f"{_fmt(bootstrap[metric]['one_sided_95_lcb'])} | "
                f"{_fmt(sanity['metrics'][metric])} | "
                f"{_fmt(sanity['bootstrap']['metrics'][metric]['one_sided_95_lcb'])} | "
                f"{minimum:.2f} |"
            )
        lines.extend(
            [
                "",
                "## Mechanical Conditions",
                "",
                *[f"- `{key}`: `{str(value).lower()}`." for key, value in heldout["checks"].items()],
                "",
                "## Transport Audit",
                "",
                f"- Rows: {result['transport']['rows']}.",
                f"- Overall balanced-accuracy delta versus held-out: "
                f"{_fmt(result['transport']['overall']['delta_balanced_accuracy_vs_heldout'])}.",
                f"- Any source-specific correction flag: "
                f"`{str(result['transport']['any_source_specific_correction_flag']).lower()}`.",
            ]
        )
        for source, value in result["transport"]["by_source"].items():
            if "metrics" in value:
                lines.append(
                    f"- {source}: BA {_fmt(value['metrics']['balanced_accuracy'])}; "
                    f"delta {_fmt(value['delta_balanced_accuracy_vs_heldout'])}; "
                    f"flag `{str(value['source_specific_correction_flag']).lower()}`."
                )
            else:
                lines.append(f"- {source}: `{value['status']}`; correction flag `true`.")
    lines.extend(
        [
            "",
            "This result is mechanical. Publication adoption and any direct PLAN/CLAIMS",
            "update remain blocked until both W2 adoption signatures are recorded.",
            "",
        ]
    )
    PROMOTION_REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_escalation(result: dict) -> None:
    ESCALATION.write_text(
        "# T6 Promotion Escalation\n\n"
        f"`CORRECTED_INSTRUMENT_STATUS = {result['CORRECTED_INSTRUMENT_STATUS']}`\n\n"
        f"Amendment signature state: `{result['amendment_signature_status']}`.\n\n"
        "No PLAN.md or CLAIMS.md adoption was applied. If the instrument is promoted,\n"
        "both W2 adoption signatures are still required before applying the prepared\n"
        "supersession drafts. If it is sensitivity-only, frozen headline numbers stand\n"
        "and every recompute remains explicitly sensitivity-labeled.\n",
        encoding="utf-8",
    )


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    _payload, ratings, admin, ingest = validate_export()
    write_csv(OFFICIAL_RATINGS, ratings)
    write_json(INGEST_AUDIT, ingest)

    rel = score_reliability(ratings, admin)
    write_json(RELIABILITY_JSON, rel)
    write_reliability_report(ingest, rel)
    if rel["RELIABILITY_STATUS"] != "PASS":
        (OUT / "T6_CLARIFICATION_RERATE_BLOCK.md").write_text(
            "# T6 Clarification And Rerate Block\n\n"
            "`RELIABILITY_STATUS = FAIL_ESCALATED`\n\n"
            "Clarify Label B using the signed amendment, rebuild only the hidden-repeat\n"
            "block, and rerate before exposing train or held-out labels.\n",
            encoding="utf-8",
        )
        return {"RELIABILITY_STATUS": "FAIL_ESCALATED", "CORRECTED_INSTRUMENT_STATUS": "BLOCKED_RELIABILITY_FAIL"}

    promotion = run_promotion(ratings, admin, {
        "status": "PASS",
        "repeat_pairs": 20,
        "exact_agreement_count": rel["label_b"]["exact_agreement_count"],
        "exact_agreement": rel["label_b"]["exact_agreement"],
        "satisfied_violated_reversals": rel["satisfied_violated_reversals"],
    })
    write_promotion_report(promotion)
    write_escalation(promotion)
    return {
        "RELIABILITY_STATUS": rel["RELIABILITY_STATUS"],
        "CORRECTED_INSTRUMENT_STATUS": promotion["CORRECTED_INSTRUMENT_STATUS"],
        "outputs": {
            "ingest": str(INGEST_AUDIT),
            "reliability": str(RELIABILITY_REPORT),
            "promotion": str(PROMOTION_REPORT),
            "promotion_json": str(PROMOTION_RESULT),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
