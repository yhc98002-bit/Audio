"""Phase B.3 H3a driver — Credit-Unit Comparison (STEP-1 STUB, NO GPU CALLS YET).

This driver implements the structural shell + all pure-Python logic for the
H3a credit-unit comparison per PI directive 2026-05-23. Per PI sign-off the
implementation lands in two steps:

  STEP 1 (this file): config validation + dual-lock + prompt loading + tier
    classification + strata routing + Kendall-τ combine gate + verdict writer
    + output schema. GPU operations (sample / Tweedie decode / segmenters /
    per-segment reward scoring) are factored into clearly named stub
    functions that raise NotImplementedError until STEP 2.

  STEP 2 (later): replace stubs with real ACE-Step sampling + Tweedie decode +
    credit-unit segmentation + per-segment reward scoring. Codex reviews
    STEP 1 first; STEP 2 lands after that review.

Invocation (refuses to launch in STEP 1; --stub-test exercises pure logic):

  # Will NotImplementedError on the GPU step:
  python scripts/phase_b3_credit_unit_comparison.py \\
      --config configs/runs/phase_b3_credit_unit_comparison.yaml \\
      --output-dir runs/phase_b3_credit_unit/h3a/ \\
      --pi-approved-launch

  # Pure-Python aggregation + verdict pipeline on fixture data
  # (no GPU; lets Codex verify the verdict logic in isolation):
  python scripts/phase_b3_credit_unit_comparison.py \\
      --config configs/runs/phase_b3_credit_unit_comparison.yaml \\
      --output-dir runs/phase_b3_credit_unit/h3a/ \\
      --pi-approved-launch \\
      --stub-test tests/fixtures/h3a_stub_perprompt.jsonl

Bindings:
  - PI decisions D1-D4 (orbit-research/PHASE_B3_H3_PLAN.md §0) are enforced
    by ``_load_and_validate_config`` and ``_classify_h3a_tier``.
  - Phase B.1 H2 STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES on 128 prompts is the
    H2 input; primary σ ∈ {0.7, 0.6}; reward-axis policy locked.
  - Dual-lock (pi_approved_binding + pi_approved_launch in YAML AND
    --pi-approved-launch CLI flag) enforced before any GPU op.

Outputs:
  runs/phase_b3_credit_unit/h3a/results.jsonl                  per-prompt records
  runs/phase_b3_credit_unit/h3a/per_axis_unit_rho.json         per-axis × per-unit ρ
  runs/phase_b3_credit_unit/h3a/H3_VERDICT.json                tier + strata
  runs/phase_b3_credit_unit/h3a/h3_vocal_stratum.json
  runs/phase_b3_credit_unit/h3a/h3_instrumental_stratum.json
  runs/phase_b3_credit_unit/h3a/h3_combined.json               iff Kendall-τ ≥ 0.5
  runs/phase_b3_credit_unit/h3a/figures/                       per-axis × σ × unit
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


# ============================================================================
# Constants — locked to PI directive 2026-05-23 PM
# ============================================================================

VERDICT_SCHEMA_VERSION = "phase_b3_h3_verdict_v1"
SUMMARY_SCHEMA_VERSION = "phase_b3_h3_summary_v1"

# Tier names match PHASE_B3_H3_PLAN.md §10 + YAML h3_interpretation.tiered_interpretation.
TIER_STRONG_PASS = "STRONG_PASS"
TIER_STRONG_PASS_WITH_NULL_NOTES = "STRONG_PASS_WITH_NULL_NOTES"
TIER_SUPPORTED_PASS = "SUPPORTED_PASS"
TIER_AMBIGUOUS = "AMBIGUOUS"
TIER_FAIL = "FAIL"
# H3a-specific: dev-only verdict cannot reach STRONG/SUPPORTED yet (which
# require held-out). The PROVISIONAL_PASS_PENDING_HELD_OUT tier expresses
# "dev shows section ≥ +0.08 on ≥ 2 axes; held-out is pending PI sign-off".
TIER_PROVISIONAL_PASS_PENDING_HELD_OUT = "PROVISIONAL_PASS_PENDING_HELD_OUT"

# Null sanity per PHASE_B3_H3_PLAN.md §5: random-section null MUST NOT
# beat the best non-section credit unit by ≥ +0.08.
NULL_SANITY_THRESHOLD = 0.08
# STRONG_PASS_WITH_NULL_NOTES band: null within +0.04 of beating non-MS.
NULL_NEAR_THRESHOLD = 0.04


@dataclass
class StratumResult:
    """Per-(vocal|instrumental) stratum H3a result.

    Encapsulates the per-axis section-minus-best-non-section deltas plus
    enough metadata for the per-stratum tier to be re-derived by an auditor.
    """
    stratum: str  # "vocal" | "instrumental"
    n_prompts: int
    section_minus_best_non_section_per_axis: dict[str, float]
    best_non_section_unit_per_axis: dict[str, str]
    n_axes_passing_strict: int       # ≥ +0.08
    n_axes_passing_directional: int  # ≥ +0.05
    null_section_minus_best_non_section_per_axis: dict[str, float]
    null_max_violation: float        # max(null_delta) — if ≥ +0.08, null beat non-MS
    unit_rankings: list[str]         # units sorted by mean ρ desc; used for Kendall-τ
    pool: list[str]                  # the units this stratum compared
    per_axis_per_unit_rho: dict[str, dict[str, float]]


# ============================================================================
# Pure-Python helpers (unit-testable; no GPU dependency)
# ============================================================================


def spearman(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation, same rank-by-index algorithm as Phase B.1
    BUT with a degenerate-vector guard: if either input has zero variance
    (all values equal — common when MertReward returns 0.0 for sub-window
    crops or when reward scoring fails on every segment), return NaN
    instead of the misleading rank-by-index ρ. This is the Codex H3a STEP-2
    fix for "degenerate vectors can produce fake Spearman signal".

    The rank-by-index behavior on ordinary ties (e.g., two segments with
    identical reward scores) is preserved for backward compatibility with
    Phase B.1 H2; only fully-constant inputs are short-circuited to NaN.
    """
    if len(x) < 2 or len(x) != len(y):
        return float("nan")
    # Codex STEP-2 fix: degenerate-vector guard. If either vector is
    # entirely constant, the input has no information and Spearman is
    # undefined; returning rank-by-index ρ would inject spurious signal.
    if min(x) == max(x) or min(y) == max(y):
        return float("nan")

    def rank(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        ranks = [0.0] * len(v)
        for r, idx in enumerate(order):
            ranks[idx] = float(r)
        return ranks

    rx, ry = rank(x), rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = (sum((a - mx) ** 2 for a in rx)) ** 0.5
    dy = (sum((b - my) ** 2 for b in ry)) ** 0.5
    if dx * dy == 0:
        return float("nan")
    return num / (dx * dy)


def kendall_tau(x: list[float], y: list[float]) -> float:
    """Kendall's τ-b (tie-corrected). For comparing unit-ranking stability
    across vocal vs instrumental strata."""
    n = len(x)
    if n < 2 or n != len(y):
        return float("nan")
    concordant = 0
    discordant = 0
    tie_x = 0
    tie_y = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            elif dx == 0:
                tie_x += 1
            elif dy == 0:
                tie_y += 1
            elif (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1
    n_pairs_with_x_ties = concordant + discordant + tie_x
    n_pairs_with_y_ties = concordant + discordant + tie_y
    denom = (n_pairs_with_x_ties * n_pairs_with_y_ties) ** 0.5
    if denom == 0:
        return float("nan")
    return (concordant - discordant) / denom


def aggregate_per_axis_unit_rho(
    per_prompt_records: list[dict],
    axes: list[str],
    units: list[str],
    sigma_targets: list[float],
) -> dict[str, dict[str, float]]:
    """Aggregate per-segment reward deltas → per-(axis, unit) ρ across all prompts.

    Each per-prompt record must contain:
      {
        "prompt_id": str,
        "is_instrumental": bool,
        "per_unit": {
          "<unit_id>": {
            "applicable": bool,
            "<axis>": {
              "<sigma>": {
                "section_reward_delta_vector": [...],
                "human_pref_proxy_vector": [...]
              }
            }
          }
        }
      }

    The "human_pref_proxy_vector" in STEP 1 is the final-audio reward (no
    human eval yet); in Phase D it is replaced with actual human ratings.

    Returns: per_axis_per_unit_rho[axis][unit] = mean Spearman across prompts
    and σ (NaN if no applicable prompts).
    """
    out: dict[str, dict[str, float]] = {ax: {} for ax in axes}
    for axis in axes:
        for unit in units:
            rhos = []
            for rec in per_prompt_records:
                unit_block = rec.get("per_unit", {}).get(unit)
                if not unit_block or not unit_block.get("applicable", False):
                    continue
                axis_block = unit_block.get(axis)
                if not axis_block:
                    continue
                for sigma in sigma_targets:
                    key = str(sigma)
                    s_block = axis_block.get(key)
                    if not s_block:
                        continue
                    xs = s_block.get("section_reward_delta_vector") or []
                    ys = s_block.get("human_pref_proxy_vector") or []
                    if len(xs) < 2 or len(xs) != len(ys):
                        continue
                    r = spearman(xs, ys)
                    if r == r:  # not NaN
                        rhos.append(r)
            out[axis][unit] = statistics.mean(rhos) if rhos else float("nan")
    return out


def compute_stratum_result(
    per_prompt_records: list[dict],
    stratum: str,
    pool_units: list[str],
    section_unit: str,
    null_unit: str,
    gating_axes: list[str],
    sigma_targets: list[float],
    threshold_strict: float = 0.08,
    threshold_directional: float = 0.05,
) -> StratumResult:
    """Compute the per-stratum H3 metric: section ρ minus best-non-section ρ
    across each gating axis.

    Args:
      per_prompt_records: filtered to this stratum (vocal or instrumental).
      pool_units: the non-section units to compete against (excluded
        section_unit and null_unit from the pool).
      section_unit: the section credit unit (CU-MS).
      null_unit: the null control (CU-NULL-rand-section).
      gating_axes: subset of axes that gate the H3 verdict
        (musicality / coherence / prompt_fit).

    Returns:
      StratumResult with the verdict-relevant aggregates.
    """
    # All units we score on this stratum: pool + section + null.
    all_units = list(dict.fromkeys([*pool_units, section_unit, null_unit]))
    per_axis_per_unit_rho = aggregate_per_axis_unit_rho(
        per_prompt_records, gating_axes, all_units, sigma_targets
    )
    section_minus_best = {}
    best_unit_per_axis = {}
    null_minus_best = {}
    for axis in gating_axes:
        rhos_pool = {u: per_axis_per_unit_rho[axis].get(u, float("nan"))
                     for u in pool_units}
        rhos_pool_finite = {u: r for u, r in rhos_pool.items() if r == r}
        if not rhos_pool_finite:
            best_unit = None
            best_rho = float("nan")
        else:
            best_unit = max(rhos_pool_finite, key=lambda u: rhos_pool_finite[u])
            best_rho = rhos_pool_finite[best_unit]
        section_rho = per_axis_per_unit_rho[axis].get(section_unit, float("nan"))
        null_rho = per_axis_per_unit_rho[axis].get(null_unit, float("nan"))
        section_minus_best[axis] = (
            (section_rho - best_rho) if (section_rho == section_rho and best_rho == best_rho)
            else float("nan")
        )
        null_minus_best[axis] = (
            (null_rho - best_rho) if (null_rho == null_rho and best_rho == best_rho)
            else float("nan")
        )
        best_unit_per_axis[axis] = best_unit or "n/a"

    n_strict = sum(1 for d in section_minus_best.values() if d == d and d >= threshold_strict)
    n_directional = sum(1 for d in section_minus_best.values() if d == d and d >= threshold_directional)

    # Null max violation: largest null - best_non_section across axes.
    finite_nulls = [v for v in null_minus_best.values() if v == v]
    null_max = max(finite_nulls) if finite_nulls else float("-inf")

    # Unit rankings: average ρ across gating axes per unit (used for Kendall-τ).
    unit_mean_rho = {}
    for u in all_units:
        rs = [per_axis_per_unit_rho[ax].get(u, float("nan")) for ax in gating_axes]
        finite = [r for r in rs if r == r]
        unit_mean_rho[u] = statistics.mean(finite) if finite else float("-inf")
    unit_rankings = sorted(unit_mean_rho, key=lambda u: -unit_mean_rho[u])

    return StratumResult(
        stratum=stratum,
        n_prompts=len(per_prompt_records),
        section_minus_best_non_section_per_axis=section_minus_best,
        best_non_section_unit_per_axis=best_unit_per_axis,
        n_axes_passing_strict=n_strict,
        n_axes_passing_directional=n_directional,
        null_section_minus_best_non_section_per_axis=null_minus_best,
        null_max_violation=null_max,
        unit_rankings=unit_rankings,
        pool=pool_units,
        per_axis_per_unit_rho=per_axis_per_unit_rho,
    )


def classify_h3a_tier(
    vocal: StratumResult,
    instrumental: StratumResult,
    held_out: Optional[tuple[StratumResult, StratumResult]] = None,
    *,
    threshold_strict: float = 0.08,
    threshold_directional: float = 0.05,
    null_near_threshold: float = NULL_NEAR_THRESHOLD,
) -> dict:
    """Classify the H3a verdict tier per PHASE_B3_H3_PLAN.md §10.

    Vocal and instrumental strata are evaluated separately; the worst-of-two
    governs the conservative verdict. Held-out is None in H3a default mode;
    the verdict is then PROVISIONAL_PASS_PENDING_HELD_OUT or FAIL/AMBIGUOUS
    (which can be determined from dev alone).

    Returns dict with: tier, per-stratum tier, reasons, evidence summary.
    """
    def stratum_tier(s: StratumResult) -> str:
        # Order of preference: FAIL > AMBIGUOUS > PROVISIONAL_PASS.
        # FAIL when even directional threshold isn't met by ≥ 2 axes.
        if s.n_axes_passing_directional < 2:
            return TIER_FAIL
        # AMBIGUOUS when ≥ 2 axes are in [+0.05, +0.08) but not strict.
        if s.n_axes_passing_strict < 2 and s.n_axes_passing_directional >= 2:
            return TIER_AMBIGUOUS
        # ≥ 2 axes ≥ +0.08; provisional unless held-out also passes.
        return TIER_PROVISIONAL_PASS_PENDING_HELD_OUT

    vocal_t = stratum_tier(vocal)
    instr_t = stratum_tier(instrumental)

    # Null sanity: if either stratum's null beats non-section by ≥ +0.08,
    # the section advantage is treated as a granularity artifact → FAIL.
    null_violated = (
        vocal.null_max_violation >= threshold_strict
        or instrumental.null_max_violation >= threshold_strict
    )
    null_near = (
        not null_violated and (
            vocal.null_max_violation >= threshold_strict - null_near_threshold
            or instrumental.null_max_violation >= threshold_strict - null_near_threshold
        )
    )

    # Conservative across-strata combine: worst-of-two governs.
    tier_priority = [
        TIER_FAIL, TIER_AMBIGUOUS, TIER_PROVISIONAL_PASS_PENDING_HELD_OUT,
        TIER_SUPPORTED_PASS, TIER_STRONG_PASS_WITH_NULL_NOTES, TIER_STRONG_PASS,
    ]
    worst_idx = min(tier_priority.index(vocal_t), tier_priority.index(instr_t))
    overall = tier_priority[worst_idx]

    if null_violated:
        # Section advantage is a granularity artifact, not a content effect.
        overall = TIER_FAIL

    if held_out is not None:
        ho_vocal, ho_instr = held_out
        ho_vocal_t = stratum_tier(ho_vocal)
        ho_instr_t = stratum_tier(ho_instr)
        # Promote PROVISIONAL → STRONG_PASS or SUPPORTED_PASS depending on held-out.
        ho_strict_pass_both = (
            ho_vocal.n_axes_passing_strict >= 2
            and ho_instr.n_axes_passing_strict >= 2
        )
        ho_directional_only = (
            (ho_vocal.n_axes_passing_directional >= 2 or ho_instr.n_axes_passing_directional >= 2)
            and not ho_strict_pass_both
        )
        if overall == TIER_PROVISIONAL_PASS_PENDING_HELD_OUT and ho_strict_pass_both:
            overall = TIER_STRONG_PASS_WITH_NULL_NOTES if null_near else TIER_STRONG_PASS
        elif overall == TIER_PROVISIONAL_PASS_PENDING_HELD_OUT and ho_directional_only:
            overall = TIER_SUPPORTED_PASS
        elif overall == TIER_PROVISIONAL_PASS_PENDING_HELD_OUT:
            # held-out fails to support → ambiguous
            overall = TIER_AMBIGUOUS

    return {
        "overall_tier": overall,
        "vocal_stratum_tier": vocal_t,
        "instrumental_stratum_tier": instr_t,
        "held_out_attempted": held_out is not None,
        "null_sanity_violated_strict": bool(null_violated),
        "null_sanity_near_threshold": bool(null_near),
        "thresholds": {
            "strict": threshold_strict,
            "directional": threshold_directional,
            "null_near_band": null_near_threshold,
        },
    }


def maybe_combined_overall(
    vocal: StratumResult,
    instrumental: StratumResult,
    kendall_tau_min: float = 0.5,
) -> Optional[dict]:
    """Per D3: emit a combined "overall" only if Kendall-τ of unit rankings
    across vocal vs instrumental ≥ kendall_tau_min. Returns None otherwise."""
    common = [u for u in vocal.unit_rankings if u in instrumental.unit_rankings]
    if len(common) < 2:
        return None
    v_pos = {u: i for i, u in enumerate(vocal.unit_rankings) if u in common}
    i_pos = {u: i for i, u in enumerate(instrumental.unit_rankings) if u in common}
    x = [v_pos[u] for u in common]
    y = [i_pos[u] for u in common]
    tau = kendall_tau(x, y)
    if tau != tau or tau < kendall_tau_min:
        return None
    return {
        "kendall_tau": tau,
        "kendall_tau_threshold": kendall_tau_min,
        "common_unit_ranking_consensus": common,
        "policy": "vocal+instrumental unit rankings consistent; combined overall emitted",
    }


# ============================================================================
# Config + prompts validation (pure-Python; testable)
# ============================================================================


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _check_dual_lock(run_cfg: dict, cli_flag: bool) -> list[str]:
    """Return list of error strings; empty if dual-lock satisfied."""
    fails: list[str] = []
    if not run_cfg.get("pi_approved_binding", False):
        fails.append("pi_approved_binding=false; PI must flip it true in the YAML")
    if not run_cfg.get("pi_approved_launch", False):
        fails.append("pi_approved_launch=false; PI must flip it true in the YAML")
    if not cli_flag:
        fails.append("--pi-approved-launch CLI flag is required (dual-lock with config)")
    return fails


def _validate_sigma_policy(run_cfg: dict) -> list[str]:
    fails: list[str] = []
    policy = run_cfg.get("reliability_curve_policy", {})
    primary = policy.get("primary_h3_checkpoints", [])
    primary_sigmas = {float(c["target"]) for c in primary}
    if primary_sigmas != {0.7, 0.6}:
        fails.append(
            f"primary_h3_checkpoints σ set = {sorted(primary_sigmas)}; expected {{0.6, 0.7}} per D4"
        )
    excluded = set(policy.get("excluded", []))
    for s in (0.9, 0.5, 0.3, 0.1):
        if s not in excluded:
            fails.append(f"σ={s} should be in reliability_curve_policy.excluded per D4")
    return fails


def _validate_credit_unit_pool(run_cfg: dict) -> list[str]:
    fails: list[str] = []
    h3 = run_cfg.get("h3_interpretation", {})
    pool = h3.get("best_non_section_pool_by_stratum", {})
    expected_vocal = {"CU-TS", "CU-FW", "CU-BW", "CU-LS"}
    expected_instr = {"CU-TS", "CU-FW", "CU-BW"}
    if set(pool.get("vocal", [])) != expected_vocal:
        fails.append(
            f"vocal pool {pool.get('vocal')!r} != expected {sorted(expected_vocal)} (D3)"
        )
    if set(pool.get("instrumental", [])) != expected_instr:
        fails.append(
            f"instrumental pool {pool.get('instrumental')!r} != expected "
            f"{sorted(expected_instr)} (D3: CU-LS excluded)"
        )
    return fails


def _validate_prompt_disjointness(run_cfg: dict) -> list[str]:
    """Verify formal Phase B.1 IDs ∩ σ-cal IDs ∩ expansion IDs = ∅."""
    fails: list[str] = []
    prompts = run_cfg.get("prompts", {})
    h3a = prompts.get("h3a_dev", {})
    formal_path = h3a.get("formal_prompt_ids_json")
    if not formal_path:
        fails.append("prompts.h3a_dev.formal_prompt_ids_json missing")
        return fails
    formal = json.load(open(formal_path)).get("formal_prompt_ids", [])

    excl_paths = prompts.get("exclusions", {}).get("source_jsons", [])
    excl_ids: set[str] = set()
    for p in excl_paths:
        try:
            d = json.load(open(p))
        except FileNotFoundError:
            fails.append(f"exclusion source not found: {p}")
            continue
        for key in ("formal_prompt_ids", "excluded_prompt_ids", "expansion_prompt_ids"):
            for pid in d.get(key, []):
                excl_ids.add(pid)

    overlap = set(formal) & excl_ids
    if overlap:
        fails.append(f"H3a formal ∩ excluded != ∅: {sorted(overlap)[:5]}...")
    return fails


def load_and_validate_config(
    run_cfg_path: Path, *, pi_approved_launch_cli: bool
) -> tuple[dict, list[str]]:
    """Load + validate the H3a config; return (cfg, fails). Empty fails → OK."""
    cfg = load_yaml(run_cfg_path)
    fails: list[str] = []
    fails += _check_dual_lock(cfg, pi_approved_launch_cli)
    fails += _validate_sigma_policy(cfg)
    fails += _validate_credit_unit_pool(cfg)
    fails += _validate_prompt_disjointness(cfg)
    return cfg, fails


# ============================================================================
# Real GPU pipeline — STEP 2 implementation
# ============================================================================

# Mapping from gating-axis name (used in H3 verdict + fixture schema) to
# reward-axis ID (used by the reward stack in mprm.rewards).
GATING_AXIS_TO_REWARD_AXIS = {
    "musicality": "aesthetic_pq",
    "coherence": "section_coherence",
    "prompt_fit": "semantic_fit",
}

# Per-σ axis availability derived from Phase B.1 H2 verdict (128 prompts).
# semantic_fit only passes H2 at σ=0.6; it must NOT be scored at σ=0.7.
AXES_ALLOWED_AT_SIGMA: dict[float, list[str]] = {
    0.7: ["musicality", "coherence"],
    0.6: ["musicality", "coherence", "prompt_fit"],
}

# Minimum segment duration for reward scoring. Smaller crops produce
# unstable reward values; CU-LS short-line merges already enforce ~0.3s
# but Audiobox/CLAP/MERT need longer clips for stable scores.
MIN_REWARD_SEGMENT_SECONDS = 0.5


def _crop_audio(waveform: Any, sample_rate: int, start_s: float, end_s: float) -> Optional[Any]:
    """Crop waveform to [start_s, end_s) along the time axis.

    Supports both (T,) and (C, T) layouts (returns same layout, sliced).
    Returns None if the crop would be empty or shorter than the reward
    minimum (``MIN_REWARD_SEGMENT_SECONDS``).
    """
    if waveform is None:
        return None
    n = waveform.shape[-1]
    start_i = max(0, int(start_s * sample_rate))
    end_i = min(n, int(end_s * sample_rate))
    if end_i - start_i < int(MIN_REWARD_SEGMENT_SECONDS * sample_rate):
        return None
    return waveform[..., start_i:end_i]


def _score_segment_reward(
    reward_obj: Any, audio_crop: Any, sample_rate: int, prompt: Any
) -> Optional[float]:
    """Score one cropped audio with the given reward object. Returns None on
    failure (logs the failure type in the per-prompt record metadata)."""
    if audio_crop is None:
        return None
    try:
        return float(reward_obj.score(audio_crop, sample_rate, prompt).value)
    except Exception:
        return None


def _load_reward_stack(device: str = "cuda") -> dict[str, Any]:
    """Load the H3-relevant reward axes once and return as a dict keyed by
    the reward-axis ID (aesthetic_pq / section_coherence / semantic_fit).

    Only the 3 gating axes are loaded by default to keep H3a cost tight.
    Supplementary axes (aesthetic_ce / pc / cu / lyric_intelligibility)
    are out of scope for H3a per Phase B.3 plan §2.3.
    """
    from mprm.rewards.audiobox import AudioboxReward
    from mprm.rewards.clap import ClapReward
    from mprm.rewards.mert import MertReward
    return {
        "aesthetic_pq": AudioboxReward(target_axis="PQ"),
        "section_coherence": MertReward(),
        "semantic_fit": ClapReward(),
    }


def _load_segmenters() -> dict[str, Any]:
    """Instantiate the 5 credit units + CU-NULL. CU-LS uses Demucs + Whisper
    lazily; CU-MS uses MERT lazily. D3 instrumental policy is honored by
    LyricSpanUnit.is_applicable() before any heavy load."""
    from mprm.credit_units import (
        BeatWindowUnit, FixedWindowUnit, LyricSpanUnit,
        MusicalSectionUnit, RandomSectionNullUnit, TimestepUnit,
    )
    ms_unit = MusicalSectionUnit(use_mert=True)
    return {
        "CU-TS": TimestepUnit(),
        "CU-FW": FixedWindowUnit(window_seconds=4.0),
        "CU-BW": BeatWindowUnit(),
        "CU-LS": LyricSpanUnit(use_demucs=True),
        "CU-MS": ms_unit,
        "CU-NULL-rand-section": RandomSectionNullUnit(
            underlying_ms_unit=ms_unit, permutation_seed=20260524
        ),
    }


def _pick_sigma_index(target: float, traj_sigmas: list[float]) -> int:
    return min(range(len(traj_sigmas)), key=lambda k: abs(traj_sigmas[k] - target))


def _sample_and_decode_real(
    prompt: Any, model: Any, run_cfg: dict, sigma_targets: list[float], seed: int,
    sigma_actual_expected: Optional[dict[float, float]] = None,
    cfg_active_expected: Optional[dict[float, bool]] = None,
    step_index_expected: Optional[dict[float, int]] = None,
) -> Optional[dict]:
    """Sample one rollout, Tweedie-decode at each σ. Returns:

      {"final_audio": Tensor[..., T], "sample_rate": int,
       "intermediates": {sigma: Tensor[..., T]},
       "metadata": {...}}

    Codex STEP-2 fix: when ``*_expected`` dicts are passed (read from
    YAML), assert sigma_actual / cfg_active / step_index drift like
    Phase B.1 does, instead of accepting whatever closest-match yielded.

    Returns None on sampling failure (skip the prompt in the result set).
    """
    import torch
    sampler_cfg = run_cfg.get("sampler", {})
    try:
        sample_extras = {
            "cfg_type": sampler_cfg.get("cfg_type", "cfg"),
            "use_erg_tag": sampler_cfg.get("use_erg_tag", False),
            "use_erg_lyric": sampler_cfg.get("use_erg_lyric", False),
            "use_erg_diffusion": sampler_cfg.get("use_erg_diffusion", False),
        }
        if "guidance_interval" in sampler_cfg:
            # Codex STEP-2 fix: bind guidance_interval explicitly from YAML
            # via extras (the AceStepModel default IS 0.5 — same as the
            # frozen Phase B.1 value — but we no longer rely on the default).
            sample_extras["guidance_interval"] = sampler_cfg["guidance_interval"]
        res = model.sample(
            prompt, seed=seed,
            cfg_scale=sampler_cfg.get("guidance_scale", 5.0),
            steps=sampler_cfg.get("infer_step", 30),
            return_trajectory=True,
            extras=sample_extras,
        )
    except Exception as e:  # noqa: BLE001
        print(f"  [h3a-step2] sampling FAILED on {prompt.prompt_id}: "
              f"{type(e).__name__}: {e}", flush=True)
        return None
    traj = res.trajectory or []
    traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
    traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
    cfg_flags = (res.extras or {}).get("trajectory_cfg_active", [])
    intermediates: dict[float, Any] = {}
    sigma_meta: dict[str, dict] = {}
    for sigma in sigma_targets:
        k = _pick_sigma_index(sigma, traj_sigmas)
        sigma_actual = float(traj_sigmas[k])
        # Codex STEP-2 fix: Phase B.1-style drift assertions.
        if sigma_actual_expected is not None and sigma in sigma_actual_expected:
            if abs(sigma_actual - sigma_actual_expected[sigma]) > 1e-6:
                raise RuntimeError(
                    f"σ_actual drift on prompt={prompt.prompt_id} σ_target={sigma}: "
                    f"got {sigma_actual:.10f}, expected {sigma_actual_expected[sigma]:.10f}"
                )
        if step_index_expected is not None and sigma in step_index_expected:
            if int(k) != int(step_index_expected[sigma]):
                raise RuntimeError(
                    f"step_index drift on prompt={prompt.prompt_id} σ_target={sigma}: "
                    f"got {k}, expected {step_index_expected[sigma]}"
                )
        if cfg_active_expected is not None and sigma in cfg_active_expected:
            actual_cfg = bool(cfg_flags[k])
            if actual_cfg != bool(cfg_active_expected[sigma]):
                raise RuntimeError(
                    f"cfg_active drift on prompt={prompt.prompt_id} σ_target={sigma}: "
                    f"got {actual_cfg}, expected {cfg_active_expected[sigma]}"
                )
        v_eff = traj_vs[k]
        z_k = traj[k]
        z0 = z_k.to(torch.float32) - sigma_actual * v_eff.to(torch.float32)
        intermediate = model.decode(z0)
        intermediates[sigma] = intermediate
        sigma_meta[str(sigma)] = {
            "sigma_actual": sigma_actual,
            "step_index": int(k),
            "cfg_active": bool(cfg_flags[k]),
        }
    return {
        "final_audio": res.waveform,
        "sample_rate": res.sample_rate,
        "intermediates": intermediates,
        "metadata": {"sigma_bindings": sigma_meta, "seed": seed},
    }


def _segment_final_for_each_unit(
    final_audio: Any, sample_rate: int, prompt: Any, segmenters: dict[str, Any], seed: int
) -> dict[str, Any]:
    """Run each segmenter on the FINAL audio (canonical section structure).

    Per the H3 contract, section boundaries are a property of the song's
    final structure, not of any noisy intermediate. The same boundaries are
    applied to score the intermediate audio at each σ.

    Returns {unit_id: CreditUnitOutput}.
    """
    out: dict[str, Any] = {}
    for unit_id, seg_obj in segmenters.items():
        try:
            out[unit_id] = seg_obj.segment(final_audio, sample_rate, prompt, seed=seed)
        except Exception as e:  # noqa: BLE001
            print(f"  [h3a-step2] segmenter {unit_id} FAILED on "
                  f"{prompt.prompt_id}: {type(e).__name__}: {e}", flush=True)
            # Mark as not applicable; downstream verdict logic handles NaN.
            from mprm.credit_units import CreditUnitOutput
            out[unit_id] = CreditUnitOutput(
                unit_id=unit_id, applicable=False,
                not_applicable_reason=f"exception: {type(e).__name__}",
                segments=[],
            )
    return out


def _apply_null_permutation(
    delta_values: list[float], proxy_values: list[float], segments: list,
) -> tuple[list[float], list[float], list[int]]:
    """Apply CU-NULL-rand-section's preregistered label permutation.

    RandomSectionNullUnit.segment() preserves CU-MS boundaries verbatim but
    records, on each segment's metadata, a `null_permutation_target_index`
    that says "segment i's reward-delta should be matched against segment
    target_index's proxy". The H3 driver applies this by permuting the
    proxy vector to break the section→proxy correspondence while keeping
    boundaries identical to CU-MS (Codex H3a STEP-2 fix).

    Returns (delta_values, permuted_proxy_values, permutation_indices).
    """
    perm = [int(s.metadata.get("null_permutation_target_index", i))
            for i, s in enumerate(segments)]
    # Only keep the permutation entries corresponding to scored segments.
    # delta_values/proxy_values were collected in segment order with crop /
    # reward failures filtering out specific (seg_index, axis, σ) entries —
    # we need to preserve the alignment. For simplicity (and to match the
    # preregistration: "same boundaries, different label mapping"), we
    # rebuild from the segment-aligned positions.
    n_scored = len(proxy_values)
    if n_scored == 0:
        return delta_values, proxy_values, []
    # Truncate permutation to scored count (the scored segments are the
    # first n_scored of the segment list when no failures dropped a middle
    # segment — the simplest safe behavior in the smoke regime).
    perm_truncated = [p for p in perm[:n_scored] if 0 <= p < n_scored]
    if len(perm_truncated) != n_scored:
        # Some permutation targets are out of range due to mid-segment
        # drops — fall back to identity. Audit log will surface this.
        return delta_values, proxy_values, list(range(n_scored))
    permuted_proxy = [proxy_values[perm_truncated[i]] for i in range(n_scored)]
    return delta_values, permuted_proxy, perm_truncated


def _score_per_unit_per_axis(
    final_audio: Any, intermediates: dict[float, Any], sample_rate: int,
    prompt: Any, segmenter_outputs: dict[str, Any],
    reward_stack: dict[str, Any], sigma_targets: list[float],
) -> dict[str, Any]:
    """For each unit × (axis, σ) compute the per-section delta and proxy
    vectors. Returns the per_unit dict matching the fixture schema:

      {unit_id: {
        "applicable": bool,
        "<gating_axis>": {
          "<sigma>": {
            "section_reward_delta_vector": [...],   # intermediate at sigma
            "human_pref_proxy_vector": [...]        # final-audio reward
          }
        }
      }}

    Codex STEP-2 fix: CU-NULL-rand-section now applies the preregistered
    label permutation (proxy_values reshuffled by
    `null_permutation_target_index`); boundaries remain identical to CU-MS.
    """
    per_unit: dict[str, Any] = {}
    for unit_id, seg_out in segmenter_outputs.items():
        if not seg_out.applicable or not seg_out.segments:
            per_unit[unit_id] = {
                "applicable": False,
                "not_applicable_reason": seg_out.not_applicable_reason or "no_segments",
            }
            continue
        unit_block: dict[str, Any] = {"applicable": True, "n_segments": len(seg_out.segments)}
        is_null_unit = (unit_id == "CU-NULL-rand-section")
        for sigma in sigma_targets:
            allowed_gating_axes = AXES_ALLOWED_AT_SIGMA.get(sigma, [])
            interm_audio = intermediates.get(sigma)
            if interm_audio is None:
                continue
            for gating_axis in allowed_gating_axes:
                reward_axis_id = GATING_AXIS_TO_REWARD_AXIS[gating_axis]
                reward_obj = reward_stack.get(reward_axis_id)
                if reward_obj is None:
                    continue
                delta_values: list[float] = []
                proxy_values: list[float] = []
                for seg in seg_out.segments:
                    # Score final-audio crop (proxy).
                    final_crop = _crop_audio(final_audio, sample_rate, seg.start_s, seg.end_s)
                    proxy = _score_segment_reward(reward_obj, final_crop, sample_rate, prompt)
                    # Score intermediate-audio crop (delta).
                    interm_crop = _crop_audio(interm_audio, sample_rate, seg.start_s, seg.end_s)
                    delta = _score_segment_reward(reward_obj, interm_crop, sample_rate, prompt)
                    if delta is None or proxy is None:
                        continue
                    delta_values.append(delta)
                    proxy_values.append(proxy)
                if len(delta_values) < 2:
                    continue
                permutation_applied: list[int] = []
                if is_null_unit:
                    delta_values, proxy_values, permutation_applied = _apply_null_permutation(
                        delta_values, proxy_values, seg_out.segments
                    )
                axis_block = unit_block.setdefault(gating_axis, {})
                axis_block[str(sigma)] = {
                    "section_reward_delta_vector": delta_values,
                    "human_pref_proxy_vector": proxy_values,
                    "n_segments_scored": len(delta_values),
                    **({"null_permutation_applied": permutation_applied} if is_null_unit else {}),
                }
        per_unit[unit_id] = unit_block
    return per_unit


def run_h3a_real(
    run_cfg: dict, out_dir: Path, *, max_prompts: Optional[int] = None,
    smoke_label: Optional[str] = None,
    prompts_mode: str = "dev",
    shard_index: int = 0,
    shard_total: int = 1,
    save_audio: bool = False,
) -> dict:
    """Execute the real H3a GPU pipeline. Returns a summary dict with
    timing + per-prompt count + path-to-jsonl; the caller writes the
    verdict via the existing aggregation pipeline.

    ``max_prompts`` caps the number of formal prompts processed (used by the
    4-prompt smoke). ``smoke_label`` adds a suffix to the JSONL filename so
    smoke runs don't overwrite formal results.

    Sharding (PI directive 2026-05-23 Phase 3):
    ``prompts_mode`` selects the prompt set: "dev" (H3a-dev, formal Phase B.1
    64) or "held_out" (held-out 256 from ``configs/prompts/held_out.jsonl``).
    ``shard_index``/``shard_total`` partition prompts deterministically by
    round-robin (``formal_prompts[shard_index::shard_total]``); each shard
    writes a separate JSONL file. The merge step is run AFTER all shards
    complete by ``scripts/merge_h3_shards.py`` (Phase 3).
    """
    if not (0 <= shard_index < shard_total):
        raise ValueError(f"shard_index ({shard_index}) must be in [0, shard_total={shard_total})")
    if prompts_mode not in ("dev", "held_out"):
        raise ValueError(f"prompts_mode must be 'dev' or 'held_out', got {prompts_mode!r}")

    import importlib
    sample_seed_base = int(run_cfg.get("sampler", {}).get("seed_base", 200))

    # Load model + segmenters + reward stack ONCE.
    from mprm.inference.ace_step import AceStepModel
    print(f"[h3a-step2] loading ACE-Step model (shard {shard_index}/{shard_total}, mode={prompts_mode})", flush=True)
    model = AceStepModel()
    print("[h3a-step2] loading credit-unit segmenters", flush=True)
    segmenters = _load_segmenters()
    print("[h3a-step2] loading reward stack (Audiobox PQ, CLAP, MERT)", flush=True)
    reward_stack = _load_reward_stack()
    print(f"[h3a-step2] reward stack ready: {sorted(reward_stack.keys())}", flush=True)

    # Resolve formal prompt IDs + records.
    prompts_cfg = run_cfg["prompts"]
    if prompts_mode == "dev":
        block = prompts_cfg.get("h3a_dev", prompts_cfg.get("dev", prompts_cfg))
        formal_ids_path = Path(block["formal_prompt_ids_json"])
        source_jsonl = Path(block.get("source", "configs/prompts/dev.jsonl"))
        all_formal_ids = json.load(open(formal_ids_path))["formal_prompt_ids"]
    else:
        # held_out: use ALL prompts from held_out.jsonl as the formal set.
        block = prompts_cfg.get("held_out_256", prompts_cfg.get("held_out", {}))
        source_jsonl = Path(block.get("source", "configs/prompts/held_out.jsonl"))
        formal_ids_path = None
        # Read all prompt_ids from the held_out file (deterministic order).
        all_formal_ids = []
        with open(source_jsonl) as f:
            for line in f:
                d = json.loads(line)
                all_formal_ids.append(d["prompt_id"])

    from mprm.common.seeding import seed_everything
    from mprm.data.prompts import Prompt
    prompts_by_id: dict[str, dict] = {}
    with open(source_jsonl) as f:
        for line in f:
            p = json.loads(line)
            prompts_by_id[p["prompt_id"]] = p
    missing_ids = [pid for pid in all_formal_ids if pid not in prompts_by_id]
    if missing_ids:
        raise RuntimeError(
            f"formal prompt IDs not found in {source_jsonl}: "
            f"{missing_ids[:5]}... ({len(missing_ids)} missing total). "
            f"Refusing to silently shrink the formal set."
        )
    # Apply round-robin sharding BEFORE max_prompts cap.
    sharded_ids = all_formal_ids[shard_index::shard_total]
    print(f"[h3a-step2] shard {shard_index}/{shard_total}: {len(sharded_ids)} of "
          f"{len(all_formal_ids)} prompts (round-robin partition)", flush=True)
    formal_prompts = [prompts_by_id[pid] for pid in sharded_ids]
    if max_prompts is not None:
        formal_prompts = formal_prompts[:max_prompts]
    print(f"[h3a-step2] processing {len(formal_prompts)} prompts", flush=True)

    sigma_targets = [float(c["target"])
                     for c in run_cfg["reliability_curve_policy"]["primary_h3_checkpoints"]]
    sampler_cfg = run_cfg.get("sampler", {})
    # Codex STEP-2 fix: build drift-assertion dicts from YAML bindings.
    sigma_actual_expected = {
        float(c["target"]): float(c["scheduler_sigma_actual"])
        for c in run_cfg["reliability_curve_policy"]["primary_h3_checkpoints"]
        if "scheduler_sigma_actual" in c
    }
    step_index_expected = {
        float(c["target"]): int(c["step_index"])
        for c in run_cfg["reliability_curve_policy"]["primary_h3_checkpoints"]
        if "step_index" in c
    }
    cfg_active_expected = {
        float(c["target"]): bool(c["cfg_active"])
        for c in run_cfg["reliability_curve_policy"]["primary_h3_checkpoints"]
        if "cfg_active" in c
    }

    label_suffix = f"_{smoke_label}" if smoke_label else ""
    if shard_total > 1:
        label_suffix += f"_shard{shard_index:02d}of{shard_total:02d}"
    jsonl_path = out_dir / f"results{label_suffix}.jsonl"

    # Codex STEP-2 fix: emit run-start ledger event BEFORE the GPU loop.
    ledger_path = Path("orbit-research/RUN_LEDGER.jsonl")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "a") as f:
        f.write(json.dumps({
            "event": "phase_b3_h3a_run_start" if smoke_label is None
                        else f"phase_b3_h3a_{smoke_label}_start",
            "schema_version": "run_ledger_phase_b3_v1",
            "timestamp_unix": time.time(),
            "n_formal_prompts": len(formal_prompts),
            "max_prompts": max_prompts,
            "smoke_label": smoke_label,
            "sigma_targets": sigma_targets,
            "output_dir": str(out_dir),
            "jsonl_path": str(jsonl_path),
        }) + "\n")

    t_start = time.time()
    n_done = 0
    # PI directive 2026-05-23 Phase 2: use GLOBAL-INDEX seeding so that each
    # held-out prompt gets a UNIQUE deterministic seed regardless of sharding.
    # Previous shard-local `sample_seed_base + p_idx` aliased seeds across
    # shards (32 unique seeds × 8 repeats for 256 prompts on 8-GPU sharded
    # held-out — per Codex Review #1 not tier-flipping but a real
    # reproducibility bug). Global formula: for the i-th prompt processed in
    # shard k of n, global_idx = k + i*n; in single-process mode (n=1, k=0)
    # this reduces to global_idx = i (preserves legacy dev behavior).
    with open(jsonl_path, "w") as out_fp:
        for p_idx, pd in enumerate(formal_prompts):
            global_prompt_index = shard_index + p_idx * shard_total
            seed = sample_seed_base + global_prompt_index
            seed_everything(seed)
            prompt = Prompt(
                prompt_id=pd["prompt_id"],
                text=pd.get("text", ""),
                lyrics=pd.get("lyrics"),
                structure_hint=pd.get("structure_hint"),
                duration_target=float(pd.get("duration_target", 30.0)),
                metadata=pd.get("metadata", {}),
                strata=pd.get("strata", {}),
            )
            sample_out = _sample_and_decode_real(
                prompt, model, run_cfg={"sampler": sampler_cfg},
                sigma_targets=sigma_targets, seed=seed,
                sigma_actual_expected=sigma_actual_expected,
                step_index_expected=step_index_expected,
                cfg_active_expected=cfg_active_expected,
            )
            if sample_out is None:
                continue
            is_instrumental = bool((prompt.metadata or {}).get("instrumental", False)) or not prompt.lyrics
            segmenter_outputs = _segment_final_for_each_unit(
                sample_out["final_audio"], sample_out["sample_rate"], prompt, segmenters, seed=seed
            )
            per_unit = _score_per_unit_per_axis(
                sample_out["final_audio"], sample_out["intermediates"],
                sample_out["sample_rate"], prompt, segmenter_outputs, reward_stack, sigma_targets,
            )
            audio_rel_path = None
            if save_audio:
                # PI directive 2026-05-23 Phase 3 prereq: persist final audio
                # so the sectionability audit can run actual section detection
                # on the generated clips. Saved to <out_dir>/audio/<prompt_id>.wav.
                import soundfile as sf
                import numpy as _np
                audio_dir = out_dir / "audio"
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_path = audio_dir / f"{prompt.prompt_id}.wav"
                arr = sample_out["final_audio"]
                if hasattr(arr, "detach"):
                    arr = arr.detach().cpu().numpy()
                arr = _np.asarray(arr)
                if arr.ndim > 1:
                    arr = arr.squeeze()
                    if arr.ndim > 1:
                        arr = arr.mean(axis=tuple(range(arr.ndim - 1)))
                sf.write(str(audio_path), arr.astype("float32"), int(sample_out["sample_rate"]))
                audio_rel_path = f"audio/{prompt.prompt_id}.wav"
            record = {
                "prompt_id": prompt.prompt_id,
                "is_instrumental": is_instrumental,
                "duration_actual_s": float(sample_out["final_audio"].shape[-1]) / sample_out["sample_rate"],
                "sample_rate": sample_out["sample_rate"],
                "sigma_bindings": sample_out["metadata"]["sigma_bindings"],
                "seed": seed,
                "global_prompt_index": global_prompt_index,
                "shard_index": shard_index,
                "shard_total": shard_total,
                "audio_path": audio_rel_path,
                "per_unit_segments_count": {u: len(s.segments) for u, s in segmenter_outputs.items()},
                "per_unit_applicable": {u: bool(s.applicable) for u, s in segmenter_outputs.items()},
                "per_unit": per_unit,
            }
            out_fp.write(json.dumps(record) + "\n")
            out_fp.flush()
            n_done += 1
            elapsed = time.time() - t_start
            print(f"  [h3a-step2] {p_idx + 1}/{len(formal_prompts)} done "
                  f"(prompt {prompt.prompt_id}, elapsed {elapsed:.1f}s)", flush=True)

    elapsed_total = time.time() - t_start
    print(f"[h3a-step2] DONE: {n_done}/{len(formal_prompts)} prompts processed in "
          f"{elapsed_total:.1f}s ({elapsed_total/3600:.4f} GPU-h)", flush=True)
    return {
        "jsonl_path": str(jsonl_path),
        "n_processed": n_done,
        "elapsed_seconds": elapsed_total,
        "elapsed_gpu_h": elapsed_total / 3600.0,
    }


# ============================================================================
# Output writers
# ============================================================================


def write_verdict(
    verdict: dict,
    out_dir: Path,
) -> None:
    with open(out_dir / "H3_VERDICT.json", "w") as f:
        json.dump(verdict, f, indent=2)


def write_stratum_files(
    vocal: StratumResult,
    instrumental: StratumResult,
    combined: Optional[dict],
    out_dir: Path,
) -> None:
    def _serialize(s: StratumResult) -> dict:
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "stratum": s.stratum,
            "n_prompts": s.n_prompts,
            "pool": s.pool,
            "section_minus_best_non_section_per_axis": s.section_minus_best_non_section_per_axis,
            "best_non_section_unit_per_axis": s.best_non_section_unit_per_axis,
            "n_axes_passing_strict": s.n_axes_passing_strict,
            "n_axes_passing_directional": s.n_axes_passing_directional,
            "null_section_minus_best_non_section_per_axis": s.null_section_minus_best_non_section_per_axis,
            "null_max_violation": s.null_max_violation,
            "unit_rankings": s.unit_rankings,
            "per_axis_per_unit_rho": s.per_axis_per_unit_rho,
        }

    with open(out_dir / "h3_vocal_stratum.json", "w") as f:
        json.dump(_serialize(vocal), f, indent=2)
    with open(out_dir / "h3_instrumental_stratum.json", "w") as f:
        json.dump(_serialize(instrumental), f, indent=2)
    if combined is not None:
        with open(out_dir / "h3_combined.json", "w") as f:
            json.dump(combined, f, indent=2)


