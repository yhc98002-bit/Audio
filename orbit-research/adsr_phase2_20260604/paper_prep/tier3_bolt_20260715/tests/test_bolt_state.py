from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bolt_state", ROOT / "bolt_state.py")
state_mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = state_mod
SPEC.loader.exec_module(state_mod)


def make_state():
    return state_mod.CheckpointState(
        state_id="p0__1__s06",
        prompt_id="p0",
        root_seed=1,
        completed_steps=6,
        scheduler_index=6,
        timestep=700.0,
        sigma=0.7,
        next_sigma=0.6,
        latent=torch.arange(24, dtype=torch.float32).reshape(1, 2, 3, 4),
        model_output=torch.ones((1, 2, 3, 4), dtype=torch.float32),
        condition_hash="c" * 64,
        model_hash="m" * 64,
        checkpoint_hash="k" * 64,
        scheduler_hash="s" * 64,
        cpu_rng_state=torch.get_rng_state(),
        cuda_rng_state=None,
        generator_rng_state=torch.Generator().manual_seed(1).get_state(),
        nfe_count=8,
        scheduler_step_count=6,
        extras={"test": True},
    )


def test_state_serialization_and_idempotent_resume(tmp_path):
    path = tmp_path / "state.pt"
    metadata = state_mod.save_checkpoint_state(make_state(), path)
    loaded, loaded_meta = state_mod.load_checkpoint_state(path)
    assert torch.equal(loaded.latent, make_state().latent)
    assert metadata["latent_sha256"] == loaded_meta["latent_sha256"]
    assert state_mod.save_checkpoint_state(make_state(), path, allow_existing=True)["state_id"] == "p0__1__s06"
    with pytest.raises(FileExistsError):
        state_mod.save_checkpoint_state(make_state(), path)


def test_cross_process_load(tmp_path):
    path = tmp_path / "state.pt"
    state_mod.save_checkpoint_state(make_state(), path)
    code = (
        "import importlib.util,json,sys; from pathlib import Path; "
        f"s=importlib.util.spec_from_file_location('bolt_state',r'{ROOT / 'bolt_state.py'}'); "
        "m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); "
        f"x,meta=m.load_checkpoint_state(Path(r'{path}')); "
        "print(json.dumps({'state_id':x.state_id,'latent':m.tensor_sha256(x.latent)}))"
    )
    output = subprocess.check_output([sys.executable, "-c", code], text=True)
    row = json.loads(output)
    assert row["state_id"] == "p0__1__s06"
    assert row["latent"] == state_mod.tensor_sha256(make_state().latent)


def test_condition_hash_change_and_silent_fallback():
    before = state_mod.canonical_condition_hash({"text": "base", "cfg": 5.0})
    after = state_mod.canonical_condition_hash({"text": "instrumental", "cfg": 7.5})
    state_mod.assert_condition_changed(before, after)
    with pytest.raises(RuntimeError, match="silent conditioning fallback"):
        state_mod.assert_condition_changed(before, before)


def test_fork_determinism_and_diversity():
    latent = torch.zeros((1, 2, 3, 4), dtype=torch.bfloat16)
    a = state_mod.fork_latent(latent, sigma=0.5, eta=0.025, branch_seed=10)
    b = state_mod.fork_latent(latent, sigma=0.5, eta=0.025, branch_seed=10)
    c = state_mod.fork_latent(latent, sigma=0.5, eta=0.025, branch_seed=11)
    assert torch.equal(a, b)
    assert not torch.equal(a, c)
