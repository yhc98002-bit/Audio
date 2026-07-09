import torch

from mprm.data.prompts import Prompt
from mprm.rewards.interface import RewardModel, RewardScore
from mprm.rewards.robust_lcb import robust_lcb


class _ConstantReward(RewardModel):
    def __init__(self, axis: str, value: float):
        self.axis = axis
        self.version = "test"
        self._value = value

    def score(self, waveform, sample_rate, prompt):
        return RewardScore(axis=self.axis, value=self._value)


def test_robust_lcb_identity_only_no_probe():
    waveform = torch.zeros(1, 16000)
    prompt = Prompt(prompt_id="t1", text="hi", lyrics=None, structure_hint=None, duration_target=1.0)
    reward_models = [_ConstantReward("a", 0.5), _ConstantReward("b", 0.7)]
    perts = {"identity": lambda w, sr: w}
    res = robust_lcb(waveform, 16000, prompt, reward_models=reward_models,
                     perturbations=perts, probe_scores={}, lambda_probe={}, beta_robust=0.5)
    # cells = [0.5, 0.7]; mean=0.6, std=0.1
    assert res.mean_cells == 0.6
    assert abs(res.std_cells - 0.1) < 1e-6
    assert abs(res.value - (0.6 - 0.5 * 0.1)) < 1e-6


def test_robust_lcb_probe_penalty_with_floor():
    waveform = torch.zeros(1, 16000)
    prompt = Prompt(prompt_id="t2", text="hi", lyrics=None, structure_hint=None, duration_target=1.0)
    reward_models = [_ConstantReward("a", 0.5)]
    perts = {"identity": lambda w, sr: w}
    res = robust_lcb(waveform, 16000, prompt, reward_models=reward_models,
                     perturbations=perts,
                     probe_scores={"silence_fraction": 0.8},
                     lambda_probe={"silence_fraction": 1.0},
                     probe_floors={"silence_fraction": 0.3},
                     beta_robust=0.5)
    # hinge: max(0, 0.8 - 0.3) * 1.0 = 0.5
    assert abs(res.probe_penalty - 0.5) < 1e-6
    # cells = [0.5]; mean=0.5; std=0; value = 0.5 - 0 - 0.5 = 0.0
    assert abs(res.value - 0.0) < 1e-6
