#!/usr/bin/env python3
"""Independently audit the self-hosted judge against amendment-compliant PI gold."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path


def load_legacy_auditor(root: Path):
    path = root / "paper_prep/scripts/audit_legacy_cxy_t7_20260710.py"
    spec = importlib.util.spec_from_file_location("pi_gold_generic_judge_auditor", path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("judge audit loader is unavailable")
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pi_manifest(path: Path, expected_split: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or any(row.get("rating_source") != "pi:Richard" for row in rows):
        raise ValueError("judge gold must have pi:Richard provenance on every row")
    if any(row.get("true_label") not in {"yes", "no"} for row in rows):
        raise ValueError("judge gold must contain only decided PI labels")
    if any(row.get("split") != expected_split for row in rows):
        raise ValueError(f"judge manifest is not entirely {expected_split}")
    hashes = [row["audio_sha256"] for row in rows]
    if len(hashes) != len(set(hashes)):
        raise ValueError("judge manifest contains duplicate media hashes")
    return rows


def audit(
    root: Path,
    smoke_manifest: Path,
    smoke_raw: Path,
    smoke_summary: Path,
    heldout_manifest: Path,
    heldout_raw: Path,
    heldout_summary: Path,
) -> dict:
    smoke_rows = validate_pi_manifest(smoke_manifest, "calibration")
    heldout_rows = validate_pi_manifest(heldout_manifest, "heldout")
    if {row["audio_sha256"] for row in smoke_rows} & {
        row["audio_sha256"] for row in heldout_rows
    }:
        raise ValueError("smoke and heldout judge media overlap")
    generic = load_legacy_auditor(root)
    smoke = generic.audit(smoke_manifest, smoke_raw, smoke_summary, 3)
    heldout = generic.audit(heldout_manifest, heldout_raw, heldout_summary, 3)
    smoke_accuracy = (
        json.loads(smoke_summary.read_text(encoding="utf-8")).get("accuracy")
    )
    # The signed materials contain no numeric automatic-judge promotion rule,
    # and gates never auto-pass. The 8/10 smoke also misses the earlier 10/10
    # engineering target, so PI_BLOCKED is the only defensible status here.
    return {
        "judge_validation_status": "PI_BLOCKED",
        "status_reason": "PI gold supersedes the CXY-only block, but smoke is 8/10 and no signed automatic-judge promotion threshold exists",
        "model": "qwen3-omni-judge",
        "calls_per_clip": 3,
        "smoke": {**smoke, "accuracy": smoke_accuracy},
        "heldout": heldout,
        "smoke_manifest_sha256": sha256_file(smoke_manifest),
        "heldout_gold_set_hash": sha256_file(heldout_manifest),
        "smoke_raw_sha256": sha256_file(smoke_raw),
        "heldout_raw_sha256": sha256_file(heldout_raw),
        "stratified_500_launched": False,
        "a_prime_gate_changed": False,
    }


def write_report(result: dict, output: Path) -> None:
    smoke = result["smoke"]
    heldout = result["heldout"]
    report = f"""# PI-Gold Self-Hosted Judge Validation

`JUDGE_VALIDATION_STATUS = {result['judge_validation_status']}`

## Result

The amendment-compliant `pi:Richard` labels replace the previous CXY-only
diagnostic basis. Media hashes are disjoint between the balanced smoke and the
held-out split, and the audit independently reconciled every manifest row,
audio SHA-256, raw clip/call key, parser output, majority vote, and summary.

| Metric | Balanced smoke | Held-out PI gold |
|---|---:|---:|
| Clips | {smoke['rows']} | {heldout['rows']} |
| Positive / negative | {smoke['positives']} / {smoke['negatives']} | {heldout['positives']} / {heldout['negatives']} |
| Calls | {smoke['calls']} | {heldout['calls']} |
| Sensitivity | {smoke['sensitivity']:.6f} | {heldout['sensitivity']:.6f} |
| Specificity | {smoke['specificity']:.6f} | {heldout['specificity']:.6f} |
| Balanced accuracy | {smoke['balanced_accuracy']:.6f} | {heldout['balanced_accuracy']:.6f} |
| MCC | {smoke['mcc']:.6f} | {heldout['mcc']:.6f} |
| Abstention rate | {smoke['abstention_rate']:.6f} | {heldout['abstention_rate']:.6f} |

## Status Decision

The held-out diagnostic is strong, but the balanced smoke is 8/10 rather than
the earlier 10/10 engineering target. The signed amendment and standing brief
do not define a numeric automatic-judge promotion threshold, and gates never
auto-pass. `JUDGE_VALIDATION_STATUS` therefore remains `PI_BLOCKED` pending a
PI decision on a promotion rule. The stratified-500 A-prime judge track was not
launched, and no A-prime status changed.

## Evidence

- Smoke manifest: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_SMOKE.csv`
- Held-out manifest: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_HELDOUT.csv`
- Smoke raw ledger: `paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_smoke_20260711.jsonl`
- Held-out raw ledger: `paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_heldout_20260711.jsonl`
- Audit JSON: `paper_prep/pi_ratings_20260711/processed/PI_GOLD_JUDGE_VALIDATION_AUDIT.json`
- Audit script: `paper_prep/scripts/audit_pi_gold_judge_20260711.py`
"""
    output.write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[4]
    processed = root / "paper_prep/pi_ratings_20260711/processed"
    parser.add_argument("--smoke-manifest", type=Path, default=processed / "PI_GOLD_SMOKE.csv")
    parser.add_argument("--smoke-raw", type=Path, default=root / "paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_smoke_20260711.jsonl")
    parser.add_argument("--smoke-summary", type=Path, default=processed / "PI_GOLD_SMOKE_JUDGE_SUMMARY.json")
    parser.add_argument("--heldout-manifest", type=Path, default=processed / "PI_GOLD_HELDOUT.csv")
    parser.add_argument("--heldout-raw", type=Path, default=root / "paper_prep/judge_raw/selfhost_qwen3_omni_pi_gold_heldout_20260711.jsonl")
    parser.add_argument("--heldout-summary", type=Path, default=processed / "PI_GOLD_HELDOUT_JUDGE_SUMMARY.json")
    parser.add_argument("--output-json", type=Path, default=processed / "PI_GOLD_JUDGE_VALIDATION_AUDIT.json")
    parser.add_argument("--output-report", type=Path, default=processed / "PI_GOLD_JUDGE_VALIDATION_REPORT.md")
    args = parser.parse_args()
    result = audit(
        root,
        args.smoke_manifest,
        args.smoke_raw,
        args.smoke_summary,
        args.heldout_manifest,
        args.heldout_raw,
        args.heldout_summary,
    )
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result, args.output_report)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
