"""Audit paired Phase C M-FixedWin/M-Section configs.

The scientific/training setup must be identical except for the selected
credit unit. Non-scientific identifiers and output directories may differ.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _drop_path(obj: Any, path: tuple[str, ...]) -> None:
    cur = obj
    for key in path[:-1]:
        if not isinstance(cur, dict) or key not in cur:
            return
        cur = cur[key]
    if isinstance(cur, dict):
        cur.pop(path[-1], None)


def _normalized(cfg: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(cfg)
    for path in [
        ("schema_version",),
        ("generated",),
        ("run_id",),
        ("method",),
        ("credit_unit",),
        ("firstwave", "output_dir"),
        ("smoke", "output_dir"),
        ("smoke", "exercises"),
        ("implementation_status", "launch_script"),
    ]:
        _drop_path(out, path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixedwin", default="configs/runs/phase_c_m_fixedwin_firstwave.yaml")
    parser.add_argument("--section", default="configs/runs/phase_c_m_section_diagnostic.yaml")
    parser.add_argument("--out", default="runs/phase_c_diagnostic_bundle/pairing_audit.json")
    args = parser.parse_args()

    fixed_path = Path(args.fixedwin)
    section_path = Path(args.section)
    fixed = _load(fixed_path)
    section = _load(section_path)
    failures: list[str] = []

    if fixed.get("method", {}).get("name") != "M-FixedWin-PRM":
        failures.append("fixed config method.name is not M-FixedWin-PRM")
    if section.get("method", {}).get("name") != "M-Section-PRM":
        failures.append("section config method.name is not M-Section-PRM")
    if fixed.get("credit_unit", {}).get("primary", {}).get("name") != "fixed_window":
        failures.append("fixed config credit unit is not fixed_window")
    if section.get("credit_unit", {}).get("primary", {}).get("name") != "musical_section":
        failures.append("section config credit unit is not musical_section")

    if _normalized(fixed) != _normalized(section):
        failures.append(
            "configs differ outside allowed non-scientific identifiers/output dirs and credit_unit"
        )

    report = {
        "schema_version": "phase_c_pairing_audit_v1",
        "fixedwin_config": str(fixed_path),
        "section_config": str(section_path),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "allowed_differences": [
            "schema_version",
            "generated",
            "run_id",
            "method",
            "credit_unit",
            "firstwave.output_dir",
            "smoke.output_dir",
            "smoke.exercises",
            "implementation_status.launch_script",
        ],
        "paired_fields_checked": [
            "scope",
            "compute_policy",
            "sampler",
            "sigma_policy",
            "reward_policy",
            "firstwave excluding output_dir",
            "smoke excluding output_dir/exercises",
            "implementation_status excluding launch_script",
        ],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"pairing_audit={report['status']} wrote {out_path}")
    for failure in failures:
        print(f"  - {failure}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
