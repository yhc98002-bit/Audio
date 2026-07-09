"""Phase B.1 — Tweedie reliability characterization driver (σ curve design).

Implements the formal Phase B.1 H2 reliability test per:
  configs/runs/phase_b1_reliability.yaml  (run config; σ curve, prompts, gates)
  configs/eval/gate_v2.yaml.draft         (gate evaluator policy; σ checkpoints)

Driver responsibilities (per PI directive 2026-05-22):
  (a) Load and validate BOTH configs; assert internal consistency of the
      σ curve, sampler binding, and ρ_gate threshold.
  (b) Enforce prompt exclusion: PHASE_B1 formal_prompt_ids ∩ SIGMA_CAL
      excluded_prompt_ids MUST be ∅.
  (c) Refuse to launch unless `pi_approved_launch: true` in the run config
      AND `--pi-approved-launch` CLI flag is set (dual lock).
  (d) For each formal prompt: sample once with return_trajectory=True;
      extract trajectory_model_outputs[k] (captured v_effective; branch-aware
      semantics per the verified captured-v parity).
  (e) For each predeclared σ (primary + late_reference): Tweedie-decode using
      `x̂_0 = z_k − σ_k · v_effective(k)`, then score all 7 reward axes.
      DO NOT recompute velocity via predict_velocity; the captured trajectory
      v_out is the authoritative effective velocity at each step.
  (f) Compute per-axis × σ Spearman ρ(intermediate reward, final reward).
  (g) Apply h2_interpretation.proposed_primary_pass_rule (primary region only).
      Late-reference σ contributes only to descriptive figures.
  (h) Emit required figure outputs (reward emergence, reliability curves,
      non-triviality diagnostics, exploratory quartile curves).
  (i) Append a run-final record to orbit-research/RUN_LEDGER.jsonl.
  (j) Hard-fail if the GPU-h budget hard cap is exceeded.

NOT YET EXECUTED. PI must approve launch separately.

Usage (non-executed example):
    python scripts/phase_b1_reliability.py \
        --config configs/runs/phase_b1_reliability.yaml \
        --gate-policy configs/eval/gate_v2.yaml.draft \
        --output-dir runs/phase_b1_reliability/ \
        --pi-approved-launch
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import yaml

from mprm.common.seeding import seed_everything
from mprm.data.prompts import Prompt


# ----------------------------------------------------------- helpers


def log_spectral_distance(a: torch.Tensor, b: torch.Tensor) -> float:
    """LSD (mono-folded) between two waveforms."""
    a = a.mean(dim=0) if a.dim() == 2 else a
    b = b.mean(dim=0) if b.dim() == 2 else b
    if a.shape[-1] > b.shape[-1]:
        a = a[..., : b.shape[-1]]
    elif b.shape[-1] > a.shape[-1]:
        b = b[..., : a.shape[-1]]
    A = torch.stft(a, n_fft=2048, hop_length=512, return_complex=True).abs().clamp_min(1e-8).log()
    B = torch.stft(b, n_fft=2048, hop_length=512, return_complex=True).abs().clamp_min(1e-8).log()
    return float((A - B).pow(2).mean().sqrt())


def spearman(x: list[float], y: list[float]) -> float:
    if len(x) < 2 or len(x) != len(y):
        return float("nan")

    def rank(v):
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
    return num / (dx * dy + 1e-12)


def _pick(target: float, sigmas: list[float]) -> int:
    return min(range(len(sigmas)), key=lambda k: abs(sigmas[k] - target))


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "median": None, "mean": None, "pstdev": None, "min": None, "max": None}
    return {
        "n": len(xs),
        "median": statistics.median(xs),
        "mean": statistics.mean(xs),
        "pstdev": statistics.pstdev(xs) if len(xs) > 1 else 0.0,
        "min": min(xs),
        "max": max(xs),
    }


def _quartiles(xs: list[float]) -> list[float]:
    """Return [q1, q2, q3] — Tukey-style hinges; falls back gracefully on small n."""
    if not xs:
        return [float("nan")] * 3
    s = sorted(xs)
    n = len(s)
    q1 = s[n // 4]
    q2 = s[n // 2]
    q3 = s[(3 * n) // 4] if (3 * n) // 4 < n else s[-1]
    return [q1, q2, q3]


# ----------------------------------------------------------- config types


@dataclass
class SigmaCheckpoint:
    target: float
    scheduler_sigma_actual: float
    step_index: int
    cfg_active: bool
    role: str  # "primary_nontrivial" | "late_reference"


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _validate_consistency(run_cfg: dict, gate_cfg: dict) -> list[str]:
    """Cross-validate run config vs gate evaluator policy. Returns list of failures."""
    fails: list[str] = []

    # Sampler binding parity
    rs = run_cfg["sampler"]
    gs = gate_cfg["round_2_context"]["sampler_binding"]
    for key in ("cfg_type", "use_erg_tag", "use_erg_lyric", "use_erg_diffusion",
                "guidance_interval", "guidance_scale", "infer_step", "scheduler_shift"):
        if rs.get(key) != gs.get(key):
            fails.append(f"sampler.{key}: run={rs.get(key)!r} vs gate={gs.get(key)!r}")

    # σ curve parity
    gate_curve = gate_cfg["round_2_context"]["tweedie_reliability_curve"]
    gate_checkpoints = gate_curve["checkpoints"]
    run_primary = run_cfg["reliability_curve"]["primary_nontrivial"]
    run_late = run_cfg["reliability_curve"]["late_reference"]
    expected_primary = set(gate_curve["primary_nontrivial_targets"])
    expected_late = set(gate_curve["late_reference_targets"])
    actual_primary = {c["target"] for c in run_primary}
    actual_late = {c["target"] for c in run_late}
    if actual_primary != expected_primary:
        fails.append(f"primary σ mismatch: run={sorted(actual_primary)} vs gate={sorted(expected_primary)}")
    if actual_late != expected_late:
        fails.append(f"late_reference σ mismatch: run={sorted(actual_late)} vs gate={sorted(expected_late)}")

    # Per-σ binding parity (full-precision sigma_actual + step_index + cfg_active)
    for cp in run_primary + run_late:
        key = f"{cp['target']:.1f}"  # YAML stores as "0.9" "0.8" etc
        # Try multiple key formats since YAML may serialize 0.9 as "0.9" or 0.9
        gate_cp = gate_checkpoints.get(key)
        if gate_cp is None:
            # Try numeric key
            for k in gate_checkpoints:
                try:
                    if abs(float(k) - cp["target"]) < 1e-9:
                        gate_cp = gate_checkpoints[k]
                        break
                except (TypeError, ValueError):
                    continue
        if gate_cp is None:
            fails.append(f"σ={cp['target']} missing from gate_cfg.checkpoints")
            continue
        if abs(gate_cp["scheduler_sigma_actual"] - cp["scheduler_sigma_actual"]) > 1e-12:
            fails.append(f"σ={cp['target']} sigma_actual mismatch")
        if gate_cp["step_index"] != cp["step_index"]:
            fails.append(f"σ={cp['target']} step_index mismatch")
        if gate_cp["cfg_active"] != cp["cfg_active"]:
            fails.append(f"σ={cp['target']} cfg_active mismatch")

    # ρ_gate threshold parity
    run_thr = run_cfg["h2_interpretation"]["eligibility_threshold"]
    gate_thr = gate_cfg["round_2_context"]["tweedie_reliability_threshold"]["rho_min"]
    if run_thr != gate_thr:
        fails.append(f"eligibility_threshold: run={run_thr} vs gate.rho_min={gate_thr}")

    # σ=0.1 must be excluded
    excluded = run_cfg["reliability_curve"]["excluded_from_primary_run"]
    if 0.1 not in excluded:
        fails.append(f"σ=0.1 must appear in reliability_curve.excluded_from_primary_run (got {excluded!r})")

    return fails


def _enforce_prompt_disjointness(formal_ids: list[str], excluded_ids: list[str]) -> list[str]:
    overlap = set(formal_ids) & set(excluded_ids)
    if overlap:
        return [f"prompt-list disjointness violated: overlap with σ-cal = {sorted(overlap)}"]
    return []


def _check_pi_approval(run_cfg: dict, cli_flag: bool) -> list[str]:
    fails: list[str] = []
    if not run_cfg.get("pi_approved_binding", False):
        fails.append("run config pi_approved_binding=false; PI must approve σ curve before launch")
    if not run_cfg.get("pi_approved_launch", False):
        fails.append("run config pi_approved_launch=false; PI must flip this to true before launch")
    if not cli_flag:
        fails.append("--pi-approved-launch CLI flag is required (dual-lock with config)")
    gate_status = (
        run_cfg["reliability_curve"].get("pi_approval_status")
        or "MISSING"
    )
    # Codex review 2026-05-23 fix: accept dated approval tags like
    # "PI_APPROVED_2026-05-23", "PI_APPROVED_2026-05-22", etc. The frozen
    # configs intentionally include the approval date in the status string
    # for audit-trail clarity. Reject only PENDING_PI_REVIEW / MISSING /
    # statuses that do not start with "PI_APPROVED".
    if not str(gate_status).startswith("PI_APPROVED"):
        fails.append(
            f"reliability_curve.pi_approval_status={gate_status!r}; "
            f"must start with 'PI_APPROVED' (e.g. 'PI_APPROVED_2026-05-23')"
        )
    return fails


def _iqr(xs: list[float]) -> float | None:
    if not xs or len(xs) < 2:
        return None
    s = sorted(xs)
    n = len(s)
    lo = s[n // 4]
    hi = s[(3 * n) // 4] if (3 * n) // 4 < n else s[-1]
    return float(hi - lo)


def _cohens_d(top: list[float], bot: list[float]) -> float | None:
    """Pooled-SD Cohen's d for top vs bottom quartile intermediate values."""
    if len(top) < 2 or len(bot) < 2:
        return None
    mt = statistics.mean(top)
    mb = statistics.mean(bot)
    vt = statistics.pvariance(top)
    vb = statistics.pvariance(bot)
    n1, n2 = len(top), len(bot)
    pooled_var = ((n1 - 1) * vt + (n2 - 1) * vb) / max(n1 + n2 - 2, 1)
    if pooled_var <= 0:
        return None
    return float((mt - mb) / (pooled_var ** 0.5))