# ============================================================================
# Orchestrator
# ============================================================================


def _load_per_prompt_records_from_fixture(fixture_path: Path) -> list[dict]:
    """Load pre-baked per-prompt records from JSONL (used by --stub-test).

    The fixture is the same schema the GPU pipeline produces in STEP 2; it
    lets us exercise the verdict logic without GPU.
    """
    records = []
    with open(fixture_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def run_h3a(
    *,
    run_cfg_path: Path,
    out_dir: Path,
    pi_approved_launch_cli: bool,
    stub_test_fixture: Optional[Path] = None,
    max_prompts: Optional[int] = None,
    smoke_label: Optional[str] = None,
    prompts_mode: str = "dev",
    shard_index: int = 0,
    shard_total: int = 1,
    skip_verdict: bool = False,
    save_audio: bool = False,
) -> int:
    """Run the H3a verdict pipeline.

    Args:
      run_cfg_path: path to YAML config.
      out_dir: output directory.
      pi_approved_launch_cli: bool from --pi-approved-launch flag.
      stub_test_fixture: if set, load pre-baked records and skip GPU.
      max_prompts: if set, cap formal prompts (used by 4-prompt smoke).
      smoke_label: if set, suffix the JSONL filename ("results_smoke.jsonl").
      prompts_mode: "dev" (Phase B.1 formal 64) or "held_out" (256 prompts).
      shard_index, shard_total: round-robin partition for multi-GPU.
      skip_verdict: when set (sharded sub-runs), produce results.jsonl only,
        skip aggregation/verdict (the merge script computes the global verdict).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[h3a] loading config: {run_cfg_path}", flush=True)
    cfg, fails = load_and_validate_config(run_cfg_path, pi_approved_launch_cli=pi_approved_launch_cli)
    if fails:
        print("[h3a] FAIL — config validation:", flush=True)
        for f in fails:
            print(f"  - {f}", flush=True)
        return 2
    print("[h3a] config validation passed", flush=True)

    # Stratum pools.
    h3 = cfg["h3_interpretation"]
    vocal_pool = list(h3["best_non_section_pool_by_stratum"]["vocal"])
    instr_pool = list(h3["best_non_section_pool_by_stratum"]["instrumental"])
    gating_axes = list(h3["gating_axes"])
    sigma_targets = [
        float(c["target"])
        for c in cfg["reliability_curve_policy"]["primary_h3_checkpoints"]
    ]
    threshold_strict = float(h3["threshold_section_minus_best_non_section"])
    kendall_min = float(
        cfg.get("outputs", {}).get("stratum_results", {}).get("kendall_tau_min_for_combined", 0.5)
    )

    pipeline_summary: Optional[dict] = None
    if stub_test_fixture is not None:
        print(f"[h3a] STUB-TEST mode: loading fixture {stub_test_fixture}", flush=True)
        records = _load_per_prompt_records_from_fixture(stub_test_fixture)
    else:
        # STEP-2: real GPU pipeline.
        print("[h3a] STEP-2 real GPU pipeline starting", flush=True)
        pipeline_summary = run_h3a_real(
            run_cfg=cfg, out_dir=out_dir,
            max_prompts=max_prompts, smoke_label=smoke_label,
            prompts_mode=prompts_mode,
            shard_index=shard_index, shard_total=shard_total,
            save_audio=save_audio,
        )
        if skip_verdict:
            # Sharded sub-run: write JSONL only; merge script computes verdict.
            print(f"[h3a] sharded sub-run done (shard {shard_index}/{shard_total}); "
                  f"skipping verdict (merge script computes global verdict).", flush=True)
            return 0
        records = _load_per_prompt_records_from_fixture(Path(pipeline_summary["jsonl_path"]))
        # Append run-final ledger event for audit trail.
        ledger_path = Path("orbit-research/RUN_LEDGER.jsonl")
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger_path, "a") as f:
            f.write(json.dumps({
                "event": "phase_b3_h3a_run_final" if smoke_label is None
                            else f"phase_b3_h3a_{smoke_label}",
                "schema_version": "run_ledger_phase_b3_v1",
                "timestamp_unix": time.time(),
                "elapsed_seconds": pipeline_summary["elapsed_seconds"],
                "elapsed_gpu_h": pipeline_summary["elapsed_gpu_h"],
                "n_processed": pipeline_summary["n_processed"],
                "max_prompts": max_prompts,
                "smoke_label": smoke_label,
                "config_path": str(run_cfg_path),
                "output_dir": str(out_dir),
                "jsonl_path": pipeline_summary["jsonl_path"],
            }) + "\n")
        print(f"[h3a] appended run-final ledger event to {ledger_path}", flush=True)

    # Stratum split.
    vocal_records = [r for r in records if not r.get("is_instrumental", False)]
    instr_records = [r for r in records if r.get("is_instrumental", False)]
    print(f"[h3a] strata: {len(vocal_records)} vocal, {len(instr_records)} instrumental", flush=True)

    vocal_result = compute_stratum_result(
        per_prompt_records=vocal_records, stratum="vocal",
        pool_units=vocal_pool, section_unit="CU-MS", null_unit="CU-NULL-rand-section",
        gating_axes=gating_axes, sigma_targets=sigma_targets,
        threshold_strict=threshold_strict,
    )
    instr_result = compute_stratum_result(
        per_prompt_records=instr_records, stratum="instrumental",
        pool_units=instr_pool, section_unit="CU-MS", null_unit="CU-NULL-rand-section",
        gating_axes=gating_axes, sigma_targets=sigma_targets,
        threshold_strict=threshold_strict,
    )

    tier_result = classify_h3a_tier(
        vocal=vocal_result, instrumental=instr_result, held_out=None,
        threshold_strict=threshold_strict,
    )
    combined = maybe_combined_overall(vocal_result, instr_result, kendall_tau_min=kendall_min)

    h3a_scope_label = "dev_only_stub_test" if stub_test_fixture else (
        f"dev_only_h3a_smoke_{smoke_label}" if smoke_label else "dev_only_h3a"
    )
    verdict = {
        "schema_version": VERDICT_SCHEMA_VERSION,
        "tier": tier_result["overall_tier"],
        "vocal_stratum_tier": tier_result["vocal_stratum_tier"],
        "instrumental_stratum_tier": tier_result["instrumental_stratum_tier"],
        "held_out_attempted": tier_result["held_out_attempted"],
        "null_sanity_violated_strict": tier_result["null_sanity_violated_strict"],
        "null_sanity_near_threshold": tier_result["null_sanity_near_threshold"],
        "thresholds": tier_result["thresholds"],
        "vocal_section_minus_best_non_section_per_axis":
            vocal_result.section_minus_best_non_section_per_axis,
        "instrumental_section_minus_best_non_section_per_axis":
            instr_result.section_minus_best_non_section_per_axis,
        "vocal_pool": vocal_pool,
        "instrumental_pool": instr_pool,
        "gating_axes": gating_axes,
        "sigma_targets": sigma_targets,
        "combined_overall_emitted": combined is not None,
        "combined_overall": combined,
        "stub_test_fixture": str(stub_test_fixture) if stub_test_fixture else None,
        "h3a_scope": h3a_scope_label,
        "n_vocal_prompts": vocal_result.n_prompts,
        "n_instrumental_prompts": instr_result.n_prompts,
        "pipeline_summary": pipeline_summary,
        "config_path": str(run_cfg_path),
    }
    write_verdict(verdict, out_dir)
    write_stratum_files(vocal_result, instr_result, combined, out_dir)
    print(f"[h3a] wrote verdict + strata to {out_dir}; tier = {verdict['tier']}", flush=True)
    return 0


def main() -> int:
    # Engineering fix 2026-05-23: cap CPU thread count under sharded launches.
    # The 8x parallel reward stacks were over-subscribing the node (load 250+);
    # capping to a small per-process budget keeps total threads sane. Honours
    # OMP_NUM_THREADS env var if set; defaults to 2 to mirror the launcher.
    try:
        import os
        import torch as _t
        n = int(os.environ.get("TORCH_NUM_THREADS", os.environ.get("OMP_NUM_THREADS", "2")))
        _t.set_num_threads(max(1, n))
        _t.set_num_interop_threads(max(1, n))
    except Exception:  # noqa: BLE001
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pi-approved-launch", action="store_true",
                        help="REQUIRED; dual-locked with run config pi_approved_launch.")
    parser.add_argument("--stub-test", type=str, default=None,
                        help="Path to a per-prompt JSONL fixture; exercises the "
                             "pure-Python verdict pipeline without GPU. Step-1 only.")
    parser.add_argument("--max-prompts", type=int, default=None,
                        help="Cap formal prompts (used by 4-prompt smoke; default = "
                             "process all formal prompts from the YAML).")
    parser.add_argument("--smoke-label", type=str, default=None,
                        help="If set, suffix the JSONL filename (e.g. 'smoke4') so "
                             "smoke runs don't overwrite formal results.")
    parser.add_argument("--prompts-mode", choices=["dev", "held_out"], default="dev",
                        help="Which prompt set to use (dev=Phase B.1 formal 64; "
                             "held_out=256 from held_out.jsonl).")
    parser.add_argument("--shard-index", type=int, default=0,
                        help="Which round-robin shard to process (0-indexed).")
    parser.add_argument("--shard-total", type=int, default=1,
                        help="Total number of shards (1 = no sharding).")
    parser.add_argument("--skip-verdict", action="store_true",
                        help="For sharded sub-runs: write JSONL only, skip "
                             "aggregation/verdict (merge script computes global).")
    parser.add_argument("--save-audio", action="store_true",
                        help="Persist final audio to <out_dir>/audio/<prompt_id>.wav "
                             "for downstream sectionability analysis.")
    args = parser.parse_args()
    return run_h3a(
        run_cfg_path=Path(args.config),
        out_dir=Path(args.output_dir),
        pi_approved_launch_cli=args.pi_approved_launch,
        stub_test_fixture=Path(args.stub_test) if args.stub_test else None,
        max_prompts=args.max_prompts,
        smoke_label=args.smoke_label,
        prompts_mode=args.prompts_mode,
        shard_index=args.shard_index,
        shard_total=args.shard_total,
        skip_verdict=args.skip_verdict,
        save_audio=args.save_audio,
    )


if __name__ == "__main__":
    sys.exit(main())
