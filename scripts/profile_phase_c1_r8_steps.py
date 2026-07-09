"""Analyze R8a/R8b Phase C1 step timing from existing train logs."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_steps(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("event") == "optimizer_step":
                rows.append(row)
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed = [float(r["elapsed_seconds"]) for r in rows if r.get("elapsed_seconds") is not None]
    if not elapsed:
        return {"n_steps": 0}
    sorted_elapsed = sorted(elapsed)
    p95_idx = min(len(sorted_elapsed) - 1, int(0.95 * (len(sorted_elapsed) - 1)))
    update = [r.get("update_metrics", {}) for r in rows]
    return {
        "n_steps": len(elapsed),
        "last_step": max(int(r["step"]) for r in rows if r.get("step") is not None),
        "mean_step_seconds": statistics.mean(elapsed),
        "median_step_seconds": statistics.median(elapsed),
        "p95_step_seconds": sorted_elapsed[p95_idx],
        "min_step_seconds": min(elapsed),
        "max_step_seconds": max(elapsed),
        "total_gpu_hours": sum(float(r.get("gpu_hours_consumed", 0.0)) for r in rows),
        "mean_reward_std": statistics.mean(float(r.get("reward_std", 0.0)) for r in rows),
        "mean_grad_norm": statistics.mean(
            float(u.get("grad_norm", 0.0)) for u in update if u.get("grad_norm") is not None
        ),
        "max_approx_kl_ref": max(
            float(u.get("approx_kl_ref", 0.0)) for u in update if u.get("approx_kl_ref") is not None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", default="runs/phase_c1_firstwave_20260524_researcher_go_01")
    parser.add_argument("--out", default="orbit-research/PHASE_C1_R8A_R8B_PROFILING.md")
    args = parser.parse_args()

    root = Path(args.run_root)
    data = {
        method: _summary(_read_steps(root / method / "train_log.jsonl"))
        for method in ("r8a", "r8b", "m_fixedwin", "m_section")
    }
    r8a = data["r8a"]
    r8b = data["r8b"]
    lines = [
        "# Phase C1 R8a/R8b Step-Time Profiling",
        "",
        f"Generated UTC: `{_now_utc()}`",
        "",
        "## Scope",
        "",
        "Read-only analysis of the live C1 train logs. No training process, config, reward definition, sigma policy, prompt split, or credit-unit definition was modified.",
        "",
        "## End-to-End Step Timing",
        "",
        "| method | n_steps | last_step | mean_s | median_s | p95_s | total_gpu_h | mean_reward_std | mean_grad_norm | max_kl_ref |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method, row in data.items():
        if not row.get("n_steps"):
            continue
        lines.append(
            f"| {method} | {row['n_steps']} | {row['last_step']} | "
            f"{row['mean_step_seconds']:.2f} | {row['median_step_seconds']:.2f} | "
            f"{row['p95_step_seconds']:.2f} | {row['total_gpu_hours']:.3f} | "
            f"{row['mean_reward_std']:.4f} | {row['mean_grad_norm']:.4f} | "
            f"{row['max_approx_kl_ref']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Bottleneck Reading",
            "",
            "- Current live logs provide reliable end-to-end optimizer-step timing but do not contain subcomponent timers for generation, reward scoring, old/ref/new forward, optimizer, checkpoint I/O, or CPU preprocessing.",
            "- R8a/R8b use terminal-infer-step `5`, while process methods use process-infer-step `30`; terminal methods are still slower in wall-clock, so the bottleneck is unlikely to be sampler step count alone.",
            "- The likely bottleneck is terminal robust reward/probe scoring and guarded lyric scoring overhead, plus old/ref logprob evaluation over terminal rollouts. This is an inference from runner structure and observed end-to-end timings, not a component timer measurement.",
            "",
            "## Profiling Questions",
            "",
            "| component | status | current conclusion |",
            "|---|---|---|",
            "| generation time | not separately logged | needs isolated timer to quantify |",
            "| reward scoring time | not separately logged | likely important for R8a/R8b terminal methods |",
            "| old/ref/new forward time | not separately logged | likely scales with group size and selected terminal steps |",
            "| ratio/logprob estimator time | not separately logged | bundled into update/logprob calls |",
            "| optimizer time | not separately logged | likely smaller than generation/reward, but unproven |",
            "| checkpoint/logging/I/O time | checkpoint events visible only every 100 steps | unlikely to dominate ordinary steps |",
            "| CPU dataloading/preprocessing | not separately logged | prompt schedule is simple; unlikely dominant |",
            "",
            "## Recommendations",
            "",
            "- Do not change the running C1 job based on this profiling memo.",
            "- Reward caching may help only for repeated deterministic terminal scoring; it is unsafe for live policy updates unless cache keys include prompt, seed, adapter digest, waveform digest, reward config, and guard state.",
            "- Rollout parallelism is the most plausible acceleration path, pending the 2GPU shared-adapter smoke and Claude audit.",
            "- Batch/group-size adjustment would alter training semantics and should not be used for the current formal C1 run.",
            "- Treat step100 as health/early trend, step250 as first-wave decision checkpoint, and step1000 as extended training only if early trends justify it.",
        ]
    )
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": args.out, "r8a_steps": r8a.get("n_steps", 0), "r8b_steps": r8b.get("n_steps", 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
