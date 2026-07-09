"""Compute the Phase A headroom gate decision per NULL_RESULT_CONTRACT.md §1.

STOP-B-7: Reads `gate_r_lcb` (the uniform `gate_v1` evaluator) — NOT each rung's
per-rung `r_lcb`. The per-rung r_lcb is computed under per-rung
`cfg.reward.lambda_probe` + `extras.perturbations`, which differ across rungs
(R0/R1 have no probe penalty + identity-only perts; R9 has full probe penalty +
5 perts). Comparing those across rungs was not commensurable — Codex flagged it
in the STOP-B-6 audit. gate_v1 fixes that by stamping a uniform metric onto
every gate-critical M1a result. compute_headroom_gate refuses to run unless
every gate-critical rung's sidecar matches the live gate_v1 hash AND every
result carries `gate_r_lcb`.

The script imports nothing torch-y: it reads results.jsonl as plain JSONL so
the gate is testable in CPU sandboxes (and so a corrupted torch install can't
hide a methodological failure behind an ImportError).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from dataclasses import asdict
from pathlib import Path

# NOTE: `headroom_gate` is imported lazily inside main() so the refusal path
# (missing sidecar, hash mismatch, missing gate_r_lcb) runs to completion
# without requiring `mprm` to be importable. This makes the gate testable in
# CPU sandboxes and means a broken `mprm` install can never hide a
# methodological failure behind an ImportError.

# STOP-B-7: gate-critical M1a rungs and their config-file basenames. KEEP THIS
# IN SYNC with scripts/launch_baseline.py::GATE_CRITICAL_RUNG_IDS. R3 is
# diagnostic-only (reward-hackability), R8a/R8b are M1b scaffolds; neither
# participates in the M1a headroom gate.
GATE_CRITICAL = {
    "r0_base": "base sampling",
    "r1_cfg_sweep": "CFG sweep (cfg-explain check)",
    "r2_bon": "BoN ceiling",
    "r4_bon_cfg": "BoN+CFG composite ceiling",
    "r9_s7_sampler_control": "S7 sampler-control (s7-explain check)",
}

GATE_EVAL_POLICY_PATH = Path("configs/eval/gate_v1.yaml")


def _load_gate_eval_policy(path: Path) -> tuple[dict, str]:
    """Local copy of `launch_baseline.load_gate_eval_policy()` — duplicated so
    compute_headroom_gate has zero `mprm.*` dependencies and can run before any
    torch import. Hash MUST match exactly. STOP-B-7.1 Q1/Q2/Q4: also validates
    finite floats + non-empty perturbations + reward_axes shape (so a broken
    policy YAML cannot quietly pass)."""
    import yaml  # pyyaml is a project-level dep, no torch
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict) or "eval_policy" not in raw:
        raise ValueError(f"{path}: missing top-level `eval_policy` key.")
    policy = raw["eval_policy"]
    for key in ("name", "version", "lambda_probe", "perturbations", "beta_robust",
                "reward_axes"):
        if key not in policy:
            raise ValueError(f"{path}: eval_policy missing required key '{key}'.")
    # STOP-B-7.2: schema parity with launch_baseline.load_gate_eval_policy —
    # reject bool, non-empty lambda_probe, validate item types.
    if not isinstance(policy["lambda_probe"], dict) or not policy["lambda_probe"]:
        raise ValueError(f"{path}: eval_policy.lambda_probe must be a non-empty dict.")
    for k, v in policy["lambda_probe"].items():
        if not isinstance(k, str):
            raise ValueError(f"{path}: lambda_probe key {k!r} must be a string.")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ValueError(f"{path}: lambda_probe[{k!r}] must be a finite real number,"
                             f" got {v!r} of type {type(v).__name__}.")
    if not isinstance(policy["perturbations"], list) or not policy["perturbations"]:
        raise ValueError(f"{path}: eval_policy.perturbations must be a non-empty list.")
    for p in policy["perturbations"]:
        if not isinstance(p, str):
            raise ValueError(f"{path}: perturbation entries must be strings, got {p!r}.")
    if (isinstance(policy["beta_robust"], bool)
            or not isinstance(policy["beta_robust"], (int, float))
            or not math.isfinite(float(policy["beta_robust"]))):
        raise ValueError(f"{path}: eval_policy.beta_robust must be a finite real number.")
    if not isinstance(policy["reward_axes"], list) or not policy["reward_axes"]:
        raise ValueError(f"{path}: eval_policy.reward_axes must be a non-empty list.")
    for ax in policy["reward_axes"]:
        if not isinstance(ax, str):
            raise ValueError(f"{path}: reward_axes entries must be strings, got {ax!r}.")
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    policy_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return policy, policy_hash


def _read_results_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    """torch-free JSONL reader. Returns (entries, errors). STOP-B-7.1 Q2:
    accepts UTF-8 BOM (utf-8-sig), catches per-line JSONDecodeError cleanly
    instead of crashing the whole gate path, and returns the line number
    of any malformed entry so the operator can repair the file."""
    out: list[dict] = []
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            for lineno, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"  - {path}:{lineno}: invalid JSON ({e.msg}).")
                    continue
                if not isinstance(entry, dict):
                    errors.append(f"  - {path}:{lineno}: top-level value is not a dict"
                                  f" ({type(entry).__name__}).")
                    continue
                out.append(entry)
    except OSError as e:
        errors.append(f"  - {path}: I/O error ({type(e).__name__}: {e}).")
    return out, errors


def _verify_sidecar(rung_dir: Path, expected_policy: dict,
                     expected_hash: str) -> list[str]:
    """Return a list of human-readable errors. Empty list = sidecar verified.

    STOP-B-7.1 Q3: field-by-field check, not just the claimed `hash` field.
    Compares lambda_probe / perturbations / beta_robust / reward_axes against
    live policy. The hash must also match; trusting the sidecar's claimed
    `hash` alone would let a malicious or buggy sidecar lie about its contents.
    """
    sidecar = rung_dir / "gate_eval_policy.json"
    if not sidecar.exists():
        return [f"  - {sidecar} not found. Re-run the rung under STOP-B-7"
                f" (production mode) so gate_r_lcb + sidecar are written."]
    try:
        prov = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return [f"  - {sidecar} could not be parsed ({type(e).__name__}: {e})."]
    if not isinstance(prov, dict):
        return [f"  - {sidecar}: top-level is not a JSON object."]

    errs: list[str] = []
    expected_name = expected_policy["name"]
    expected_version = expected_policy["version"]
    if prov.get("name") != expected_name:
        errs.append(f"  - {sidecar}: name={prov.get('name')!r}, expected {expected_name!r}.")
    if prov.get("version") != expected_version:
        errs.append(f"  - {sidecar}: version={prov.get('version')!r},"
                    f" expected {expected_version!r}.")
    # Hash must match.
    if prov.get("hash") != expected_hash:
        errs.append(f"  - {sidecar}: hash mismatch."
                    f" sidecar={prov.get('hash')!r}, live={expected_hash!r}."
                    " Re-run the rung after editing gate_v1.yaml — or"
                    " bump the policy version and rerun all gate-critical rungs.")
    # STOP-B-7.1 Q3: field-by-field check.
    if prov.get("lambda_probe") != dict(expected_policy["lambda_probe"]):
        errs.append(f"  - {sidecar}: lambda_probe content differs from live"
                    f" gate_v1.yaml. sidecar={prov.get('lambda_probe')!r}.")
    if list(prov.get("perturbations") or []) != list(expected_policy["perturbations"]):
        errs.append(f"  - {sidecar}: perturbations content differs from live"
                    f" gate_v1.yaml. sidecar={prov.get('perturbations')!r}.")
    if prov.get("beta_robust") != float(expected_policy["beta_robust"]):
        errs.append(f"  - {sidecar}: beta_robust={prov.get('beta_robust')!r},"
                    f" expected {float(expected_policy['beta_robust'])!r}.")
    if list(prov.get("reward_axes") or []) != list(expected_policy["reward_axes"]):
        errs.append(f"  - {sidecar}: reward_axes content differs from live"
                    f" gate_v1.yaml. sidecar={prov.get('reward_axes')!r}.")
    return errs


def _peek_rung_mode(runs_dir: Path, rung: str, split: str) -> str | None:
    """STOP-B-8: read `extras.r9_mode` (or generic `extras.mode`) off the first result
    line of `runs/<rung>/<split>/results.jsonl`. Returns None if the file/key is missing.
    Used to surface R9-lite vs R9-full in the gate decision JSON."""
    for candidate in (runs_dir / rung / split / "results.jsonl",
                       runs_dir / rung / "results.jsonl"):
        if candidate.exists():
            try:
                with candidate.open("r", encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        extras = entry.get("extras") or {}
                        mode = extras.get("r9_mode") or extras.get("mode")
                        return mode
            except Exception:  # noqa: BLE001
                return None
    return None


def _load_gate_r_lcb(runs_dir: Path, rung: str, split: str,
                       expected_policy: dict, expected_hash: str
                       ) -> tuple[list[float], list[str]]:
    """Return (gate_r_lcb_values, errors). STOP-B-7.1 Q2/Q3: robust to NaN/inf
    values, malformed JSONL lines, non-dict metrics/extras, and BOM-encoded
    files; sidecar verification is field-by-field, not just hash."""
    rung_dir = runs_dir / rung / split
    path = rung_dir / "results.jsonl"
    if not path.exists():
        # Backward-compat fallback for legacy results without a split subdir.
        rung_dir = runs_dir / rung
        path = rung_dir / "results.jsonl"
    if not path.exists():
        return [], [f"  - {rung}: missing results file at {path}"]

    sidecar_errs = _verify_sidecar(rung_dir, expected_policy, expected_hash)
    if sidecar_errs:
        return [], [f"  - {rung}: gate-policy sidecar verification FAILED.",
                    *sidecar_errs]

    raw, read_errors = _read_results_jsonl(path)
    values: list[float] = []
    errors: list[str] = list(read_errors)
    for entry in raw:
        prompt_id = entry.get("prompt_id", "<unknown>")
        metrics = entry.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"  - {rung}: result for {prompt_id} has no metrics dict"
                          f" (got {type(metrics).__name__}).")
            continue
        if "gate_r_lcb" not in metrics:
            errors.append(
                f"  - {rung}: result for {prompt_id} lacks `gate_r_lcb` metric."
                " Re-run the rung under STOP-B-7 production mode."
            )
            continue
        # STOP-B-7.1/7.2 Q2: reject NaN / +inf / -inf / non-numeric / bool.
        # `isinstance(True, int) is True` in Python — bool sneaks through a
        # naive `(int, float)` check, so we reject it explicitly.
        raw_val = metrics["gate_r_lcb"]
        if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)):
            errors.append(f"  - {rung}: result for {prompt_id} has"
                          f" gate_r_lcb={raw_val!r} of type"
                          f" {type(raw_val).__name__} (expected real number).")
            continue
        val = float(raw_val)
        if not math.isfinite(val):
            errors.append(f"  - {rung}: result for {prompt_id} has non-finite"
                          f" gate_r_lcb={val!r}; refuse to feed gate.")
            continue
        # Sanity check: per-result extras should also carry the gate policy
        # (defensive; sidecar already verified field-by-field at rung level).
        extras = entry.get("extras")
        if not isinstance(extras, dict):
            errors.append(f"  - {rung}: result for {prompt_id} extras is not a dict.")
            continue
        per_res_policy = extras.get("gate_eval_policy")
        if not isinstance(per_res_policy, dict):
            errors.append(f"  - {rung}: result for {prompt_id} lacks gate_eval_policy"
                          " block in extras.")
            continue
        if per_res_policy.get("hash") != expected_hash:
            errors.append(
                f"  - {rung}: result for {prompt_id} carries"
                f" gate_eval_policy.hash={per_res_policy.get('hash')!r},"
                f" expected {expected_hash!r}."
            )
            continue
        values.append(val)
    if not values and not errors:
        errors.append(f"  - {rung}: empty results")
    return values, errors


# =============================================================================
# R4 HEDGE 2026-05-19: paired test + bootstrap CI supplementary analysis.
# Pre-registered in orbit-research/HEADROOM_GATE_PREREG.md. These helpers add
# higher-power statistical views on top of the main mean-comparison logic in
# `mprm.audit.headroom_gate.headroom_gate()` (which stays the binding rule);
# they are *supplementary* and do not change the gate PASS/FAIL decision.
# Pure stdlib (math + statistics + random) to keep the script torch-free.
# =============================================================================


def _normal_cdf(z: float) -> float:
    """Standard normal CDF via the error function (stdlib only)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _two_sided_p_from_t(t_stat: float, df: int) -> float:
    """Approximate two-sided p-value for a t-statistic.

    For df ≥ 100 (our regime: 256 paired prompts), the Student t distribution is
    indistinguishable from normal at any practical α — we use the normal CDF.
    For smaller df, falls back to scipy if available, else conservative normal.
    """
    if not math.isfinite(t_stat):
        return 0.0
    if df >= 100:
        return 2.0 * (1.0 - _normal_cdf(abs(t_stat)))
    try:
        from scipy.stats import t as t_dist  # type: ignore
        return float(2.0 * (1.0 - t_dist.cdf(abs(t_stat), df)))
    except ImportError:
        return 2.0 * (1.0 - _normal_cdf(abs(t_stat)))


