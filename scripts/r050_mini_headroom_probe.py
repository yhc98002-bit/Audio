"""R050 — informal mini-headroom probe (STOP-B-4 pre-M1a pause point).

32 stratified ACE-Step prompts × {Base seed=42, BoN-8 with R_lcb under reduced
Π = {identity, crop}}. Reports per-prompt Δ = R_lcb(BoN-8) − R_lcb(Base) and exits 1
(pause-and-report) if the trend is not positive. Non-paper-bearing — M1a's 256-prompt
audit is the authoritative gate.

STOP-B-5 fixes (per Codex STOP-B-4 review):
- Base probe scoring now passes `base_reference=base_res.waveform` to itself, so
  `hf_artifact_score` is the same ratio metric for Base and BoN candidates.
- Production mode now asserts `len(deltas) == args.n_prompts` so the 16/32 rule is
  not silently relaxed if fewer prompts loaded; pass `--allow-partial` to override
  (debug only).
- New `--mock-deltas N` flag generates synthetic deltas and exercises the pass/fail +
  assertion logic *without* importing torch / mprm.inference / mprm.rewards. Used by
  the STOP-B-5 test harness to verify gating without a GPU env.

STOP-B-6 fixes:
- `_stratified_subset` is now true deterministic round-robin across strata; the
  prior implementation iterated each stratum to exhaustion and could draw all
  32 prompts from one stratum.
- In production mode, `--allow-template-prompts` alone is no longer sufficient
  to proceed against template stubs; the PI must also set
  `R050_TEMPLATE_PROMPTS_PI_ACK=1` for an explicit, audit-traceable bypass.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path


def _stratified_subset(prompts, n: int = 32):
    """Pick `n` prompts via deterministic round-robin across primary strata keys.

    STOP-B-6 fix: the prior implementation iterated `sorted(by_stratum)` and
    drained each stratum fully before moving to the next, so a single stratum
    with >= n prompts could fill the entire subset. True round-robin (one
    prompt per stratum per pass) keeps the subset balanced across strata while
    still being fully deterministic — strata are visited in `sorted(keys)`
    order and prompts within a stratum are taken in input order.
    """
    by_stratum: dict[str, list] = {}
    for p in prompts:
        key = "|".join(p.strata.get(k, "?") for k in ("genre", "vocal_vs_instrumental"))
        by_stratum.setdefault(key, []).append(p)
    if not by_stratum:
        return []
    sorted_keys = sorted(by_stratum.keys())
    cursors = {k: 0 for k in sorted_keys}
    out: list = []
    while len(out) < n:
        progressed = False
        for k in sorted_keys:
            idx = cursors[k]
            if idx < len(by_stratum[k]):
                out.append(by_stratum[k][idx])
                cursors[k] = idx + 1
                progressed = True
                if len(out) == n:
                    return out
        if not progressed:
            break
    return out


def _evaluate_deltas(deltas: list[float], n_prompts_target: int, mode: str,
                      allow_partial: bool, summary_path: Path | None) -> int:
    """Apply the STOP-B-5 production assertion and the pass/fail rule.

    Returns the script exit code (0 pass / 1 pause-and-report / 2 block).
    """
    if not deltas:
        print("R050 FAIL: no deltas computed.")
        return 1

    if mode == "production" and not allow_partial:
        if len(deltas) != n_prompts_target:
            print(f"R050 BLOCK (STOP-B-5): production mode requires"
                  f" len(deltas) == {n_prompts_target}, got {len(deltas)}.")
            print("  Either rerun on the full prompt set, or pass --allow-partial (debug only).")
            return 2

    median_d = statistics.median(deltas)
    mean_d = statistics.mean(deltas)
    n_pos = sum(1 for d in deltas if d > 0)
    n_neg = sum(1 for d in deltas if d <= 0)
    # STOP-B-5: with n_prompts == 32 the threshold len(deltas)/2 = 16.0 exactly,
    # matching the user contract "≥ 16 of 32 positive". For n != 32 in
    # --allow-partial mode the rule is "≥ half of n positive".
    positive_trend = median_d > 0 and n_pos >= len(deltas) / 2

    summary_lines = [
        "# R050 mini-headroom probe summary",
        "",
        f"- Prompts evaluated: {len(deltas)} (target {n_prompts_target})",
        f"- Mode: {mode}{'  [--allow-partial set]' if allow_partial else ''}",
        f"- median Δ: {median_d:+.4f}",
        f"- mean Δ:   {mean_d:+.4f}",
        f"- count(Δ > 0): {n_pos} / {len(deltas)}",
        f"- count(Δ ≤ 0): {n_neg} / {len(deltas)}",
        f"- pass rule: median Δ > 0 AND n_pos >= {len(deltas) / 2:.1f}",
        f"- positive trend: **{positive_trend}**",
        "",
        "Decision (per `EXPERIMENT_PLAN_EXEC.md` Decision Tree M0.5 row):",
        ("  proceed to M1a" if positive_trend else
            "  **PAUSE and report to PI.** Median Δ ≤ 0 or < 50 % of prompts show positive Δ."),
        "" if positive_trend else
            "  PI options: (a) proceed to M1a anyway (the probe is informal — M1a's 256-prompt"
            " audit is the authoritative gate); (b) recalibrate β_robust / λ_probe / Π and"
            " rerun R050; (c) abort and pivot to saturation paper.",
    ]
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        print(f"\nR050 summary written to {summary_path}")

    if positive_trend:
        print("R050 PASS (informal positive trend).")
        return 0
    print("R050 PAUSE-AND-REPORT: trend is not positive. See summary; PI must acknowledge.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", default="configs/prompts/dev.jsonl")
    parser.add_argument("--n-prompts", type=int, default=32)
    parser.add_argument("--bon-n", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="runs/r050/r050_results.jsonl")
    parser.add_argument("--summary", default="orbit-research/R050_SUMMARY.md")
    parser.add_argument("--mode", choices=["dev", "production"], default="dev")
    parser.add_argument("--allow-template-prompts", action="store_true",
                        help="Run even if MISSING_REAL_PROMPTS.flag exists (dev only).")
    parser.add_argument("--allow-partial", action="store_true",
                        help="DEBUG: skip the production-mode len(deltas)==n_prompts assertion.")
    parser.add_argument("--mock-deltas", type=int, default=None,
                        help=("TEST HARNESS: generate N synthetic positive deltas and exercise"
                              " the pass/fail + production assertion logic. Skips all"
                              " torch/model/reward imports."))
    parser.add_argument("--mock-delta-value", type=float, default=0.1,
                        help="TEST HARNESS: value to use for each mock delta (default 0.1).")
    # STOP-B-8 sharded mode (2026-05-17): if both --shard-index and --shard-total
    # are set, the script processes only `subset[shard_index::shard_total]` (round-
    # robin slice of the stratified 32-prompt subset), writes per-shard JSONL to
    # `<out>.shard_{i}_of_{n}.jsonl`, and exits 0 on success WITHOUT computing the
    # pass rule (the orchestrator `r050_run_sharded.py` aggregates and applies it).
    parser.add_argument("--shard-index", type=int, default=None,
                        help="0-indexed shard ID; requires --shard-total. Sharded mode "
                             "skips _evaluate_deltas; orchestrator aggregates.")
    parser.add_argument("--shard-total", type=int, default=None,
                        help="Total number of shards (e.g. 8 for 8-GPU sharding).")
    # STOP-B-8: detect whether --summary was explicitly passed (used below to keep
    # mock-test runs from clobbering the production R050_SUMMARY.md file).
    DEFAULT_SUMMARY = "orbit-research/R050_SUMMARY.md"
    parser.set_defaults(summary=DEFAULT_SUMMARY)
    args = parser.parse_args()
    summary_explicit = (args.summary != DEFAULT_SUMMARY) if args.summary else False
    sharded = args.shard_index is not None and args.shard_total is not None
    if (args.shard_index is None) ^ (args.shard_total is None):
        print("R050 BLOCK: --shard-index and --shard-total must be set together.")
        return 2
    if sharded and not (0 <= args.shard_index < args.shard_total):
        print(f"R050 BLOCK: --shard-index {args.shard_index} out of range"
              f" [0, {args.shard_total}).")
        return 2

    summary_path = Path(args.summary) if args.summary else None

    # STOP-B-5 test-harness path: synthetic deltas, no torch / model / reward needed.
    if args.mock_deltas is not None:
        # STOP-B-8: prevent silent overwrite of the production R050_SUMMARY.md by
        # mock-test invocations. If --summary was not explicitly given, write to a
        # /tmp path instead so the canonical production summary stays honest.
        if not summary_explicit:
            import tempfile as _tempfile
            summary_path = Path(_tempfile.gettempdir()) / "r050_mock_summary.md"
            print(f"R050 MOCK: --summary not explicit; redirecting mock summary to"
                  f" {summary_path} (production summary preserved).")
        deltas = [float(args.mock_delta_value)] * args.mock_deltas
        print(f"R050 MOCK: generated {len(deltas)} synthetic deltas of value"
              f" {args.mock_delta_value:+.4f}. Skipping all torch/model/reward imports.")
        return _evaluate_deltas(deltas, args.n_prompts, args.mode,
                                  args.allow_partial, summary_path)

    # STOP-B-6 fix #7: template-prompts gate runs BEFORE any mprm / torch import,
    # so the production BLOCK fires even in CPU sandboxes (and in production
    # without GPU deps installed). This matches the launch_baseline.py M0.5 gate
    # philosophy — refuse before doing any heavy work.
    prompts_path = Path(args.prompts)
    flag = prompts_path.parent / "MISSING_REAL_PROMPTS.flag"
    if flag.exists():
        if args.mode == "production":
            if (args.allow_template_prompts
                    and os.environ.get("R050_TEMPLATE_PROMPTS_PI_ACK") == "1"):
                print(f"R050 WARN (production, STOP-B-6): proceeding with template stubs"
                      f" at {prompts_path}. Both --allow-template-prompts and"
                      " R050_TEMPLATE_PROMPTS_PI_ACK=1 are set — explicit PI override.")
            else:
                print(f"R050 BLOCK: prompts at {prompts_path} are template stubs (flag {flag}).")
                print("  Populate real prompts before running R050 in production mode.")
                print("  STOP-B-6: --allow-template-prompts alone is NOT sufficient in")
                print("  production. For an explicit PI override, set BOTH:")
                print("    --allow-template-prompts   (CLI flag)")
                print("    R050_TEMPLATE_PROMPTS_PI_ACK=1   (env var)")
                return 2
        elif not args.allow_template_prompts:
            print(f"R050 BLOCK (dev): prompts at {prompts_path} are template stubs (flag"
                  f" {flag}). Pass --allow-template-prompts to proceed with stubs in dev.")
            return 2

    # Normal path: real model + reward harness required.
    from mprm.common.seeding import seed_everything  # noqa: E402  (delayed for --mock-deltas)
    from mprm.data.prompts import load_prompts  # noqa: E402
    seed_everything(args.seed)

    prompts = load_prompts(prompts_path)
    subset = _stratified_subset(prompts, n=args.n_prompts)
    print(f"R050: loaded {len(subset)} stratified prompts (target {args.n_prompts}).")

    # STOP-B-8 sharded mode: round-robin slice + per-shard output path.
    if sharded:
        full_subset_n = len(subset)
        subset = subset[args.shard_index::args.shard_total]
        out_path_str = args.out
        # Insert ".shard_{i}_of_{n}" before the .jsonl extension
        if out_path_str.endswith(".jsonl"):
            args.out = out_path_str.replace(
                ".jsonl", f".shard_{args.shard_index}_of_{args.shard_total}.jsonl"
            )
        else:
            args.out = f"{out_path_str}.shard_{args.shard_index}_of_{args.shard_total}"
        summary_path = None  # orchestrator writes the canonical summary
        print(f"R050 SHARD {args.shard_index}/{args.shard_total}: processing"
              f" {len(subset)} of {full_subset_n} prompts; out={args.out}")

    try:
        from mprm.inference.ace_step import AceStepModel
        from mprm.rewards.audiobox import AudioboxReward
        from mprm.rewards.clap import ClapReward
        from mprm.rewards.perturbations import perturbation_set
        from mprm.rewards.probes import anti_hacking_probes, probe_floors
        from mprm.rewards.robust_lcb import robust_lcb
    except ImportError as e:
        print(f"R050 ERROR: cannot import dependencies ({e}). Run `pip install -e .` first.")
        return 2

    model = AceStepModel(checkpoint="ace-step/ACE-Step-1.5")
    reward_models = [AudioboxReward(target_axis="PQ"), ClapReward()]
    perts = perturbation_set(["identity", "crop"])
    floors = probe_floors()
    lambda_probe = {"silence_fraction": 1.0, "autocorr_repetition": 1.0,
                     "off_prompt_distance": 1.0, "hf_artifact_score": 0.5}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    deltas: list[float] = []

    for p in subset:
        try:
            base_res = model.sample(p, seed=args.seed)
            # STOP-B-5 fix #3: pass base_reference=base_res.waveform to Base too, so
            # hf_artifact_score is a ratio-vs-Base metric for both arms. Without this,
            # Base gets absolute HF energy while BoN candidates get ratio — asymmetric
            # probe definitions.
            base_probe = anti_hacking_probes(base_res.waveform, base_res.sample_rate, p,
                                              base_reference=base_res.waveform,
                                              clap=reward_models[1])
            base_lcb = robust_lcb(base_res.waveform, base_res.sample_rate, p,
                                    reward_models=reward_models,
                                    perturbations=perts,
                                    probe_scores=base_probe,
                                    lambda_probe=lambda_probe,
                                    probe_floors=floors,
                                    beta_robust=0.5)

            bon_lcb_values: list[float] = []
            for i in range(args.bon_n):
                cand = model.sample(p, seed=args.seed + 100 + i)
                cand_probe = anti_hacking_probes(cand.waveform, cand.sample_rate, p,
                                                   base_reference=base_res.waveform,
                                                   clap=reward_models[1])
                cand_lcb = robust_lcb(cand.waveform, cand.sample_rate, p,
                                       reward_models=reward_models,
                                       perturbations=perts,
                                       probe_scores=cand_probe,
                                       lambda_probe=lambda_probe,
                                       probe_floors=floors,
                                       beta_robust=0.5)
                bon_lcb_values.append(cand_lcb.value)
            bon_best = max(bon_lcb_values)
            delta = bon_best - base_lcb.value
            deltas.append(delta)
            row = {
                "prompt_id": p.prompt_id,
                "strata": p.strata,
                "base_lcb": base_lcb.value,
                "bon_best_lcb": bon_best,
                "delta": delta,
            }
            # STOP-B-8 sharded mode: stamp shard_index + physical gpu_id (from
            # CUDA_VISIBLE_DEVICES, which the orchestrator sets per shard) for
            # provenance / forensics.
            if sharded:
                row["shard_index"] = args.shard_index
                row["shard_total"] = args.shard_total
                row["gpu_id"] = os.environ.get("CUDA_VISIBLE_DEVICES", "")
            results.append(row)
            print(f"  {p.prompt_id}: base={base_lcb.value:+.4f}  bon8={bon_best:+.4f}  Δ={delta:+.4f}")
        except Exception as e:  # noqa: BLE001
            print(f"  {p.prompt_id}: FAIL ({type(e).__name__}: {e})")
            return 1

    # Re-resolve out_path after the shard rename above
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # STOP-B-8 sharded mode: skip the global pass-rule evaluation. The orchestrator
    # `scripts/r050_run_sharded.py` concatenates all per-shard JSONLs, sorts by
    # original subset index, and applies `_evaluate_deltas` on the aggregated 32
    # deltas. Per-shard `len(deltas) == n_prompts` would be meaningless (each shard
    # only sees n_prompts/n_shards prompts).
    if sharded:
        print(f"R050 SHARD {args.shard_index}/{args.shard_total}: wrote {len(results)}"
              f" results to {out_path}. Orchestrator will aggregate + apply pass rule.")
        return 0

    return _evaluate_deltas(deltas, args.n_prompts, args.mode,
                              args.allow_partial, summary_path)


if __name__ == "__main__":
    sys.exit(main())
