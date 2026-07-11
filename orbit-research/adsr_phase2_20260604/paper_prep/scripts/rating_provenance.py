"""Strict rating-source contracts shared by publication gate scorers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


PI_RE = re.compile(r"^pi:(?P<identity>[A-Za-z][A-Za-z0-9 ._-]{0,63})$")
HUMAN_RE = re.compile(r"^human:(?P<identity>[A-Z][A-Z0-9_-]{0,15})$")
JUDGE_RE = re.compile(
    r"^judge:(?P<identity>[A-Za-z0-9][A-Za-z0-9._/-]{0,127}):"
    r"validated:(?P<gold_set_hash>[0-9a-f]{64})$"
)
REQUIRED_JUDGE_METRICS = (
    "sensitivity",
    "specificity",
    "balanced_accuracy",
    "mcc",
    "abstention_rate",
)


@dataclass(frozen=True)
class RatingSource:
    raw: str
    kind: str
    identity: str
    gold_set_hash: str = ""


def parse_rating_source(value: str) -> RatingSource:
    """Parse only the frozen explicit provenance enum; aliases are forbidden."""
    raw = (value or "").strip()
    match = PI_RE.fullmatch(raw)
    if match:
        return RatingSource(raw=raw, kind="pi", identity=match.group("identity"))
    match = HUMAN_RE.fullmatch(raw)
    if match:
        return RatingSource(raw=raw, kind="human", identity=match.group("identity"))
    match = JUDGE_RE.fullmatch(raw)
    if match:
        return RatingSource(
            raw=raw,
            kind="judge",
            identity=match.group("identity"),
            gold_set_hash=match.group("gold_set_hash"),
        )
    raise ValueError(
        "invalid rating_source; expected pi:<name>, human:<initials>, or "
        "judge:<model>:validated:<64-char-gold-set-sha256>"
    )


def require_human_source(value: str) -> RatingSource:
    source = parse_rating_source(value)
    if source.kind not in {"pi", "human"}:
        raise ValueError("this rating row requires pi:<name> or human:<initials> provenance")
    return source


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_judge_metrics(value: str | dict) -> dict[str, float]:
    try:
        parsed = value if isinstance(value, dict) else json.loads(value or "")
    except json.JSONDecodeError as exc:
        raise ValueError("judge_calibration_metrics must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError("judge_calibration_metrics must be a JSON object")
    output: dict[str, float] = {}
    for key in REQUIRED_JUDGE_METRICS:
        if key not in parsed:
            raise ValueError(f"judge calibration metric is missing: {key}")
        try:
            metric = float(parsed[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"judge calibration metric is not numeric: {key}") from exc
        if not math.isfinite(metric):
            raise ValueError(f"judge calibration metric is not finite: {key}")
        if key == "mcc":
            if not -1.0 <= metric <= 1.0:
                raise ValueError("judge MCC must be in [-1, 1]")
        elif not 0.0 <= metric <= 1.0:
            raise ValueError(f"judge calibration metric must be in [0, 1]: {key}")
        output[key] = metric
    return output


def require_validated_judge_metadata(row: dict[str, str], source: RatingSource) -> dict[str, float]:
    if source.kind != "judge":
        raise ValueError("judge metadata validation requires judge provenance")
    if row.get("judge_validation_status", "").strip() != "PASS":
        raise ValueError("judge_validation_status must be PASS")
    if row.get("judge_model_id", "").strip() != source.identity:
        raise ValueError("judge_model_id does not match rating_source")
    if row.get("judge_gold_set_hash", "").strip() != source.gold_set_hash:
        raise ValueError("judge_gold_set_hash does not match rating_source")
    metrics = parse_judge_metrics(row.get("judge_calibration_metrics", ""))
    raw_ledger = Path(row.get("judge_raw_response_ledger", "").strip())
    if not raw_ledger.is_file():
        raise ValueError("judge_raw_response_ledger must point to an existing file")
    expected_hash = row.get("judge_raw_response_ledger_sha256", "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError("judge_raw_response_ledger_sha256 must be a SHA-256 digest")
    if sha256_file(raw_ledger) != expected_hash:
        raise ValueError("judge raw-response ledger SHA-256 mismatch")
    return metrics


def validate_a_prime_rating_provenance(
    admin: list[dict[str, str]],
    ratings: list[dict[str, str]],
) -> dict[str, int]:
    admin_by_id = {row["rating_id"]: row for row in admin}
    if len(admin_by_id) != len(admin):
        raise ValueError("duplicate A-prime admin rating_id")
    counts = {"pi": 0, "human": 0, "judge": 0}
    for rating in ratings:
        rating_id = rating.get("rating_id", "")
        if rating_id not in admin_by_id:
            raise ValueError(f"rating outside A-prime admin: {rating_id}")
        admin_row = admin_by_id[rating_id]
        source = parse_rating_source(rating.get("rating_source", ""))
        if admin_row.get("analysis_role") == "primary":
            require_human_source(source.raw)
        elif admin_row.get("analysis_role") == "global_bound":
            if source.kind == "judge":
                require_validated_judge_metadata(rating, source)
            elif source.kind not in {"pi", "human"}:
                raise ValueError("invalid global-bound rating provenance")
        else:
            raise ValueError(f"unknown A-prime analysis_role: {admin_row.get('analysis_role')!r}")
        counts[source.kind] += 1
    return counts


def validate_human_rating_rows(
    ratings: list[dict[str, str]],
    *,
    id_field: str,
) -> dict[str, int]:
    counts = {"pi": 0, "human": 0}
    for row in ratings:
        try:
            source = require_human_source(row.get("rating_source", ""))
        except ValueError as exc:
            raise ValueError(f"invalid provenance for {row.get(id_field, '<missing>')}: {exc}") from exc
        counts[source.kind] += 1
    return counts