def _paired_diff_test(a_by_prompt: dict, b_by_prompt: dict) -> dict:
    """Paired t-test on Δ = a - b for each prompt_id common to both rungs.

    Pairing by prompt removes between-prompt variance (which dominates SD of
    raw rung means at n=3 seeds), raising statistical power 5-10× vs treating
    seed-averaged rung means as independent samples.
    """
    common = sorted(set(a_by_prompt) & set(b_by_prompt))
    if len(common) < 2:
        return {"error": f"too few common prompts (n={len(common)})",
                "n_common": len(common)}
    deltas = [a_by_prompt[k] - b_by_prompt[k] for k in common]
    mean_d = statistics.fmean(deltas)
    sd_d = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    n = len(deltas)
    se = sd_d / math.sqrt(n) if sd_d > 0 else 0.0
    if se > 0:
        t_stat = mean_d / se
    elif mean_d == 0:
        t_stat = 0.0
    else:
        t_stat = float("inf")
    df = n - 1
    p = _two_sided_p_from_t(t_stat, df)
    return {"n_common": n, "mean_diff": mean_d, "sd_diff": sd_d,
            "se_diff": se, "t_stat": t_stat, "df": df, "p_value": p}


def _bootstrap_ci(values, *, n_iter: int = 1000, alpha: float = 0.05,
                   seed: int = 42) -> dict:
    """Percentile bootstrap 95% CI for the mean. Fixed seed → reproducible."""
    vals = list(values)
    if not vals:
        return {"error": "empty"}
    if len(vals) == 1:
        v = float(vals[0])
        return {"mean": v, "ci_low": v, "ci_high": v, "n": 1, "n_iter": n_iter}
    rng = random.Random(seed)
    n = len(vals)
    means = []
    for _ in range(n_iter):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    lo_idx = int(alpha / 2 * n_iter)
    hi_idx = min(int((1 - alpha / 2) * n_iter), n_iter - 1)
    return {"mean": statistics.fmean(vals),
            "sd": statistics.stdev(vals) if n > 1 else 0.0,
            "ci_low": means[lo_idx],
            "ci_high": means[hi_idx],
            "n": n, "n_iter": n_iter}


