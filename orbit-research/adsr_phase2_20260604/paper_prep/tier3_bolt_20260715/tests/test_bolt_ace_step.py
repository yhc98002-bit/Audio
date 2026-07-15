from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import torch


ROOT = Path(__file__).resolve().parents[1]
for name in ("bolt_state", "bolt_ace_step"):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
bolt = sys.modules["bolt_ace_step"]


def test_positive_instrumental_condition_has_zero_forbidden_lexemes():
    prompt = bolt.Prompt(
        prompt_id="dev_x", text="No vocals, no lyrics, a rock track", lyrics=None,
        structure_hint=None, duration_target=30.0,
        strata={"genre": "rock", "tempo_bin": "fast_120_160", "structural_complexity": "AABA"},
    )
    active, guidance, cfg = bolt.direction_condition(prompt, 0)
    assert active.lyrics is None
    assert bolt.FORBIDDEN_INSTRUMENTAL_SWITCH_TERMS.search(active.text) is None
    assert guidance == {}
    assert cfg == 7.5


class FakeTransformer:
    def decode(self, hidden_states, **_kwargs):
        return SimpleNamespace(sample=hidden_states + 1)


def fake_bundle(*, double=False):
    cache = {
        "encoder_hidden_cond": torch.ones((1, 1, 1)),
        "encoder_mask_cond": torch.ones((1, 1)),
        "encoder_hidden_null": torch.zeros((1, 1, 1)),
        "encoder_mask_null": torch.ones((1, 1)),
    }
    return bolt.ConditionBundle(
        prompt=None, requested_vocal=1, switched=double, cfg_scale=5.0,
        guidance_scale_text=5.0 if double else 0.0,
        guidance_scale_lyric=7.5 if double else 0.0,
        cache=cache, only_text_cache=cache if double else None,
        payload={}, condition_hash="x",
    )


def test_direct_transformer_call_accounting_by_guidance_branch():
    runner = bolt.AceStepBOLTRunner.__new__(bolt.AceStepBOLTRunner)
    runner.pipeline = SimpleNamespace(ace_step_transformer=FakeTransformer())
    runner.device = torch.device("cpu")
    runner.dtype = torch.float32
    runner._total_transformer_calls = 0
    latent = torch.zeros((1, 1, 1, 2))
    t = torch.tensor(500.0)
    runner._velocity(latent, t, 0, fake_bundle(double=False))
    assert runner.total_transformer_calls == 1
    runner._velocity(latent, t, 10, fake_bundle(double=False))
    assert runner.total_transformer_calls == 3
    runner._velocity(latent, t, 10, fake_bundle(double=True))
    assert runner.total_transformer_calls == 6
