"""Unit tests for the H3a STEP-1 driver pure-Python logic.

The driver itself lives at ``scripts/phase_b3_credit_unit_comparison.py`` and
factors all GPU operations into named stub functions that raise
NotImplementedError until STEP-2 lands. These tests exercise the
launch-time-relevant logic *without* GPU:

  - dual-lock config validation (D1/D4/D3 enforcement at load time)
  - prompt-disjointness check
  - Spearman + Kendall-τ helpers
  - per-stratum result aggregation (vocal vs instrumental pool routing)
  - H3a tier classification (FAIL / AMBIGUOUS / PROVISIONAL_PASS_PENDING_HELD_OUT
    + null-sanity violations + held-out promotion path)
  - Kendall-τ combined-overall gate (D3 strict-strata default)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import phase_b3_credit_unit_comparison as h3 # noqa: E402


# ============================================================================
# Helpers + fixtures
# ============================================================================


_BASE_YAML = """\
schema_version: phase_b3_credit_unit_comparison_v1
pi_approved_binding: true
pi_approved_launch: true

prompts:
  h3a_dev:
    formal_prompt_ids_json: "{formal_ids_path}"
  exclusions:
    source_jsons:
      - "{cal_ids_path}"
      - "{expansion_ids_path}"

reliability_curve_policy:
  primary_h3_checkpoints:
    - target: 0.7
    - target: 0.6
  excluded:
    - 0.9
    - 0.5
    - 0.3
    - 0.1

h3_interpretation:
  threshold_section_minus_best_non_section: 0.08
  gating_axes:
    - musicality
    - coherence
    - prompt_fit
  best_non_section_pool_by_stratum:
    vocal: ["CU-TS", "CU-FW", "CU-BW", "CU-LS"]
    instrumental: ["CU-TS", "CU-FW", "CU-BW"]

outputs:
  stratum_results:
    kendall_tau_min_for_combined: 0.5
