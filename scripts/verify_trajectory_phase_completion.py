"""Verify trajectory-aware phase completion from current artifacts."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


OUT_JSON = Path("orbit-research/TRAJECTORY_PHASE_COMPLETION_CHECK_2026-05-28.json")
OUT_MD = Path("orbit-research/TRAJECTORY_PHASE_COMPLETION_CHECK_2026-05-28.md")


REQUIRED_FILES = [
    "orbit-research/trajectory_candidate_dataset.jsonl",
    "orbit-research/TRAJECTORY_CANDIDATE_DATASET_CARD.md",
    "orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.md",
    "orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.json",
    "orbit-research/EARLY_TWEEDIE_PARETO.csv",
    "orbit-research/EARLY_TWEEDIE_AXIS_BREAKDOWN.csv",
    "orbit-research/EARLY_TWEEDIE_STRATUM_BREAKDOWN.csv",
    "orbit-research/EARLY_TWEEDIE_CROSS_AXIS_GENERALIZATION.csv",
    "orbit-research/EARLY_TWEEDIE_BON4_BOOTSTRAP.csv",
    "orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.md",
    "orbit-research/EARLY_TRAJECTORY_VERIFIER_RESULTS.json",
    "orbit-research/EARLY_VALUE_FEATURE_IMPORTANCE.csv",
    "orbit-research/RISK_CONTROLLED_PRUNING_TABLE.csv",
    "orbit-research/BON16_PRUNING_SUBSET_RESULTS.md",
    "orbit-research/BON16_PRUNING_SUBSET_RESULTS.json",
    "orbit-research/BON16_PRUNING_SUBSET_RESULTS.csv",
    "orbit-research/human_spotcheck_packet_20260528/HUMAN_SPOTCHECK_PACKET_MANIFEST.md",
    "orbit-research/human_spotcheck_packet_20260528/human_spotcheck_pairs.with_audio.jsonl",
    "orbit-research/GLOBAL_QUALITY_MECHANISM_FIGURES.md",
    "orbit-research/GLOBAL_QUALITY_MECHANISM_TABLES.csv",
    "orbit-research/ICLR_REVIEWER_RISK_AUDIT.md",
    "orbit-research/CLAUDE_AUDIT_1_DATASET_LEAKAGE_2026-05-28.json",
    "orbit-research/CLAUDE_AUDIT_2_BASELINE_FAIRNESS_2026-05-28.json",
    "orbit-research/CLAUDE_AUDIT_3_LEARNED_ETV_RISK_2026-05-28.json",
    "orbit-research/TRAJECTORY_AWARE_FINAL_PI_REPORT_2026-05-28.md",
]


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_verdict(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    obj = _read_json(path) or {}
    text = str(obj.get("result") or obj.get("response") or obj)
    match = re.search(r"\b(ACCEPT_WITH_NONBLOCKING_NOTES|ACCEPT|REJECT)\b", text)
    return match.group(1) if match else "UNKNOWN"


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _check_audio_pairs(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "pairs": 0, "present_pairs": 0, "missing_files": []}
    pairs = []
    missing = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                pairs.append(row)
                for side in ("left", "right"):
                    audio = row.get(f"{side}_audio_path")
                    if not audio or not Path(audio).exists():
                        missing.append({"pair_id": row.get("pair_id"), "side": side, "audio_path": audio})
    present_pairs = sum(1 for row in pairs if row.get("audio_status") == "present")
    return {
        "status": "pass" if pairs and not missing and present_pairs == len(pairs) else "incomplete",
        "pairs": len(pairs),
        "present_pairs": present_pairs,
        "missing_files": missing[:20],
    }


def main() -> int:
    checks: dict[str, Any] = {
        "generated_utc": _now_utc(),
        "required_files": {},
        "quantitative": {},
        "audits": {},
        "audio": {},
        "safety": {},
    }

    for name in REQUIRED_FILES:
        path = Path(name)
        checks["required_files"][name] = {"exists": path.exists(), "size": path.stat().st_size if path.exists() else 0}

    dataset_count = _count_jsonl(Path("orbit-research/trajectory_candidate_dataset.jsonl"))
    main = _read_json(Path("orbit-research/EARLY_TWEEDIE_MAIN_RESULTS.json")) or {}
    bon16 = _read_json(Path("orbit-research/BON16_PRUNING_SUBSET_RESULTS.json")) or {}
    checks["quantitative"] = {
        "dataset_candidates": dataset_count,
        "main_prompts": main.get("n_prompts"),
        "main_candidates": main.get("n_candidates"),
        "bon16_prompts": bon16.get("n_prompts"),
        "bon16_candidates": bon16.get("n_candidates"),
    }

    for key, path in {
        "dataset_leakage": Path("orbit-research/CLAUDE_AUDIT_1_DATASET_LEAKAGE_2026-05-28.json"),
        "baseline_fairness": Path("orbit-research/CLAUDE_AUDIT_2_BASELINE_FAIRNESS_2026-05-28.json"),
        "learned_etv_risk": Path("orbit-research/CLAUDE_AUDIT_3_LEARNED_ETV_RISK_2026-05-28.json"),
    }.items():
        checks["audits"][key] = _audit_verdict(path)

    checks["audio"] = _check_audio_pairs(Path("orbit-research/human_spotcheck_packet_20260528/human_spotcheck_pairs.with_audio.jsonl"))

    safety = {}
    for payload in (main, bon16):
        for key, value in (payload.get("safety") or {}).items():
            safety[key] = safety.get(key, False) or bool(value)
    checks["safety"] = safety

    file_pass = all(item["exists"] and item["size"] > 0 for item in checks["required_files"].values())
    quantity_pass = (
        checks["quantitative"]["dataset_candidates"] == 4096
        and checks["quantitative"]["main_prompts"] == 512
        and checks["quantitative"]["main_candidates"] == 4096
        and checks["quantitative"]["bon16_prompts"] == 128
        and checks["quantitative"]["bon16_candidates"] == 2048
    )
    audit_pass = all(v in {"ACCEPT", "ACCEPT_WITH_NONBLOCKING_NOTES"} for v in checks["audits"].values())
    audio_pass = checks["audio"]["status"] == "pass"
    safety_pass = not any(
        safety.get(key)
        for key in (
            "rl_training_launched",
            "pruning_rl_launched",
            "phase_d_launched",
            "human_crowdsourcing_launched",
            "gate_v1_modified",
            "reward_definitions_changed",
            "prompt_splits_changed",
        )
    )
    checks["status"] = "PASS" if file_pass and quantity_pass and audit_pass and audio_pass and safety_pass else "INCOMPLETE"
    checks["summary"] = {
        "file_pass": file_pass,
        "quantity_pass": quantity_pass,
        "audit_pass": audit_pass,
        "audio_pass": audio_pass,
        "safety_pass": safety_pass,
    }

    OUT_JSON.write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Trajectory Phase Completion Check",
        "",
        f"Generated UTC: `{checks['generated_utc']}`",
        f"Status: `{checks['status']}`",
        "",
        "| check | pass |",
        "|---|---:|",
    ]
    for key, value in checks["summary"].items():
        lines.append(f"| {key} | `{value}` |")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- JSON: `{OUT_JSON}`",
            f"- Audio pairs present: `{checks['audio'].get('present_pairs')}/{checks['audio'].get('pairs')}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": checks["status"], "json": str(OUT_JSON), "md": str(OUT_MD)}, indent=2))
    return 0 if checks["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