def _compute_quartile_emergence(
    rewards_keys: list[str],
    per_axis_final: dict[str, list[float]],
    formal_ids: list[str],
    final_per_prompt_axis: dict[str, dict[str, float]],
    per_axis_sigma_intermediate_prompt: dict[tuple[str, float], list[tuple[str, float]]],
    all_checkpoints: list,
    cfg_boundary_meta: dict,
) -> dict:
    """Quartile-stratified intermediate reward across σ for each reward axis.

    Per PI directive 2026-05-23 (revised): handle degenerate quartile
    boundaries (q1==q3 when many prompts tie at a single value, common for
    lyric_intelligibility WER=0 on a clean-vocal corpus) by falling back to
    median-split top/bottom buckets. Adds IQR, range, top-bot gap, and
    Cohen's d to per-sigma stats.

    Output is `must_not_influence_gate: true` per spec.
    """
    qe: dict[str, dict] = {"_cfg_branch_metadata": cfg_boundary_meta}
    for axis_id in rewards_keys:
        finals = per_axis_final[axis_id]
        n_final = len(finals)
        if n_final < 4:
            qe[axis_id] = {
                "note": f"n<4 ({n_final}); quartile stratification skipped",
                "must_not_influence_gate": True,
            }
            continue
        q1, q2, q3 = _quartiles(finals)
        degenerate = (q1 == q3)
        bucket_top: list[str] = []
        bucket_bottom: list[str] = []
        if degenerate:
            # Fall back to median-split top/bottom (use mean for tie-breaking
            # vs median when median equals min or max).
            mean_final = statistics.mean(finals)
            median_final = statistics.median(finals)
            split_point = mean_final if mean_final != median_final else median_final
            for pid in formal_ids:
                v = final_per_prompt_axis.get(pid, {}).get(axis_id)
                if v is None:
                    continue
                if v > split_point:
                    bucket_top.append(pid)
                elif v < split_point:
                    bucket_bottom.append(pid)
                # ties at the split point are dropped (rare since we picked
                # mean over median when median was degenerate)
            stratification_mode = "median_split_fallback"
        else:
            for pid in formal_ids:
                v = final_per_prompt_axis.get(pid, {}).get(axis_id)
                if v is None:
                    continue
                if v <= q1:
                    bucket_bottom.append(pid)
                elif v >= q3:
                    bucket_top.append(pid)
            stratification_mode = "quartile_q1_q3"

        per_sigma_top_bot: dict[str, dict] = {}
        for cp in all_checkpoints:
            interm = per_axis_sigma_intermediate_prompt.get((axis_id, cp.target), [])
            interm_by_pid = dict(interm)
            top_vals = [interm_by_pid[p] for p in bucket_top if p in interm_by_pid]
            bot_vals = [interm_by_pid[p] for p in bucket_bottom if p in interm_by_pid]
            top_stats = _stats(top_vals)
            bot_stats = _stats(bot_vals)
            top_med = top_stats.get("median")
            bot_med = bot_stats.get("median")
            gap = (top_med - bot_med) if (top_med is not None and bot_med is not None) else None
            top_range = None
            bot_range = None
            if top_vals:
                top_range = float(max(top_vals) - min(top_vals))
            if bot_vals:
                bot_range = float(max(bot_vals) - min(bot_vals))
            per_sigma_top_bot[str(cp.target)] = {
                "top_quartile_stats": top_stats,
                "bottom_quartile_stats": bot_stats,
                "top_iqr": _iqr(top_vals),
                "bottom_iqr": _iqr(bot_vals),
                "top_range": top_range,
                "bottom_range": bot_range,
                "top_minus_bottom_median_gap": gap,
                "cohens_d_top_minus_bottom": _cohens_d(top_vals, bot_vals),
            }
        qe[axis_id] = {
            "final_quartile_thresholds": {"q1": q1, "q2": q2, "q3": q3},
            "stratification_mode": stratification_mode,
            "stratification_note": (
                "Final-reward quartile boundaries are degenerate "
                "(q1==q3); falling back to median-split top/bottom."
                if degenerate else
                "Standard top-Q4 (final >= q3) vs bottom-Q1 (final <= q1) split."
            ),
            "n_top": len(bucket_top),
            "n_bottom": len(bucket_bottom),
            "per_sigma": per_sigma_top_bot,
            "must_not_influence_gate": True,
        }
    return qe


