"""Directly compare the tensors passed to `ACEStepTransformer2DModel.decode`
during pipeline sampling vs. during AceStepModel.predict_velocity reconstruction.

This isolates H2 (text-encoder cpu_offload state) and H3 (condition cache
ordering) from H1 (timestep dtype). For one prompt × one seed:

1. Spy on every `.decode(...)` call during sampling, capturing all kwargs.
2. Identify the step index whose σ ≈ 0.5 (a checkpoint inside the guidance
   interval where pipeline does cond + null CFG mixing).
3. Call predict_velocity at the same (z, σ, prompt) and spy on its `.decode`
   calls (one cond + one null pair).
4. Diff: hidden_states, attention_mask, encoder_hidden_states,
   encoder_hidden_mask, timestep — for both cond and null branches.

Output: which input tensor(s) differ, by how much, and dtype/shape info.
"""
from __future__ import annotations

import sys
from collections import OrderedDict

import torch

from mprm.common.seeding import seed_everything
from mprm.data.prompts import Prompt


def _summarize(name, t):
    if not torch.is_tensor(t):
        return f"{name}=<not tensor: {type(t).__name__}>"
    return (f"{name}: dtype={t.dtype} shape={tuple(t.shape)} "
            f"min={float(t.float().min()):.4e} max={float(t.float().max()):.4e} "
            f"mean={float(t.float().mean()):.4e} sum_abs={float(t.float().abs().sum()):.4e}")


def _diff(name, a, b):
    if (a is None) != (b is None):
        return f"{name}: one is None (pipeline={a is None}, predict_v={b is None})"
    if a is None:
        return f"{name}: both None ✓"
    af, bf = a.detach().float().cpu(), b.detach().float().cpu()
    if af.shape != bf.shape:
        return f"{name}: SHAPE DIFF pipeline={tuple(af.shape)} predict_v={tuple(bf.shape)}"
    d = (af - bf).abs()
    max_abs = float(d.max())
    mean_abs = float(d.mean())
    rel = mean_abs / max(float(bf.abs().mean()), 1e-12)
    marker = "✓" if max_abs < 1e-6 else ("≈" if max_abs < 1e-3 else "✗")
    return (f"{name}: {marker} max_abs={max_abs:.4e} mean_abs={mean_abs:.4e} "
            f"rel={rel:.4e} | dtypes pipe={a.dtype} pv={b.dtype} | "
            f"shapes pipe={tuple(a.shape)} pv={tuple(b.shape)}")


