"""Fail-closed A-prime and B-prime human-rating gate calculations."""
from __future__ import annotations

import math
from collections import Counter, defaultdict


def require_unique(rows: list[dict[str, str]], key: str, source: str) -> None:
    values = [row[key] for row in rows]
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {key} in {source}: {duplicates[:10]}")


def validate_exact_ids(
    admin: list[dict[str, str]],
    ratings: list[dict[str, str]],
    key: str = "rating_id",
) -> None:
    require_unique(admin, key, "admin")
    require_unique(ratings, key, "ratings")
    expected = {row[key] for row in admin}
    actual = {row[key] for row in ratings}
    if actual != expected:
        raise ValueError(
            f"rating/admin ID mismatch: missing={sorted(expected-actual)[:10]}, "
            f"unknown={sorted(actual-expected)[:10]}"
        )


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        return math.nan, math.nan, math.nan
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denominator
    return p, max(0.0, center - half), min(1.0, center + half)


def exact_binom_less_equal(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return math.nan
    return sum(math.comb(n, value) * p**value * (1 - p) ** (n - value) for value in range(k + 1))


def _normal(value: str) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_label_a(value: str) -> str:
    value = _normal(value)
    if value in {"yes", "y", "1"}:
        return "yes"
    if value in {"no", "n", "0"}:
        return "no"
    if value in {"unsure", "unknown", "uncertain", "u", ""}:
        return "unsure"
    raise ValueError(f"invalid Label A value: {value!r}")


def normalize_label_b(value: str) -> str:
    value = _normal(value)
    if value in {"satisfied", "satisfy"}:
        return "satisfied"
    if value in {"violated", "violation", "fail"}:
        return "violated"
    if value in {"unsure", "unknown", "uncertain", "u", ""}:
        return "unsure"
    raise ValueError(f"invalid Label B value: {value!r}")


def normalize_preference(value: str) -> str:
    value = _normal(value)
    if value in {"a", "clip_a", "left", "first"}:
        return "a"
    if value in {"b", "clip_b", "right", "second"}:
        return "b"
    if value in {"tie", "same", "equal", "neither"}:
        return "tie"
    if value in {"unsure", "unknown", "uncertain", "u", ""}:
        return "unsure"
    raise ValueError(f"invalid preference value: {value!r}")


def _a_presence(row: dict[str, str], construct: str) -> int | None:
    if construct == "label_a":
        value = normalize_label_a(row.get("label_a_voice_presence", ""))
        return None if value == "unsure" else int(value == "yes")
    value = normalize_label_b(row.get("label_b_constraint", ""))
    if value == "unsure":
        return None
    requested_vocal = row["requested_vocal"] == "1"
    return int((requested_vocal and value == "satisfied") or (not requested_vocal and value == "violated"))


def _real_ratings_complete(ratings: list[dict[str, str]]) -> bool:
    sources = [_normal(row.get("rating_source", "")) for row in ratings]
    return bool(sources) and all(source and source not in {"synthetic", "test_fixture"} for source in sources)


def score_a_prime(
    admin: list[dict[str, str]],
    ratings: list[dict[str, str]],
    abstain_policy: str = "report",
) -> dict:
    if abstain_policy not in {"report", "count-as-disagree"}:
        raise ValueError(f"invalid abstain policy {abstain_policy}")
    validate_exact_ids(admin, ratings)
    require_unique(admin, "source_clip_id", "A-prime admin")
    rating_index = {row["rating_id"]: row for row in ratings}
    primary = [row for row in admin if row["analysis_role"] == "primary" and row["media_class"] == "original"]
    excluded_regenerated = [row for row in admin if row["analysis_role"] == "primary" and row["media_class"] != "original"]
    counts = Counter(row["set_bucket"] for row in primary)
    expected = {
        "detector_disagreement_112": 112,
        "rare_basin_48": 48,
        "agreement_spotcheck_30": 30,
    }
    for bucket, count in expected.items():
        if counts[bucket] != count:
            raise ValueError(f"A-prime cardinality-short {bucket}: {counts[bucket]} != {count}")
    global_rows = [row for row in admin if row["analysis_role"] == "global_bound" and row["media_class"] == "original"]
    if len(global_rows) != 500 or any(row["set_bucket"] != "stratified_random_500" for row in global_rows):
        raise ValueError(f"A-prime stratified global-bound cardinality must be 500, got {len(global_rows)}")

    constructs = {}
    for construct in ("label_a", "label_b"):
        bucket_results = {}
        for bucket in (*expected, "stratified_random_500"):
            source_rows = primary if bucket in expected else global_rows
            source_rows = [row for row in source_rows if row["set_bucket"] == bucket]
            decided = 0
            matches = 0
            abstains = 0
            for admin_row in source_rows:
                rating = {**admin_row, **rating_index[admin_row["rating_id"]]}
                presence = _a_presence(rating, construct)
                if presence is None:
                    abstains += 1
                    if abstain_policy == "count-as-disagree":
                        decided += 1
                    continue
                decided += 1
                matches += int(presence == int(admin_row["expected_demucs_label"]))
            rate, low, high = wilson(matches, decided)
            bucket_results[bucket] = {
                "rows": len(source_rows),
                "decided": decided,
                "abstains": abstains,
                "matches": matches,
                "match_rate": rate,
                "wilson_low": low,
                "wilson_high": high,
            }
        constructs[construct] = bucket_results

    primary_b = constructs["label_b"]
    mechanical_pass = (
        primary_b["rare_basin_48"]["match_rate"] >= 0.90
        and primary_b["detector_disagreement_112"]["match_rate"] >= 0.70
        and primary_b["agreement_spotcheck_30"]["decided"] - primary_b["agreement_spotcheck_30"]["matches"] <= 2
    )
    complete_real = _real_ratings_complete(ratings)
    status = "PASS" if complete_real and mechanical_pass else "FAIL" if complete_real else "AWAITING_RATINGS"
    return {
        "status": status,
        "mechanical_pass": mechanical_pass,
        "complete_real_ratings": complete_real,
        "abstain_policy": abstain_policy,
        "excluded_regenerated_primary": len(excluded_regenerated),
        "constructs": constructs,
    }


def _preference_class(admin_row: dict[str, str], value: str, abstain_policy: str) -> str:
    preference = normalize_preference(value)
    if preference == "unsure":
        return "baseline" if abstain_policy == "count-as-disagree" else "abstain"
    if preference == "tie":
        return "tie"
    arm = admin_row["presented_a_is"] if preference == "a" else admin_row["presented_b_is"]
    return "method" if arm == "arm6" else "baseline"


def score_b_prime(
    pair_admin: list[dict[str, str]],
    ordered_admin: list[dict[str, str]],
    ratings: list[dict[str, str]],
    abstain_policy: str = "report",
) -> dict:
    if abstain_policy not in {"report", "count-as-disagree"}:
        raise ValueError(f"invalid abstain policy {abstain_policy}")
    require_unique(pair_admin, "pair_id", "B-prime pair admin")
    if len(pair_admin) != 80:
        raise ValueError(f"B-prime needs 80 unique pairs, got {len(pair_admin)}")
    validate_exact_ids(ordered_admin, ratings)
    require_unique(ordered_admin, "rating_id", "B-prime ordered admin")
    primary = [row for row in ordered_admin if row["presentation_role"] == "primary"]
    reverse = [row for row in ordered_admin if row["presentation_role"] == "reliability_reverse"]
    if len(primary) != 80 or len({row["pair_id"] for row in primary}) != 80:
        raise ValueError("B-prime requires exactly one primary presentation for each of 80 pairs")
    calibration = {row["pair_id"] for row in pair_admin if row["in_calibration_24"] == "true"}
    if len(calibration) != 24:
        raise ValueError(f"B-prime calibration subset must be 24 pairs, got {len(calibration)}")
    reverse_by_pair = {row["pair_id"]: row for row in reverse}
    if len(reverse) != 24 or set(reverse_by_pair) != calibration:
        raise ValueError("B-prime missing reverse order for one or more calibration pairs")
    primary_by_pair = {row["pair_id"]: row for row in primary}
    for pair_id, reversed_row in reverse_by_pair.items():
        first = primary_by_pair[pair_id]
        if not (
            first["presented_a_is"] == reversed_row["presented_b_is"]
            and first["presented_b_is"] == reversed_row["presented_a_is"]
        ):
            raise ValueError(f"B-prime reverse order is not reversed for {pair_id}")

    rating_index = {row["rating_id"]: row for row in ratings}
    endpoints = {}
    primary_classes: dict[str, dict[str, str]] = defaultdict(dict)
    for endpoint in ("quality_preference", "overall_preference", "constraint_preference"):
        classes = []
        for admin_row in primary:
            klass = _preference_class(admin_row, rating_index[admin_row["rating_id"]].get(endpoint, ""), abstain_policy)
            classes.append(klass)
            primary_classes[admin_row["pair_id"]][endpoint] = klass
        counts = Counter(classes)
        decided = counts["method"] + counts["baseline"]
        rate, lower_one_sided, _ = wilson(counts["method"], decided, z=1.6448536269514722)
        original_p = exact_binom_less_equal(counts["method"], decided)
        endpoints[endpoint] = {
            "counts": dict(counts),
            "decided": decided,
            "method_rate": rate,
            "one_sided_95_lower": lower_one_sided,
            "primary_noninferiority_pass": lower_one_sided > 0.40,
            "ties_as_half_rate": (counts["method"] + 0.5 * counts["tie"]) / (decided + counts["tie"]) if decided + counts["tie"] else math.nan,
            "ties_against_method_rate": counts["method"] / (decided + counts["tie"]) if decided + counts["tie"] else math.nan,
            "original_rule_p_less_equal_under_0p5": original_p,
            "original_rule_pass": rate >= 0.40 and original_p >= 0.05,
        }

    reliability = {}
    for endpoint in endpoints:
        agreed = 0
        decided = 0
        for pair_id, admin_row in reverse_by_pair.items():
            reverse_class = _preference_class(admin_row, rating_index[admin_row["rating_id"]].get(endpoint, ""), abstain_policy)
            first_class = primary_classes[pair_id][endpoint]
            if "abstain" in {reverse_class, first_class}:
                continue
            decided += 1
            agreed += int(reverse_class == first_class)
        reliability[endpoint] = {"decided": decided, "agreed": agreed, "agreement_rate": agreed / decided if decided else math.nan}

    complete_real = _real_ratings_complete(ratings)
    quality_pass = bool(endpoints["quality_preference"]["primary_noninferiority_pass"])
    status = "PASS" if complete_real and quality_pass else "FAIL" if complete_real else "AWAITING_RATINGS"
    return {
        "status": status,
        "complete_real_ratings": complete_real,
        "abstain_policy": abstain_policy,
        "endpoints": endpoints,
        "reliability": reliability,
    }