def _write_quartile_table(quartile_emergence: dict, csv_path: Path) -> None:
    """Plot-ready long-format CSV: sigma,axis,top_q_median,bot_q_median,gap,top_iqr,bot_iqr,top_range,bot_range,cohens_d,branch."""
    import csv
    branch_per_sigma = quartile_emergence.get("_cfg_branch_metadata", {}).get(
        "branch_per_sigma", {}
    )
    rows = []
    for axis_id, payload in quartile_emergence.items():
        if axis_id.startswith("_"):
            continue
        per_sigma = payload.get("per_sigma")
        if not per_sigma:
            continue
        for sigma_key, stats in per_sigma.items():
            rows.append({
                "sigma": sigma_key,
                "axis": axis_id,
                "top_q_median": stats.get("top_quartile_stats", {}).get("median"),
                "bot_q_median": stats.get("bottom_quartile_stats", {}).get("median"),
                "top_minus_bot_gap": stats.get("top_minus_bottom_median_gap"),
                "top_iqr": stats.get("top_iqr"),
                "bot_iqr": stats.get("bottom_iqr"),
                "top_range": stats.get("top_range"),
                "bot_range": stats.get("bottom_range"),
                "cohens_d": stats.get("cohens_d_top_minus_bottom"),
                "branch": branch_per_sigma.get(sigma_key, "unknown"),
                "n_top": stats.get("top_quartile_stats", {}).get("n"),
                "n_bottom": stats.get("bottom_quartile_stats", {}).get("n"),
            })
    with open(csv_path, "w", newline="") as f:
        if not rows:
            f.write("sigma,axis,top_q_median,bot_q_median,top_minus_bot_gap,top_iqr,bot_iqr,top_range,bot_range,cohens_d,branch,n_top,n_bottom\n")
            return
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _classify_tier(per_axis_sigma_rho: dict[str, dict[str, float]],
                    threshold: float,
                    early_sigmas: set[float],
                    middle_sigmas: set[float],
                    primary_sigmas: set[float],
                    late_reference_sigmas: set[float],
                    ) -> dict:
    """Apply the PI-locked tiered H2 interpretation rule (2026-05-23, revised).

    PI directive 2026-05-23 (revision): a STRONG-looking result that has
    near-threshold primary pairs but whose STRONG classification does NOT
    depend on counting those pairs is classified as
    ``STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES``, not AMBIGUOUS. AMBIGUOUS is
    reserved for cases where the tier classification TRULY depends on
    threshold-rounding (i.e. removing near-threshold pairs breaks the STRONG
    criterion).

    Returns dict with tier and all introspection fields used by the verdict
    writer (surviving pairs, near-threshold pairs, coverage flags, etc.).
    """
    surviving_primary: list[tuple[str, float, float]] = []
    surviving_late: list[tuple[str, float, float]] = []
    near_threshold_primary: list[tuple[str, float, float]] = []  # ρ ∈ [0.5, 0.55] PRIMARY only
    for axis_id, by_sigma in per_axis_sigma_rho.items():
        for sigma_key, rho in by_sigma.items():
            if rho is None or (isinstance(rho, float) and rho != rho):
                continue
            s = float(sigma_key)
            if rho >= threshold:
                if s in primary_sigmas:
                    surviving_primary.append((axis_id, s, rho))
                    if threshold <= rho <= threshold + 0.05:
                        near_threshold_primary.append((axis_id, s, rho))
                elif s in late_reference_sigmas:
                    surviving_late.append((axis_id, s, rho))

    has_early = any(p[1] in early_sigmas for p in surviving_primary)
    has_middle = any(p[1] in middle_sigmas for p in surviving_primary)
    n_primary = len(surviving_primary)

    # Non-near-threshold (strict) subset — used to check whether STRONG
    # classification holds independent of threshold-rounding-sensitive pairs.
    surviving_primary_strict = [
        (a, s, r) for (a, s, r) in surviving_primary
        if not (threshold <= r <= threshold + 0.05)
    ]
    n_primary_strict = len(surviving_primary_strict)
    has_early_strict = any(p[1] in early_sigmas for p in surviving_primary_strict)
    has_middle_strict = any(p[1] in middle_sigmas for p in surviving_primary_strict)

    strong_holds_full = n_primary >= 2 and has_early and has_middle
    strong_holds_strict = n_primary_strict >= 2 and has_early_strict and has_middle_strict

    # Tier classification (PI directive 2026-05-23 revised):
    #   FAIL           → no primary pair survives.
    #   AMBIGUOUS      → either exactly 1 primary pair survives, OR STRONG
    #                    classification depends on near-threshold pairs (i.e.
    #                    holds with them but breaks without).
    #   STRONG_PASS    → STRONG criteria hold AND no near-threshold pairs.
    #   STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES → STRONG criteria hold even
    #                    when near-threshold pairs are excluded; near-
    #                    threshold pairs are present but non-load-bearing.
    #   SUPPORTED_PASS → ≥2 primary pairs but qualifying pairs are confined
    #                    to middle σ ∈ {0.7, 0.6}.
    #   AMBIGUOUS (early-only edge case) → ≥2 primary pairs but no middle σ.
    if n_primary == 0:
        tier = "FAIL"
    elif n_primary == 1:
        tier = "AMBIGUOUS"
    elif strong_holds_full and strong_holds_strict:
        # STRONG holds even after dropping near-threshold pairs.
        if near_threshold_primary:
            tier = "STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES"
        else:
            tier = "STRONG_PASS"
    elif strong_holds_full and not strong_holds_strict:
        # STRONG holds only with near-threshold pairs counted — truly
        # threshold-rounding-sensitive → AMBIGUOUS per PI rule.
        tier = "AMBIGUOUS"
    elif n_primary >= 2 and (not has_early) and has_middle:
        tier = "SUPPORTED_PASS"
    elif n_primary >= 2 and has_early and (not has_middle):
        # Early-only edge case.
        tier = "AMBIGUOUS"
    else:
        # Defensive default (should be unreachable given the branches above).
        tier = "FAIL"

    return {
        "tier": tier,
        "surviving_primary_pairs": [
            {"axis": a, "sigma": s, "rho": r}
            for a, s, r in sorted(surviving_primary)
        ],
        "surviving_primary_pairs_excluding_near_threshold": [
            {"axis": a, "sigma": s, "rho": r}
            for a, s, r in sorted(surviving_primary_strict)
        ],
        "surviving_late_reference_pairs_descriptive_only": [
            {"axis": a, "sigma": s, "rho": r}
            for a, s, r in sorted(surviving_late)
        ],
        "near_threshold_band_primary_only_0.50_0.55": [
            {"axis": a, "sigma": s, "rho": r}
            for a, s, r in sorted(near_threshold_primary)
        ],
        "has_early_sigma_0.9_or_0.8": has_early,
        "has_middle_sigma_0.7_or_0.6": has_middle,
        "has_early_strict_excluding_near_threshold": has_early_strict,
        "has_middle_strict_excluding_near_threshold": has_middle_strict,
        "n_surviving_primary_pairs": n_primary,
        "n_surviving_primary_pairs_strict": n_primary_strict,
        "strong_holds_full": bool(strong_holds_full),
        "strong_holds_strict": bool(strong_holds_strict),
        "classification_depends_on_near_threshold": bool(
            strong_holds_full and not strong_holds_strict
        ),
        "edge_case_early_only_ge2_primary": bool(
            n_primary >= 2 and has_early and (not has_middle)
        ),
    }