def main() -> int:
    seed_everything(42)
    from mprm.inference.ace_step import AceStepModel
    import acestep.models.ace_step_transformer as t_mod

    model = AceStepModel()
    prompt = Prompt(prompt_id="diff_00",
                    text="a calm acoustic guitar melody with no vocals",
                    lyrics=None, structure_hint=None, duration_target=10.0)

    captured_pipeline_calls: list[dict] = []
    captured_predictv_calls: list[dict] = []
    spy_mode = ["pipeline"]  # mutable list so closure can update

    _orig_decode = t_mod.ACEStepTransformer2DModel.decode

    def _spy_decode(self, *args, hidden_states=None, attention_mask=None,
                    encoder_hidden_states=None, encoder_hidden_mask=None,
                    timestep=None, output_length=0, **kwargs):
        # Clone-detach every input tensor so the model can move them around freely.
        snap = OrderedDict(
            hidden_states=hidden_states.detach().clone() if torch.is_tensor(hidden_states) else hidden_states,
            attention_mask=attention_mask.detach().clone() if torch.is_tensor(attention_mask) else attention_mask,
            encoder_hidden_states=encoder_hidden_states.detach().clone() if torch.is_tensor(encoder_hidden_states) else encoder_hidden_states,
            encoder_hidden_mask=encoder_hidden_mask.detach().clone() if torch.is_tensor(encoder_hidden_mask) else encoder_hidden_mask,
            timestep=timestep.detach().clone() if torch.is_tensor(timestep) else timestep,
            output_length=output_length,
        )
        bucket = captured_pipeline_calls if spy_mode[0] == "pipeline" else captured_predictv_calls
        bucket.append(snap)
        return _orig_decode(self, *args, hidden_states=hidden_states,
                             attention_mask=attention_mask,
                             encoder_hidden_states=encoder_hidden_states,
                             encoder_hidden_mask=encoder_hidden_mask,
                             timestep=timestep,
                             output_length=output_length,
                             **kwargs)

    t_mod.ACEStepTransformer2DModel.decode = _spy_decode

    # --- Pipeline sample with spy active ---
    spy_mode[0] = "pipeline"
    res = model.sample(prompt, seed=42, cfg_scale=5.0, steps=30,
                        return_trajectory=True,
                        extras={"cfg_type": "cfg",
                                 "use_erg_tag": False,
                                 "use_erg_lyric": False,
                                 "use_erg_diffusion": False})
    traj_sigmas = (res.extras or {}).get("trajectory_sigmas", [])
    print(f"\nPipeline made {len(captured_pipeline_calls)} decode() calls during sampling.")
    print(f"Trajectory has {len(traj_sigmas)} steps; first σ values: "
          f"{[round(s, 4) for s in traj_sigmas[:6]]}")

    # Pick the trajectory step closest to σ≈0.5 (inside guidance interval).
    target_sigma = 0.5
    k = min(range(len(traj_sigmas)), key=lambda i: abs(traj_sigmas[i] - target_sigma))
    sigma_actual = float(traj_sigmas[k])
    print(f"\nChose trajectory step k={k}, σ_actual={sigma_actual:.6f}")

    # Pipeline does TWO decode calls per step inside the guidance interval
    # (cond + uncond). Map: step k → decode calls (2*k, 2*k+1) inside the
    # interval [start_idx, end_idx) = [7, 22). Outside, only one call per step.
    # Easier: find decode calls whose `timestep` value matches σ*1000.
    timestep_target = sigma_actual * 1000.0
    pipe_at_step = [c for c in captured_pipeline_calls
                    if torch.is_tensor(c["timestep"]) and
                       abs(float(c["timestep"][0].item()) - timestep_target) < 0.5]
    print(f"Found {len(pipe_at_step)} pipeline decode() calls at σ≈{sigma_actual:.3f} "
          f"(timestep≈{timestep_target:.2f})")
    for i, c in enumerate(pipe_at_step):
        ehs = c["encoder_hidden_states"]
        ehs_sum = float(ehs.float().abs().sum()) if torch.is_tensor(ehs) else float("nan")
        print(f"  pipe call {i}: encoder_hidden_states sum_abs={ehs_sum:.4e}  "
              f"(cond branch if sum_abs > 0; null branch if ≈ small)")

    # --- predict_velocity with spy ---
    spy_mode[0] = "predictv"
    condition_cache = model._build_condition_cache(prompt)
    z_k = res.trajectory[k]
    v_pred = model.predict_velocity(z_k, sigma_actual, prompt,
                                     cfg_scale=5.0,
                                     condition_cache=condition_cache)
    print(f"\npredict_velocity made {len(captured_predictv_calls)} decode() calls.")

    if len(pipe_at_step) < 2 or len(captured_predictv_calls) < 2:
        print(f"WARN: expected 2 calls each (cond + null). "
              f"pipe={len(pipe_at_step)}, predictv={len(captured_predictv_calls)}.")

    # Pair: pipeline call 0 = cond (larger encoder_hidden_states magnitude)
    # vs pipeline call 1 = null (zeros-driven). predict_velocity also runs
    # cond first (line 695), null second (line 704).
    print("\n=== INPUT TENSOR DIFF: pipeline vs predict_velocity ===")
    for branch_idx, branch_name in enumerate(["COND (text+lyric+speaker)", "NULL (zero-driven)"]):
        if branch_idx >= len(pipe_at_step) or branch_idx >= len(captured_predictv_calls):
            print(f"  [{branch_name}] skipped (not enough captured calls)")
            continue
        p = pipe_at_step[branch_idx]
        q = captured_predictv_calls[branch_idx]
        print(f"\n  [{branch_name}]")
        for key in ("hidden_states", "attention_mask",
                    "encoder_hidden_states", "encoder_hidden_mask",
                    "timestep"):
            print(f"    {_diff(key, p[key], q[key])}")
        print(f"    output_length: pipe={p['output_length']} predictv={q['output_length']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
