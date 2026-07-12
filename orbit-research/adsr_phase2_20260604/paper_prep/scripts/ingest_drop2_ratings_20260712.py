#!/usr/bin/env python3
"""Validate and score the 2026-07-12 t3/t4/t5 PI rating drop."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
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

from rating_provenance import require_human_source  # noqa: E402
from validation_gate_v2 import (  # noqa: E402
    exact_binom_less_equal,
    normalize_preference,
    wilson,
)


INPUT_DIR = PAPER / "pi_ratings_20260712"
PROCESSED = INPUT_DIR / "processed"
KEYS = PAPER / "rater_admin_keys_20260711"
B_KEYS = KEYS / "t3_t4_bprime"
SA3_KEYS = KEYS / "t5_sa3_calibration"
T3_INPUT = INPUT_DIR / "t3_bprime_primary_v2.json"
T4_INPUT = INPUT_DIR / "t4_bprime_reverse_v2.json"
T5_INPUT = INPUT_DIR / "t5_sa3_calibration.json"
T3_KEY = B_KEYS / "T3_BUNDLE_KEY_V2.csv"
T4_KEY = B_KEYS / "T4_BUNDLE_KEY_V2.csv"
T5_KEY = SA3_KEYS / "T5_BUNDLE_KEY.csv"
PAIR_ADMIN = B_KEYS / "B_PRIME_PAIR_ADMIN.csv"
ORDERED_ADMIN = B_KEYS / "B_PRIME_ORDERED_ADMIN.csv"
SA3_ADMIN = SA3_KEYS / "SA3_LABEL_CALIBRATION_ADMIN.csv"
B_REPORT = PAPER / "validation_B_prime/B_PRIME_GATE_REPORT_20260712.md"
B_RESULT = PAPER / "validation_B_prime/B_PRIME_GATE_RESULT_20260712.json"
T4_REPORT = PROCESSED / "T4_ORDER_BIAS_AND_RELIABILITY_REPORT_20260712.md"
T4_RESULT = PROCESSED / "T4_ORDER_BIAS_AND_RELIABILITY_RESULT_20260712.json"
SA3_REPORT = PROCESSED / "SA3_LABEL_CALIBRATION_REPORT_20260712.md"
SA3_RESULT = PROCESSED / "SA3_LABEL_CALIBRATION_RESULT_20260712.json"
INGEST_AUDIT = PROCESSED / "DROP2_INGEST_AUDIT.json"
STUDY_LOG = INPUT_DIR / "DROP2_STUDY_LOG.jsonl"
AMENDMENT_APPENDIX = PAPER / "HUMAN_STUDY_CRITERIA_AMENDMENT_20260709_APPENDIX_20260712.md"

ENDPOINTS = (
    "quality_preference",
    "overall_preference",
    "constraint_preference",
)
PREFERENCE_VALUES = {"a", "b", "tie", "unsure"}
PI_SOURCE = "pi:Richard"
SCORE_Z_ONE_SIDED_95 = 1.6448536269514722


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
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(dt.timezone.utc)


def _required(row: dict, fields: tuple[str, ...], context: str) -> None:
    blanks = [field for field in fields if str(row.get(field, "")).strip() == ""]
    if blanks:
        raise ValueError(f"blank required fields for {context}: {blanks}")


def _load_export(path: Path, expected_bundle: str) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("bundle_id") != expected_bundle:
        raise ValueError(f"unexpected bundle_id in {path}")
    if payload.get("rating_source") != PI_SOURCE:
        raise ValueError(f"top-level rating_source must be {PI_SOURCE} in {path}")
    require_human_source(payload["rating_source"])
    parse_timestamp(str(payload.get("exported_at", "")))
    rows = payload.get("responses")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"responses must be a non-empty list in {path}")
    return payload, [dict(row) for row in rows]


def _validate_key(key_path: Path, expected_bundle: str) -> list[dict[str, str]]:
    rows = read_csv(key_path)
    if not rows:
        raise ValueError(f"empty bundle key: {key_path}")
    required = {"bundle_rating_id", "scorer_rating_id", "bundle_name"}
    if not required.issubset(rows[0]):
        raise ValueError(f"invalid bundle key schema: {key_path}")
    if any(row["bundle_name"] != expected_bundle for row in rows):
        raise ValueError(f"bundle-name mismatch in {key_path}")
    bundle_ids = [row["bundle_rating_id"] for row in rows]
    scorer_ids = [row["scorer_rating_id"] for row in rows]
    if len(bundle_ids) != len(set(bundle_ids)) or len(scorer_ids) != len(set(scorer_ids)):
        raise ValueError(f"duplicate IDs in {key_path}")
    return rows


def validate_and_remap_pair_export(
    input_path: Path,
    key_path: Path,
    expected_bundle: str,
    expected_rows: int,
) -> tuple[dict, list[dict], dict]:
    payload, rows = _load_export(input_path, expected_bundle)
    keys = _validate_key(key_path, expected_bundle)
    if len(rows) != expected_rows or len(keys) != expected_rows:
        raise ValueError(
            f"{expected_bundle} cardinality mismatch: responses={len(rows)}, keys={len(keys)}"
        )
    key_by_bundle = {row["bundle_rating_id"]: row for row in keys}
    incoming = [str(row.get("rating_id", "")).strip() for row in rows]
    if len(incoming) != len(set(incoming)) or set(incoming) != set(key_by_bundle):
        raise ValueError(f"{expected_bundle} does not exactly match its bundle key IDs")

    official = []
    sequence_anomalies = []
    for row in rows:
        rating_id = row["rating_id"]
        _required(
            row,
            (
                "rating_id",
                "rating_source",
                "quality_preference",
                "overall_preference",
                "constraint_preference",
                "confidence_1_to_5",
                "request_mode",
                "request_revealed",
                "quality_answer_sequence",
                "reveal_sequence",
                "constraint_answer_sequence",
                "overall_answer_sequence",
            ),
            rating_id,
        )
        if row["rating_source"] != PI_SOURCE:
            raise ValueError(f"row rating_source must be {PI_SOURCE}: {rating_id}")
        require_human_source(row["rating_source"])
        normalized = {endpoint: normalize_preference(str(row[endpoint])) for endpoint in ENDPOINTS}
        if any(value not in PREFERENCE_VALUES for value in normalized.values()):
            raise ValueError(f"invalid preference in {rating_id}")
        confidence = int(row["confidence_1_to_5"])
        if not 1 <= confidence <= 5:
            raise ValueError(f"confidence outside 1-5 in {rating_id}")
        key = key_by_bundle[rating_id]
        request_mode = str(row["request_mode"]).strip().lower()
        if request_mode not in {"vocal", "instrumental"}:
            raise ValueError(f"invalid request_mode in {rating_id}")
        if key.get("request_mode", request_mode) != request_mode:
            raise ValueError(f"request_mode disagrees with keys-side manifest in {rating_id}")
        if str(row["request_revealed"]).strip().lower() not in {"true", "1"}:
            raise ValueError(f"request was not revealed in {rating_id}")
        sequences = {
            field: int(row[field])
            for field in (
                "quality_answer_sequence",
                "reveal_sequence",
                "constraint_answer_sequence",
                "overall_answer_sequence",
            )
        }
        if not (
            sequences["quality_answer_sequence"] < sequences["reveal_sequence"]
            and sequences["reveal_sequence"] < sequences["constraint_answer_sequence"]
            and sequences["reveal_sequence"] < sequences["overall_answer_sequence"]
        ):
            raise ValueError(f"staged-reveal order failed in {rating_id}")
        if sequences["constraint_answer_sequence"] > sequences["overall_answer_sequence"]:
            sequence_anomalies.append(
                {
                    "bundle_rating_id": rating_id,
                    "scorer_rating_id": key["scorer_rating_id"],
                    **sequences,
                }
            )
        official.append(
            {
                **row,
                "bundle_rating_id": rating_id,
                "rating_id": key["scorer_rating_id"],
                "rating_source": PI_SOURCE,
                "exported_at": payload["exported_at"],
                **normalized,
            }
        )
    return payload, official, {
        "bundle_id": expected_bundle,
        "rows": len(rows),
        "exact_id_set_match": True,
        "rating_source": PI_SOURCE,
        "required_answer_blanks": 0,
        "sequence_anomalies_constraint_after_overall": sequence_anomalies,
        "input_sha256": sha256_file(input_path),
        "key_sha256": sha256_file(key_path),
    }


def validate_and_remap_t5() -> tuple[dict, list[dict], dict]:
    payload, rows = _load_export(T5_INPUT, "t5_sa3_calibration")
    keys = _validate_key(T5_KEY, "t5_sa3_calibration")
    if len(rows) != 60 or len(keys) != 60:
        raise ValueError(f"t5 cardinality mismatch: responses={len(rows)}, keys={len(keys)}")
    key_by_bundle = {row["bundle_rating_id"]: row for row in keys}
    incoming = [str(row.get("rating_id", "")).strip() for row in rows]
    if len(incoming) != len(set(incoming)) or set(incoming) != set(key_by_bundle):
        raise ValueError("t5 does not exactly match its bundle key IDs")
    official = []
    missing_confidence = 0
    for row in rows:
        rating_id = row["rating_id"]
        _required(row, ("rating_id", "rating_source", "label_a_voice_presence"), rating_id)
        if row["rating_source"] != PI_SOURCE:
            raise ValueError(f"row rating_source must be {PI_SOURCE}: {rating_id}")
        require_human_source(row["rating_source"])
        label = str(row["label_a_voice_presence"]).strip().lower()
        if label not in {"yes", "no", "unsure"}:
            raise ValueError(f"invalid t5 Label A in {rating_id}: {label!r}")
        confidence_raw = str(row.get("confidence_1_to_5", "")).strip()
        if confidence_raw:
            confidence = int(confidence_raw)
            if not 1 <= confidence <= 5:
                raise ValueError(f"t5 confidence outside 1-5 in {rating_id}")
        else:
            missing_confidence += 1
        key = key_by_bundle[rating_id]
        official.append(
            {
                **row,
                "bundle_rating_id": rating_id,
                "blind_id": key["scorer_rating_id"],
                "rating_source": PI_SOURCE,
                "label_a_voice_presence": label,
                "exported_at": payload["exported_at"],
            }
        )
    return payload, official, {
        "bundle_id": "t5_sa3_calibration",
        "rows": len(rows),
        "exact_id_set_match": True,
        "rating_source": PI_SOURCE,
        "required_answer_blanks": 0,
        "optional_confidence_missing": missing_confidence,
        "input_sha256": sha256_file(T5_INPUT),
        "key_sha256": sha256_file(T5_KEY),
    }


def exact_binomial_lower(k: int, n: int, alpha: float = 0.05) -> float:
    """One-sided Clopper-Pearson lower bound without a scipy dependency."""
    if n <= 0 or not 0 <= k <= n:
        return math.nan
    if k == 0:
        return 0.0

    def upper_tail(probability: float) -> float:
        return sum(
            math.comb(n, value)
            * probability**value
            * (1.0 - probability) ** (n - value)
            for value in range(k, n + 1)
        )

    low, high = 0.0, k / n
    for _ in range(100):
        midpoint = (low + high) / 2
        if upper_tail(midpoint) < alpha:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2


def _classify_preference(admin: dict[str, str], pair: dict[str, str], value: str) -> str:
    preference = normalize_preference(value)
    if preference in {"tie", "unsure"}:
        return "abstain" if preference == "unsure" else "tie"
    selected_arm = admin["presented_a_is"] if preference == "a" else admin["presented_b_is"]
    if selected_arm == pair["method_arm"]:
        return "method"
    if selected_arm == pair["baseline_arm"]:
        return "baseline"
    raise ValueError(f"presentation arm is neither method nor baseline: {admin['rating_id']}")


def endpoint_statistics(classes: list[str]) -> dict:
    counts = Counter(classes)
    for key in ("method", "baseline", "tie", "abstain"):
        counts.setdefault(key, 0)
    decided = counts["method"] + counts["baseline"]
    rate = counts["method"] / decided if decided else math.nan
    score_lower = wilson(counts["method"], decided, z=SCORE_Z_ONE_SIDED_95)[1]
    exact_lower = exact_binomial_lower(counts["method"], decided)
    nonabstain = decided + counts["tie"]
    original_p = exact_binom_less_equal(counts["method"], decided, 0.5)
    return {
        "counts": dict(counts),
        "decided": decided,
        "method_rate": rate,
        "score_one_sided_95_lower": score_lower,
        "exact_one_sided_95_lower": exact_lower,
        "score_lower_gt_0p40": bool(score_lower > 0.40),
        "exact_lower_gt_0p40": bool(exact_lower > 0.40),
        "ties_as_half_rate": (
            (counts["method"] + 0.5 * counts["tie"]) / nonabstain
            if nonabstain
            else math.nan
        ),
        "ties_against_method_rate": (
            counts["method"] / nonabstain if nonabstain else math.nan
        ),
        "original_rule_p_lower_tail_under_0p5": original_p,
        "original_rule_rate_at_least_0p40": bool(rate >= 0.40),
        "original_rule_not_significantly_below_0p50": bool(original_p >= 0.05),
        "original_rule_pass": bool(rate >= 0.40 and original_p >= 0.05),
    }


def score_b_prime(t3: list[dict]) -> tuple[dict, dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    pair_rows = read_csv(PAIR_ADMIN)
    ordered_rows = read_csv(ORDERED_ADMIN)
    pairs = {row["pair_id"]: row for row in pair_rows}
    primary = {row["rating_id"]: row for row in ordered_rows if row["presentation_role"] == "primary"}
    if len(pairs) != 80 or len(primary) != 80 or set(row["rating_id"] for row in t3) != set(primary):
        raise ValueError("t3 must exactly match the 80 first-presentation admin rows")
    if any(pair["method_arm"] != "arm6" for pair in pairs.values()):
        raise ValueError("unexpected B-prime method arm")
    ratings = {row["rating_id"]: row for row in t3}
    endpoint_classes: dict[str, dict[str, str]] = {}
    endpoints = {}
    by_direction = {}
    for endpoint in ENDPOINTS:
        classes = {}
        for rating_id, admin in primary.items():
            pair = pairs[admin["pair_id"]]
            classes[admin["pair_id"]] = _classify_preference(
                admin, pair, ratings[rating_id][endpoint]
            )
        endpoint_classes[endpoint] = classes
        endpoints[endpoint] = endpoint_statistics(list(classes.values()))
        direction_results = {}
        for direction in ("vocal", "instrumental"):
            selected = []
            for rating_id, admin in primary.items():
                rating = ratings[rating_id]
                if rating["request_mode"] == direction:
                    selected.append(classes[admin["pair_id"]])
            direction_results[direction] = endpoint_statistics(selected)
        by_direction[endpoint] = direction_results
    quality = endpoints["quality_preference"]
    result = {
        "b_prime_gate": "PI_CALL_PENDING",
        "primary_endpoint": "quality_preference",
        "frozen_signed_criterion": "one-sided 95% score lower bound > 0.40",
        "frozen_signed_condition_met": quality["score_lower_gt_0p40"],
        "exact_bound_crosscheck_met": quality["exact_lower_gt_0p40"],
        "both_score_and_exact_bounds_gt_0p40": bool(
            quality["score_lower_gt_0p40"] and quality["exact_lower_gt_0p40"]
        ),
        "gate_never_auto_passes": True,
        "endpoints": endpoints,
        "by_request_direction": by_direction,
    }
    return result, primary, pairs


def _fmt(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "NA"
    return f"{float(value):.6f}"


def write_b_report(result: dict) -> None:
    lines = [
        "# B-prime Gate Report: PI Drop 2",
        "",
        "`B_PRIME_GATE = PI_CALL_PENDING`",
        "",
        "Primary evidence uses only the 80 t3 first presentations. The 24 t4",
        "reversed presentations are excluded from every gate denominator.",
        "",
        "## Endpoint Results",
        "",
        "| Endpoint | Method | Baseline | Ties | Abstains | Rate | Score LCB | Exact LCB | Score > .40 | Exact > .40 | Ties half | Ties against |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for endpoint in ENDPOINTS:
        value = result["endpoints"][endpoint]
        counts = value["counts"]
        lines.append(
            f"| `{endpoint}` | {counts['method']} | {counts['baseline']} | "
            f"{counts['tie']} | {counts['abstain']} | {_fmt(value['method_rate'])} | "
            f"{_fmt(value['score_one_sided_95_lower'])} | "
            f"{_fmt(value['exact_one_sided_95_lower'])} | "
            f"{str(value['score_lower_gt_0p40']).lower()} | "
            f"{str(value['exact_lower_gt_0p40']).lower()} | "
            f"{_fmt(value['ties_as_half_rate'])} | "
            f"{_fmt(value['ties_against_method_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Condition Booleans",
            "",
            f"- Frozen signed score-LCB condition met: `{str(result['frozen_signed_condition_met']).lower()}`.",
            f"- Exact-LCB cross-check met: `{str(result['exact_bound_crosscheck_met']).lower()}`.",
            f"- Both lower bounds exceed 0.40: `{str(result['both_score_and_exact_bounds_gt_0p40']).lower()}`.",
            "- Final gate call made mechanically: `false`.",
            "",
            "## Original Frozen-Rule Sensitivity",
            "",
            "This is secondary only: method preference at least 40% and not",
            "significantly below 50% by the one-sided exact lower-tail test.",
            "",
            "| Endpoint | Rate >= .40 | p(lower tail at .50) | Not below .50 | Rule met |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for endpoint in ENDPOINTS:
        value = result["endpoints"][endpoint]
        lines.append(
            f"| `{endpoint}` | {str(value['original_rule_rate_at_least_0p40']).lower()} | "
            f"{_fmt(value['original_rule_p_lower_tail_under_0p5'])} | "
            f"{str(value['original_rule_not_significantly_below_0p50']).lower()} | "
            f"{str(value['original_rule_pass']).lower()} |"
        )
    lines.extend(
        [
            "",
            "## Request-Direction Breakdown",
            "",
            "| Endpoint | Direction | Rows | Method | Baseline | Ties | Rate | Score LCB | Exact LCB |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for endpoint in ENDPOINTS:
        for direction in ("vocal", "instrumental"):
            value = result["by_request_direction"][endpoint][direction]
            counts = value["counts"]
            rows = sum(counts.values())
            lines.append(
                f"| `{endpoint}` | {direction} | {rows} | {counts['method']} | "
                f"{counts['baseline']} | {counts['tie']} | {_fmt(value['method_rate'])} | "
                f"{_fmt(value['score_one_sided_95_lower'])} | "
                f"{_fmt(value['exact_one_sided_95_lower'])} |"
            )
    lines.extend(
        [
            "",
            "The numerical scorer cannot emit PASS. Richard must make and record",
            "the PI gate call after reviewing this report and the t4 deviation.",
            "",
        ]
    )
    B_REPORT.parent.mkdir(parents=True, exist_ok=True)
    B_REPORT.write_text("\n".join(lines), encoding="utf-8")


def analyze_t4(
    t3: list[dict],
    t4: list[dict],
    t3_payload: dict,
    t4_payload: dict,
    primary: dict[str, dict[str, str]],
    pairs: dict[str, dict[str, str]],
    t4_sequence_anomalies: list[dict],
) -> dict:
    ordered_rows = read_csv(ORDERED_ADMIN)
    reverse = {
        row["rating_id"]: row
        for row in ordered_rows
        if row["presentation_role"] == "reliability_reverse"
    }
    if len(reverse) != 24 or set(row["rating_id"] for row in t4) != set(reverse):
        raise ValueError("t4 must exactly match the 24 reverse-presentation admin rows")
    t3_by_pair = {
        primary[row["rating_id"]]["pair_id"]: row
        for row in t3
        if row["rating_id"] in primary
    }
    t4_by_pair = {reverse[row["rating_id"]]["pair_id"]: row for row in t4}
    if not set(t4_by_pair).issubset(t3_by_pair):
        raise ValueError("t4 contains a pair absent from t3")

    first_time = parse_timestamp(t3_payload["exported_at"])
    reverse_time = parse_timestamp(t4_payload["exported_at"])
    delta_seconds = (reverse_time - first_time).total_seconds()
    same_utc_day = first_time.date() == reverse_time.date()
    if delta_seconds <= 0:
        raise ValueError("t4 export must follow t3 export")

    endpoint_results = {}
    for endpoint in ENDPOINTS:
        first_classes = []
        reverse_classes = []
        first_raw = []
        reverse_raw = []
        arm_agreed = 0
        raw_agreed = 0
        comparable = 0
        for pair_id, reverse_rating in t4_by_pair.items():
            first_rating = t3_by_pair[pair_id]
            first_admin = primary[first_rating["rating_id"]]
            reverse_admin = reverse[reverse_rating["rating_id"]]
            pair = pairs[pair_id]
            first_class = _classify_preference(first_admin, pair, first_rating[endpoint])
            reverse_class = _classify_preference(reverse_admin, pair, reverse_rating[endpoint])
            first_classes.append(first_class)
            reverse_classes.append(reverse_class)
            first_value = normalize_preference(first_rating[endpoint])
            reverse_value = normalize_preference(reverse_rating[endpoint])
            first_raw.append(first_value)
            reverse_raw.append(reverse_value)
            if "abstain" not in {first_class, reverse_class}:
                comparable += 1
                arm_agreed += int(first_class == reverse_class)
                raw_agreed += int(first_value == reverse_value)
        first_stats = endpoint_statistics(first_classes)
        reverse_stats = endpoint_statistics(reverse_classes)
        first_position = Counter(first_raw)
        reverse_position = Counter(reverse_raw)
        first_ab = first_position["a"] + first_position["b"]
        reverse_ab = reverse_position["a"] + reverse_position["b"]
        endpoint_results[endpoint] = {
            "first_24": first_stats,
            "reverse_24": reverse_stats,
            "first_position_counts": dict(first_position),
            "reverse_position_counts": dict(reverse_position),
            "first_a_rate_excluding_ties": first_position["a"] / first_ab if first_ab else math.nan,
            "reverse_a_rate_excluding_ties": reverse_position["a"] / reverse_ab if reverse_ab else math.nan,
            "arm_mapped_agreement_numerator": arm_agreed,
            "raw_position_answer_agreement_numerator": raw_agreed,
            "agreement_denominator": comparable,
            "arm_mapped_agreement_rate_upper_bound": arm_agreed / comparable if comparable else math.nan,
            "raw_position_agreement_rate_upper_bound": raw_agreed / comparable if comparable else math.nan,
        }

    nonuniform = []
    for pair_id, rating in t4_by_pair.items():
        triple = [normalize_preference(rating[endpoint]) for endpoint in ENDPOINTS]
        if len(set(triple)) > 1:
            nonuniform.append(
                {
                    "pair_id": pair_id,
                    "bundle_rating_id": rating["bundle_rating_id"],
                    "scorer_rating_id": rating["rating_id"],
                    "quality_preference": triple[0],
                    "overall_preference": triple[1],
                    "constraint_preference": triple[2],
                }
            )
    if len(nonuniform) != 1 or len(t4_sequence_anomalies) != 1:
        raise ValueError(
            "expected one non-uniform t4 answer triple and one constraint/overall sequence anomaly"
        )
    return {
        "protocol_deviation": "PROTOCOL_DEVIATION_T4_SAME_SESSION",
        "t3_exported_at": t3_payload["exported_at"],
        "t4_exported_at": t4_payload["exported_at"],
        "elapsed_seconds": delta_seconds,
        "same_utc_day": same_utc_day,
        "later_day_rule_met": False,
        "agreement_interpretation": "UPPER_BOUND_ONLY",
        "t6_supersedes_as_primary_rater_stability_evidence": True,
        "endpoint_results": endpoint_results,
        "nonuniform_answer_triples": nonuniform,
        "constraint_overall_sequence_anomalies": t4_sequence_anomalies,
    }


def write_t4_report(result: dict) -> None:
    lines = [
        "# t4 Order-Bias And Reliability Analysis",
        "",
        "`PROTOCOL_DEVIATION_T4_SAME_SESSION`",
        "",
        f"- t3 export: `{result['t3_exported_at']}`.",
        f"- t4 export: `{result['t4_exported_at']}`.",
        f"- Elapsed time: {result['elapsed_seconds']:.3f} seconds.",
        "- Later-day rule met: `false`.",
        "- Every agreement figure below is an **upper bound**, not valid delayed-day reliability.",
        "- The t6 hidden-repeat block supersedes t4 as primary rater-stability evidence.",
        "",
        "## Agreement And Position Results",
        "",
        "| Endpoint | First method/base/tie | Reverse method/base/tie | Arm agreement upper bound | Raw-position agreement upper bound | First A rate | Reverse A rate |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for endpoint in ENDPOINTS:
        value = result["endpoint_results"][endpoint]
        first = value["first_24"]["counts"]
        reverse = value["reverse_24"]["counts"]
        lines.append(
            f"| `{endpoint}` | {first['method']}/{first['baseline']}/{first['tie']} | "
            f"{reverse['method']}/{reverse['baseline']}/{reverse['tie']} | "
            f"{value['arm_mapped_agreement_numerator']}/{value['agreement_denominator']} "
            f"({_fmt(value['arm_mapped_agreement_rate_upper_bound'])}) | "
            f"{value['raw_position_answer_agreement_numerator']}/{value['agreement_denominator']} "
            f"({_fmt(value['raw_position_agreement_rate_upper_bound'])}) | "
            f"{_fmt(value['first_a_rate_excluding_ties'])} | "
            f"{_fmt(value['reverse_a_rate_excluding_ties'])} |"
        )
    nonuniform = result["nonuniform_answer_triples"][0]
    anomaly = result["constraint_overall_sequence_anomalies"][0]
    lines.extend(
        [
            "",
            "## Informational Flags",
            "",
            f"- One t4 answer triple is not uniform across endpoints: bundle "
            f"`{nonuniform['bundle_rating_id']}`, scorer `{nonuniform['scorer_rating_id']}`.",
            f"- One t4 row answered overall before constraint after the valid reveal: bundle "
            f"`{anomaly['bundle_rating_id']}`, scorer `{anomaly['scorer_rating_id']}`.",
            "- Neither informational flag changes t3 gate counts.",
            "",
        ]
    )
    T4_REPORT.write_text("\n".join(lines), encoding="utf-8")


def confusion(rows: list[tuple[str, int]]) -> dict:
    decided = [(label, prediction) for label, prediction in rows if label != "unsure"]
    tp = sum(label == "yes" and prediction == 1 for label, prediction in decided)
    tn = sum(label == "no" and prediction == 0 for label, prediction in decided)
    fp = sum(label == "no" and prediction == 1 for label, prediction in decided)
    fn = sum(label == "yes" and prediction == 0 for label, prediction in decided)
    sensitivity = tp / (tp + fn) if tp + fn else None
    specificity = tn / (tn + fp) if tn + fp else None
    balanced = (
        (sensitivity + specificity) / 2
        if sensitivity is not None and specificity is not None
        else None
    )
    return {
        "rows": len(rows),
        "human_label_counts": dict(Counter(label for label, _ in rows)),
        "decided": len(decided),
        "abstains": sum(label == "unsure" for label, _ in rows),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": balanced,
    }


def score_sa3(t5: list[dict]) -> dict:
    admin_rows = read_csv(SA3_ADMIN)
    admin = {row["blind_id"]: row for row in admin_rows}
    if len(admin) != 60 or set(row["blind_id"] for row in t5) != set(admin):
        raise ValueError("t5 must exactly match the 60-row SA3 admin manifest")
    joined = []
    missing_confidence = 0
    for rating in t5:
        row = admin[rating["blind_id"]]
        label = rating["label_a_voice_presence"]
        joined.append(
            {
                "label": label,
                "prediction": int(row["demucs_present_0p1791"]),
                "band": row["calibration_band"],
            }
        )
        missing_confidence += int(str(rating.get("confidence_1_to_5", "")).strip() == "")
    overall = confusion([(row["label"], row["prediction"]) for row in joined])
    bands = {
        band: confusion(
            [
                (row["label"], row["prediction"])
                for row in joined
                if row["band"] == band
            ]
        )
        for band in ("far_below", "near_threshold", "far_above")
    }
    if overall["balanced_accuracy"] is None:
        status = "SCORED_INFORMATIONAL"
    elif overall["balanced_accuracy"] >= 0.70:
        status = "SCORED_PASS"
    else:
        status = "SCORED_FAIL"
    return {
        "sa3_label_calibration_status": status,
        "criterion": "overall Label-A balanced accuracy >= 0.70",
        "criterion_met": bool(
            overall["balanced_accuracy"] is not None
            and overall["balanced_accuracy"] >= 0.70
        ),
        "overall": overall,
        "by_calibration_band": bands,
        "optional_confidence_missing": missing_confidence,
        "sa3_disposition": "PILOT_REGARDLESS_OF_CALIBRATION_STATUS",
    }


def write_sa3_report(result: dict) -> None:
    lines = [
        "# SA3 Label Calibration: PI Drop 2",
        "",
        f"`SA3_LABEL_CALIBRATION_STATUS = {result['sa3_label_calibration_status']}`",
        "",
        "Human Yes/No labels are the reference; Unsure is an abstention. Blank",
        "confidence is optional annotation-missing and never a validation failure.",
        "",
        "| Stratum | Rows | Yes | No | Unsure | TP | TN | FP | FN | Sensitivity | Specificity | Balanced accuracy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    display = [("overall", result["overall"]), *result["by_calibration_band"].items()]
    for name, value in display:
        labels = value["human_label_counts"]
        lines.append(
            f"| `{name}` | {value['rows']} | {labels.get('yes', 0)} | "
            f"{labels.get('no', 0)} | {labels.get('unsure', 0)} | {value['tp']} | "
            f"{value['tn']} | {value['fp']} | {value['fn']} | "
            f"{_fmt(value['sensitivity'])} | {_fmt(value['specificity'])} | "
            f"{_fmt(value['balanced_accuracy'])} |"
        )
    lines.extend(
        [
            "",
            f"- Optional confidence missing: {result['optional_confidence_missing']}/60.",
            f"- Frozen package criterion met: `{str(result['criterion_met']).lower()}`.",
            "- SA3 remains a pilot regardless of this calibration result; this",
            "  score does not promote a full second-backbone ADSR claim.",
            "",
        ]
    )
    SA3_REPORT.write_text("\n".join(lines), encoding="utf-8")


def append_deviation_log(result: dict) -> str:
    event_id = hashlib.sha256(
        (
            result["protocol_deviation"]
            + result["t3_exported_at"]
            + result["t4_exported_at"]
        ).encode()
    ).hexdigest()[:20]
    existing = []
    if STUDY_LOG.exists():
        existing = [json.loads(line) for line in STUDY_LOG.read_text(encoding="utf-8").splitlines() if line]
    if event_id not in {row.get("event_id") for row in existing}:
        STUDY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with STUDY_LOG.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event_id": event_id,
                        "event": result["protocol_deviation"],
                        "t3_exported_at": result["t3_exported_at"],
                        "t4_exported_at": result["t4_exported_at"],
                        "elapsed_seconds": result["elapsed_seconds"],
                        "interpretation": "t4 agreement figures are upper bounds",
                        "superseded_by": "t6 hidden-repeat calibration block",
                        "status": "LOGGED",
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return event_id


def write_amendment_appendix(t4: dict, event_id: str) -> None:
    AMENDMENT_APPENDIX.write_text(
        "# Human Study Criteria Amendment: 2026-07-12 Appendix\n\n"
        "The signed 2026-07-09 amendment remains unchanged. This appendix records\n"
        "an execution deviation discovered after export.\n\n"
        "`PROTOCOL_DEVIATION_T4_SAME_SESSION`\n\n"
        f"- Study-log event: `{event_id}`.\n"
        f"- t3 export: `{t4['t3_exported_at']}`.\n"
        f"- t4 export: `{t4['t4_exported_at']}`.\n"
        f"- Separation: {t4['elapsed_seconds']:.3f} seconds on the same UTC day.\n"
        "- The required later-day separation was not met.\n"
        "- All t4 order-bias and agreement figures are upper bounds and cannot be\n"
        "  used as primary delayed reliability evidence.\n"
        "- The t6 calibration package's 20 hidden repeats supersede t4 as the\n"
        "  primary rater-stability instrument.\n\n"
        "This appendix changes no t3 answer, gate count, signed criterion, frozen\n"
        "artifact, or PLAN claim status.\n",
        encoding="utf-8",
    )


def run() -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    t3_payload, t3, t3_audit = validate_and_remap_pair_export(
        T3_INPUT, T3_KEY, "t3_bprime_primary_v2", 80
    )
    t4_payload, t4, t4_audit = validate_and_remap_pair_export(
        T4_INPUT, T4_KEY, "t4_bprime_reverse_v2", 24
    )
    _t5_payload, t5, t5_audit = validate_and_remap_t5()

    write_csv(PROCESSED / "T3_B_PRIME_PRIMARY_OFFICIAL.csv", t3)
    write_csv(PROCESSED / "T4_B_PRIME_REVERSE_OFFICIAL.csv", t4)
    write_csv(PROCESSED / "T5_SA3_CALIBRATION_OFFICIAL.csv", t5)
    ingest = {
        "drop2_ingestion": "PASS",
        "t3": t3_audit,
        "t4": t4_audit,
        "t5": t5_audit,
        "all_exact_id_sets": True,
        "all_required_answer_fields_complete": True,
        "all_rating_sources": PI_SOURCE,
    }
    write_json(INGEST_AUDIT, ingest)

    b_result, primary, pairs = score_b_prime(t3)
    write_json(B_RESULT, b_result)
    write_b_report(b_result)

    t4_result = analyze_t4(
        t3,
        t4,
        t3_payload,
        t4_payload,
        primary,
        pairs,
        t4_audit["sequence_anomalies_constraint_after_overall"],
    )
    write_json(T4_RESULT, t4_result)
    write_t4_report(t4_result)
    event_id = append_deviation_log(t4_result)
    write_amendment_appendix(t4_result, event_id)

    sa3_result = score_sa3(t5)
    write_json(SA3_RESULT, sa3_result)
    write_sa3_report(sa3_result)
    return {
        "drop2_ingestion": "PASS",
        "b_prime_gate": b_result["b_prime_gate"],
        "b_prime_frozen_condition_met": b_result["frozen_signed_condition_met"],
        "t4_deviation_logged": True,
        "t4_event_id": event_id,
        "sa3_calibration": sa3_result["sa3_label_calibration_status"],
        "outputs": {
            "ingest_audit": str(INGEST_AUDIT),
            "b_report": str(B_REPORT),
            "t4_report": str(T4_REPORT),
            "sa3_report": str(SA3_REPORT),
            "study_log": str(STUDY_LOG),
            "amendment_appendix": str(AMENDMENT_APPENDIX),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