"""


def _write_prompt_jsons(tmp_path: Path, formal_ids: list[str], cal_ids: list[str], exp_ids: list[str]) -> tuple[Path, Path, Path]:
    formal = tmp_path / "formal.json"
    cal = tmp_path / "cal.json"
    exp = tmp_path / "exp.json"
    formal.write_text(json.dumps({"formal_prompt_ids": formal_ids}))
    cal.write_text(json.dumps({"excluded_prompt_ids": cal_ids}))
    exp.write_text(json.dumps({"formal_prompt_ids": exp_ids}))
    return formal, cal, exp


def _build_cfg_file(tmp_path: Path, *, formal_ids: list[str] | None = None,
                    cal_ids: list[str] | None = None,
                    exp_ids: list[str] | None = None,
                    overrides: dict | None = None) -> Path:
    f_ids = formal_ids if formal_ids is not None else ["a", "b", "c"]
    c_ids = cal_ids if cal_ids is not None else ["x", "y"]
    e_ids = exp_ids if exp_ids is not None else ["p", "q"]
    formal_path, cal_path, exp_path = _write_prompt_jsons(tmp_path, f_ids, c_ids, e_ids)
    raw = _BASE_YAML.format(
        formal_ids_path=str(formal_path),
        cal_ids_path=str(cal_path),
        expansion_ids_path=str(exp_path),
    )
    cfg = yaml.safe_load(raw)
    if overrides:
        # Shallow merge: caller supplies top-level keys to override.
        for k, v in overrides.items():
            cfg[k] = v
    out = tmp_path / "phase_b3.yaml"
    out.write_text(yaml.safe_dump(cfg))
    return out


# ============================================================================
# Spearman + Kendall-τ
# ============================================================================


def test_spearman_perfect_positive():
    assert h3.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_spearman_perfect_negative():
    assert h3.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_short_returns_nan():
    r = h3.spearman([1.0], [1.0])
    assert r != r  # NaN


def test_spearman_fully_constant_input_returns_nan_after_step2_guard():
    """Phase B.1's rank-by-index spearman returned 1.0 on fully-constant
    input (the four equal x's ranked 0,1,2,3 by index). The STEP-2 Codex
    fix added a fully-constant guard: if either input has min == max, return
    NaN instead. Ordinary ties (some but not all values equal) still use
    rank-by-index for Phase B.1 backward compat.
    """
    r = h3.spearman([1, 1, 1, 1], [1, 2, 3, 4])
    assert r != r  # NaN — fully-constant short-circuit


def test_kendall_tau_full_concordance():
    assert h3.kendall_tau([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_kendall_tau_full_discordance():
    assert h3.kendall_tau([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_kendall_tau_mixed():
    # rank x = [0,1,2,3], rank y = [0,1,3,2]: 1 swap → τ = (5−1)/6 ≈ 0.667
    tau = h3.kendall_tau([1, 2, 3, 4], [10, 20, 40, 30])
    assert tau == pytest.approx((6 - 2 * 1) / 6)


# ============================================================================
# Dual-lock + D-policy config validation
# ============================================================================


def test_dual_lock_blocks_when_cli_flag_missing(tmp_path):
    cfg_path = _build_cfg_file(tmp_path)
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=False)
    assert any("CLI flag" in f for f in fails)


def test_dual_lock_blocks_when_pi_approved_binding_false(tmp_path):
    cfg_path = _build_cfg_file(
        tmp_path, overrides={"pi_approved_binding": False, "pi_approved_launch": True}
    )
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("pi_approved_binding" in f for f in fails)


def test_dual_lock_blocks_when_pi_approved_launch_false(tmp_path):
    cfg_path = _build_cfg_file(
        tmp_path, overrides={"pi_approved_binding": True, "pi_approved_launch": False}
    )
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("pi_approved_launch" in f for f in fails)


def test_dual_lock_passes_when_all_three_satisfied(tmp_path):
    cfg_path = _build_cfg_file(tmp_path)
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert fails == []


def test_d4_sigma_policy_rejects_extra_primary(tmp_path):
    overrides = {
        "reliability_curve_policy": {
            "primary_h3_checkpoints": [
                {"target": 0.7}, {"target": 0.6}, {"target": 0.8},
            ],
            "excluded": [0.9, 0.5, 0.3, 0.1],
        }
    }
    cfg_path = _build_cfg_file(tmp_path, overrides=overrides)
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("primary_h3_checkpoints σ set" in f for f in fails)


def test_d4_sigma_policy_rejects_missing_excluded(tmp_path):
    overrides = {
        "reliability_curve_policy": {
            "primary_h3_checkpoints": [{"target": 0.7}, {"target": 0.6}],
            "excluded": [0.5, 0.3, 0.1],  # missing 0.9
        }
    }
    cfg_path = _build_cfg_file(tmp_path, overrides=overrides)
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("σ=0.9 should be in" in f for f in fails)


def test_d3_pool_rejects_lyric_span_in_instrumental_pool(tmp_path):
    overrides = {
        "h3_interpretation": {
            "threshold_section_minus_best_non_section": 0.08,
            "gating_axes": ["musicality", "coherence", "prompt_fit"],
            "best_non_section_pool_by_stratum": {
                "vocal": ["CU-TS", "CU-FW", "CU-BW", "CU-LS"],
                # CU-LS smuggled into instrumental → must FAIL validation
                "instrumental": ["CU-TS", "CU-FW", "CU-BW", "CU-LS"],
            },
        }
    }
    cfg_path = _build_cfg_file(tmp_path, overrides=overrides)
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("instrumental pool" in f and "CU-LS" in f for f in fails)


def test_d3_pool_rejects_missing_lyric_span_from_vocal_pool(tmp_path):
    overrides = {
        "h3_interpretation": {
            "threshold_section_minus_best_non_section": 0.08,
            "gating_axes": ["musicality", "coherence", "prompt_fit"],
            "best_non_section_pool_by_stratum": {
                # CU-LS missing → must FAIL: D3 says vocal uses lyric_span normally.
                "vocal": ["CU-TS", "CU-FW", "CU-BW"],
                "instrumental": ["CU-TS", "CU-FW", "CU-BW"],
            },
        }
    }
    cfg_path = _build_cfg_file(tmp_path, overrides=overrides)
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("vocal pool" in f for f in fails)


def test_prompt_disjointness_detects_overlap(tmp_path):
    # Put one prompt id in both formal and cal — must FAIL.
    cfg_path = _build_cfg_file(
        tmp_path,
        formal_ids=["dev_0000", "dev_0001"],
        cal_ids=["dev_0001"],  # overlap
        exp_ids=[],
    )
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert any("disjoint" in f.lower() or "∩" in f for f in fails)


def test_prompt_disjointness_passes_when_disjoint(tmp_path):
    cfg_path = _build_cfg_file(
        tmp_path,
        formal_ids=["a", "b"],
        cal_ids=["c", "d"],
        exp_ids=["e", "f"],
    )
    _, fails = h3.load_and_validate_config(cfg_path, pi_approved_launch_cli=True)
    assert fails == []


# ============================================================================
# Aggregation + stratum routing
# ============================================================================


def _fake_perfect_record(prompt_id: str, *, is_instrumental: bool, ls_applicable: bool = True) -> dict:
    """One per-prompt record where CU-MS perfectly matches the human proxy
    and every non-section unit has scrambled proxy (low Spearman)."""
    delta = [0.1, 0.2, 0.3, 0.4]
    proxy_match = [0.1, 0.2, 0.3, 0.4]
    proxy_scramble = [0.3, 0.1, 0.4, 0.2]
    axes = {
        "musicality": {"0.7": (delta, proxy_match), "0.6": (delta, proxy_match)},
        "coherence":  {"0.7": (delta, proxy_match), "0.6": (delta, proxy_match)},
        "prompt_fit": {"0.6": (delta, proxy_match)},
    }
    def _axis_block(use_match: bool):
        return {
            "musicality": {s: {"section_reward_delta_vector": d,
                                "human_pref_proxy_vector": (proxy_match if use_match else proxy_scramble)}
                            for s, (d, _) in axes["musicality"].items()},
            "coherence":  {s: {"section_reward_delta_vector": d,
                                "human_pref_proxy_vector": (proxy_match if use_match else proxy_scramble)}
                            for s, (d, _) in axes["coherence"].items()},
            "prompt_fit": {s: {"section_reward_delta_vector": d,
                                "human_pref_proxy_vector": (proxy_match if use_match else proxy_scramble)}
                            for s, (d, _) in axes["prompt_fit"].items()},
        }

    per_unit = {
        "CU-TS": {"applicable": True, **_axis_block(use_match=False)},
        "CU-FW": {"applicable": True, **_axis_block(use_match=False)},
        "CU-BW": {"applicable": True, **_axis_block(use_match=False)},
        "CU-MS": {"applicable": True, **_axis_block(use_match=True)},
        "CU-NULL-rand-section": {"applicable": True, **_axis_block(use_match=False)},
    }
    if ls_applicable and not is_instrumental:
        per_unit["CU-LS"] = {"applicable": True, **_axis_block(use_match=False)}
    else:
        per_unit["CU-LS"] = {"applicable": False, "not_applicable_reason": "instrumental"}
    return {
        "prompt_id": prompt_id,
        "is_instrumental": is_instrumental,
        "per_unit": per_unit,
    }


def test_aggregation_cu_ms_dominates_when_proxy_matches_section_delta():
    recs = [_fake_perfect_record(f"v{i}", is_instrumental=False) for i in range(4)]
    rho = h3.aggregate_per_axis_unit_rho(
        recs, axes=["musicality", "coherence", "prompt_fit"],
        units=["CU-TS", "CU-FW", "CU-BW", "CU-LS", "CU-MS", "CU-NULL-rand-section"],
        sigma_targets=[0.7, 0.6],
    )
    # CU-MS should be ρ=1.0 (perfect match across all axes).
    assert rho["musicality"]["CU-MS"] == pytest.approx(1.0)
    # Non-section units should be lower.
    for u in ("CU-TS", "CU-FW", "CU-BW", "CU-LS"):
        assert rho["musicality"][u] < rho["musicality"]["CU-MS"]


def test_stratum_pool_excludes_section_and_null():
    recs = [_fake_perfect_record(f"v{i}", is_instrumental=False) for i in range(4)]
    res = h3.compute_stratum_result(
        per_prompt_records=recs, stratum="vocal",
        pool_units=["CU-TS", "CU-FW", "CU-BW", "CU-LS"],
        section_unit="CU-MS", null_unit="CU-NULL-rand-section",
        gating_axes=["musicality", "coherence", "prompt_fit"],
        sigma_targets=[0.7, 0.6],
    )
    assert "CU-MS" not in res.pool
    assert "CU-NULL-rand-section" not in res.pool
    assert set(res.pool) == {"CU-TS", "CU-FW", "CU-BW", "CU-LS"}


def test_stratum_section_minus_best_positive_when_cu_ms_dominates():
    recs = [_fake_perfect_record(f"v{i}", is_instrumental=False) for i in range(4)]
    res = h3.compute_stratum_result(
        per_prompt_records=recs, stratum="vocal",
        pool_units=["CU-TS", "CU-FW", "CU-BW", "CU-LS"],
        section_unit="CU-MS", null_unit="CU-NULL-rand-section",
        gating_axes=["musicality", "coherence", "prompt_fit"],
        sigma_targets=[0.7, 0.6],
    )
    for axis in ("musicality", "coherence", "prompt_fit"):
        assert res.section_minus_best_non_section_per_axis[axis] >= 0.08, (
            f"axis={axis} delta={res.section_minus_best_non_section_per_axis[axis]}"
        )


def test_instrumental_stratum_excludes_cu_ls_from_pool():
    recs = [_fake_perfect_record(f"i{i}", is_instrumental=True) for i in range(4)]
    res = h3.compute_stratum_result(
        per_prompt_records=recs, stratum="instrumental",
        pool_units=["CU-TS", "CU-FW", "CU-BW"],  # NO CU-LS per D3
        section_unit="CU-MS", null_unit="CU-NULL-rand-section",
        gating_axes=["musicality", "coherence", "prompt_fit"],
        sigma_targets=[0.7, 0.6],
    )
    assert "CU-LS" not in res.pool
    # CU-LS is not applicable on instrumental records → aggregate ρ is NaN
    rho = res.per_axis_per_unit_rho
    assert all(rho[ax].get("CU-LS", float("nan")) != rho[ax].get("CU-LS", float("nan"))
                for ax in ("musicality", "coherence", "prompt_fit"))


# ============================================================================
# Tier classification
# ============================================================================


def _strong_stratum(stratum: str, *, n_axes_strict: int = 3, null_violation: float = -1.0) -> h3.StratumResult:
    """Build a synthetic StratumResult passing strict on n_axes_strict axes."""
    axes = ["musicality", "coherence", "prompt_fit"]
    section_minus = {ax: 0.20 if i < n_axes_strict else 0.0
                     for i, ax in enumerate(axes)}
    return h3.StratumResult(
        stratum=stratum, n_prompts=4,
        section_minus_best_non_section_per_axis=section_minus,
        best_non_section_unit_per_axis={ax: "CU-TS" for ax in axes},
        n_axes_passing_strict=n_axes_strict,
        n_axes_passing_directional=n_axes_strict,
        null_section_minus_best_non_section_per_axis={ax: null_violation for ax in axes},
        null_max_violation=null_violation,
        unit_rankings=["CU-MS", "CU-TS", "CU-FW", "CU-BW", "CU-LS"]
            if stratum == "vocal" else ["CU-MS", "CU-TS", "CU-FW", "CU-BW"],
        pool=["CU-TS", "CU-FW", "CU-BW", "CU-LS"] if stratum == "vocal"
            else ["CU-TS", "CU-FW", "CU-BW"],
        per_axis_per_unit_rho={ax: {} for ax in axes},
    )


def _ambiguous_stratum(stratum: str) -> h3.StratumResult:
    axes = ["musicality", "coherence", "prompt_fit"]
    section_minus = {ax: 0.06 for ax in axes}  # in [0.05, 0.08]
    return h3.StratumResult(
        stratum=stratum, n_prompts=4,
        section_minus_best_non_section_per_axis=section_minus,
        best_non_section_unit_per_axis={ax: "CU-TS" for ax in axes},
        n_axes_passing_strict=0,
        n_axes_passing_directional=3,
        null_section_minus_best_non_section_per_axis={ax: -1.0 for ax in axes},
        null_max_violation=-1.0,
        unit_rankings=["CU-MS", "CU-TS", "CU-FW", "CU-BW"],
        pool=[],
        per_axis_per_unit_rho={ax: {} for ax in axes},
    )


def _fail_stratum(stratum: str) -> h3.StratumResult:
    axes = ["musicality", "coherence", "prompt_fit"]
    section_minus = {ax: -0.05 for ax in axes}
    return h3.StratumResult(
        stratum=stratum, n_prompts=4,
        section_minus_best_non_section_per_axis=section_minus,
        best_non_section_unit_per_axis={ax: "CU-TS" for ax in axes},
        n_axes_passing_strict=0,
        n_axes_passing_directional=0,
        null_section_minus_best_non_section_per_axis={ax: -1.0 for ax in axes},
        null_max_violation=-1.0,
        unit_rankings=["CU-TS", "CU-FW", "CU-BW", "CU-MS"],
        pool=[],
        per_axis_per_unit_rho={ax: {} for ax in axes},
    )


def test_classify_provisional_pass_when_both_strata_pass_strict_dev_only():
    v = _strong_stratum("vocal")
    i = _strong_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=None)
    assert res["overall_tier"] == h3.TIER_PROVISIONAL_PASS_PENDING_HELD_OUT


def test_classify_fail_when_any_stratum_fails():
    v = _strong_stratum("vocal")
    i = _fail_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=None)
    assert res["overall_tier"] == h3.TIER_FAIL


def test_classify_ambiguous_when_any_stratum_ambiguous():
    v = _strong_stratum("vocal")
    i = _ambiguous_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=None)
    assert res["overall_tier"] == h3.TIER_AMBIGUOUS


def test_classify_null_sanity_violation_demotes_to_fail():
    v = _strong_stratum("vocal", null_violation=0.10)  # null beat best non-MS
    i = _strong_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=None)
    assert res["overall_tier"] == h3.TIER_FAIL
    assert res["null_sanity_violated_strict"] is True


def test_classify_null_near_threshold_flagged():
    v = _strong_stratum("vocal", null_violation=0.05)  # within +0.04 of 0.08
    i = _strong_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=None)
    assert res["null_sanity_violated_strict"] is False
    assert res["null_sanity_near_threshold"] is True


def test_classify_strong_pass_when_held_out_also_passes_strict():
    v = _strong_stratum("vocal")
    i = _strong_stratum("instrumental")
    ho_v = _strong_stratum("vocal")
    ho_i = _strong_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=(ho_v, ho_i))
    assert res["overall_tier"] in (h3.TIER_STRONG_PASS, h3.TIER_STRONG_PASS_WITH_NULL_NOTES)


def test_classify_supported_pass_when_held_out_only_directional():
    v = _strong_stratum("vocal")
    i = _strong_stratum("instrumental")
    ho_v = _ambiguous_stratum("vocal")
    ho_i = _ambiguous_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=(ho_v, ho_i))
    assert res["overall_tier"] == h3.TIER_SUPPORTED_PASS


def test_classify_ambiguous_when_held_out_fails_to_support():
    v = _strong_stratum("vocal")
    i = _strong_stratum("instrumental")
    ho_v = _fail_stratum("vocal")
    ho_i = _fail_stratum("instrumental")
    res = h3.classify_h3a_tier(v, i, held_out=(ho_v, ho_i))
    assert res["overall_tier"] == h3.TIER_AMBIGUOUS


# ============================================================================
# Kendall-τ combined-overall gate (D3)
# ============================================================================


def test_kendall_combined_emits_when_rankings_agree():
    v = _strong_stratum("vocal")
    # Strip CU-LS from vocal rankings so the common set is comparable.
    v_no_ls = h3.StratumResult(
        stratum=v.stratum, n_prompts=v.n_prompts,
        section_minus_best_non_section_per_axis=v.section_minus_best_non_section_per_axis,
        best_non_section_unit_per_axis=v.best_non_section_unit_per_axis,
        n_axes_passing_strict=v.n_axes_passing_strict,
        n_axes_passing_directional=v.n_axes_passing_directional,
        null_section_minus_best_non_section_per_axis=v.null_section_minus_best_non_section_per_axis,
        null_max_violation=v.null_max_violation,
        unit_rankings=["CU-MS", "CU-TS", "CU-FW", "CU-BW"],
        pool=v.pool, per_axis_per_unit_rho=v.per_axis_per_unit_rho,
    )
    i = _strong_stratum("instrumental")  # rankings already match
    combined = h3.maybe_combined_overall(v_no_ls, i, kendall_tau_min=0.5)
    assert combined is not None
    assert combined["kendall_tau"] >= 0.5


def test_kendall_combined_returns_none_when_rankings_disagree():
    v = _strong_stratum("vocal")
    i_reversed = h3.StratumResult(
        stratum="instrumental", n_prompts=4,
        section_minus_best_non_section_per_axis={"musicality": 0.2, "coherence": 0.2, "prompt_fit": 0.2},
        best_non_section_unit_per_axis={"musicality": "CU-TS", "coherence": "CU-TS", "prompt_fit": "CU-TS"},
        n_axes_passing_strict=3, n_axes_passing_directional=3,
        null_section_minus_best_non_section_per_axis={"musicality": -1.0, "coherence": -1.0, "prompt_fit": -1.0},
        null_max_violation=-1.0,
        unit_rankings=["CU-BW", "CU-FW", "CU-TS", "CU-MS"],  # exactly reversed
        pool=["CU-TS", "CU-FW", "CU-BW"],
        per_axis_per_unit_rho={"musicality": {}, "coherence": {}, "prompt_fit": {}},
    )
    combined = h3.maybe_combined_overall(v, i_reversed, kendall_tau_min=0.5)
    assert combined is None


# ============================================================================
# End-to-end stub-test fixture run
# ============================================================================


def test_run_h3a_stub_test_fixture_writes_verdict(tmp_path):
    fixture = REPO_ROOT / "tests" / "fixtures" / "h3a_stub_perprompt.jsonl"
    assert fixture.exists()
    cfg_path = _build_cfg_file(tmp_path)
    out_dir = tmp_path / "h3a_out"
    rc = h3.run_h3a(
        run_cfg_path=cfg_path, out_dir=out_dir,
        pi_approved_launch_cli=True, stub_test_fixture=fixture,
    )
    assert rc == 0
    verdict = json.loads((out_dir / "H3_VERDICT.json").read_text())
    assert "tier" in verdict
    assert verdict["vocal_stratum_tier"] in (
        h3.TIER_FAIL, h3.TIER_AMBIGUOUS, h3.TIER_PROVISIONAL_PASS_PENDING_HELD_OUT,
    )
    assert (out_dir / "h3_vocal_stratum.json").exists()
    assert (out_dir / "h3_instrumental_stratum.json").exists()


def test_step2_real_pipeline_helpers_exist():
    """Sanity: STEP-2 added the real-pipeline helpers; sampling fns are no
    longer stubs raising NotImplementedError. (We don't actually call them
    here — they need GPU + the model. The real GPU path is exercised by
    scripts/h3_smoke.py-style end-to-end smokes.)
    """
    assert hasattr(h3, "run_h3a_real")
    assert hasattr(h3, "_sample_and_decode_real")
    assert hasattr(h3, "_segment_final_for_each_unit")
    assert hasattr(h3, "_score_per_unit_per_axis")
    assert hasattr(h3, "_crop_audio")
    assert hasattr(h3, "_score_segment_reward")


def test_axes_allowed_at_sigma_honors_h2_policy():
    # semantic_fit (prompt_fit) MUST NOT be scored at σ=0.7 per H2.
    assert "prompt_fit" not in h3.AXES_ALLOWED_AT_SIGMA[0.7]
    assert "prompt_fit" in h3.AXES_ALLOWED_AT_SIGMA[0.6]
    # musicality + coherence are allowed at both.
    for sigma in (0.7, 0.6):
        assert "musicality" in h3.AXES_ALLOWED_AT_SIGMA[sigma]
        assert "coherence" in h3.AXES_ALLOWED_AT_SIGMA[sigma]


def test_gating_axis_to_reward_axis_mapping():
    assert h3.GATING_AXIS_TO_REWARD_AXIS["musicality"] == "aesthetic_pq"
    assert h3.GATING_AXIS_TO_REWARD_AXIS["coherence"] == "section_coherence"
    assert h3.GATING_AXIS_TO_REWARD_AXIS["prompt_fit"] == "semantic_fit"


def test_crop_audio_too_short_returns_none():
    import torch as _t
    audio = _t.zeros(int(0.3 * 44_100))  # 0.3s < MIN_REWARD_SEGMENT_SECONDS (0.5s)
    crop = h3._crop_audio(audio, sample_rate=44_100, start_s=0.0, end_s=0.3)
    assert crop is None


def test_crop_audio_normal_returns_slice():
    import torch as _t
    audio = _t.arange(44_100 * 4, dtype=_t.float32)  # 4s
    crop = h3._crop_audio(audio, sample_rate=44_100, start_s=1.0, end_s=3.0)
    assert crop is not None
    assert crop.shape[-1] == 44_100 * 2  # 2s


# ============================================================================
# Codex STEP-2 fix tests: degenerate Spearman + null permutation
# ============================================================================


def test_spearman_degenerate_constant_x_returns_nan_step2_fix():
    """STEP-2 Codex fix: zero-variance inputs must yield NaN, not 1.0.
    Prevents fake signal when MertReward returns 0.0 on sub-window crops."""
    r = h3.spearman([0.0, 0.0, 0.0, 0.0], [1.0, 2.0, 3.0, 4.0])
    assert r != r  # NaN


def test_spearman_degenerate_constant_y_returns_nan_step2_fix():
    r = h3.spearman([1.0, 2.0, 3.0, 4.0], [5.0, 5.0, 5.0, 5.0])
    assert r != r  # NaN


def test_spearman_ordinary_ties_still_use_rank_by_index():
    """Backward compat with Phase B.1: ordinary ties (not full constant)
    are still ranked by index — only fully constant inputs short-circuit."""
    r = h3.spearman([1.0, 1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0])
    # Not NaN — there's variance in both.
    assert r == r
    assert abs(r) <= 1.0


def test_apply_null_permutation_reshuffles_proxy():
    """STEP-2 Codex fix: CU-NULL-rand-section must actually permute the
    proxy vector, not pass through identity."""
    # Build a fake "segments" list with null_permutation_target_index.
    class _FakeSeg:
        def __init__(self, target):
            self.metadata = {"null_permutation_target_index": target}

    segments = [_FakeSeg(t) for t in [2, 0, 3, 1]]  # permutation [2,0,3,1]
    delta = [10.0, 11.0, 12.0, 13.0]
    proxy = [100.0, 101.0, 102.0, 103.0]
    delta_out, proxy_out, perm_used = h3._apply_null_permutation(delta, proxy, segments)
    assert delta_out == delta  # delta unchanged
    # proxy is permuted: proxy_out[i] = proxy[perm[i]] = proxy[[2,0,3,1][i]]
    assert proxy_out == [102.0, 100.0, 103.0, 101.0]
    assert perm_used == [2, 0, 3, 1]


def test_apply_null_permutation_truncates_to_scored_count():
    """When some segments were dropped mid-scoring (crop too short, reward
    failure), the permutation truncates to the surviving count or falls
    back to identity if indices are out of range."""
    class _FakeSeg:
        def __init__(self, target):
            self.metadata = {"null_permutation_target_index": target}

    # 4 segments specified by the unit, but only 3 scored.
    segments = [_FakeSeg(t) for t in [2, 0, 3, 1]]
    delta = [10.0, 11.0, 12.0]
    proxy = [100.0, 101.0, 102.0]
    delta_out, proxy_out, perm_used = h3._apply_null_permutation(delta, proxy, segments)
    # The first 3 entries of [2,0,3,1] include 3 → out of range → identity fallback.
    assert proxy_out == proxy
    assert perm_used == [0, 1, 2]


def test_apply_null_permutation_breaks_perfect_correlation():
    """End-to-end: a perfectly correlated (delta, proxy) pair becomes weakly
    correlated after null permutation. Spearman ρ on permuted should
    typically be less than on identity."""
    class _FakeSeg:
        def __init__(self, target):
            self.metadata = {"null_permutation_target_index": target}

    # Identity permutation → perfect correlation preserved.
    segments_id = [_FakeSeg(i) for i in range(5)]
    delta = [1.0, 2.0, 3.0, 4.0, 5.0]
    proxy = [10.0, 20.0, 30.0, 40.0, 50.0]
    d_id, p_id, _ = h3._apply_null_permutation(delta, proxy, segments_id)
    assert h3.spearman(d_id, p_id) == pytest.approx(1.0)

    # Reverse permutation → anti-correlation.
    segments_rev = [_FakeSeg(i) for i in [4, 3, 2, 1, 0]]
    d_rev, p_rev, _ = h3._apply_null_permutation(delta, proxy, segments_rev)
    assert h3.spearman(d_rev, p_rev) == pytest.approx(-1.0)