def _load_gate_r_lcb_per_prompt(runs_dir: Path, rung: str, split: str,
                                  expected_policy: dict, expected_hash: str
                                  ) -> tuple[dict, list[str]]:
    """Variant of `_load_gate_r_lcb` that returns {prompt_id: avg_gate_r_lcb}.

    Averages across all seeds present for each prompt. Used only by the R4
    paired-analysis supplementary; main decision logic still consumes the
    flat list. Lenient on a per-entry basis (silently drops malformed rows
    so a few bad lines don't kill the paired analysis); rung-level sidecar
    verification is still enforced.
    """
    rung_dir = runs_dir / rung / split
    path = rung_dir / "results.jsonl"
    if not path.exists():
        rung_dir = runs_dir / rung
        path = rung_dir / "results.jsonl"
    if not path.exists():
        return {}, [f"  - {rung}: missing results file at {path}"]
    sidecar_errs = _verify_sidecar(rung_dir, expected_policy, expected_hash)
    if sidecar_errs:
        return {}, [f"  - {rung}: sidecar verification FAILED.", *sidecar_errs]
    raw, _read_errors = _read_results_jsonl(path)
    per_prompt: dict = {}
    for entry in raw:
        prompt_id = entry.get("prompt_id")
        if not isinstance(prompt_id, str):
            continue
        metrics = entry.get("metrics")
        if not isinstance(metrics, dict):
            continue
        raw_val = metrics.get("gate_r_lcb")
        if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)):
            continue
        val = float(raw_val)
        if not math.isfinite(val):
            continue
        per_prompt.setdefault(prompt_id, []).append(val)
    avg = {pid: statistics.fmean(vals) for pid, vals in per_prompt.items()}
    return avg, []