# ----------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--gate-policy", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pi-approved-launch", action="store_true",
                        help="REQUIRED for launch. Dual-locked with run config pi_approved_launch.")
    parser.add_argument("--audit-only", action="store_true",
                        help="Load + validate configs, print preflight summary, do NOT launch.")
    parser.add_argument("--smoke-prompt-id", default=None,
                        help="Smoke-test mode: run a single prompt (by prompt_id) through the FULL "
                             "formal pipeline (sampling, captured-v Tweedie decode, all reward "
                             "axes, all figure outputs, ledger event labeled 'smoke'). The smoke "
                             "prompt MUST NOT be in formal_prompt_ids or excluded_prompt_ids. "
                             "Smoke mode skips the pi_approved_launch dual-lock but still runs the "
                             "config cross-validation and prompt-disjointness check. Output dir is "
                             "automatically suffixed with '_smoke'.")
    args = parser.parse_args()

    run_cfg_path = Path(args.config)
    gate_cfg_path = Path(args.gate_policy)
    out_dir = Path(args.output_dir)

    print(f"[preflight] Loading {run_cfg_path}", flush=True)
    run_cfg = _load_yaml(run_cfg_path)
    print(f"[preflight] Loading {gate_cfg_path}", flush=True)
    gate_cfg = _load_yaml(gate_cfg_path)

    # --- consistency checks ---
    print("[preflight] Cross-validating run config vs gate evaluator policy...", flush=True)
    fails = _validate_consistency(run_cfg, gate_cfg)
    if fails:
        print("\n[preflight] FAIL — consistency violations:", flush=True)
        for f in fails:
            print(f"  - {f}", flush=True)
        return 2

    # --- prompt-list disjointness ---
    formal = json.load(open(run_cfg["prompts"]["formal_prompt_ids_json"]))
    excluded = json.load(open(run_cfg["prompts"]["exclusions"]["source_json"]))
    formal_ids = formal["formal_prompt_ids"]
    excluded_ids = excluded["excluded_prompt_ids"]
    expected_n = run_cfg["prompts"]["n_formal_prompts"]
    if len(formal_ids) != expected_n:
        print(f"[preflight] FAIL — n_formal_prompts mismatch: file has {len(formal_ids)}, config expects {expected_n}",
              flush=True)
        return 2
    fails = _enforce_prompt_disjointness(formal_ids, excluded_ids)
    if fails:
        print("\n[preflight] FAIL — prompt-list:", flush=True)
        for f in fails:
            print(f"  - {f}", flush=True)
        return 2
    print(f"[preflight] OK: {len(formal_ids)} formal prompts, {len(excluded_ids)} excluded, "
          f"disjoint ✓", flush=True)

    # --- σ curve binding ---
    primary: list[SigmaCheckpoint] = [
        SigmaCheckpoint(c["target"], c["scheduler_sigma_actual"], c["step_index"],
                         c["cfg_active"], "primary_nontrivial")
        for c in run_cfg["reliability_curve"]["primary_nontrivial"]
    ]
    late: list[SigmaCheckpoint] = [
        SigmaCheckpoint(c["target"], c["scheduler_sigma_actual"], c["step_index"],
                         c["cfg_active"], "late_reference")
        for c in run_cfg["reliability_curve"]["late_reference"]
    ]
    all_checkpoints = primary + late
    print(f"[preflight] σ curve: {len(primary)} primary + {len(late)} late_reference = "
          f"{len(all_checkpoints)} checkpoints", flush=True)
    for cp in all_checkpoints:
        print(f"            σ={cp.target} (actual={cp.scheduler_sigma_actual:.4f}, step={cp.step_index}, "
              f"cfg_active={cp.cfg_active}, role={cp.role})", flush=True)

    # --- smoke-test mode override ---
    is_smoke = args.smoke_prompt_id is not None
    if is_smoke:
        if args.smoke_prompt_id in formal_ids:
            print(f"[preflight] FAIL — smoke prompt {args.smoke_prompt_id!r} is in formal_prompt_ids; "
                  f"choose a smoke prompt outside the formal set.", flush=True)
            return 2
        if args.smoke_prompt_id in excluded_ids:
            print(f"[preflight] FAIL — smoke prompt {args.smoke_prompt_id!r} is in σ-calibration "
                  f"excluded_prompt_ids; choose a different smoke prompt.", flush=True)
            return 2
        # Override the prompt list to just the smoke prompt.
        formal_ids = [args.smoke_prompt_id]
        out_dir = Path(str(out_dir).rstrip("/") + "_smoke")
        print(f"[smoke] Smoke-test mode: 1 prompt ({args.smoke_prompt_id}), "
              f"output_dir={out_dir}", flush=True)

    # --- PI approval (dual lock) — bypassed in smoke mode ---
    if is_smoke:
        print("[smoke] PI approval dual-lock skipped (smoke test); curve binding "
              "consistency still enforced.", flush=True)
    else:
        pi_fails = _check_pi_approval(run_cfg, args.pi_approved_launch)
        if args.audit_only:
            if pi_fails:
                print(f"\n[audit-only] PI approval gate would block launch:", flush=True)
                for f in pi_fails:
                    print(f"  - {f}", flush=True)
            else:
                print(f"\n[audit-only] PI approval gate would PASS launch.", flush=True)
            print("[audit-only] Preflight complete. Exiting without launching.", flush=True)
            return 0
        if pi_fails:
            print("\n[preflight] FAIL — PI approval gate:", flush=True)
            for f in pi_fails:
                print(f"  - {f}", flush=True)
            return 2

    # ============================================================
    # LAUNCH (gated above; we only reach here if PI fully approved)
    # ============================================================

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(exist_ok=True)
    results_path = out_dir / "results.jsonl"
    summary_path = out_dir / "per_axis_sigma_rho.json"
    verdict_path = out_dir / "H2_VERDICT.json"
    figures_dir = out_dir / "figures"

    # Build full prompt records.
    prompts_by_id: dict[str, dict] = {}
    with open(run_cfg["prompts"]["source"]) as f:
        for line in f:
            p = json.loads(line)
            prompts_by_id[p["prompt_id"]] = p
    formal_prompts = [prompts_by_id[pid] for pid in formal_ids if pid in prompts_by_id]

    # Load model + reward stack.
    from mprm.inference.ace_step import AceStepModel
    model = AceStepModel()

    from mprm.rewards.audiobox import AudioboxReward
    rewards: dict[str, Any] = {}
    for axis in ["PQ", "PC", "CE", "CU"]:
        rewards[f"aesthetic_{axis.lower()}"] = AudioboxReward(target_axis=axis)
    from mprm.rewards.clap import ClapReward
    rewards["semantic_fit"] = ClapReward()
    from mprm.rewards.mert import MertReward
    rewards["section_coherence"] = MertReward()
    from mprm.rewards.whisper_wer import WhisperWerReward
    rewards["lyric_intelligibility"] = WhisperWerReward()
    print(f"[run] Loaded {len(rewards)} reward axes", flush=True)

    sampler_cfg = run_cfg["sampler"]
    seed_base = 42
    t_start = time.time()
    hard_cap_s = run_cfg["compute"]["hard_cap_gpu_h"] * 3600.0

    # Per-prompt records (jsonl).
    # Per-(axis, σ) aggregates for Spearman + curves.
    per_axis_sigma_intermediate: dict[tuple[str, float], list[float]] = {}
    per_axis_final: dict[str, list[float]] = {axis: [] for axis in rewards}
    per_sigma_lsd: dict[float, list[float]] = {cp.target: [] for cp in all_checkpoints}
    # For exploratory quartile stratification:
    per_axis_sigma_intermediate_prompt: dict[tuple[str, float], list[tuple[str, float]]] = {}
    final_per_prompt_axis: dict[str, dict[str, float]] = {}

    with open(results_path, "w") as out_fp:
        for p_idx, pd in enumerate(formal_prompts):
            if time.time() - t_start > hard_cap_s:
                print(f"[abort] hard_cap_gpu_h={run_cfg['compute']['hard_cap_gpu_h']} exceeded", flush=True)
                return 3
            prompt = Prompt(
                prompt_id=pd["prompt_id"],
                text=pd.get("text", ""),
                lyrics=pd.get("lyrics"),
                structure_hint=pd.get("structure_hint"),
                duration_target=float(pd.get("duration_target", 30.0)),
            )
            seed = seed_base + p_idx
            seed_everything(seed)
            try:
                res = model.sample(
                    prompt, seed=seed,
                    cfg_scale=sampler_cfg["guidance_scale"],
                    steps=sampler_cfg["infer_step"],
                    return_trajectory=True,
                    extras={"cfg_type": sampler_cfg["cfg_type"],
                             "use_erg_tag": sampler_cfg["use_erg_tag"],
                             "use_erg_lyric": sampler_cfg["use_erg_lyric"],
                             "use_erg_diffusion": sampler_cfg["use_erg_diffusion"]},
                )
            except Exception as e:  # noqa: BLE001
                print(f"[run] FAIL sampling prompt={prompt.prompt_id}: {type(e).__name__}: {e}",
                      flush=True)
                return 1
            traj = res.trajectory or []
            traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
            traj_vs = (res.extras or {}).get("trajectory_model_outputs", [])
            cfg_active_flags = (res.extras or {}).get("trajectory_cfg_active", [])
            final_audio = res.waveform

            is_instrumental = bool((pd.get("metadata") or {}).get("instrumental", False)) \
                or (prompt.lyrics is None or len(prompt.lyrics or "") == 0)

            # Final-audio rewards
            final_axis_vals = {}
            for axis_id, reward_obj in rewards.items():
                if axis_id == "lyric_intelligibility" and is_instrumental:
                    final_axis_vals[axis_id] = None
                    continue
                try:
                    v = reward_obj.score(final_audio, res.sample_rate, prompt).value
                except Exception as e:  # noqa: BLE001
                    print(f"[run] final reward {axis_id} FAILED on {prompt.prompt_id}: {e}",
                          flush=True)
                    return 1
                final_axis_vals[axis_id] = v
                per_axis_final[axis_id].append(v)
            final_per_prompt_axis[prompt.prompt_id] = final_axis_vals

            # Per-σ intermediates
            per_sigma_records: list[dict] = []
            for cp in all_checkpoints:
                k = _pick(cp.target, traj_sigmas)
                sigma_actual = float(traj_sigmas[k])
                # Audit: confirm scheduler-σ matches binding within float tolerance
                if abs(sigma_actual - cp.scheduler_sigma_actual) > 1e-6:
                    print(f"[run] WARN σ drift on {prompt.prompt_id} σ_target={cp.target}: "
                          f"actual={sigma_actual} bound={cp.scheduler_sigma_actual}",
                          flush=True)
                if bool(cfg_active_flags[k]) != cp.cfg_active:
                    print(f"[run] FAIL cfg_active drift on {prompt.prompt_id} σ_target={cp.target}: "
                          f"actual={cfg_active_flags[k]} bound={cp.cfg_active}",
                          flush=True)
                    return 1
                v_eff = traj_vs[k]
                z_k = traj[k]
                # x̂_0 = z - σ · v_effective  (captured velocity; branch-aware semantics)
                z0 = z_k.to(torch.float32) - sigma_actual * v_eff.to(torch.float32)
                ahat = model.decode(z0)
                lsd = log_spectral_distance(ahat, final_audio)
                per_sigma_lsd[cp.target].append(lsd)

                axis_vals = {}
                for axis_id, reward_obj in rewards.items():
                    if axis_id == "lyric_intelligibility" and is_instrumental:
                        axis_vals[axis_id] = None
                        continue
                    try:
                        v = reward_obj.score(ahat, res.sample_rate, prompt).value
                    except Exception as e:  # noqa: BLE001
                        print(f"[run] intermediate reward {axis_id} FAILED on "
                              f"{prompt.prompt_id} σ={cp.target}: {e}", flush=True)
                        return 1
                    axis_vals[axis_id] = v
                    key = (axis_id, cp.target)
                    per_axis_sigma_intermediate.setdefault(key, []).append(v)
                    per_axis_sigma_intermediate_prompt.setdefault(key, []).append((prompt.prompt_id, v))

                per_sigma_records.append({
                    "sigma_target": cp.target,
                    "sigma_actual": sigma_actual,
                    "step_index": int(k),
                    "cfg_active": bool(cfg_active_flags[k]),
                    "role": cp.role,
                    "lsd": lsd,
                    "axis_values": axis_vals,
                })

            # Append per-prompt record
            out_fp.write(json.dumps({
                "prompt_id": prompt.prompt_id,
                "seed": seed,
                "is_instrumental": is_instrumental,
                "final_axis_values": final_axis_vals,
                "per_sigma": per_sigma_records,
            }) + "\n")
            out_fp.flush()

            if (p_idx + 1) % 8 == 0:
                el = time.time() - t_start
                print(f"  [run] {p_idx+1}/{len(formal_prompts)} prompts done, elapsed {el:.1f}s",
                      flush=True)

    elapsed_total = time.time() - t_start

    # --- per-axis × σ Spearman ---
    summary: dict[str, Any] = {
        "schema_version": "phase_b1_reliability_summary_v2",
        "run_config_sha": run_cfg_path.name,
        "gate_policy_sha": gate_cfg_path.name,
        "elapsed_seconds": elapsed_total,
        "elapsed_gpu_h": elapsed_total / 3600.0,
        "n_formal_prompts": len(formal_prompts),
        "per_axis_sigma_rho": {},
        "per_axis_sigma_n_paired": {},
    }
    for axis_id in rewards:
        summary["per_axis_sigma_rho"][axis_id] = {}
        summary["per_axis_sigma_n_paired"][axis_id] = {}
        finals = per_axis_final[axis_id]
        for cp in all_checkpoints:
            interm_pairs = per_axis_sigma_intermediate_prompt.get((axis_id, cp.target), [])
            # Align by prompt_id with final-audio reward list (which is in prompt-iteration order).
            # We use the same per-prompt order: per_axis_final[axis_id] is appended once per prompt
            # IFF the axis is computed for that prompt (e.g. lyric skipped on instrumental).
            # To keep alignment trivially correct, recompute pairs from final_per_prompt_axis:
            xs, ys = [], []
            for pid, v_interm in interm_pairs:
                v_final = final_per_prompt_axis[pid].get(axis_id)
                if v_final is None or v_interm is None:
                    continue
                xs.append(v_interm)
                ys.append(v_final)
            rho = spearman(xs, ys)
            summary["per_axis_sigma_rho"][axis_id][str(cp.target)] = rho
            summary["per_axis_sigma_n_paired"][axis_id][str(cp.target)] = len(xs)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[run] Per-axis × σ Spearman written: {summary_path}", flush=True)

    # --- apply h2_interpretation tiered rule (PI-locked 2026-05-23) ---
    threshold = run_cfg["h2_interpretation"]["eligibility_threshold"]
    rs = run_cfg["h2_interpretation"]["region_separation"]
    primary_sigmas = set(rs["primary_nontrivial_sigmas"])
    early_sigmas = set(rs["early_sigmas"])
    middle_sigmas = set(rs["middle_sigmas"])
    late_reference_sigmas = set(rs["late_reference_sigmas"])

    tier_result = _classify_tier(
        summary["per_axis_sigma_rho"], threshold,
        early_sigmas, middle_sigmas,
        primary_sigmas, late_reference_sigmas,
    )

    tier_meanings = {
        "STRONG_PASS": "Early quality-emergence evidence is supported (no near-threshold pairs).",
        "STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES": (
            "Early quality-emergence evidence is supported. Some primary pairs lie in "
            "the [0.50, 0.55] near-threshold band, but the STRONG criterion holds "
            "even when those pairs are excluded — classification is NOT load-bearing "
            "on near-threshold pairs."
        ),
        "SUPPORTED_PASS": ("Non-trivial process reward is supported, but do not claim "
                             "very-early emergence. Use only empirically supported σ "
                             "checkpoints for downstream M-PRM."),
        "AMBIGUOUS": ("Expand to 128 prompts using the SAME six-σ curve. Do not add "
                        "or change σ points."),
        "FAIL": ("Pivot to outcome-only / terminal-reward route per "
                   "NULL_RESULT_CONTRACT §2 Block B.1. Late_reference passes do NOT rescue."),
    }
    verdict = {
        "schema_version": "phase_b1_h2_verdict_v4",
        "tiered_rule_applied": (
            "PI-locked 2026-05-23 revised (STRONG_PASS / "
            "STRONG_PASS_WITH_NEAR_THRESHOLD_NOTES / SUPPORTED_PASS / AMBIGUOUS / FAIL)"
        ),
        "threshold": threshold,
        "tier": tier_result["tier"],
        "tier_meaning": tier_meanings[tier_result["tier"]],
        "surviving_primary_pairs": tier_result["surviving_primary_pairs"],
        "surviving_primary_pairs_excluding_near_threshold":
            tier_result["surviving_primary_pairs_excluding_near_threshold"],
        "surviving_late_reference_pairs_descriptive_only":
            tier_result["surviving_late_reference_pairs_descriptive_only"],
        "near_threshold_band_primary_only_0.50_0.55":
            tier_result["near_threshold_band_primary_only_0.50_0.55"],
        "edge_case_early_only_ge2_primary_pairs":
            tier_result["edge_case_early_only_ge2_primary"],
        "primary_region_coverage": {
            "has_early_sigma_0.9_or_0.8": tier_result["has_early_sigma_0.9_or_0.8"],
            "has_middle_sigma_0.7_or_0.6": tier_result["has_middle_sigma_0.7_or_0.6"],
            "has_early_strict_excluding_near_threshold":
                tier_result["has_early_strict_excluding_near_threshold"],
            "has_middle_strict_excluding_near_threshold":
                tier_result["has_middle_strict_excluding_near_threshold"],
            "n_surviving_primary_pairs": tier_result["n_surviving_primary_pairs"],
            "n_surviving_primary_pairs_strict":
                tier_result["n_surviving_primary_pairs_strict"],
        },
        "classification_depends_on_near_threshold":
            tier_result["classification_depends_on_near_threshold"],
        "strong_holds_full": tier_result["strong_holds_full"],
        "strong_holds_strict": tier_result["strong_holds_strict"],
        "note": (
            "Late-reference σ ∈ {0.5, 0.3} pairs above are descriptive only and "
            "DO NOT contribute to STRONG/SUPPORTED_PASS classification, and DO NOT "
            "rescue FAIL, per PI directive 2026-05-23."
        ),
    }
    with open(verdict_path, "w") as f:
        json.dump(verdict, f, indent=2)
    print(f"[run] H2 VERDICT written: {verdict_path} → tier={tier_result['tier']}",
          flush=True)

    # --- figure outputs (non-gating) ---
    figs: dict[str, Any] = {}

    # Shared metadata for all figures: marks the CFG-active → cond-only branch
    # transition (between σ=0.6 and σ=0.5 under guidance_interval=0.5 + 30 steps).
    # PI directive 2026-05-23: figures MUST surface this boundary so paper
    # readers understand the discontinuity in v_effective semantics across σ.
    sigma_ordered_desc = sorted(set(cp.target for cp in all_checkpoints), reverse=True)
    cfg_boundary_meta = {
        "guidance_interval": run_cfg["sampler"]["guidance_interval"],
        "start_idx": 7,
        "end_idx": 22,
        "cfg_branch_transition_between": [0.6, 0.5],
        "cfg_branch_transition_step_indices": [19, 22],
        "cfg_branch_transition_note": (
            "Captured v_effective is CFG-mixed for σ in {0.9, 0.8, 0.7, 0.6} "
            "(steps 7/12/16/19 inside guidance interval [7, 22)) and cond-only "
            "for σ in {0.5, 0.3} (steps 22/25 outside the interval). The "
            "transition lies between σ=0.6 (last CFG-mixed) and σ=0.5 (first "
            "cond-only); paper figures MUST mark this with a visible "
            "annotation (e.g. vertical dashed line between σ=0.6 and σ=0.5) "
            "and the legend must distinguish the two branches."
        ),
        "branch_per_sigma": {
            str(cp.target): ("CFG-mixed" if cp.cfg_active else "cond-only")
            for cp in all_checkpoints
        },
    }

    # reward_emergence_curves: median across prompts per (axis, σ); final reference
    reward_emergence: dict[str, dict] = {"_cfg_branch_metadata": cfg_boundary_meta}
    for axis_id in rewards:
        per_sigma_med = {}
        for cp in all_checkpoints:
            xs = per_axis_sigma_intermediate.get((axis_id, cp.target), [])
            per_sigma_med[str(cp.target)] = _stats(xs)
        final_stats = _stats(per_axis_final[axis_id])
        reward_emergence[axis_id] = {
            "per_sigma_stats": per_sigma_med,
            "final_stats": final_stats,
            "sigma_targets": [cp.target for cp in all_checkpoints],
            "primary_sigmas": sorted(primary_sigmas, reverse=True),
            "late_reference_sigmas": sorted(late_reference_sigmas, reverse=True),
        }
    with open(figures_dir / "reward_emergence.json", "w") as f:
        json.dump(reward_emergence, f, indent=2)
    figs["reward_emergence"] = str(figures_dir / "reward_emergence.json")

    # reliability_curves: same per_axis_sigma_rho already in summary
    with open(figures_dir / "reliability_curves.json", "w") as f:
        json.dump({
            "_cfg_branch_metadata": cfg_boundary_meta,
            "per_axis_sigma_rho": summary["per_axis_sigma_rho"],
            "threshold": threshold,
            "sigma_targets_ordered": sigma_ordered_desc,
            "primary_sigmas": sorted(primary_sigmas, reverse=True),
            "late_reference_sigmas": sorted(late_reference_sigmas, reverse=True),
        }, f, indent=2)
    figs["reliability_curves"] = str(figures_dir / "reliability_curves.json")

    # non_triviality_diagnostics: LSD + reward-gap-to-final
    nt: dict[str, Any] = {"_cfg_branch_metadata": cfg_boundary_meta,
                            "lsd_per_sigma": {}, "reward_gap_per_sigma_per_axis": {}}
    for cp in all_checkpoints:
        nt["lsd_per_sigma"][str(cp.target)] = _stats(per_sigma_lsd[cp.target])
    for axis_id in rewards:
        nt["reward_gap_per_sigma_per_axis"][axis_id] = {}
        for cp in all_checkpoints:
            interm_pairs = per_axis_sigma_intermediate_prompt.get((axis_id, cp.target), [])
            gaps = []
            for pid, v_interm in interm_pairs:
                v_final = final_per_prompt_axis[pid].get(axis_id)
                if v_final is None or v_interm is None:
                    continue
                gaps.append(v_interm - v_final)
            nt["reward_gap_per_sigma_per_axis"][axis_id][str(cp.target)] = _stats(gaps)
    with open(figures_dir / "non_triviality.json", "w") as f:
        json.dump(nt, f, indent=2)
    figs["non_triviality"] = str(figures_dir / "non_triviality.json")

    # quartile_emergence (exploratory; must_not_influence_gate)
    quartile_emergence = _compute_quartile_emergence(
        rewards_keys=list(rewards.keys()),
        per_axis_final=per_axis_final,
        formal_ids=formal_ids,
        final_per_prompt_axis=final_per_prompt_axis,
        per_axis_sigma_intermediate_prompt=per_axis_sigma_intermediate_prompt,
        all_checkpoints=all_checkpoints,
        cfg_boundary_meta=cfg_boundary_meta,
    )
    with open(figures_dir / "quartile_emergence.json", "w") as f:
        json.dump(quartile_emergence, f, indent=2)
    figs["quartile_emergence"] = str(figures_dir / "quartile_emergence.json")
    # plot-ready table CSV (long format: sigma, axis, top_q_median, bot_q_median, gap, top_iqr, bot_iqr)
    plot_table_path = figures_dir / "quartile_emergence_table.csv"
    _write_quartile_table(quartile_emergence, plot_table_path)
    figs["quartile_emergence_table"] = str(plot_table_path)

    # --- run-final ledger record ---
    ledger_event = {
        "event": ("phase_b1_reliability_smoke" if is_smoke
                  else "phase_b1_reliability_run_final"),
        "schema_version": "run_ledger_phase_b1_v3",
        "timestamp_unix": time.time(),
        "elapsed_seconds": elapsed_total,
        "elapsed_gpu_h": elapsed_total / 3600.0,
        "hard_cap_gpu_h": run_cfg["compute"]["hard_cap_gpu_h"],
        "config_path": str(run_cfg_path),
        "gate_policy_path": str(gate_cfg_path),
        "output_dir": str(out_dir),
        "n_formal_prompts": len(formal_prompts),
        "n_sigma_checkpoints": len(all_checkpoints),
        "is_smoke_test": is_smoke,
        "smoke_prompt_id": args.smoke_prompt_id if is_smoke else None,
        "h2_tier": tier_result["tier"],
        "verdict_path": str(verdict_path),
        "summary_path": str(summary_path),
        "figure_outputs": figs,
        "audit_trail": run_cfg["outputs"]["audit_trail"],
    }
    ledger_path = Path("orbit-research/RUN_LEDGER.jsonl")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "a") as f:
        f.write(json.dumps(ledger_event) + "\n")
    print(f"[run] Appended run-final event to {ledger_path}", flush=True)

    label = "smoke" if is_smoke else "formal"
    print(f"\n[run] DONE ({label}). elapsed={elapsed_total:.1f}s "
          f"({elapsed_total/3600:.4f} GPU-h); H2 tier={tier_result['tier']}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[fatal] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.exit(99)
