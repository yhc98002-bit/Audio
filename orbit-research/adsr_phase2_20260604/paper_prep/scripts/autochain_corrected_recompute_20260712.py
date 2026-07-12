#!/usr/bin/env python3
"""Produce adoption-gated W2 corrected and calibrated publication tables."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
OUT = PAPER / "autochain_20260712/recompute"
AUTOCHAIN = PAPER / "autochain_20260712"
PROMOTION = AUTOCHAIN / "T6_PROMOTION_RESULT.json"
RATINGS = AUTOCHAIN / "T6_OFFICIAL_RATINGS.csv"
ADMIN = PAPER / "rater_admin_keys_20260712/t6_calibration_torch251_recovery/T6_CALIBRATION_ADMIN.csv"
SELECTION = PAPER / "w2_execution_20260712/calibration_torch251_recovery/W2_CALIBRATION_SELECTION_MANIFEST.csv"
TARGET = PAPER / "w2_execution_20260712/analysis_torch251_recovery/W2_TARGET_SCORE_TABLE.csv"
PUBLICATION_TEMPLATE = PAPER / "w2_execution_20260712/analysis_torch251_recovery/W2_PUBLICATION_RATES.csv"
CALIBRATION_SCRIPT = PAPER / "scripts/w2_calibrated_prevalence_20260712.py"
AMENDMENT = PAPER / "W2_AMENDMENT_20260712.md"

TARGET_ROWS = OUT / "CORRECTED_TARGET_ROWS.csv"
PUBLICATION_RATES = OUT / "CORRECTED_PUBLICATION_RATES.csv"
PROMPT_RATES = OUT / "CORRECTED_PROMPT_RATES.csv"
PROMPT_ECDF = OUT / "CORRECTED_PROMPT_ECDFS.csv"
MODEL_AUDIT = OUT / "CALIBRATION_MODEL_AUDIT.json"
REPORT = OUT / "CORRECTED_RECOMPUTE_REPORT.md"
PLAN_DRAFT = OUT / "PLAN_UPDATE_DRAFT.md"
CLAIMS_DRAFT = OUT / "CLAIMS_UPDATE_DRAFT.md"
ADOPTION_PACKET = OUT / "DUAL_PI_ADOPTION_PACKET.md"
FIGURE_PNG = OUT / "corrected_prevalence_summary.png"
FIGURE_PDF = OUT / "corrected_prevalence_summary.pdf"

BOOTSTRAP_SEED = 20260714
BOOTSTRAP_REPLICATES = 2_000


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAL = load_module(CALIBRATION_SCRIPT, "w2_calibrated_prevalence_autochain")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def prepare_calibration() -> list[dict]:
    admin = read_csv(ADMIN)
    ratings = {row["rating_id"]: row for row in read_csv(RATINGS)}
    prompt_by_clip = {
        row["canonical_clip_id"]: row["prompt_id"]
        for row in read_csv(SELECTION)
    }
    rows = []
    for row in admin:
        if row["role"] != "train":
            continue
        label = ratings[row["rating_id"]]["label_b_constraint"]
        if label == "unsure":
            continue
        probability = float(row["inclusion_probability"])
        rows.append(
            {
                "rating_id": row["rating_id"],
                "prompt_id": prompt_by_clip[row["canonical_clip_id"]],
                "requested_vocal": int(row["requested_vocal"]),
                "demucs_score": float(row["demucs_score"]),
                "panns_score": float(row["panns_score"]),
                "truth_violation": int(label == "violated"),
                "design_weight": 1.0 / probability,
                "calibration_stratum": row["calibration_stratum"],
                "rating_source": ratings[row["rating_id"]]["rating_source"],
            }
        )
    if len(rows) != 58 or set(row["truth_violation"] for row in rows) != {0, 1}:
        raise ValueError(f"expected 58 decided train rows with both classes, found {len(rows)}")
    return rows


def selected_present(row: dict, candidate: dict) -> int:
    demucs = float(row["demucs_score"]) >= float(candidate["demucs_threshold"])
    panns = float(row["panns_score"]) >= float(candidate["panns_threshold"])
    family = candidate["family"]
    if family == "or":
        return int(demucs or panns)
    if family in {"and", "fixed_20260711_and"}:
        return int(demucs and panns)
    if family in {"demucs", "current_demucs"}:
        return int(demucs)
    if family == "panns":
        return int(panns)
    raise ValueError(f"unsupported candidate family {family!r}")


def prepare_targets(candidate: dict, fit: dict) -> list[dict]:
    source = read_csv(TARGET)
    prepared = [
        {
            **row,
            "requested_vocal": int(row["requested_vocal"]),
            "demucs_score": float(row["demucs_score"]),
            "panns_score": float(row["panns_score"]),
            "design_weight": float(row.get("target_sampling_weight", 1.0)),
            "apparent_violation": int(row["apparent_violation"]),
        }
        for row in source
    ]
    probabilities = CAL.predict_probability(prepared, fit)
    output = []
    for row, probability in zip(prepared, probabilities):
        present = selected_present(row, candidate)
        violation = int(present != int(row["requested_vocal"]))
        output.append(
            {
                **row,
                "corrected_present": present,
                "corrected_violation": violation,
                "calibrated_violation_probability": float(probability),
                "instrument_status": "DRAFT_PROMOTED_AWAITING_DUAL_PI_ADOPTION",
            }
        )
    if len(output) != 27_966 or len({row["record_id"] for row in output}) != 27_966:
        raise ValueError("corrected target cardinality or identity mismatch")
    return output


def request_direction(row: dict) -> str:
    return "vocal_request" if int(row["requested_vocal"]) else "instrumental_request"


def publication_groups(rows: list[dict]) -> list[tuple[dict, list[int]]]:
    template = read_csv(PUBLICATION_TEMPLATE)
    groups = []
    for spec in template:
        indices = [
            index
            for index, row in enumerate(rows)
            if row["cohort"] == spec["cohort"]
            and request_direction(row) == spec["request_direction"]
            and row["condition"] == spec["condition"]
            and row["arm"] == spec["arm"]
        ]
        if len(indices) != int(spec["rows"]):
            raise ValueError(f"publication group drift for {spec}: {len(indices)}")
        groups.append((spec, indices))
    if len(groups) != 28:
        raise ValueError(f"expected 28 publication groups, found {len(groups)}")
    return groups


def _stratified_calibration_sample(rows: list[dict], rng: np.random.Generator) -> list[dict]:
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        strata[row["calibration_stratum"]].append(row)
    sampled = []
    for key in sorted(strata):
        source = strata[key]
        sampled.extend(source[int(i)] for i in rng.integers(0, len(source), len(source)))
    return sampled


def nested_intervals(
    calibration: list[dict],
    target: list[dict],
    groups: list[tuple[dict, list[int]]],
    fit: dict,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[list[list[float]], dict]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    selected_form = fit["selected"]["form"]
    selected_l2 = float(fit["selected"]["l2"])
    target_by_group_prompt = []
    for _spec, indices in groups:
        prompt_indices: dict[str, list[int]] = defaultdict(list)
        for index in indices:
            prompt_indices[target[index]["prompt_id"]].append(index)
        target_by_group_prompt.append(prompt_indices)
    estimates: list[list[float]] = [[] for _ in groups]
    failures = Counter()
    for _ in range(replicates):
        sampled = _stratified_calibration_sample(calibration, rng)
        try:
            if set(row["truth_violation"] for row in sampled) != {0, 1}:
                raise ValueError("bootstrap calibration sample lost a class")
            transform = CAL.fit_transform(sampled)
            model = CAL.fit_model(sampled, selected_form, selected_l2, transform)
            sampled_fit = {
                "selected": {"form": selected_form, "l2": selected_l2},
                "transform": transform.as_dict(),
                "model": model,
            }
            probability = CAL.predict_probability(target, sampled_fit)
            for group_index, prompt_indices in enumerate(target_by_group_prompt):
                prompts = sorted(prompt_indices)
                sampled_prompts = rng.choice(prompts, size=len(prompts), replace=True)
                indices = [index for prompt in sampled_prompts for index in prompt_indices[str(prompt)]]
                weights = np.asarray([target[index]["design_weight"] for index in indices])
                estimates[group_index].append(float(np.average(probability[indices], weights=weights)))
        except (ValueError, np.linalg.LinAlgError) as exc:
            failures[type(exc).__name__] += 1
    valid = min(len(values) for values in estimates)
    if valid < int(replicates * 0.8):
        raise RuntimeError(f"nested bootstrap valid replicates too low: {valid}/{replicates}")
    return estimates, {
        "seed": BOOTSTRAP_SEED,
        "requested_replicates": replicates,
        "valid_replicates": valid,
        "failure_counts": dict(failures),
        "model_form_refit_each_replicate": selected_form,
        "model_l2_refit_each_replicate": selected_l2,
        "target_resampling_unit": "prompt_within_publication_group",
        "calibration_resampling_unit": "row_within_frozen_calibration_stratum",
    }


def calibration_operating_characteristics(candidate: dict) -> dict[str, dict]:
    admin = read_csv(ADMIN)
    ratings = {row["rating_id"]: row for row in read_csv(RATINGS)}
    result = {}
    for requested, name in ((None, "overall"), (0, "instrumental_request"), (1, "vocal_request")):
        rows = []
        for row in admin:
            if row["role"] != "heldout":
                continue
            if requested is not None and int(row["requested_vocal"]) != requested:
                continue
            label = ratings[row["rating_id"]]["label_b_constraint"]
            if label == "unsure":
                continue
            truth = int(label == "violated")
            predicted = int(selected_present(row, candidate) != requested)
            rows.append((truth, predicted, 1.0 / float(row["inclusion_probability"])))
        tp = sum(weight for truth, pred, weight in rows if truth == pred == 1)
        fn = sum(weight for truth, pred, weight in rows if truth == 1 and pred == 0)
        tn = sum(weight for truth, pred, weight in rows if truth == pred == 0)
        fp = sum(weight for truth, pred, weight in rows if truth == 0 and pred == 1)
        result[name] = {
            "rows": len(rows),
            "positive_weight": tp + fn,
            "negative_weight": tn + fp,
            "sensitivity": tp / (tp + fn) if tp + fn else None,
            "specificity": tn / (tn + fp) if tn + fp else None,
            "status": "ESTIMABLE" if tp + fn and tn + fp else "NOT_ESTIMABLE_BOTH_CLASSES_REQUIRED",
        }
    return result


def rogan_gladen(apparent: float, sensitivity: float, specificity: float) -> float:
    denominator = sensitivity + specificity - 1
    if denominator <= 0:
        return math.nan
    return float(np.clip((apparent + specificity - 1) / denominator, 0, 1))


def build_publication_rows(
    target: list[dict],
    groups: list[tuple[dict, list[int]]],
    intervals: list[list[float]],
    operating: dict[str, dict],
) -> list[dict]:
    output = []
    for (spec, indices), samples in zip(groups, intervals):
        subset = [target[index] for index in indices]
        weights = np.asarray([row["design_weight"] for row in subset])
        apparent_values = np.asarray([row["apparent_violation"] for row in subset])
        corrected_values = np.asarray([row["corrected_violation"] for row in subset])
        calibrated_values = np.asarray([row["calibrated_violation_probability"] for row in subset])
        apparent = float(np.average(apparent_values, weights=weights))
        corrected = float(np.average(corrected_values, weights=weights))
        calibrated = float(np.average(calibrated_values, weights=weights))
        apparent_ci = wilson(int(apparent_values.sum()), len(subset))
        corrected_ci = wilson(int(corrected_values.sum()), len(subset))
        direction_op = operating[spec["request_direction"]]
        op = direction_op if direction_op["status"] == "ESTIMABLE" else operating["overall"]
        output.append(
            {
                "cohort": spec["cohort"],
                "request_direction": spec["request_direction"],
                "condition": spec["condition"],
                "arm": spec["arm"],
                "rows": len(subset),
                "prompt_count": len({row["prompt_id"] for row in subset}),
                "apparent_rate": apparent,
                "apparent_95_ci_low": apparent_ci[0],
                "apparent_95_ci_high": apparent_ci[1],
                "corrected_instrument_rate": corrected,
                "corrected_95_ci_low": corrected_ci[0],
                "corrected_95_ci_high": corrected_ci[1],
                "calibrated_rate": calibrated,
                "joint_95_interval_low": float(np.quantile(samples, 0.025)),
                "joint_95_interval_high": float(np.quantile(samples, 0.975)),
                "rogan_gladen_sensitivity_rate": rogan_gladen(corrected, op["sensitivity"], op["specificity"]),
                "heldout_direction_sensitivity": op["sensitivity"],
                "heldout_direction_specificity": op["specificity"],
                "rogan_gladen_operating_stratum": (
                    spec["request_direction"]
                    if direction_op["status"] == "ESTIMABLE"
                    else "overall_fallback_direction_not_estimable"
                ),
                "transport_source_correction": "NONE_REQUIRED",
                "publication_status": "DRAFT_AWAITING_DUAL_PI_ADOPTION",
            }
        )
    return output


def build_prompt_outputs(target: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in target:
        grouped[(row["cohort"], request_direction(row), row["prompt_id"])].append(row)
    rates = []
    for (cohort, direction, prompt_id), rows in sorted(grouped.items()):
        rates.append(
            {
                "cohort": cohort,
                "request_direction": direction,
                "prompt_id": prompt_id,
                "rows": len(rows),
                "apparent_violation_rate": float(np.mean([row["apparent_violation"] for row in rows])),
                "corrected_violation_rate": float(np.mean([row["corrected_violation"] for row in rows])),
                "calibrated_violation_rate": float(np.mean([row["calibrated_violation_probability"] for row in rows])),
                "publication_status": "DRAFT_AWAITING_DUAL_PI_ADOPTION",
            }
        )
    ecdf = []
    for key in sorted({(row["cohort"], row["request_direction"]) for row in rates}):
        group = [row for row in rates if (row["cohort"], row["request_direction"]) == key]
        for metric in ("apparent_violation_rate", "corrected_violation_rate", "calibrated_violation_rate"):
            ordered = sorted(float(row[metric]) for row in group)
            for rank, value in enumerate(ordered, 1):
                ecdf.append(
                    {
                        "cohort": key[0],
                        "request_direction": key[1],
                        "metric": metric,
                        "violation_rate": value,
                        "ecdf": rank / len(ordered),
                        "prompt_count": len(ordered),
                        "publication_status": "DRAFT_AWAITING_DUAL_PI_ADOPTION",
                    }
                )
    return rates, ecdf


def build_figure(rows: list[dict]) -> None:
    import matplotlib.pyplot as plt

    selected = [
        row for row in rows
        if row["cohort"] in {"candidate_spine_4096", "n2_population_retry"}
        and row["condition"] in {"candidate_final", "none"}
    ]
    labels = [f"{row['cohort'].replace('_', ' ')}\n{row['request_direction'].replace('_', ' ')}" for row in selected]
    x = np.arange(len(selected))
    width = 0.25
    fig, axis = plt.subplots(figsize=(11, 5.8))
    axis.bar(x - width, [row["apparent_rate"] for row in selected], width, label="Apparent")
    axis.bar(x, [row["corrected_instrument_rate"] for row in selected], width, label="Corrected instrument")
    axis.bar(x + width, [row["calibrated_rate"] for row in selected], width, label="Calibrated model")
    axis.set_ylabel("Constraint-violation rate")
    axis.set_ylim(0, 1)
    axis.set_xticks(x, labels, rotation=15, ha="right")
    axis.legend(frameon=False)
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURE_PNG, dpi=180)
    fig.savefig(FIGURE_PDF)
    plt.close(fig)


def write_reports(rows: list[dict], fit_audit: dict, bootstrap: dict, promotion: dict) -> None:
    def find(cohort: str, direction: str, condition: str) -> dict:
        return next(
            row for row in rows
            if row["cohort"] == cohort and row["request_direction"] == direction and row["condition"] == condition
        )

    spine_i = find("candidate_spine_4096", "instrumental_request", "candidate_final")
    spine_v = find("candidate_spine_4096", "vocal_request", "candidate_final")
    n2_i = find("n2_population_retry", "instrumental_request", "none")
    n2_v = find("n2_population_retry", "vocal_request", "none")
    REPORT.write_text(
        "# Corrected W2 Recompute\n\n"
        "`RECOMPUTE_STATUS = COMPLETE_DRAFT_AWAITING_ADOPTION`\n\n"
        "The mechanically promoted instrument was applied to all 27,966 target rows. "
        "These are draft supersession values only: the W2 amendment still lacks both "
        "adoption signatures, so PLAN.md, CLAIMS.md, and frozen historical reports were not changed.\n\n"
        "| Cohort / direction | Rows | Apparent | Corrected instrument | Calibrated model | Nested 95% interval |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        + "\n".join(
            f"| {row['cohort']} / {row['request_direction']} | {row['rows']} | {row['apparent_rate']:.4f} | "
            f"{row['corrected_instrument_rate']:.4f} | {row['calibrated_rate']:.4f} | "
            f"[{row['joint_95_interval_low']:.4f}, {row['joint_95_interval_high']:.4f}] |"
            for row in (spine_i, spine_v, n2_i, n2_v)
        )
        + "\n\n"
        f"Calibration model: `{fit_audit['selected']['form']}`, L2={fit_audit['selected']['l2']}; "
        f"selected on the 58 decided train rows only. The {bootstrap['requested_replicates']:,}-replicate "
        "nested bootstrap resamples frozen calibration strata, refits the selected model form, and resamples target prompts.\n\n"
        f"Transport source-specific correction required: `{str(promotion['transport']['any_source_specific_correction_flag']).lower()}`. "
        "Rogan-Gladen direction-stratified estimates are sensitivity analyses, not the primary corrected values.\n",
        encoding="utf-8",
    )
    draft_header = (
        "# Draft Only - Requires Dual-PI W2 Adoption\n\n"
        "This file is not an applied PLAN/CLAIMS change. It records the exact values that may be adopted only after both W2 signatures.\n\n"
    )
    PLAN_DRAFT.write_text(
        draft_header
        + f"- Corrected instrument: `{promotion['heldout']['selected_candidate']['family']}` with held-out design-weighted BA "
        f"{promotion['heldout']['heldout_metrics']['balanced_accuracy']:.6f}.\n"
        + f"- Spine instrumental calibrated violation rate: {spine_i['calibrated_rate']:.6f} "
        f"[{spine_i['joint_95_interval_low']:.6f}, {spine_i['joint_95_interval_high']:.6f}].\n"
        + f"- Spine vocal calibrated violation rate: {spine_v['calibrated_rate']:.6f} "
        f"[{spine_v['joint_95_interval_low']:.6f}, {spine_v['joint_95_interval_high']:.6f}].\n"
        + "- Required wording: instrument-scoped corrected estimates; never present them as ground-truth population rates.\n",
        encoding="utf-8",
    )
    CLAIMS_DRAFT.write_text(
        draft_header
        + "Allowed after adoption: the pre-W2 detector undercounted violations relative to a PI-calibrated Demucs/PANNs instrument on the audited design.\n\n"
        + "Forbidden: generic population rate; proved no loss; causal vocal-generation bias; retrospective hard difficulty bins.\n",
        encoding="utf-8",
    )
    ADOPTION_PACKET.write_text(
        "# Dual-PI W2 Adoption Packet\n\n"
        "`ADOPTION_STATUS = AWAITING_BOTH_PI_SIGNATURES`\n\n"
        f"- W2 amendment: `{AMENDMENT.relative_to(ROOT)}` ({sha256(AMENDMENT)}).\n"
        f"- Promotion report: `{REPORT.parent.parent / 'T6_PROMOTION_REPORT.md'}`.\n"
        f"- Corrected table: `{PUBLICATION_RATES.relative_to(ROOT)}`.\n"
        f"- Draft PLAN update: `{PLAN_DRAFT.relative_to(ROOT)}`.\n"
        f"- Draft CLAIMS update: `{CLAIMS_DRAFT.relative_to(ROOT)}`.\n\n"
        "Both PIs must sign the W2 adoption before applying either draft.\n",
        encoding="utf-8",
    )


def run(replicates: int = BOOTSTRAP_REPLICATES) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    promotion = json.loads(PROMOTION.read_text(encoding="utf-8"))
    if promotion["CORRECTED_INSTRUMENT_STATUS"] != "PROMOTED":
        raise ValueError("corrected recompute requires mechanical PROMOTED status")
    if promotion.get("plan_or_claim_status_changed") is not False:
        raise ValueError("promotion artifact unexpectedly reports a claim-status change")
    calibration = prepare_calibration()
    fit = CAL.select_model(calibration)
    fit_audit = {key: value for key, value in fit.items() if key != "model"}
    target = prepare_targets(promotion["heldout"]["selected_candidate"], fit)
    groups = publication_groups(target)
    intervals, bootstrap = nested_intervals(calibration, target, groups, fit, replicates)
    operating = calibration_operating_characteristics(promotion["heldout"]["selected_candidate"])
    publication = build_publication_rows(target, groups, intervals, operating)
    prompt_rates, prompt_ecdf = build_prompt_outputs(target)
    write_csv(TARGET_ROWS, target)
    write_csv(PUBLICATION_RATES, publication)
    write_csv(PROMPT_RATES, prompt_rates)
    write_csv(PROMPT_ECDF, prompt_ecdf)
    MODEL_AUDIT.write_text(
        json.dumps(
            {
                "status": "TRAIN_ONLY_CALIBRATION_MODEL_FIT",
                "train_rows_total": 60,
                "train_rows_decided": len(calibration),
                "train_rows_abstained": 2,
                "rating_source": "pi:Richard",
                "selection": fit_audit,
                "nested_bootstrap": bootstrap,
                "operating_characteristics": operating,
                "promotion_sha256": sha256(PROMOTION),
                "target_sha256": sha256(TARGET),
                "adoption_status": "BLOCKED_UNTIL_BOTH_W2_SIGNATURES",
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    build_figure(publication)
    write_reports(publication, fit_audit, bootstrap, promotion)
    return {
        "RECOMPUTE_STATUS": "COMPLETE_DRAFT_AWAITING_ADOPTION",
        "target_rows": len(target),
        "publication_rows": len(publication),
        "prompt_rows": len(prompt_rates),
        "bootstrap": bootstrap,
        "selected_model": fit_audit["selected"],
        "outputs": [str(path.relative_to(ROOT)) for path in (
            TARGET_ROWS, PUBLICATION_RATES, PROMPT_RATES, PROMPT_ECDF,
            MODEL_AUDIT, REPORT, PLAN_DRAFT, CLAIMS_DRAFT, ADOPTION_PACKET,
            FIGURE_PNG, FIGURE_PDF,
        )],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
