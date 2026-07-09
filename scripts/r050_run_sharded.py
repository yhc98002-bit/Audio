"""R050 multi-GPU orchestrator (STOP-B-8 Phase-1 follow-up, 2026-05-17).

Runs `r050_mini_headroom_probe.py` as N concurrent subprocesses, one per GPU,
each handling a round-robin slice of the stratified 32-prompt subset. After all
shards complete, aggregates per-shard JSONLs (sorted by original subset order),
writes the canonical `runs/r050/r050_results.jsonl` + `orbit-research/R050_SUMMARY.md`
via the existing `_evaluate_deltas()` pass-rule machinery, and emits a
reproducibility manifest at `runs/r050/launch_context.json`.

PI directive 2026-05-17: "fully occupy" all 8 GPUs. Default
`--gpus 0,1,2,3,4,5,6,7 --n-shards 8`. With `n_prompts=32` and 8 shards each
shard handles 4 prompts × (1 Base + 8 BoN) ACE-Step samples ≈ 36 samples per
shard ≈ ~25-30 min wall on a 4090; expected to be faster on the Paratera
A800 80 GB nodes (sm_80) once that environment is benchmarked.

Usage:
    PYTHONPATH=src python scripts/r050_run_sharded.py

Optional flags (all have safe defaults):
    --n-shards 8
    --gpus 0,1,2,3,4,5,6,7
    --mode {production,dev}
    --prompts configs/prompts/dev.jsonl
    --n-prompts 32
    --bon-n 8
    --seed 42
    --allow-partial          # forwarded to each shard; orchestrator also relaxes len(deltas) == n_prompts
    --dry-run                # print per-shard commands without launching
    --runs-dir runs/r050     # where per-shard outputs + lock + log live
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SHARD_SCRIPT = REPO_ROOT / "scripts" / "r050_mini_headroom_probe.py"


def _import_r050_module():
    """Import scripts/r050_mini_headroom_probe.py as a module so we can reuse
    `_stratified_subset` (for ordering) and `_evaluate_deltas` (for the canonical
    summary write)."""
    spec = importlib.util.spec_from_file_location("r050", str(SHARD_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _nvidia_smi_check(target_gpus: list[int]) -> list[str]:
    """Return list of human-readable warnings (does NOT refuse). Uses
    `nvidia-smi --query-gpu` to detect busy GPUs that the operator may not
    have realized are occupied."""
    warnings: list[str] = []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        warnings.append(f"could not query nvidia-smi ({type(e).__name__}: {e})")
        return warnings
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[0])
            mem_used_mib = int(parts[1])
            util_pct = int(parts[2])
        except ValueError:
            continue
        if idx in target_gpus and (mem_used_mib > 2048 or util_pct > 5):
            warnings.append(f"GPU {idx}: {mem_used_mib} MiB used, {util_pct}% util"
                            f" (some other process is active; OOM risk if it grows)")
    return warnings


def _build_shard_env(gpu: int, n_shards: int) -> dict:
    """Build the env dict for a shard subprocess. Inherit everything except
    CUDA_VISIBLE_DEVICES (force-pinned to this GPU), CUDA_DEVICE_ORDER (PCI for
    consistency with nvidia-smi), and OMP/MKL thread counts (avoid 8-way
    oversubscription)."""
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    cpus = os.cpu_count() or 8
    threads = max(1, cpus // max(1, n_shards))
    env["OMP_NUM_THREADS"] = str(threads)
    env["MKL_NUM_THREADS"] = str(threads)
    return env


def _build_shard_cmd(args, shard_idx: int) -> list[str]:
    cmd = [
        sys.executable, str(SHARD_SCRIPT),
        "--prompts", args.prompts,
        "--n-prompts", str(args.n_prompts),
        "--bon-n", str(args.bon_n),
        "--seed", str(args.seed),
        "--mode", args.mode,
        "--shard-index", str(shard_idx),
        "--shard-total", str(args.n_shards),
    ]
    if args.allow_partial:
        cmd.append("--allow-partial")
    if args.allow_template_prompts:
        cmd.append("--allow-template-prompts")
    return cmd


def _atomic_write(path: Path, payload: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-shards", type=int, default=8)
    parser.add_argument("--gpus", default="0,1,2,3,4,5,6,7",
                        help="Comma-separated physical GPU indices.")
    parser.add_argument("--mode", choices=["dev", "production"], default="production")
    parser.add_argument("--prompts", default="configs/prompts/dev.jsonl")
    parser.add_argument("--n-prompts", type=int, default=32)
    parser.add_argument("--bon-n", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--allow-partial", action="store_true",
                        help="Forwarded to each shard; orchestrator also skips the"
                             " aggregate len(deltas) == n_prompts assertion.")
    parser.add_argument("--allow-template-prompts", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--runs-dir", default="runs/r050")
    parser.add_argument("--out", default="runs/r050/r050_results.jsonl",
                        help="Canonical aggregate output path.")
    parser.add_argument("--summary", default="orbit-research/R050_SUMMARY.md")
    args = parser.parse_args()

    gpus = [int(g.strip()) for g in args.gpus.split(",") if g.strip()]
    if len(gpus) != args.n_shards:
        print(f"R050 ORCHESTRATOR BLOCK: --n-shards={args.n_shards} but --gpus has"
              f" {len(gpus)} entries ({gpus}).")
        return 2
    if args.n_prompts < args.n_shards:
        print(f"R050 ORCHESTRATOR BLOCK: --n-prompts={args.n_prompts} <"
              f" --n-shards={args.n_shards}; some shards would have zero prompts.")
        return 2

    runs_dir = Path(args.runs_dir)
    shards_dir = runs_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)
    lock_path = runs_dir / ".lock"

    if lock_path.exists():
        print(f"R050 ORCHESTRATOR BLOCK: {lock_path} exists — a previous run may still"
              " be active. If you're sure no other run is in flight, remove the lock"
              " and retry: rm runs/r050/.lock")
        return 2

    # Sanity warnings (do not refuse).
    warnings = _nvidia_smi_check(gpus)
    if warnings:
        print("R050 ORCHESTRATOR WARN (informational, not a block):")
        for w in warnings:
            print(f"  - {w}")

    # Build per-shard commands.
    cmds = [_build_shard_cmd(args, i) for i in range(args.n_shards)]
    envs = [_build_shard_env(gpus[i], args.n_shards) for i in range(args.n_shards)]

    if args.dry_run:
        print("R050 ORCHESTRATOR DRY-RUN: would launch the following:")
        for i, (cmd, env) in enumerate(zip(cmds, envs)):
            print(f"  shard {i} → GPU {gpus[i]}:")
            print(f"    CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']} \\")
            print(f"    OMP_NUM_THREADS={env['OMP_NUM_THREADS']} \\")
            print("    " + " ".join(cmd))
        return 0

    # Acquire lock + record start.
    start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lock_payload = {"pid": os.getpid(), "start_time": start_time,
                     "n_shards": args.n_shards, "gpus": gpus}
    _atomic_write(lock_path, json.dumps(lock_payload, indent=2))

    procs: list[subprocess.Popen] = []
    log_paths: list[Path] = []
    try:
        for i, (cmd, env) in enumerate(zip(cmds, envs)):
            log_path = shards_dir / f"shard_{i}_of_{args.n_shards}.log"
            log_paths.append(log_path)
            log_handle = log_path.open("w", encoding="utf-8")
            print(f"R050 launch shard {i} → GPU {gpus[i]} → {log_path}")
            p = subprocess.Popen(cmd, env=env, stdout=log_handle,
                                  stderr=subprocess.STDOUT, cwd=str(REPO_ROOT))
            procs.append(p)

        first_log = shards_dir / f"shard_0_of_{args.n_shards}.log"
        print(f"\nR050 ORCHESTRATOR: {args.n_shards} shards launched at {start_time}."
              " Waiting for all to complete...\n"
              f"  Tail any shard log to follow progress, e.g.: tail -f {first_log}")

        # Wait-all (does NOT cancel siblings on first failure — more informative).
        exit_codes = [p.wait() for p in procs]
        end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        print(f"\nR050 ORCHESTRATOR: all shards done at {end_time}.")
        for i, code in enumerate(exit_codes):
            print(f"  shard {i} (GPU {gpus[i]}): exit={code}  log={log_paths[i]}")

        if any(c != 0 for c in exit_codes):
            print("\nR050 ORCHESTRATOR ABORT: one or more shards failed; refusing to"
                  " aggregate partial results. Inspect the shard logs above.")
            # Persist launch_context even on failure for forensics.
            _atomic_write(
                runs_dir / "launch_context.json",
                json.dumps({
                    "n_shards": args.n_shards, "gpus": gpus, "mode": args.mode,
                    "n_prompts": args.n_prompts, "seed": args.seed,
                    "prompts": args.prompts, "start_time": start_time,
                    "end_time": end_time, "per_shard_exit_codes": exit_codes,
                    "outcome": "shard_failure",
                }, indent=2),
            )
            return max(exit_codes)

        # All shards green — aggregate.
        r050 = _import_r050_module()
        # Replay stratified subset on the FULL prompt set to get the canonical
        # ordering, then build a prompt_id → subset_index map for re-sorting.
        from mprm.data.prompts import load_prompts
        full_subset = r050._stratified_subset(
            load_prompts(args.prompts), n=args.n_prompts
        )
        pid_to_subset_idx = {p.prompt_id: idx for idx, p in enumerate(full_subset)}

        # Concatenate per-shard JSONLs.
        raw_rows: list[dict] = []
        for i in range(args.n_shards):
            shard_jsonl = runs_dir / f"r050_results.shard_{i}_of_{args.n_shards}.jsonl"
            if not shard_jsonl.exists():
                print(f"R050 ORCHESTRATOR ABORT: shard {i} reported success but"
                      f" {shard_jsonl} is missing.")
                return 2
            for line in shard_jsonl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                raw_rows.append(json.loads(line))

        # Sort by original subset index for provenance.
        raw_rows.sort(key=lambda r: pid_to_subset_idx.get(r["prompt_id"], 1 << 30))
        deltas = [float(r["delta"]) for r in raw_rows]

        # Sanity-assert aggregate size.
        if not args.allow_partial and len(deltas) != args.n_prompts:
            print(f"R050 ORCHESTRATOR BLOCK: aggregated {len(deltas)} deltas; expected"
                  f" {args.n_prompts}. Per-shard JSONLs may be incomplete.")
            return 2

        # Atomic write of canonical aggregate JSONL.
        canonical_out = Path(args.out)
        canonical_out.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in raw_rows) + "\n"
        _atomic_write(canonical_out, payload)

        # Apply pass rule via the existing _evaluate_deltas → also writes summary.
        # We pass the summary path here (single-process default) so the canonical
        # R050_SUMMARY.md gets written.
        summary_path = Path(args.summary)
        verdict = r050._evaluate_deltas(
            deltas, args.n_prompts, args.mode, args.allow_partial, summary_path
        )

        # Record launch context.
        _atomic_write(
            runs_dir / "launch_context.json",
            json.dumps({
                "n_shards": args.n_shards,
                "gpu_assignment": {str(i): gpus[i] for i in range(args.n_shards)},
                "mode": args.mode,
                "n_prompts": args.n_prompts,
                "bon_n": args.bon_n,
                "seed": args.seed,
                "prompts": args.prompts,
                "start_time": start_time,
                "end_time": end_time,
                "per_shard_exit_codes": exit_codes,
                "outcome": "pass" if verdict == 0 else "pause_and_report",
                "verdict_exit_code": verdict,
                "aggregated_n_deltas": len(deltas),
                "hostname": os.uname().nodename,
                "summary_path": str(summary_path),
                "results_jsonl": str(canonical_out),
            }, indent=2),
        )

        print(f"\nR050 ORCHESTRATOR: wrote canonical results to {canonical_out}")
        print(f"R050 ORCHESTRATOR: wrote launch context to {runs_dir / 'launch_context.json'}")
        return verdict

    finally:
        # Always release the lock, even on exception.
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
