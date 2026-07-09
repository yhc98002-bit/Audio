"""H3a launch preflight checks.

This script performs config-only checks before any Phase B.3 H3a launch. It
does not sample, segment, score, or write experiment outputs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def _fail(message: str) -> None:
    raise SystemExit(f"H3a preflight FAIL: {message}")


def _targets(checkpoints: list[dict]) -> list[float]:
    return [float(x["target"]) for x in checkpoints]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/runs/phase_b3_credit_unit_comparison.yaml")
    parser.add_argument(
        "--pi-approved-launch",
        action="store_true",
        help="Required dual-lock CLI acknowledgement for H3a launch.",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text())

    if not args.pi_approved_launch:
        _fail("--pi-approved-launch CLI flag is required")
    if cfg.get("pi_approved_binding") is not True:
        _fail("pi_approved_binding is not true")
    if cfg.get("pi_approved_launch") is not True:
        _fail("pi_approved_launch is not true")

    h3a = cfg["prompts"]["h3a_dev"]
    if h3a.get("reuses_phase_b1_intermediates") is not False:
        _fail("H3a must not claim reusable Phase B.1 audio intermediates")
    if h3a.get("requires_fresh_sampling") is not True:
        _fail("H3a must require fresh sampling")

    held_out = cfg["prompts"]["held_out_256"]
    if held_out.get("role") != "CONDITIONAL_ON_H3A_TREND_OR_PI_APPROVAL":
        _fail("held_out_256 is not conditional")

    policy = cfg["reliability_curve_policy"]
    if _targets(policy.get("primary_h3_checkpoints", [])) != [0.7, 0.6]:
        _fail("primary H3 checkpoints must be exactly [0.7, 0.6]")
    if _targets(policy.get("appendix_only_optional", [])) != [0.8]:
        _fail("sigma 0.8 must be appendix-only")

    interpretation = cfg["h3_interpretation"]
    if interpretation.get("gating_axes") != ["musicality", "coherence", "prompt_fit"]:
        _fail("H3 gating axes must be exactly musicality/coherence/prompt_fit")
    pools = interpretation.get("best_non_section_pool_by_stratum", {})
    if "CU-LS" not in pools.get("vocal", []):
        _fail("vocal stratum must include CU-LS in the non-section pool")
    if "CU-LS" in pools.get("instrumental", []):
        _fail("instrumental stratum must exclude CU-LS")

    stratum = cfg["outputs"].get("stratum_results", {})
    if float(stratum.get("kendall_tau_min_for_combined", -1.0)) < 0.5:
        _fail("combined output requires Kendall tau threshold >= 0.5")

    ambiguous = interpretation["tiered_interpretation"]["AMBIGUOUS"].get("action", "")
    if "No automatic 128-dev escalation" not in ambiguous:
        _fail("AMBIGUOUS routing must not auto-use the Phase B.1 expansion prompts")

    print(f"H3a preflight PASS: {cfg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