def _benjamini_hochberg_q(tests: dict) -> None:
    """Mutates `tests` in-place: adds `bh_q_value` to each entry with a
    finite p_value. BH FDR correction for the family of paired tests."""
    p_pairs = [(k, v["p_value"]) for k, v in tests.items()
                 if isinstance(v.get("p_value"), (int, float))
                 and math.isfinite(float(v["p_value"]))]
    if not p_pairs:
        return
    p_pairs.sort(key=lambda kv: kv[1])
    m = len(p_pairs)
    # Walk in ascending p-order; q_i = p_i * m / rank_i, monotone non-increasing
    # when traversed in DESC order (standard BH trick).
    qs = []
    prev_q = 1.0
    for rank in range(m, 0, -1):
        k, p = p_pairs[rank - 1]
        q = p * m / rank
        q = min(q, prev_q)
        prev_q = q
        qs.append((k, q))
    for k, q in qs:
        tests[k]["bh_q_value"] = min(max(q, 0.0), 1.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="held_out")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--human-spot-check", choices=["confirm", "disconfirm", "pending"],
                        default="pending")
    parser.add_argument("--out", default="orbit-research/HEADROOM_GATE_DECISION.json")
    parser.add_argument("--policy-path", default=str(GATE_EVAL_POLICY_PATH),
                        help="Path to gate_v1.yaml. Default: configs/eval/gate_v1.yaml.")
    args = parser.parse_args()

    policy_path = Path(args.policy_path)
    if not policy_path.exists():
        print(f"Headroom gate CANNOT BE EVALUATED — gate-policy file missing at {policy_path}.")
        print("  Fix: ensure configs/eval/gate_v1.yaml is checked in and present at the path.")
        return 2
    expected_policy, expected_hash = _load_gate_eval_policy(policy_path)
    print(f"STOP-B-7 gate policy: {expected_policy['name']}"
          f" v{expected_policy['version']} (hash {expected_hash[:12]}…)")

    runs = Path(args.runs_dir)
    all_errors: list[str] = []
    per_rung: dict[str, list[float]] = {}

    for rung in GATE_CRITICAL:
        values, errors = _load_gate_r_lcb(runs, rung, args.split, expected_policy,
                                            expected_hash)
        per_rung[rung] = values
        if errors:
            all_errors.extend(errors)

    if all_errors:
        print("Headroom gate CANNOT BE EVALUATED — the following inputs are invalid:")
        for e in all_errors:
            print(e)
        print("\nFix: run all five gate-critical baselines on the requested split with"
              "\nthe STOP-B-7 uniform gate_v1 evaluator (production mode auto-computes"
              "\n`gate_r_lcb` for gate-critical rungs), then re-run this script.")
        return 2

    spot = None if args.human_spot_check == "pending" else (args.human_spot_check == "confirm")

    # Lazy import (see top-of-file note) — all refusal checks above have passed by now.
    try:
        from mprm.audit.headroom_gate import headroom_gate
    except ImportError as e:
        print(f"Headroom gate CANNOT COMPUTE the decision — mprm.audit.headroom_gate"
              f" is not importable ({type(e).__name__}: {e}).")
        print("  Fix: `pip install -e .` from the repo root, or run with"
              " PYTHONPATH=src.")
        return 2

    decision = headroom_gate(
        base_lcb=per_rung["r0_base"],
        bon8_lcb=per_rung["r2_bon"],
        bon_plus_cfg_lcb=per_rung["r4_bon_cfg"],
        cfg_sweep_lcb=per_rung["r1_cfg_sweep"],
        s7_lcb=per_rung["r9_s7_sampler_control"],
        human_spot_check=spot,
    )

    # STOP-B-8: surface R9 mode (lite vs full) on the decision so the M1a auditor
    # knows whether the s7-explain check used the weaker lite controller. Reads
    # the first R9 result's extras.r9_mode; defaults to "unknown" if absent.
    r9_mode = _peek_rung_mode(runs, "r9_s7_sampler_control", args.split)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(decision)
    payload["split"] = args.split
    payload["n_inputs"] = {k: len(v) for k, v in per_rung.items()}
    payload["gate_eval_policy"] = {
        "name": expected_policy["name"],
        "version": expected_policy["version"],
        "hash": expected_hash,
    }
    payload["r9_mode"] = r9_mode
    if r9_mode and r9_mode != "r9_full_4axis":
        payload.setdefault("notes", []).append(
            f"R9 ran in mode={r9_mode!r} (STOP-B-8 r9-lite); the s7-explain check is a"
            " WEAKER falsifier than the original 4-axis design — see"
            " orbit-research/STOP_B8_BLOCKER_REPORT.md."
        )

    # =====================================================================
    # R4 HEDGE 2026-05-19: paired test + bootstrap CI supplementary analysis.
    # Pre-registered in orbit-research/HEADROOM_GATE_PREREG.md.
    # Does NOT change the binding decision above; provides higher-power
    # statistical views for the paper's significance table.
    # =====================================================================
    per_rung_per_prompt: dict = {}
    for rung in GATE_CRITICAL:
        pp, _supp_errs = _load_gate_r_lcb_per_prompt(
            runs, rung, args.split, expected_policy, expected_hash
        )
        per_rung_per_prompt[rung] = pp

    PAIR_PROBES = [
        ("r1_cfg_sweep",     "r0_base",                   "cfg-explain check (CFG sweep vs baseline)"),
        ("r2_bon",           "r0_base",                   "BoN-8 ceiling vs baseline"),
        ("r4_bon_cfg",       "r0_base",                   "BoN+CFG composite vs baseline"),
        ("r1_cfg_sweep",     "r9_s7_sampler_control",     "CFG vs sampler-control (real CFG signal)"),
        ("r2_bon",           "r9_s7_sampler_control",     "BoN vs sampler-control"),
    ]
    paired_tests: dict = {}
    for a, b, label in PAIR_PROBES:
        if not per_rung_per_prompt.get(a) or not per_rung_per_prompt.get(b):
            paired_tests[f"{a}_minus_{b}"] = {"label": label, "skipped":
                "missing per-prompt data for one of the rungs"}
            continue
        paired_tests[f"{a}_minus_{b}"] = {
            "label": label,
            **_paired_diff_test(per_rung_per_prompt[a], per_rung_per_prompt[b]),
        }
    _benjamini_hochberg_q(paired_tests)

    bootstrap_per_rung: dict = {
        rung: _bootstrap_ci(vals) for rung, vals in per_rung.items()
    }

    payload["supplementary"] = {
        "paired_tests_by_prompt": paired_tests,
        "bootstrap_95_ci_per_rung": bootstrap_per_rung,
        "minimum_effect_of_interest_gate_r_lcb": 0.05,
        "prereg_path": "orbit-research/HEADROOM_GATE_PREREG.md",
        "note": (
            "Supplementary statistics, pre-registered 2026-05-19. Paired t-test"
            " pairs each prompt across rungs (seeds averaged). BH q-values"
            " correct for multiple comparison. Bootstrap percentile CIs"
            " (n_iter=1000) on each rung's gate_r_lcb mean. This block does"
            " NOT change the binding `pass_gate` above."
        ),
    }
    # ===== end R4 HEDGE supplementary =====

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    print(f"\nWrote decision to {out_path}")
    return 0 if decision.pass_gate else 1


if __name__ == "__main__":
    sys.exit(main())
