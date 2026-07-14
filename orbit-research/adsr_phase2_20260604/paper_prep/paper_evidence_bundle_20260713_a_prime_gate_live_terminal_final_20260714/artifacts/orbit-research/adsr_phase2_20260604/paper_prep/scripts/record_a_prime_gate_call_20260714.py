#!/usr/bin/env python3
"""Record Richard's A-prime gate call against the completed 690-row evidence."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src/mprm").is_dir() and (candidate / "orbit-research").is_dir():
            return candidate
    raise RuntimeError(f"repository root not found from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
PAPER = ROOT / "paper_prep"
GATE_RESULT = PAPER / "validation_A_prime/A_PRIME_GATE_RESULT_20260713.json"
GATE_REPORT = PAPER / "validation_A_prime/A_PRIME_GATE_REPORT_20260713.md"
STUDY_LOG = PAPER / "validation_A_prime/A_PRIME_STUDY_LOG.jsonl"
AUDIT = PAPER / "validation_A_prime/A_PRIME_GATE_CALL_AUDIT_20260713.json"
EXECUTION_LEDGER = PAPER / "t7_judge_gold_20260713/T7_EXECUTION_LEDGER.jsonl"
MERGE_REPORT = PAPER / "t7_judge_gold_20260713/judge_completion/A_PRIME_INSTRUMENT_MERGE_REPORT.json"
JUDGE_REPORT = PAPER / "t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md"
T6_PROMOTION = PAPER / "autochain_20260712/T6_PROMOTION_RESULT.json"
T6_RELIABILITY = PAPER / "autochain_20260712/T6_RELIABILITY_RESULT.json"

GATE = "FAIL_LEGACY_INSTRUMENT_NOT_VALIDATED"
PROVENANCE = "pi:Richard"
DECISION_DATE = "2026-07-13"
EXPECTED_BUCKETS = {
    "detector_disagreement_112": {"rows": 112, "decided": 112, "matches": 7},
    "rare_basin_48": {"rows": 48, "decided": 47, "matches": 16},
    "agreement_spotcheck_30": {"rows": 30, "decided": 30, "matches": 28},
    "stratified_random_500": {"rows": 493, "decided": 493, "matches": 124},
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def append_once(path: Path, row: dict) -> None:
    prior = [item for item in read_jsonl(path) if item.get("event_id") == row["event_id"]]
    if prior:
        if len(prior) != 1 or prior[0] != row:
            raise ValueError(f"conflicting append-only event {row['event_id']} in {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def verify_inputs() -> tuple[dict, dict, dict, dict]:
    result = read_json(GATE_RESULT)
    if result.get("A_PRIME_GATE") not in {"PI_CALL_PENDING", GATE}:
        raise ValueError(f"unexpected prior A-prime status: {result.get('A_PRIME_GATE')}")
    if result.get("instrument_merge_rows") != 690:
        raise ValueError("A-prime instrument merge must contain exactly 690 rows")
    if result.get("instrument_merge_provenance") != {"human": 0, "judge": 500, "pi": 190}:
        raise ValueError("A-prime provenance composition is not 190 PI + 500 validated judge")
    if result.get("judge_validation_status") != "PASS":
        raise ValueError("validated-judge supplement is not in PASS state")
    for name, expected in EXPECTED_BUCKETS.items():
        actual = result["label_a_bucket_results"][name]
        for key, value in expected.items():
            if actual.get(key) != value:
                raise ValueError(f"{name}.{key}: expected {value}, got {actual.get(key)}")
    if result.get("all_frozen_label_a_criteria_met") is not False:
        raise ValueError("PI FAIL call requires the frozen A-prime criteria to be unmet")

    merge = read_json(MERGE_REPORT)
    if merge.get("admin_rows") != 690:
        raise ValueError("merge report does not confirm 690 provenance-enforced rows")
    promotion = read_json(T6_PROMOTION)
    reliability = read_json(T6_RELIABILITY)
    held_out = promotion["heldout"]["heldout_metrics"]
    if promotion.get("CORRECTED_INSTRUMENT_STATUS") != "PROMOTED":
        raise ValueError("T6 corrected instrument is not promoted")
    expected_metrics = {
        "balanced_accuracy": 0.987308,
        "sensitivity": 1.0,
        "specificity": 0.974616,
    }
    for key, expected in expected_metrics.items():
        if abs(float(held_out[key]) - expected) > 5e-7:
            raise ValueError(f"unexpected T6 {key}: {held_out[key]}")
    if reliability["label_a"].get("exact_agreement_count") != 20:
        raise ValueError("T6 Label-A hidden-repeat agreement is not 20/20")
    if reliability["label_b"].get("exact_agreement_count") != 20:
        raise ValueError("T6 Label-B hidden-repeat agreement is not 20/20")
    return result, merge, promotion, reliability


def decision_record(result: dict) -> dict:
    event_id = hashlib.sha256((GATE + PROVENANCE + DECISION_DATE).encode()).hexdigest()[:20]
    buckets = result["label_a_bucket_results"]
    return {
        "event_id": event_id,
        "event": "A_PRIME_PI_GATE_DECISION",
        "A_PRIME_GATE": GATE,
        "provenance": PROVENANCE,
        "decision_date": DECISION_DATE,
        "automatic_pass_forbidden": True,
        "demucs_missing_finding_quantified": True,
        "legacy_instrument": "Demucs-energy threshold 0.1791",
        "legacy_instrument_validated": False,
        "instrument_merge_rows": 690,
        "instrument_merge_provenance": result["instrument_merge_provenance"],
        "label_a_results": {
            name: {
                "matches": buckets[name]["matches"],
                "decided": buckets[name]["decided"],
                "rows": buckets[name]["rows"],
                "match_rate": buckets[name]["match_rate"],
            }
            for name in EXPECTED_BUCKETS
        },
        "scope": "A-prime tests Label A; the signed amendment's paper-primary endpoint is Label B",
        "rationale": (
            "The frozen A-prime criteria test the legacy 0.1791 Demucs-energy "
            "instrument against human gold. The disagreement and rare-basin criteria "
            "fail, quantifying the demucs_missing finding; A-prime is therefore a "
            "falsification study for the legacy instrument, not validation of it."
        ),
        "status": "RECORDED",
    }


def finalized_result(result: dict, decision: dict, promotion: dict, reliability: dict) -> dict:
    finalized = copy.deepcopy(result)
    finalized["A_PRIME_GATE"] = GATE
    finalized["pi_gate_decision"] = decision
    finalized["legacy_instrument_validated"] = False
    finalized["demucs_missing_finding_quantified"] = True
    finalized["label_validity_carried_by"] = "T6 corrected-instrument prospective held-out promotion"
    finalized["t6_corrected_instrument_evidence"] = {
        "status": promotion["CORRECTED_INSTRUMENT_STATUS"],
        "balanced_accuracy": promotion["heldout"]["heldout_metrics"]["balanced_accuracy"],
        "sensitivity": promotion["heldout"]["heldout_metrics"]["sensitivity"],
        "specificity": promotion["heldout"]["heldout_metrics"]["specificity"],
        "label_a_repeat_agreement": [reliability["label_a"]["exact_agreement_count"], 20],
        "label_b_repeat_agreement": [reliability["label_b"]["exact_agreement_count"], 20],
    }
    return finalized


def write_report(result: dict) -> None:
    buckets = result["label_a_bucket_results"]
    decision = result["pi_gate_decision"]
    lines = [
        "# A-Prime Gate Report - PI Decision",
        "",
        f"`A_PRIME_GATE = {GATE}`",
        "",
        "## PI Gate Call",
        "",
        f"- Provenance: `{decision['provenance']}`.",
        f"- Decision date: `{decision['decision_date']}`.",
        "- The 690-row provenance-enforced instrument contains 190 PI human-core rows",
        "  and 500 held-out-validated-judge supplement rows.",
        "- The frozen criteria evaluate the legacy Demucs-energy threshold 0.1791.",
        "- The failed disagreement and rare-basin criteria quantify `demucs_missing`.",
        "- The legacy instrument is **not validated** and must never be described as validated.",
        "",
        "| Set | Reference | Matches/decided | Match rate | Frozen condition met |",
        "|---|---|---:|---:|---:|",
        f"| Detector disagreement | `pi:Richard` | 7/112 | {buckets['detector_disagreement_112']['match_rate']:.6f} | `false` |",
        f"| Rare basin | `pi:Richard` | 16/47 | {buckets['rare_basin_48']['match_rate']:.6f} | `false` |",
        f"| Agreement controls | `pi:Richard` | 28/30 | {buckets['agreement_spotcheck_30']['match_rate']:.6f} | `true` |",
        f"| Stratified global disagreement | validated judge | 124/493 | {buckets['stratified_random_500']['match_rate']:.6f} | outside pass shape |",
        "",
        "## Endpoint Scope And Replacement Instrument",
        "",
        "A-prime measures Label A (perceived voice presence). The signed amendment's",
        "paper-primary endpoint is Label B (request-conditional constraint satisfaction).",
        "A-prime therefore does not validate or invalidate the paper-primary endpoint.",
        "",
        "The positive label-validity evidence is the separate T6 prospective held-out",
        "promotion of the corrected instrument: design-weighted balanced accuracy",
        "0.987308, sensitivity 1.000000, specificity 0.974616, with 20/20 Label-A",
        "and 20/20 Label-B hidden-repeat agreement. This T6 evidence must not be",
        "misreported as an A-prime PASS or as validation of the legacy detector.",
        "",
        "## Evidence",
        "",
        "- `paper_prep/t7_judge_gold_20260713/judge_completion/A_PRIME_INSTRUMENT_MERGED_690.csv`",
        "- `paper_prep/t7_judge_gold_20260713/judge_completion/POOLED_JUDGE_VALIDATION_REPORT.md`",
        "- `paper_prep/autochain_20260712/T6_PROMOTION_REPORT.md`",
        "- `paper_prep/autochain_20260712/T6_RELIABILITY_REPORT.md`",
        "- `paper_prep/validation_A_prime/A_PRIME_STUDY_LOG.jsonl`",
        "",
    ]
    GATE_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run() -> dict:
    result, merge, promotion, reliability = verify_inputs()
    decision = decision_record(result)
    append_once(STUDY_LOG, decision)
    finalized = finalized_result(result, decision, promotion, reliability)
    write_json(GATE_RESULT, finalized)
    write_report(finalized)

    audit = {
        "status": "PASS",
        "A_PRIME_GATE": GATE,
        "decision_provenance": PROVENANCE,
        "decision_date": DECISION_DATE,
        "decision_event_id": decision["event_id"],
        "decision_event_count": sum(
            row.get("event") == "A_PRIME_PI_GATE_DECISION" for row in read_jsonl(STUDY_LOG)
        ),
        "instrument_merge_rows": merge["admin_rows"],
        "instrument_merge_provenance": finalized["instrument_merge_provenance"],
        "legacy_instrument_validated": False,
        "demucs_missing_finding_quantified": True,
        "t6_corrected_instrument_status": promotion["CORRECTED_INSTRUMENT_STATUS"],
        "gate_report_sha256": sha256_file(GATE_REPORT),
        "gate_result_sha256": sha256_file(GATE_RESULT),
        "study_log_sha256": sha256_file(STUDY_LOG),
        "input_hashes": {
            str(MERGE_REPORT.relative_to(ROOT)): sha256_file(MERGE_REPORT),
            str(JUDGE_REPORT.relative_to(ROOT)): sha256_file(JUDGE_REPORT),
            str(T6_PROMOTION.relative_to(ROOT)): sha256_file(T6_PROMOTION),
            str(T6_RELIABILITY.relative_to(ROOT)): sha256_file(T6_RELIABILITY),
        },
    }
    write_json(AUDIT, audit)

    execution_event_id = "a-prime-gate-call-20260713-pi-richard"
    prior_execution = [
        row for row in read_jsonl(EXECUTION_LEDGER) if row.get("event_id") == execution_event_id
    ]
    execution_timestamp = (
        prior_execution[0]["timestamp"]
        if len(prior_execution) == 1
        else dt.datetime.now().astimezone().isoformat(timespec="seconds")
    )
    execution_event = {
        "event_id": execution_event_id,
        "timestamp": execution_timestamp,
        "host": "local",
        "command": "python paper_prep/scripts/record_a_prime_gate_call_20260714.py",
        "input_artifacts": [str(MERGE_REPORT), str(T6_PROMOTION), str(T6_RELIABILITY)],
        "output_artifacts": [str(GATE_REPORT), str(GATE_RESULT), str(STUDY_LOG), str(AUDIT)],
        "status": "PASS",
        "next_action": "Update live PLAN/CLAIMS wording; preserve signature gates.",
    }
    append_once(EXECUTION_LEDGER, execution_event)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
