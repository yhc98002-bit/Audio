#!/usr/bin/env python3
"""Poll non-preemptively and launch a queued ADSR GPU job after 20 idle minutes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[4]
PAPER = ROOT / "paper_prep"
MASTER_LEDGER = PAPER / "autochain_20260712/AUTOCHAIN_EXECUTION_LEDGER.jsonl"
PROJECT_TIMEZONE = ZoneInfo("Asia/Shanghai")


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def gpu_state(node: str) -> list[dict]:
    command = (
        "nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu "
        "--format=csv,noheader,nounits; echo __APPS__; "
        "nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null || true"
    )
    output = subprocess.check_output(["ssh", node, command], text=True, timeout=30)
    gpu_text, app_text = output.split("__APPS__", 1)
    occupied = {line.strip() for line in app_text.splitlines() if line.strip()}
    rows = []
    for line in gpu_text.splitlines():
        if not line.strip():
            continue
        index, uuid, memory, utilization = [value.strip() for value in line.split(",")]
        rows.append(
            {
                "index": int(index),
                "uuid": uuid,
                "memory_mib": int(memory),
                "utilization_pct": int(utilization),
                "compute_process": uuid in occupied,
            }
        )
    return rows


def free_indices(rows: list[dict]) -> list[int]:
    return [
        row["index"]
        for row in rows
        if not row["compute_process"] and row["memory_mib"] <= 1024 and row["utilization_pct"] <= 1
    ]


def signature_ready() -> bool:
    amendment = (PAPER / "W2_AMENDMENT_20260712.md").read_text(encoding="utf-8")
    adoption = (PAPER / "t7_judge_gold_20260713/W2_ADOPTION_SIGNATURE_REQUEST.md").read_text(encoding="utf-8")
    return (
        "W2_AMENDMENT_STATUS = SIGNED_BY_BOTH_PIS" in amendment
        and "W2_ADOPTION = SIGNED" in adoption
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", choices=("judge", "live"), required=True)
    parser.add_argument("--poll-seconds", type=int, default=600)
    parser.add_argument("--idle-seconds", type=int, default=1200)
    parser.add_argument("--timeout-seconds", type=int, default=86400)
    parser.add_argument("--session-name", required=True)
    args = parser.parse_args()
    required = 4
    nodes = ["an29"] if args.job == "judge" else ["an12", "an29"]
    out = PAPER / "t7_judge_gold_20260713/gpu_queue"
    log = out / f"{args.job}_gpu_watch.jsonl"
    status_path = out / f"{args.job}_gpu_watch_status.json"
    started = time.time()
    eligible_since: dict[tuple[str, tuple[int, ...]], float] = {}
    while True:
        now = dt.datetime.now(PROJECT_TIMEZONE).isoformat(timespec="seconds")
        observations = []
        candidates = []
        signatures = True if args.job == "judge" else signature_ready()
        for node in nodes:
            try:
                state = gpu_state(node)
                free = free_indices(state)
                observations.append({"node": node, "state": state, "free_indices": free})
                if len(free) >= required and signatures:
                    key = (node, tuple(free[:required]))
                    eligible_since.setdefault(key, time.time())
                    candidates.append(key)
            except Exception as exc:  # noqa: BLE001
                observations.append({"node": node, "error": f"{type(exc).__name__}: {exc}"})
        active_keys = set(candidates)
        eligible_since = {key: value for key, value in eligible_since.items() if key in active_keys}
        record = {
            "timestamp": now,
            "task": f"{args.job.upper()}_GPU_QUEUE_POLL",
            "host": "ln207",
            "command": str(Path(__file__).resolve()),
            "inputs": [f"nodes={','.join(nodes)}", f"required_gpus={required}", f"signatures_ready={signatures}"],
            "outputs": [str(log)],
            "status": "WAITING",
            "next_action": "poll again in 10 minutes without preemption",
            "observations": observations,
        }
        append(log, record)
        append(MASTER_LEDGER, record)
        for node, indices in candidates:
            idle_for = time.time() - eligible_since[(node, indices)]
            if idle_for < args.idle_seconds:
                continue
            gpu_list = ",".join(str(index) for index in indices)
            if args.job == "judge":
                remote_session = "adsr_t7_judge_chain_20260713"
                script = PAPER / "scripts/run_t7_judge_chain_on_an29.sh"
            else:
                remote_session = "adsr_w2_liveconfirm_20260713"
                script = PAPER / "scripts/run_w2_liveconfirm_20260713.sh"
            remote = (
                f"cd {ROOT} && tmux has-session -t {remote_session} 2>/dev/null || "
                f"tmux new-session -d -s {remote_session} 'bash {script} {gpu_list}'"
            )
            subprocess.check_call(["ssh", node, remote])
            launched = {
                **record,
                "status": "LAUNCHED",
                "next_action": "monitor the remote tmux job; do not start the 48-hour live clock before this launch",
                "launch_node": node,
                "gpu_indices": list(indices),
                "remote_tmux_session": remote_session,
                "actual_launch_timestamp": dt.datetime.now(PROJECT_TIMEZONE).isoformat(timespec="seconds"),
                "idle_predicate_seconds": idle_for,
            }
            append(log, launched)
            append(MASTER_LEDGER, launched)
            status_path.write_text(json.dumps(launched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return 0
        if time.time() - started >= args.timeout_seconds:
            escalation = {
                **record,
                "status": "TIMEOUT_24H_ESCALATED",
                "next_action": "PI should consider yielding a four-GPU same-node job; judge needs four idle an29 GPUs, while live confirmation minimally needs four idle GPUs on one node",
            }
            append(log, escalation)
            append(MASTER_LEDGER, escalation)
            status_path.write_text(json.dumps(escalation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (out / f"{args.job.upper()}_GPU_QUEUE_24H_ESCALATION.md").write_text(
                f"# {args.job.title()} GPU Queue Escalation\n\n"
                "No qualifying GPU allocation became continuously idle for 20 minutes within 24 hours. No job was preempted. "
                + ("The judge requires four idle GPUs on an29 because its 66 GiB node-local model and TP=4 service cannot split across nodes. " if args.job == "judge" else "The prepared live launcher requires four idle GPUs on one node; a reduced-prompt run would still require one GPU but would deviate from the frozen 64-prompt design. ")
                + "Please consider which currently running job may be voluntarily yielded.\n",
                encoding="utf-8",
            )
            return 3
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
