"""M1a parallel rungs orchestrator (STOP-B-8 Phase-2, 2026-05-17;
oversubscription patch 2026-05-19 for Paratera 8× A800 80 GB).

Spawns subprocesses of `scripts/launch_baseline.py`, each pinned to a physical
GPU via `CUDA_VISIBLE_DEVICES`. Per-task stdout+stderr is redirected to
`runs/m1a_phase/<split>/<rung>[-seed<N>].log`. Polls all subprocesses, fills
empty slots as tasks finish, reports per-task exit codes.

Two scheduling modes:

  (A) **Per-rung (default; backwards-compatible).** No `--seeds`; each
      rung becomes one subprocess that iterates its config-declared seeds
      sequentially internally. `--concurrency-per-gpu 1` (default) → one
      active subprocess per GPU. Suitable when len(rungs) ≤ len(gpus) and you
      want clean per-GPU isolation.

  (B) **Per (rung × seed) — oversubscribed (Paratera A800).** Pass
      `--seeds 0,1,2 --concurrency-per-gpu 3`; the orchestrator expands the
      Cartesian product (rungs × seeds) and dispatches tuples round-robin to
      GPUs, with up to `concurrency-per-gpu` concurrent subprocesses per GPU.
      Each subprocess receives `--seeds <single>` so launch_baseline runs
      exactly one seed end-to-end. M1a dev (6 rungs × 3 seeds = 18 tasks)
      fits in 8 GPUs × 3 slots = 24 slots → all 18 concurrent; wallclock
      drops vs the current 6-GPU-of-8 single-task pattern.

      Memory: ACE-Step + reward harness peak ~20 GB per subprocess on this
      stack (sichuan RUN_LEDGER OOM at ~14 GB on 4090; A800 reward stack
      adds ~6 GB). 3 subprocesses × 20 GB = 60 GB < 80 GB A800 budget.
      CPU: OMP/MKL threads autoscale to (nproc // total_concurrent_tasks),
      not (nproc // 8), so 18 concurrent tasks on 112 CPUs → 6 threads/task.

Sharding boundary: still pure per-task launcher. Each subprocess is
bit-identical to a serial `launch_baseline.py --seeds <N>` invocation;
RunLedger appends are atomic per the existing `open("a", ...)` contract.

Pre-flight:
  - Refuse if `runs/m1a_phase/.<split>.lock` exists (concurrent-run guard).
  - Warn (don't refuse) when len(tasks) > len(gpus) × concurrency_per_gpu —
    drain logic queues the overflow.
  - Warn (don't refuse) if any target GPU has > 2 GB used or > 5 % util.

Usage:
    # Per-rung default (legacy):
    python scripts/m1a_run_parallel_rungs.py --split dev --rungs r0,r1,... \\
        --gpus 0,1,2,3,4,5,6,7 --mode production
    # Per (rung × seed) oversubscribed (A800):
    python scripts/m1a_run_parallel_rungs.py --split dev --rungs r0,r1,... \\
        --gpus 0,1,2,3,4,5,6,7 --seeds 0,1,2 --concurrency-per-gpu 3 \\
        --mode production
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCH_BASELINE = REPO_ROOT / "scripts" / "launch_baseline.py"
CONFIG_DIR = REPO_ROOT / "configs" / "baselines"


def _nvidia_smi_check(target_gpus: list[int]) -> list[str]:
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
        if idx in target_gpus:
            if mem_used_mib > 2048 or util_pct > 5:
                warnings.append(
                    f"GPU {idx}: mem_used={mem_used_mib} MiB, util={util_pct} %"
                    " (>2 GB or >5 % — another process may be running there)"
                )
    return warnings


def _build_cmd(rung: str, split: str, mode: str, prompts: str | None) -> list[str]:
    cfg = CONFIG_DIR / f"{rung}.yaml"
    if not cfg.exists():
        raise FileNotFoundError(f"rung config not found: {cfg}")
    py = sys.executable  # propagate the caller's conda env Python
    cmd = [py, str(LAUNCH_BASELINE), "--config", str(cfg),
           "--split", split, "--mode", mode]
    if prompts:
        cmd += ["--prompts", prompts]
    return cmd


def _build_cmd_with_seed(rung: str, split: str, mode: str, prompts: str | None,
                          seed: int | None) -> list[str]:
    cmd = _build_cmd(rung, split, mode, prompts)
    if seed is not None:
        cmd += ["--seeds", str(seed)]
    return cmd


def _task_key(rung: str, seed: int | None) -> str:
    return f"{rung}-seed{seed}" if seed is not None else rung


def _spawn_task(rung: str, seed: int | None, gpu_id: int, split: str, mode: str,
                prompts: str | None, logs_dir: Path,
                cpu_share: int) -> tuple[subprocess.Popen, Path]:
    cmd = _build_cmd_with_seed(rung, split, mode, prompts, seed)
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    # 2026-05-19 Codex review: cover all common thread-pool env vars; the OMP/MKL
    # pair alone leaves OpenBLAS / NumExpr / blis pools at their unbounded default,
    # which oversubscribes the 112-core box at 18× concurrency. Also disable HF
    # tokenizers fork-parallelism (per-task DataLoader workers do per-worker
    # tokenization already; in-process parallel tokenizers fight for the same SMs).
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
        env[var] = str(cpu_share)
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    # PYTHONPATH: explicitly prepend src/ so it works even if the parent shell
    # had a PYTHONPATH without src in it. `setdefault` would no-op in that case.
    _src = str(REPO_ROOT / "src")
    _existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_src}{os.pathsep}{_existing}" if _existing else _src
    log_path = logs_dir / f"{_task_key(rung, seed)}.log"
    log_fh = log_path.open("w", buffering=1)
    log_fh.write(f"# M1a orchestrator — rung={rung} seed={seed} gpu={gpu_id} split={split} mode={mode}\n")
    log_fh.write(f"# CUDA_VISIBLE_DEVICES={gpu_id} OMP_NUM_THREADS={cpu_share}\n")
    log_fh.write(f"# cmd={' '.join(cmd)}\n")
    log_fh.write(f"# start={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n\n")
    log_fh.flush()
    proc = subprocess.Popen(cmd, env=env, stdout=log_fh, stderr=subprocess.STDOUT,
                            cwd=str(REPO_ROOT))
    return proc, log_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "held_out"], required=True,
                        help="prompt split for all rungs in this batch")
    parser.add_argument("--rungs", required=True,
                        help="comma-separated rung names (must match configs/baselines/<rung>.yaml)")
    parser.add_argument("--gpus", default="0,1,2,3,4,5,6,7",
                        help="comma-separated physical GPU indices")
    parser.add_argument("--mode", choices=["dev", "production"], default="production")
    parser.add_argument("--prompts", default=None,
                        help="override per-rung prompts path (e.g. configs/prompts/held_out.jsonl)")
    parser.add_argument("--runs-dir", default="runs/m1a_phase",
                        help="where per-task logs + lock live")
    parser.add_argument("--dry-run", action="store_true",
                        help="print per-task commands without launching")
    parser.add_argument("--seeds", default=None,
                        help="comma-separated seeds; when set, expand the Cartesian "
                             "product (rungs × seeds) into separate processes (each "
                             "subprocess gets --seeds <single>). Default None: each "
                             "rung subprocess iterates its config-declared seeds "
                             "internally (legacy backwards-compatible).")
    parser.add_argument("--concurrency-per-gpu", type=int, default=1,
                        help="max concurrent subprocesses per GPU. Default 1 (no "
                             "oversubscription). Use 2-3 on A800 80 GB when each task "
                             "uses <40 GB (ACE-Step + reward harness ≈ 20 GB).")
    parser.add_argument("--poll-interval", type=float, default=2.0,
                        help="seconds between poll cycles during drain (default 2.0)")
    args = parser.parse_args()

    rungs = [r.strip() for r in args.rungs.split(",") if r.strip()]
    gpus = [int(g.strip()) for g in args.gpus.split(",") if g.strip()]
    seeds: list[int | None]
    if args.seeds:
        seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    else:
        seeds = [None]  # backwards-compatible: one subprocess per rung
    slots_per_gpu = max(1, int(args.concurrency_per_gpu))

    if not rungs:
        print("ERROR: --rungs cannot be empty", file=sys.stderr)
        return 2
    if not gpus:
        print("ERROR: --gpus cannot be empty", file=sys.stderr)
        return 2

    # Build the (rung, seed) task list and assign to GPUs round-robin.
    tasks: list[tuple[str, int | None]] = [(r, s) for r in rungs for s in seeds]
    total_slots = slots_per_gpu * len(gpus)
    if len(tasks) > total_slots:
        print(f"NOTICE: {len(tasks)} tasks > {total_slots} concurrent slots"
              f" ({len(gpus)} GPUs × {slots_per_gpu} per GPU) — drain queue"
              " will hold overflow.", file=sys.stderr)

    runs_dir = Path(args.runs_dir).resolve()
    logs_dir = runs_dir / args.split
    logs_dir.mkdir(parents=True, exist_ok=True)
    lock_path = runs_dir / f".{args.split}.lock"

    if lock_path.exists():
        print(f"BLOCK: another orchestrator is running ({lock_path} exists)."
              f"\n  Remove the lock manually after confirming no live python processes"
              f" remain: rm {lock_path}", file=sys.stderr)
        return 2

    warnings = _nvidia_smi_check(gpus)
    if warnings:
        print("nvidia-smi warnings (informational; not blocking):")
        for w in warnings:
            print(f"  WARN: {w}")

    # CPU thread budget: scale down by actual concurrency, not the gpu count alone.
    # 112 CPUs / 18 concurrent tasks ≈ 6 threads/task vs old fixed 14.
    concurrent_cap = min(len(tasks), total_slots)
    cpu_share = max(1, (os.cpu_count() or 8) // max(1, concurrent_cap))

    # Round-robin (rung, seed) tuples across GPUs.
    assignment: list[tuple[str, int | None, int]] = [
        (rung, seed, gpus[i % len(gpus)])
        for i, (rung, seed) in enumerate(tasks)
    ]

    print(f"=== M1a orchestrator — split={args.split} mode={args.mode}"
          f" rungs={len(rungs)} seeds={seeds} tasks={len(tasks)}"
          f" slots/GPU={slots_per_gpu} cpu/task={cpu_share} ===")
    for rung, seed, gpu in assignment:
        print(f"  {_task_key(rung, seed):40s} -> GPU {gpu}")

    if args.dry_run:
        for rung, seed, gpu in assignment:
            cmd = _build_cmd_with_seed(rung, args.split, args.mode, args.prompts, seed)
            print(f"DRY: CUDA_VISIBLE_DEVICES={gpu} OMP_NUM_THREADS={cpu_share}"
                  f" {' '.join(cmd)}")
        return 0

    lock_path.write_text(json.dumps({
        "pid": os.getpid(),
        "split": args.split,
        "mode": args.mode,
        "rungs": rungs,
        "seeds": seeds,
        "gpus": gpus,
        "slots_per_gpu": slots_per_gpu,
        "start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hostname": os.uname().nodename,
    }, indent=2))

    per_gpu_queue: dict[int, list[tuple[str, int | None]]] = {g: [] for g in gpus}
    for rung, seed, gpu in assignment:
        per_gpu_queue[gpu].append((rung, seed))

    exit_codes: dict[str, int] = {}
    try:
        # active_procs: list of (rung, seed, gpu, proc, log_path)
        active_procs: list[tuple[str, int | None, int, subprocess.Popen, Path]] = []

        # Initial fill: up to slots_per_gpu concurrent tasks per GPU.
        for gpu in gpus:
            for _ in range(slots_per_gpu):
                if not per_gpu_queue[gpu]:
                    break
                rung, seed = per_gpu_queue[gpu].pop(0)
                proc, log_path = _spawn_task(rung, seed, gpu, args.split,
                                             args.mode, args.prompts, logs_dir,
                                             cpu_share)
                active_procs.append((rung, seed, gpu, proc, log_path))
                print(f"  spawned {_task_key(rung, seed):40s} on GPU {gpu}"
                      f" (pid={proc.pid}) -> {log_path}")
                time.sleep(0.5)

        print(f"\nFirst wave: {len(active_procs)} subprocesses live"
              f" ({slots_per_gpu}/GPU target). Polling every {args.poll_interval}s.")

        # Drain: poll completions; refill empty slots as they free up.
        while active_procs or any(per_gpu_queue.values()):
            still_active: list[tuple[str, int | None, int, subprocess.Popen, Path]] = []
            for rung, seed, gpu, proc, log_path in active_procs:
                ec = proc.poll()
                if ec is None:
                    still_active.append((rung, seed, gpu, proc, log_path))
                    continue
                key = _task_key(rung, seed)
                exit_codes[key] = ec
                sym = "OK" if ec == 0 else f"FAIL exit={ec}"
                print(f"  [{key:40s} GPU {gpu}] {sym}  log={log_path}")
            active_procs = still_active

            # Refill: any GPU with free slots launches its next queued task.
            for gpu in gpus:
                used = sum(1 for _, _, g, _, _ in active_procs if g == gpu)
                slots_free = slots_per_gpu - used
                for _ in range(max(0, slots_free)):
                    if not per_gpu_queue[gpu]:
                        break
                    rung, seed = per_gpu_queue[gpu].pop(0)
                    proc, log_path = _spawn_task(rung, seed, gpu, args.split,
                                                 args.mode, args.prompts, logs_dir,
                                                 cpu_share)
                    active_procs.append((rung, seed, gpu, proc, log_path))
                    print(f"  spawned {_task_key(rung, seed):40s} on GPU {gpu}"
                          f" (pid={proc.pid}) -> {log_path}")
                    time.sleep(0.5)

            if active_procs:
                time.sleep(args.poll_interval)

    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass

    failed = [k for k, ec in exit_codes.items() if ec != 0]
    summary = {
        "split": args.split,
        "mode": args.mode,
        "rungs": rungs,
        "seeds": seeds,
        "gpus": gpus,
        "slots_per_gpu": slots_per_gpu,
        "tasks": [_task_key(r, s) for r, s in tasks],
        "exit_codes": exit_codes,
        "failed": failed,
        "end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hostname": os.uname().nodename,
    }
    summary_path = logs_dir / "orchestrator_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nOrchestrator summary written to {summary_path}")

    if failed:
        print(f"\nFAIL: {len(failed)}/{len(tasks)} tasks failed: {failed}", file=sys.stderr)
        print(f"  Inspect per-task logs under {logs_dir}/", file=sys.stderr)
        return max(ec for ec in exit_codes.values() if ec != 0)

    print(f"\nPASS: all {len(tasks)} tasks completed (exit=0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
