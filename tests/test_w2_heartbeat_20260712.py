from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "orbit-research/adsr_phase2_20260604/paper_prep/scripts/w2_heartbeat_20260712.sh"
)


def run_once(root: Path, node: str) -> str:
    (root / "paper_prep/scripts").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({"MPRM_REPO_ROOT": str(root), "MPRM_HEARTBEAT_ONCE": "1"})
    subprocess.run(["bash", str(SCRIPT), node], check=True, env=env)
    return (root / f"paper_prep/heartbeat_{node}.log").read_text(encoding="utf-8")


def test_heartbeat_does_not_count_itself_or_shell_wrappers(tmp_path: Path) -> None:
    report = run_once(tmp_path, "idle")
    assert "--- ADSR Python processes ---\nNONE\n" in report
    assert "NO_ADSR_RELEVANT_PROCESS_ACTIVE" in report
    assert "ADSR_RELEVANT_PROCESS_ACTIVE" not in report.splitlines()


def test_heartbeat_detects_live_w2_python_process(tmp_path: Path) -> None:
    dummy = tmp_path / "paper_prep/scripts/w2_dummy.py"
    dummy.parent.mkdir(parents=True, exist_ok=True)
    dummy.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(dummy)])
    try:
        report = run_once(tmp_path, "active")
    finally:
        process.terminate()
        process.wait(timeout=10)
    assert str(dummy) in report
    assert "ADSR_RELEVANT_PROCESS_ACTIVE" in report
