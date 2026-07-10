import json
from pathlib import Path

import pytest

from mprm.common.run_ledger import RunLedger


def test_run_ledger_appends(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = RunLedger(ledger_path)
    ledger.start(
        run_id="r0_test",
        rung_id="R0",
        stage="phase_a",
        config_hash="config-sha",
        git_sha="git-sha",
        model_sha="model-sha",
    )
    ledger.final(run_id="r0_test", rung_id="R0", stage="phase_a",
                 metrics={"r_lcb": 0.42})

    lines = ledger_path.read_text().splitlines()
    assert len(lines) == 2
    entries = [json.loads(line) for line in lines]
    assert entries[0]["event"] == "start"
    assert entries[1]["event"] == "final"
    assert entries[1]["metrics"]["r_lcb"] == pytest.approx(0.42)
    assert entries[1]["config_hash"] == "config-sha"
    assert entries[1]["git_sha"] == "git-sha"
    assert entries[1]["model_sha"] == "model-sha"


def test_run_ledger_fail_path(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    ledger.start(
        run_id="r0_test",
        rung_id="R0",
        stage="phase_a",
        config_hash="config-sha",
        git_sha="git-sha",
        model_sha="model-sha",
    )
    ledger.fail(run_id="r0_test", rung_id="R0", stage="phase_a", error="checkpoint missing")

    entries = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert entries[-1]["event"] == "fail"
    assert "checkpoint missing" in entries[-1]["notes"]
    assert entries[-1]["config_hash"] == "config-sha"
    assert entries[-1]["git_sha"] == "git-sha"
    assert entries[-1]["model_sha"] == "model-sha"
